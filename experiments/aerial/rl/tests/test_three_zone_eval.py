"""Unit tests for three-zone kinematic depth budget."""
from __future__ import annotations

from experiments.aerial.rl.v4_three_zone_eval import (
    ThreeZoneSpec,
    depth_precision_vs_budget,
    kinematic_budget,
    max_engage_delay_m,
    need,
    simulate_three_zone,
)
import numpy as np


def test_need_braking_distance():
    assert abs(need(5.0, 2.0, 2.5) - 4.2) < 0.05


def test_default_spec_kinematically_feasible():
    spec = ThreeZoneSpec()
    ok, _, viol = simulate_three_zone(spec)
    assert ok, viol
    assert max_engage_delay_m(spec) > 0.1


def test_user_7_5_1_5_strict_infeasible_with_delay():
    spec = ThreeZoneSpec(l1_m=7.0, l2_m=5.0, v1_m_s=2.0, v2_m_s=1.0)
    ok, _, _ = simulate_three_zone(spec)
    assert not ok


def test_depth_budget_passes_tight_errors():
    spec = ThreeZoneSpec()
    kin = kinematic_budget(spec)
    budget = kin["max_underread_at_engage_m"]
    gt = np.array([kin["engage_outer_m"], spec.l1_m, spec.l2_m, spec.l3_m])
    dhat = gt - 0.05  # slight over-read (safe)
    v = np.full_like(gt, 5.0)
    out = depth_precision_vs_budget(gt, dhat, v, kin, spec)
    assert out["all_bands_ok"]
