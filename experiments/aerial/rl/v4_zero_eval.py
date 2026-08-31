"""V4-⓪ v2 offline eval (P3) — near-band depth + ⓪f reaction-band diagnostics.

Runs on H100 (torch). Scores deployment ``DepthMinPredictor`` + ``TauPredictor``
against a GT-depth rollout corpus. Authority = RUNBOOK §2.1 / 6ap re-freeze
(⓪h primary @ engage_outer 12.2 m; ⓪d_legacy report-only).

    python -m experiments.aerial.rl.v4_zero_eval \\
        --dataset .../dataset_v0_local_depth_r60_20260814 \\
        --depth-ckpt .../depth_step_2000_da3_ft_head.pt \\
        --tau-ckpt .../tau_foe_calibrator.pt \\
        --emit artifacts/v4_zero_p3_20260820.json

Exits 0 when all scored sub-items PASS; 1 otherwise. ``⓪f`` band ``[lo,hi]`` is
never filled — only clearance-sweep diagnostics for later freeze.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from experiments.aerial.rl.depth_geometry import forward_min_depth, full_min_depth
from experiments.aerial.rl.tau_predictor import (
    DEFAULT_MAX_TAU_S,
    DEFAULT_MIN_CLOSING_M_S,
    closing_speed_m_s,
    make_tau_predictor,
)


# Frozen §4.6.2 thresholds (do not invent).
_NEAR_LO = 0.0
_NEAR_HI = 3.0
_OUTER_LO = 3.0
_OUTER_HI = 8.0
_SUPPORT_MIN = 10_000
_N_FRAMES_MIN = 100
_MAX_FRAME_FRAC = 0.20
_ABSREL_MEDIAN_MAX = 0.30
_ABSREL_P90_MAX = 0.50
_FALSE_TRIGGER_MAX = 0.05
_ENGAGE_MISS_MAX = 0.10  # ⓪h — looser than ⓪d@3m (declare 2026-08-23)
_ENGAGE_MISS_CONSEC_MAX = 4  # fail if >=4 consecutive (⓪d uses <2 ⇒ max 1)
_ENGAGE_OUTER_M = 12.2  # three_zone 8/5/1.5 @ 2/1 (6ap re-freeze 2026-08-24)
_PRIMARY_REFREEZE = "V4_ZERO_PRIMARY_MIGRATION_REFREEZE_20260824"
_TAU_MARGIN_FACTOR = 2.0


@dataclass(frozen=True)
class ZeroThresholds:
    trigger_m: float = 3.0
    min_tau_s: float = 1.0
    center_frac: float = 0.5
    absrel_median_max: float = _ABSREL_MEDIAN_MAX
    absrel_p90_max: float = _ABSREL_P90_MAX
    support_min: int = _SUPPORT_MIN
    n_frames_min: int = _N_FRAMES_MIN
    max_frame_frac: float = _MAX_FRAME_FRAC
    false_trigger_max: float = _FALSE_TRIGGER_MAX
    engage_miss_max: float = _ENGAGE_MISS_MAX
    engage_miss_consec_max: int = _ENGAGE_MISS_CONSEC_MAX


def pixel_absrel_stats(
    pred: np.ndarray,
    gt: np.ndarray,
    *,
    gt_lo: float,
    gt_hi: float,
    max_depth_m: float = 200.0,
) -> Dict[str, Any]:
    """AbsRel on pixels with ``gt_lo < GT <= gt_hi`` (upper inclusive hi)."""
    p = np.asarray(pred, dtype=np.float64).reshape(-1)
    g = np.asarray(gt, dtype=np.float64).reshape(-1)
    m = np.isfinite(p) & np.isfinite(g) & (g > gt_lo) & (g <= gt_hi)
    if max_depth_m is not None:
        m &= g <= float(max_depth_m)
    n = int(np.count_nonzero(m))
    if n == 0:
        return {"n": 0, "median_absrel": float("nan"), "p90_absrel": float("nan")}
    rel = np.abs(p[m] - g[m]) / np.clip(g[m], 1e-6, None)
    return {
        "n": n,
        "median_absrel": round(float(np.median(rel)), 4),
        "p90_absrel": round(float(np.percentile(rel, 90)), 4),
    }


def near_absrel_gt_bins(
    pred: np.ndarray,
    gt: np.ndarray,
    *,
    edges: Sequence[float] = (0.0, 1.5, 3.0),
) -> List[Dict[str, Any]]:
    """AbsRel stats on ``(edges[i], edges[i+1]]`` GT bins (near-band diagnostics)."""
    out: List[Dict[str, Any]] = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        st = pixel_absrel_stats(pred, gt, gt_lo=float(lo), gt_hi=float(hi))
        out.append(
            {
                "gt_lo": float(lo),
                "gt_hi": float(hi),
                "domain": f"({lo:g}, {hi:g}]",
                "n_px": st["n"],
                "median_absrel": st["median_absrel"],
                "p90_absrel": st["p90_absrel"],
            }
        )
    return out


def check_support_b(
    per_frame_near_px: Sequence[int],
    *,
    thr: ZeroThresholds,
) -> Dict[str, Any]:
    total = int(sum(per_frame_near_px))
    n_frames = int(sum(1 for x in per_frame_near_px if x > 0))
    max_frac = (
        float(max(per_frame_near_px) / total) if total > 0 else float("nan")
    )
    ok = (
        total >= thr.support_min
        and n_frames >= thr.n_frames_min
        and (total == 0 or max_frac <= thr.max_frame_frac)
    )
    reason = None
    if total < thr.support_min:
        reason = f"support={total} < {thr.support_min}"
    elif n_frames < thr.n_frames_min:
        reason = f"n_frames_with_near_px={n_frames} < {thr.n_frames_min}"
    elif total > 0 and max_frac > thr.max_frame_frac:
        reason = f"max_frame_frac={max_frac:.3f} > {thr.max_frame_frac}"
    return {
        "ok": bool(ok),
        "support_px": total,
        "n_frames_with_near_px": n_frames,
        "max_frame_frac": round(max_frac, 4) if np.isfinite(max_frac) else None,
        "reason": reason,
    }


def check_0a(stats: Dict[str, Any], *, thr: ZeroThresholds) -> Dict[str, Any]:
    med = stats.get("median_absrel", float("nan"))
    ok = stats.get("n", 0) >= thr.support_min and np.isfinite(med) and med <= thr.absrel_median_max
    return {
        "ok": bool(ok),
        "median_absrel": med,
        "threshold": thr.absrel_median_max,
        "n_px": stats.get("n", 0),
        "domain": f"({ _NEAR_LO:g}, {_NEAR_HI:g}]",
    }


def check_0c(stats: Dict[str, Any], *, thr: ZeroThresholds) -> Dict[str, Any]:
    p90 = stats.get("p90_absrel", float("nan"))
    ok = stats.get("n", 0) >= thr.support_min and np.isfinite(p90) and p90 <= thr.absrel_p90_max
    return {
        "ok": bool(ok),
        "p90_absrel": p90,
        "threshold": thr.absrel_p90_max,
        "n_px": stats.get("n", 0),
        "domain": f"({ _NEAR_LO:g}, {_NEAR_HI:g}]",
    }


def check_0d(
    gt_fwd: np.ndarray,
    dhat_fwd: np.ndarray,
    *,
    thr: ZeroThresholds,
    episode_ids: Optional[np.ndarray] = None,
) -> Dict[str, Any]:
    """Functional miss-trigger rate on forward min (⓪d)."""
    g = np.asarray(gt_fwd, dtype=np.float64)
    d = np.asarray(dhat_fwd, dtype=np.float64)
    m = np.isfinite(g) & np.isfinite(d) & (g <= thr.trigger_m)
    n = int(np.count_nonzero(m))
    if n == 0:
        return {"ok": False, "reason": "no frames with D_gt_fwd <= trigger", "n": 0}
    miss = d[m] > thr.trigger_m
    rate = float(np.mean(miss))
    # Consecutive miss-run check (per episode when ids provided, else global).
    max_run = _max_consecutive_true(miss, episode_ids[m] if episode_ids is not None else None)
    ok = rate <= thr.false_trigger_max and max_run < 2
    return {
        "ok": bool(ok),
        "p_miss_trigger": round(rate, 4),
        "threshold": thr.false_trigger_max,
        "max_consecutive_miss": int(max_run),
        "n_cond": n,
        # Alias — denominator of p_miss_trigger (GT_forward ≤ trigger).
        # Required for rate-leg CI; consec FAIL does not depend on this.
        "n_near_forward_frames": n,
        "trigger_m": thr.trigger_m,
    }


def check_0h(
    gt_fwd: np.ndarray,
    dhat_fwd: np.ndarray,
    *,
    engage_outer_m: float,
    thr: ZeroThresholds,
    episode_ids: Optional[np.ndarray] = None,
) -> Dict[str, Any]:
    """Functional engage-miss on forward min (⓪h) — three-zone deploy primary.

    Condition: ``GT_fwd ≤ engage_outer_m`` (shield should be slowing).
    Miss: ``D̂_fwd > engage_outer_m`` (under-read ⇒ late engage).
    """
    g = np.asarray(gt_fwd, dtype=np.float64)
    d = np.asarray(dhat_fwd, dtype=np.float64)
    trig = float(engage_outer_m)
    m = np.isfinite(g) & np.isfinite(d) & (g <= trig)
    n = int(np.count_nonzero(m))
    if n == 0:
        return {
            "ok": False,
            "reason": "no frames with D_gt_fwd <= engage_outer",
            "n": 0,
            "n_cond": 0,
            "engage_outer_m": trig,
        }
    miss = d[m] > trig
    eids = None
    if episode_ids is not None:
        eids_arr = np.asarray(episode_ids).reshape(-1)
        if eids_arr.size == g.size:
            eids = eids_arr[m]
    rate = float(np.mean(miss))
    max_run = _max_consecutive_true(miss, eids)
    ok = rate <= thr.engage_miss_max and max_run < int(thr.engage_miss_consec_max)
    return {
        "ok": bool(ok),
        "p_engage_miss": round(rate, 4),
        "threshold": thr.engage_miss_max,
        "max_consecutive_miss": int(max_run),
        "n_cond": n,
        "engage_outer_m": trig,
        "label": "0h_engage_miss",
    }


def _max_consecutive_true(flags: np.ndarray, episode_ids: Optional[np.ndarray]) -> int:
    flags = np.asarray(flags, dtype=bool).reshape(-1)
    if episode_ids is None:
        return _max_run_in_segment(flags)
    eids = np.asarray(episode_ids).reshape(-1)
    best = 0
    for e in np.unique(eids):
        best = max(best, _max_run_in_segment(flags[eids == e]))
    return best


def _max_run_in_segment(flags: np.ndarray) -> int:
    best = run = 0
    for f in flags:
        if f:
            run += 1
            best = max(best, run)
        else:
            run = 0
    return best


def temporal_min_per_episode(
    values: np.ndarray,
    episode_ids: np.ndarray,
    *,
    k: int,
) -> np.ndarray:
    """Causal per-episode min over the last ``k`` finite samples (K=1 ⇒ identity).

    Used for D̂ temporal smoothing on ⓪d / ⓪f(3) only. Does not touch pixel AbsRel.
    Window shorter than ``k`` at episode start uses whatever samples exist so far.
    """
    v = np.asarray(values, dtype=np.float64).reshape(-1)
    eids = np.asarray(episode_ids).reshape(-1)
    if v.size != eids.size:
        raise ValueError("temporal_min_per_episode: values/episode_ids length mismatch")
    kk = int(k)
    if kk < 1:
        raise ValueError(f"dhat temporal min K must be >= 1, got {kk}")
    if kk == 1 or v.size == 0:
        return v.copy()
    out = np.empty_like(v)
    for e in np.unique(eids):
        idx = np.flatnonzero(eids == e)
        hist: deque = deque(maxlen=kk)
        for i in idx:
            hist.append(float(v[i]))
            out[i] = float(min(hist))
    return out


def engage_release_hysteresis(
    dhat: np.ndarray,
    episode_ids: np.ndarray,
    *,
    trigger_m: float,
    release_m: float,
) -> np.ndarray:
    """Causal per-episode engage/release on a scalar D̂ channel.

    Engage when ``D̂ ≤ trigger``; stay engaged until ``D̂ ≥ release``.
    ``release`` must be ≥ ``trigger``. Returns bool array (triggered/engaged).
    """
    v = np.asarray(dhat, dtype=np.float64).reshape(-1)
    eids = np.asarray(episode_ids).reshape(-1)
    if v.size != eids.size:
        raise ValueError("engage_release_hysteresis: length mismatch")
    trig = float(trigger_m)
    rel = float(release_m)
    if rel < trig:
        raise ValueError(f"release_m ({rel}) must be >= trigger_m ({trig})")
    out = np.zeros(v.size, dtype=bool)
    if v.size == 0:
        return out
    for e in np.unique(eids):
        idx = np.flatnonzero(eids == e)
        engaged = False
        for i in idx:
            d = float(v[i])
            if not np.isfinite(d):
                out[i] = engaged
                continue
            if engaged:
                if d >= rel:
                    engaged = False
            elif d <= trig:
                engaged = True
            out[i] = engaged
    return out


def check_0d_from_triggered(
    gt_fwd: np.ndarray,
    triggered: np.ndarray,
    *,
    thr: ZeroThresholds,
    episode_ids: Optional[np.ndarray] = None,
) -> Dict[str, Any]:
    """⓪d miss/consec using a boolean trigger decision (e.g. after hysteresis)."""
    g = np.asarray(gt_fwd, dtype=np.float64)
    t = np.asarray(triggered, dtype=bool)
    if g.size != t.size:
        raise ValueError("check_0d_from_triggered: length mismatch")
    m = np.isfinite(g) & (g <= thr.trigger_m)
    n = int(np.count_nonzero(m))
    if n == 0:
        return {"ok": False, "reason": "no frames with D_gt_fwd <= trigger", "n": 0}
    miss = ~t[m]
    rate = float(np.mean(miss))
    max_run = _max_consecutive_true(miss, episode_ids[m] if episode_ids is not None else None)
    ok = rate <= thr.false_trigger_max and max_run < 2
    return {
        "ok": bool(ok),
        "p_miss_trigger": round(rate, 4),
        "threshold": thr.false_trigger_max,
        "max_consecutive_miss": int(max_run),
        "n_cond": n,
        "n_near_forward_frames": n,
        "trigger_m": thr.trigger_m,
    }



def check_tau_miss(
    tau_gt: np.ndarray,
    tau_hat: np.ndarray,
    *,
    min_tau_s: float,
    false_trigger_max: float = _FALSE_TRIGGER_MAX,
    episode_ids: Optional[np.ndarray] = None,
) -> Dict[str, Any]:
    """T-1: τ miss = τ̂ ≥ min_tau while τ_gt ≤ min_tau (leak / late trigger)."""
    g = np.asarray(tau_gt, dtype=np.float64)
    h = np.asarray(tau_hat, dtype=np.float64)
    m = np.isfinite(g) & np.isfinite(h) & (g <= float(min_tau_s))
    n = int(np.count_nonzero(m))
    if n == 0:
        return {
            "ok": False,
            "reason": "no frames with tau_gt <= min_tau_s",
            "n_tau_miss_cond": 0,
            "p_tau_miss": None,
            "max_consecutive_tau_miss": 0,
            "min_tau_s": float(min_tau_s),
        }
    miss = h[m] >= float(min_tau_s)
    rate = float(np.mean(miss))
    max_run = _max_consecutive_true(
        miss, episode_ids[m] if episode_ids is not None else None
    )
    return {
        "ok": bool(rate <= float(false_trigger_max) and max_run < 2),
        "p_tau_miss": round(rate, 4),
        "max_consecutive_tau_miss": int(max_run),
        "n_tau_miss_cond": n,
        "min_tau_s": float(min_tau_s),
        "threshold": float(false_trigger_max),
        "note": "diagnostic (declare T-1); not a signed gate until 5ao/⓪g",
    }


def dhat_tau_miss_crosstab(
    gt_fwd: np.ndarray,
    dhat_fwd: np.ndarray,
    tau_gt: np.ndarray,
    tau_hat: np.ndarray,
    *,
    trigger_m: float,
    min_tau_s: float,
    stratum: Optional[np.ndarray] = None,
) -> Dict[str, Any]:
    """T-2: framewise {D̂ miss} × {τ miss} on frames where both conds hold."""
    g = np.asarray(gt_fwd, dtype=np.float64)
    d = np.asarray(dhat_fwd, dtype=np.float64)
    tg = np.asarray(tau_gt, dtype=np.float64)
    th = np.asarray(tau_hat, dtype=np.float64)
    d_cond = np.isfinite(g) & np.isfinite(d) & (g <= float(trigger_m))
    t_cond = np.isfinite(tg) & np.isfinite(th) & (tg <= float(min_tau_s))
    if stratum is not None:
        s = np.asarray(stratum, dtype=bool).reshape(-1)
        if s.size != g.size:
            raise ValueError("dhat_tau_miss_crosstab: stratum length mismatch")
        d_cond &= s
        t_cond &= s
    both = d_cond & t_cond
    n_both = int(np.count_nonzero(both))
    if n_both == 0:
        return {"n_both_cond": 0, "table": None, "phi": None, "note": "no overlapping cond frames"}
    d_miss = d[both] > float(trigger_m)
    t_miss = th[both] >= float(min_tau_s)
    n11 = int(np.count_nonzero(d_miss & t_miss))
    n10 = int(np.count_nonzero(d_miss & ~t_miss))
    n01 = int(np.count_nonzero(~d_miss & t_miss))
    n00 = int(np.count_nonzero(~d_miss & ~t_miss))
    # Phi coefficient for 2x2
    num = n11 * n00 - n10 * n01
    den = np.sqrt(max((n11 + n10) * (n01 + n00) * (n11 + n01) * (n10 + n00), 1e-12))
    phi = float(num / den)
    return {
        "n_both_cond": n_both,
        "table": {
            "dhat_miss_and_tau_miss": n11,
            "dhat_miss_only": n10,
            "tau_miss_only": n01,
            "neither": n00,
        },
        "phi": round(phi, 4),
        "p_tau_miss_given_dhat_miss": (
            round(n11 / (n11 + n10), 4) if (n11 + n10) > 0 else None
        ),
        "p_dhat_miss_given_tau_miss": (
            round(n11 / (n11 + n01), 4) if (n11 + n01) > 0 else None
        ),
        "note": (
            "high phi / high conditional overlap ⇒ (b) weak (same failure mode); "
            "orthogonal misses ⇒ (b) may add information"
        ),
    }


def tau_by_speed_bins(
    v_fwd: np.ndarray,
    tau_gt: np.ndarray,
    tau_hat: np.ndarray,
    *,
    min_tau_s: float,
    edges: Sequence[float] = (0.0, 0.05, 0.2, 0.5, 1.0, 2.0, 5.0, float("inf")),
) -> List[Dict[str, Any]]:
    """T-4: τ-miss rate stratified by forward closing speed."""
    v = np.asarray(v_fwd, dtype=np.float64)
    tg = np.asarray(tau_gt, dtype=np.float64)
    th = np.asarray(tau_hat, dtype=np.float64)
    rows: List[Dict[str, Any]] = []
    edges = list(edges)
    for i in range(len(edges) - 1):
        lo, hi = float(edges[i]), float(edges[i + 1])
        if np.isfinite(hi):
            in_bin = np.isfinite(v) & (v >= lo) & (v < hi)
        else:
            in_bin = np.isfinite(v) & (v >= lo)
        m = in_bin & np.isfinite(tg) & np.isfinite(th)
        cond = m & (tg <= float(min_tau_s))
        n_cond = int(np.count_nonzero(cond))
        row: Dict[str, Any] = {
            "v_lo": lo,
            "v_hi": None if not np.isfinite(hi) else hi,
            "n_frames": int(np.count_nonzero(m)),
            "n_tau_miss_cond": n_cond,
        }
        if n_cond > 0:
            row["p_tau_miss"] = round(float(np.mean(th[cond] >= float(min_tau_s))), 4)
            row["median_tau_hat"] = round(float(np.median(th[m])), 4)
        rows.append(row)
    return rows


def build_tau_miss_diag(
    gt_fwd: np.ndarray,
    dhat_fwd: np.ndarray,
    tau_hat: np.ndarray,
    v_fwd: np.ndarray,
    episode_ids: np.ndarray,
    *,
    thr: ZeroThresholds,
    min_closing_m_s: float = DEFAULT_MIN_CLOSING_M_S,
    max_tau_s: float = DEFAULT_MAX_TAU_S,
    yaml_min_depth_m: Optional[float] = None,
    center_frac: float = 0.5,
    tau_ckpt: str = "",
    dt_samples: Optional[Sequence[float]] = None,
    dt_fallback_count: int = 0,
    flow_mag: Optional[np.ndarray] = None,
    split: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Assemble T-1..T-4 + B-a/B-b/B-d fields (declare §3/§4/§5)."""
    g = np.asarray(gt_fwd, dtype=np.float64)
    v = np.asarray(v_fwd, dtype=np.float64)
    # Same formula as tau_predictor.gt_tau_from_depth_velocity (declare T-1 / B-d).
    tau_gt = np.full_like(g, np.nan, dtype=np.float64)
    ok = np.isfinite(g) & (g > 0) & np.isfinite(v)
    slow = ok & (v < float(min_closing_m_s))
    fast = ok & ~slow
    tau_gt[slow] = float(max_tau_s)
    tau_gt[fast] = np.minimum(g[fast] / np.maximum(v[fast], 1e-6), float(max_tau_s))

    t1 = check_tau_miss(
        tau_gt,
        tau_hat,
        min_tau_s=thr.min_tau_s,
        false_trigger_max=thr.false_trigger_max,
        episode_ids=episode_ids,
    )
    t2 = dhat_tau_miss_crosstab(
        g, dhat_fwd, tau_gt, tau_hat, trigger_m=thr.trigger_m, min_tau_s=thr.min_tau_s
    )
    t4 = tau_by_speed_bins(v, tau_gt, tau_hat, min_tau_s=thr.min_tau_s)

    t3: Dict[str, Any]
    if flow_mag is None:
        t3 = {
            "ok": False,
            "reason": "flow_mag not collected this run",
            "note": "T-3 deferred unless --emit-tau-miss-diag collects Farneback mag",
        }
    else:
        fm = np.asarray(flow_mag, dtype=np.float64)
        near_wall = np.isfinite(g) & (g >= 3.0) & (g < 3.5)
        rows = []
        if np.any(near_wall & np.isfinite(fm)):
            qs = np.nanpercentile(fm[near_wall & np.isfinite(fm)], [0, 33, 66, 100])
            edges = [float(qs[0]), float(qs[1]), float(qs[2]), float(qs[3]) + 1e-6]
            for i in range(3):
                m = near_wall & np.isfinite(fm) & (fm >= edges[i]) & (fm < edges[i + 1])
                cond = m & np.isfinite(tau_gt) & (tau_gt <= thr.min_tau_s)
                n_cond = int(np.count_nonzero(cond))
                row = {
                    "flow_lo": edges[i],
                    "flow_hi": edges[i + 1],
                    "n_near_wall_3_3_5": int(np.count_nonzero(m)),
                    "n_tau_miss_cond": n_cond,
                }
                if n_cond > 0:
                    row["p_tau_miss"] = round(
                        float(np.mean(np.asarray(tau_hat)[cond] >= thr.min_tau_s)), 4
                    )
                flow_bin = m
                t2_slice = dhat_tau_miss_crosstab(
                    g,
                    dhat_fwd,
                    tau_gt,
                    tau_hat,
                    trigger_m=thr.trigger_m,
                    min_tau_s=thr.min_tau_s,
                    stratum=flow_bin,
                )
                if int(t2_slice.get("n_both_cond") or 0) > 0:
                    row["T2_slice"] = t2_slice
                rows.append(row)
        t3 = {"near_wall_flow_strata": rows, "note": "T-3 low-texture proxy via |flow| tertiles"}

    dts = list(dt_samples or [])
    return {
        "declare_id": "V4_TAU_TRIGGER_MIGRATION_DECLARE_20260821",
        "authoritative": False,
        "note": "T-1..T-4 diagnostic only; 5ao unsigned ⇒ D̂ OR leg untouched",
        "p_tau_miss": t1.get("p_tau_miss"),
        "max_consecutive_tau_miss": t1.get("max_consecutive_tau_miss"),
        "n_tau_miss_cond": t1.get("n_tau_miss_cond"),
        "T1_tau_miss": t1,
        "T2_dhat_tau_crosstab": t2,
        "T3_low_texture": t3,
        "T4_tau_by_speed": t4,
        "tau_by_speed": t4,
        "B_a_dt": {
            "n_samples": len(dts),
            "median_dt_s": round(float(np.median(dts)), 4) if dts else None,
            "dt_hist": {
                "p10": round(float(np.percentile(dts, 10)), 4) if dts else None,
                "p50": round(float(np.percentile(dts, 50)), 4) if dts else None,
                "p90": round(float(np.percentile(dts, 90)), 4) if dts else None,
            },
            "dt_fallback_used": bool(dt_fallback_count > 0),
            "dt_fallback_count": int(dt_fallback_count),
            "blocking_if_fallback": True,
        },
        "dt_hist": {
            "p10": round(float(np.percentile(dts, 10)), 4) if dts else None,
            "p50": round(float(np.percentile(dts, 50)), 4) if dts else None,
            "p90": round(float(np.percentile(dts, 90)), 4) if dts else None,
        },
        "dt_fallback_used": bool(dt_fallback_count > 0),
        "B_b_min_depth": {
            "yaml_min_depth_m": yaml_min_depth_m,
            "min_depth_m_effective": thr.trigger_m,
            "gate_trigger_m_effective": thr.trigger_m,
            "note": "three-way inconsistency: yaml vs safety default vs gate — record both",
        },
        "min_depth_m_effective": thr.trigger_m,
        "B_d_geometry": {
            "center_frac": float(center_frac),
            "tau_gt_formula": "gt_fwd / max(v_fwd, min_closing) clipped to max_tau_s",
            "min_closing_m_s": float(min_closing_m_s),
            "max_tau_s": float(max_tau_s),
        },
        "center_frac": float(center_frac),
        "tau_ckpt": str(tau_ckpt),
        "split": split,
    }


def clearance_sweep(
    gt_fov: np.ndarray,
    dhat_fov: np.ndarray,
    gt_fwd: np.ndarray,
    tau_hat: np.ndarray,
    v_fwd: np.ndarray,
    *,
    thr: ZeroThresholds,
    bin_width: float = 0.25,
) -> List[Dict[str, Any]]:
    """Per-clearance-bin false-trigger diagnostics for ⓪f (no ``[lo,hi]`` commit).

    All input arrays must be aligned per-frame (same length).
    """
    gt_fov = np.asarray(gt_fov, dtype=np.float64)
    dhat_fov = np.asarray(dhat_fov, dtype=np.float64)
    gt_fwd = np.asarray(gt_fwd, dtype=np.float64)
    tau_hat = np.asarray(tau_hat, dtype=np.float64)
    v_fwd = np.asarray(v_fwd, dtype=np.float64)
    n = gt_fov.size
    if not (dhat_fov.size == gt_fwd.size == tau_hat.size == v_fwd.size == n):
        raise ValueError("clearance_sweep inputs must have equal length")

    rows: List[Dict[str, Any]] = []
    c = _OUTER_LO
    while c < _OUTER_HI:
        hi = min(c + bin_width, _OUTER_HI)
        m = np.isfinite(gt_fov) & (gt_fov >= c) & (gt_fov < hi)
        n_bin = int(np.count_nonzero(m))
        row: Dict[str, Any] = {"clearance_lo": round(c, 3), "clearance_hi": round(hi, 3), "n": n_bin}
        if n_bin > 0:
            row["p_dhat_false_trigger"] = round(
                float(np.mean(dhat_fov[m] < thr.trigger_m)), 4
            )
            margin = gt_fwd / np.clip(v_fwd, 1e-6, None)
            need = _TAU_MARGIN_FACTOR * thr.min_tau_s
            tau_m = (
                m
                & np.isfinite(tau_hat)
                & np.isfinite(gt_fwd)
                & np.isfinite(v_fwd)
                & (v_fwd >= 0.05)
                & (margin >= need)
            )
            if np.any(tau_m):
                row["p_tau_false_trigger"] = round(
                    float(np.mean(tau_hat[tau_m] < thr.min_tau_s)), 4
                )
                row["n_tau_cond"] = int(np.count_nonzero(tau_m))
        rows.append(row)
        c = hi
    return rows


def suggest_delta(rows: Sequence[Dict[str, Any]], *, thr: ZeroThresholds) -> Dict[str, Any]:
    """Smallest clearance bin edge where both channels meet ``<= false_trigger_max``."""
    for row in rows:
        if row.get("n", 0) <= 0:
            continue
        pd = row.get("p_dhat_false_trigger")
        pt = row.get("p_tau_false_trigger")
        if pd is None or pt is None:
            continue
        if pd <= thr.false_trigger_max and pt <= thr.false_trigger_max:
            lo = float(row["clearance_lo"])
            return {
                "suggested_lo_clearance_m": lo,
                "suggested_delta_m": round(lo - thr.trigger_m, 3),
                "note": "diagnostic only — [lo,hi] not frozen in P3",
            }
    return {
        "suggested_lo_clearance_m": None,
        "suggested_delta_m": None,
        "note": "no bin satisfied both false-trigger rates",
    }


def aggregate_verdict(sub: Dict[str, Any]) -> Dict[str, Any]:
    """Primary merge = ⓪a–⓪e with **⓪h** (6ap 2026-08-24). ⓪d_legacy is report-only.

    ⓪f is report/diag until ``[lo,hi]`` is frozen. Outer AbsRel (⓪f(1)(2)) is
    **report-only** — §4.6.2 does not give it the ⓪a/⓪c thresholds ``0.30`` /
    ``0.50``. False-trigger bins (3)(4) gate only after a band is frozen.
    """
    keys_primary = ("0a", "0b", "0c", "0h", "0e")
    ok_primary = all(sub[k].get("ok") for k in keys_primary if k in sub)
    f = sub.get("0f", {})
    ok_f = bool(f.get("ok", False))
    leg = sub.get("0d_legacy", {})
    return {
        "ok": bool(ok_primary),
        "ok_primary": ok_primary,
        "ok_0f": ok_f,
        "ok_0d_legacy": bool(leg.get("ok", False)) if leg else None,
        "primary_refreeze": _PRIMARY_REFREEZE,
        "sub": {k: sub[k].get("ok") for k in sorted(sub)},
    }


def _heldout_episodes(
    episodes: List[Any],
    frac: float,
    *,
    seed: int = 0,
    expect_split: Optional[Dict[str, Any]] = None,
    dataset_dir: Optional[Path] = None,
) -> Tuple[List[Any], Dict[str, Any]]:
    """Seeded holdout — MUST match ``train_depth_head`` (holdout_split / §3 #19).

    ``frac<=0`` scores all episodes (honest max slice for a head that never
    trained on this corpus — e.g. control-arm old head).
    """
    from experiments.aerial.rl.holdout_split import (
        apply_indices,
        assert_same_holdout,
        split_holdout_indices,
        summarize_merge_sources,
    )

    _train_idx, hold_idx, meta = split_holdout_indices(
        len(episodes), frac=float(frac), seed=int(seed)
    )
    if expect_split is not None:
        assert_same_holdout(
            meta, expect_split, label_a="eval", label_b="expect_holdout_split"
        )
        print("[v4-zero] holdout indices MATCH expect-holdout-split ✓")
    if dataset_dir is not None and meta.get("holdout_indices"):
        meta["merge_sources"] = summarize_merge_sources(
            dataset_dir, meta["holdout_indices"]
        )
    if meta["regime"] == "all_episodes":
        scored = list(episodes)
    else:
        scored = apply_indices(episodes, hold_idx)
    meta = {
        **meta,
        "n_scored": len(scored),
        "n_train_prefix": meta.get("n_train"),  # compat key name
    }
    return scored, meta


def run_eval(
    dataset: Path,
    depth_ckpt: Path,
    tau_ckpt: Path,
    device: str,
    config: Dict[str, Any],
    max_episodes: int = 0,
    emit: Optional[Path] = None,
    heldout_frac: float = 0.0,
    split_seed: int = 0,
    expect_holdout_split: Optional[Path] = None,
    dhat_temporal_min: int = 1,
    scan_dhat_temporal_min: Optional[Sequence[int]] = None,
    scan_trigger_hysteresis_delta: Optional[Sequence[float]] = None,
    emit_tau_miss_diag: bool = False,
    yaml_min_depth_m: Optional[float] = None,
) -> Dict[str, Any]:
    import torch

    from experiments.aerial.rl import dataset as ds
    from experiments.aerial.rl.depth_predictor import DepthMinPredictor

    safety = config.get("safety", {}) or {}
    tau_cfg = config.get("tau_predictor", {}) or {}
    thr = ZeroThresholds(
        trigger_m=float(safety.get("min_depth_m", 3.0)),
        min_tau_s=float(safety.get("min_tau_s", 1.0)),
        center_frac=float(tau_cfg.get("center_frac", 0.5)),
    )
    if yaml_min_depth_m is None and "yaml_min_depth_m" in config:
        raw = config.get("yaml_min_depth_m")
        yaml_min_depth_m = float(raw) if raw is not None else None

    scan_ks: List[int] = []
    if scan_dhat_temporal_min:
        scan_ks = sorted({int(x) for x in scan_dhat_temporal_min})
        if any(k < 1 for k in scan_ks):
            raise ValueError(f"scan K must be >= 1, got {scan_ks}")
    k_single = int(dhat_temporal_min)
    if k_single < 1:
        raise ValueError(f"dhat_temporal_min must be >= 1, got {k_single}")
    if scan_ks and k_single != 1:
        print(
            f"[v4-zero] WARN: --scan-dhat-temporal-min set; ignoring "
            f"--dhat-temporal-min={k_single} for primary path (scan owns K)"
        )

    scan_deltas: List[float] = []
    if scan_trigger_hysteresis_delta:
        scan_deltas = sorted({float(x) for x in scan_trigger_hysteresis_delta})
        if any(d < 0 for d in scan_deltas):
            raise ValueError(f"hysteresis delta must be >= 0, got {scan_deltas}")
    if scan_ks and scan_deltas:
        raise ValueError(
            "refusing both --scan-dhat-temporal-min and --scan-trigger-hysteresis-delta"
        )

    pred = DepthMinPredictor.from_checkpoint(depth_ckpt, device=device)
    n_frames = int(pred.n_frames)
    tau_pred = make_tau_predictor(
        kind=str(tau_cfg.get("kind", "foe_calibrated")),
        ckpt=tau_ckpt,
        device=device,
        center_frac=thr.center_frac,
        min_closing_m_s=float(tau_cfg.get("min_closing_m_s", 0.05)),
        max_tau_s=float(tau_cfg.get("max_tau_s", 60.0)),
        dt_s=float(tau_cfg.get("dt_s", 0.1)),
        use_gt_depth=False,
    )

    episodes = ds.load_dataset(dataset, skip_quarantined=True)
    if max_episodes > 0:
        episodes = episodes[: int(max_episodes)]
    expect_meta = None
    if expect_holdout_split is not None:
        expect_meta = json.loads(Path(expect_holdout_split).expanduser().read_text())
    episodes, split_meta = _heldout_episodes(
        episodes,
        float(heldout_frac),
        seed=int(split_seed),
        expect_split=expect_meta,
        dataset_dir=Path(dataset),
    )
    if split_meta["regime"] == "seeded_holdout":
        print(
            f"[v4-zero] held-out split: score {split_meta['n_scored']}/"
            f"{split_meta['n_total']} (seeded seed={split_meta.get('split_seed')}); "
            f"train {split_meta.get('n_train')} excluded; "
            f"indices={split_meta.get('holdout_indices')}"
        )
        ms = split_meta.get("merge_sources") or {}
        if ms.get("available"):
            print(
                f"[v4-zero] holdout by_src={ms.get('holdout_by_src')} "
                f"by_layer={ms.get('holdout_by_layer')}"
            )
    elif float(heldout_frac) <= 0.0:
        print(
            "[v4-zero] --heldout-frac=0 → scoring ALL episodes "
            "(honest max slice if depth head never trained on this corpus; "
            "in-sample if it did — declare which)"
        )
    if scan_deltas:
        print(
            f"[v4-zero] trigger hysteresis SCAN delta={scan_deltas} "
            f"(release=trigger+delta; one forward pass; offline only)"
        )
    elif scan_ks:
        print(f"[v4-zero] D̂ temporal-min SCAN K={scan_ks} (one forward pass)")
    elif k_single != 1:
        print(
            f"[v4-zero] D̂ temporal-min K={k_single} "
            "(⓪d + ⓪f(3) only; diagnostic unless declared for gate)"
        )
    if emit_tau_miss_diag:
        print(
            "[v4-zero] τ-miss diag ON (T-1..T-4; authoritative=false; "
            "D̂ OR leg untouched; 5ao unsigned)"
        )

    near_pred: List[float] = []
    near_gt: List[float] = []
    outer_pred: List[float] = []
    outer_gt: List[float] = []
    per_frame_near_px: List[int] = []

    gt_fwd_list: List[float] = []
    dhat_fwd_list: List[float] = []
    ep_ids: List[int] = []
    per_frame_outer_px: List[int] = []
    fov_gt: List[float] = []
    fov_dhat: List[float] = []
    fov_gt_fwd: List[float] = []
    fov_dhat_fwd: List[float] = []
    fov_tau: List[float] = []
    fov_vfwd: List[float] = []
    fov_ep_ids: List[int] = []
    fov_flow_mag: List[float] = []

    dt_fallback_count = 0
    dt_samples: List[float] = []
    n_no_depth = 0
    n_frames_total = 0

    for ep_i, ep in enumerate(episodes):
        hist: deque = deque(maxlen=n_frames)
        tau_pred.reset()
        for t in ep:
            rgb = np.asarray(t.obs.rgb, dtype=np.uint8)
            hist.append(rgb)
            depth_gt = getattr(t.obs, "depth", None)
            if depth_gt is None:
                n_no_depth += 1
                continue
            frames = list(hist)
            while len(frames) < n_frames:
                frames.insert(0, frames[0])
            stack = np.stack(frames[-n_frames:], axis=0)
            tensor = torch.from_numpy(stack).unsqueeze(0)
            with torch.no_grad():
                dmap_t, _ = pred._model.predict_from_window(tensor.to(device))  # noqa: SLF001
            dmap = np.squeeze(dmap_t.squeeze(0).detach().float().cpu().numpy())

            gmap = np.asarray(depth_gt, dtype=np.float64)
            near_m = (
                np.isfinite(gmap)
                & (gmap > _NEAR_LO)
                & (gmap <= _NEAR_HI)
                & (gmap <= 200.0)
            )
            outer_m = (
                np.isfinite(gmap)
                & (gmap > _OUTER_LO)
                & (gmap <= _OUTER_HI)
                & (gmap <= 200.0)
            )
            if np.any(near_m):
                near_pred.extend(dmap.reshape(-1)[near_m.reshape(-1)].tolist())
                near_gt.extend(gmap.reshape(-1)[near_m.reshape(-1)].tolist())
                per_frame_near_px.append(int(np.count_nonzero(near_m)))
            else:
                per_frame_near_px.append(0)
            if np.any(outer_m):
                outer_pred.extend(dmap.reshape(-1)[outer_m.reshape(-1)].tolist())
                outer_gt.extend(gmap.reshape(-1)[outer_m.reshape(-1)].tolist())
                per_frame_outer_px.append(int(np.count_nonzero(outer_m)))
            else:
                per_frame_outer_px.append(0)

            g_fov = full_min_depth(gmap)
            d_fov = full_min_depth(dmap)
            g_fwd = forward_min_depth(gmap, center_frac=thr.center_frac)
            d_fwd = forward_min_depth(dmap, center_frac=thr.center_frac)

            obs = t.obs
            prev_t = tau_pred._prev_t  # noqa: SLF001
            tau_v = tau_pred.predict_tau(obs)
            obs_t = float(obs.t)
            if prev_t is not None and np.isfinite(obs_t) and np.isfinite(prev_t) and obs_t > prev_t:
                dt_samples.append(float(obs_t - prev_t))
            elif prev_t is not None:
                dt_fallback_count += 1

            if np.isfinite(g_fwd) and np.isfinite(d_fwd):
                gt_fwd_list.append(g_fwd)
                dhat_fwd_list.append(d_fwd)
                ep_ids.append(ep_i)
            if (
                np.isfinite(g_fov)
                and np.isfinite(d_fov)
                and tau_v is not None
                and np.isfinite(g_fwd)
            ):
                fov_gt.append(g_fov)
                fov_dhat.append(d_fov)
                fov_gt_fwd.append(g_fwd)
                fov_dhat_fwd.append(d_fwd)
                fov_tau.append(float(tau_v))
                fov_vfwd.append(closing_speed_m_s(obs))
                fov_ep_ids.append(ep_i)
                if emit_tau_miss_diag:
                    fmag = getattr(tau_pred, "_last_flow_mag", None)
                    fov_flow_mag.append(
                        float(fmag)
                        if fmag is not None and np.isfinite(fmag)
                        else float("nan")
                    )
            n_frames_total += 1

    near_stats = pixel_absrel_stats(
        np.asarray(near_pred), np.asarray(near_gt), gt_lo=_NEAR_LO, gt_hi=_NEAR_HI
    )
    near_gt_bins = near_absrel_gt_bins(
        np.asarray(near_pred), np.asarray(near_gt), edges=(0.0, 1.5, 3.0)
    )
    outer_stats = pixel_absrel_stats(
        np.asarray(outer_pred), np.asarray(outer_gt), gt_lo=_OUTER_LO, gt_hi=_OUTER_HI
    )
    sup_b = check_support_b(per_frame_near_px, thr=thr)
    sub_0a = check_0a(near_stats, thr=thr)
    sub_0b = {**sup_b, "label": "0b", "near_px_total": sup_b["support_px"]}
    sub_0c = {
        **check_0c(near_stats, thr=thr),
        "gt_bins": near_gt_bins,
        "note": "gt_bins: AbsRel on (0,1.5] vs (1.5,3.0]; not a PASS criterion — attribution only",
    }
    sub_0e = {
        "ok": True,
        "distribution": "deployment_rollout_corpus",
        "dataset": str(dataset),
        "note": "⓪e: not WM train holdout; rollout frames with GT depth",
    }
    outer_sup = check_support_b(per_frame_outer_px, thr=thr)

    gt_fwd_arr = np.asarray(gt_fwd_list, dtype=np.float64)
    dhat_fwd_raw = np.asarray(dhat_fwd_list, dtype=np.float64)
    ep_ids_arr = np.asarray(ep_ids, dtype=np.int64)
    fov_gt_arr = np.asarray(fov_gt, dtype=np.float64)
    fov_dhat_raw = np.asarray(fov_dhat, dtype=np.float64)
    fov_gt_fwd_arr = np.asarray(fov_gt_fwd, dtype=np.float64)
    fov_dhat_fwd_arr = np.asarray(fov_dhat_fwd, dtype=np.float64)
    fov_tau_arr = np.asarray(fov_tau, dtype=np.float64)
    fov_vfwd_arr = np.asarray(fov_vfwd, dtype=np.float64)
    fov_ep_arr = np.asarray(fov_ep_ids, dtype=np.int64)

    def _score_dhat_k(k: int) -> Dict[str, Any]:
        d_fwd = temporal_min_per_episode(dhat_fwd_raw, ep_ids_arr, k=k)
        d_fov = temporal_min_per_episode(fov_dhat_raw, fov_ep_arr, k=k)
        sub_0d = check_0d(gt_fwd_arr, d_fwd, thr=thr, episode_ids=ep_ids_arr)
        sweep = clearance_sweep(
            fov_gt_arr, d_fov, fov_gt_fwd_arr, fov_tau_arr, fov_vfwd_arr, thr=thr
        )
        delta_hint = suggest_delta(sweep, thr=thr)
        wall = [
            r
            for r in sweep
            if r.get("n", 0) > 0
            and float(r["clearance_lo"]) >= 3.0
            and float(r["clearance_hi"]) <= 5.0
        ]
        n_wall = int(sum(int(r["n"]) for r in wall))
        if n_wall > 0:
            p_wall = sum(
                float(r["p_dhat_false_trigger"]) * int(r["n"]) for r in wall
            ) / n_wall
        else:
            p_wall = float("nan")
        return {
            "k": k,
            "0d": sub_0d,
            "0f": {
                "ok": bool(outer_sup["ok"]),
                "domain": f"({_OUTER_LO:g}, {_OUTER_HI:g}]",
                "median_absrel": outer_stats["median_absrel"],
                "p90_absrel": outer_stats["p90_absrel"],
                "n_px": outer_stats["n"],
                "support": outer_sup,
                "clearance_sweep": sweep,
                "delta_hint": delta_hint,
                "band_lo_hi": None,
                "p_dhat_false_trigger_3_to_5m": (
                    round(float(p_wall), 4) if np.isfinite(p_wall) else None
                ),
                "n_frames_3_to_5m": n_wall,
                "note": (
                    "⓪f(1)(2) AbsRel unchanged by temporal-min (pixel maps raw); "
                    "(3)(4) use temporally-min'd D̂_fov; [lo,hi] null pre-freeze"
                ),
            },
        }

    def _score_hyst_delta(delta: float) -> Dict[str, Any]:
        release = float(thr.trigger_m) + float(delta)
        trig_fwd = engage_release_hysteresis(
            dhat_fwd_raw, ep_ids_arr, trigger_m=thr.trigger_m, release_m=release
        )
        trig_fov = engage_release_hysteresis(
            fov_dhat_raw, fov_ep_arr, trigger_m=thr.trigger_m, release_m=release
        )
        sub_0d = check_0d_from_triggered(
            gt_fwd_arr, trig_fwd, thr=thr, episode_ids=ep_ids_arr
        )
        # Map triggered → synthetic D̂ for reuse of clearance_sweep FT formula.
        d_fov_syn = np.where(
            trig_fov, thr.trigger_m - 1e-3, thr.trigger_m + 1e-3
        ).astype(np.float64)
        sweep = clearance_sweep(
            fov_gt_arr, d_fov_syn, fov_gt_fwd_arr, fov_tau_arr, fov_vfwd_arr, thr=thr
        )
        delta_hint = suggest_delta(sweep, thr=thr)
        wall = [
            r
            for r in sweep
            if r.get("n", 0) > 0
            and float(r["clearance_lo"]) >= 3.0
            and float(r["clearance_hi"]) <= 5.0
        ]
        n_wall = int(sum(int(r["n"]) for r in wall))
        if n_wall > 0:
            p_wall = sum(
                float(r["p_dhat_false_trigger"]) * int(r["n"]) for r in wall
            ) / n_wall
        else:
            p_wall = float("nan")
        return {
            "delta_m": float(delta),
            "release_m": release,
            "0d": sub_0d,
            "0f": {
                "ok": bool(outer_sup["ok"]),
                "domain": f"({_OUTER_LO:g}, {_OUTER_HI:g}]",
                "median_absrel": outer_stats["median_absrel"],
                "p90_absrel": outer_stats["p90_absrel"],
                "n_px": outer_stats["n"],
                "support": outer_sup,
                "clearance_sweep": sweep,
                "delta_hint": delta_hint,
                "band_lo_hi": None,
                "p_dhat_false_trigger_3_to_5m": (
                    round(float(p_wall), 4) if np.isfinite(p_wall) else None
                ),
                "n_frames_3_to_5m": n_wall,
                "note": (
                    "⓪f(3) uses engage/release triggered(D̂_fov); "
                    "AbsRel (1)(2) still raw pixels; offline diagnostic only"
                ),
            },
        }

    if scan_deltas:
        rows = [_score_hyst_delta(d) for d in scan_deltas]
        base = next(r for r in rows if r["delta_m"] == 0.0) if 0.0 in scan_deltas else rows[0]
        sub_0d = base["0d"]
        sub_0f = base["0f"]
        curves = {
            "consec": [
                {
                    "delta_m": r["delta_m"],
                    "max_consecutive_miss": r["0d"]["max_consecutive_miss"],
                }
                for r in rows
            ],
            "rate": [
                {
                    "delta_m": r["delta_m"],
                    "p_miss_trigger": r["0d"]["p_miss_trigger"],
                    "n_near_forward_frames": r["0d"]["n_near_forward_frames"],
                }
                for r in rows
            ],
            "0f3": [
                {
                    "delta_m": r["delta_m"],
                    "release_m": r["release_m"],
                    "suggested_lo_clearance_m": (r["0f"].get("delta_hint") or {}).get(
                        "suggested_lo_clearance_m"
                    ),
                    "p_dhat_false_trigger_3_to_5m": r["0f"].get(
                        "p_dhat_false_trigger_3_to_5m"
                    ),
                    "n_frames_3_to_5m": r["0f"].get("n_frames_3_to_5m"),
                }
                for r in rows
            ],
        }
        scan_payload = {
            "declare_id": "V4_HYSTERESIS_SCAN_20260821",
            "note": "diagnostic Phase C only — not a gate freeze; see declare doc",
            "deltas_m": scan_deltas,
            "trigger_m": thr.trigger_m,
            "rows": rows,
            "curves": curves,
        }
    elif scan_ks:
        rows = [_score_dhat_k(k) for k in scan_ks]
        base = next(r for r in rows if r["k"] == 1) if 1 in scan_ks else rows[0]
        sub_0d = base["0d"]
        sub_0f = base["0f"]
        curves = {
            "consec": [
                {"k": r["k"], "max_consecutive_miss": r["0d"]["max_consecutive_miss"]}
                for r in rows
            ],
            "rate": [
                {
                    "k": r["k"],
                    "p_miss_trigger": r["0d"]["p_miss_trigger"],
                    "n_near_forward_frames": r["0d"]["n_near_forward_frames"],
                }
                for r in rows
            ],
            "0f3": [
                {
                    "k": r["k"],
                    "suggested_lo_clearance_m": (r["0f"].get("delta_hint") or {}).get(
                        "suggested_lo_clearance_m"
                    ),
                    "p_dhat_false_trigger_3_to_5m": r["0f"].get(
                        "p_dhat_false_trigger_3_to_5m"
                    ),
                    "n_frames_3_to_5m": r["0f"].get("n_frames_3_to_5m"),
                }
                for r in rows
            ],
        }
        scan_payload = {
            "declare_id": "V4_DHAT_TEMPORAL_MIN_SCAN_20260821",
            "note": "diagnostic only — not a gate freeze; see declare doc",
            "ks": scan_ks,
            "rows": rows,
            "curves": curves,
        }
    else:
        scored = _score_dhat_k(k_single)
        sub_0d = scored["0d"]
        sub_0f = scored["0f"]
        scan_payload = None
        curves = None

    d_fwd_scored = temporal_min_per_episode(dhat_fwd_raw, ep_ids_arr, k=k_single)
    sub_0h = check_0h(
        gt_fwd_arr,
        d_fwd_scored,
        engage_outer_m=_ENGAGE_OUTER_M,
        thr=thr,
        episode_ids=ep_ids_arr,
    )
    sub_0d_legacy = {**sub_0d, "label": "0d_legacy", "note": "report-only; not merge primary (6ap)"}

    sub = {
        "0a": sub_0a,
        "0b": sub_0b,
        "0c": sub_0c,
        "0h": sub_0h,
        "0d_legacy": sub_0d_legacy,
        "0e": sub_0e,
        "0f": sub_0f,
    }
    verdict = aggregate_verdict(sub)

    payload: Dict[str, Any] = {
        "step": "P3",
        "signal": "V4-⓪-v2",
        "primary_refreeze": _PRIMARY_REFREEZE,
        "dataset": str(dataset),
        "depth_ckpt": str(depth_ckpt),
        "tau_ckpt": str(tau_ckpt),
        "device": device,
        "dhat_temporal_min": (1 if scan_ks else k_single),
        "thresholds": {
            "trigger_m": thr.trigger_m,
            "engage_outer_m": _ENGAGE_OUTER_M,
            "min_tau_s": thr.min_tau_s,
            "center_frac": thr.center_frac,
            "engage_miss_max": thr.engage_miss_max,
            "engage_miss_consec_max": thr.engage_miss_consec_max,
        },
        "split": split_meta,
        "episodes": len(episodes),
        "frames_scored": n_frames_total,
        "n_no_depth_frames": n_no_depth,
        "near_pixel_stats": {**near_stats, "gt_bins": near_gt_bins},
        "outer_pixel_stats": outer_stats,
        "tau_dt": {
            "n_samples": len(dt_samples),
            "median_dt_s": round(float(np.median(dt_samples)), 4) if dt_samples else None,
            "dt_fallback_count": dt_fallback_count,
            "used_default_dt_s": dt_fallback_count > 0,
        },
        "sub": sub,
        "verdict": verdict,
    }
    if scan_payload is not None:
        if scan_payload.get("declare_id") == "V4_HYSTERESIS_SCAN_20260821":
            payload["trigger_hysteresis_scan"] = scan_payload
        else:
            payload["dhat_temporal_min_scan"] = scan_payload
        payload["curves"] = curves

    if emit_tau_miss_diag:
        # Align on fov_* rows (τ̂ available); D̂_fwd uses same center_frac as TauPredictor.
        flow_arr = (
            np.asarray(fov_flow_mag, dtype=np.float64)
            if fov_flow_mag
            else None
        )
        payload["tau_miss_diag"] = build_tau_miss_diag(
            fov_gt_fwd_arr,
            fov_dhat_fwd_arr,
            fov_tau_arr,
            fov_vfwd_arr,
            fov_ep_arr,
            thr=thr,
            min_closing_m_s=float(tau_cfg.get("min_closing_m_s", DEFAULT_MIN_CLOSING_M_S)),
            max_tau_s=float(tau_cfg.get("max_tau_s", DEFAULT_MAX_TAU_S)),
            yaml_min_depth_m=yaml_min_depth_m,
            center_frac=thr.center_frac,
            tau_ckpt=str(tau_ckpt),
            dt_samples=dt_samples,
            dt_fallback_count=dt_fallback_count,
            flow_mag=flow_arr,
            split=split_meta,
        )
        t1 = payload["tau_miss_diag"]["T1_tau_miss"]
        print(
            f"[v4-zero] tau_miss_diag T-1 p={t1.get('p_tau_miss')} "
            f"consec={t1.get('max_consecutive_tau_miss')} "
            f"n={t1.get('n_tau_miss_cond')} "
            f"dt_fallback={dt_fallback_count}"
        )

    if emit:
        emit.parent.mkdir(parents=True, exist_ok=True)
        emit.write_text(json.dumps(payload, indent=2) + "\n")
        print(f"[v4-zero] wrote {emit}")
        if curves is not None:
            print("[v4-zero] curves consec=", curves["consec"])
            print("[v4-zero] curves rate=", curves["rate"])
            print("[v4-zero] curves 0f3=", curves["0f3"])

    _print_summary(payload)
    return payload


def _print_summary(payload: Dict[str, Any]) -> None:
    v = payload["verdict"]
    print(f"[v4-zero] episodes={payload['episodes']} frames={payload['frames_scored']}")
    for k in ("0a", "0b", "0c", "0h", "0d_legacy", "0e", "0f"):
        s = payload["sub"][k]
        mark = "PASS" if s.get("ok") else "FAIL"
        gate = " [primary]" if k in ("0a", "0b", "0c", "0h", "0e") else ""
        print(
            f"  {k}: {mark}{gate}  "
            f"{json.dumps({x: s[x] for x in s if x != 'ok'}, default=str)[:120]}"
        )
    print(f"[v4-zero] merge ok={v['ok']} (primary=⓪a∧⓪b∧⓪c∧⓪h∧⓪e)")


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--depth-ckpt", required=True)
    ap.add_argument("--tau-ckpt", required=True)
    ap.add_argument("--config", default="configs/aerial_rl.yaml")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--max-episodes", type=int, default=0)
    ap.add_argument(
        "--heldout-frac",
        type=float,
        default=0.0,
        help=(
            "score only the seeded holdout fraction (MUST match train_depth_head "
            "--holdout-frac + --split-seed; RUNBOOK §3 #19). 0 = all episodes."
        ),
    )
    ap.add_argument(
        "--split-seed",
        type=int,
        default=0,
        help="seed for holdout permutation (default 0; must match depth train)",
    )
    ap.add_argument(
        "--expect-holdout-split",
        default=None,
        help="path to holdout_split.json from train_depth_head; assert index equality",
    )
    ap.add_argument(
        "--dhat-temporal-min",
        type=int,
        default=1,
        help=(
            "causal K-frame min on D̂_fwd / D̂_fov for ⓪d and ⓪f(3) only "
            "(default 1 = off). Diagnostic unless declared for gate; "
            "train/eval/deploy must share K if promoted."
        ),
    )
    ap.add_argument(
        "--scan-dhat-temporal-min",
        default=None,
        help=(
            "comma-separated K list (e.g. 1,2,3,4,5): one forward pass, re-score "
            "each K; emit curves consec/rate/0f3. See "
            "V4_DHAT_TEMPORAL_MIN_SCAN_DECLARE_20260821.md"
        ),
    )
    ap.add_argument(
        "--scan-trigger-hysteresis-delta",
        default=None,
        help=(
            "comma-separated release margins δ (e.g. 0,0.25,0.5,1,1.5,2): "
            "engage at trigger, release at trigger+δ; one forward pass. "
            "See V4_HYSTERESIS_SCAN_DECLARE_20260821.md (Phase C offline)"
        ),
    )
    ap.add_argument("--emit", default=None)
    ap.add_argument("--trigger-m", type=float, default=None, help="override safety.min_depth_m (default 3.0 for V4 gate)")
    ap.add_argument(
        "--emit-tau-miss-diag",
        action="store_true",
        help=(
            "attach tau_miss_diag (T-1..T-4 + B-a/b/d) to JSON; "
            "diagnostic only (authoritative=false); does not strip D̂ OR leg"
        ),
    )
    args = ap.parse_args(argv)

    import yaml

    cfg_path = Path(args.config)
    cfg = yaml.safe_load(cfg_path.read_text()) or {}
    yaml_min_depth_m = (cfg.get("safety") or {}).get("min_depth_m")
    if args.trigger_m is not None:
        cfg.setdefault("safety", {})["min_depth_m"] = float(args.trigger_m)
    elif float((cfg.get("safety") or {}).get("min_depth_m", 1.5)) < 2.0:
        cfg.setdefault("safety", {})["min_depth_m"] = 3.0

    scan_ks = None
    if args.scan_dhat_temporal_min:
        scan_ks = [
            int(x.strip())
            for x in str(args.scan_dhat_temporal_min).split(",")
            if x.strip()
        ]
    scan_deltas = None
    if args.scan_trigger_hysteresis_delta:
        scan_deltas = [
            float(x.strip())
            for x in str(args.scan_trigger_hysteresis_delta).split(",")
            if x.strip()
        ]

    payload = run_eval(
        dataset=Path(args.dataset).expanduser(),
        depth_ckpt=Path(args.depth_ckpt).expanduser(),
        tau_ckpt=Path(args.tau_ckpt).expanduser(),
        device=str(args.device),
        config=cfg,
        max_episodes=int(args.max_episodes),
        heldout_frac=float(args.heldout_frac),
        split_seed=int(args.split_seed),
        expect_holdout_split=(
            Path(args.expect_holdout_split).expanduser()
            if args.expect_holdout_split
            else None
        ),
        dhat_temporal_min=int(args.dhat_temporal_min),
        scan_dhat_temporal_min=scan_ks,
        scan_trigger_hysteresis_delta=scan_deltas,
        emit_tau_miss_diag=bool(args.emit_tau_miss_diag),
        yaml_min_depth_m=(
            float(yaml_min_depth_m) if yaml_min_depth_m is not None else None
        ),
        emit=Path(args.emit).expanduser() if args.emit else None,
    )
    return 0 if payload["verdict"]["ok"] else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
