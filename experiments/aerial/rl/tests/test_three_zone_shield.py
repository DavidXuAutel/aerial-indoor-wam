"""Tests for ThreeZoneSpeedShield deploy governor."""
from __future__ import annotations

import numpy as np
import pytest

from experiments.aerial.rl.env.action import body_delta_limits
from experiments.aerial.rl.env.obs import Observation
from experiments.aerial.rl.safety import ThreeZoneSpeedShield
from experiments.aerial.rl.three_zone import ThreeZoneSpec, planned_speed_m_s


def _obs(*, depth: float, v_fwd: float = 5.0, info=None):
    state = np.array([0.0, 0.0, 0.0, v_fwd, 0.0, 0.0, 0.0], dtype=np.float32)
    return Observation(
        rgb=np.zeros((8, 8, 3), dtype=np.uint8),
        state=state,
        depth=np.full((8, 8), depth, dtype=np.float32),
        info={"depth_min_pred": depth, **(info or {})},
    )


def test_planned_speed_at_boundaries():
    spec = ThreeZoneSpec()
    assert planned_speed_m_s(20.0, spec) == pytest.approx(5.0)
    assert planned_speed_m_s(spec.engage_outer_m + 0.1, spec) == pytest.approx(5.0)
    assert planned_speed_m_s(spec.l1_m, spec) == pytest.approx(2.0, abs=0.05)
    assert planned_speed_m_s(spec.l2_m, spec) == pytest.approx(1.0, abs=0.05)
    assert planned_speed_m_s(spec.l3_m * 0.5, spec) == pytest.approx(0.2, abs=0.05)


def test_three_zone_caps_forward_at_5m():
    shield = ThreeZoneSpeedShield()
    limits = body_delta_limits(0.2)
    action = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64)  # max fwd @ 5 Hz
    obs = _obs(depth=5.0)
    capped, changed = shield.apply_action(action, obs, limits=limits)
    assert changed
    assert capped[0] < 1.0
    assert capped[0] == pytest.approx(1.0 * 0.2, abs=0.05)  # ~1 m/s * 0.2s


def test_indoor_micro_limits_open_space_no_false_cap():
    """E2i diag: indoor limits must not use outdoor MAX_V for dt (was 0.15/5=0.03)."""
    zone = ThreeZoneSpec(
        l1_m=0.45, l2_m=0.28, l3_m=0.14,
        v1_m_s=0.55, v2_m_s=0.3, v_stop_m_s=0.05,
        v_cruise_m_s=0.75, dt_s=0.2,
    )
    shield = ThreeZoneSpeedShield(zone=zone, retreat_step_m=0.12, min_tau_s=0.35)
    limits = np.array([0.15, 0.08, 0.08, 0.10], dtype=np.float64)
    action = np.array([0.15, 0.0, 0.0, 0.0], dtype=np.float64)
    obs = _obs(depth=5.0)  # >> L1 — open lobby
    capped, changed = shield.apply_action(action, obs, limits=limits)
    assert not changed, "open-space cruise step must not be three_zone-capped"
    assert capped[0] == pytest.approx(0.15, abs=1e-6)
    # Near field still caps
    obs_near = _obs(depth=0.3)  # inside L2
    capped_n, changed_n = shield.apply_action(action, obs_near, limits=limits)
    assert changed_n
    assert capped_n[0] < 0.15


def test_three_zone_no_latch_on_depth():
    shield = ThreeZoneSpeedShield()
    limits = body_delta_limits(0.2)
    obs_near = _obs(depth=1.0)
    obs_far = _obs(depth=20.0)
    shield.apply_action(np.array([1.0, 0, 0, 0]), obs_near, limits=limits)
    assert not shield.should_override(obs_far)
    capped, _ = shield.apply_action(np.array([1.0, 0, 0, 0]), obs_far, limits=limits)
    assert capped[0] == pytest.approx(1.0)


def test_three_zone_tau_emergency_latches():
    shield = ThreeZoneSpeedShield(min_tau_s=2.0)
    limits = body_delta_limits(0.2)
    obs = _obs(depth=20.0, info={"tau_pred": 0.5})
    _, changed = shield.apply_action(np.zeros(4), obs, limits=limits)
    assert changed
    assert shield.last_channels == ("tau",)
    assert shield.should_override(_obs(depth=20.0))


def test_collector_three_zone_intervention():
    from experiments.aerial.rl.buffer import ReplayBuffer
    from experiments.aerial.rl.collector import RolloutCollector

    class _Env:
        def __init__(self):
            self.config = type("C", (), {"step_hz": 5.0})()
            self.goal = np.array([10.0, 0.0, 0.0])

        def reset(self, episode=None):
            return _obs(depth=10.0)

        def step(self, action):
            return _obs(depth=10.0), {}

    class _Pred:
        def reset(self):
            pass

        def predict_min(self, obs):
            return 4.0  # inside L2 → cap < max fwd

    class _Policy:
        def act(self, view):
            return np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64)

    col = RolloutCollector(
        _Env(),
        _Policy(),
        ReplayBuffer(capacity_episodes=1, seed=0),
        safety=ThreeZoneSpeedShield(),
        depth_predictor=_Pred(),
        max_steps=2,
        target_hz=0.0,
        skip_reset_collision=False,
    )
    ep, stats = col.collect_episode()
    assert stats.interventions >= 1
    assert ep[0].obs.info.get("three_zone_speed_cap_m_s") is not None
