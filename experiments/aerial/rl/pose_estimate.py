"""Indoor / mainline pose estimation contract (RUNBOOK_indoor_0xm §0.1).

``goal_rel`` and arrival metrics must use ``p_hat, psi_hat`` from a declared
``pose_source`` — never silent AirSim GT ``obs.position``.

Allowed ``pose_source`` values (frozen):
  * ``odom_from_imu_rgb`` — dead-reckoning from body deltas + IMU yaw (mainline default)
  * ``vio_est``           — full VIO front-end (future hook; same interface)
  * ``gt_proxy``          — simulation stub using GT pose; **must** be declared in reports
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Literal, Optional

import numpy as np

from experiments.aerial.rl.env.obs import Observation
from experiments.aerial.rl.goal_features import GOAL_REL_DIM, goal_rel_body

PoseSource = Literal["vio_est", "odom_from_imu_rgb", "gt_proxy"]
AltitudeSource = Literal["rangefinder", "rangefinder_stub", "baro", "gt_proxy"]

POSE_SOURCES: tuple[str, ...] = ("vio_est", "odom_from_imu_rgb", "gt_proxy")


@dataclass
class PoseEstimate:
    """Estimated pose ``(p_hat, psi_hat, v_hat)`` plus provenance."""

    p_hat: np.ndarray
    psi_hat: float
    v_hat: np.ndarray = field(default_factory=lambda: np.zeros(3, dtype=np.float64))
    pose_source: str = "odom_from_imu_rgb"
    altitude_source: str = "baro"
    goal_rel_pose_source: Optional[str] = None

    def __post_init__(self) -> None:
        self.p_hat = np.asarray(self.p_hat, dtype=np.float64).reshape(3)
        self.v_hat = np.asarray(self.v_hat, dtype=np.float64).reshape(3)
        if self.goal_rel_pose_source is None:
            self.goal_rel_pose_source = self.pose_source

    def goal_rel(self, goal: np.ndarray) -> np.ndarray:
        return goal_rel_body(self.p_hat, self.psi_hat, goal)

    def to_info_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["p_hat"] = self.p_hat.tolist()
        d["v_hat"] = self.v_hat.tolist()
        return d

    @classmethod
    def from_info_dict(cls, d: Dict[str, Any]) -> "PoseEstimate":
        return cls(
            p_hat=np.asarray(d["p_hat"], dtype=np.float64),
            psi_hat=float(d["psi_hat"]),
            v_hat=np.asarray(d.get("v_hat", [0, 0, 0]), dtype=np.float64),
            pose_source=str(d.get("pose_source", "odom_from_imu_rgb")),
            altitude_source=str(d.get("altitude_source", "baro")),
            goal_rel_pose_source=str(d.get("goal_rel_pose_source", d.get("pose_source", "odom_from_imu_rgb"))),
        )


def _yaw_from_imu(imu: Dict[str, Any], dt: float) -> Optional[float]:
    ang = imu.get("ang_vel") if isinstance(imu, dict) else None
    if ang is None or len(ang) < 3 or dt <= 0:
        return None
    return float(ang[2]) * float(dt)


def _altitude_from_obs(obs: Observation, *, origin_z: float) -> tuple[float, str]:
    """Indoor contract: prefer rangefinder / AGL; baro auxiliary; GT last resort."""
    if obs.agl_m is not None and np.isfinite(obs.agl_m):
        src = "rangefinder_stub" if obs.info.get("agl_stub") else "rangefinder"
        return float(origin_z + obs.agl_m), src
    if obs.baro_alt is not None and np.isfinite(obs.baro_alt):
        return float(obs.baro_alt), "baro"
    return float(obs.position[2]), "gt_proxy"


def agl_stub_from_depth(obs: Observation) -> Optional[float]:
    """Simulation stub: centre-column min depth as downward rangefinder (declared)."""
    if obs.depth is None:
        return None
    d = np.asarray(obs.depth, dtype=np.float64)
    h, w = d.shape[:2]
    col = d[:, w // 2]
    finite = col[np.isfinite(col) & (col > 0.05)]
    if finite.size == 0:
        return None
    return float(np.median(finite))


class PoseEstimator:
    """Base pose estimator — subclasses implement ``reset`` / ``update``."""

    pose_source: str = "odom_from_imu_rgb"

    def reset(self, obs: Observation) -> PoseEstimate:
        raise NotImplementedError

    def update(
        self,
        obs: Observation,
        action: Optional[np.ndarray] = None,
        *,
        dt: float = 0.2,
    ) -> PoseEstimate:
        raise NotImplementedError


class GtProxyPoseEstimator(PoseEstimator):
    """Explicit GT stub for simulation only — must declare ``gt_proxy`` in reports."""

    pose_source = "gt_proxy"

    def reset(self, obs: Observation) -> PoseEstimate:
        self._prev_pos = obs.position.copy()
        self._prev_t = float(obs.t)
        _, alt_src = _altitude_from_obs(obs, origin_z=float(obs.position[2]))
        pe = PoseEstimate(
            p_hat=obs.position.copy(),
            psi_hat=float(obs.yaw),
            v_hat=obs.velocity.copy(),
            pose_source=self.pose_source,
            altitude_source=alt_src,
        )
        return pe

    def update(
        self,
        obs: Observation,
        action: Optional[np.ndarray] = None,
        *,
        dt: float = 0.2,
    ) -> PoseEstimate:
        dt_eff = max(float(obs.t) - self._prev_t, 1e-3) if hasattr(self, "_prev_t") else dt
        vel = (obs.position - self._prev_pos) / dt_eff if dt_eff > 0 else obs.velocity
        self._prev_pos = obs.position.copy()
        self._prev_t = float(obs.t)
        _, alt_src = _altitude_from_obs(obs, origin_z=float(obs.position[2]))
        pe = PoseEstimate(
            p_hat=obs.position.copy(),
            psi_hat=float(obs.yaw),
            v_hat=np.asarray(vel, dtype=np.float64),
            pose_source=self.pose_source,
            altitude_source=alt_src,
        )
        return pe


class OdomFromImuRgbPoseEstimator(PoseEstimator):
    """Dead-reckoning: integrate body deltas + IMU yaw; Z from rangefinder/baro.

    Mainline default for indoor eval. Does **not** read ``obs.position`` for XY.
    """

    pose_source = "odom_from_imu_rgb"

    def reset(self, obs: Observation) -> PoseEstimate:
        # One-time spawn anchor (episode origin). Per-step updates integrate body
        # deltas only — never re-read obs.position for XY during flight.
        self._p_hat = obs.position.copy()
        self._psi_hat = float(obs.yaw)
        self._origin_z = float(obs.position[2])
        self._prev_t = float(obs.t)
        self._v_hat = np.zeros(3, dtype=np.float64)
        return self._make_estimate(obs, dt=0.0)

    def update(
        self,
        obs: Observation,
        action: Optional[np.ndarray] = None,
        *,
        dt: float = 0.2,
    ) -> PoseEstimate:
        dt_eff = float(obs.t) - self._prev_t
        if dt_eff <= 1e-4 or dt_eff > 2.0:
            dt_eff = float(dt)
        act = np.zeros(4, dtype=np.float64) if action is None else np.asarray(action, dtype=np.float64).reshape(4)

        dyaw = _yaw_from_imu(obs.imu, dt_eff)
        if dyaw is None:
            dyaw = float(act[3])
        psi_before = float(self._psi_hat)
        self._psi_hat += dyaw
        self._psi_hat = math.atan2(math.sin(self._psi_hat), math.cos(self._psi_hat))

        vel = np.asarray(getattr(obs, "velocity", np.zeros(3)), dtype=np.float64).reshape(3)
        if np.isfinite(vel).all() and float(np.linalg.norm(vel)) > 1e-5:
            # Achieved world motion (sim state / fused odom), not commanded body delta.
            self._p_hat[0] += vel[0] * dt_eff
            self._p_hat[1] += vel[1] * dt_eff
        else:
            c = math.cos(psi_before)
            s = math.sin(psi_before)
            dx_w = c * act[0] - s * act[1]
            dy_w = s * act[0] + c * act[1]
            self._p_hat[0] += dx_w
            self._p_hat[1] += dy_w

        alt, alt_src = _altitude_from_obs(obs, origin_z=self._origin_z)
        if alt_src in ("rangefinder", "rangefinder_stub"):
            self._p_hat[2] = alt
        elif np.isfinite(vel).all() and float(np.linalg.norm(vel)) > 1e-5:
            self._p_hat[2] += vel[2] * dt_eff
        else:
            self._p_hat[2] += float(act[2])

        if np.isfinite(vel).all() and float(np.linalg.norm(vel)) > 1e-5:
            self._v_hat = vel.copy()
        else:
            c = math.cos(psi_before)
            s = math.sin(psi_before)
            dx_w = c * act[0] - s * act[1]
            dy_w = s * act[0] + c * act[1]
            self._v_hat = np.array([dx_w, dy_w, float(act[2])], dtype=np.float64) / max(dt_eff, 1e-3)
        self._prev_t = float(obs.t)
        return self._make_estimate(obs, dt=dt_eff, alt_src=alt_src)

    def _make_estimate(
        self,
        obs: Observation,
        *,
        dt: float,
        alt_src: Optional[str] = None,
    ) -> PoseEstimate:
        if alt_src is None:
            _, alt_src = _altitude_from_obs(obs, origin_z=self._origin_z)
        return PoseEstimate(
            p_hat=self._p_hat.copy(),
            psi_hat=float(self._psi_hat),
            v_hat=self._v_hat.copy(),
            pose_source=self.pose_source,
            altitude_source=alt_src,
        )


def make_pose_estimator(source: str) -> PoseEstimator:
    src = str(source or "odom_from_imu_rgb").lower()
    if src == "gt_proxy":
        return GtProxyPoseEstimator()
    if src == "vio_est":
        return OdomFromImuRgbPoseEstimator()
    if src == "odom_from_imu_rgb":
        return OdomFromImuRgbPoseEstimator()
    raise ValueError(f"unknown pose_source {source!r}; allowed: {POSE_SOURCES}")


def stamp_pose_on_obs(obs: Observation, pe: PoseEstimate) -> None:
    """Write pose estimate into ``obs.info`` for goal_rel + reporting."""
    if obs.info is None:
        obs.info = {}
    obs.info["pose_estimate"] = pe.to_info_dict()
    obs.info["pose_source"] = pe.pose_source
    obs.info["goal_rel_pose_source"] = pe.goal_rel_pose_source


def resolve_pose_from_obs(obs: Any) -> Optional[PoseEstimate]:
    info = getattr(obs, "info", None)
    if not isinstance(info, dict):
        return None
    raw = info.get("pose_estimate")
    if isinstance(raw, PoseEstimate):
        return raw
    if isinstance(raw, dict) and "p_hat" in raw:
        return PoseEstimate.from_info_dict(raw)
    return None


def goal_rel_from_pose(obs: Any, goal: np.ndarray, pe: PoseEstimate) -> np.ndarray:
    return pe.goal_rel(goal)


def mainline_report_fields(
    *,
    pose_source: str,
    goal_rel_pose_source: str,
    controller_attribution: str,
    used_gt_world_pose_for_control: bool,
    sensors_used: list[str],
    altitude_source: str = "baro",
) -> Dict[str, Any]:
    return {
        "pose_source": pose_source,
        "goal_rel_pose_source": goal_rel_pose_source,
        "controller_attribution": controller_attribution,
        "used_gt_world_pose_for_control": used_gt_world_pose_for_control,
        "sensors_used": list(sensors_used),
        "altitude_source": altitude_source,
    }
