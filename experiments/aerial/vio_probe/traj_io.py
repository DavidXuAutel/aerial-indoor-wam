"""Trajectory I/O (TUM / OpenVINS-style) and pose helpers."""
from __future__ import annotations

from pathlib import Path
from typing import Tuple

import numpy as np


def yaw_to_quat_wxyz(yaw: float) -> np.ndarray:
    """ENU yaw (rad) → quaternion ``[qw, qx, qy, qz]`` (rotation about +Z)."""
    half = 0.5 * float(yaw)
    return np.array([np.cos(half), 0.0, 0.0, np.sin(half)], dtype=np.float64)


def quat_wxyz_to_yaw(q: np.ndarray) -> float:
    """Extract yaw from ``[qw, qx, qy, qz]`` (ZYX-ish; flat flight)."""
    qw, qx, qy, qz = (float(x) for x in np.asarray(q, dtype=np.float64).reshape(4))
    # yaw from quaternion (assuming small roll/pitch for planar MAV)
    siny_cosp = 2.0 * (qw * qz + qx * qy)
    cosy_cosp = 1.0 - 2.0 * (qy * qy + qz * qz)
    return float(np.arctan2(siny_cosp, cosy_cosp))


def write_tum_trajectory(
    path: Path,
    timestamps_s: np.ndarray,
    positions: np.ndarray,
    quats_wxyz: np.ndarray,
) -> Path:
    """Write TUM RGB-D format: ``t px py pz qx qy qz qw`` (note qx..qw order)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    ts = np.asarray(timestamps_s, dtype=np.float64).reshape(-1)
    pos = np.asarray(positions, dtype=np.float64).reshape(-1, 3)
    quat = np.asarray(quats_wxyz, dtype=np.float64).reshape(-1, 4)
    if not (ts.shape[0] == pos.shape[0] == quat.shape[0]):
        raise ValueError("timestamps/positions/quats length mismatch")
    with path.open("w", encoding="utf-8") as f:
        f.write("# timestamp tx ty tz qx qy qz qw\n")
        for t, p, q in zip(ts, pos, quat):
            qw, qx, qy, qz = q
            f.write(
                f"{t:.9f} {p[0]:.9f} {p[1]:.9f} {p[2]:.9f} "
                f"{qx:.9f} {qy:.9f} {qz:.9f} {qw:.9f}\n"
            )
    return path


def load_tum_trajectory(path: Path) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Load TUM traj → ``(t[N], pos[N,3], quat_wxyz[N,4])``."""
    rows = []
    with Path(path).open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 8:
                continue
            t, px, py, pz, qx, qy, qz, qw = (float(x) for x in parts[:8])
            rows.append((t, px, py, pz, qw, qx, qy, qz))
    if not rows:
        raise ValueError(f"no poses in {path}")
    arr = np.asarray(rows, dtype=np.float64)
    return arr[:, 0], arr[:, 1:4], arr[:, 4:8]


def interpolate_pose(
    query_t: float,
    timestamps_s: np.ndarray,
    positions: np.ndarray,
    quats_wxyz: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """Linear pos + yaw-slerp-ish quat at ``query_t`` (clamp to ends)."""
    ts = np.asarray(timestamps_s, dtype=np.float64).reshape(-1)
    pos = np.asarray(positions, dtype=np.float64).reshape(-1, 3)
    quat = np.asarray(quats_wxyz, dtype=np.float64).reshape(-1, 4)
    if query_t <= ts[0]:
        return pos[0].copy(), quat[0].copy()
    if query_t >= ts[-1]:
        return pos[-1].copy(), quat[-1].copy()
    i = int(np.searchsorted(ts, query_t) - 1)
    i = max(0, min(i, ts.shape[0] - 2))
    t0, t1 = ts[i], ts[i + 1]
    a = 0.0 if t1 <= t0 else (query_t - t0) / (t1 - t0)
    p = (1.0 - a) * pos[i] + a * pos[i + 1]
    # Nlerp then renormalize (adequate for MAV yaw-dominant quats)
    q = (1.0 - a) * quat[i] + a * quat[i + 1]
    n = float(np.linalg.norm(q))
    if n < 1e-12:
        q = quat[i].copy()
    else:
        q = q / n
    return p, q
