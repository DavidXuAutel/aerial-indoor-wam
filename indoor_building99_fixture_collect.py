#!/usr/bin/env python3
"""E2h.2 Building_99 fixture corpus: body-frame GT-PD → NPZ (+ optional ego mp4).

Declared assist=gt_pd_body (not mainline). Uses the same micro limits / +up
coords as indoor_loop_collect, but skips WAM/planner so short indoor legs can
actually arrive (needed for keep-arrived corpus on Building_99 atrium).

Multi-waypoint annotations (len(pos)>=3) chain gt_pd_body through detour
waypoints — used for E2i.D fixture avoid demos (lateral arc, not straight BC).
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

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


def _yaw_at(yaw: np.ndarray, idx: int) -> float:
    if len(yaw) == 0:
        return 0.0
    return float(yaw[min(idx, len(yaw) - 1)])


def _load_segments(
    ann_path: Path,
    target_len_m: float,
    *,
    route_indices: List[int],
) -> List[Dict[str, Any]]:
    routes = json.loads(ann_path.read_text(encoding="utf-8"))
    segs: List[Dict[str, Any]] = []
    for idx in route_indices:
        if idx < 0 or idx >= len(routes):
            logger.warning("route index %d out of range (n=%d)", idx, len(routes))
            continue
        r = routes[idx]
        pos = np.asarray(r["pos"], dtype=np.float64)
        yaw = np.asarray(r["yaw"], dtype=np.float64).reshape(-1)
        tid = r.get("trajectory_id", f"R{idx + 1:02d}")
        if len(pos) >= 3:
            path_len = float(sum(np.linalg.norm(pos[k + 1] - pos[k]) for k in range(len(pos) - 1)))
            segs.append(
                {
                    "source_route_idx": int(r.get("source_route_idx", idx)),
                    "route_name": tid,
                    "segment_name": f"B99_avoid_{tid}",
                    "pos": pos.tolist(),
                    "yaw": [float(y) for y in yaw],
                    "waypoints": pos.tolist(),
                    "d0_m": round(path_len, 3),
                    "avoid_tag": r.get("avoid_tag"),
                    "gpt_instruction": r.get("gpt_instruction", "Building_99 indoor avoid"),
                }
            )
            continue
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
                "source_route_idx": int(r.get("source_route_idx", idx)),
                "route_name": tid,
                "segment_name": f"B99_{tid}",
                "pos": [start.tolist(), goal.tolist()],
                "yaw": [float(yaw[0]), float(_yaw_at(yaw, end))],
                "d0_m": round(float(np.linalg.norm(goal - start)), 3),
                "gpt_instruction": r.get("gpt_instruction", "Building_99 indoor"),
            }
        )
    return segs


def _lateral_offset_m(traj: np.ndarray, start: np.ndarray, goal: np.ndarray) -> float:
    if len(traj) < 2:
        return 0.0
    chord = goal - start
    chord_len = float(np.linalg.norm(chord[:2]))
    if chord_len < 1e-3:
        return 0.0
    u = chord[:2] / chord_len
    perp = np.array([-u[1], u[0]], dtype=np.float64)
    offsets = [abs(float(perp @ (p[:2] - start[:2]))) for p in traj]
    return float(max(offsets)) if offsets else 0.0


def run_ep(
    env,
    seg: Dict[str, Any],
    *,
    max_steps: int,
    success_dist: float,
    wp_reach_m: float,
    limits: np.ndarray,
    reward_cfg: Any,
    drop_collided: bool,
    bc_tag: str,
) -> Tuple[Dict[str, Any], List[Any]]:
    from experiments.aerial.rl.buffer import Transition
    from experiments.aerial.rl.reward import NavigationReward

    waypoints_raw = seg.get("waypoints") or seg["pos"]
    waypoints = [np.asarray(p, dtype=np.float64) for p in waypoints_raw]
    goal = waypoints[-1]
    start = waypoints[0]
    reset_pos = [start.tolist(), goal.tolist()]
    reset_yaw = seg["yaw"] if len(seg["yaw"]) >= 2 else [seg["yaw"][0], seg["yaw"][-1]]

    obs = env.reset({"pos": reset_pos, "yaw": reset_yaw, "gpt_instruction": seg["gpt_instruction"]})
    if obs is None or getattr(obs, "rgb", None) is None:
        return {"ok": False, "reason": "reset_failed", "segment_name": seg["segment_name"]}, []
    if float(np.asarray(obs.rgb).mean()) < 1.0:
        return {"ok": False, "reason": "black_rgb", "segment_name": seg["segment_name"]}, []

    obs.info["goal"] = goal.tolist()
    reward_fn = NavigationReward(goal, reward_cfg)
    reward_fn.reset(goal, obs.position)
    transitions: List[Any] = []
    dmins: List[float] = []
    positions: List[np.ndarray] = [np.asarray(obs.position, dtype=np.float64).copy()]
    wp_idx = 0
    n_wp_hits = 0
    step_i = 0
    for step_i in range(max_steps):
        active_goal = waypoints[wp_idx]
        action = body_pd(np.asarray(obs.position, dtype=np.float64), float(obs.yaw), active_goal, limits)
        next_obs, info = env.step(action)
        next_obs.info["goal"] = goal.tolist()
        dmin = _depth_min(next_obs)
        if not math.isnan(dmin):
            dmins.append(dmin)
        r, done, terms = reward_fn.step(next_obs, action)
        ep_info = {
            **info,
            **terms,
            "intervention": False,
            "goal": goal.tolist(),
            "assist": "gt_pd_body",
            "active_wp_idx": wp_idx,
            "avoid_tag": seg.get("avoid_tag"),
        }
        transitions.append(
            Transition(obs=obs, action=action, reward=r, done=done, next_obs=next_obs, info=ep_info)
        )
        obs = next_obs
        positions.append(np.asarray(obs.position, dtype=np.float64).copy())
        pos = positions[-1]
        d_active = float(np.linalg.norm(pos - active_goal))
        reach = success_dist if wp_idx >= len(waypoints) - 1 else wp_reach_m
        if d_active <= reach and wp_idx < len(waypoints) - 1:
            wp_idx += 1
            n_wp_hits += 1
        d = float(np.linalg.norm(pos - goal))
        if d <= success_dist or bool(getattr(obs, "collided", False)):
            break

    d_end = float(np.linalg.norm(np.asarray(obs.position) - goal))
    collided = bool(getattr(obs, "collided", False))
    finite = [x for x in dmins if not math.isnan(x)]
    lateral_m = _lateral_offset_m(np.asarray(positions), start, goal)
    rep = {
        "ok": True,
        "segment_name": seg["segment_name"],
        "route_name": seg["route_name"],
        "source_route_idx": seg["source_route_idx"],
        "steps": step_i + 1,
        "d0_m": seg["d0_m"],
        "d_end_m_gt": round(d_end, 4),
        "arrived_gt": d_end <= success_dist and not (drop_collided and collided),
        "collided": collided,
        "intervention_rate": 0.0,
        "depth_min_median_m": round(float(np.median(finite)), 3) if finite else None,
        "near_depth_frac": round(float(np.mean([x < 5.0 for x in finite])), 3) if finite else None,
        "assist": "gt_pd_body",
        "bc_tag": bc_tag,
        "avoid_tag": seg.get("avoid_tag"),
        "n_waypoints": len(waypoints),
        "n_wp_hits": n_wp_hits,
        "lateral_offset_m": round(lateral_m, 3),
        "scene": "Building_99",
        "pose_source": "gt_proxy",
    }
    if drop_collided and collided:
        rep["arrived_gt"] = False
        rep["reason"] = "collided"
    return rep, transitions


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--annotation", default="artifacts/building99_indoor_short_routes.json")
    ap.add_argument("--routes", default="all", help="0-based indices comma-sep, or 'all'")
    ap.add_argument("--out", required=True)
    ap.add_argument("--episodes", type=int, default=40)
    ap.add_argument("--segment-len-m", type=float, default=3.0)
    ap.add_argument("--success-dist", type=float, default=0.50)
    ap.add_argument("--wp-reach-m", type=float, default=0.35, help="Intermediate waypoint reach (m)")
    ap.add_argument("--max-steps", type=int, default=120)
    ap.add_argument("--min-usable", type=int, default=10)
    ap.add_argument("--keep-arrived-only", action="store_true", default=True)
    ap.add_argument("--no-keep-arrived-only", action="store_false", dest="keep_arrived_only")
    ap.add_argument("--drop-collided", action="store_true", help="Reject episodes that end collided")
    ap.add_argument(
        "--bc-tag",
        default="fixture_gt_pd_building99_body",
        help="Bookkeeping tag for mix (e.g. fixture_avoid_e2i_d)",
    )
    ap.add_argument(
        "--protocol",
        default="indoor_fixture_bc_E2h_building99_body",
        help="Protocol id in collection_summary",
    )
    ap.add_argument("--append", action="store_true")
    ap.add_argument("--min-usable-new", type=int, default=None)
    args = ap.parse_args()

    root = _ROOT
    from experiments.aerial.rl import dataset as ds
    from experiments.aerial.rl.env.airsim_env import AirSimDroneEnv, AirSimEnvConfig
    from experiments.aerial.rl.reward import RewardConfig

    ann = Path(args.annotation) if Path(args.annotation).is_absolute() else root / args.annotation
    routes = json.loads(ann.read_text(encoding="utf-8"))
    if args.routes.strip().lower() == "all":
        route_indices = list(range(len(routes)))
    else:
        route_indices = [int(x) for x in args.routes.split(",") if x.strip()]
    segs = _load_segments(ann, args.segment_len_m, route_indices=route_indices)
    if not segs:
        logger.error("no segments from annotation=%s routes=%s", ann, args.routes)
        return 2
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
            logger.info("--- %s d0=%.1fm wps=%d ---", seg["segment_name"], seg["d0_m"], len(seg.get("waypoints") or seg["pos"]))
            rep, transitions = run_ep(
                env,
                seg,
                max_steps=args.max_steps,
                success_dist=args.success_dist,
                wp_reach_m=args.wp_reach_m,
                limits=limits,
                reward_cfg=reward_cfg,
                drop_collided=args.drop_collided,
                bc_tag=args.bc_tag,
            )
            if not rep.get("ok") or not transitions:
                skipped += 1
                logger.warning("skip %s: %s", seg["segment_name"], rep.get("reason"))
                continue
            if args.keep_arrived_only and not rep.get("arrived_gt"):
                skipped += 1
                logger.info(
                    "drop non-arrived %s d_end=%.2f coll=%s lateral=%.2f",
                    seg["segment_name"],
                    rep["d_end_m_gt"],
                    rep.get("collided"),
                    rep.get("lateral_offset_m", 0.0),
                )
                continue

            path = ds.write_episode(out_dir, ep_idx, transitions)
            qrep = ds.quality_report(transitions)
            bad = ds.assert_nontrivial(qrep)
            quar = ds.quarantine_reasons(qrep)
            usable = not bad and not quar
            logger.info(
                "ep %d %s steps=%d d_end=%.2f lateral=%.2f wp_hits=%s usable=%s -> %s",
                ep_idx,
                seg["segment_name"],
                rep["steps"],
                rep["d_end_m_gt"],
                rep.get("lateral_offset_m", 0.0),
                rep.get("n_wp_hits"),
                usable,
                path.name,
            )
            manifest.append(
                {
                    "file": path.name,
                    "steps": qrep["steps"],
                    "return": qrep["reward_sum"],
                    "segment_name": rep["segment_name"],
                    "route_name": rep["route_name"],
                    "source_route_idx": rep.get("source_route_idx"),
                    "d_end_m_gt": rep["d_end_m_gt"],
                    "arrived_gt": rep["arrived_gt"],
                    "lateral_offset_m": rep.get("lateral_offset_m"),
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
    dmins = [r.get("depth_min_median_m") for r in all_reports if r.get("depth_min_median_m") is not None]
    meta = {
        "protocol": args.protocol,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "scene": "Building_99",
        "annotation": str(ann),
        "routes": args.routes,
        "assist": "gt_pd_body",
        "bc_tag": args.bc_tag,
        "pose_source": "gt_proxy",
        "keep_arrived_only": bool(args.keep_arrived_only),
        "drop_collided": bool(args.drop_collided),
        "success_dist_m": args.success_dist,
        "wp_reach_m": args.wp_reach_m,
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
        "note": "Body-frame GT-PD fixture; multi-waypoint = avoid demo. NOT mainline assist=none completion.",
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
        "mean_lateral_offset_m": round(float(np.mean([r.get("lateral_offset_m") or 0.0 for r in all_reports])), 4)
        if all_reports
        else None,
        "episodes": all_reports,
    }
    (out_dir / "collection_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    logger.info(
        "summary total usable=%d/%d new=%d near_depth=%s -> %s",
        usable_n,
        len(all_manifest),
        usable_new,
        meta.get("near_depth_frac"),
        out_dir,
    )
    gate = args.min_usable_new if args.min_usable_new is not None else args.min_usable
    check_n = usable_new if args.append else usable_n
    if check_n < gate:
        logger.error("usable %d < min gate %d (append=%s)", check_n, gate, args.append)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
