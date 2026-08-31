"""Short-horizon imagination planner (V1b, frozen spec §7).

Scores a small set of candidate body deltas by rolling them forward through a
``LatentDynamics`` model for ``horizon`` steps (≤ ``MAX_IMAGINATION_HORIZON``),
then returns the first action of the highest-return sequence. This is the
test-time imagination scoring path — distinct from V4 actor-critic training.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Sequence

import numpy as np

from experiments.aerial.rl.dynamics import LatentDynamics
from experiments.aerial.rl.env.obs import Observation
from experiments.aerial.rl.imagination import MAX_IMAGINATION_HORIZON, imagine
from experiments.aerial.rl.reward import RewardConfig


class ConstantLatentPolicy:
    """Imagination policy that repeats one body delta every step."""

    def __init__(self, action: np.ndarray) -> None:
        self._action = np.asarray(action, dtype=np.float64).reshape(4)

    def act_latent(self, z: np.ndarray, goal_rel: Optional[np.ndarray] = None) -> np.ndarray:
        return self._action.copy()


class CandidateFollowerPolicy:
    """Execute candidate action on step 0, then follow underlying policy for subsequent steps."""

    def __init__(self, first_action: np.ndarray, fallback_policy: Optional[Any] = None) -> None:
        self._first_action = np.asarray(first_action, dtype=np.float64).reshape(4)
        self._fallback_policy = fallback_policy
        self._step = 0

    def act_latent(self, z: np.ndarray, goal_rel: Optional[np.ndarray] = None) -> np.ndarray:
        if self._step == 0 or self._fallback_policy is None:
            self._step += 1
            return self._first_action.copy()
        self._step += 1
        fn = getattr(self._fallback_policy, "act_latent", None) or getattr(self._fallback_policy, "act", None)
        if callable(fn):
            try:
                return np.asarray(fn(z, goal_rel=goal_rel), dtype=np.float64).reshape(4)
            except TypeError:
                try:
                    return np.asarray(fn(z), dtype=np.float64).reshape(4)
                except Exception:
                    return self._first_action.copy()
        return self._first_action.copy()


def default_candidates(base_action: np.ndarray) -> List[np.ndarray]:
    """Discrete candidate action set around the policy proposal including evasive maneuvers."""
    base = np.asarray(base_action, dtype=np.float64).reshape(4)
    dx, dy, dz, dyaw = base
    return [
        base,
        np.array([dx * 0.5, dy, dz, dyaw], dtype=np.float64),
        np.array([dx * 0.5, -0.3, dz, -0.2], dtype=np.float64),
        np.array([dx * 0.5, 0.3, dz, 0.2], dtype=np.float64),
        np.array([0.2, -0.4, dz, -0.314], dtype=np.float64),
        np.array([0.2, 0.4, dz, 0.314], dtype=np.float64),
        np.array([0.0, -0.4, 0.0, -0.314], dtype=np.float64),
        np.array([0.0, 0.4, 0.0, 0.314], dtype=np.float64),
        np.array([dx * 0.5, 0.0, 0.35, dyaw], dtype=np.float64),
        np.zeros(4, dtype=np.float64),
        np.array([-max(abs(dx), 0.5), 0.0, 0.0, 0.0], dtype=np.float64),
        np.array([dx, dy * 0.5, dz, dyaw], dtype=np.float64),
        np.array([max(abs(dx), 1.0), 0.0, 0.0, 0.0], dtype=np.float64),
    ]


@dataclass
class ImaginationPlanner:
    """Pick the best first action via batched short imagined rollouts with terminal value bootstrap."""

    dynamics: LatentDynamics
    horizon: int = 5
    reward_cfg: Optional[RewardConfig] = None
    candidate_fn: Any = field(default=default_candidates)
    action_limits: Optional[np.ndarray] = None
    policy: Optional[Any] = None
    gamma: float = 0.997
    critic: Optional[Any] = None

    def __post_init__(self) -> None:
        self.horizon = int(self.horizon)
        if self.action_limits is not None:
            lim = np.abs(np.asarray(self.action_limits, dtype=np.float64).reshape(-1))
            if lim.shape != (4,) or not np.all(lim > 0):
                raise ValueError(
                    f"action_limits must be 4 positive values, got {self.action_limits!r}"
                )
            self.action_limits = lim
        if self.horizon < 1:
            raise ValueError("horizon must be >= 1")
        if self.horizon > MAX_IMAGINATION_HORIZON:
            raise ValueError(
                f"planner horizon {self.horizon} exceeds cap {MAX_IMAGINATION_HORIZON}"
            )

    def set_goal(self, goal: Optional[np.ndarray]) -> None:
        set_goal = getattr(self.dynamics, "set_goal", None)
        if callable(set_goal):
            set_goal(goal)

    def _value_fn(self) -> Optional[Any]:
        if self.critic is not None:
            fn = getattr(self.critic, "value", None)
            if callable(fn):
                return fn
        if self.policy is not None:
            fn = getattr(self.policy, "value", None)
            if callable(fn):
                return fn
            ac = getattr(self.policy, "_ac", None)
            if ac is not None:
                fn = getattr(ac, "value", None)
                if callable(fn):
                    return fn
        return None

    def plan(self, obs: Observation, base_action: np.ndarray) -> np.ndarray:
        """Return the candidate first action with highest imagined return + terminal value."""
        z0 = np.asarray(self.dynamics.encode(obs), dtype=np.float64)
        candidates = list(self.candidate_fn(np.asarray(base_action, dtype=np.float64)))
        if not candidates:
            return np.asarray(base_action, dtype=np.float64).reshape(4)
        if self.action_limits is not None:
            lim = self.action_limits
            candidates = [np.clip(c, -lim, lim) for c in candidates]

        goal_rel0: Optional[np.ndarray] = None
        goal = None
        if isinstance(obs.info, dict) and obs.info.get("goal") is not None:
            goal = np.asarray(obs.info["goal"], dtype=np.float32).reshape(3)
        elif getattr(self.dynamics, "_goal", None) is not None:
            goal = np.asarray(self.dynamics._goal, dtype=np.float32).reshape(3)

        if goal is not None:
            from experiments.aerial.rl.goal_features import goal_rel_body
            goal_rel0 = goal_rel_body(obs.position, obs.yaw, goal).reshape(1, -1)

        val_fn = self._value_fn()
        discounts = np.array([self.gamma ** t for t in range(self.horizon)], dtype=np.float64)

        best_a = candidates[0]
        best_score = -np.inf
        for cand in candidates:
            cand_pol = CandidateFollowerPolicy(cand, fallback_policy=self.policy)
            roll = imagine(
                self.dynamics,
                cand_pol,
                z0[None, :],
                self.horizon,
                reward_cfg=self.reward_cfg,
                goal_rel0=goal_rel0,
                action_limits=self.action_limits,
            )
            # 1. Discounted stage reward sum
            stage_rewards = roll.rewards[0]
            disc_return = float(np.sum(stage_rewards * discounts[: len(stage_rewards)]))

            # 2. Risk 1 Fix: Value Bootstrap from Critic at horizon H
            terminal_val = 0.0
            if val_fn is not None and not roll.done[0, -1]:
                z_term = roll.z[0, -1]
                g_term = roll.goal_rel[0, -1] if roll.goal_rel is not None else None
                try:
                    v_out = val_fn(z_term, goal_rel=g_term)
                    terminal_val = float(np.asarray(v_out).reshape(-1)[0])
                except Exception:
                    terminal_val = 0.0

            score = disc_return + (self.gamma ** self.horizon) * terminal_val
            if score > best_score:
                best_score = score
                best_a = cand
        return np.asarray(best_a, dtype=np.float64).reshape(4)
