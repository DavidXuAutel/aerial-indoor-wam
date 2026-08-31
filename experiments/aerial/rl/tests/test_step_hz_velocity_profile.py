"""Unit tests for step_hz velocity profile analysis."""
from __future__ import annotations

from experiments.aerial.rl.step_hz_velocity_profile import (
    body_fwd_velocity,
    run_profile,
    summarize_steps,
)
from experiments.aerial.rl.env.mock_env import MockAirSimDroneEnv, MockEnvConfig
import numpy as np


def test_body_fwd_velocity_heading():
    state = np.array([0, 0, 0, 3.0, 4.0, 0, 0.0], dtype=np.float32)  # yaw=0 → vx
    assert abs(body_fwd_velocity(state) - 3.0) < 1e-5
    state = np.array([0, 0, 0, 3.0, 4.0, 0, np.pi / 2], dtype=np.float32)
    assert abs(body_fwd_velocity(state) - 4.0) < 1e-5


def test_mock_profile_reaches_commanded_cruise():
    env = MockAirSimDroneEnv(MockEnvConfig(step_hz=5.0))
    out = run_profile(env, step_hz=5.0)
    env.close()
    s = out["summary"]
    assert s["achieved_hz_median"] >= 4.9
    assert s["v_fwd_cruise_median_m_s"] is not None
    assert s["v_fwd_cruise_median_m_s"] >= 4.5


def test_summarize_empty():
    assert summarize_steps([])["n"] == 0
