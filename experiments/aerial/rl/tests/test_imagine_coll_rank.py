"""Unit tests for imagination collision-ranking verdict (runbook step B)."""
from __future__ import annotations

from experiments.aerial.rl.imagine_coll_rank import pairwise_gaps, verdict_from_gaps


def test_pairwise_gaps_prefers_safer_lateral():
    arms = {
        "forward": {"sum_reward": -5.0, "mean_p_coll": 0.8, "sum_progress": 1.0, "n_steps": 15},
        "left": {"sum_reward": 2.0, "mean_p_coll": 0.1, "sum_progress": 0.5, "n_steps": 15},
        "right": {"sum_reward": 1.0, "mean_p_coll": 0.2, "sum_progress": 0.4, "n_steps": 15},
        "retreat": {"sum_reward": 0.0, "mean_p_coll": 0.05, "sum_progress": -1.0, "n_steps": 15},
    }
    g = pairwise_gaps(arms)
    assert g["best_lateral"] == "left"
    assert g["return_gap_lateral_minus_forward"] == 7.0
    assert abs(g["p_coll_gap_forward_minus_lateral"] - 0.7) < 1e-9


def test_verdict_useful_when_p_coll_separates():
    gaps = [
        {
            "return_gap_lateral_minus_forward": 0.1,
            "p_coll_gap_forward_minus_lateral": 0.2,
        }
        for _ in range(8)
    ]
    v = verdict_from_gaps(gaps)
    assert v["useful"] is True
    assert v["label"] == "useful"


def test_verdict_insufficient_when_flat():
    gaps = [
        {
            "return_gap_lateral_minus_forward": 0.0,
            "p_coll_gap_forward_minus_lateral": 0.0,
        }
        for _ in range(8)
    ]
    v = verdict_from_gaps(gaps)
    assert v["useful"] is False
    assert v["label"] == "insufficient"


def test_verdict_rejects_return_gap_without_p_coll():
    gaps = [
        {
            "return_gap_lateral_minus_forward": 9.0,
            "p_coll_gap_forward_minus_lateral": 0.0,
        }
        for _ in range(8)
    ]
    v = verdict_from_gaps(gaps)
    assert v["useful"] is False
    assert v["return_gap_without_p_coll"] is True
