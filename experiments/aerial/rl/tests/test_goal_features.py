"""Unit tests for goal-relative reward features (V1-②)."""
from __future__ import annotations

import numpy as np

from experiments.aerial.rl.buffer import Transition
from experiments.aerial.rl.env.obs import Observation
from experiments.aerial.rl.goal_features import (
    GOAL_REL_DIM,
    REWARD_AUX_DIM,
    analytic_progress,
    attach_goal,
    body_vel_from_obs,
    fit_goal_from_progress,
    goal_rel_body,
    resolve_episode_goal,
    reward_aux_features,
)


def test_goal_rel_body_axis_aligned():
    g = goal_rel_body(pos=np.zeros(3), yaw=0.0, goal=np.array([3.0, 4.0, 0.0]))
    assert g.shape == (GOAL_REL_DIM,)
    np.testing.assert_allclose(g[:3], [3.0, 4.0, 0.0], atol=1e-5)
    np.testing.assert_allclose(g[3], 5.0, atol=1e-5)


def test_fit_goal_recovers_known_goal():
    goal = np.array([10.0, 0.0, 0.0], dtype=np.float64)
    pos = np.stack([np.array([float(i), 0.0, 0.0]) for i in range(8)], axis=0)
    d = np.linalg.norm(pos - goal[None, :], axis=1)
    prog = np.zeros(len(pos))
    prog[:-1] = d[:-1] - d[1:]
    got = fit_goal_from_progress(pos, prog)
    # Along a straight approach, goals beyond the last pose are underdetermined;
    # require reconstructed progress to match, not a unique g.
    d_hat = np.linalg.norm(pos - got[None, :], axis=1)
    pred = d_hat[:-1] - d_hat[1:]
    np.testing.assert_allclose(pred, prog[:-1], atol=1e-3)
    assert got[0] >= pos[-1, 0] - 1e-3


def test_resolve_prefers_info_goal():
    obs = Observation(
        rgb=np.zeros((4, 4, 3), np.uint8),
        state=np.array([0, 0, 0, 0, 0, 0, 0], np.float32),
    )
    tr = Transition(obs=obs, action=np.zeros(4, np.float32), reward=1.0, done=False,
                    info={"goal": np.array([9.0, 1.0, 2.0], np.float32)})
    g = resolve_episode_goal([tr], allow_fit=False)
    np.testing.assert_allclose(g, [9.0, 1.0, 2.0])


def test_attach_goal_stamps_obs_info():
    obs = Observation(
        rgb=np.zeros((4, 4, 3), np.uint8),
        state=np.array([1, 2, 3, 0, 0, 0, 0.1], np.float32),
    )
    tr = Transition(obs=obs, action=np.zeros(4, np.float32), reward=0.0, done=True)
    attach_goal([tr], np.array([5.0, 6.0, 7.0]))
    np.testing.assert_allclose(tr.obs.info["goal"], [5.0, 6.0, 7.0])


def test_body_vel_and_reward_aux_analytic():
    obs = Observation(
        rgb=np.zeros((4, 4, 3), np.uint8),
        # state: x,y,z, vx,vy,vz, yaw — world vel +x at yaw=0 → body fwd
        state=np.array([0, 0, 0, 5.0, 0, 0, 0.0], np.float32),
    )
    obs.info["goal"] = np.array([10.0, 0.0, 0.0], np.float32)
    vb = body_vel_from_obs(obs)
    np.testing.assert_allclose(vb, [5.0, 0.0, 0.0], atol=1e-5)
    g = goal_rel_body(obs.position, obs.yaw, obs.info["goal"])
    a = np.array([1.0, 0.0, 0.0, 0.0], np.float32)
    aux = reward_aux_features(g, vb, a, dt=0.2, w_maneuver=0.01)
    assert aux.shape == (REWARD_AUX_DIM,)
    # vel*dt = 1.0 forward → same as moving 1m toward goal at dist=10
    expect = analytic_progress(g, vb * 0.2, a, w_maneuver=0.01)
    np.testing.assert_allclose(aux[-1], expect, atol=1e-5)
    np.testing.assert_allclose(expect, 1.0 - 0.01, atol=1e-4)
