"""Live OpenVINS stream client → ``pose_source=vio_est`` for indoor closed-loop."""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Optional, Tuple

import numpy as np

from experiments.aerial.rl.env.obs import Observation
from experiments.aerial.rl.pose_estimate import PoseEstimate, PoseEstimator
from experiments.aerial.vio_probe.euroc_export import pinhole_from_hfov
from experiments.aerial.vio_probe.frames import convert_airsim_imu_to_openvins
from experiments.aerial.vio_probe.openvins_runner import resolve_openvins_bin, stage_openvins_config
from experiments.aerial.vio_probe.traj_io import quat_wxyz_to_yaw, yaw_to_quat_wxyz


def resolve_stream_bin(explicit: Optional[str | Path] = None) -> Optional[Path]:
    cand = explicit or os.environ.get("OPENVINS_STREAM_BIN")
    if cand:
        p = Path(cand).expanduser()
        return p if p.is_file() else None
    here = Path(__file__).resolve().parent / "cpp" / "build" / "ov_stream_online"
    if here.is_file():
        return here
    # Same dir as offline bin if OPENVINS_BIN points at ov_euroc_offline
    offline = resolve_openvins_bin()
    if offline is not None:
        sibling = offline.parent / "ov_stream_online"
        if sibling.is_file():
            return sibling
    return None


class OpenVinsStreamClient:
    """Line-protocol client for ``ov_stream_online``."""

    def __init__(
        self,
        config_yaml: Path,
        *,
        bin_path: Optional[Path] = None,
        work_dir: Optional[Path] = None,
    ) -> None:
        binary = resolve_stream_bin(bin_path)
        if binary is None:
            raise RuntimeError(
                "ov_stream_online not found; set OPENVINS_STREAM_BIN or build "
                "experiments/aerial/vio_probe/cpp"
            )
        self.work_dir = Path(work_dir or tempfile.mkdtemp(prefix="ov_stream_"))
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self._img_i = 0
        self._proc = subprocess.Popen(
            [str(binary), str(config_yaml)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        hello = self._readline(timeout_note="startup")
        if not hello.startswith("OK"):
            raise RuntimeError(f"ov_stream_online bad hello: {hello!r}")

    def _readline(self, *, timeout_note: str = "") -> str:
        """Read until a protocol line (OK/ERR/POSE); skip OpenVINS debug on stdout."""
        assert self._proc.stdout is not None
        while True:
            line = self._proc.stdout.readline()
            if not line:
                err = ""
                if self._proc.stderr is not None:
                    try:
                        err = self._proc.stderr.read()[-2000:]
                    except Exception:
                        err = ""
                raise RuntimeError(
                    f"ov_stream_online EOF ({timeout_note}); stderr={err!r}"
                )
            s = line.strip()
            if not s:
                continue
            if s.startswith("OK") or s.startswith("ERR") or s.startswith("POSE"):
                return s
            # OpenVINS PRINT_* noise on stdout — ignore

    def _cmd(self, line: str) -> str:
        assert self._proc.stdin is not None
        self._proc.stdin.write(line.rstrip() + "\n")
        self._proc.stdin.flush()
        return self._readline(timeout_note=line.split()[0])

    def reset(self) -> None:
        rep = self._cmd("RESET")
        if not rep.startswith("OK"):
            raise RuntimeError(f"RESET failed: {rep}")

    def gt_init(self, imustate17: np.ndarray) -> None:
        vals = " ".join(f"{float(x):.9f}" for x in np.asarray(imustate17, dtype=np.float64).reshape(17))
        rep = self._cmd(f"GTINIT {vals}")
        if not rep.startswith("OK"):
            raise RuntimeError(f"GTINIT failed: {rep}")

    def feed_imu(self, t: float, wm: np.ndarray, am: np.ndarray) -> None:
        wm = np.asarray(wm, dtype=np.float64).reshape(3)
        am = np.asarray(am, dtype=np.float64).reshape(3)
        rep = self._cmd(
            f"IMU {float(t):.9f} {wm[0]:.9f} {wm[1]:.9f} {wm[2]:.9f} "
            f"{am[0]:.9f} {am[1]:.9f} {am[2]:.9f}"
        )
        if not rep.startswith("OK"):
            raise RuntimeError(f"IMU failed: {rep}")

    def feed_cam(self, t: float, rgb_or_gray: np.ndarray) -> str:
        import cv2

        img = np.asarray(rgb_or_gray)
        if img.ndim == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        else:
            gray = img
        path = self.work_dir / f"frame_{self._img_i:06d}.png"
        self._img_i += 1
        cv2.imwrite(str(path), gray)
        rep = self._cmd(f"CAM {float(t):.9f} {path}")
        if not rep.startswith("OK"):
            raise RuntimeError(f"CAM failed: {rep}")
        return rep

    def pose(self) -> Tuple[float, np.ndarray, np.ndarray, bool, bool]:
        """Return ``(t, pos, quat_wxyz, initialized, seeded)``."""
        rep = self._cmd("POSE")
        if rep.startswith("ERR"):
            raise RuntimeError(f"POSE failed: {rep}")
        parts = rep.split()
        # POSE t px py pz qx qy qz qw init=0 seeded=0
        if len(parts) < 9 or parts[0] != "POSE":
            raise RuntimeError(f"bad POSE reply: {rep}")
        t = float(parts[1])
        pos = np.array([float(parts[2]), float(parts[3]), float(parts[4])], dtype=np.float64)
        qx, qy, qz, qw = (float(parts[5]), float(parts[6]), float(parts[7]), float(parts[8]))
        quat_wxyz = np.array([qw, qx, qy, qz], dtype=np.float64)
        init = "init=1" in rep
        seeded = "seeded=1" in rep
        return t, pos, quat_wxyz, init, seeded

    def close(self) -> None:
        try:
            if self._proc.poll() is None and self._proc.stdin is not None:
                self._proc.stdin.write("QUIT\n")
                self._proc.stdin.flush()
        except Exception:
            pass
        try:
            self._proc.kill()
        except Exception:
            pass


def _imu_from_obs(obs: Observation) -> Tuple[np.ndarray, np.ndarray]:
    """AirSim NED body IMU → ENU body for OpenVINS."""
    imu = obs.imu if isinstance(obs.imu, dict) else {}
    wm = np.asarray(imu.get("ang_vel", [0.0, 0.0, 0.0]), dtype=np.float64).reshape(3)
    am = np.asarray(imu.get("lin_acc", [0.0, 0.0, -9.81]), dtype=np.float64).reshape(3)
    return convert_airsim_imu_to_openvins(wm, am)


def _capture_rgb(obs: Observation) -> np.ndarray:
    """Prefer fan-out ``rgb_vio`` (native capture); else ``rgb``."""
    if getattr(obs, "rgb_vio", None) is not None:
        return np.asarray(obs.rgb_vio)
    return np.asarray(obs.rgb)


def sim_gt_imustate17(obs: Observation, *, gravity_mag: float = 10.10) -> np.ndarray:
    """Build OpenVINS GTINIT vector from sim ``obs`` (probe only; declare gt_seed).

    Layout: ``[t, qx,qy,qz,qw, px,py,pz, vx,vy,vz, bg(3), ba(3)]`` (JPL quat).
    ``ba`` seeded so AirSim |a|≈10.1 does not fight ``gravity_mag``.
    """
    t = float(obs.t)
    p = np.asarray(obs.position, dtype=np.float64).reshape(3)
    v = np.asarray(obs.velocity, dtype=np.float64).reshape(3)
    qw, qx, qy, qz = yaw_to_quat_wxyz(float(obs.yaw))
    wm, am = _imu_from_obs(obs)
    ba = am - np.array([0.0, 0.0, float(gravity_mag)], dtype=np.float64)
    out = np.zeros(17, dtype=np.float64)
    out[0] = t
    out[1:5] = (qx, qy, qz, qw)
    out[5:8] = p
    # Zero vel for thrifty GT seed (npz vel can be large/noisy on fixtures).
    out[8:11] = 0.0
    out[14:17] = ba
    return out


class LiveVioEstPoseEstimator(PoseEstimator):
    """Closed-loop ``vio_est`` via streaming OpenVINS.

    Env:
      * ``OPENVINS_STREAM_BIN`` / build ``ov_stream_online``
      * ``AERIAL_VIO_GT_SEED=1`` — sim-only GT seed on reset (auto-init still fails on AirSim)
      * ``AERIAL_VIO_LIVE_CONFIG_DIR`` — optional staged OpenVINS yaml dir
    """

    pose_source = "vio_est"

    def __init__(
        self,
        *,
        stream_bin: Optional[Path] = None,
        gt_seed: Optional[bool] = None,
        capture_wh: Tuple[int, int] = (640, 480),
        hfov_deg: float = 90.0,
    ) -> None:
        self.gt_seed = (
            bool(gt_seed)
            if gt_seed is not None
            else os.environ.get("AERIAL_VIO_GT_SEED", "1") not in ("0", "false", "False")
        )
        self._stream_bin = stream_bin
        self._client: Optional[OpenVinsStreamClient] = None
        self._prev_p: Optional[np.ndarray] = None
        self._prev_t: Optional[float] = None
        self._used_gt_seed = False
        w, h = int(capture_wh[0]), int(capture_wh[1])
        cam = pinhole_from_hfov(w, h, hfov_deg)
        template = Path(__file__).resolve().parent / "config" / "indoor_placeholder"
        stage = Path(
            os.environ.get(
                "AERIAL_VIO_LIVE_CONFIG_DIR",
                str(Path(tempfile.mkdtemp(prefix="ov_live_cfg_"))),
            )
        )
        self._config_yaml = stage_openvins_config(template, stage, cam)
        self._cam_wh = (w, h)

    def _ensure_client(self) -> OpenVinsStreamClient:
        if self._client is None:
            self._client = OpenVinsStreamClient(
                self._config_yaml, bin_path=self._stream_bin
            )
        return self._client

    def _push_obs(self, obs: Observation) -> PoseEstimate:
        client = self._ensure_client()
        t = float(obs.t)
        wm, am = _imu_from_obs(obs)
        client.feed_imu(t, wm, am)
        client.feed_cam(t, _capture_rgb(obs))
        _t, p, q, _init, seeded = client.pose()
        psi = quat_wxyz_to_yaw(q)
        v = np.zeros(3, dtype=np.float64)
        if self._prev_p is not None and self._prev_t is not None:
            dt = t - float(self._prev_t)
            if 1e-4 < dt < 2.0:
                v = (p - self._prev_p) / dt
        self._prev_p = p.copy()
        self._prev_t = t
        self._prev_psi = psi
        self._used_gt_seed = self._used_gt_seed or seeded
        return PoseEstimate(
            p_hat=p,
            psi_hat=psi,
            v_hat=v,
            pose_source=self.pose_source,
            altitude_source="baro",
        )

    def reset(self, obs: Observation) -> PoseEstimate:
        client = self._ensure_client()
        client.reset()
        self._prev_p = None
        self._prev_t = None
        self._prev_psi = 0.0
        self._used_gt_seed = False
        if self.gt_seed:
            client.gt_init(sim_gt_imustate17(obs))
            self._used_gt_seed = True
            # stamp info for reports
            if obs.info is None:
                obs.info = {}
            obs.info["vio_gt_seed"] = True
        return self._push_obs(obs)

    def update(
        self,
        obs: Observation,
        action: Optional[np.ndarray] = None,
        *,
        dt: float = 0.2,
    ) -> PoseEstimate:
        del action, dt
        if self._used_gt_seed and obs.info is not None:
            obs.info["vio_gt_seed"] = True
        return self._push_obs(obs)

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None


def make_live_vio_est_pose_estimator(**kwargs: Any) -> LiveVioEstPoseEstimator:
    return LiveVioEstPoseEstimator(**kwargs)
