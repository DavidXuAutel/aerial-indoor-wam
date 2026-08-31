#!/usr/bin/env python3
"""Indoor mainline baseline eval (RUNBOOK_indoor_0xm phase B).

Contractual protocol:
  * pose_source=odom_from_imu_rgb (default) — goal_rel from p_hat, not silent GT
  * assist=none, forbid_gt_world_pose_control=True
  * Routes 07/10/13/14 (~10 m micro segments)

Usage on 125:
  source experiments/aerial/scripts/env_4090.sh
  $AERIAL_PY experiments/aerial/scripts/indoor_mainline_baseline_eval.py \\
    --out artifacts/indoor_mainline_baseline_20260829.json
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import yaml

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("indoor_mainline_baseline")

# 0-based route indices for Route 07, 10, 13, 14
DEFAULT_ROUTE_INDICES = [6, 9, 12, 13]


def _goal_dist(pos: np.ndarray, goal: np.ndarray) -> float:
    return float(np.linalg.norm(np.asarray(goal, dtype=np.float64).reshape(3) - np.asarray(pos, dtype=np.float64).reshape(3)))


def build_segments(
    routes: List[Dict[str, Any]],
    route_indices: List[int],
    target_len_m: float = 10.0,
) -> List[Dict[str, Any]]:
    segments: List[Dict[str, Any]] = []
    for idx in route_indices:
        if idx >= len(routes):
            logger.warning("route index %d out of range (n=%d)", idx, len(routes))
            continue
        r = routes[idx]
        pos_list = np.asarray(r["pos"], dtype=np.float64)
        yaw_list = np.asarray(r["yaw"], dtype=np.float64)
        end_idx = 1
        cum = 0.0
        for k in range(len(pos_list) - 1):
            cum += float(np.linalg.norm(pos_list[k + 1] - pos_list[k]))
            end_idx = k + 1
            if cum >= target_len_m:
                break
        seg_start = pos_list[0].copy()
        seg_goal = pos_list[end_idx].copy()
        segments.append({
            "source_route_idx": idx,
            "route_name": f"Route_{idx + 1:02d}",
            "segment_name": f"Mainline_Route_{idx + 1:02d}",
            "pos": [seg_start.tolist(), seg_goal.tolist()],
            "yaw": [float(yaw_list[0]), float(yaw_list[end_idx])],
            "d0_m": round(_goal_dist(seg_start, seg_goal), 3),
            "gpt_instruction": (r.get("gpt_instruction", "")[:100] + " (mainline baseline)"),
        })
    return segments


class MainlineIndoorPolicyWrapper:
    """WAM + altitude lock; assist=none; pose estimator drives goal_rel."""

    def __init__(
        self,
        base_policy: Any,
        pose_estimator: Any,
        *,
        max_dz: float = 0.08,
        step_hz: float = 5.0,
        assist: str = "none",
        forbid_gt_world_pose_control: bool = True,
    ):
        self.base_policy = base_policy
        self.pose_estimator = pose_estimator
        self.step_hz = step_hz
        self.assist = assist
        self.forbid_gt_world_pose_control = forbid_gt_world_pose_control
        from experiments.aerial.rl.indoor_controller import (
            AltitudeLockController,
            TwoPhaseIndoorController,
            VisualServoingController,
        )

        self.two_phase_ctrl = TwoPhaseIndoorController(
            d_switch=1.2,
            alt_ctrl=AltitudeLockController(kp=1.5, kd=0.6, max_dz=max_dz),
            ibvs_ctrl=VisualServoingController(kp_xy=0.6, kp_yaw=0.8, d_switch=1.2),
        )
        self.goal_pos: Optional[np.ndarray] = None
        self.goal_yaw: float = 0.0
        self.last_phase = "INIT"
        self.action_limits = np.array([0.15, 0.08, 0.08, 0.10], dtype=np.float64)
        self.used_gt_world_pose_for_control = False
        self.pose_source = pose_estimator.pose_source
        self.altitude_source = "baro"
        self._last_action: Optional[np.ndarray] = None

    def reset(self, obs: Any, target_pos: Optional[np.ndarray] = None, target_yaw: float = 0.0):
        if hasattr(self.base_policy, "reset"):
            self.base_policy.reset()
        if target_pos is not None:
            self.goal_pos = np.asarray(target_pos, dtype=np.float64)
        self.goal_yaw = float(target_yaw)
        self.used_gt_world_pose_for_control = False
        self._last_action = None
        self.two_phase_ctrl.reset(obs, self.goal_pos)
        pe = self.pose_estimator.reset(obs)
        self._stamp_obs(obs, pe)

    def _stamp_obs(self, obs: Any, pe: Any) -> None:
        from experiments.aerial.rl.pose_estimate import agl_stub_from_depth, stamp_pose_on_obs

        agl = agl_stub_from_depth(obs)
        if agl is not None:
            obs.agl_m = agl
            if obs.info is None:
                obs.info = {}
            obs.info["agl_stub"] = True
            obs.info["agl_origin_z"] = float(obs.position[2]) - agl
        stamp_pose_on_obs(obs, pe)
        self.pose_source = pe.pose_source
        self.altitude_source = pe.altitude_source
        if self.goal_pos is not None:
            obs.info["goal"] = self.goal_pos.tolist()

    def act(self, view: Any) -> np.ndarray:
        return self.base_policy.act(view)

    def post_step(self, obs: Any, action: np.ndarray) -> None:
        pe = self.pose_estimator.update(obs, action=action, dt=1.0 / self.step_hz)
        self._stamp_obs(obs, pe)
        self._last_action = action.copy()

    def arbitrate(self, obs: Any, wam_action: np.ndarray) -> np.ndarray:
        assert self.goal_pos is not None
        final_action, phase, _dist, used_gt = self.two_phase_ctrl.arbitrate_action(
            obs=obs,
            wam_action=wam_action,
            goal_pos=self.goal_pos,
            goal_yaw=self.goal_yaw,
            action_limits=self.action_limits,
            step_hz=self.step_hz,
            assist=self.assist,
            forbid_gt_world_pose_control=self.forbid_gt_world_pose_control,
        )
        self.last_phase = phase
        if used_gt:
            self.used_gt_world_pose_for_control = True
        return final_action


def run_episode(
    env: Any,
    policy: MainlineIndoorPolicyWrapper,
    dynamics: Any,
    depth_pred: Any,
    shield: Any,
    planner: Any,
    seg: Dict[str, Any],
    *,
    max_steps: int,
    success_dist: float,
    action_limits: np.ndarray,
) -> Dict[str, Any]:
    from experiments.aerial.rl.collector import act_delta, clip_body_delta
    from experiments.aerial.rl.goal_features import body_vel_from_obs, goal_rel_from_obs
    from experiments.aerial.rl.indoor_controller import controller_attribution_from_counts, mainline_sensors_used
    from experiments.aerial.rl.pose_estimate import mainline_report_fields

    goal_pos = np.asarray(seg["pos"][1], dtype=np.float64)
    goal_yaw = float(seg["yaw"][1])
    d0 = float(seg["d0_m"])

    obs = env.reset({"pos": seg["pos"], "yaw": seg["yaw"], "gpt_instruction": seg["gpt_instruction"]})
    if obs is None or getattr(obs, "rgb", None) is None:
        return {"ok": False, "segment_name": seg["segment_name"], "reason": "reset_failed"}
    if float(np.asarray(obs.rgb).mean()) < 1.0:
        return {"ok": False, "segment_name": seg["segment_name"], "reason": "black_rgb"}

    obs.info["goal"] = goal_pos.tolist()
    policy.reset(obs, target_pos=goal_pos, target_yaw=goal_yaw)
    if hasattr(shield, "reset"):
        shield.reset()
    latent = np.asarray(dynamics.encode(obs), dtype=np.float64)

    n_interv = 0
    for step_i in range(max_steps):
        action = act_delta(policy, obs, seg["gpt_instruction"], action_limits)
        if planner is not None:
            if callable(getattr(planner, "set_goal", None)):
                planner.set_goal(goal_pos)
            action = np.asarray(planner.plan(obs, action), dtype=np.float64).reshape(4)
            action = clip_body_delta(action, action_limits)
        action = policy.arbitrate(obs, action)

        if depth_pred is not None:
            d_min = depth_pred.predict_min(obs)
            if d_min is not None:
                obs.info["depth_min_pred"] = float(d_min)

        wm_out = dynamics.step(
            latent, action,
            goal_rel=goal_rel_from_obs(obs),
            body_vel=body_vel_from_obs(obs),
        )
        intervened = False
        if shield is not None:
            apply_fn = getattr(shield, "apply_action", None)
            if callable(apply_fn):
                action, intervened = apply_fn(action, obs, wm_out=wm_out, limits=action_limits)
            elif shield.should_override(obs, wm_out=wm_out):
                action = clip_body_delta(shield.override_action(obs), action_limits)
                intervened = True
        if intervened:
            n_interv += 1

        next_obs, _info = env.step(action)
        next_obs.info["goal"] = goal_pos.tolist()
        policy.post_step(next_obs, action)
        out = dynamics.step(
            latent, action,
            goal_rel=goal_rel_from_obs(obs),
            body_vel=body_vel_from_obs(obs),
        )
        latent = np.asarray(out.z_next, dtype=np.float64)
        obs = next_obs

        d_hat = _goal_dist(obs.info["pose_estimate"]["p_hat"], goal_pos) if isinstance(obs.info.get("pose_estimate"), dict) else float("nan")
        d_gt = _goal_dist(obs.position, goal_pos)
        if d_gt <= success_dist:
            break
        if bool(getattr(obs, "collided", False)):
            break

    d_end_gt = _goal_dist(obs.position, goal_pos)
    pe_raw = obs.info.get("pose_estimate", {})
    d_end_hat = _goal_dist(np.asarray(pe_raw.get("p_hat", obs.position)), goal_pos) if pe_raw else d_end_gt
    arrived_gt = d_end_gt <= success_dist
    arrived_hat = d_end_hat <= success_dist

    report = {
        "ok": True,
        "segment_name": seg["segment_name"],
        "route_name": seg["route_name"],
        "source_route_idx": seg["source_route_idx"],
        "steps": step_i + 1,
        "d0_m": d0,
        "d_end_m_gt": round(d_end_gt, 4),
        "d_end_m_hat": round(d_end_hat, 4),
        "arrived_gt": bool(arrived_gt),
        "arrived_hat": bool(arrived_hat),
        "arrived": bool(arrived_hat),
        "collided": bool(getattr(obs, "collided", False)),
        "intervention_rate": round(n_interv / max(step_i + 1, 1), 4),
        **mainline_report_fields(
            pose_source=policy.pose_source,
            goal_rel_pose_source=str(obs.info.get("goal_rel_pose_source", policy.pose_source)),
            controller_attribution=controller_attribution_from_counts(
                assist=policy.assist,
                wam_steps=policy.two_phase_ctrl.wam_steps,
                gt_pd_steps=policy.two_phase_ctrl.gt_pd_steps,
            ),
            used_gt_world_pose_for_control=bool(policy.used_gt_world_pose_for_control),
            sensors_used=mainline_sensors_used(depth_shield=depth_pred is not None, pose_source=policy.pose_source),
            altitude_source=policy.altitude_source,
        ),
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Indoor mainline baseline (phase B)")
    parser.add_argument("--config", default="configs/aerial_rl_indoor_lossless.yaml")
    parser.add_argument("--wm-ckpt", default="experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt")
    parser.add_argument("--actor-ckpt", default="experiments/aerial/rl/artifacts/v4_ac_ckpt_step_e_20260828/v4_ac_latest.pt")
    parser.add_argument("--depth-ckpt", default="experiments/aerial/rl/artifacts/depth_ckpt_p45mid_s8j_20260825/depth_best_holdout_da3_ft_head.pt")
    parser.add_argument("--annotation", default="artifacts/seen_airsim16_m1a20.json")
    parser.add_argument("--routes", default="6,9,12,13", help="0-based route indices (Route 07/10/13/14)")
    parser.add_argument("--segment-len-m", type=float, default=10.0)
    parser.add_argument("--max-steps", type=int, default=120)
    parser.add_argument("--success-dist", type=float, default=0.20)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--pose-source", default="odom_from_imu_rgb", choices=["odom_from_imu_rgb", "gt_proxy", "vio_est"])
    parser.add_argument("--assist", choices=["none", "gt_pd"], default="none")
    parser.add_argument("--shield-off", action="store_true", help="disable ThreeZoneSpeedShield (diagnostic only)")
    parser.add_argument("--out", default="artifacts/indoor_mainline_baseline_20260829.json")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from experiments.aerial.rl.actor_critic import LatentActorCritic, LatentActorDeployPolicy
    from experiments.aerial.rl.depth_predictor import DepthMinPredictor
    from experiments.aerial.rl.planner import ImaginationPlanner
    from experiments.aerial.rl.pose_estimate import make_pose_estimator
    from experiments.aerial.rl.reward import RewardConfig
    from experiments.aerial.scripts.indoor_shield_config import build_indoor_shield, shield_spec_summary
    from experiments.aerial.rl.train_rl import _build_env, load_torch_dynamics

    route_indices = [int(x) for x in args.routes.split(",") if x.strip()]
    ann_path = Path(args.annotation) if Path(args.annotation).is_absolute() else root / args.annotation
    routes = json.loads(ann_path.read_text(encoding="utf-8"))
    segments = build_segments(routes, route_indices, target_len_m=args.segment_len_m)
    logger.info(
        "Mainline B: %d segments, pose_source=%s assist=%s shield=%s",
        len(segments), args.pose_source, args.assist, "off" if args.shield_off else "on",
    )

    cfg = yaml.safe_load((root / args.config).read_text()) or {}
    cfg.setdefault("env", {})["backend"] = "airsim"
    cfg["env"]["step_hz"] = 5.0
    cfg["env"]["grab_depth"] = True
    # Building_99 flat walls trip depth-span health gate; indoor eval disables it.
    cfg["env"]["health_check"] = False
    import os as _os
    cfg["env"]["camera"] = _os.environ.get("AIRSIM_CAMERA", cfg["env"].get("camera", "0"))
    cfg["env"]["vehicle"] = _os.environ.get("AIRSIM_VEHICLE", cfg["env"].get("vehicle", "drone_1"))
    env = _build_env(cfg["env"])

    reward_cfg = RewardConfig(**(cfg.get("reward") or {}))
    reward_cfg.success_dist_m = float(args.success_dist)

    wm_path = Path(args.wm_ckpt) if Path(args.wm_ckpt).is_absolute() else root / args.wm_ckpt
    dynamics, _ = load_torch_dynamics(cfg.get("world_model") or {}, str(wm_path), device=str(args.device), success_dist_m=float(args.success_dist))
    actor_path = Path(args.actor_ckpt) if Path(args.actor_ckpt).is_absolute() else root / args.actor_ckpt
    actor_ac = LatentActorCritic.load_from_checkpoint(actor_path, device=str(args.device))
    base_policy = LatentActorDeployPolicy(dynamics, actor_ac, deterministic=True)
    depth_path = Path(args.depth_ckpt) if Path(args.depth_ckpt).is_absolute() else root / args.depth_ckpt
    depth_pred = DepthMinPredictor.from_checkpoint(depth_path, device=str(args.device)) if depth_path.is_file() else None

    limits = np.array([0.15, 0.08, 0.08, 0.10], dtype=np.float64)
    shield = build_indoor_shield(cfg, shield_off=args.shield_off)
    if not args.shield_off:
        logger.info("shield spec: %s", shield_spec_summary(cfg))
    planner = ImaginationPlanner(dynamics=dynamics, horizon=5, reward_cfg=reward_cfg, action_limits=limits, policy=actor_ac)

    pose_est = make_pose_estimator(args.pose_source)
    policy = MainlineIndoorPolicyWrapper(
        base_policy, pose_est, max_dz=0.08, step_hz=5.0,
        assist=args.assist, forbid_gt_world_pose_control=True,
    )
    policy.action_limits = limits

    results = []
    for seg in segments:
        logger.info("--- %s d0=%.1fm ---", seg["segment_name"], seg["d0_m"])
        rep = run_episode(env, policy, dynamics, depth_pred, shield, planner, seg, max_steps=args.max_steps, success_dist=args.success_dist, action_limits=limits)
        results.append(rep)
        if rep.get("ok"):
            logger.info(
                "%s steps=%d d_end_hat=%.3f arrived=%s attr=%s pose=%s",
                seg["segment_name"], rep["steps"], rep["d_end_m_hat"], rep["arrived"],
                rep["controller_attribution"], rep["pose_source"],
            )
        else:
            logger.warning("%s FAILED: %s", seg["segment_name"], rep.get("reason"))

    n_ok = sum(1 for r in results if r.get("ok"))
    n_arr = sum(1 for r in results if r.get("arrived"))
    payload = {
        "evaluation_title": "Indoor Mainline Baseline (phase B · contract A0)",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "protocol": {
            "pose_source": args.pose_source,
            "assist": args.assist,
            "shield": "off" if args.shield_off else "on",
            "shield_spec": None if args.shield_off else shield_spec_summary(cfg),
            "config": str(args.config),
            "forbid_gt_world_pose_control": True,
            "success_dist_m": args.success_dist,
            "voided_baselines": [
                "artifacts/indoor_lossless_eval_20260828.json",
                "artifacts/indoor_odom_alt_eval_20260828.json",
                "artifacts/indoor_two_phase_eval_20260828.json",
            ],
        },
        "n_segments": len(results),
        "arrival_rate_hat": round(n_arr / max(n_ok, 1), 4),
        "mean_d_end_hat_m": round(float(np.mean([r["d_end_m_hat"] for r in results if r.get("ok")])), 4) if n_ok else None,
        "episodes": results,
    }

    out_path = Path(args.out) if Path(args.out).is_absolute() else root / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info("Wrote %s (arrival_rate_hat=%.1f%%)", out_path, 100 * payload["arrival_rate_hat"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
