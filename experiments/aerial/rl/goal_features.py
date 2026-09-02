"""Goal-relative features for the V1-② reward head.

``NavigationReward`` progress is Δdist(goal). r60 episode npz historically omitted
``goal``, so open-loop reward fidelity cannot see the quantity the label depends
on. This module:

  * builds body-frame ``goal_rel = (fwd, left, up, remaining_dist)`` from pose+goal
  * resolves a per-episode goal from stored npz / transition info, or (legacy)
    an arrived end-proprio proxy / Gauss–Newton fit to the reward channel

Goal may condition the **policy / critic** (imagination-to-goal) as well as the
reward head. Depth / IMU remain supervision-only and stay off the policy graph.
"""
from __future__ import annotations

from typing import Any, List, Optional, Sequence

import numpy as np

from experiments.aerial.rl.buffer import Transition

GOAL_REL_DIM = 4  # body-frame fwd, left, up, remaining_dist_m
BODY_VEL_DIM = 3  # body-frame linear velocity (fwd, left, up)
# Reward-head aux (not encoder input): unit goal dir + log1p(dist) + body vel +
# analytic Δdist from vel·dt (action alone ≠ realized displacement on r60 starts).
REWARD_AUX_DIM = 8
DEFAULT_REWARD_DT = 0.2  # 1/step_hz for r60 (step_hz=5)
DEFAULT_MANEUVER_W = 0.01


def goal_rel_body(
    pos: np.ndarray,
    yaw: float,
    goal: np.ndarray,
) -> np.ndarray:
    """World goal → body-frame delta + remaining distance ``[fwd, left, up, dist]``."""
    pos = np.asarray(pos, dtype=np.float64).reshape(3)
    goal = np.asarray(goal, dtype=np.float64).reshape(3)
    delta = goal - pos
    dist = float(np.linalg.norm(delta))
    c = float(np.cos(yaw))
    s = float(np.sin(yaw))
    fwd = c * delta[0] + s * delta[1]
    left = -s * delta[0] + c * delta[1]
    up = float(delta[2])
    return np.array([fwd, left, up, dist], dtype=np.float32)


def goal_rel_from_obs(obs: Any) -> np.ndarray:
    """``goal_rel`` for one observation; zeros when goal is missing.

    Mainline (RUNBOOK_indoor_0xm §0.1): when ``obs.info['pose_estimate']`` is
    present, ``goal_rel`` is computed from ``p_hat, psi_hat`` — never silent GT.
    Legacy paths without a stamped pose fall back to ``obs.position`` only when
    ``obs.info['pose_source']=='gt_proxy'`` is explicitly declared.
    """
    goal = None
    info = getattr(obs, "info", None)
    if isinstance(info, dict):
        goal = info.get("goal")
    if goal is None:
        return np.zeros(GOAL_REL_DIM, dtype=np.float32)
    goal_arr = np.asarray(goal, dtype=np.float64).reshape(3)

    from experiments.aerial.rl.pose_estimate import resolve_pose_from_obs

    pe = resolve_pose_from_obs(obs)
    if pe is not None:
        return pe.goal_rel(goal_arr)

    declared = info.get("pose_source") if isinstance(info, dict) else None
    if declared == "gt_proxy":
        return goal_rel_body(obs.position, float(obs.yaw), goal_arr)

    raise RuntimeError(
        "goal_rel requires obs.info['pose_estimate'] or explicit pose_source='gt_proxy'; "
        "silent GT obs.position is forbidden on mainline (RUNBOOK_indoor_0xm §0.1)"
    )


def advance_goal_rel_body(
    goal_rel: np.ndarray,
    action: np.ndarray,
) -> np.ndarray:
    """Update body-frame ``goal_rel`` after one body-delta action (imagination aux).

    Accounts for both 3D translation disp=action[:3] and body yaw rotation action[3]=dyaw.
    """
    g = np.asarray(goal_rel, dtype=np.float64).reshape(GOAL_REL_DIM).copy()
    act = np.asarray(action, dtype=np.float64).reshape(4)
    disp = act[:3]
    dyaw = float(act[3])

    # 1. Deduct 3D translation in previous body frame
    p_trans = g[:3] - disp

    # 2. Rotate by -dyaw around z-axis to transform into new body frame
    c = float(np.cos(dyaw))
    s = float(np.sin(dyaw))
    x_new = c * p_trans[0] + s * p_trans[1]
    y_new = -s * p_trans[0] + c * p_trans[1]
    z_new = p_trans[2]

    g[0] = x_new
    g[1] = y_new
    g[2] = z_new
    g[3] = float(np.linalg.norm(g[:3]))
    return g.astype(np.float32, copy=False)


def body_vel_from_obs(obs: Any) -> np.ndarray:
    """World-frame ``obs.velocity`` → body-frame ``[fwd, left, up]`` (m/s)."""
    v = np.asarray(getattr(obs, "velocity", np.zeros(3)), dtype=np.float64).reshape(3)
    yaw = float(getattr(obs, "yaw", 0.0))
    c = float(np.cos(yaw))
    s = float(np.sin(yaw))
    fwd = c * v[0] + s * v[1]
    left = -s * v[0] + c * v[1]
    up = float(v[2])
    return np.array([fwd, left, up], dtype=np.float32)


def analytic_progress(
    goal_rel: np.ndarray,
    body_disp: np.ndarray,
    action: Optional[np.ndarray] = None,
    *,
    w_maneuver: float = DEFAULT_MANEUVER_W,
) -> float:
    """``||g|| − ||g − body_disp|| − w‖a‖`` — NavigationReward progress proxy."""
    g = np.asarray(goal_rel, dtype=np.float64).reshape(GOAL_REL_DIM)
    disp = np.asarray(body_disp, dtype=np.float64).reshape(3)
    dist = float(g[3])
    prog = dist - float(np.linalg.norm(g[:3] - disp))
    if action is None:
        return float(prog)
    man = float(np.linalg.norm(np.asarray(action, dtype=np.float64).reshape(-1)))
    return float(prog - float(w_maneuver) * man)


def reward_aux_features(
    goal_rel: np.ndarray,
    body_vel: np.ndarray,
    action: np.ndarray,
    *,
    dt: float = DEFAULT_REWARD_DT,
    w_maneuver: float = DEFAULT_MANEUVER_W,
) -> np.ndarray:
    """Scale-stable reward-head conditioning ``[û, log1p(d), v_body, analytic]``.

    r60 open-loop reward fails when the head sees raw metre-scale ``goal_rel`` and
    near-constant actions: early-horizon commanded ``a`` ≫ realized displacement
    (accel from rest). Body velocity × ``dt`` recovers that displacement; the
    analytic channel alone beats the constant-mean baseline on honest held-out
    windows (oracle beat_frac=1.0).
    """
    g = np.asarray(goal_rel, dtype=np.float64).reshape(GOAL_REL_DIM)
    v = np.asarray(body_vel, dtype=np.float64).reshape(BODY_VEL_DIM)
    a = np.asarray(action, dtype=np.float64).reshape(4)
    dist = max(float(g[3]), 1e-6)
    unit = (g[:3] / dist).astype(np.float32)
    logd = np.float32(np.log1p(dist))
    analytic = np.float32(
        analytic_progress(g, v * float(dt), a, w_maneuver=float(w_maneuver))
    )
    return np.concatenate(
        [unit, np.array([logd], dtype=np.float32), v.astype(np.float32),
         np.array([analytic], dtype=np.float32)],
        axis=0,
    ).astype(np.float32, copy=False)


def _goal_from_info(transitions: Sequence[Transition]) -> Optional[np.ndarray]:
    for tr in transitions:
        for bag in (tr.info, getattr(tr.obs, "info", {}) or {}):
            if not isinstance(bag, dict):
                continue
            g = bag.get("goal")
            if g is not None:
                arr = np.asarray(g, dtype=np.float64).reshape(-1)
                if arr.size >= 3 and np.all(np.isfinite(arr[:3])):
                    return arr[:3].astype(np.float64)
    return None


def fit_goal_from_progress(
    pos: np.ndarray,
    prog: np.ndarray,
    *,
    n_iter: int = 30,
    damp: float = 0.5,
) -> np.ndarray:
    """Gauss–Newton fit of a fixed goal to observed progress ``Δdist`` labels.

    ``prog[t] ≈ ||pos[t]−g|| − ||pos[t+1]−g||`` for ``t < N−1``. Used as a legacy
    npz recovery path when the collector did not persist ``goal``.
    """
    pos = np.asarray(pos, dtype=np.float64).reshape(-1, 3)
    prog = np.asarray(prog, dtype=np.float64).reshape(-1)
    if pos.shape[0] < 2:
        return pos[-1].copy() if pos.shape[0] else np.zeros(3, dtype=np.float64)
    g = pos[-1].copy()
    for _ in range(int(n_iter)):
        d = np.linalg.norm(pos - g[None, :], axis=1) + 1e-6
        pred = d[:-1] - d[1:]
        err = pred - prog[:-1]
        u = (pos - g[None, :]) / d[:, None]
        jac = -u[:-1] + u[1:]
        dg, *_ = np.linalg.lstsq(jac, err, rcond=None)
        g = g + float(damp) * dg
    return g.astype(np.float64)


def end_proprio_goal_proxy(transitions: Sequence[Transition]) -> Optional[np.ndarray]:
    """Last pre-step position when the episode terminated without collision.

    Arrived episodes end within ``success_dist_m`` of the true goal; the stored
    terminal proprio is one step early but still a usable proxy for r60.
    """
    if not transitions:
        return None
    last = transitions[-1]
    post = last.next_obs if last.next_obs is not None else last.obs
    collided = bool(getattr(post, "collided", False) or last.obs.collided)
    if not (last.done and not collided):
        return None
    return np.asarray(last.obs.position, dtype=np.float64).reshape(3)


def resolve_episode_goal(
    transitions: Sequence[Transition],
    *,
    allow_fit: bool = False,
    allow_end_proxy: bool = True,
    maneuver_w: float = 0.01,
) -> Optional[np.ndarray]:
    """Best-effort episode goal: info → optional fit → optional end-proprio proxy.

    Default ``allow_fit=False``: Gauss–Newton recovery from the reward channel is
    **not** reliable on r60 (reconstructed progress MAE ≫ mean baseline), so we
    refuse to inject a misleading goal into ``goal_rel`` unless the caller opts in.
    """
    stored = _goal_from_info(transitions)
    if stored is not None:
        return stored
    if not transitions:
        return None
    if allow_fit and len(transitions) >= 3:
        pos = np.stack([t.obs.position for t in transitions], axis=0)
        acts = np.stack([np.asarray(t.action, dtype=np.float64).reshape(4)
                         for t in transitions], axis=0)
        rew = np.asarray([t.reward for t in transitions], dtype=np.float64)
        prog = rew + float(maneuver_w) * np.linalg.norm(acts, axis=1)
        return fit_goal_from_progress(pos, prog)
    if allow_end_proxy:
        return end_proprio_goal_proxy(transitions)
    return None


def stamp_train_pose_source(
    transitions: Sequence[Transition],
    pose_source: str = "gt_proxy",
) -> None:
    """Stamp declared ``pose_estimate`` for offline imagination training (in-place).

    Real-env eval must use ``odom_from_imu_rgb`` / ``vio_est``; this helper is
    only for H100 offline AC when replay NPZ lacks a pose estimator.
    """
    from experiments.aerial.rl.pose_estimate import PoseEstimate

    src = str(pose_source)
    for tr in transitions:
        for obs in (tr.obs, tr.next_obs):
            if obs is None:
                continue
            if obs.info is None:
                obs.info = {}
            pe = PoseEstimate(
                p_hat=np.asarray(obs.position, dtype=np.float64).reshape(3),
                psi_hat=float(obs.yaw),
                v_hat=np.asarray(getattr(obs, "velocity", np.zeros(3)), dtype=np.float64).reshape(3),
                pose_source=src,
                altitude_source="gt_proxy" if src == "gt_proxy" else "baro",
            )
            obs.info["pose_estimate"] = pe.to_info_dict()
            obs.info["pose_source"] = src
            obs.info.setdefault("goal_rel_pose_source", src)


def attach_goal(transitions: List[Transition], goal: Optional[np.ndarray]) -> None:
    """Stamp ``goal`` onto every transition / obs ``info`` (in-place)."""
    if goal is None:
        return
    g = np.asarray(goal, dtype=np.float32).reshape(3)
    for tr in transitions:
        tr.info["goal"] = g.copy()
        if tr.obs.info is None:
            tr.obs.info = {}
        tr.obs.info["goal"] = g.copy()
        if tr.next_obs is not None:
            if tr.next_obs.info is None:
                tr.next_obs.info = {}
            tr.next_obs.info["goal"] = g.copy()


class SpatialGoalTracker:
    """Risk 5: 3D Spatial Goal Anchor & Dead-Reckoning under Total Occlusion (Method B).

    Maintains world-frame target anchor P_world. When visual target is in view, updates
    anchor via depth back-projection with EMA. When visual target is occluded/lost in frame,
    provides continuous body-relative goal_rel via forward kinematic dead-reckoning.
    """

    def __init__(self, ema_alpha: float = 0.7) -> None:
        self.ema_alpha = float(ema_alpha)
        self.world_target: Optional[np.ndarray] = None
        self.has_visual_lock: bool = False

    def reset(self) -> None:
        self.world_target = None
        self.has_visual_lock = False

    def update_from_vision(
        self,
        drone_pos: np.ndarray,
        drone_yaw: float,
        target_body_rel: np.ndarray,
        confidence: float = 1.0,
    ) -> np.ndarray:
        """Update world target from vision detection + depth back-projection."""
        pos = np.asarray(drone_pos, dtype=np.float64).reshape(3)
        b_rel = np.asarray(target_body_rel, dtype=np.float64).reshape(3)
        c = float(np.cos(drone_yaw))
        s = float(np.sin(drone_yaw))

        # Rotate body-rel to world frame: x_w = c*fwd - s*left, y_w = s*fwd + c*left
        w_offset = np.array([
            c * b_rel[0] - s * b_rel[1],
            s * b_rel[0] + c * b_rel[1],
            b_rel[2],
        ], dtype=np.float64)
        measured_world = pos + w_offset

        if self.world_target is None or not self.has_visual_lock:
            self.world_target = measured_world
        else:
            eff_alpha = min(1.0, max(0.0, self.ema_alpha * float(confidence)))
            self.world_target = (1.0 - eff_alpha) * self.world_target + eff_alpha * measured_world

        self.has_visual_lock = True
        return self.world_target.copy()

    def get_goal_rel(
        self,
        drone_pos: np.ndarray,
        drone_yaw: float,
    ) -> Optional[np.ndarray]:
        """Compute body-frame goal_rel [dx_body, dy_body, dz_body, dist] from world anchor."""
        if self.world_target is None:
            return None
        return goal_rel_body(drone_pos, drone_yaw, self.world_target)
