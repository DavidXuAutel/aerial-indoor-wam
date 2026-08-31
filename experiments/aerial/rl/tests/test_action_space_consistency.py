"""C2 action-space consistency: imagined action set == deployed action set.

Landed 2026-08-18 (proposal §4.1). §A.4 showed V4-① 's rank inversion came from
the *unbounded action channel*: ``imagine()`` never clipped, every deployed path
clips to ``body_delta_limits(1/step_hz)``, and with ``w_progress:w_maneuver =
100:1`` "make ‖a‖ big" was unconditionally profitable in imagination.

The fix lands on the **sampling law** (``a = limits ⊙ tanh(u)`` with the tanh
Jacobian in ``log_prob``), not on a clip line, because the actor update is
REINFORCE: a literal clip would score boundary atoms under an unclipped Gaussian
and collapse exploration. These tests pin both halves — the law is bounded, and
the deployed-box clip inside ``imagine()`` is measurably a no-op under it.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

pytest.importorskip("torch")

import torch

from experiments.aerial.rl.actor_critic import (
    POLICY_TANH_BOUNDED,
    POLICY_UNBOUNDED_LEGACY,
    ActorCriticConfig,
    ImaginationActorPolicy,
    LatentActorCritic,
)
from experiments.aerial.rl.dynamics import StubLatentDynamics
from experiments.aerial.rl.env.action import body_delta_limits
from experiments.aerial.rl.imagination import imagine
from experiments.aerial.rl.planner import ImaginationPlanner, default_candidates
from experiments.aerial.rl.reward import RewardConfig
from experiments.aerial.rl.tests.test_followups import _obs

STEP_HZ = 5.0  # the rate the V0/V1 corpora and rollouts actually run at


def _ac(**kw):
    cfg = ActorCriticConfig(latent_dim=8, step_hz=STEP_HZ, device="cpu", **kw)
    return LatentActorCritic(config=cfg)


class _BigForwardPolicy:
    """Deliberately out-of-box action (the pre-C2 failure mode)."""

    def act_latent(self, z):
        return np.array([9.0, 0.0, 0.0, 0.0], dtype=np.float64)


# -- the box itself ------------------------------------------------------


def test_limits_come_from_deployed_step_hz():
    cfg = ActorCriticConfig(step_hz=STEP_HZ)
    expected = body_delta_limits(1.0 / STEP_HZ)
    assert np.allclose(cfg.action_limits, expected)
    # Same numbers the deployed clip uses (collector.py:167).
    assert np.allclose(cfg.action_limits, [1.0, 0.4, 0.4, math.pi / 10.0])


def test_default_policy_class_is_bounded():
    ac = _ac()
    assert ac.config.policy_class == POLICY_TANH_BOUNDED
    assert ac.bounded is True


def test_action_scale_default_is_unity_gain():
    # It was 3.0 as a raw output gain (an unbounded magnitude multiplier); under
    # C2 it is a pre-tanh gain, and >1 only pre-saturates tanh.
    assert ActorCriticConfig.action_scale == 1.0


# -- the sampling law is bounded -----------------------------------------


def test_sampled_actions_stay_inside_the_deployed_box():
    ac = _ac()
    lim = ac.action_limits
    rng = np.random.default_rng(0)
    torch.manual_seed(0)
    for _ in range(200):
        z = rng.normal(scale=3.0, size=8)
        a = ac.act_latent(z)
        assert np.all(np.abs(a) <= lim + 1e-9), (a, lim)


def test_deterministic_action_also_inside_box():
    ac = _ac()
    a = ac.act_latent(np.zeros(8), deterministic=True)
    assert np.all(np.abs(a) <= ac.action_limits + 1e-9)


def test_large_pre_tanh_gain_cannot_escape_the_box():
    """Even a saturating gain only pushes actions onto the boundary."""
    ac = _ac(action_scale=50.0)
    torch.manual_seed(1)
    rng = np.random.default_rng(2)
    for _ in range(50):
        a = ac.act_latent(rng.normal(size=8))
        assert np.all(np.abs(a) <= ac.action_limits + 1e-9)


# -- the likelihood is the change-of-variables one -----------------------


def test_logp_matches_torch_transformed_distribution():
    """Independent check against torch's own tanh + affine transform stack."""
    ac = _ac()
    z = np.random.default_rng(3).normal(size=(6, 8))
    torch.manual_seed(4)
    acts = np.stack([ac.act_latent(z[i]) for i in range(z.shape[0])], axis=0)

    logp, _, _ = ac.evaluate_actions(z, acts)

    z_t = ac._z_tensor(z)
    mean, std = ac._pre_dist(z_t)
    base = torch.distributions.Normal(mean, std)
    tf = torch.distributions.TransformedDistribution(
        base,
        [
            torch.distributions.transforms.TanhTransform(),
            torch.distributions.transforms.AffineTransform(loc=0.0, scale=ac._limits),
        ],
    )
    ref = tf.log_prob(torch.as_tensor(acts, dtype=torch.float32)).sum(-1)
    assert torch.allclose(logp, ref, atol=2e-2, rtol=2e-3), (logp, ref)


def test_squashing_reduces_entropy():
    """H(a) = H(u) + E[log|det J|], and the Jacobian term is negative here."""
    bounded = _ac()
    legacy = _ac(policy_class=POLICY_UNBOUNDED_LEGACY)
    legacy._actor.load_state_dict(bounded._actor.state_dict())
    legacy._log_std.data = bounded._log_std.data.clone()

    z = np.zeros((4, 8))
    torch.manual_seed(5)
    acts = np.stack([bounded.act_latent(z[i]) for i in range(4)], axis=0)
    _, ent_b, _ = bounded.evaluate_actions(z, acts)
    _, ent_u, _ = legacy.evaluate_actions(z, acts)
    assert float(ent_b.mean()) < float(ent_u.mean())


def test_off_box_actions_score_finite_not_nan():
    """Diagnosis path: other policies' arms may sit outside the box."""
    ac = _ac()
    acts = np.array([[9.0, -9.0, 0.4, 0.0], [1.0, 0.4, 0.4, math.pi / 10.0]])
    logp, ent, _ = ac.evaluate_actions(np.zeros((2, 8)), acts)
    assert torch.all(torch.isfinite(logp))
    assert torch.all(torch.isfinite(ent))


# -- the invalidated policy class is replay-only --------------------------


def test_update_refuses_legacy_policy_class():
    ac = _ac(policy_class=POLICY_UNBOUNDED_LEGACY)
    dyn = StubLatentDynamics(goal=np.array([10.0, 0.0, 0.0]), latent_dim=8)
    roll = imagine(dyn, ImaginationActorPolicy(ac), dyn.encode(_obs())[None], 4,
                   reward_cfg=RewardConfig())
    with pytest.raises(RuntimeError, match="refusing to train"):
        ac.update(roll)


def test_pre_c2_checkpoint_loads_as_legacy_and_is_untrainable(tmp_path):
    ac = _ac()
    payload = {
        "actor": ac._actor.state_dict(),
        "critic": ac._critic.state_dict(),
        "log_std": ac._log_std.detach().cpu(),
        # Pre-C2 payloads have no policy_class / action_limits.
        "config": {"latent_dim": 8, "action_scale": 3.0, "device": "cpu"},
    }
    path = tmp_path / "v4_ac_pre_c2.pt"
    torch.save(payload, path)

    restored = LatentActorCritic.load_from_checkpoint(path)
    assert restored.config.policy_class == POLICY_UNBOUNDED_LEGACY
    assert restored.bounded is False
    assert restored.config.action_scale == 3.0  # replays the old gain exactly

    dyn = StubLatentDynamics(goal=np.array([10.0, 0.0, 0.0]), latent_dim=8)
    roll = imagine(dyn, ImaginationActorPolicy(restored), dyn.encode(_obs())[None], 3,
                   reward_cfg=RewardConfig())
    with pytest.raises(RuntimeError, match="refusing to train"):
        restored.update(roll)


def test_c2_checkpoint_round_trips_bounded(tmp_path):
    ac = _ac()
    path = tmp_path / "v4_ac_c2.pt"
    torch.save(
        {
            "actor": ac._actor.state_dict(),
            "critic": ac._critic.state_dict(),
            "log_std": ac._log_std.detach().cpu(),
            "config": ac.config.__dict__,
        },
        path,
    )
    restored = LatentActorCritic.load_from_checkpoint(path)
    assert restored.bounded is True
    assert np.allclose(restored.action_limits, ac.action_limits)


# -- imagine(): the clip is measurably a no-op ---------------------------


def test_imagine_clip_is_noop_under_bounded_policy():
    ac = _ac()
    dyn = StubLatentDynamics(goal=np.array([30.0, 0.0, 0.0]), latent_dim=8)
    z0 = np.stack([dyn.encode(_obs())] * 4, axis=0)
    torch.manual_seed(6)
    roll = imagine(
        dyn, ImaginationActorPolicy(ac), z0, 10,
        reward_cfg=RewardConfig(), action_limits=ac.action_limits,
    )
    assert roll.n_action_clipped == 0
    assert np.all(np.abs(roll.actions) <= ac.action_limits + 1e-9)


def test_imagine_clip_counts_out_of_box_actions():
    dyn = StubLatentDynamics(goal=np.array([30.0, 0.0, 0.0]), latent_dim=8)
    z0 = dyn.encode(_obs())[None]
    lim = body_delta_limits(1.0 / STEP_HZ)
    roll = imagine(dyn, _BigForwardPolicy(), z0, 5, reward_cfg=RewardConfig(),
                   action_limits=lim)
    assert roll.n_action_clipped == 5  # one axis, every step
    assert np.all(np.abs(roll.actions) <= lim + 1e-9)


def test_imagine_without_limits_stays_unbounded_for_audit_replay():
    dyn = StubLatentDynamics(goal=np.array([30.0, 0.0, 0.0]), latent_dim=8)
    roll = imagine(dyn, _BigForwardPolicy(), dyn.encode(_obs())[None], 3,
                   reward_cfg=RewardConfig())
    assert roll.n_action_clipped == 0
    assert float(roll.actions[0, 0, 0]) == 9.0


def test_imagine_rejects_bad_limits():
    dyn = StubLatentDynamics(goal=np.array([1.0, 0.0, 0.0]), latent_dim=8)
    with pytest.raises(ValueError):
        imagine(dyn, _BigForwardPolicy(), dyn.encode(_obs())[None], 2,
                action_limits=np.array([1.0, 0.0, 0.4, 0.3]))


# -- planner: opt-in only, V1 deployed path unchanged by default ---------


def test_planner_default_keeps_unclipped_candidate_scoring():
    """Direct ImaginationPlanner() still defaults to None (V1 unit tests)."""
    planner = ImaginationPlanner(
        StubLatentDynamics(goal=np.array([50.0, 0.0, 0.0]), latent_dim=8), horizon=3,
    )
    assert planner.action_limits is None
    cands = default_candidates(np.array([9.0, 0.0, 0.0, 0.0]))
    assert max(float(abs(c[0])) for c in cands) > 1.0  # still out of the box


def test_build_planner_sets_action_limits_from_step_hz():
    """V4 RUNBOOK P6: deployed planner path clips candidates to body_delta_limits."""
    from experiments.aerial.rl.train_rl import _build_planner

    cfg = {"planner": {"enable": True, "horizon": 3}, "env": {"step_hz": 5.0}}
    dyn = StubLatentDynamics(goal=np.array([50.0, 0.0, 0.0]), latent_dim=8)
    planner = _build_planner(cfg, dyn, RewardConfig())
    assert planner is not None
    lim = body_delta_limits(1.0 / STEP_HZ)
    assert np.allclose(planner.action_limits, lim)


def test_planner_action_limits_clips_candidates():
    lim = body_delta_limits(1.0 / STEP_HZ)
    dyn = StubLatentDynamics(goal=np.array([50.0, 0.0, 0.0]), latent_dim=8)
    planner = ImaginationPlanner(dyn, horizon=3, reward_cfg=RewardConfig(),
                                 action_limits=lim)
    planned = planner.plan(_obs(), np.array([9.0, 0.0, 0.0, 0.0]))
    assert np.all(np.abs(planned) <= lim + 1e-9)
