#!/usr/bin/env python3
"""Indoor / Micro-Space Lossless Evaluation (Step 1: Zero Retraining).

Evaluates the existing Aerial-WAM models in micro-scale spaces (5m ~ 15m) with a tight
0.xm (0.5m) arrival tolerance.

Compares:
  1. Default Outdoor Mode (Limits [1.0, 0.4, 0.4, 0.314], L3=1.5m)
  2. Indoor Lossless Mode (Micro Limits [0.15, 0.08, 0.08, 0.10], Micro Shield L3=0.4m)

Usage on 125:
  source experiments/aerial/scripts/env_4090.sh
  $AERIAL_PY experiments/aerial/scripts/indoor_lossless_eval.py \
    --config configs/aerial_rl_indoor_lossless.yaml \
    --episodes 6 \
    --out artifacts/indoor_lossless_eval_20260828.json
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import yaml

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("indoor_lossless")


def _goal_dist(pos: np.ndarray, goal: np.ndarray) -> float:
    return float(np.linalg.norm(np.asarray(goal, dtype=np.float64).reshape(3) - np.asarray(pos, dtype=np.float64).reshape(3)))


def _full_min_depth(depth: Optional[np.ndarray]) -> float:
    if depth is None:
        return float("nan")
    d = np.asarray(depth, dtype=np.float64)
    finite = d[np.isfinite(d) & (d > 0)]
    return float(np.min(finite)) if finite.size else float("nan")


def build_micro_test_segments(
    routes: List[Dict[str, Any]],
    target_len_m: float = 10.0,
    max_routes: int = 8,
) -> List[Dict[str, Any]]:
    """Slice near-ground / near-structure routes into 5m~15m micro-space test segments."""
    segments = []
    # Prioritize low-altitude near-structure routes (e.g. Route 9, 10, 7, 13, 14, 18, 5, 20)
    priority_indices = [8, 9, 6, 12, 13, 17, 4, 19, 0, 2]

    for idx in priority_indices:
        if idx >= len(routes) or len(segments) >= max_routes:
            continue
        r = routes[idx]
        pos_list = np.asarray(r["pos"], dtype=np.float64)
        yaw_list = np.asarray(r["yaw"], dtype=np.float64)

        # Find a segment of ~target_len_m along the route
        start_idx = 0
        end_idx = min(len(pos_list) - 1, 4)
        cum_dist = 0.0
        for k in range(len(pos_list) - 1):
            seg_d = np.linalg.norm(pos_list[k + 1] - pos_list[k])
            cum_dist += seg_d
            if cum_dist >= target_len_m:
                end_idx = k + 1
                break

        seg_start = pos_list[start_idx].copy()
        seg_goal = pos_list[end_idx].copy()
        seg_yaw = float(yaw_list[start_idx])
        d0 = _goal_dist(seg_start, seg_goal)

        segments.append({
            "source_route_idx": idx,
            "segment_name": f"MicroRoute_{len(segments)+1:02d}_(from_Route_{idx+1:02d})",
            "pos": [seg_start.tolist(), seg_goal.tolist()],
            "yaw": [seg_yaw, seg_yaw],
            "d0_m": round(d0, 3),
            "start_z": round(float(seg_start[2]), 2),
            "gpt_instruction": r.get("gpt_instruction", "")[:80] + " (micro-space slice)",
        })

    return segments


def run_evaluation_mode(
    mode_name: str,
    segments: List[Dict[str, Any]],
    env: Any,
    collector_cls: Any,
    policy: Any,
    dynamics: Any,
    depth_pred: Any,
    shield: Any,
    planner: Any,
    reward_cfg: Any,
    action_limits: np.ndarray,
    max_steps: int = 120,
    success_dist: float = 0.5,
    step_hz: float = 5.0,
) -> Dict[str, Any]:
    """Run closed-loop evaluation on the segment suite under a specific configuration."""
    from experiments.aerial.rl.buffer import ReplayBuffer

    buf = ReplayBuffer(capacity_episodes=4, seed=0)
    collector = collector_cls(
        env=env,
        policy=policy,
        buffer=buf,
        reward_cfg=reward_cfg,
        safety=shield,
        max_steps=max_steps,
        target_hz=step_hz,
        skip_reset_collision=True,
        depth_predictor=depth_pred,
        planner=planner,
        dynamics=dynamics,
        takeoff_scan_steps=2,
    )

    logger.info(f"\n=======================================================")
    logger.info(f"🚀 Running Evaluation: [{mode_name}]")
    logger.info(f"   Limits: dx={action_limits[0]:.2f}m, dy={action_limits[1]:.2f}m, dz={action_limits[2]:.2f}m, dyaw={action_limits[3]:.2f}rad")
    logger.info(f"   Success Dist Threshold: {success_dist:.2f} m | Max Steps: {max_steps}")
    logger.info(f"=======================================================")

    results = []
    n_arrived = 0
    n_severe_coll = 0
    progress_ratios = []
    intervention_rates = []
    final_distances = []

    for seg in segments:
        ep_dict = {
            "pos": seg["pos"],
            "yaw": seg["yaw"],
            "gpt_instruction": seg["gpt_instruction"],
        }
        goal_pos = np.asarray(seg["pos"][1], dtype=np.float64)
        d0 = seg["d0_m"]

        if hasattr(policy, "reset"):
            policy.reset()
        if hasattr(shield, "reset"):
            shield.reset()

        ep_trans, stats = collector.collect_episode(ep_dict)
        if not ep_trans:
            logger.warning(f"{seg['segment_name']} reset retry...")
            time.sleep(0.5)
            ep_trans, stats = collector.collect_episode(ep_dict)

        if not ep_trans:
            logger.error(f"{seg['segment_name']} failed to spawn.")
            continue

        d_end = _goal_dist(
            ep_trans[-1].next_obs.position if ep_trans[-1].next_obs is not None else ep_trans[-1].obs.position,
            goal_pos,
        )
        d_min = min(_goal_dist(tr.obs.position, goal_pos) for tr in ep_trans)
        arrived = (d_min <= success_dist) or (d_end <= success_dist)
        if arrived:
            n_arrived += 1

        collided = any(bool(getattr(tr.next_obs, "collided", False)) for tr in ep_trans)
        min_clearance = min((_full_min_depth(tr.obs.depth) for tr in ep_trans), default=float("nan"))
        severe_coll = collided or (np.isfinite(min_clearance) and min_clearance < 0.35)
        if severe_coll:
            n_severe_coll += 1

        prog_ratio = (d0 - d_end) / max(d0, 1e-3)
        progress_ratios.append(float(prog_ratio))
        final_distances.append(float(d_end))

        n_interv = sum(1 for tr in ep_trans if tr.info.get("intervention", False))
        interv_rate = n_interv / len(ep_trans)
        intervention_rates.append(float(interv_rate))

        logger.info(
            f"[{mode_name}] {seg['segment_name']} | steps={len(ep_trans):3d} | "
            f"d0={d0:4.1f}m -> d_end={d_end:4.2f}m (min={d_min:4.2f}m) | "
            f"prog={prog_ratio*100:+5.1f}% | arrived={arrived!s:5s} | shield={interv_rate*100:4.1f}%"
        )

        results.append({
            "segment_name": seg["segment_name"],
            "steps": len(ep_trans),
            "d0_m": d0,
            "d_end_m": round(d_end, 3),
            "d_min_m": round(d_min, 3),
            "arrived": bool(arrived),
            "severe_collision": bool(severe_coll),
            "progress_ratio": round(prog_ratio, 4),
            "intervention_rate": round(interv_rate, 4),
            "min_clearance_m": round(min_clearance, 3) if np.isfinite(min_clearance) else None,
        })

    n_scored = len(results)
    summary = {
        "mode_name": mode_name,
        "n_scored": n_scored,
        "arrival_rate": round(n_arrived / max(n_scored, 1), 4),
        "mean_progress_ratio": round(float(np.mean(progress_ratios)), 4) if progress_ratios else 0.0,
        "mean_final_distance_m": round(float(np.mean(final_distances)), 3) if final_distances else 0.0,
        "mean_intervention_rate": round(float(np.mean(intervention_rates)), 4) if intervention_rates else 0.0,
        "severe_collision_rate": round(n_severe_coll / max(n_scored, 1), 4),
        "episodes": results,
    }
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Indoor Lossless Zero-Retraining Verification")
    parser.add_argument("--config", default="configs/aerial_rl_indoor_lossless.yaml")
    parser.add_argument("--wm-ckpt", default="experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt")
    parser.add_argument("--actor-ckpt", default="experiments/aerial/rl/artifacts/v4_ac_ckpt_step_e_20260828/v4_ac_latest.pt")
    parser.add_argument("--depth-ckpt", default="experiments/aerial/rl/artifacts/depth_ckpt_p45mid_s8j_20260825/depth_best_holdout_da3_ft_head.pt")
    parser.add_argument("--annotation", default="artifacts/seen_airsim16_m1a20.json")
    parser.add_argument("--episodes", type=int, default=6)
    parser.add_argument("--segment-len-m", type=float, default=10.0)
    parser.add_argument("--max-steps", type=int, default=100)
    parser.add_argument("--success-dist", type=float, default=0.5, help="0.xm precision threshold (default: 0.5m)")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--out", default="artifacts/indoor_lossless_eval_20260828.json")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from experiments.aerial.rl.actor_critic import LatentActorCritic, LatentActorDeployPolicy
    from experiments.aerial.rl.collector import RolloutCollector
    from experiments.aerial.rl.depth_predictor import DepthMinPredictor
    from experiments.aerial.rl.planner import ImaginationPlanner
    from experiments.aerial.rl.reward import RewardConfig
    from experiments.aerial.rl.safety import ThreeZoneSpeedShield
    from experiments.aerial.rl.three_zone import ThreeZoneSpec
    from experiments.aerial.rl.train_rl import _build_env, load_torch_dynamics

    # Load Route Annotations
    ann_path = (root / args.annotation).resolve() if not Path(args.annotation).is_absolute() else Path(args.annotation)
    with ann_path.open("r", encoding="utf-8") as f:
        routes = json.load(f)

    # Build 5m~15m micro-space test segments
    segments = build_micro_test_segments(routes, target_len_m=args.segment_len_m, max_routes=args.episodes)
    logger.info(f"Built {len(segments)} micro-space test segments (target length: ~{args.segment_len_m}m).")

    # Load Config and Base Models
    cfg = yaml.safe_load((root / args.config).read_text()) or {}
    cfg.setdefault("env", {})["backend"] = "airsim"
    cfg["env"]["step_hz"] = 5.0
    cfg["env"]["grab_depth"] = True
    env = _build_env(cfg["env"])

    reward_cfg = RewardConfig(**(cfg.get("reward") or {}))
    reward_cfg.success_dist_m = float(args.success_dist)

    wm_cfg = cfg.get("world_model") or {}
    wm_path = (root / args.wm_ckpt).resolve() if not Path(args.wm_ckpt).is_absolute() else Path(args.wm_ckpt)
    dynamics, _ = load_torch_dynamics(wm_cfg, str(wm_path), device=str(args.device), success_dist_m=float(args.success_dist))

    actor_path = (root / args.actor_ckpt).resolve() if not Path(args.actor_ckpt).is_absolute() else Path(args.actor_ckpt)
    actor_ac = LatentActorCritic.load_from_checkpoint(actor_path, device=str(args.device))
    policy = LatentActorDeployPolicy(dynamics, actor_ac, deterministic=True)

    depth_path = (root / args.depth_ckpt).resolve() if not Path(args.depth_ckpt).is_absolute() else Path(args.depth_ckpt)
    depth_pred = DepthMinPredictor.from_checkpoint(depth_path, device=str(args.device)) if depth_path.is_file() else None

    # 1. Evaluate Mode A: Outdoor Baseline (1.0m Action Box, 1.5m L3 Shield)
    outdoor_limits = np.array([1.0, 0.4, 0.4, math.pi / 10.0], dtype=np.float64)
    outdoor_shield = ThreeZoneSpeedShield(
        zone=ThreeZoneSpec(l1_m=8.0, l2_m=5.0, l3_m=1.5, v1_m_s=2.0, v2_m_s=1.0, v_stop_m_s=0.2, v_cruise_m_s=5.0, dt_s=0.2),
        retreat_step_m=3.0,
    )
    outdoor_planner = ImaginationPlanner(
        dynamics=dynamics,
        horizon=5,
        reward_cfg=reward_cfg,
        action_limits=outdoor_limits,
        policy=actor_ac,
    )

    summary_outdoor = run_evaluation_mode(
        mode_name="Outdoor_Default_Baseline",
        segments=segments,
        env=env,
        collector_cls=RolloutCollector,
        policy=policy,
        dynamics=dynamics,
        depth_pred=depth_pred,
        shield=outdoor_shield,
        planner=outdoor_planner,
        reward_cfg=reward_cfg,
        action_limits=outdoor_limits,
        max_steps=args.max_steps,
        success_dist=args.success_dist,
    )

    # 2. Evaluate Mode B: Indoor Micro-Scale Lossless (0.15m Action Box, 0.4m L3 Shield)
    indoor_limits = np.array([0.15, 0.08, 0.08, 0.10], dtype=np.float64)
    indoor_shield = ThreeZoneSpeedShield(
        zone=ThreeZoneSpec(l1_m=1.5, l2_m=0.8, l3_m=0.4, v1_m_s=0.6, v2_m_s=0.3, v_stop_m_s=0.05, v_cruise_m_s=1.0, dt_s=0.2),
        retreat_step_m=0.3,
        min_tau_s=0.5,
    )
    indoor_planner = ImaginationPlanner(
        dynamics=dynamics,
        horizon=5,
        reward_cfg=reward_cfg,
        action_limits=indoor_limits,
        policy=actor_ac,
    )

    summary_indoor = run_evaluation_mode(
        mode_name="Indoor_Micro_Lossless",
        segments=segments,
        env=env,
        collector_cls=RolloutCollector,
        policy=policy,
        dynamics=dynamics,
        depth_pred=depth_pred,
        shield=indoor_shield,
        planner=indoor_planner,
        reward_cfg=reward_cfg,
        action_limits=indoor_limits,
        max_steps=args.max_steps,
        success_dist=args.success_dist,
    )

    # Combine and save results
    out_payload = {
        "evaluation_title": "Indoor Micro-Space Lossless Zero-Retraining Evaluation",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "target_precision_m": args.success_dist,
        "segment_count": len(segments),
        "comparison": {
            "outdoor_baseline": summary_outdoor,
            "indoor_lossless": summary_indoor,
        },
    }

    out_file = (root / args.out).resolve() if not Path(args.out).is_absolute() else Path(args.out)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with out_file.open("w", encoding="utf-8") as f:
        json.dump(out_payload, f, indent=2)

    logger.info(f"\n=======================================================")
    logger.info(f"📊 Evaluation Complete! Results saved to: {out_file}")
    logger.info(f"   Outdoor Baseline Arrival Rate @ 0.5m: {summary_outdoor['arrival_rate']*100:.1f}%, Mean Final Dist: {summary_outdoor['mean_final_distance_m']:.2f}m, Shield Interv: {summary_outdoor['mean_intervention_rate']*100:.1f}%")
    logger.info(f"   Indoor Lossless  Arrival Rate @ 0.5m: {summary_indoor['arrival_rate']*100:.1f}%, Mean Final Dist: {summary_indoor['mean_final_distance_m']:.2f}m, Shield Interv: {summary_indoor['mean_intervention_rate']*100:.1f}%")
    logger.info(f"=======================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
