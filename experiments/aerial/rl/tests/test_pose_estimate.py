"""Tests for mainline pose contract (RUNBOOK_indoor_0xm A0)."""
from __future__ import annotations

import numpy as np
import pytest

from experiments.aerial.rl.env.obs import Observation
from experiments.aerial.rl.goal_features import goal_rel_from_obs
from experiments.aerial.rl.pose_estimate import (
    GtProxyPoseEstimator,
    OdomFromImuRgbPoseEstimator,
    make_pose_estimator,
    stamp_pose_on_obs,
)


def _obs(x: float = 0.0, yaw: float = 0.0, *, goal=None) -> Observation:
    state = np.array([x, 0.0, 2.0, 0.0, 0.0, 0.0, yaw], dtype=np.float32)
    rgb = np.zeros((8, 8, 3), dtype=np.uint8)
    info = {}
    if goal is not None:
        info["goal"] = np.asarray(goal, dtype=np.float32).reshape(3)
    return Observation(rgb=rgb, state=state, info=info)


def test_goal_rel_requires_pose_or_declared_gt_proxy():
    obs = _obs(goal=[10.0, 0.0, 2.0])
    with pytest.raises(RuntimeError, match="silent GT"):
        goal_rel_from_obs(obs)


def test_goal_rel_from_stamped_odom():
    obs = _obs(goal=[10.0, 0.0, 2.0])
    est = OdomFromImuRgbPoseEstimator()
    pe = est.reset(obs)
    stamp_pose_on_obs(obs, pe)
    gr = goal_rel_from_obs(obs)
    assert gr[3] > 9.0


def test_odom_integrates_action_not_gt_position():
    obs0 = _obs(x=0.0, goal=[10.0, 0.0, 2.0])
    est = OdomFromImuRgbPoseEstimator()
    est.reset(obs0)
    obs1 = _obs(x=99.0, goal=[10.0, 0.0, 2.0])
    pe = est.update(obs1, action=np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64), dt=0.2)
    assert pe.p_hat[0] == pytest.approx(1.0)
    assert pe.p_hat[0] != pytest.approx(99.0)


def test_odom_reset_anchors_spawn_world_coords():
    """Dead-reckoning must anchor at spawn, not origin — AirSim routes use large world XY."""
    obs0 = _obs(x=-729.62, yaw=0.0, goal=[-717.0, -35.0, 2.0])
    est = OdomFromImuRgbPoseEstimator()
    pe0 = est.reset(obs0)
    assert pe0.p_hat[0] == pytest.approx(-729.62)
    assert pe0.psi_hat == pytest.approx(0.0)
    obs1 = _obs(x=-728.62, yaw=0.0, goal=[-717.0, -35.0, 2.0])
    obs1.state[0] = -728.62
    pe1 = est.update(obs1, action=np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64), dt=0.2)
    assert pe1.p_hat[0] == pytest.approx(-728.62)


def test_gt_proxy_explicit_ok():
    obs = _obs(goal=[10.0, 0.0, 2.0])
    pe = GtProxyPoseEstimator().reset(obs)
    stamp_pose_on_obs(obs, pe)
    gr = goal_rel_from_obs(obs)
    assert gr[0] > 9.0


def test_make_pose_estimator_sources():
    assert make_pose_estimator("gt_proxy").pose_source == "gt_proxy"
    assert make_pose_estimator("odom_from_imu_rgb").pose_source == "odom_from_imu_rgb"
