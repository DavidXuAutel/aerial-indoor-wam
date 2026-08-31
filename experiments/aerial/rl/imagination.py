"""Batched imagined rollout over a ``LatentDynamics`` (Plan-A parallelism).

This is where sample *volume* comes from: instead of many real envs (the
renderer is single-consumer), we roll a batch of latent states forward through
the fast world model. ``imagine`` takes a batch of encoded start states ``z0``
and an imagination policy, rolls ``horizon`` steps, and returns per-step
latents / actions / rewards / p_coll / done masks for the RL update (V4).

The horizon is capped (spec §9): multi-step WM error compounds, so until the WM
is shown non-divergent the rollout length stays bounded. ``done`` masking stops
reward accrual after a trajectory terminates.

Pure numpy; works with ``StubLatentDynamics`` for offline tests. Imagination
policies expose ``act_latent(z) -> [4]`` (fallback: ``act(z)``).

ACTION SPACE (2026-08-18): pass ``action_limits`` to hold the imagined action
set equal to the deployed one (``body_delta_limits(1/step_hz)``, clipped in
``collector.py:167``). ``ImaginedRollout.n_action_clipped`` counts how often the
clip actually bit — with the C2 bounded policy it must stay **0**, which is how
the "clip is a no-op" claim gets measured instead of assumed. Note this clip
alone is NOT the consistency fix: the actor update is REINFORCE, so a policy
that can propose out-of-box actions needs its *sampling law* bounded (see
``actor_critic`` C2 / proposal §4.1), not its samples truncated here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional

import numpy as np

from experiments.aerial.rl.dynamics import LatentDynamics
from experiments.aerial.rl.goal_features import (
    BODY_VEL_DIM,
    GOAL_REL_DIM,
    advance_goal_rel_body,
    analytic_progress,
)
from experiments.aerial.rl.reward import RewardConfig, reward_terms

MAX_IMAGINATION_HORIZON = 15  # §9 safety cap until WM error shown non-divergent


@dataclass
class ImaginedRollout:
    z: np.ndarray            # [B, H+1, latent_dim]
    actions: np.ndarray      # [B, H, 4]
    rewards: np.ndarray      # [B, H]
    p_coll: np.ndarray       # [B, H]
    progress: np.ndarray     # [B, H]
    done: np.ndarray         # [B, H] bool (cumulative)
    #: How many (b, t, axis) entries the deployed-action clip actually changed.
    #: 0 under the C2 bounded policy; > 0 means imagined != deployed action set.
    n_action_clipped: int = 0
    #: Body-frame goal relative features at each latent before the action
    #: ``[B, H+1, GOAL_REL_DIM]``. ``None`` when imagination ran without goals.
    goal_rel: Optional[np.ndarray] = None

    @property
    def returns(self) -> np.ndarray:
        """Per-trajectory summed reward (done steps already zero-masked)."""
        return self.rewards.sum(axis=1)


def _act_latent(
    policy: Any,
    z: np.ndarray,
    goal_rel: Optional[np.ndarray] = None,
) -> np.ndarray:
    fn = getattr(policy, "act_latent", None) or getattr(policy, "act", None)
    if not callable(fn):
        raise TypeError("imagination policy must implement act_latent(z) or act(z)")
    try:
        out = fn(z, goal_rel=goal_rel)
    except TypeError:
        out = fn(z)
    return np.asarray(out, dtype=np.float64).reshape(4)


def imagine(
    dynamics: LatentDynamics,
    policy: Any,
    z0_batch: np.ndarray,
    horizon: int,
    *,
    reward_cfg: Optional[RewardConfig] = None,
    max_horizon: int = MAX_IMAGINATION_HORIZON,
    goal_rel0: Optional[np.ndarray] = None,
    body_vel0: Optional[np.ndarray] = None,
    propagate_goal_rel: bool = True,
    action_limits: Optional[np.ndarray] = None,
) -> ImaginedRollout:
    """Roll ``z0_batch`` forward ``horizon`` steps through ``dynamics``.

    When ``goal_rel0`` / ``body_vel0`` are provided (shapes ``[B,4]`` / ``[B,3]``),
    each imagined ``step`` receives aux conditioning for the torch reward head.
    ``propagate_goal_rel`` advances ``goal_rel`` with ``advance_goal_rel_body`` after
    each action (stub-consistent kinematics); ``body_vel`` is held at the start value.

    ``action_limits`` [4] (per-axis, positive) constrains imagined actions to the
    deployed set; ``None`` leaves the historical unbounded behaviour so pre-C2
    audit runs replay bit-for-bit.
    """
    cfg = reward_cfg or RewardConfig()
    if action_limits is None:
        lim = None
    else:
        lim = np.abs(np.asarray(action_limits, dtype=np.float64).reshape(-1))
        if lim.shape != (4,) or not np.all(lim > 0):
            raise ValueError(f"action_limits must be 4 positive values, got {action_limits!r}")
    n_clipped = 0
    z0 = np.atleast_2d(np.asarray(z0_batch, dtype=np.float64))
    batch, latent_dim = z0.shape
    if horizon < 1:
        raise ValueError("horizon must be >= 1")
    if horizon > max_horizon:
        raise ValueError(
            f"horizon {horizon} exceeds cap {max_horizon} (spec §9: WM multi-step "
            "error is unbounded until validated); raise max_horizon explicitly"
        )

    zs = np.zeros((batch, horizon + 1, latent_dim), dtype=np.float64)
    acts = np.zeros((batch, horizon, 4), dtype=np.float64)
    rews = np.zeros((batch, horizon), dtype=np.float64)
    pcs = np.zeros((batch, horizon), dtype=np.float64)
    progs = np.zeros((batch, horizon), dtype=np.float64)
    dones = np.zeros((batch, horizon), dtype=bool)
    zs[:, 0] = z0
    goals_hist = np.zeros((batch, horizon + 1, GOAL_REL_DIM), dtype=np.float32)

    use_aux = goal_rel0 is not None or body_vel0 is not None
    if use_aux:
        if goal_rel0 is None:
            goal_rel0 = np.zeros((batch, GOAL_REL_DIM), dtype=np.float32)
        else:
            goal_rel0 = np.asarray(goal_rel0, dtype=np.float32).reshape(batch, GOAL_REL_DIM)
        if body_vel0 is None:
            body_vel0 = np.zeros((batch, BODY_VEL_DIM), dtype=np.float32)
        else:
            body_vel0 = np.asarray(body_vel0, dtype=np.float32).reshape(batch, BODY_VEL_DIM)
        goal_rel_t = goal_rel0.copy()
        body_vel_t = body_vel0.copy()
        goals_hist[:, 0] = goal_rel_t
    else:
        goal_rel_t = body_vel_t = None

    alive = np.ones(batch, dtype=bool)
    for t in range(horizon):
        for b in range(batch):
            if not alive[b]:
                zs[b, t + 1] = zs[b, t]
                dones[b, t] = True
                if goal_rel_t is not None:
                    goals_hist[b, t + 1] = goals_hist[b, t]
                continue
            gr_b = None if goal_rel_t is None else goal_rel_t[b]
            a = _act_latent(policy, zs[b, t], goal_rel=gr_b)
            if lim is not None:
                a_clipped = np.clip(a, -lim, lim)
                n_clipped += int(np.count_nonzero(a_clipped != a))
                a = a_clipped
            step_kw: dict = {}
            if use_aux:
                step_kw["goal_rel"] = goal_rel_t[b]
                step_kw["body_vel"] = body_vel_t[b]
            out = dynamics.step(zs[b, t], a, **step_kw)
            zs[b, t + 1] = np.asarray(out.z_next, dtype=np.float64).reshape(latent_dim)
            acts[b, t] = a
            pcs[b, t] = out.p_coll
            if use_aux:
                prog = analytic_progress(goal_rel_t[b], a[:3])
            else:
                prog = out.progress
            progs[b, t] = prog
            maneuver = float(np.linalg.norm(a))
            r = reward_terms(prog, out.p_coll, maneuver, cfg)["reward"]
            # Mirror NavigationReward.step: arrival earns the same success bonus,
            # so imagined and real returns are on one scale (spec reward §4.5).
            if getattr(out, "arrived", False):
                r += cfg.success_bonus
            rews[b, t] = r
            if out.done:
                alive[b] = False
                dones[b, t] = True
            if use_aux and propagate_goal_rel and alive[b]:
                goal_rel_t[b] = advance_goal_rel_body(goal_rel_t[b], a)
            if goal_rel_t is not None:
                goals_hist[b, t + 1] = goal_rel_t[b]

    return ImaginedRollout(
        z=zs, actions=acts, rewards=rews, p_coll=pcs, progress=progs, done=dones,
        n_action_clipped=int(n_clipped),
        goal_rel=(goals_hist if use_aux else None),
    )
