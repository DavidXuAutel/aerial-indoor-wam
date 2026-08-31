#!/usr/bin/env python3
"""Indoor pose short-segment diagnostic (RUNBOOK phase A · blocks C FT).

Runs:
  1. Estimator step audit (||Δp_hat - Δp_gt|| per step on arm H)
  2. Three-arm short segment on Route 07 (~10–12 m):
       H — odom_from_imu_rgb (mainline, post-bugfix)
       G — gt_proxy (explicit upper bound; NOT mainline completion)
       N — optional noisy odom (sensitivity)

Usage on 125:
  source experiments/aerial/scripts/env_4090.sh
  $AERIAL_PY experiments/aerial/scripts/indoor_pose_diag_eval.py \\
    --out artifacts/indoor_pose_diag_20260829.json
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
logger = logging.getLogger("indoor_pose_diag")

# Reuse mainline baseline helpers
from experiments.aerial.scripts.indoor_mainline_baseline_eval import (  # noqa: E402
    MainlineIndoorPolicyWrapper,
    build_segments,
    run_episode,
    _goal_dist,
)


class NoisyOdomWrapper:
    """Wrap odom estimator: add Gaussian noise to integrated XY deltas (arm N)."""

    def __init__(self, inner: Any, *, sigma_m: float = 0.02):
        self._inner = inner
        self.sigma_m = float(sigma_m)
        self.pose_source = f"odom_noisy(sigma={sigma_m})"

    def reset(self, obs: Any) -> Any:
        return self._inner.reset(obs)

    def update(self, obs: Any, action: Optional[np.ndarray] = None, *, dt: float = 0.2) -> Any:
        pe = self._inner.update(obs, action=action, dt=dt)
        if self.sigma_m > 0:
            pe.p_hat[0] += float(np.random.randn()) * self.sigma_m
            pe.p_hat[1] += float(np.random.randn()) * self.sigma_m
        return pe


def run_episode_with_audit(
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
    """Like run_episode but records per-step Δp_hat vs Δp_gt for estimator audit."""
    from experiments.aerial.rl.collector import act_delta, clip_body_delta
    from experiments.aerial.rl.goal_features import body_vel_from_obs, goal_rel_from_obs

    goal_pos = np.asarray(seg["pos"][1], dtype=np.float64)
    goal_yaw = float(seg["yaw"][1])

    obs = env.reset({"pos": seg["pos"], "yaw": seg["yaw"], "gpt_instruction": seg["gpt_instruction"]})
    if obs is None or bool(getattr(obs, "collided", False)):
        return {"ok": False, "segment_name": seg["segment_name"], "reason": "spawn_collision"}

    obs.info["goal"] = goal_pos.tolist()
    policy.reset(obs, target_pos=goal_pos, target_yaw=goal_yaw)
    if hasattr(shield, "reset"):
        shield.reset()
    latent = np.asarray(dynamics.encode(obs), dtype=np.float64)

    prev_p_gt = obs.position.copy()
    prev_p_hat = np.asarray(policy.pose_estimator._p_hat, dtype=np.float64).copy()
    step_audit: List[Dict[str, Any]] = []

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
        if shield is not None:
            apply_fn = getattr(shield, "apply_action", None)
            if callable(apply_fn):
                action, _ = apply_fn(action, obs, wm_out=wm_out, limits=action_limits)
            elif shield.should_override(obs, wm_out=wm_out):
                action = clip_body_delta(shield.override_action(obs), action_limits)

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

        p_gt = obs.position.copy()
        p_hat = np.asarray(obs.info["pose_estimate"]["p_hat"], dtype=np.float64)
        d_p_gt = p_gt - prev_p_gt
        d_p_hat = p_hat - prev_p_hat
        delta_err = float(np.linalg.norm(d_p_hat - d_p_gt))
        cum_drift = float(np.linalg.norm(p_hat - p_gt))
        step_audit.append({
            "step": step_i + 1,
            "delta_err_m": round(delta_err, 5),
            "cum_drift_m": round(cum_drift, 5),
            "d_gt_m": round(float(np.linalg.norm(d_p_gt)), 5),
            "d_hat_m": round(float(np.linalg.norm(d_p_hat)), 5),
        })
        prev_p_gt = p_gt.copy()
        prev_p_hat = p_hat.copy()

        if _goal_dist(obs.position, goal_pos) <= success_dist:
            break
        if bool(getattr(obs, "collided", False)):
            break

    from experiments.aerial.rl.indoor_controller import controller_attribution_from_counts, mainline_sensors_used
    from experiments.aerial.rl.pose_estimate import mainline_report_fields

    d_end_gt = _goal_dist(obs.position, goal_pos)
    pe_raw = obs.info.get("pose_estimate", {})
    d_end_hat = _goal_dist(np.asarray(pe_raw.get("p_hat", obs.position)), goal_pos) if pe_raw else d_end_gt

    delta_errs = [s["delta_err_m"] for s in step_audit]
    cum_drifts = [s["cum_drift_m"] for s in step_audit]

    return {
        "ok": True,
        "segment_name": seg["segment_name"],
        "route_name": seg["route_name"],
        "source_route_idx": seg["source_route_idx"],
        "steps": len(step_audit),
        "d0_m": float(seg["d0_m"]),
        "d_end_m_gt": round(d_end_gt, 4),
        "d_end_m_hat": round(d_end_hat, 4),
        "arrived_gt": bool(d_end_gt <= success_dist),
        "arrived_hat": bool(d_end_hat <= success_dist),
        "collided": bool(getattr(obs, "collided", False)),
        "estimator_audit": {
            "n_steps": len(step_audit),
            "mean_delta_err_m": round(float(np.mean(delta_errs)), 5) if delta_errs else None,
            "max_delta_err_m": round(float(np.max(delta_errs)), 5) if delta_errs else None,
            "final_cum_drift_m": round(float(cum_drifts[-1]), 5) if cum_drifts else None,
            "max_cum_drift_m": round(float(np.max(cum_drifts)), 5) if cum_drifts else None,
            "per_step": step_audit,
        },
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


def _classify_estimator(
    audit: Dict[str, Any],
    arm_h: Dict[str, Any],
    arm_g: Dict[str, Any],
    *,
    success_dist: float,
) -> tuple[str, bool, str]:
    per_step = audit.get("per_step") or []
    warmup = per_step[2:] if len(per_step) > 2 else per_step
    delta_errs = [s["delta_err_m"] for s in warmup]
    mean_de = float(np.mean(delta_errs)) if delta_errs else float(audit.get("mean_delta_err_m") or 0.0)
    max_de = float(np.max(delta_errs)) if delta_errs else float(audit.get("max_delta_err_m") or 0.0)
    final_drift = float(audit.get("final_cum_drift_m") or 0.0)
    d0 = float(arm_h.get("d0_m") or 12.0)
    d_end_hat = float(arm_h.get("d_end_m_hat") or 999.0)
    d_end_gt = float(arm_h.get("d_end_m_gt") or 999.0)
    g_hat = float(arm_g.get("d_end_m_hat") or 999.0)
    g_gt = float(arm_g.get("d_end_m_gt") or 999.0)
    g_pose_ok = abs(g_hat - g_gt) < 0.05

    # Scale bug: sustained per-step error >> max body delta (~0.15 m); ignore spawn settling (steps 1–2)
    if mean_de > 0.25 or max_de > 1.5:
        return (
            "broken",
            False,
            f"Per-step delta error too large after warmup (mean={mean_de:.3f} m, max={max_de:.3f} m).",
        )

    hat_gt_gap = abs(d_end_hat - d_end_gt)
    drift_ratio = final_drift / max(d0, 1.0)
    if hat_gt_gap <= max(3.0, 0.5 * d0) and drift_ratio <= 0.5:
        status = "short_segment_ok"
        ready = True
        msg = (
            f"Odom usable on {d0:.0f} m segment (drift {final_drift:.2f} m, d_end gap {hat_gt_gap:.2f} m)."
        )
    else:
        status = "drifts_as_expected"
        ready = g_pose_ok and mean_de <= 0.15
        if g_pose_ok and not arm_g.get("arrived_gt"):
            msg = (
                f"B baseline d_end_hat≈700 m was spawn-anchor bug (fixed). "
                f"H DR drift {final_drift:.2f} m on {d0:.0f} m segment; "
                f"G (gt_proxy) confirms π gap d_end={g_gt:.1f} m is policy not pose."
            )
        else:
            msg = f"DR drift {final_drift:.2f} m on {d0:.0f} m segment; review before FT."

    return status, ready, msg


def main() -> int:
    parser = argparse.ArgumentParser(description="Indoor pose short-segment diagnostic")
    parser.add_argument("--config", default="configs/aerial_rl_indoor_lossless.yaml")
    parser.add_argument("--wm-ckpt", default="experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt")
    parser.add_argument("--actor-ckpt", default="experiments/aerial/rl/artifacts/v4_ac_ckpt_step_e_20260828/v4_ac_latest.pt")
    parser.add_argument("--depth-ckpt", default="experiments/aerial/rl/artifacts/depth_ckpt_p45mid_s8j_20260825/depth_best_holdout_da3_ft_head.pt")
    parser.add_argument("--annotation", default="artifacts/seen_airsim16_m1a20.json")
    parser.add_argument("--route-idx", type=int, default=6, help="0-based (6=Route07)")
    parser.add_argument("--segment-len-m", type=float, default=12.0)
    parser.add_argument("--max-steps", type=int, default=120)
    parser.add_argument("--success-dist", type=float, default=0.20)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--noise-sigma", type=float, default=0.02, help="Arm N Gaussian XY noise (m); 0=skip")
    parser.add_argument("--out", default="artifacts/indoor_pose_diag_20260829.json")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from experiments.aerial.rl.actor_critic import LatentActorCritic, LatentActorDeployPolicy
    from experiments.aerial.rl.depth_predictor import DepthMinPredictor
    from experiments.aerial.rl.planner import ImaginationPlanner
    from experiments.aerial.rl.pose_estimate import make_pose_estimator
    from experiments.aerial.rl.reward import RewardConfig
    from experiments.aerial.rl.safety import ThreeZoneSpeedShield
    from experiments.aerial.rl.three_zone import ThreeZoneSpec
    from experiments.aerial.rl.train_rl import _build_env, load_torch_dynamics

    ann_path = Path(args.annotation) if Path(args.annotation).is_absolute() else root / args.annotation
    routes = json.loads(ann_path.read_text(encoding="utf-8"))
    segments = build_segments(routes, [args.route_idx], target_len_m=args.segment_len_m)
    if not segments:
        logger.error("No segment built for route_idx=%d", args.route_idx)
        return 1
    seg = segments[0]
    logger.info("Pose diag: %s d0=%.1fm", seg["segment_name"], seg["d0_m"])

    cfg = yaml.safe_load((root / args.config).read_text()) or {}
    cfg.setdefault("env", {})["backend"] = "airsim"
    cfg["env"]["step_hz"] = 5.0
    cfg["env"]["grab_depth"] = True
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
    shield = ThreeZoneSpeedShield(
        zone=ThreeZoneSpec(l1_m=1.5, l2_m=0.8, l3_m=0.4, v1_m_s=0.6, v2_m_s=0.3, v_stop_m_s=0.05, v_cruise_m_s=1.0, dt_s=0.2),
        retreat_step_m=0.3, min_tau_s=0.5,
    )
    planner = ImaginationPlanner(dynamics=dynamics, horizon=5, reward_cfg=reward_cfg, action_limits=limits, policy=actor_ac)

    bugfix = {
        "applied": True,
        "file": "experiments/aerial/rl/pose_estimate.py",
        "issues": [
            {
                "component": "OdomFromImuRgbPoseEstimator.reset",
                "symptom": "d_end_hat≈700 m on B baseline (p_hat at origin, goals at AirSim world coords)",
                "fix": "Anchor p_hat and psi_hat at spawn; per-step updates integrate body deltas only.",
            },
            {
                "component": "GtProxyPoseEstimator",
                "symptom": "G arm d_end_hat inflated when AGL stub overwrote p_hat[2]",
                "fix": "gt_proxy uses full obs.position (GT) for all axes.",
            },
        ],
        "pre_fix_mean_d_end_hat_m_baseline_b": 702.5,
    }

    arms: Dict[str, Any] = {}

    # Arm H — odom (with step audit)
    pose_h = make_pose_estimator("odom_from_imu_rgb")
    policy_h = MainlineIndoorPolicyWrapper(base_policy, pose_h, max_dz=0.08, step_hz=5.0, assist="none", forbid_gt_world_pose_control=True)
    policy_h.action_limits = limits
    logger.info("--- Arm H (odom_from_imu_rgb) ---")
    rep_h = run_episode_with_audit(env, policy_h, dynamics, depth_pred, shield, planner, seg, max_steps=args.max_steps, success_dist=args.success_dist, action_limits=limits)
    arms["H_odom_from_imu_rgb"] = rep_h

    # Arm G — gt_proxy upper bound
    pose_g = make_pose_estimator("gt_proxy")
    policy_g = MainlineIndoorPolicyWrapper(base_policy, pose_g, max_dz=0.08, step_hz=5.0, assist="none", forbid_gt_world_pose_control=True)
    policy_g.action_limits = limits
    logger.info("--- Arm G (gt_proxy · explicit upper bound) ---")
    rep_g = run_episode(env, policy_g, dynamics, depth_pred, shield, planner, seg, max_steps=args.max_steps, success_dist=args.success_dist, action_limits=limits)
    arms["G_gt_proxy"] = rep_g

    # Arm N — noisy odom (optional)
    if args.noise_sigma > 0:
        pose_n = NoisyOdomWrapper(make_pose_estimator("odom_from_imu_rgb"), sigma_m=args.noise_sigma)
        policy_n = MainlineIndoorPolicyWrapper(base_policy, pose_n, max_dz=0.08, step_hz=5.0, assist="none", forbid_gt_world_pose_control=True)
        policy_n.action_limits = limits
        logger.info("--- Arm N (noisy odom sigma=%.3f) ---", args.noise_sigma)
        rep_n = run_episode(env, policy_n, dynamics, depth_pred, shield, planner, seg, max_steps=args.max_steps, success_dist=args.success_dist, action_limits=limits)
        arms["N_odom_noisy"] = rep_n

    audit = rep_h.get("estimator_audit", {}) if rep_h.get("ok") else {}
    est_status, ready_ft, conclusion = _classify_estimator(audit, rep_h, rep_g, success_dist=args.success_dist)

    payload = {
        "evaluation_title": "Indoor Pose Short-Segment Diagnostic (blocks C FT)",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "workspace": str(root),
        "protocol": {
            "segment": seg["segment_name"],
            "route_idx_0based": args.route_idx,
            "segment_len_m_target": args.segment_len_m,
            "assist": "none",
            "forbid_gt_world_pose_control": True,
            "success_dist_m": args.success_dist,
        },
        "bugfix": bugfix,
        "estimator_audit_summary": {
            k: audit.get(k) for k in (
                "n_steps", "mean_delta_err_m", "max_delta_err_m",
                "final_cum_drift_m", "max_cum_drift_m",
            )
        },
        "arms": arms,
        "estimator_status": est_status,
        "ready_for_ft_signoff": ready_ft,
        "conclusion": conclusion,
    }

    out_path = Path(args.out) if Path(args.out).is_absolute() else root / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info("Wrote %s estimator_status=%s ready_for_ft=%s", out_path, est_status, ready_ft)
    return 0


if __name__ == "__main__":
    sys.exit(main())
