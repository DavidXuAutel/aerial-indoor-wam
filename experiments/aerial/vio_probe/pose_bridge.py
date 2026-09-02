"""``vio_est`` PoseEstimator backed by an offline OpenVINS (TUM) trajectory."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import numpy as np

from experiments.aerial.rl.env.obs import Observation
from experiments.aerial.rl.pose_estimate import PoseEstimate, PoseEstimator
from experiments.aerial.vio_probe.traj_io import (
    interpolate_pose,
    load_tum_trajectory,
    quat_wxyz_to_yaw,
)


class VioEstPoseEstimator(PoseEstimator):
    """Replay OpenVINS (or any TUM) poses by ``obs.t`` — isolated offline bridge.

    Not a live frontend. Live OpenVINS IPC can replace ``_lookup`` later without
    changing ``pose_source`` / ``goal_rel`` callers.
    """

    pose_source = "vio_est"

    def __init__(self, tum_path: Path | str) -> None:
        self.tum_path = Path(tum_path)
        self._t, self._pos, self._quat = load_tum_trajectory(self.tum_path)
        self._prev_p: Optional[np.ndarray] = None
        self._prev_t: Optional[float] = None
        self._origin_z = 0.0

    def _lookup(self, t: float) -> tuple[np.ndarray, float, np.ndarray]:
        p, q = interpolate_pose(float(t), self._t, self._pos, self._quat)
        psi = quat_wxyz_to_yaw(q)
        v = np.zeros(3, dtype=np.float64)
        if self._prev_p is not None and self._prev_t is not None:
            dt = float(t) - float(self._prev_t)
            if 1e-4 < dt < 2.0:
                v = (p - self._prev_p) / dt
        return p, psi, v

    def reset(self, obs: Observation) -> PoseEstimate:
        self._prev_p = None
        self._prev_t = None
        self._origin_z = float(obs.position[2])
        p, psi, v = self._lookup(float(obs.t))
        self._prev_p = p.copy()
        self._prev_t = float(obs.t)
        return PoseEstimate(
            p_hat=p,
            psi_hat=psi,
            v_hat=v,
            pose_source=self.pose_source,
            altitude_source="baro",
        )

    def update(
        self,
        obs: Observation,
        action: Optional[np.ndarray] = None,
        *,
        dt: float = 0.2,
    ) -> PoseEstimate:
        del action, dt  # offline traj is time-indexed
        p, psi, v = self._lookup(float(obs.t))
        self._prev_p = p.copy()
        self._prev_t = float(obs.t)
        return PoseEstimate(
            p_hat=p,
            psi_hat=psi,
            v_hat=v,
            pose_source=self.pose_source,
            altitude_source="baro",
        )


def make_vio_est_pose_estimator(
    tum_path: Optional[str | Path] = None,
) -> VioEstPoseEstimator:
    """Build ``vio_est`` from ``tum_path`` or ``AERIAL_VIO_TRAJ`` env.

    Raises if unset — never silently aliases to ``odom_from_imu_rgb``.
    """
    path = tum_path or os.environ.get("AERIAL_VIO_TRAJ")
    if not path:
        raise RuntimeError(
            "pose_source=vio_est requires an OpenVINS/TUM trajectory: set "
            "AERIAL_VIO_TRAJ=/path/to/est_tum.txt or pass tum_path=. "
            "See docs/handover/INDOOR_VIO_OPENSOURCE_PROBE_20260902.md. "
            "For sim dead-reckoning use pose_source=odom_from_imu_rgb."
        )
    return VioEstPoseEstimator(path)
