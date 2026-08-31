"""V4 two-signal gate metrics (frozen spec §4)."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Mapping, Optional, Sequence

import numpy as np


@dataclass(frozen=True)
class V4GateThresholds:
    """Aligned with frozen spec §4.1 n re-freeze 2026-08-17 (n=8 floor)."""

    progress_delta_p: float = 0.10
    near_coll_rate_ratio_max: float = 0.80
    n_eval_episodes: int = 8


DEFAULT_V4_THRESHOLDS = V4GateThresholds()


def check_progress_vs_heuristic(
    actor_progress_sums: Sequence[float],
    heuristic_progress_sums: Sequence[float],
    *,
    delta_p: float = DEFAULT_V4_THRESHOLDS.progress_delta_p,
) -> Dict[str, Any]:
    """V4-①: actor progress_sum ≥ heuristic × (1 + δ_p) on obstacle-facing starts."""
    ap = np.asarray(actor_progress_sums, dtype=np.float64)
    hp = np.asarray(heuristic_progress_sums, dtype=np.float64)
    if min(ap.size, hp.size) == 0:
        return {"ok": False, "reason": "empty progress arrays"}
    mean_actor = float(np.mean(ap))
    mean_heur = float(np.mean(hp))
    if not np.isfinite(mean_heur) or mean_heur <= 0:
        return {
            "ok": False,
            "reason": "heuristic baseline must be positive",
            "mean_progress_actor": mean_actor,
            "mean_progress_heuristic": mean_heur,
        }
    target = mean_heur * (1.0 + float(delta_p))
    n = int(min(ap.size, hp.size))
    ok = bool(np.isfinite(mean_actor) and mean_actor >= target)
    n_floor = int(DEFAULT_V4_THRESHOLDS.n_eval_episodes)
    authoritative = bool(n >= n_floor)
    return {
        "ok": ok,
        "mean_progress_actor": mean_actor,
        "mean_progress_heuristic": mean_heur,
        "target_min": target,
        "delta_p": float(delta_p),
        "n": n,
        "n_floor": n_floor,
        "authoritative": authoritative,
        **(
            {}
            if authoritative
            else {"reason": f"n={n} < frozen floor {n_floor} (non-authoritative)"}
        ),
    }


def check_safety_no_regression(
    v4_coll_rate: float,
    v1_coll_rate: float,
    *,
    near_coll_rate_ratio: Optional[float] = None,
    ratio_max: float = DEFAULT_V4_THRESHOLDS.near_coll_rate_ratio_max,
) -> Dict[str, Any]:
    """V4-④: hard coll_rate ≤ V1-① baseline; optional V0-④ ratio ≤ 0.80."""
    if not np.isfinite(v4_coll_rate) or not np.isfinite(v1_coll_rate):
        return {"ok": False, "reason": "invalid collision rates"}
    coll_ok = bool(v4_coll_rate <= v1_coll_rate)
    ratio_ok: Optional[bool] = None
    if near_coll_rate_ratio is not None and np.isfinite(near_coll_rate_ratio):
        ratio_ok = bool(near_coll_rate_ratio <= ratio_max)
    ok = coll_ok and (ratio_ok is not False)
    out: Dict[str, Any] = {
        "ok": ok,
        "v4_coll_rate": float(v4_coll_rate),
        "v1_coll_rate": float(v1_coll_rate),
        "coll_ok": coll_ok,
        "authoritative": True,
    }
    if ratio_ok is not None:
        out["near_coll_rate_ratio"] = float(near_coll_rate_ratio)
        out["ratio_max"] = float(ratio_max)
        out["ratio_ok"] = ratio_ok
    if not coll_ok:
        out["reason"] = "v4_coll_rate exceeds v1 baseline"
    elif ratio_ok is False:
        out["reason"] = "near_coll_rate_ratio exceeds cap"
    return out


def aggregate_v4_verdict(results: Mapping[str, Mapping[str, Any]]) -> Dict[str, Any]:
    keys = ("1", "4")
    missing = [k for k in keys if k not in results]
    if missing:
        return {"ok": False, "passed": {}, "reason": f"missing signals {missing}"}
    bad_type = [k for k in keys if not isinstance(results[k].get("ok"), bool)]
    if bad_type:
        return {
            "ok": False,
            "passed": {},
            "details": dict(results),
            "reason": f"signals {bad_type} have a non-bool 'ok'",
        }
    passed = {k: results[k].get("ok") is True for k in keys}
    # Frozen §4.1 n floor (2026-08-17): n<8 on ① → non-authoritative, cannot merge PASS.
    non_auth = [
        k
        for k in keys
        if results[k].get("authoritative") is False
    ]
    overall_ok = all(passed.values()) and not non_auth
    out: Dict[str, Any] = {
        "ok": overall_ok,
        "passed": passed,
        "thresholds": asdict(DEFAULT_V4_THRESHOLDS),
        "details": dict(results),
    }
    if non_auth:
        out["reason"] = f"signals {non_auth} non-authoritative (n below frozen floor)"
        out["non_authoritative"] = non_auth
    return out
