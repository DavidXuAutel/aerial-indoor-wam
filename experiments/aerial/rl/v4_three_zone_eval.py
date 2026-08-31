"""Three-zone speed shield: kinematic feasibility + depth-precision budget (offline).

Runs on 4090/H100 like ``v4_zero_eval`` — one forward pass over a GT-depth corpus,
scores whether the **old-head** ``D̂_fwd`` errors fit the margins implied by an
optimal three-line speed profile.

    python -m experiments.aerial.rl.v4_three_zone_eval \\
        --dataset .../dataset_v0_p45_merged_20260821 \\
        --depth-ckpt .../depth_ckpt_da3_r60_20260814/depth_step_2000_da3_ft_head.pt \\
        --tau-ckpt .../tau_foe_calibrator.pt \\
        --heldout-frac 0.35 --split-seed 0 \\
        --emit artifacts/v4_three_zone_oldhead_hold035_20260822.json

``authoritative=false`` — diagnostic only; does not change frozen gate thresholds.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from experiments.aerial.rl.depth_geometry import forward_min_depth
from experiments.aerial.rl.three_zone import (
    DEFAULT_A_MAX,
    DEFAULT_DELAY_S,
    DEFAULT_L1,
    DEFAULT_L2,
    DEFAULT_L3,
    DEFAULT_V1,
    DEFAULT_V2,
    ThreeZoneSpec,
    kinematic_budget,
    max_engage_delay_m,
    need,
    simulate_three_zone,
)
from experiments.aerial.rl.tau_predictor import closing_speed_m_s, make_tau_predictor
from experiments.aerial.rl.v4_zero_eval import ZeroThresholds, _heldout_episodes, check_0d, check_0h

DEFAULT_CENTER_FRAC = 0.5

# Re-export for tests / callers.
__all__ = [
    "ThreeZoneSpec",
    "need",
    "simulate_three_zone",
    "max_engage_delay_m",
    "kinematic_budget",
    "depth_precision_vs_budget",
    "run_eval",
]


def _band_stats(
    gt: np.ndarray,
    dhat: np.ndarray,
    v: np.ndarray,
    *,
    lo: float,
    hi: float,
    budget_m: float,
) -> Dict[str, Any]:
    m = (
        np.isfinite(gt)
        & np.isfinite(dhat)
        & (gt > lo)
        & (gt <= hi)
    )
    n = int(np.count_nonzero(m))
    if n == 0:
        return {
            "gt_lo": lo,
            "gt_hi": hi,
            "n": 0,
            "budget_m": budget_m,
            "ok": False,
            "reason": "no_support",
        }
    err = dhat[m] - gt[m]  # >0 under-read (late)
    under = err[err > 0]
    p90_under = float(np.percentile(under, 90)) if under.size else 0.0
    p95_under = float(np.percentile(under, 95)) if under.size else 0.0
    frac_late = float(np.mean(err > 0))
    frac_exceed = float(np.mean(err > budget_m)) if budget_m > 0 else float(np.mean(err > 0))
    med_v = float(np.median(v[m])) if v is not None else float("nan")
    return {
        "gt_lo": lo,
        "gt_hi": hi,
        "n": n,
        "budget_m": round(budget_m, 3),
        "median_signed_err_m": round(float(np.median(err)), 4),
        "p90_underread_m": round(p90_under, 4),
        "p95_underread_m": round(p95_under, 4),
        "frac_underread": round(frac_late, 4),
        "frac_exceed_budget": round(frac_exceed, 4),
        "ok": p95_under <= budget_m and frac_exceed <= 0.05,
        "median_v_fwd_m_s": round(med_v, 3),
    }


def depth_precision_vs_budget(
    gt_fwd: np.ndarray,
    dhat_fwd: np.ndarray,
    v_fwd: np.ndarray,
    budget: Dict[str, Any],
    spec: ThreeZoneSpec,
) -> Dict[str, Any]:
    eng = float(budget["engage_outer_m"])
    delay_b = float(budget["max_underread_at_engage_m"])
    half = 0.5
    bands = {
        "engage_outer": (eng - 1.0, eng + 0.5, delay_b),
        "cap_l1": (spec.l1_m - half, spec.l1_m + half, delay_b),
        "cap_l2": (spec.l2_m - half, spec.l2_m + half, float(budget["segment_margin_m"]["l1_to_l2"])),
        "cap_l3": (spec.l3_m - 0.25, spec.l3_m + 0.25, float(budget["segment_margin_m"]["l2_to_l3"])),
    }
    rows = {
        name: _band_stats(gt_fwd, dhat_fwd, v_fwd, lo=lo, hi=hi, budget_m=b)
        for name, (lo, hi, b) in bands.items()
    }
    all_ok = all(r.get("ok") for r in rows.values() if r.get("n", 0) > 0)
    return {"bands": rows, "all_bands_ok": all_ok}


def run_eval(
    *,
    dataset: Path,
    depth_ckpt: Path,
    tau_ckpt: Path,
    device: str,
    config: Dict[str, Any],
    spec: ThreeZoneSpec,
    heldout_frac: float = 0.0,
    split_seed: int = 0,
    max_episodes: int = 0,
    emit: Optional[Path] = None,
) -> Dict[str, Any]:
    import torch

    from experiments.aerial.rl import dataset as ds
    from experiments.aerial.rl.depth_predictor import DepthMinPredictor

    tau_cfg = config.get("tau") or {}
    safety_cfg = config.get("safety") or {}
    zone_cfg = ThreeZoneSpec.from_mapping(safety_cfg)
    thr = ZeroThresholds(
        trigger_m=float(zone_cfg.l3_m),
        center_frac=DEFAULT_CENTER_FRAC,
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
    episodes, split_meta = _heldout_episodes(
        episodes, float(heldout_frac), seed=int(split_seed), dataset_dir=dataset
    )

    gt_fwd_list: List[float] = []
    dhat_fwd_list: List[float] = []
    v_fwd_list: List[float] = []
    ep_id_list: List[int] = []

    for ep_i, ep in enumerate(episodes):
        hist: List[np.ndarray] = []
        tau_pred.reset()
        for t in ep:
            rgb = np.asarray(t.obs.rgb, dtype=np.uint8)
            hist.append(rgb)
            depth_gt = getattr(t.obs, "depth", None)
            if depth_gt is None:
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
            g_fwd = forward_min_depth(gmap, center_frac=thr.center_frac)
            d_fwd = forward_min_depth(dmap, center_frac=thr.center_frac)
            if np.isfinite(g_fwd) and np.isfinite(d_fwd):
                gt_fwd_list.append(float(g_fwd))
                dhat_fwd_list.append(float(d_fwd))
                v_fwd_list.append(float(closing_speed_m_s(t.obs)))
                ep_id_list.append(int(ep_i))

    gt_arr = np.asarray(gt_fwd_list, dtype=np.float64)
    dhat_arr = np.asarray(dhat_fwd_list, dtype=np.float64)
    v_arr = np.asarray(v_fwd_list, dtype=np.float64)
    ep_ids_arr = np.asarray(ep_id_list, dtype=np.int64)

    kin = kinematic_budget(spec)
    depth = depth_precision_vs_budget(gt_arr, dhat_arr, v_arr, kin, spec)
    sub_0h = check_0h(
        gt_arr,
        dhat_arr,
        engage_outer_m=float(kin["engage_outer_m"]),
        thr=thr,
        episode_ids=ep_ids_arr,
    )
    sub_0d_legacy = check_0d(gt_arr, dhat_arr, thr=thr, episode_ids=ep_ids_arr)

    payload: Dict[str, Any] = {
        "authoritative": False,
        "label": "three_zone_kinematic_depth_budget",
        "dataset": str(dataset),
        "depth_ckpt": str(depth_ckpt),
        "split": split_meta,
        "kinematic": kin,
        "depth_vs_budget": depth,
        "0h_engage_miss": sub_0h,
        "0d_legacy": sub_0d_legacy,
        "verdict": {
            "kinematic_feasible": kin["feasible_nominal"],
            "depth_meets_budget": depth["all_bands_ok"],
            "engage_miss_ok": sub_0h.get("ok", False),
            "ok": kin["feasible_nominal"] and depth["all_bands_ok"] and sub_0h.get("ok", False),
        },
    }
    if emit is not None:
        emit.parent.mkdir(parents=True, exist_ok=True)
        emit.write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--depth-ckpt", required=True)
    ap.add_argument("--tau-ckpt", required=True)
    ap.add_argument("--config", default="configs/aerial_rl.yaml")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--max-episodes", type=int, default=0)
    ap.add_argument("--heldout-frac", type=float, default=0.35)
    ap.add_argument("--split-seed", type=int, default=0)
    ap.add_argument("--emit", default=None)
    ap.add_argument("--l1", type=float, default=DEFAULT_L1)
    ap.add_argument("--l2", type=float, default=DEFAULT_L2)
    ap.add_argument("--l3", type=float, default=DEFAULT_L3)
    ap.add_argument("--v1", type=float, default=DEFAULT_V1)
    ap.add_argument("--v2", type=float, default=DEFAULT_V2)
    ap.add_argument("--a-max", type=float, default=DEFAULT_A_MAX)
    ap.add_argument("--delay-s", type=float, default=DEFAULT_DELAY_S)
    args = ap.parse_args(argv)

    import yaml

    cfg = yaml.safe_load(Path(args.config).read_text()) or {}
    spec = ThreeZoneSpec(
        l1_m=float(args.l1),
        l2_m=float(args.l2),
        l3_m=float(args.l3),
        v1_m_s=float(args.v1),
        v2_m_s=float(args.v2),
        a_max_m_s2=float(args.a_max),
        delay_s=float(args.delay_s),
    )
    payload = run_eval(
        dataset=Path(args.dataset).expanduser(),
        depth_ckpt=Path(args.depth_ckpt).expanduser(),
        tau_ckpt=Path(args.tau_ckpt).expanduser(),
        device=str(args.device),
        config=cfg,
        spec=spec,
        heldout_frac=float(args.heldout_frac),
        split_seed=int(args.split_seed),
        max_episodes=int(args.max_episodes),
        emit=Path(args.emit).expanduser() if args.emit else None,
    )
    kin = payload["kinematic"]
    print(
        f"[three-zone] kinematic feasible={kin['feasible_nominal']} "
        f"engage≥{kin['engage_outer_m']}m budget={kin['max_underread_at_engage_m']}m"
    )
    for name, row in payload["depth_vs_budget"]["bands"].items():
        if row.get("n", 0) == 0:
            print(f"  {name}: no support")
            continue
        mark = "OK" if row.get("ok") else "FAIL"
        print(
            f"  {name}: {mark} n={row['n']} p95_under={row['p95_underread_m']}m "
            f"budget={row['budget_m']}m exceed_frac={row['frac_exceed_budget']}"
        )
    h = payload.get("0h_engage_miss", {})
    if h.get("n_cond", 0):
        mark = "OK" if h.get("ok") else "FAIL"
        print(
            f"  0h engage_miss: {mark} n={h.get('n_cond')} "
            f"p={h.get('p_engage_miss')} consec={h.get('max_consecutive_miss')} "
            f"@ {h.get('engage_outer_m')}m"
        )
    else:
        print("  0h engage_miss: no support")
    print(f"[three-zone] verdict ok={payload['verdict']['ok']}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
