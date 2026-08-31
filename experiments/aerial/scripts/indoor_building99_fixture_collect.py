#!/usr/bin/env python3
"""E2h.2 Building_99 fixture corpus: body-frame GT-PD → NPZ (+ optional ego mp4).

Declared assist=gt_pd_body (not mainline). Uses the same micro limits / +up
coords as indoor_loop_collect, but skips WAM/planner so short indoor legs can
actually arrive (needed for keep-arrived corpus on Building_99 atrium).
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("b99_fixture_npz")

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def body_pd(pos: np.ndarray, yaw: float, goal: np.ndarray, limits: np.ndarray) -> np.ndarray:
    c, s = math.cos(yaw), math.sin(yaw)
    R = np.array([[c, s, 0], [-s, c, 0], [0, 0, 1]], dtype=np.float64)
    rel = R @ (goal - pos)
    a = 0.45 * rel
    a = np.array([a[0], a[1], a[2], 0.0], dtype=np.float64)
    lim = np.asarray(limits, dtype=np.float64)
    a[:3] = np.clip(a[:3], -lim[:3], lim[:3])
    a[3] = float(np.clip(0.5 * math.atan2(rel[1], max(rel[0], 1e-3)), -lim[3], lim[3]))
    return a


def _depth_min(obs) -> float:
    depth = getattr(obs, "depth", None)
    if depth is None:
        return float("nan")
    d = np.asarray(depth, dtype=np.float64)
    fin = np.isfinite(d) & (d > 0)
    return float(np.nanmin(d[fin])) if fin.any() else float("nan")


def _load_segments(ann_path: Path, target_len_m: float) -> List[Dict[str, Any]]:
    routes = json.loads(ann_path.read_text(encoding="utf-8"))
    segs: List[Dict[str, Any]] = []
    for idx, r in enumerate(routes):
        pos = np.asarray(r["pos"], dtype=np.float64)
        yaw = np.asarray(r["yaw"], dtype=np.float64).reshape(-1)
        end = 1
        cum = 0.0
        for k in range(len(pos) - 1):
            cum += float(np.linalg.norm(pos[k + 1] - pos[k]))
            end = k + 1
            if cum >= target_len_m:
                break
        start, goal = pos[0], pos[end]
        segs.append(
            {
                "source_route_idx": idx,
                "route_name": r.get("trajectory_id", f"Route_{idx + 1:02d}"),
                "segment_name": f"B99_{r.get('trajectory_id', f'R{idx+1:02d}')}",
                "pos": [start.tolist(), goal.tolist()],
                "yaw": [float(yaw[0]), float(yaw[min(end, len(yaw) - 1)])],
                "d0_m": round(float(np.linalg.norm(goal - start)), 3),
                "gpt_instruction": r.get("gpt_instruction", "Building_99 indoor"),
            }
        )
    return segs


def run_ep(
    env,
    seg: Dict[str, Any],
    *,
    max_steps: int,
    success_dist: float,
    limits: np.ndarray,
    reward_cfg: Any,
) -> Tuple[Dict[str, Any], List[Any]]:
    from experiments.aerial.rl.buffer import Transition
    from experiments.aerial.rl.reward import NavigationReward

    goal = np.asarray(seg["pos"][1], dtype=np.float64)
    obs = env.reset({"pos": seg["pos"], "yaw": seg["yaw"], "gpt_instruction": seg["gpt_instruction"]})
    if obs is None or getattr(obs, "rgb", None) is None:
        return {"ok": False, "reason": "reset_failed", "segment_name": seg["segment_name"]}, []
    if float(np.asarray(obs.rgb).mean()) < 1.0:
        return {"ok": False, "reason": "black_rgb", "segment_name": seg["segment_name"]}, []

    obs.info["goal"] = goal.tolist()
    reward_fn = NavigationReward(goal, reward_cfg)
    reward_fn.reset(goal, obs.position)
    transitions: List[Any] = []
    dmins: List[float] = []
    step_i = 0
    for step_i in range(max_steps):
        action = body_pd(np.asarray(obs.position, dtype=np.float64), float(obs.yaw), goal, limits)
        next_obs, info = env.step(action)
        next_obs.info["goal"] = goal.tolist()
        dmin = _depth_min(next_obs)
        if not math.isnan(dmin):
            dmins.append(dmin)
        r, done, terms = reward_fn.step(next_obs, action)
        ep_info = {**info, **terms, "intervention": False, "goal": goal.tolist(), "assist": "gt_pd_body"}
        transitions.append(
            Transition(obs=obs, action=action, reward=r, done=done, next_obs=next_obs, info=ep_info)
        )
        obs = next_obs
        d = float(np.linalg.norm(np.asarray(obs.position) - goal))
        if d <= success_dist or bool(getattr(obs, "collided", False)):
            break

    d_end = float(np.linalg.norm(np.asarray(obs.position) - goal))
    finite = [x for x in dmins if not math.isnan(x)]
    rep = {
        "ok": True,
        "segment_name": seg["segment_name"],
        "route_name": seg["route_name"],
        "source_route_idx": seg["source_route_idx"],
        "steps": step_i + 1,
        "d0_m": seg["d0_m"],
        "d_end_m_gt": round(d_end, 4),
        "arrived_gt": d_end <= success_dist,
        "collided": bool(getattr(obs, "collided", False)),
        "intervention_rate": 0.0,
        "depth_min_median_m": round(float(np.median(finite)), 3) if finite else None,
        "near_depth_frac": round(float(np.mean([x < 5.0 for x in finite])), 3) if finite else None,
        "assist": "gt_pd_body",
        "bc_tag": "fixture_gt_pd_building99_body",
        "scene": "Building_99",
        "pose_source": "gt_proxy",
    }
    return rep, transitions


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--annotation", default="artifacts/building99_indoor_short_routes.json")
    ap.add_argument("--out", required=True)
    ap.add_argument("--episodes", type=int, default=40)
    ap.add_argument("--segment-len-m", type=float, default=3.0)
    ap.add_argument("--success-dist", type=float, default=0.50)
    ap.add_argument("--max-steps", type=int, default=120)
    ap.add_argument("--min-usable", type=int, default=10)
    ap.add_argument("--keep-arrived-only", action="store_true", default=True)
    ap.add_argument("--no-keep-arrived-only", action="store_false", dest="keep_arrived_only")
    ap.add_argument("--write-ego-mp4", action="store_true")
    ap.add_argument(
        "--append",
        action="store_true",
        help="Append to existing out-dir (do not overwrite prior NPZ; merge summary)",
    )
    ap.add_argument(
        "--min-usable-new",
        type=int,
        default=None,
        help="When --append, gate only on new episodes this run (default: --min-usable)",
    )
    args = ap.parse_args()

    root = _ROOT
    from experiments.aerial.rl import dataset as ds
    from experiments.aerial.rl.env.airsim_env import AirSimDroneEnv, AirSimEnvConfig
    from experiments.aerial.rl.reward import RewardConfig

    ann = Path(args.annotation) if Path(args.annotation).is_absolute() else root / args.annotation
    segs = _load_segments(ann, args.segment_len_m)
    plan = [segs[i % len(segs)] for i in range(args.episodes)]

    cfg = AirSimEnvConfig(
        host="127.0.0.1",
        port=41451,
        vehicle=os.environ.get("AIRSIM_VEHICLE", "drone_1"),
        camera=os.environ.get("AIRSIM_CAMERA", "0"),
        grab_depth=True,
        step_hz=5.0,
        health_check=False,
    )
    env = AirSimDroneEnv(cfg)
    limits = np.array([0.15, 0.08, 0.08, 0.10], dtype=np.float64)
    reward_cfg = RewardConfig(success_dist_m=float(args.success_dist))

    out_dir = Path(args.out) if Path(args.out).is_absolute() else root / args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    prior_manifest: List[Dict[str, Any]] = []
    prior_reports: List[Dict[str, Any]] = []
    prior_quality: List[Dict[str, Any]] = []
    ep_idx = 0
    if args.append:
        existing = sorted(out_dir.glob("episode_*.npz"))
        ep_idx = len(existing)
        summary_path = out_dir / "collection_summary.json"
        if summary_path.is_file():
            old = json.loads(summary_path.read_text(encoding="utf-8"))
            prior_reports = list(old.get("episodes") or [])
        manifest_path = out_dir / "manifest.json"
        if manifest_path.is_file():
            old_m = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(old_m, dict):
                prior_manifest = list(old_m.get("episodes") or old_m.get("manifest") or [])
            elif isinstance(old_m, list):
                prior_manifest = old_m
        qpath = out_dir / "QUALITY_SUMMARY.json"
        if qpath.is_file():
            prior_quality = json.loads(qpath.read_text(encoding="utf-8"))
            if not isinstance(prior_quality, list):
                prior_quality = []
        logger.info("append mode: prior_npz=%d start_idx=%d", ep_idx, ep_idx)

    manifest: List[Dict[str, Any]] = []
    reports: List[Dict[str, Any]] = []
    quality_reports: List[Dict[str, Any]] = []
    skipped = 0

    try:
        for seg in plan:
            logger.info("--- %s d0=%.1fm ---", seg["segment_name"], seg["d0_m"])
            rep, transitions = run_ep(
                env, seg,
                max_steps=args.max_steps,
                success_dist=args.success_dist,
                limits=limits,
                reward_cfg=reward_cfg,
            )
            if not rep.get("ok") or not transitions:
                skipped += 1
                logger.warning("skip %s: %s", seg["segment_name"], rep.get("reason"))
                continue
            if args.keep_arrived_only and not rep.get("arrived_gt"):
                skipped += 1
                logger.info("drop non-arrived %s d_end=%.2f", seg["segment_name"], rep["d_end_m_gt"])
                continue

            path = ds.write_episode(out_dir, ep_idx, transitions)
            qrep = ds.quality_report(transitions)
            bad = ds.assert_nontrivial(qrep)
            quar = ds.quarantine_reasons(qrep)
            usable = not bad and not quar
            logger.info(
                "ep %d %s steps=%d d_end=%.2f arrived=%s depth_med=%s usable=%s -> %s",
                ep_idx, seg["segment_name"], rep["steps"], rep["d_end_m_gt"],
                rep["arrived_gt"], rep.get("depth_min_median_m"), usable, path.name,
            )
            manifest.append(
                {
                    "file": path.name,
                    "steps": qrep["steps"],
                    "return": qrep["reward_sum"],
                    "segment_name": rep["segment_name"],
                    "route_name": rep["route_name"],
                    "d_end_m_gt": rep["d_end_m_gt"],
                    "arrived_gt": rep["arrived_gt"],
                    "depth_min_median_m": rep.get("depth_min_median_m"),
                    "nontrivial": not bad,
                    "quarantined": bool(quar),
                    "usable": usable,
                }
            )
            quality_reports.append(qrep)
            reports.append({**qrep, **rep})
            ep_idx += 1
    finally:
        try:
            env.close()
        except Exception:
            pass

    all_manifest = prior_manifest + manifest
    all_reports = prior_reports + reports
    all_quality = prior_quality + quality_reports
    usable_n = sum(1 for m in all_manifest if m.get("usable"))
    usable_new = sum(1 for m in manifest if m.get("usable"))
    dmins = [
        r.get("depth_min_median_m")
        for r in all_reports
        if r.get("depth_min_median_m") is not None
    ]
    meta = {
        "protocol": "indoor_fixture_bc_E2h_building99_body",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "scene": "Building_99",
        "annotation": str(ann),
        "assist": "gt_pd_body",
        "bc_tag": "fixture_gt_pd_building99_body",
        "pose_source": "gt_proxy",
        "keep_arrived_only": bool(args.keep_arrived_only),
        "success_dist_m": args.success_dist,
        "segment_len_m": args.segment_len_m,
        "n_requested_this_run": args.episodes,
        "n_collected_this_run": len(manifest),
        "n_usable_this_run": usable_new,
        "skipped_this_run": skipped,
        "n_collected": len(all_manifest),
        "n_usable": usable_n,
        "append": bool(args.append),
        "near_depth_frac": round(float(np.mean([x < 5.0 for x in dmins])), 3) if dmins else None,
        "depth_min_median_mean": round(float(np.mean(dmins)), 3) if dmins else None,
        "note": "Body-frame GT-PD fixture on Building_99; NOT mainline assist=none completion.",
    }
    ds.write_manifest(out_dir, all_manifest, meta=meta)
    ds.write_quality_summary(out_dir, all_quality)
    summary = {
        **meta,
        "arrival_rate_gt": round(
            sum(1 for r in all_reports if r.get("arrived_gt")) / max(len(all_reports), 1), 4
        ),
        "mean_d_end_gt": round(float(np.mean([r["d_end_m_gt"] for r in all_reports])), 4)
        if all_reports
        else None,
        "episodes": all_reports,
    }
    (out_dir / "collection_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    logger.info(
        "summary total usable=%d/%d new=%d near_depth=%s -> %s",
        usable_n, len(all_manifest), usable_new, meta.get("near_depth_frac"), out_dir,
    )
    gate = args.min_usable_new if args.min_usable_new is not None else args.min_usable
    check_n = usable_new if args.append else usable_n
    if check_n < gate:
        logger.error("usable %d < min gate %d (append=%s)", check_n, gate, args.append)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
