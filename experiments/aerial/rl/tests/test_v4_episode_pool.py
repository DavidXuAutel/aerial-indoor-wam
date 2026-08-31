"""Unit tests for P0c episode pool / drop counters (no renderer)."""
from __future__ import annotations

from typing import Any, Dict, Optional

import numpy as np
import pytest

from experiments.aerial.rl import v0_rollout_eval as rollout
from experiments.aerial.rl import v4_episode_pool as epool
from experiments.aerial.rl.buffer import Episode, Transition
from experiments.aerial.rl.env.obs import Observation
from experiments.aerial.rl.train_rl import HeuristicPolicy


class _OkEnv:
    def __init__(self, *, step_hz: float = 5.0) -> None:
        self.config = type("C", (), {"step_hz": float(step_hz)})()
        self._pos = np.zeros(3, dtype=np.float64)
        self._goal = np.array([30.0, 0.0, 0.0], dtype=np.float64)
        self._step = 0

    @property
    def goal(self) -> Optional[np.ndarray]:
        return self._goal

    def reset(self, episode: Optional[Dict[str, Any]] = None) -> Observation:
        self._pos = np.zeros(3, dtype=np.float64)
        self._step = 0
        return self._observe(False)

    def step(self, action: np.ndarray) -> tuple[Observation, Dict[str, Any]]:
        self._step += 1
        self._pos[0] += float(action[0])
        return self._observe(False), {}

    def _observe(self, collided: bool) -> Observation:
        state = np.array([*self._pos[:3], 0, 0, 0, 0.0], np.float32)
        return Observation(
            rgb=np.zeros((8, 8, 3), np.uint8),
            state=state,
            depth=np.full((8, 8), 5.0, np.float32),
            collided=collided,
            info={},
        )


class _FailThenOkEnv(_OkEnv):
    """First reset fails (empty episode path), second succeeds."""

    def __init__(self) -> None:
        super().__init__()
        self._resets = 0

    def reset(self, episode: Optional[Dict[str, Any]] = None) -> Observation:
        self._resets += 1
        if self._resets <= 1:
            return self._observe(True)  # spawn collided → empty episode
        return super().reset(episode)


def _make_episode() -> Dict[str, np.ndarray]:
    eps = rollout.make_start_episodes(1, seed=0)
    return eps[0]


def test_classify_resilient_drop_kind():
    assert epool.classify_resilient_drop_kind("spawn_collision") == "n_invalid_spawn"
    assert epool.classify_resilient_drop_kind("proprio_jitter") == "n_invalid_spawn"
    assert epool.classify_resilient_drop_kind("health") == "n_none_returned"


def test_split_primary_spare_manifest_deterministic():
    episodes = [{"start": np.zeros(3)} for _ in range(24)]
    primary, spare, manifest = epool.split_primary_spare(
        episodes, target_n=16, spare_count=8, layer="test", seed=42,
    )
    assert len(primary) == 16
    assert len(spare) == 8
    assert manifest.target_n == 16
    assert len(manifest.consume_order) == 8
    _, _, manifest2 = epool.split_primary_spare(
        episodes, target_n=16, spare_count=8, layer="test", seed=42,
    )
    assert manifest.consume_order == manifest2.consume_order


def test_run_paired_two_arm_pair_broken(monkeypatch: pytest.MonkeyPatch):
    counters = epool.EpisodeDropCounters()

    def ok_arm() -> tuple[Optional[Episode], Optional[str]]:
        tr = Transition(
            obs=Observation(
                rgb=np.zeros((2, 2, 3), np.uint8),
                state=np.zeros(7, np.float32),
                depth=None,
                collided=False,
                info={},
            ),
            action=np.zeros(4, np.float32),
            reward=0.0,
            done=False,
            info={},
            next_obs=None,
        )
        return [tr], None

    def fail_arm() -> tuple[Optional[Episode], Optional[str]]:
        return None, "health"

    ep_a, ep_b, ok = epool.run_paired_two_arm(
        None, _make_episode(),
        run_arm_a=ok_arm, run_arm_b=fail_arm, counters=counters,
    )
    assert ep_a is None and ep_b is None and not ok
    assert counters.n_pair_broken == 1
    assert counters.n_none_returned == 0
    assert counters.n_invalid_spawn == 0


def test_fill_to_target_n_uses_spare(monkeypatch: pytest.MonkeyPatch):
    primary = [_make_episode() for _ in range(2)]
    spare = [_make_episode() for _ in range(2)]
    _, _, manifest = epool.split_primary_spare(
        primary + spare, target_n=2, spare_count=2, seed=0,
    )
    calls: list[int] = []

    def score_one(epi: Dict[str, np.ndarray], counters: epool.EpisodeDropCounters) -> bool:
        calls.append(1)
        # First two fail, third succeeds → needs spare refill.
        return len(calls) >= 3

    result = epool.fill_to_target_n(
        None, primary[:2], spare[:2], manifest, target_n=1, score_one=score_one,
    )
    assert result.n_scored == 1
    assert result.spare_consumed >= 1
    assert result.authoritative


def test_run_progress_eval_p0c_scores_with_ok_env():
    env = _OkEnv()
    policy = HeuristicPolicy(goal_getter=lambda: env.goal)
    episodes = [_make_episode() for _ in range(4)]
    primary, spare, manifest = epool.split_primary_spare(
        episodes, target_n=2, spare_count=2, seed=1,
    )
    prog, result = epool.run_progress_eval_p0c(
        env, policy, policy, primary, spare, manifest,
        target_n=2, max_steps=5, reward_cfg=None, retry_sleep_s=0.0,
    )
    assert result.n_scored == 2
    assert result.authoritative
    assert len(prog["policy_progress_sums"]) == 2
    assert result.counters.to_dict() == {
        "n_invalid_spawn": 0,
        "n_none_returned": 0,
        "n_pair_broken": 0,
    }
