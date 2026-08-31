"""Tests for V4 gate metrics."""
from experiments.aerial.rl import v4_metrics as m


def _pair(n: int = 8, actor: float = 12.0, heur: float = 10.0):
    return [actor] * n, [heur] * n


def test_progress_vs_heuristic_pass():
    ap, hp = _pair(8, 12.0, 10.0)
    r = m.check_progress_vs_heuristic(ap, hp, delta_p=0.10)
    assert r["ok"]
    assert r["authoritative"] is True
    assert r["n"] == 8
    assert r["mean_progress_actor"] >= r["target_min"]


def test_progress_vs_heuristic_fail():
    r = m.check_progress_vs_heuristic([10.0], [10.0], delta_p=0.10)
    assert not r["ok"]
    assert r["authoritative"] is False  # n=1 < floor 8


def test_progress_n_below_floor_non_authoritative():
    ap, hp = _pair(5, 12.0, 10.0)
    r = m.check_progress_vs_heuristic(ap, hp, delta_p=0.10)
    assert r["ok"]
    assert r["authoritative"] is False
    assert r["n_floor"] == 8


def test_safety_no_regression_pass():
    r = m.check_safety_no_regression(0.05, 0.10, near_coll_rate_ratio=0.75)
    assert r["ok"]


def test_safety_no_regression_coll_fail():
    r = m.check_safety_no_regression(0.15, 0.10)
    assert not r["ok"]


def test_aggregate_v4_verdict():
    ap, hp = _pair(8, 12.0, 10.0)
    s1 = m.check_progress_vs_heuristic(ap, hp)
    s4 = m.check_safety_no_regression(0.05, 0.10)
    v = m.aggregate_v4_verdict({"1": s1, "4": s4})
    assert v["ok"]


def test_aggregate_rejects_non_authoritative_n():
    ap, hp = _pair(5, 12.0, 10.0)
    s1 = m.check_progress_vs_heuristic(ap, hp)
    s4 = m.check_safety_no_regression(0.05, 0.10)
    v = m.aggregate_v4_verdict({"1": s1, "4": s4})
    assert not v["ok"]
    assert "1" in v.get("non_authoritative", [])


def test_v4_gate_self_check():
    from experiments.aerial.rl._v4_gate import main

    assert main(["--self-check"]) == 0
