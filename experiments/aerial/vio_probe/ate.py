"""Posyaw-aligned absolute trajectory error (ATE RMSE)."""
from __future__ import annotations

from typing import Any, Dict, Tuple

import numpy as np


def _yaw_align(est: np.ndarray, gt: np.ndarray) -> Tuple[np.ndarray, float, np.ndarray]:
    """Align ``est`` to ``gt`` with yaw+translation (4-DOF unobservable VIO gauge).

    Returns ``(est_aligned, yaw_rad, t_xyz)``.
    """
    est = np.asarray(est, dtype=np.float64).reshape(-1, 3)
    gt = np.asarray(gt, dtype=np.float64).reshape(-1, 3)
    if est.shape[0] != gt.shape[0] or est.shape[0] < 2:
        raise ValueError("need matching trajectories with >=2 poses")
    # Center XY for yaw estimate via Kabsch in 2D
    e_xy = est[:, :2] - est[:, :2].mean(axis=0)
    g_xy = gt[:, :2] - gt[:, :2].mean(axis=0)
    h = e_xy.T @ g_xy
    u, _, vt = np.linalg.svd(h)
    r2 = vt.T @ u.T
    if np.linalg.det(r2) < 0:
        vt = vt.copy()
        vt[-1, :] *= -1.0
        r2 = vt.T @ u.T
    yaw = float(np.arctan2(r2[1, 0], r2[0, 0]))
    c, s = np.cos(yaw), np.sin(yaw)
    r3 = np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]], dtype=np.float64)
    est_r = (r3 @ est.T).T
    t = gt.mean(axis=0) - est_r.mean(axis=0)
    return est_r + t, yaw, t


def associate_by_time(
    t_est: np.ndarray,
    pos_est: np.ndarray,
    t_gt: np.ndarray,
    pos_gt: np.ndarray,
    *,
    max_dt_s: float = 0.05,
) -> Tuple[np.ndarray, np.ndarray]:
    """Nearest-neighbor associate est→gt within ``max_dt_s``."""
    t_est = np.asarray(t_est, dtype=np.float64).reshape(-1)
    t_gt = np.asarray(t_gt, dtype=np.float64).reshape(-1)
    pos_est = np.asarray(pos_est, dtype=np.float64).reshape(-1, 3)
    pos_gt = np.asarray(pos_gt, dtype=np.float64).reshape(-1, 3)
    e_out, g_out = [], []
    for i, te in enumerate(t_est):
        j = int(np.argmin(np.abs(t_gt - te)))
        if abs(float(t_gt[j] - te)) <= max_dt_s:
            e_out.append(pos_est[i])
            g_out.append(pos_gt[j])
    if len(e_out) < 2:
        raise ValueError(f"association produced {len(e_out)} pairs; need >=2")
    return np.asarray(e_out), np.asarray(g_out)


def ate_rmse_posyaw(
    t_est: np.ndarray,
    pos_est: np.ndarray,
    t_gt: np.ndarray,
    pos_gt: np.ndarray,
    *,
    max_dt_s: float = 0.05,
) -> Dict[str, Any]:
    """Compute posyaw-aligned ATE RMSE (metres)."""
    e, g = associate_by_time(t_est, pos_est, t_gt, pos_gt, max_dt_s=max_dt_s)
    aligned, yaw, tvec = _yaw_align(e, g)
    err = np.linalg.norm(aligned - g, axis=1)
    return {
        "n_pairs": int(err.shape[0]),
        "ate_rmse_m": float(np.sqrt(np.mean(err ** 2))),
        "ate_mean_m": float(np.mean(err)),
        "ate_median_m": float(np.median(err)),
        "ate_max_m": float(np.max(err)),
        "align_yaw_rad": float(yaw),
        "align_t_m": [float(x) for x in tvec],
        "max_dt_s": float(max_dt_s),
    }
