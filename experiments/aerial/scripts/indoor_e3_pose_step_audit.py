#!/usr/bin/env python3
"""E3.5 — per-step odom audit on clean_sg scored routes (east/south)."""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import yaml

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("e3_pose_step_audit")

from experiments.aerial.scripts.indoor_mainline_baseline_eval import (  # noqa: E402
    MainlineIndoorPolicyWrapper,
    build_segments,
)
from experiments.aerial.scripts.indoor_pose_diag_eval import (  # noqa: E402
    run_episode_with_audit,
)


def _parse_int_list(s: str) -> List[int]:
    return [int(x.strip()) for x in s.split(",") if x.strip()]


def _audit_row(rep: Dict[str, Any], *, route_idx: int, seed: int) -> Dict[str, Any]:
    audit = rep.get("estimator_audit") or {}
    per_step = audit.get("per_step") or []
    warmup = per_step[2:] if len(per_step) > 2 else per_step
    delta_errs = [float(s["delta_err_m"]) for s in warmup]
    return {
        "route_idx": route_idx,
        "seed": seed,
        "ok": bool(rep.get("ok")),
        "segment_name": rep.get("segment_name"),
        "route_name": rep.get("route_name"),
        "steps": rep.get("steps"),
        "d0_m": rep.get("d0_m"),
        "d_end_m_gt": rep.get("d_end_m_gt"),
        "d_end_m_hat": rep.get("d_end_m_hat"),
        "arrived_gt": rep.get("arrived_gt"),
        "arrived_hat": rep.get("arrived_hat"),
        "collided": rep.get("collided"),
        "mean_delta_err_m": audit.get("mean_delta_err_m"),
        "mean_delta_err_warmup_m": round(float(np.mean(delta_errs)), 5) if delta_errs else None,
        "max_delta_err_m": audit.get("max_delta_err_m"),
        "final_cum_drift_m": audit.get("final_cum_drift_m"),
        "max_cum_drift_m": audit.get("max_cum_drift_m"),
        "d_gap_hat_minus_gt": (
            round(float(rep["d_end_m_hat"]) - float(rep["d_end_m_gt"]), 4)
            if rep.get("d_end_m_hat") is not None and rep.get("d_end_m_gt") is not None
            else None
        ),
        "per_step": per_step,
    }


def _verdict(rows: List[Dict[str, Any]]) -> str:
    ok_rows = [r for r in rows if r.get("ok")]
    if not ok_rows:
        return "All runs failed — check renderer/spawn."
    mean_de = [r["mean_delta_err_warmup_m"] for r in ok_rows if r.get("mean_delta_err_warmup_m") is not None]
    drifts = [r["final_cum_drift_m"] for r in ok_rows if r.get("final_cum_drift_m") is not None]
    gt_only = sum(1 for r in ok_rows if r.get("arrived_gt") and not r.get("arrived_hat"))
    if mean_de and float(np.mean(mean_de)) > 0.15:
        return (
            f"Broken per-step integration: warmup mean Δerr={float(np.mean(mean_de)):.3f} m "
            f"(target <0.05–0.15). Fix pose_estimate before FT."
        )
    if drifts and float(np.median(drifts)) > 0.35:
        return (
            f"Accumulated drift median={float(np.median(drifts)):.2f} m on ~3 m segments "
            f"({gt_only}/{len(ok_rows)} arrived_gt-only). Estimator CE budget insufficient for @0.50 hat gate."
        )
    return "Step errors modest — investigate route-specific yaw/scale or policy stopping early."


def main() -> int:
    ap = argparse.ArgumentParser(description="E3.5 odom step audit")
    ap.add_argument("--config", default="configs/aerial_rl_indoor_shield_v3.yaml")
    ap.add_argument("--wm-ckpt", default="experiments/aerial/rl/artifacts/wm_ckpt_indoor_encode_e2i_b_20260901/wm_step_400.pt")
    ap.add_argument("--actor-ckpt", default="experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2i_e_20260901/v4_ac_latest.pt")
    ap.add_argument("--depth-ckpt", default="experiments/aerial/rl/artifacts/depth_ckpt_p45mid_s8j_20260825/depth_best_holdout_da3_ft_head.pt")
    ap.add_argument("--annotation", default="artifacts/building99_indoor_short_routes_clean_sg.json")
    ap.add_argument("--routes", default="1,2", help="0-based scored routes (default south+east)")
    ap.add_argument("--seeds", default="0,1,2")
    ap.add_argument("--segment-len-m", type=float, default=3.0)
    ap.add_argument("--max-steps", type=int, default=160)
    ap.add_argument("--success-dist", type=float, default=0.50)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

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

    route_indices = _parse_int_list(args.routes)
    seeds = _parse_int_list(args.seeds)
    ann_path = root / args.annotation
    routes = json.loads(ann_path.read_text(encoding="utf-8"))

    cfg_base = yaml.safe_load((root / args.config).read_text()) or {}
    reward_cfg = RewardConfig(**(cfg_base.get("reward") or {}))
    reward_cfg.success_dist_m = float(args.success_dist)

    wm_path = root / args.wm_ckpt
    actor_path = root / args.actor_ckpt
    depth_path = root / args.depth_ckpt
    dynamics, _ = load_torch_dynamics(
        cfg_base.get("world_model") or {}, str(wm_path), device=str(args.device),
        success_dist_m=float(args.success_dist),
    )
    actor_ac = LatentActorCritic.load_from_checkpoint(actor_path, device=str(args.device))
    base_policy = LatentActorDeployPolicy(dynamics, actor_ac, deterministic=True)
    depth_pred = DepthMinPredictor.from_checkpoint(depth_path, device=str(args.device)) if depth_path.is_file() else None
    limits = np.array([0.15, 0.08, 0.08, 0.10], dtype=np.float64)
    shield = build_indoor_shield(cfg_base, shield_off=False)
    logger.info("shield spec: %s", shield_spec_summary(cfg_base))
    planner = ImaginationPlanner(dynamics=dynamics, horizon=5, reward_cfg=reward_cfg, action_limits=limits, policy=actor_ac)

    runs: List[Dict[str, Any]] = []
    env = None

    for seed in seeds:
        cfg = yaml.safe_load((root / args.config).read_text()) or {}
        env_cfg = cfg.setdefault("env", {})
        env_cfg["backend"] = "airsim"
        env_cfg["step_hz"] = 5.0
        env_cfg["grab_depth"] = True
        env_cfg["health_check"] = False
        env_cfg["seed"] = seed
        env_cfg["spawn_retry_max"] = 3
        env_cfg["spawn_min_z_m"] = 1.4
        env_cfg["spawn_z_bump_m"] = 0.15
        env_cfg["spawn_settle_s"] = 0.35
        import os as _os
        env_cfg["camera"] = _os.environ.get("AIRSIM_CAMERA", env_cfg.get("camera", "0"))
        env_cfg["vehicle"] = _os.environ.get("AIRSIM_VEHICLE", env_cfg.get("vehicle", "drone_1"))
        if env is not None:
            try:
                env.close()
            except Exception:
                pass
        env = _build_env(env_cfg)

        for route_idx in route_indices:
            segments = build_segments(routes, [route_idx], target_len_m=args.segment_len_m)
            if not segments:
                logger.warning("skip route_idx=%d (no segment)", route_idx)
                continue
            seg = segments[0]
            pose_h = make_pose_estimator("odom_from_imu_rgb")
            policy_h = MainlineIndoorPolicyWrapper(
                base_policy, pose_h, max_dz=0.08, step_hz=5.0, assist="none",
                forbid_gt_world_pose_control=True,
            )
            policy_h.action_limits = limits
            logger.info("--- seed=%d route=%d %s d0=%.2fm ---", seed, route_idx, seg["segment_name"], seg["d0_m"])
            rep = run_episode_with_audit(
                env, policy_h, dynamics, depth_pred, shield, planner, seg,
                max_steps=args.max_steps, success_dist=args.success_dist, action_limits=limits,
            )
            row = _audit_row(rep, route_idx=route_idx, seed=seed)
            runs.append(row)
            logger.info(
                "seed=%d %s steps=%s drift=%s mean_de=%s arr_gt=%s arr_hat=%s",
                seed, seg["segment_name"], row.get("steps"), row.get("final_cum_drift_m"),
                row.get("mean_delta_err_warmup_m"), row.get("arrived_gt"), row.get("arrived_hat"),
            )

    if env is not None:
        try:
            env.close()
        except Exception:
            pass

    by_route: Dict[str, Any] = {}
    for ri in route_indices:
        sub = [r for r in runs if r.get("route_idx") == ri and r.get("ok")]
        if not sub:
            continue
        drifts = [r["final_cum_drift_m"] for r in sub if r.get("final_cum_drift_m") is not None]
        by_route[f"route_{ri}"] = {
            "n": len(sub),
            "mean_cum_drift_m": round(float(np.mean(drifts)), 4) if drifts else None,
            "mean_delta_err_warmup_m": round(
                float(np.mean([r["mean_delta_err_warmup_m"] for r in sub if r.get("mean_delta_err_warmup_m") is not None])), 5
            ) if sub else None,
            "arrived_gt": sum(1 for r in sub if r.get("arrived_gt")),
            "arrived_hat": sum(1 for r in sub if r.get("arrived_hat")),
        }

    payload = {
        "protocol": "e3_pose_step_audit",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "annotation": str(args.annotation),
        "routes": route_indices,
        "seeds": seeds,
        "segment_len_m": args.segment_len_m,
        "success_dist_m": args.success_dist,
        "by_route": by_route,
        "runs": runs,
        "verdict": _verdict(runs),
        "budget": {"max_final_drift_m": 0.35, "max_mean_delta_err_warmup_m": 0.15},
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    logger.info("Wrote %s verdict=%s", out_path, payload["verdict"])
    print(json.dumps({"verdict": payload["verdict"], "by_route": by_route}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
