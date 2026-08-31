"""Unit tests for V4-⓪ scorers (torch-free)."""
from __future__ import annotations

import numpy as np

from experiments.aerial.rl.v4_zero_eval import (
    ZeroThresholds,
    build_tau_miss_diag,
    check_0a,
    check_0c,
    check_0d,
    check_0d_from_triggered,
    check_0h,
    check_support_b,
    check_tau_miss,
    clearance_sweep,
    dhat_tau_miss_crosstab,
    engage_release_hysteresis,
    near_absrel_gt_bins,
    pixel_absrel_stats,
    suggest_delta,
    tau_by_speed_bins,
    temporal_min_per_episode,
)


def test_pixel_absrel_near_domain():
    gt = np.array([1.0, 2.0, 4.0, 5.0])
    pred = np.array([1.1, 2.2, 4.4, 5.5])
    stats = pixel_absrel_stats(pred, gt, gt_lo=0.0, gt_hi=3.0)
    assert stats["n"] == 2
    assert abs(stats["median_absrel"] - 0.1) < 1e-6


def test_near_absrel_gt_bins_split():
    # (0,1.5]: AbsRel 1.0; (1.5,3]: AbsRel 0.1
    gt = np.array([1.0, 1.0, 2.0, 2.0])
    pred = np.array([2.0, 2.0, 2.2, 2.2])
    bins = near_absrel_gt_bins(pred, gt, edges=(0.0, 1.5, 3.0))
    assert bins[0]["n_px"] == 2
    assert abs(bins[0]["p90_absrel"] - 1.0) < 1e-6
    assert bins[1]["n_px"] == 2
    assert abs(bins[1]["p90_absrel"] - 0.1) < 1e-6


def test_support_b_pass():
    thr = ZeroThresholds()
    ok = check_support_b([200] * 120, thr=thr)
    assert ok["ok"] is True
    assert ok["support_px"] == 24_000


def test_support_b_fail_single_frame_dominates():
    thr = ZeroThresholds()
    frames = [90000] + [500] * 20
    bad = check_support_b(frames, thr=thr)
    assert bad["ok"] is False


def test_0h_engage_miss_at_outer():
    thr = ZeroThresholds(engage_miss_max=0.10)
    eng = 12.2
    gt = np.array([12.0] * 9 + [11.0])
    dhat = np.array([11.0] * 9 + [13.0])  # 1/10 miss
    r = check_0h(gt, dhat, engage_outer_m=eng, thr=thr)
    assert r["n_cond"] == 10
    assert r["p_engage_miss"] == 0.1
    assert r["ok"] is True


def test_0d_miss_rate_and_consecutive():
    thr = ZeroThresholds(trigger_m=3.0)
    gt = np.array([2.0, 2.5, 2.0, 2.0, 4.0])
    dhat = np.array([3.5, 3.5, 3.5, 2.0, 4.0])  # two consecutive misses
    r = check_0d(gt, dhat, thr=thr)
    assert r["ok"] is False
    assert r["max_consecutive_miss"] == 3
    assert r["n_near_forward_frames"] == r["n_cond"] == 4


def test_temporal_min_per_episode_k1_identity():
    v = np.array([4.0, 3.0, 5.0, 2.0], dtype=np.float64)
    e = np.array([0, 0, 1, 1], dtype=np.int64)
    out = temporal_min_per_episode(v, e, k=1)
    assert np.allclose(out, v)


def test_temporal_min_per_episode_causal_and_resets():
    # ep0: 4,3,5 → K=2 → 4, min(4,3)=3, min(3,5)=3
    # ep1: 9,1 → K=2 → 9, min(9,1)=1  (must not see ep0)
    v = np.array([4.0, 3.0, 5.0, 9.0, 1.0], dtype=np.float64)
    e = np.array([0, 0, 0, 1, 1], dtype=np.int64)
    out = temporal_min_per_episode(v, e, k=2)
    assert np.allclose(out, [4.0, 3.0, 3.0, 9.0, 1.0])


def test_temporal_min_reduces_0d_miss_rate():
    thr = ZeroThresholds(trigger_m=3.0)
    gt = np.array([2.0, 2.0, 2.0], dtype=np.float64)
    dhat = np.array([3.5, 2.5, 3.5], dtype=np.float64)  # miss, hit, miss
    e = np.array([0, 0, 0], dtype=np.int64)
    raw = check_0d(gt, dhat, thr=thr, episode_ids=e)
    assert raw["p_miss_trigger"] == round(2 / 3, 4)
    assert raw["max_consecutive_miss"] == 1
    filt = temporal_min_per_episode(dhat, e, k=2)
    # [3.5, min(3.5,2.5)=2.5, min(2.5,3.5)=2.5] → only warm-up miss remains
    assert np.allclose(filt, [3.5, 2.5, 2.5])
    r2 = check_0d(gt, filt, thr=thr, episode_ids=e)
    assert r2["p_miss_trigger"] == round(1 / 3, 4)
    assert r2["max_consecutive_miss"] == 1


def test_temporal_min_breaks_consec_run():
    thr = ZeroThresholds(trigger_m=3.0)
    gt = np.array([2.0, 2.0, 2.0, 2.0], dtype=np.float64)
    # two consec misses, then a good read, then a miss that K=2 clears via prior good
    dhat = np.array([3.5, 3.5, 2.0, 3.5], dtype=np.float64)
    e = np.array([0, 0, 0, 0], dtype=np.int64)
    raw = check_0d(gt, dhat, thr=thr, episode_ids=e)
    assert raw["max_consecutive_miss"] == 2
    filt = temporal_min_per_episode(dhat, e, k=2)
    # 3.5, 3.5, min(3.5,2)=2, min(2,3.5)=2
    r2 = check_0d(gt, filt, thr=thr, episode_ids=e)
    assert r2["max_consecutive_miss"] == 2  # early run untouched
    assert r2["n_cond"] == 4
    # rate: raw 3/4 miss → filt 2/4
    assert abs(r2["p_miss_trigger"] - 0.5) < 1e-6


def test_engage_release_hysteresis_holds_through_overread():
    # engage at 2.5, over-read 3.5 still held until release 4.0
    dhat = np.array([2.5, 3.5, 3.5, 4.1], dtype=np.float64)
    e = np.array([0, 0, 0, 0], dtype=np.int64)
    eng = engage_release_hysteresis(dhat, e, trigger_m=3.0, release_m=4.0)
    assert eng.tolist() == [True, True, True, False]


def test_hysteresis_can_break_0d_consec():
    thr = ZeroThresholds(trigger_m=3.0)
    gt = np.array([2.0, 2.0, 2.0], dtype=np.float64)
    # hit then two over-reads — raw consec=2; with release=4 hold covers them
    dhat = np.array([2.5, 3.5, 3.5], dtype=np.float64)
    e = np.array([0, 0, 0], dtype=np.int64)
    raw = check_0d(gt, dhat, thr=thr, episode_ids=e)
    assert raw["max_consecutive_miss"] == 2
    eng = engage_release_hysteresis(dhat, e, trigger_m=3.0, release_m=4.0)
    r2 = check_0d_from_triggered(gt, eng, thr=thr, episode_ids=e)
    assert r2["max_consecutive_miss"] == 0
    assert r2["p_miss_trigger"] == 0.0


def test_heldout_episodes_seeded_split():
    from experiments.aerial.rl.holdout_split import split_holdout_indices
    from experiments.aerial.rl.v4_zero_eval import _heldout_episodes

    eps = list(range(10))
    scored, meta = _heldout_episodes(eps, 0.25, seed=0)
    _, hold_idx, meta2 = split_holdout_indices(10, frac=0.25, seed=0)
    assert meta["regime"] == "seeded_holdout"
    assert meta["holdout_indices"] == sorted(hold_idx)
    assert len(scored) == meta["n_holdout"] == 2  # round(0.25*10)=2 (banker)
    all_eps, meta0 = _heldout_episodes(eps, 0.0, seed=0)
    assert all_eps == eps
    assert meta0["regime"] == "all_episodes"


def test_train_eval_holdout_indices_match():
    from experiments.aerial.rl.holdout_split import split_holdout_indices

    t1, h1, m1 = split_holdout_indices(77, frac=0.2, seed=0)
    t2, h2, m2 = split_holdout_indices(77, frac=0.2, seed=0)
    assert sorted(h1) == sorted(h2) == m1["holdout_indices"]
    assert set(t1) | set(h1) == set(range(77))
    assert set(t1).isdisjoint(h1)


def test_clearance_sweep_aligned():
    thr = ZeroThresholds(trigger_m=3.0, min_tau_s=1.0)
    gt_fov = np.array([3.5, 4.0, 5.0, 6.0])
    dhat = np.array([2.5, 3.5, 4.0, 5.0])
    gt_fwd = np.array([3.5, 4.0, 5.0, 6.0])
    tau = np.array([2.0, 2.0, 2.0, 2.0])
    v = np.array([1.0, 1.0, 1.0, 1.0])
    rows = clearance_sweep(gt_fov, dhat, gt_fwd, tau, v, thr=thr, bin_width=1.0)
    assert rows
    assert all("clearance_lo" in r for r in rows)


def test_suggest_delta_finds_first_bin():
    thr = ZeroThresholds()
    rows = [
        {"clearance_lo": 3.0, "n": 10, "p_dhat_false_trigger": 0.2, "p_tau_false_trigger": 0.1},
        {"clearance_lo": 3.5, "n": 10, "p_dhat_false_trigger": 0.03, "p_tau_false_trigger": 0.02},
    ]
    hint = suggest_delta(rows, thr=thr)
    assert hint["suggested_lo_clearance_m"] == 3.5


def test_0f_outer_absrel_not_gated_by_0c_threshold():
    """⓪f(1)(2) are report-only — outer p90>0.50 must not fail primary merge."""
    from experiments.aerial.rl.v4_zero_eval import aggregate_verdict

    sub = {
        "0a": {"ok": True},
        "0b": {"ok": True},
        "0c": {"ok": True},
        "0h": {"ok": True},
        "0e": {"ok": True},
        "0d_legacy": {"ok": False},
        "0f": {
            "ok": True,  # support-only pre-freeze
            "median_absrel": 0.10,
            "p90_absrel": 0.80,  # would fail if wrongly using ⓪c's 0.50
        },
    }
    v = aggregate_verdict(sub)
    assert v["ok"] is True
    assert v["ok_primary"] is True
    assert v["ok_0f"] is True
    assert v["ok_0d_legacy"] is False


def test_aggregate_primary_ignores_0f_fail():
    from experiments.aerial.rl.v4_zero_eval import aggregate_verdict

    sub = {
        "0a": {"ok": True},
        "0b": {"ok": True},
        "0c": {"ok": False},
        "0h": {"ok": True},
        "0e": {"ok": True},
        "0d_legacy": {"ok": True},
        "0f": {"ok": False},
    }
    v = aggregate_verdict(sub)
    assert v["ok"] is False
    assert v["ok_primary"] is False
    assert v["ok_0f"] is False


def test_aggregate_0d_legacy_fail_does_not_block_primary():
    from experiments.aerial.rl.v4_zero_eval import aggregate_verdict

    sub = {
        "0a": {"ok": True},
        "0b": {"ok": True},
        "0c": {"ok": True},
        "0h": {"ok": True},
        "0e": {"ok": True},
        "0d_legacy": {"ok": False, "max_consecutive_miss": 2},
        "0f": {"ok": True},
    }
    v = aggregate_verdict(sub)
    assert v["ok"] is True
    assert v["ok_primary"] is True
    assert v["ok_0d_legacy"] is False


def test_check_tau_miss_rate_and_consecutive():
    thr = ZeroThresholds(min_tau_s=1.0)
    tau_gt = np.array([0.5, 0.8, 0.5, 0.5, 2.0])
    tau_hat = np.array([1.2, 0.5, 1.1, 1.2, 0.5])
    e = np.array([0, 0, 0, 0, 0])
    r = check_tau_miss(
        tau_gt,
        tau_hat,
        min_tau_s=thr.min_tau_s,
        false_trigger_max=thr.false_trigger_max,
        episode_ids=e,
    )
    assert r["n_tau_miss_cond"] == 4
    assert r["p_tau_miss"] == 0.75
    assert r["max_consecutive_tau_miss"] == 2
    assert r["ok"] is False


def test_dhat_tau_miss_crosstab_counts():
    g = np.array([2.0, 2.0, 2.0, 4.0])
    d = np.array([3.5, 2.5, 3.5, 2.0])
    tg = np.array([0.5, 0.5, 2.0, 0.5])
    th = np.array([1.2, 0.5, 1.2, 0.5])
    out = dhat_tau_miss_crosstab(g, d, tg, th, trigger_m=3.0, min_tau_s=1.0)
    assert out["n_both_cond"] == 2
    assert out["table"]["dhat_miss_and_tau_miss"] == 1
    assert out["table"]["neither"] == 1


def test_tau_by_speed_bins_includes_high_speed_tail():
    v = np.array([0.1, 1.0, 6.0])
    tg = np.array([0.5, 0.5, 0.5])
    th = np.array([1.2, 0.5, 1.2])
    rows = tau_by_speed_bins(v, tg, th, min_tau_s=1.0)
    tail = [r for r in rows if r.get("v_lo") == 5.0][0]
    assert tail["n_frames"] == 1
    assert tail["p_tau_miss"] == 1.0


def test_build_tau_miss_diag_contract_fields():
    g = np.array([2.0, 2.0])
    d = np.array([3.5, 2.5])
    th = np.array([1.2, 0.5])
    v = np.array([2.0, 2.0])
    e = np.array([0, 0])
    diag = build_tau_miss_diag(
        g,
        d,
        th,
        v,
        e,
        thr=ZeroThresholds(trigger_m=3.0, min_tau_s=1.0),
        yaml_min_depth_m=1.5,
        center_frac=0.5,
        tau_ckpt="tau.pt",
        dt_samples=[0.2, 0.2],
        dt_fallback_count=0,
    )
    assert diag["authoritative"] is False
    assert diag["p_tau_miss"] == 0.5
    assert diag["center_frac"] == 0.5
    assert diag["B_b_min_depth"]["yaml_min_depth_m"] == 1.5
    assert diag["dt_hist"]["p50"] == 0.2
