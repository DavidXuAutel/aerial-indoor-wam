"""Indoor Altitude, Odometry & Two-Phase Visual Servoing Controllers.

Provides:
  1. AltitudeLockController: Decoupled Z-axis geometric altitude hold using
     altimeter / barometer / ToF relative to initial or target ceiling.
  2. RelativeOdometryTracker: Tracks local incremental pose [dx, dy, dz, dyaw]
     in body or local odometry frame for GPS-denied navigation.
  3. VisualServoingController: Near-field Image-Based / Geometric Visual Servoing
     with dynamic action P-tapering for terminal 0.xm (0.1m~0.2m) positioning.
  4. TwoPhaseIndoorController: Unified coordinator transitioning smoothly from
     coarse WAM latent cruising to near-field visual servoing.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional, Tuple

import numpy as np

from experiments.aerial.rl.env.obs import Observation


@dataclass
class AltitudeLockController:
    """Decoupled Z-axis PD controller for indoor altitude locking.

    In indoor environments (height ~ 2.5m - 3.5m), vertical altitude is held
    tightly around a desired target height (e.g. 1.2m above floor or initial altitude)
    to prevent ceiling/ground strikes while the WAM policy focuses on X-Y-Yaw navigation.
    """

    kp: float = 1.2
    kd: float = 0.5
    max_dz: float = 0.08      # max vertical per-step delta (m)
    target_alt: Optional[float] = None
    _prev_alt: Optional[float] = None

    def reset(self, initial_alt: Optional[float] = None) -> None:
        self.target_alt = initial_alt
        self._prev_alt = initial_alt

    def step(self, current_alt: float, dt: float = 0.2) -> float:
        """Compute the corrective dz command."""
        if self.target_alt is None:
            self.target_alt = current_alt
            self._prev_alt = current_alt
            return 0.0

        error = self.target_alt - current_alt
        d_alt = (current_alt - self._prev_alt) / max(dt, 1e-3) if self._prev_alt is not None else 0.0
        self._prev_alt = current_alt

        dz_cmd = self.kp * error - self.kd * d_alt
        dz_clipped = float(np.clip(dz_cmd * dt, -self.max_dz, self.max_dz))
        return dz_clipped


@dataclass
class RelativeOdometryTracker:
    """Tracks local body-frame relative displacement and velocity."""

    _last_pos: Optional[np.ndarray] = None
    _last_yaw: Optional[float] = None
    _origin_pos: Optional[np.ndarray] = None
    _origin_yaw: Optional[float] = None

    def reset(self, obs: Observation) -> None:
        self._origin_pos = obs.position.copy()
        self._origin_yaw = float(obs.yaw)
        self._last_pos = obs.position.copy()
        self._last_yaw = float(obs.yaw)

    def update(self, obs: Observation) -> Tuple[np.ndarray, np.ndarray]:
        """Returns:
          rel_step_body: [dx, dy, dz, dyaw] relative to step t-1 in body frame.
          cum_odom_rel: [dx, dy, dz, dyaw] cumulative displacement from episode start.
        """
        curr_pos = obs.position
        curr_yaw = float(obs.yaw)

        if self._last_pos is None:
            self.reset(obs)
            return np.zeros(4, dtype=np.float64), np.zeros(4, dtype=np.float64)

        # Delta in world frame
        d_world = curr_pos - self._last_pos
        d_yaw = curr_yaw - self._last_yaw
        d_yaw = math.atan2(math.sin(d_yaw), math.cos(d_yaw))

        # Rotate d_world into body frame (yaw CCW)
        cy = math.cos(self._last_yaw)
        sy = math.sin(self._last_yaw)
        dx_b = cy * d_world[0] + sy * d_world[1]
        dy_b = -sy * d_world[0] + cy * d_world[1]
        dz_b = d_world[2]

        rel_step_body = np.array([dx_b, dy_b, dz_b, d_yaw], dtype=np.float64)

        # Cumulative displacement from origin
        d_cum = curr_pos - self._origin_pos
        cy0 = math.cos(self._origin_yaw)
        sy0 = math.sin(self._origin_yaw)
        cum_x = cy0 * d_cum[0] + sy0 * d_cum[1]
        cum_y = -sy0 * d_cum[0] + cy0 * d_cum[1]
        cum_z = d_cum[2]
        cum_yaw = math.atan2(math.sin(curr_yaw - self._origin_yaw), math.cos(curr_yaw - self._origin_yaw))
        cum_odom_rel = np.array([cum_x, cum_y, cum_z, cum_yaw], dtype=np.float64)

        self._last_pos = curr_pos.copy()
        self._last_yaw = curr_yaw
        return rel_step_body, cum_odom_rel


@dataclass
class VisualServoingController:
    """Image-Based / Near-Field Geometric Visual Servoing (IBVS) Controller.

    Activates when the drone enters the near-field (d <= d_switch, default 1.2m).
    Applies:
      1. Action P-Tapering: dynamic shrinkage of action box as distance closes.
      2. High-precision proportional error feedback in body frame.
      3. Terminal damping to prevent overshoot/oscillation in the 0.1m~0.3m zone.
    """

    kp_xy: float = 0.6
    kp_yaw: float = 0.8
    kd_vel: float = 0.2
    d_switch: float = 1.2
    min_limit_ratio: float = 0.20  # minimum action limit scale (20% of max limits)

    def compute_action(
        self,
        current_pos: np.ndarray,
        current_yaw: float,
        goal_pos: np.ndarray,
        goal_yaw: float,
        current_vel_body: np.ndarray,
        base_limits: np.ndarray,
    ) -> np.ndarray:
        # Vector to goal in world frame
        delta_world = np.asarray(goal_pos, dtype=np.float64) - np.asarray(current_pos, dtype=np.float64)
        dist_xy = float(np.linalg.norm(delta_world[:2]))
        dist_3d = float(np.linalg.norm(delta_world))

        # Rotate delta into body frame
        cy = math.cos(current_yaw)
        sy = math.sin(current_yaw)
        err_x = cy * delta_world[0] + sy * delta_world[1]
        err_y = -sy * delta_world[0] + cy * delta_world[1]
        err_z = delta_world[2]

        err_yaw = goal_yaw - current_yaw
        err_yaw = math.atan2(math.sin(err_yaw), math.cos(err_yaw))

        # Dynamic P-Tapering limit scaling
        scale = max(self.min_limit_ratio, min(1.0, dist_3d / self.d_switch))
        dynamic_limits = base_limits * scale

        # PD control in body frame
        cmd_dx = self.kp_xy * err_x - self.kd_vel * current_vel_body[0]
        cmd_dy = self.kp_xy * err_y - self.kd_vel * current_vel_body[1]
        cmd_dz = 0.0  # handled by AltitudeLockController
        cmd_dyaw = self.kp_yaw * err_yaw - self.kd_vel * current_vel_body[2] if len(current_vel_body) > 2 else self.kp_yaw * err_yaw

        action = np.array([cmd_dx, cmd_dy, cmd_dz, cmd_dyaw], dtype=np.float64)
        clipped_action = np.clip(action, -dynamic_limits, dynamic_limits)
        return clipped_action


def _altitude_reading(obs: Observation) -> float:
    """Indoor contract: rangefinder/AGL first, baro auxiliary, proprio z last."""
    if obs.agl_m is not None and np.isfinite(obs.agl_m):
        origin = obs.info.get("agl_origin_z") if isinstance(obs.info, dict) else None
        if origin is not None:
            return float(origin) + float(obs.agl_m)
        return float(obs.agl_m)
    if obs.baro_alt is not None and np.isfinite(obs.baro_alt):
        return float(obs.baro_alt)
    return float(obs.position[2])


def controller_attribution_from_counts(*, assist: str, wam_steps: int, gt_pd_steps: int) -> str:
    if assist == "gt_pd":
        if gt_pd_steps > 0 and wam_steps > 0:
            return "mixed"
        return "gt_pd"
    if gt_pd_steps > 0:
        return "mixed"
    return "wam"


def mainline_sensors_used(*, depth_shield: bool, pose_source: str = "odom_from_imu_rgb") -> list[str]:
    sensors = ["rgb", "imu", "alt"]
    if pose_source:
        sensors.append(f"pose:{pose_source}")
    if depth_shield:
        sensors.append("depth_shield")
    return sensors


@dataclass
class TwoPhaseIndoorController:
    """Seamless Two-Phase Controller:

    Phase 1 (Distance > d_switch): WAM Latent RSSM Planner + Altitude Lock
    Phase 2 (Distance <= d_switch): Near-Field Visual Servoing (IBVS) + P-Tapering

    Mainline default (``assist=none``, ``forbid_gt_world_pose_control=True``):
    Phase 2 IBVS is disabled; WAM + altitude lock only.
    """

    d_switch: float = 1.2
    alt_ctrl: AltitudeLockController = field(default_factory=AltitudeLockController)
    ibvs_ctrl: VisualServoingController = field(default_factory=VisualServoingController)
    odom_tracker: RelativeOdometryTracker = field(default_factory=RelativeOdometryTracker)
    wam_steps: int = 0
    gt_pd_steps: int = 0

    def reset(self, initial_obs: Observation, target_pos: Optional[np.ndarray] = None) -> None:
        self.odom_tracker.reset(initial_obs)
        self.wam_steps = 0
        self.gt_pd_steps = 0
        target_z = float(target_pos[2]) if target_pos is not None else _altitude_reading(initial_obs)
        self.alt_ctrl.reset(target_z)

    def arbitrate_action(
        self,
        obs: Observation,
        wam_action: np.ndarray,
        goal_pos: np.ndarray,
        goal_yaw: float,
        action_limits: np.ndarray,
        step_hz: float = 5.0,
        *,
        assist: str = "none",
        forbid_gt_world_pose_control: bool = True,
    ) -> Tuple[np.ndarray, str, float, bool]:
        """Returns: (action, phase_name, goal_distance, used_gt_world_pose_this_step)"""
        rel_body, _cum_odom = self.odom_tracker.update(obs)
        obs.rel_odom = rel_body

        cur_pos = obs.position
        cur_yaw = float(obs.yaw)
        dist = float(np.linalg.norm(goal_pos - cur_pos))
        cur_alt = _altitude_reading(obs)

        use_ibvs = assist == "gt_pd" and not forbid_gt_world_pose_control and dist <= self.d_switch

        if use_ibvs:
            vel_body = rel_body[:3] * step_hz
            phase = "PHASE_2_VISUAL_SERVO"
            ibvs_act = self.ibvs_ctrl.compute_action(
                current_pos=cur_pos,
                current_yaw=cur_yaw,
                goal_pos=goal_pos,
                goal_yaw=goal_yaw,
                current_vel_body=vel_body,
                base_limits=action_limits,
            )
            ibvs_act[2] = self.alt_ctrl.step(cur_alt, dt=1.0 / step_hz)
            final_action = ibvs_act
            self.gt_pd_steps += 1
            used_gt = True
        else:
            phase = "PHASE_1_WAM_CRUISE"
            act = wam_action.copy()
            act[2] = self.alt_ctrl.step(cur_alt, dt=1.0 / step_hz)
            final_action = np.clip(act, -action_limits, action_limits)
            self.wam_steps += 1
            used_gt = False

        return final_action, phase, dist, used_gt
