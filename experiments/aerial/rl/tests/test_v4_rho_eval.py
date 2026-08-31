"""Unit tests for V4-⓿ scorers (torch-free)."""
from __future__ import annotations

import numpy as np

from experiments.aerial.rl.goal_features import goal_rel_body
from experiments.aerial.rl.reward import RewardConfig
from experiments.aerial.rl.v4_rho_eval import (
    RhoThresholds,
    analytic_sum_g,
    check_rho_a,
    check_rho_b,
    check_rho_c,
    default_candidate_actions,
    spearman_rho,
    top1_in_real_top_quarter,
)
from experiments.aerial.rl.env.action import body_delta_limits


def test_spearman_perfect_monotone():
    x = [1.0, 2.0, 3.0, 4.0, 5.0]
    y = [10.0, 20.0, 30.0, 40.0, 50.0]
    assert abs(spearman_rho(x, y) - 1.0) < 1e-9


def test_spearman_anti_monotone():
    x = [1.0, 2.0, 3.0, 4.0]
    y = [4.0, 3.0, 2.0, 1.0]
    assert abs(spearman_rho(x, y) + 1.0) < 1e-9


def test_top1_hit():
    real = [10.0, 5.0, 1.0, 0.0]
    imag = [0.0, 100.0, 0.0, 0.0]  # imag picks idx=1 (real score 5.0 = 2nd best)
    assert top1_in_real_top_quarter(real, imag, quantile=0.25) is False
    imag2 = [100.0, 0.0, 0.0, 0.0]  # imag picks idx=0 (real best)
    assert top1_in_real_top_quarter(real, imag2, quantile=0.25) is True


def test_default_candidates_at_least_eight():
    lim = body_delta_limits(0.2)
    cands = default_candidate_actions(lim)
    assert len(cands) >= 8


def test_analytic_sum_forward_positive():
    g = goal_rel_body(np.zeros(3), 0.0, np.array([30.0, 0.0, 1.0]))
    cfg = RewardConfig()
    lim = body_delta_limits(0.2)
    s_fwd = analytic_sum_g(g, np.array([lim[0], 0, 0, 0]), horizon=15, reward_cfg=cfg)
    s_back = analytic_sum_g(g, np.array([-lim[0], 0, 0, 0]), horizon=15, reward_cfg=cfg)
    assert s_fwd > s_back


def test_check_rho_a_pass():
    thr = RhoThresholds()
    r = check_rho_a([0.6, 0.55, 0.7, 0.5, 0.8, 0.52, 0.61, 0.58], thr=thr)
    assert r["ok"] is True


def test_check_rho_b_fail():
    thr = RhoThresholds()
    r = check_rho_b([False] * 8, thr=thr)
    assert r["ok"] is False


def test_check_rho_c_guard():
    assert check_rho_c(horizon=15, used_pearson=False, mixed_horizon=False)["ok"] is True
    assert check_rho_c(horizon=15, used_pearson=True, mixed_horizon=False)["ok"] is False
