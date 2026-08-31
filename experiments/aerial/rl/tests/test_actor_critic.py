"""Unit tests for V4 λ-return actor-critic (mock dynamics, no env)."""
from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("torch")

from experiments.aerial.rl.actor_critic import (
    ActorCriticConfig,
    ImaginationActorPolicy,
    LatentActorCritic,
    compute_lambda_returns,
    normalize_advantage,
)
from experiments.aerial.rl.dynamics import StubLatentDynamics
from experiments.aerial.rl.imagination import imagine
from experiments.aerial.rl.reward import RewardConfig


class _ForwardPolicy:
    def act_latent(self, z):
        return np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64)


def test_compute_lambda_returns_bootstrap():
    rews = np.array([[1.0, 1.0]], dtype=np.float64)
    vals = np.array([[0.0, 0.5, 1.0]], dtype=np.float64)
    ret = compute_lambda_returns(rews, vals, gamma=0.9, lambda_gae=0.95)
    assert ret.shape == (1, 2)
    assert np.all(np.isfinite(ret))


def test_normalize_advantage_zero_std():
    adv = np.ones(8)
    out = normalize_advantage(adv)
    assert np.allclose(out, 0.0)


def test_act_latent_returns_4d():
    ac = LatentActorCritic(config=ActorCriticConfig(latent_dim=8, device="cpu"))
    z = np.zeros(8, dtype=np.float64)
    a = ac.act_latent(z)
    assert a.shape == (4,)
    assert np.all(np.isfinite(a))


def test_imagination_actor_policy_adapter():
    ac = LatentActorCritic(config=ActorCriticConfig(latent_dim=8, device="cpu"))
    pol = ImaginationActorPolicy(ac, deterministic=True)
    a = pol.act_latent(np.zeros(8))
    assert a.shape == (4,)


def test_update_on_mock_rollout():
    from experiments.aerial.rl.tests.test_followups import _obs

    dyn = StubLatentDynamics(
        goal=np.array([10.0, 0.0, 0.0]), latent_dim=8, success_dist_m=1.0,
    )
    z0 = dyn.encode(_obs())
    z_batch = np.stack([z0, z0], axis=0)
    roll = imagine(
        dyn, _ForwardPolicy(), z_batch, horizon=5,
        reward_cfg=RewardConfig(w_maneuver=0.0),
    )
    ac = LatentActorCritic(config=ActorCriticConfig(latent_dim=8, device="cpu"))
    out = ac.update(roll)
    assert out["status"] == "updated"
    assert out["n_steps"] > 0
    assert np.isfinite(out["actor_loss"])
    assert np.isfinite(out["critic_loss"])


def test_update_twice_loss_finite():
    dyn = StubLatentDynamics(goal=np.array([5.0, 0.0, 0.0]), latent_dim=8)
    from experiments.aerial.rl.tests.test_followups import _obs

    z0 = dyn.encode(_obs())
    roll = imagine(dyn, _ForwardPolicy(), z0[None], horizon=8, reward_cfg=RewardConfig())
    ac = LatentActorCritic(config=ActorCriticConfig(latent_dim=8, device="cpu"))
    o1 = ac.update(roll)
    o2 = ac.update(roll)
    assert o1["status"] == "updated" and o2["status"] == "updated"
