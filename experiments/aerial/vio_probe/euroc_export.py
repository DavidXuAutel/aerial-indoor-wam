"""Export indoor ``episode_*.npz`` to EuRoC ASL layout for OpenVINS offline."""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np

from experiments.aerial.vio_probe.frames import (
    T_IMU_CAM_NEU_FORWARD,
    convert_airsim_imu_to_openvins,
)
from experiments.aerial.vio_probe.traj_io import write_tum_trajectory, yaw_to_quat_wxyz

try:
    import cv2
except ImportError:  # pragma: no cover
    cv2 = None  # type: ignore


def pinhole_from_hfov(width: int, height: int, hfov_deg: float = 90.0) -> Dict[str, float]:
    """Simple pinhole K from HFOV (matches indoor teleop overlay assumption)."""
    hfov = math.radians(float(hfov_deg))
    fx = (width / 2.0) / math.tan(hfov / 2.0)
    fy = fx
    return {
        "fx": float(fx),
        "fy": float(fy),
        "cx": float(width) / 2.0,
        "cy": float(height) / 2.0,
        "width": float(width),
        "height": float(height),
        "hfov_deg": float(hfov_deg),
    }


def _ns(t_s: float, t0_s: float) -> int:
    return int(round((float(t_s) - float(t0_s)) * 1e9))


def _imu_rows_from_gt_consistent(
    timestamps: np.ndarray,
    positions: np.ndarray,
    yaws: np.ndarray,
    *,
    t0: float,
    imu_rate_hz: float,
    gravity_mag: float = 10.10,
) -> list:
    """Synthesize body IMU consistent with NEU GT (thrifty sim self-check).

    OpenVINS: ``a_world = Rᵀ â − g`` with ``g=[0,0,+g]`` ⇒ ``â = R(a_world+g)``.
    Not a substitute for real IMU / robot calib.
    """
    ts = np.asarray(timestamps, dtype=np.float64).reshape(-1)
    pos = np.asarray(positions, dtype=np.float64).reshape(-1, 3)
    yaw = np.asarray(yaws, dtype=np.float64).reshape(-1)
    n = int(ts.shape[0])
    vel = np.zeros_like(pos)
    if n >= 2:
        for i in range(n):
            i0 = max(0, i - 1)
            i1 = min(n - 1, i + 1)
            dt = float(ts[i1] - ts[i0])
            if dt > 1e-6:
                vel[i] = (pos[i1] - pos[i0]) / dt
    acc_w = np.zeros_like(pos)
    for i in range(n):
        i0 = max(0, i - 1)
        i1 = min(n - 1, i + 1)
        dt = float(ts[i1] - ts[i0])
        if dt > 1e-6:
            acc_w[i] = (vel[i1] - vel[i0]) / dt
    yaw_rate = np.zeros(n)
    for i in range(n):
        i0 = max(0, i - 1)
        i1 = min(n - 1, i + 1)
        dt = float(ts[i1] - ts[i0])
        if dt > 1e-6:
            dy = float(yaw[i1] - yaw[i0])
            while dy > np.pi:
                dy -= 2 * np.pi
            while dy < -np.pi:
                dy += 2 * np.pi
            yaw_rate[i] = dy / dt

    g = np.array([0.0, 0.0, float(gravity_mag)], dtype=np.float64)
    rows = []
    dt_imu = 1.0 / float(imu_rate_hz)
    for i in range(n - 1):
        t_a, t_b = float(ts[i]), float(ts[i + 1])
        c, s = np.cos(float(yaw[i])), np.sin(float(yaw[i]))
        # body→world yaw-only; a_hat = R (a_w + g)
        R = np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]], dtype=np.float64)
        a_hat = R @ (acc_w[i] + g)
        w_i = np.array([0.0, 0.0, float(yaw_rate[i])], dtype=np.float64)
        t = t_a
        while t < t_b - 1e-9:
            rows.append((_ns(t, t0), w_i[0], w_i[1], w_i[2], a_hat[0], a_hat[1], a_hat[2]))
            t += dt_imu
    # last
    c, s = np.cos(float(yaw[-1])), np.sin(float(yaw[-1]))
    R = np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]], dtype=np.float64)
    a_hat = R @ (acc_w[-1] + g)
    w_i = np.array([0.0, 0.0, float(yaw_rate[-1])], dtype=np.float64)
    rows.append(
        (_ns(float(ts[-1]), t0), w_i[0], w_i[1], w_i[2], a_hat[0], a_hat[1], a_hat[2])
    )
    return rows


def export_episode_npz_to_euroc(
    npz_path: Path,
    out_dir: Path,
    *,
    hfov_deg: float = 90.0,
    imu_rate_assume_hz: float = 200.0,
    sensor_yaml_name: str = "sensor_camera.yaml",
    resize_hw: Optional[Tuple[int, int]] = None,
    imu_mode: str = "airsim",
    gravity_mag: float = 10.10,
) -> Dict[str, Any]:
    """Write EuRoC-ish folder from one episode npz.

    ``imu_mode``:
      * ``airsim`` — ZOH of AirSim NED IMU → NEU (flip z); **not** thrifty-quality
      * ``gt_consistent`` — synthesize IMU from GT (experimental)
      * ``hover`` — constant ``a=[0,0,g]``, ``w=0`` (thrifty plumbing / no free-fall gate)
    """
    if cv2 is None:
        raise RuntimeError("opencv-python required for EuRoC image export")

    npz_path = Path(npz_path)
    out_dir = Path(out_dir)
    raw = np.load(npz_path)
    if "rgb" not in raw.files and "rgb_vio" not in raw.files:
        raise ValueError(f"{npz_path} missing rgb / rgb_vio")
    # Prefer native capture branch for VIO (same grab as WAM ``rgb``, not a 2nd cam).
    if "rgb_vio" in raw.files:
        rgb = np.asarray(raw["rgb_vio"])
    else:
        rgb = np.asarray(raw["rgb"])
    n = int(rgb.shape[0])
    if n < 2:
        raise ValueError("need >=2 frames")
    h, w = int(rgb.shape[1]), int(rgb.shape[2])
    if resize_hw is not None:
        rh, rw = int(resize_hw[0]), int(resize_hw[1])
        rgb = np.stack(
            [cv2.resize(rgb[i], (rw, rh), interpolation=cv2.INTER_LINEAR) for i in range(n)],
            axis=0,
        )
        h, w = rh, rw
    proprio = np.asarray(raw["proprio"], dtype=np.float64)
    timestamps = (
        np.asarray(raw["timestamps"], dtype=np.float64)
        if "timestamps" in raw.files
        else np.arange(n, dtype=np.float64) * 0.2
    )
    imu_ang = (
        np.asarray(raw["imu_ang_vel"], dtype=np.float64)
        if "imu_ang_vel" in raw.files
        else np.full((n, 3), np.nan)
    )
    imu_acc = (
        np.asarray(raw["imu_lin_acc"], dtype=np.float64)
        if "imu_lin_acc" in raw.files
        else np.full((n, 3), np.nan)
    )
    imu_present = (
        np.asarray(raw["imu_present"], dtype=bool)
        if "imu_present" in raw.files
        else np.ones(n, dtype=bool)
    )

    t0 = float(timestamps[0])
    cam_dir = out_dir / "mav0" / "cam0" / "data"
    cam_dir.mkdir(parents=True, exist_ok=True)
    imu_dir = out_dir / "mav0" / "imu0"
    imu_dir.mkdir(parents=True, exist_ok=True)
    gt_dir = out_dir / "mav0" / "state_groundtruth_estimate0"
    gt_dir.mkdir(parents=True, exist_ok=True)

    cam_csv = out_dir / "mav0" / "cam0" / "data.csv"
    with cam_csv.open("w", newline="", encoding="utf-8") as f:
        # lineterminator='\n' — default csv \r\n breaks C++ filename parse (trailing \r)
        wri = csv.writer(f, lineterminator="\n")
        wri.writerow(["#timestamp [ns]", "filename"])
        for i in range(n):
            ts_ns = _ns(timestamps[i], t0)
            name = f"{ts_ns}.png"
            bgr = cv2.cvtColor(rgb[i], cv2.COLOR_RGB2BGR)
            cv2.imwrite(str(cam_dir / name), bgr)
            wri.writerow([ts_ns, name])

    # Upsample IMU ZOH between frames (or synthesize from GT).
    imu_mode_l = str(imu_mode or "airsim").lower()
    if imu_mode_l in ("hover", "gravity", "static_imu"):
        imu_rows = []
        dt_imu = 1.0 / float(imu_rate_assume_hz)
        g = float(gravity_mag)
        t_end = float(timestamps[-1])
        t = float(timestamps[0])
        while t <= t_end + 1e-9:
            imu_rows.append((_ns(t, t0), 0.0, 0.0, 0.0, 0.0, 0.0, g))
            t += dt_imu
    elif imu_mode_l in ("gt_consistent", "gt", "from_gt"):
        imu_rows = _imu_rows_from_gt_consistent(
            timestamps,
            proprio[:, :3],
            proprio[:, 3],
            t0=t0,
            imu_rate_hz=imu_rate_assume_hz,
            gravity_mag=gravity_mag,
        )
    else:
        imu_rows = []
        dt_imu = 1.0 / float(imu_rate_assume_hz)
        for i in range(n - 1):
            t_a, t_b = float(timestamps[i]), float(timestamps[i + 1])
            if not imu_present[i] or not np.all(np.isfinite(imu_ang[i])) or not np.all(
                np.isfinite(imu_acc[i])
            ):
                w_i = np.zeros(3, dtype=np.float64)
                a_i = np.array([0.0, 0.0, float(gravity_mag)], dtype=np.float64)
            else:
                w_i = imu_ang[i].copy()
                a_i = imu_acc[i].copy()
                w_i, a_i = convert_airsim_imu_to_openvins(w_i, a_i)
            t = t_a
            while t < t_b - 1e-9:
                imu_rows.append((_ns(t, t0), w_i[0], w_i[1], w_i[2], a_i[0], a_i[1], a_i[2]))
                t += dt_imu
        i = n - 1
        if imu_present[i] and np.all(np.isfinite(imu_ang[i])) and np.all(np.isfinite(imu_acc[i])):
            w_i, a_i = convert_airsim_imu_to_openvins(imu_ang[i], imu_acc[i])
        else:
            w_i = np.zeros(3)
            a_i = np.array([0.0, 0.0, float(gravity_mag)])
        imu_rows.append(
            (_ns(timestamps[i], t0), w_i[0], w_i[1], w_i[2], a_i[0], a_i[1], a_i[2])
        )

    imu_csv = imu_dir / "data.csv"
    with imu_csv.open("w", newline="", encoding="utf-8") as f:
        wri = csv.writer(f, lineterminator="\n")
        wri.writerow(
            [
                "#timestamp [ns]",
                "w_RS_S_x [rad s^-1]",
                "w_RS_S_y [rad s^-1]",
                "w_RS_S_z [rad s^-1]",
                "a_RS_S_x [m s^-2]",
                "a_RS_S_y [m s^-2]",
                "a_RS_S_z [m s^-2]",
            ]
        )
        for row in imu_rows:
            wri.writerow(row)

    gt_csv = gt_dir / "data.csv"
    quats = []
    positions = proprio[:, :3].copy()
    with gt_csv.open("w", newline="", encoding="utf-8") as f:
        wri = csv.writer(f, lineterminator="\n")
        wri.writerow(
            [
                "#timestamp",
                "p_RS_R_x [m]",
                "p_RS_R_y [m]",
                "p_RS_R_z [m]",
                "q_RS_w",
                "q_RS_x",
                "q_RS_y",
                "q_RS_z",
                "v_RS_R_x [m s^-1]",
                "v_RS_R_y [m s^-1]",
                "v_RS_R_z [m s^-1]",
                "b_w_RS_S_x [rad s^-1]",
                "b_w_RS_S_y [rad s^-1]",
                "b_w_RS_S_z [rad s^-1]",
                "b_a_RS_S_x [m s^-2]",
                "b_a_RS_S_y [m s^-2]",
                "b_a_RS_S_z [m s^-2]",
            ]
        )
        vel = (
            np.asarray(raw["vel"], dtype=np.float64)
            if "vel" in raw.files
            else np.zeros((n, 3))
        )
        for i in range(n):
            q = yaw_to_quat_wxyz(float(proprio[i, 3]))
            quats.append(q)
            wri.writerow(
                [
                    _ns(timestamps[i], t0),
                    positions[i, 0],
                    positions[i, 1],
                    positions[i, 2],
                    q[0],
                    q[1],
                    q[2],
                    q[3],
                    vel[i, 0],
                    vel[i, 1],
                    vel[i, 2],
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                ]
            )
    quats_a = np.stack(quats, axis=0)
    # TUM times relative to t0 — same time base as EuRoC cam/IMU and ov_euroc_offline.
    tum_rel = np.asarray(timestamps, dtype=np.float64) - float(t0)
    tum_path = write_tum_trajectory(
        out_dir / "gt_tum.txt", tum_rel, positions, quats_a
    )

    K = pinhole_from_hfov(w, h, hfov_deg=hfov_deg)
    meta = {
        "source_npz": str(npz_path.resolve()),
        "n_frames": n,
        "n_imu_rows": len(imu_rows),
        "imu_rate_assume_hz": float(imu_rate_assume_hz),
        "imu_upsample": "zero_order_hold",
        "imu_mode": imu_mode_l,
        "imu_frame": "neu_body_from_airsim_ned_flip_z"
        if imu_mode_l == "airsim"
        else "neu_body_from_gt",
        "world_frame": "neu_up",
        "T_imu_cam": T_IMU_CAM_NEU_FORWARD,
        "camera": K,
        "gravity_mag": float(gravity_mag),
        "note": (
            "Thrifty sim export. imu_mode=%s. Not robot calib." % imu_mode_l
        ),
        "t0_s": t0,
        "gt_tum": str(tum_path.name),
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    # Minimal camera yaml for human / future OpenVINS config copy
    yaml_path = out_dir / sensor_yaml_name
    yaml_path.write_text(
        "\n".join(
            [
                f"# placeholder camera model for {npz_path.name}",
                f"image_width: {w}",
                f"image_height: {h}",
                f"fx: {K['fx']}",
                f"fy: {K['fy']}",
                f"cx: {K['cx']}",
                f"cy: {K['cy']}",
                f"hfov_deg: {hfov_deg}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    meta["sensor_yaml"] = str(yaml_path.name)
    return meta


def make_synthetic_episode_npz(path: Path, *, n: int = 40, dt: float = 0.2) -> Path:
    """Tiny RGB+IMU episode for dry-run without AirSim."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    h = w = 64
    rgb = np.zeros((n, h, w, 3), dtype=np.uint8)
    proprio = np.zeros((n, 4), dtype=np.float32)
    vel = np.zeros((n, 3), dtype=np.float32)
    imu_ang = np.zeros((n, 3), dtype=np.float32)
    imu_acc = np.zeros((n, 3), dtype=np.float32)
    imu_acc[:, 2] = 9.81
    ts = np.arange(n, dtype=np.float32) * float(dt)
    for i in range(n):
        # textured strip so VIO would have features if run
        rgb[i, :, :, 0] = (np.arange(w)[None, :] * (i + 3)) % 255
        rgb[i, :, :, 1] = (np.arange(h)[:, None] * (i + 7)) % 255
        rgb[i, :, :, 2] = 40
        proprio[i, 0] = 0.15 * i  # forward
        proprio[i, 2] = 1.8
        vel[i, 0] = 0.15 / dt
    np.savez_compressed(
        path,
        rgb=rgb,
        proprio=proprio,
        actions=np.zeros((n, 4), dtype=np.float32),
        rewards=np.zeros(n, dtype=np.float32),
        dones=np.zeros(n, dtype=bool),
        collided=np.zeros(n, dtype=bool),
        vel=vel,
        imu_ang_vel=imu_ang,
        imu_lin_acc=imu_acc,
        imu_present=np.ones(n, dtype=bool),
        timestamps=ts,
        goal=np.array([10.0, 0.0, 1.8], dtype=np.float32),
    )
    return path
