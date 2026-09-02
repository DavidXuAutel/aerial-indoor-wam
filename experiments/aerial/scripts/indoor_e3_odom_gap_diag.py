#!/usr/bin/env python3
"""E3.4 — odom gt vs hat gap diagnostic (eval JSON + optional collect NPZ replay).

Answers: is G1 failure from policy miss or odom terminal error?
"""
from __future__ import annotations

import argparse
import glob
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np


def _goal_dist(p: np.ndarray, goal: np.ndarray) -> float:
    return float(np.linalg.norm(np.asarray(p, dtype=np.float64).reshape(3) - goal))


def _is_spawn(ep: Dict[str, Any], spawn_max_steps: int = 8) -> bool:
    return bool(ep.get("collided")) and int(ep.get("steps") or 0) <= spawn_max_steps


def _load_eval_eps(paths: Sequence[Path]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for p in paths:
        data = json.loads(p.read_text())
        tag = p.stem
        for ep in data.get("episodes") or data.get("results") or []:
            rows.append({"eval_file": str(p), "eval_tag": tag, **ep})
    return rows


def _summarize_eval(rows: List[Dict[str, Any]], *, success_dist: float, spawn_max_steps: int) -> Dict[str, Any]:
    scored: List[Dict[str, Any]] = []
    per_ep: List[Dict[str, Any]] = []
    for ep in rows:
        spawn = _is_spawn(ep, spawn_max_steps)
        d_gt = ep.get("d_end_m_gt", ep.get("d_end_m"))
        d_hat = ep.get("d_end_m_hat", ep.get("d_end_m"))
        arr_gt = bool(ep.get("arrived_gt")) if ep.get("arrived_gt") is not None else (
            float(d_gt) <= success_dist if d_gt is not None else False
        )
        arr_hat = bool(ep.get("arrived_hat")) if ep.get("arrived_hat") is not None else (
            bool(ep.get("arrived") or ep.get("success"))
        )
        d_gap = None
        if d_gt is not None and d_hat is not None:
            d_gap = float(d_hat) - float(d_gt)
        bucket = "SPAWN" if spawn else (
            "ARRIVE_BOTH" if arr_gt and arr_hat else
            "ARRIVE_GT_ONLY" if arr_gt and not arr_hat else
            "ARRIVE_HAT_ONLY" if arr_hat and not arr_gt else
            "NEITHER"
        )
        row = {
            "eval_tag": ep.get("eval_tag"),
            "route_name": ep.get("route_name"),
            "segment_name": ep.get("segment_name"),
            "seed": ep.get("seed"),
            "steps": ep.get("steps"),
            "spawn": spawn,
            "d_end_m_gt": d_gt,
            "d_end_m_hat": d_hat,
            "d_gap_hat_minus_gt": round(d_gap, 4) if d_gap is not None else None,
            "arrived_gt": arr_gt,
            "arrived_hat": arr_hat,
            "bucket": bucket,
            "collided": bool(ep.get("collided")),
        }
        per_ep.append(row)
        if not spawn:
            scored.append(row)

    gaps = [r["d_gap_hat_minus_gt"] for r in scored if r["d_gap_hat_minus_gt"] is not None]
    gt_only = [r for r in scored if r["bucket"] == "ARRIVE_GT_ONLY"]
    by_route: Dict[str, List[float]] = {}
    for r in scored:
        if r["d_gap_hat_minus_gt"] is not None:
            by_route.setdefault(str(r["route_name"]), []).append(r["d_gap_hat_minus_gt"])

    return {
        "n_episodes": len(rows),
        "n_scored": len(scored),
        "n_spawn": sum(1 for r in per_ep if r["spawn"]),
        "arrived_gt_scored": sum(1 for r in scored if r["arrived_gt"]),
        "arrived_hat_scored": sum(1 for r in scored if r["arrived_hat"]),
        "gt_only_hat_miss": len(gt_only),
        "d_gap_hat_minus_gt": {
            "mean": round(float(np.mean(gaps)), 4) if gaps else None,
            "median": round(float(np.median(gaps)), 4) if gaps else None,
            "min": round(float(np.min(gaps)), 4) if gaps else None,
            "max": round(float(np.max(gaps)), 4) if gaps else None,
        },
        "by_route_mean_d_gap": {
            k: round(float(np.mean(v)), 4) for k, v in sorted(by_route.items())
        },
        "bucket_counts_scored": _count_buckets(scored),
        "episodes": per_ep,
    }


def _count_buckets(rows: List[Dict[str, Any]]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for r in rows:
        out[r["bucket"]] = out.get(r["bucket"], 0) + 1
    return out


def _replay_odom_terminal(npz_path: Path) -> Optional[Dict[str, Any]]:
    """Offline dead-reckoning on one NPZ; compare terminal p_hat vs proprio GT."""
    try:
        z = np.load(npz_path, allow_pickle=False)
    except Exception:
        return None
    if "proprio" not in z or "actions" not in z or "goal" not in z:
        return None
    proprio = np.asarray(z["proprio"], dtype=np.float64)
    actions = np.asarray(z["actions"], dtype=np.float64)
    goal = np.asarray(z["goal"], dtype=np.float64).reshape(3)
    if proprio.shape[0] < 1:
        return None

    p_hat = proprio[0, :3].copy()
    psi_hat = float(proprio[0, 3])
    origin_z = float(proprio[0, 2])
    ts = np.asarray(z["timestamps"], dtype=np.float64) if "timestamps" in z else None
    imu_ang = np.asarray(z["imu_ang_vel"], dtype=np.float64) if "imu_ang_vel" in z else None

    for i in range(actions.shape[0]):
        act = actions[i].reshape(4)
        dt = 0.2
        if ts is not None and i > 0:
            dt = max(float(ts[i] - ts[i - 1]), 1e-3)
        dyaw = float(act[3])
        if imu_ang is not None and np.all(np.isfinite(imu_ang[i])):
            dyaw = float(imu_ang[i, 2]) * dt
        psi_hat += dyaw
        psi_hat = math.atan2(math.sin(psi_hat), math.cos(psi_hat))
        c = math.cos(psi_hat - dyaw)
        s = math.sin(psi_hat - dyaw)
        dx_w = c * act[0] - s * act[1]
        dy_w = s * act[0] + c * act[1]
        p_hat[0] += dx_w
        p_hat[1] += dy_w
        p_hat[2] += float(act[2])

    p_gt = proprio[-1, :3]
    pos_err = float(np.linalg.norm(p_hat - p_gt))
    d_gt = _goal_dist(p_gt, goal)
    d_hat = _goal_dist(p_hat, goal)
    return {
        "npz": str(npz_path.name),
        "steps": int(proprio.shape[0]),
        "pos_err_m": round(pos_err, 4),
        "d_end_m_gt": round(d_gt, 4),
        "d_end_m_hat_replay": round(d_hat, 4),
        "d_gap_hat_minus_gt": round(d_hat - d_gt, 4),
        "arrived_gt": bool(d_gt <= 0.50),
        "arrived_hat_replay": bool(d_hat <= 0.50),
    }


def _summarize_dataset(dataset_dir: Path, *, success_dist: float) -> Dict[str, Any]:
    paths = sorted(dataset_dir.glob("episode_*.npz"))
    rows = [r for p in paths if (r := _replay_odom_terminal(p)) is not None]
    if not rows:
        return {"n_npz": 0, "note": "no usable npz with goal+proprio+actions"}
    gaps = [r["d_gap_hat_minus_gt"] for r in rows]
    pos_errs = [r["pos_err_m"] for r in rows]
    return {
        "n_npz": len(rows),
        "pos_err_m": {
            "mean": round(float(np.mean(pos_errs)), 4),
            "median": round(float(np.median(pos_errs)), 4),
            "p90": round(float(np.percentile(pos_errs, 90)), 4),
        },
        "d_gap_hat_minus_gt": {
            "mean": round(float(np.mean(gaps)), 4),
            "median": round(float(np.median(gaps)), 4),
        },
        "arrived_gt_frac": round(sum(1 for r in rows if r["arrived_gt"]) / len(rows), 4),
        "arrived_hat_replay_frac": round(
            sum(1 for r in rows if r["arrived_hat_replay"]) / len(rows), 4
        ),
        "gt_only_hat_miss": sum(
            1 for r in rows if r["arrived_gt"] and not r["arrived_hat_replay"]
        ),
        "episodes_sample": rows[:5],
    }


def _verdict(eval_sum: Dict[str, Any], ds_sum: Optional[Dict[str, Any]], *, success_dist: float) -> str:
    gt = eval_sum.get("arrived_gt_scored", 0)
    hat = eval_sum.get("arrived_hat_scored", 0)
    gt_only = eval_sum.get("gt_only_hat_miss", 0)
    gap_mean = (eval_sum.get("d_gap_hat_minus_gt") or {}).get("mean")
    if gt > 0 and hat == 0 and gt_only == gt:
        return (
            f"G1 miss is odom-dominated: scored {gt}/{eval_sum.get('n_scored')} arrived_gt "
            f"but 0 arrived_hat; mean d_hat−d_gt≈{gap_mean} m (>0 ⇒ hat thinks farther). "
            f"Fix estimator / terminal CE before blind FT."
        )
    if hat > 0:
        return "Mixed: some arrived_hat — policy + odom both contribute."
    return "No scored arrivals under gt either — check policy/spawn separately."


def main() -> int:
    ap = argparse.ArgumentParser(description="E3 odom gt vs hat gap diagnostic")
    ap.add_argument("--eval-glob", required=True, help="Glob for eval JSON files")
    ap.add_argument("--dataset", default="", help="Optional collect NPZ dir for offline replay")
    ap.add_argument("--success-dist", type=float, default=0.50)
    ap.add_argument("--spawn-max-steps", type=int, default=8)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    paths = sorted(Path(p) for p in glob.glob(args.eval_glob))
    if not paths:
        raise SystemExit(f"no eval files match {args.eval_glob!r}")

    rows = _load_eval_eps(paths)
    eval_sum = _summarize_eval(
        rows, success_dist=float(args.success_dist), spawn_max_steps=int(args.spawn_max_steps)
    )
    ds_sum = None
    if args.dataset:
        ds_sum = _summarize_dataset(Path(args.dataset), success_dist=float(args.success_dist))

    out = {
        "protocol": "e3_odom_gap_diag",
        "success_dist_m": float(args.success_dist),
        "eval_files": [str(p) for p in paths],
        "eval": eval_sum,
        "dataset_replay": ds_sum,
        "verdict": _verdict(eval_sum, ds_sum, success_dist=float(args.success_dist)),
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps({k: out[k] for k in ("verdict", "eval", "dataset_replay")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
