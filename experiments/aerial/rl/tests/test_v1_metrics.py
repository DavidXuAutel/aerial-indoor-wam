"""Tests for V1 gate metrics (re-freeze §1.2)."""
from __future__ import annotations

import numpy as np

from experiments.aerial.rl import v1_metrics


def test_collision_reduction_pass():
    out = v1_metrics.check_collision_reduction(0.10, 0.07, delta=0.20)
    assert out["ok"] is True
    assert abs(out["target_max"] - 0.08) < 1e-9


def test_collision_reduction_tied_zero_not_authoritative_by_default():
    out = v1_metrics.check_collision_reduction(0.0, 0.0, shield_off_coll_rate=1.0)
    assert out["ok"] is False
    assert out["reason"] == "tied_zero_not_authoritative"
    assert out["authoritative"] is False


def test_collision_reduction_tied_zero_soft_opt_in():
    out = v1_metrics.check_collision_reduction(
        0.0, 0.0, shield_off_coll_rate=1.0, allow_tied_zero=True,
    )
    assert out["ok"] is True
    assert out["baseline_kind"] == "tied_zero_collision_bearing"


def test_collision_reduction_zero_without_off_still_invalid():
    out = v1_metrics.check_collision_reduction(0.0, 0.0)
    assert out["ok"] is False
    assert out["reason"] == "invalid v0_coll_rate baseline"


def test_collision_reduction_delta_is_authoritative():
    out = v1_metrics.check_collision_reduction(0.50, 0.30, delta=0.20)
    assert out["ok"] is True
    assert out["authoritative"] is True
    assert out["baseline_kind"] == "delta_reduction"


def test_wm_fidelity_coll_na_when_no_collision_trajs():
    verdict = {
        "reward_ok": True,
        "done_ok": True,
        "recon_growth_ok": True,
        "passed": False,
        "coll_ok": False,
    }
    agg = {"coll_traj_pos": 0, "coll_auroc": float("nan"), "latent_norm_max": 19.0}
    out = v1_metrics.check_wm_fidelity(verdict, agg=agg, recon_growth_ok=True)
    assert out["coll_ok"] is None
    assert out["coll_insufficient"] is True
    assert out["coll_claimed"] is False
    assert out["ok"] is True


def test_wm_fidelity_coll_na_when_pos_one():
    """08-15 merge shape: pos=1 is diagnostic-only, not a ②-coll claim."""
    verdict = {
        "reward_ok": True,
        "done_ok": True,
        "recon_growth_ok": True,
        "coll_ok": True,
    }
    agg = {"coll_traj_pos": 1, "coll_auroc": 0.909, "latent_norm_max": 21.3}
    out = v1_metrics.check_wm_fidelity(verdict, agg=agg, recon_growth_ok=True)
    assert out["coll_ok"] is None
    assert out["coll_claimed"] is False
    assert out["coll_insufficient"] is True
    assert out["ok"] is True


def test_wm_fidelity_coll_claimed_when_pos_ge_3():
    verdict = {"reward_ok": True, "done_ok": True, "recon_growth_ok": True}
    agg = {"coll_traj_pos": 5, "coll_auroc": 0.972, "latent_norm_max": 21.6}
    out = v1_metrics.check_wm_fidelity(verdict, agg=agg, recon_growth_ok=True)
    assert out["coll_ok"] is True
    assert out["coll_claimed"] is True
    assert out["coll_insufficient"] is False
    assert out["ok"] is True


def test_wm_fidelity_coll_claimed_fails_low_auroc():
    verdict = {"reward_ok": True, "done_ok": True, "recon_growth_ok": True}
    agg = {"coll_traj_pos": 5, "coll_auroc": 0.50, "latent_norm_max": 19.0}
    out = v1_metrics.check_wm_fidelity(verdict, agg=agg, recon_growth_ok=True)
    assert out["coll_ok"] is False
    assert out["coll_claimed"] is True
    assert out["ok"] is False


def test_wm_fidelity_fails_on_reward():
    verdict = {"reward_ok": False, "done_ok": True, "recon_growth_ok": True}
    agg = {"coll_traj_pos": 0, "latent_norm_max": 19.0}
    out = v1_metrics.check_wm_fidelity(verdict, agg=agg, recon_growth_ok=True)
    assert out["ok"] is False


def test_aggregate_rejects_non_authoritative_signal1():
    s1 = {"ok": True, "authoritative": False, "baseline_kind": "tied_zero_collision_bearing"}
    s2 = {"ok": True}
    s3 = {"ok": True, "authoritative": True, "phase": "auth"}
    out = v1_metrics.aggregate_v1_verdict({"1": s1, "2": s2, "3": s3})
    assert out["ok"] is False
    assert "signal 1" in out["reason"]


def test_aggregate_rejects_proxy_signal3_for_merge():
    s1 = {"ok": True, "authoritative": True}
    s2 = {"ok": True}
    s3 = {"ok": True, "authoritative": False, "phase": "proxy"}
    out = v1_metrics.aggregate_v1_verdict({"1": s1, "2": s2, "3": s3})
    assert out["ok"] is False
    assert "Phase 2" in out["reason"]


def test_dual_channel_proxy_marks_phase():
    d = np.array([True, False, False])
    t = np.array([False, True, False])
    out = v1_metrics.check_dual_channel_independence(d, t, phase="proxy")
    assert out["phase"] == "proxy"
    assert out["authoritative"] is False


def test_dual_channel_auth_requires_tau_only_and_mae():
    # mostly independent channels, low co-trigger
    d = np.array([True, True, False, False, False, False, False, False] * 20)
    t = np.array([False, False, True, False, False, False, False, False] * 20)
    out = v1_metrics.check_dual_channel_independence(
        d, t, phase="auth", tau_mae_s=1.5, depth_pred_vs_gt_both_fail_frac=0.1
    )
    assert out["authoritative"] is True
    assert out["both_fail_max"] == 0.20
    assert out["ok"] is True


def test_dual_channel_auth_fails_high_mae():
    d = np.array([True, False, False, False] * 50)
    t = np.array([False, True, False, False] * 50)
    out = v1_metrics.check_dual_channel_independence(d, t, phase="auth", tau_mae_s=3.5)
    assert out["ok"] is False
    assert "tau_mae" in out.get("fail_reasons", [])


def test_aggregate_accepts_auth_signal3():
    s1 = {"ok": True}
    s2 = {"ok": True}
    s3 = {"ok": True, "authoritative": True, "phase": "auth"}
    out = v1_metrics.aggregate_v1_verdict({"1": s1, "2": s2, "3": s3})
    assert out["ok"] is True
