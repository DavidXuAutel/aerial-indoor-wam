"""``RolloutCollector`` — the serial real-env worker (Plan A).

One env instance (the renderer is single-consumer) driven at ~``step_hz``: reset
→ loop {policy → step → reward} → push a full episode to the ``ReplayBuffer``.
This is the only place that touches the real renderer; sample *volume* for
learning comes from imagination, not from parallel envs.

Policy dispatch is duck-typed (mirrors ``collect_dagger._predict_delta``):

  1. ``policy.act(obs) -> [4] body delta``            (RL / continuous policy)
  2. ``policy.predict_delta(rgb, state, instr)``      (delta-native policy)
  3. ``policy.predict_primitive(rgb, state, instr)``  → ``primitive_to_delta``
     (the existing ``FastWAMAerialPolicy`` / ``ReplayPolicy`` primitive path)

Achieved Hz is measured and logged every episode; a warning fires if it drops
below the configured target so the ~30 Hz Plan-A assumption is validated on real
hardware rather than assumed.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import numpy as np

from experiments.aerial.openfly_actions import primitive_to_delta
from experiments.aerial.rl.buffer import Episode, ReplayBuffer, Transition
from experiments.aerial.rl.env.action import DEFAULT_STEP_HZ, body_delta_limits, clip_body_delta
from experiments.aerial.rl.env.obs import Observation
from experiments.aerial.rl.goal_features import body_vel_from_obs, goal_rel_body, goal_rel_from_obs
from experiments.aerial.rl.reward import NavigationReward, RewardConfig
from experiments.aerial.rl.safety import SafetyShield

logger = logging.getLogger(__name__)


def act_delta(
    policy: Any,
    obs: Observation,
    instruction: str,
    limits: Optional[np.ndarray] = None,
) -> np.ndarray:
    """Resolve any supported policy to a finite, clipped 4-D body delta.

    ``limits`` is the per-step displacement cap for the env's control rate
    (``body_delta_limits(dt)``); defaults to the 30 Hz continuous cap. NOTE: a
    discrete-primitive policy returns a macro-sized delta (e.g. fwd 9 m) which
    this clips to a single per-step increment — driving macro primitives
    faithfully needs a multi-step executor, out of scope for the V0 skeleton.
    """
    from experiments.aerial.rl.pose_estimate import resolve_pose_from_obs

    act = getattr(policy, "act", None)
    goal = None
    if isinstance(obs.info, dict):
        g = obs.info.get("goal")
        if g is not None:
            goal = np.asarray(g, dtype=np.float64).reshape(3)
    pe = resolve_pose_from_obs(obs)
    view = (
        obs.policy_view(nav_pos=pe.p_hat, nav_yaw=pe.psi_hat, goal=goal)
        if pe is not None
        else obs.policy_view(goal=goal)
    )
    if callable(act):
        raw = act(view)
    else:
        predict_delta = getattr(policy, "predict_delta", None)
        if callable(predict_delta):
            raw = predict_delta(obs.rgb, obs.proprio4(), instruction)
        else:
            primitive = int(policy.predict_primitive(obs.rgb, obs.proprio4(), instruction))
            raw = primitive_to_delta(primitive)
    return clip_body_delta(np.asarray(raw, dtype=np.float64), limits)


@dataclass
class CollectStats:
    episodes: int = 0
    steps: int = 0
    seconds: float = 0.0
    interventions: int = 0
    # Episodes dropped at reset because the vehicle spawned already colliding
    # (spawn-inside-geometry). Not counted in `episodes`; never reach the buffer.
    skipped: int = 0
    returns: List[float] = field(default_factory=list)

    @property
    def achieved_hz(self) -> float:
        return self.steps / self.seconds if self.seconds > 0 else 0.0


class RolloutCollector:
    def __init__(
        self,
        env: Any,
        policy: Any,
        buffer: ReplayBuffer,
        *,
        reward_cfg: Optional[RewardConfig] = None,
        safety: Optional[SafetyShield] = None,
        max_steps: int = 200,
        target_hz: float = 30.0,
        on_episode: Optional[Callable[[Episode, CollectStats], None]] = None,
        skip_reset_collision: bool = True,
        depth_predictor: Optional[Any] = None,
        tau_predictor: Optional[Any] = None,
        planner: Optional[Any] = None,
        dynamics: Optional[Any] = None,
        takeoff_scan_steps: int = 0,
        terminal_dock: bool = True,
    ) -> None:
        self.env = env
        self.policy = policy
        self.buffer = buffer
        self.reward_cfg = reward_cfg or RewardConfig()
        self.safety = safety
        self.max_steps = int(max_steps)
        self.target_hz = float(target_hz)
        self.takeoff_scan_steps = int(max(0, takeoff_scan_steps))
        # When False, never bypass the policy with GT ann-goal docking
        # (needed for visual-goal / vgoal eval). Default True preserves F-cap.
        self.terminal_dock = bool(terminal_dock)
        # Drop episodes whose reset spawns the vehicle already in collision
        # (inside geometry): no action has been taken, so it's a spawn artifact,
        # not a learnable trajectory. Skipped before any step / buffer write.
        self.skip_reset_collision = bool(skip_reset_collision)
        # Optional sink invoked with every completed episode (e.g. persist to
        # disk). None -> collector stays purely in-memory (offline tests / V0).
        self.on_episode = on_episode
        # Frozen §4 ④: produce ``obs.info['depth_min_pred']`` BEFORE the shield
        # runs. ``DepthMinPredictor`` (or any object with ``predict_min`` /
        # optional ``reset``). None → leave info empty (default V0 posture).
        self.depth_predictor = depth_predictor
        # V1b [1d]: τ independent of D̂ — ``predict_tau(obs)`` → obs.info['tau_pred'].
        self.tau_predictor = tau_predictor
        # V1b: optional short-horizon imagination planner (scores candidates).
        self.planner = planner
        # V4 P2: online WM for live p_coll → should_override(obs, wm_out=...).
        self.dynamics = dynamics
        self._latent: Optional[np.ndarray] = None

    def collect_episode(self, episode: Optional[Dict[str, Any]] = None) -> tuple[Episode, CollectStats]:
        instruction = str((episode or {}).get("gpt_instruction", ""))
        obs = self.env.reset(episode)
        start_pos = np.asarray(obs.position, dtype=np.float32).copy()
        # Entry guard: a vehicle already colliding at reset spawned inside
        # geometry. Skip before any step so it never pollutes the buffer/dataset
        # as a 1-step instant crash. (`collided` is populated at reset by both
        # backends — airsim_env.observe() / mock bounds check.)
        if self.skip_reset_collision and bool(getattr(obs, "collided", False)):
            logger.warning(
                "reset spawned in collision — skipping episode "
                "(spawn-inside-geometry; start pose may need resampling)"
            )
            return [], CollectStats(episodes=0, skipped=1)
        bind_ep = getattr(self.policy, "bind_episode", None)
        if callable(bind_ep):
            bind_ep(episode)
        if hasattr(self.policy, "reset"):
            self.policy.reset()
        reset_pred = getattr(self.depth_predictor, "reset", None)
        if callable(reset_pred):
            reset_pred()
        from experiments.aerial.rl.pose_estimate import stamp_pose_on_obs

        pose_src = str(getattr(self, "pose_source", "odom_from_imu_rgb"))
        self._pose_est = getattr(self, "_pose_est", None)
        if self._pose_est is None or getattr(self._pose_est, "pose_source", None) != pose_src:
            from experiments.aerial.rl.pose_estimate import make_pose_estimator

            self._pose_est = make_pose_estimator(pose_src)
        if self.dynamics is not None:
            self._latent = np.asarray(self.dynamics.encode(obs), dtype=np.float64)

        reward = NavigationReward(getattr(self.env, "goal", None), self.reward_cfg)
        env_goal = getattr(self.env, "goal", None)
        goal_xyz = (
            None if env_goal is None
            else np.asarray(env_goal, dtype=np.float32).reshape(3)
        )
        reward.reset(getattr(self.env, "goal", None), obs.position)

        pe0 = self._pose_est.reset(obs)
        stamp_pose_on_obs(obs, pe0)
        if goal_xyz is not None:
            obs.info["goal"] = goal_xyz.copy()

        transitions: List[Transition] = []
        stats = CollectStats(episodes=1)
        # Per-step displacement cap for this env's control rate (keeps the clip
        # consistent with what env.step will apply).
        step_hz = float(getattr(getattr(self.env, "config", None), "step_hz", DEFAULT_STEP_HZ))
        limits = body_delta_limits(1.0 / step_hz)
        prev_obs_t: Optional[float] = float(obs.t) if hasattr(obs, "t") else None
        t_start = time.perf_counter()

        for step_idx in range(self.max_steps):
            # Risk 2: Dynamic control dt measurement to eliminate frequency mismatch & brake margin degradation
            current_obs_t = float(obs.t) if hasattr(obs, "t") else None
            if prev_obs_t is not None and current_obs_t is not None and 0.02 < (current_obs_t - prev_obs_t) < 1.0:
                control_dt = current_obs_t - prev_obs_t
            else:
                control_dt = 1.0 / step_hz
            prev_obs_t = current_obs_t
            limits = body_delta_limits(control_dt)

            # Refresh depth & tau predictions at step onset for planner, docking, and shield
            if self.depth_predictor is not None:
                predict_bundle = getattr(
                    self.depth_predictor, "predict_min_and_cones", None
                )
                predict_cones = getattr(self.depth_predictor, "predict_cones", None)
                if callable(predict_bundle):
                    d_min, cones = predict_bundle(obs)
                else:
                    d_min = self.depth_predictor.predict_min(obs)
                    cones = predict_cones(obs) if callable(predict_cones) else None
                if d_min is not None:
                    obs.info["depth_min_pred"] = float(d_min)
                if cones is not None:
                    obs.info["depth_cones_pred"] = {
                        str(k): float(v) for k, v in cones.items()
                    }
            if self.tau_predictor is not None:
                tau = self.tau_predictor.predict_tau(obs)
                if tau is not None:
                    obs.info["tau_pred"] = float(tau)

            if step_idx < self.takeoff_scan_steps:
                # Active perception: in-place takeoff 360° panoramic scan to populate RSSM memory
                yaw_delta = float(2.0 * np.pi / max(1, self.takeoff_scan_steps))
                action = clip_body_delta(np.array([0.0, 0.0, 0.0, yaw_delta], dtype=np.float64), limits)
            else:
                d_curr_goal = (
                    float(np.linalg.norm(obs.position - goal_xyz))
                    if goal_xyz is not None
                    else 999.0
                )
                cones_raw = obs.info.get("depth_cones_pred") if isinstance(obs.info, dict) else None
                d_fwd = float(cones_raw.get("forward", 5.0)) if isinstance(cones_raw, dict) and cones_raw.get("forward") is not None else 5.0

                if (
                    self.terminal_dock
                    and goal_xyz is not None
                    and 0.01 < d_curr_goal <= 35.0
                    and d_fwd >= 1.5
                ):
                    # Spec 20260828 §5.2: Terminal 3D precision docking within 35.0m when forward path is clear
                    gr = goal_rel_body(obs.position, obs.yaw, goal_xyz)
                    body_v = body_vel_from_obs(obs)
                    desired_dyaw = float(np.arctan2(gr[1], max(gr[0], 0.1)))
                    fwd_cmd = max(0.5, min(1.0, 0.6 * gr[0] - 0.1 * body_v[0])) if gr[0] > 0 else 0.5 * gr[0] - 0.2 * body_v[0]
                    dock_act = np.array([
                        fwd_cmd,
                        0.5 * gr[1] - 0.2 * body_v[1],
                        0.6 * gr[2] - 0.2 * body_v[2],
                        desired_dyaw,
                    ], dtype=np.float64)
                    action = clip_body_delta(dock_act, limits)
                else:
                    action = act_delta(self.policy, obs, instruction, limits)
                    if self.planner is not None:
                        set_goal = getattr(self.planner, "set_goal", None)
                        if callable(set_goal):
                            set_goal(getattr(self.env, "goal", None))
                        action = np.asarray(
                            self.planner.plan(obs, action), dtype=np.float64
                        ).reshape(4)

                    # Global Cruise Altitude Envelope: prevent vertical drift during long-distance cruise
                    target_z = float(goal_xyz[2]) if goal_xyz is not None else float(start_pos[2])
                    z_err = target_z - float(obs.position[2])
                    if abs(z_err) > 1.5 and d_fwd >= 1.5:
                        body_v = body_vel_from_obs(obs)
                        z_correction = max(-0.25, min(0.25, 0.4 * z_err - 0.1 * body_v[2]))
                        action[2] = float(action[2] + z_correction)

                    action = clip_body_delta(action, limits)
            intervened = False
            wm_out = None
            if self.dynamics is not None and self._latent is not None:
                wm_out = self.dynamics.step(
                    self._latent,
                    action,
                    goal_rel=goal_rel_from_obs(obs),
                    body_vel=body_vel_from_obs(obs),
                )
            if self.safety is not None:
                apply_fn = getattr(self.safety, "apply_action", None)
                if callable(apply_fn):
                    action, intervened = apply_fn(action, obs, wm_out=wm_out, limits=limits)
                elif self.safety.should_override(obs, wm_out=wm_out):
                    action = clip_body_delta(self.safety.override_action(obs), limits)
                    intervened = True

            next_obs, info = self.env.step(action)
            pe_next = self._pose_est.update(next_obs, action=action, dt=control_dt)
            stamp_pose_on_obs(next_obs, pe_next)
            if goal_xyz is not None:
                next_obs.info["goal"] = goal_xyz.copy()
            if self.dynamics is not None and self._latent is not None:
                out = self.dynamics.step(
                    self._latent,
                    action,
                    goal_rel=goal_rel_from_obs(obs),
                    body_vel=body_vel_from_obs(obs),
                )
                self._latent = np.asarray(out.z_next, dtype=np.float64)
            r, done, terms = reward.step(next_obs, action)
            emergency_override = bool(obs.info.get("shield_emergency_override", False))
            governor_cap = bool(obs.info.get("shield_governor_cap", False))
            ep_info = {
                **info,
                **terms,
                "intervention": intervened,
                "emergency_override": emergency_override,
                "governor_cap": governor_cap,
            }
            # ATTR / TZ: copy pre-step obs.info preds into transition.info so
            # P7/attr harness can read d̂/τ from tr.info (not only obs.info).
            for _k in ("depth_min_pred", "tau_pred", "depth_cones_pred"):
                if _k in obs.info and obs.info[_k] is not None:
                    ep_info[_k] = obs.info[_k]
            # TZ-3: persist shield channel tags from the pre-step obs (speed-cap
            # vs τ/p_coll emergency) so P7 band_frac can treat them differently.
            ch = obs.info.get("shield_channels")
            if ch:
                ep_info["shield_channels"] = list(ch)
            if goal_xyz is not None:
                ep_info["goal"] = goal_xyz.copy()
            transitions.append(
                Transition(
                    obs=obs, action=action, reward=r, done=done,
                    next_obs=next_obs,
                    info=ep_info,
                )
            )
            stats.steps += 1
            stats.interventions += int(intervened)
            obs = next_obs
            if done:
                break

        stats.seconds = time.perf_counter() - t_start
        stats.returns.append(float(sum(t.reward for t in transitions)))
        if self.target_hz > 0 and stats.achieved_hz < self.target_hz * 0.8:
            logger.warning(
                "collector achieved %.1f Hz (< %.1f Hz target) over %d steps",
                stats.achieved_hz, self.target_hz, stats.steps,
            )
        self.buffer.add_episode(transitions)
        if self.on_episode is not None:
            self.on_episode(transitions, stats)
        return transitions, stats

    def collect(self, num_episodes: int = 1, episodes: Optional[List[Dict[str, Any]]] = None) -> CollectStats:
        total = CollectStats()
        for i in range(int(num_episodes)):
            ep = None
            if episodes:
                ep = episodes[i % len(episodes)]
            _, s = self.collect_episode(ep)
            total.episodes += s.episodes
            total.steps += s.steps
            total.seconds += s.seconds
            total.interventions += s.interventions
            total.skipped += s.skipped
            total.returns.extend(s.returns)
        return total
