#!/usr/bin/env python3
"""Indoor Two-Phase Policy Evaluation (WAM Cruising + Near-Field IBVS Visual Servoing).

Evaluates high-precision indoor positioning at 0.15m ~ 0.20m (15cm ~ 20cm) arrival threshold.

Compares:
  1. Single-Phase WAM + Altitude Lock (Baseline from Step 2)
  2. Two-Phase Policy (Far: WAM Cruise -> Near <= 1.2m: Visual Servoing + P-Tapering)

Usage on 125:
  source experiments/aerial/scripts/env_4090.sh
  $AERIAL_PY experiments/aerial/scripts/indoor_two_phase_eval.py \
    --config configs/aerial_rl_indoor_lossless.yaml \
    --episodes 6 \
    --success-dist 0.20 \
    --out artifacts/indoor_two_phase_eval_20260828.json
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
logger = logging.getLogger("indoor_two_phase")


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
    segments = []
    priority_indices = [8, 9, 6, 12, 13, 17, 4, 19, 0, 2]

    for idx in priority_indices:
        if idx >= len(routes) or len(segments) >= max_routes:
            continue
        r = routes[idx]
        pos_list = np.asarray(r["pos"], dtype=np.float64)
        yaw_list = np.asarray(r["yaw"], dtype=np.float64)

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
        goal_yaw = float(yaw_list[end_idx])
        d0 = _goal_dist(seg_start, seg_goal)

        segments.append({
            "source_route_idx": idx,
            "segment_name": f"MicroRoute_{len(segments)+1:02d}_(from_Route_{idx+1:02d})",
            "pos": [seg_start.tolist(), seg_goal.tolist()],
            "yaw": [seg_yaw, goal_yaw],
            "d0_m": round(d0, 3),
            "start_z": round(float(seg_start[2]), 2),
            "gpt_instruction": r.get("gpt_instruction", "")[:80] + " (micro-space slice)",
        })

    return segments


class TwoPhasePolicyWrapper:
    """Combines WAM policy (cruising) with Near-Field Visual Servoing (IBVS)."""

    def __init__(
        self,
        base_policy: Any,
        enable_visual_servo: bool = True,
        max_dz: float = 0.08,
        step_hz: float = 5.0,
        d_switch: float = 1.2,
    ):
        self.base_policy = base_policy
        self.enable_visual_servo = enable_visual_servo
        self.step_hz = step_hz
        from experiments.aerial.rl.indoor_controller import (
            AltitudeLockController,
            TwoPhaseIndoorController,
            VisualServoingController,
        )
        self.two_phase_ctrl = TwoPhaseIndoorController(
            d_switch=d_switch,
            alt_ctrl=AltitudeLockController(kp=1.5, kd=0.6, max_dz=max_dz),
            ibvs_ctrl=VisualServoingController(kp_xy=0.6, kp_yaw=0.8, d_switch=d_switch),
        )
        self.goal_pos: Optional[np.ndarray] = None
        self.goal_yaw: float = 0.0
        self.last_phase: str = "INIT"
        self.action_limits = np.array([0.15, 0.08, 0.08, 0.10], dtype=np.float64)

    def reset(self, initial_obs: Optional[Any] = None, target_pos: Optional[np.ndarray] = None, target_yaw: float = 0.0):
        if hasattr(self.base_policy, "reset"):
            self.base_policy.reset()
        if target_pos is not None:
            self.goal_pos = target_pos
        if target_yaw != 0.0:
            self.goal_yaw = target_yaw
        from experiments.aerial.rl.env.obs import Observation
        if isinstance(initial_obs, Observation):
            self.two_phase_ctrl.reset(initial_obs, self.goal_pos)

    def act(self, view: Any) -> np.ndarray:
        raw_wam = self.base_policy.act(view)
        from experiments.aerial.rl.env.obs import Observation

        cur_state = np.array([view.proprio[0], view.proprio[1], view.proprio[2], 0, 0, 0, view.proprio[3]], dtype=np.float32)
        full_obs = Observation(rgb=view.rgb, state=cur_state, t=view.t)

        if not self.enable_visual_servo or self.goal_pos is None:
            # Single-Phase: WAM + Altitude Lock only
            target_z = float(self.goal_pos[2]) if self.goal_pos is not None else float(view.proprio[2])
            act = raw_wam.copy()
            act[2] = self.two_phase_ctrl.alt_ctrl.step(float(view.proprio[2]), dt=1.0 / self.step_hz)
            self.last_phase = "SINGLE_PHASE_WAM"
            return np.clip(act, -self.action_limits, self.action_limits)

        # Two-Phase Arbitrator
        final_action, phase, dist = self.two_phase_ctrl.arbitrate_action(
            obs=full_obs,
            wam_action=raw_wam,
            goal_pos=self.goal_pos,
            goal_yaw=self.goal_yaw,
            action_limits=self.action_limits,
            step_hz=self.step_hz,
        )
        self.last_phase = phase
        return final_action


def run_evaluation_mode(
    mode_name: str,
    segments: List[Dict[str, Any]],
    env: Any,
    policy: Any,
    dynamics: Any,
    depth_pred: Any,
    shield: Any,
    planner: Any,
    reward_cfg: Any,
    action_limits: np.ndarray,
    enable_visual_servo: bool = True,
    max_steps: int = 100,
    success_dist: float = 0.20,
    step_hz: float = 5.0,
) -> Dict[str, Any]:
    from experiments.aerial.rl.buffer import ReplayBuffer
    from experiments.aerial.rl.collector import RolloutCollector

    wrapped_policy = TwoPhasePolicyWrapper(
        base_policy=policy,
        enable_visual_servo=enable_visual_servo,
        max_dz=action_limits[2],
        step_hz=step_hz,
        d_switch=1.2,
    )
    wrapped_policy.action_limits = action_limits

    buf = ReplayBuffer(capacity_episodes=4, seed=0)
    collector = RolloutCollector(
        env=env,
        policy=wrapped_policy,
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
    logger.info(f"🚀 Running Evaluation: [{mode_name}] (Near-Field IBVS: {enable_visual_servo})")
    logger.info(f"   Target Success Radius: {success_dist:.2f} m (0.xm precision gate)")
    logger.info(f"   Action Limits: dx={action_limits[0]:.2f}m, dy={action_limits[1]:.2f}m, dz={action_limits[2]:.2f}m, dyaw={action_limits[3]:.2f}rad")
    logger.info(f"=======================================================")

    results = []
    n_arrived = 0
    n_severe_coll = 0
    progress_ratios = []
    intervention_rates = []
    final_distances = []
    min_distances = []
    z_variations = []

    for seg in segments:
        ep_dict = {
            "pos": seg["pos"],
            "yaw": seg["yaw"],
            "gpt_instruction": seg["gpt_instruction"],
        }
        goal_pos = np.asarray(seg["pos"][1], dtype=np.float64)
        goal_yaw = float(seg["yaw"][1])
        d0 = seg["d0_m"]

        # Reset wrapper with goal info
        if hasattr(wrapped_policy, "reset"):
            wrapped_policy.reset(None, target_pos=goal_pos, target_yaw=goal_yaw)
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
        min_distances.append(float(d_min))

        n_interv = sum(1 for tr in ep_trans if tr.info.get("intervention", False))
        interv_rate = n_interv / len(ep_trans)
        intervention_rates.append(float(interv_rate))

        # Vertical tracking error
        z_errs = [abs(tr.obs.position[2] - goal_pos[2]) for tr in ep_trans]
        mean_z_err = float(np.mean(z_errs)) if z_errs else 0.0
        z_variations.append(mean_z_err)

        logger.info(
            f"[{mode_name}] {seg['segment_name']} | steps={len(ep_trans):3d} | "
            f"d0={d0:4.1f}m -> d_end={d_end:4.3f}m (min={d_min:4.3f}m) | "
            f"z_err={mean_z_err:4.3f}m | prog={prog_ratio*100:+5.1f}% | arrived @ {success_dist:.2f}m={arrived!s:5s} | shield={interv_rate*100:4.1f}%"
        )

        results.append({
            "segment_name": seg["segment_name"],
            "steps": len(ep_trans),
            "d0_m": d0,
            "d_end_m": round(d_end, 4),
            "d_min_m": round(d_min, 4),
            "mean_z_error_m": round(mean_z_err, 4),
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
        "arrival_rate_strict_20cm": round(n_arrived / max(n_scored, 1), 4),
        "mean_progress_ratio": round(float(np.mean(progress_ratios)), 4) if progress_ratios else 0.0,
        "mean_final_distance_m": round(float(np.mean(final_distances)), 4) if final_distances else 0.0,
        "mean_min_distance_m": round(float(np.mean(min_distances)), 4) if min_distances else 0.0,
        "mean_z_error_m": round(float(np.mean(z_variations)), 4) if z_variations else 0.0,
        "mean_intervention_rate": round(float(np.mean(intervention_rates)), 4) if intervention_rates else 0.0,
        "severe_collision_rate": round(n_severe_coll / max(n_scored, 1), 4),
        "episodes": results,
    }
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Indoor Two-Phase High Precision Evaluation")
    parser.add_argument("--config", default="configs/aerial_rl_indoor_lossless.yaml")
    parser.add_argument("--wm-ckpt", default="experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt")
    parser.add_argument("--actor-ckpt", default="experiments/aerial/rl/artifacts/v4_ac_ckpt_step_e_20260828/v4_ac_latest.pt")
    parser.add_argument("--depth-ckpt", default="experiments/aerial/rl/artifacts/depth_ckpt_p45mid_s8j_20260825/depth_best_holdout_da3_ft_head.pt")
    parser.add_argument("--annotation", default="artifacts/seen_airsim16_m1a20.json")
    parser.add_argument("--episodes", type=int, default=6)
    parser.add_argument("--segment-len-m", type=float, default=10.0)
    parser.add_argument("--max-steps", type=int, default=100)
    parser.add_argument("--success-dist", type=float, default=0.20, help="Strict 0.2m (20cm) arrival threshold")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--out", default="artifacts/indoor_two_phase_eval_20260828.json")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from experiments.aerial.rl.actor_critic import LatentActorCritic, LatentActorDeployPolicy
    from experiments.aerial.rl.depth_predictor import DepthMinPredictor
    from experiments.aerial.rl.planner import ImaginationPlanner
    from experiments.aerial.rl.reward import RewardConfig
    from experiments.aerial.rl.safety import ThreeZoneSpeedShield
    from experiments.aerial.rl.three_zone import ThreeZoneSpec
    from experiments.aerial.rl.train_rl import _build_env, load_torch_dynamics

    ann_path = (root / args.annotation).resolve() if not Path(args.annotation).is_absolute() else Path(args.annotation)
    with ann_path.open("r", encoding="utf-8") as f:
        routes = json.load(f)

    segments = build_micro_test_segments(routes, target_len_m=args.segment_len_m, max_routes=args.episodes)

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

    # 1. Mode A: Single-Phase WAM + Altitude Lock (Baseline from Step 2)
    summary_single_phase = run_evaluation_mode(
        mode_name="Single_Phase_WAM_AltitudeLock",
        segments=segments,
        env=env,
        policy=policy,
        dynamics=dynamics,
        depth_pred=depth_pred,
        shield=indoor_shield,
        planner=indoor_planner,
        reward_cfg=reward_cfg,
        action_limits=indoor_limits,
        enable_visual_servo=False,
        max_steps=args.max_steps,
        success_dist=args.success_dist,
    )

    # 2. Mode B: Two-Phase Policy (WAM Cruising -> Near-Field IBVS + P-Tapering)
    summary_two_phase = run_evaluation_mode(
        mode_name="Two_Phase_WAM_plus_IBVS_Servoing",
        segments=segments,
        env=env,
        policy=policy,
        dynamics=dynamics,
        depth_pred=depth_pred,
        shield=indoor_shield,
        planner=indoor_planner,
        reward_cfg=reward_cfg,
        action_limits=indoor_limits,
        enable_visual_servo=True,
        max_steps=args.max_steps,
        success_dist=args.success_dist,
    )

    out_payload = {
        "evaluation_title": "Indoor Two-Phase High Precision Evaluation (0.2m Strict Gate)",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "target_precision_m": args.success_dist,
        "segment_count": len(segments),
        "comparison": {
            "single_phase_baseline": summary_single_phase,
            "two_phase_ibvs": summary_two_phase,
        },
    }

    out_file = (root / args.out).resolve() if not Path(args.out).is_absolute() else Path(args.out)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with out_file.open("w", encoding="utf-8") as f:
        json.dump(out_payload, f, indent=2)

    logger.info(f"\n=======================================================")
    logger.info(f"📊 Two-Phase High Precision Evaluation Complete!")
    logger.info(f"   Single-Phase Strict Arrival @ {args.success_dist}m: {summary_single_phase['arrival_rate_strict_20cm']*100:.1f}%, Mean Final Dist: {summary_single_phase['mean_final_distance_m']:.3f}m, Min Dist: {summary_single_phase['mean_min_distance_m']:.3f}m")
    logger.info(f"   Two-Phase    Strict Arrival @ {args.success_dist}m: {summary_two_phase['arrival_rate_strict_20cm']*100:.1f}%, Mean Final Dist: {summary_two_phase['mean_final_distance_m']:.3f}m, Min Dist: {summary_two_phase['mean_min_distance_m']:.3f}m")
    logger.info(f"=======================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
