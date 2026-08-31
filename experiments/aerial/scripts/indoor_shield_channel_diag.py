#!/usr/bin/env python3
"""E2i shield intervention-channel diagnostic (Building_99).

Per-step log: depth_min_pred / GT depth_min / zone / v_cap / action dx /
intervened / channels (three_zone|tau|p_coll|emergency_latch) / tau / p_coll.

Usage (125, Building_99 up):
  source experiments/aerial/scripts/env_4090.sh
  $AERIAL_PY experiments/aerial/scripts/indoor_shield_channel_diag.py \\
    --config configs/aerial_rl_indoor_shield_v3.yaml \\
    --actor-ckpt experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2h4_20260831/v4_ac_latest.pt \\
    --out artifacts/indoor_shield_channel_diag_v3_seed0_20260831.json
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import os
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import yaml

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("shield_channel_diag")


def _goal_dist(pos: np.ndarray, goal: np.ndarray) -> float:
    return float(np.linalg.norm(np.asarray(goal, dtype=np.float64).reshape(3) - np.asarray(pos, dtype=np.float64).reshape(3)))


def _gt_depth_min(obs: Any) -> Optional[float]:
    depth = getattr(obs, "depth", None)
    if depth is None:
        return None
    d = np.asarray(depth, dtype=np.float64)
    fin = np.isfinite(d) & (d > 0)
    return float(np.nanmin(d[fin])) if fin.any() else None


def run_diag_episode(
    env: Any,
    policy: Any,
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
    from experiments.aerial.rl.three_zone import planned_speed_m_s

    goal_pos = np.asarray(seg["pos"][1], dtype=np.float64)
    goal_yaw = float(seg["yaw"][1])
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

    steps: List[Dict[str, Any]] = []
    channel_counts: Counter = Counter()
    n_interv = 0

    for step_i in range(max_steps):
        action_pre = act_delta(policy, obs, seg["gpt_instruction"], action_limits)
        if planner is not None:
            if callable(getattr(planner, "set_goal", None)):
                planner.set_goal(goal_pos)
            action_pre = np.asarray(planner.plan(obs, action_pre), dtype=np.float64).reshape(4)
            action_pre = clip_body_delta(action_pre, action_limits)
        action_pre = policy.arbitrate(obs, action_pre)
        action_pre = np.asarray(action_pre, dtype=np.float64).reshape(4)

        d_pred = None
        if depth_pred is not None:
            d_pred = depth_pred.predict_min(obs)
            if d_pred is not None:
                obs.info["depth_min_pred"] = float(d_pred)
                d_pred = float(d_pred)

        d_gt = _gt_depth_min(obs)
        wm_out = dynamics.step(
            latent, action_pre,
            goal_rel=goal_rel_from_obs(obs),
            body_vel=body_vel_from_obs(obs),
        )
        tau = obs.info.get("tau_pred")
        p_coll = getattr(wm_out, "p_coll", None)
        if p_coll is not None:
            p_coll = float(p_coll)

        emergency_before = bool(getattr(shield, "_emergency_engaged", False))
        v_cap = planned_speed_m_s(float(d_pred), shield.zone) if d_pred is not None else None
        max_dx = (v_cap * float(shield.zone.dt_s)) if v_cap is not None else None

        action = action_pre.copy()
        intervened = False
        channels: List[str] = []
        if shield is not None:
            apply_fn = getattr(shield, "apply_action", None)
            if callable(apply_fn):
                action, intervened = apply_fn(action, obs, wm_out=wm_out, limits=action_limits)
            channels = list(obs.info.get("shield_channels") or [])
            if intervened and emergency_before:
                channels = list(dict.fromkeys(channels + ["emergency_latch"]))
            if intervened and not channels:
                # classify from state
                if getattr(shield, "_emergency_engaged", False):
                    channels = list(getattr(shield, "last_channels", ()) or ("emergency",))
                elif d_pred is not None and max_dx is not None and action_pre[0] > max_dx + 1e-6:
                    channels = ["three_zone"]

        if intervened:
            n_interv += 1
            for c in (channels or ["unknown"]):
                channel_counts[c] += 1

        row = {
            "t": step_i,
            "intervened": bool(intervened),
            "channels": channels,
            "depth_min_pred": None if d_pred is None else round(d_pred, 4),
            "depth_min_gt": None if d_gt is None else round(d_gt, 4),
            "pred_gt_gap": None if (d_pred is None or d_gt is None) else round(d_pred - d_gt, 4),
            "v_cap_m_s": None if v_cap is None else round(v_cap, 4),
            "max_dx": None if max_dx is None else round(max_dx, 4),
            "dx_pre": round(float(action_pre[0]), 4),
            "dx_post": round(float(action[0]), 4),
            "tau_pred": None if tau is None else round(float(tau), 4),
            "p_coll": None if p_coll is None else round(p_coll, 4),
            "emergency_engaged": bool(getattr(shield, "_emergency_engaged", False)),
            "zone_l1": float(shield.zone.l1_m),
            "d_goal_gt": round(_goal_dist(obs.position, goal_pos), 4),
        }
        steps.append(row)

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

        if _goal_dist(obs.position, goal_pos) <= success_dist:
            break
        if bool(getattr(obs, "collided", False)):
            break

    d_end = _goal_dist(obs.position, goal_pos)
    preds = [s["depth_min_pred"] for s in steps if s["depth_min_pred"] is not None]
    gts = [s["depth_min_gt"] for s in steps if s["depth_min_gt"] is not None]
    gaps = [s["pred_gt_gap"] for s in steps if s["pred_gt_gap"] is not None]
    frac_pred_lt_l1 = (
        float(np.mean([1.0 if p < float(shield.zone.l1_m) else 0.0 for p in preds])) if preds else None
    )
    return {
        "ok": True,
        "segment_name": seg["segment_name"],
        "steps_n": len(steps),
        "d_end_m_gt": round(d_end, 4),
        "arrived_gt": bool(d_end <= success_dist),
        "collided": bool(getattr(obs, "collided", False)),
        "intervention_rate": round(n_interv / max(len(steps), 1), 4),
        "channel_counts": dict(channel_counts),
        "depth_min_pred_median": round(float(np.median(preds)), 4) if preds else None,
        "depth_min_gt_median": round(float(np.median(gts)), 4) if gts else None,
        "pred_gt_gap_median": round(float(np.median(gaps)), 4) if gaps else None,
        "frac_pred_lt_l1": None if frac_pred_lt_l1 is None else round(frac_pred_lt_l1, 4),
        "steps": steps,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/aerial_rl_indoor_shield_v3.yaml")
    ap.add_argument("--wm-ckpt", default="experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt")
    ap.add_argument("--actor-ckpt", default="experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2h4_20260831/v4_ac_latest.pt")
    ap.add_argument("--depth-ckpt", default="experiments/aerial/rl/artifacts/depth_ckpt_p45mid_s8j_20260825/depth_best_holdout_da3_ft_head.pt")
    ap.add_argument("--annotation", default="artifacts/building99_indoor_short_routes.json")
    ap.add_argument("--routes", default="0,1,2,3,4,5,6,7")
    ap.add_argument("--segment-len-m", type=float, default=3.0)
    ap.add_argument("--max-steps", type=int, default=80)
    ap.add_argument("--success-dist", type=float, default=0.20)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--out", default="artifacts/indoor_shield_channel_diag_v3_seed0_20260831.json")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from experiments.aerial.rl.actor_critic import LatentActorCritic, LatentActorDeployPolicy
    from experiments.aerial.rl.depth_predictor import DepthMinPredictor
    from experiments.aerial.rl.planner import ImaginationPlanner
    from experiments.aerial.rl.pose_estimate import make_pose_estimator
    from experiments.aerial.rl.reward import RewardConfig
    from experiments.aerial.rl.train_rl import _build_env, load_torch_dynamics
    from experiments.aerial.scripts.indoor_mainline_baseline_eval import (
        MainlineIndoorPolicyWrapper,
        build_segments,
    )
    from experiments.aerial.scripts.indoor_shield_config import build_indoor_shield, shield_spec_summary

    ann = Path(args.annotation) if Path(args.annotation).is_absolute() else root / args.annotation
    routes = json.loads(ann.read_text(encoding="utf-8"))
    idxs = [int(x) for x in args.routes.split(",") if x.strip()]
    segments = build_segments(routes, idxs, target_len_m=args.segment_len_m)

    cfg = yaml.safe_load((root / args.config).read_text()) or {}
    cfg.setdefault("env", {})["backend"] = "airsim"
    cfg["env"]["step_hz"] = 5.0
    cfg["env"]["grab_depth"] = True
    cfg["env"]["health_check"] = False
    cfg["env"]["camera"] = os.environ.get("AIRSIM_CAMERA", cfg["env"].get("camera", "0"))
    cfg["env"]["vehicle"] = os.environ.get("AIRSIM_VEHICLE", cfg["env"].get("vehicle", "drone_1"))
    env = _build_env(cfg["env"])

    reward_cfg = RewardConfig(**(cfg.get("reward") or {}))
    reward_cfg.success_dist_m = float(args.success_dist)
    wm_path = root / args.wm_ckpt
    dynamics, _ = load_torch_dynamics(cfg.get("world_model") or {}, str(wm_path), device=str(args.device), success_dist_m=float(args.success_dist))
    actor_ac = LatentActorCritic.load_from_checkpoint(root / args.actor_ckpt, device=str(args.device))
    base_policy = LatentActorDeployPolicy(dynamics, actor_ac, deterministic=True)
    depth_path = root / args.depth_ckpt
    depth_pred = DepthMinPredictor.from_checkpoint(depth_path, device=str(args.device)) if depth_path.is_file() else None

    limits = np.array([0.15, 0.08, 0.08, 0.10], dtype=np.float64)
    shield = build_indoor_shield(cfg, shield_off=False)
    assert shield is not None
    planner = ImaginationPlanner(dynamics=dynamics, horizon=5, reward_cfg=reward_cfg, action_limits=limits, policy=actor_ac)
    policy = MainlineIndoorPolicyWrapper(
        base_policy, make_pose_estimator("gt_proxy"), max_dz=0.08, step_hz=5.0,
        assist="none", forbid_gt_world_pose_control=True,
    )
    policy.action_limits = limits

    logger.info("shield spec: %s", shield_spec_summary(cfg))
    reports = []
    for seg in segments:
        logger.info("--- %s ---", seg["segment_name"])
        rep = run_diag_episode(
            env, policy, dynamics, depth_pred, shield, planner, seg,
            max_steps=args.max_steps, success_dist=args.success_dist, action_limits=limits,
        )
        reports.append(rep)
        if rep.get("ok"):
            logger.info(
                "%s interv=%.2f channels=%s pred_med=%s gt_med=%s frac_pred<L1=%s d_end=%.2f",
                seg["segment_name"], rep["intervention_rate"], rep["channel_counts"],
                rep["depth_min_pred_median"], rep["depth_min_gt_median"],
                rep["frac_pred_lt_l1"], rep["d_end_m_gt"],
            )

    # aggregate
    tot_ch: Counter = Counter()
    tot_steps = 0
    tot_interv = 0
    pred_all: List[float] = []
    gt_all: List[float] = []
    for r in reports:
        if not r.get("ok"):
            continue
        tot_steps += int(r["steps_n"])
        tot_interv += int(round(r["intervention_rate"] * r["steps_n"]))
        for k, v in (r.get("channel_counts") or {}).items():
            tot_ch[k] += int(v)
        for s in r.get("steps") or []:
            if s.get("depth_min_pred") is not None:
                pred_all.append(float(s["depth_min_pred"]))
            if s.get("depth_min_gt") is not None:
                gt_all.append(float(s["depth_min_gt"]))

    l1 = float(shield.zone.l1_m)
    summary = {
        "protocol": "E2i_shield_channel_diag",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "config": str(args.config),
        "actor_ckpt": str(args.actor_ckpt),
        "shield_spec": shield_spec_summary(cfg),
        "n_routes": len(reports),
        "total_steps": tot_steps,
        "intervention_rate": round(tot_interv / max(tot_steps, 1), 4),
        "channel_counts": dict(tot_ch),
        "channel_frac_of_interventions": {
            k: round(v / max(tot_interv, 1), 4) for k, v in tot_ch.items()
        },
        "depth_min_pred_median": round(float(np.median(pred_all)), 4) if pred_all else None,
        "depth_min_gt_median": round(float(np.median(gt_all)), 4) if gt_all else None,
        "frac_pred_lt_l1": round(float(np.mean([p < l1 for p in pred_all])), 4) if pred_all else None,
        "frac_gt_lt_l1": round(float(np.mean([g < l1 for g in gt_all])), 4) if gt_all else None,
        "episodes": [{k: v for k, v in r.items() if k != "steps"} for r in reports],
        "episodes_with_steps": reports,
    }
    # diagnosis one-liner
    dominant = tot_ch.most_common(1)[0][0] if tot_ch else None
    if summary["frac_pred_lt_l1"] is not None and summary["frac_gt_lt_l1"] is not None:
        if summary["frac_pred_lt_l1"] > 0.7 and summary["frac_gt_lt_l1"] < 0.3:
            verdict = "depth_head_bias_low: D̂ << GT → three_zone always engaged"
        elif dominant in ("tau", "p_coll", "emergency_latch"):
            verdict = f"emergency_dominant:{dominant}"
        elif dominant == "three_zone":
            verdict = "three_zone_dominant: zone/L1 still too aggressive OR open-space D̂ low"
        else:
            verdict = f"mixed_or_unknown dominant={dominant}"
    else:
        verdict = f"incomplete_depth dominant={dominant}"
    summary["verdict"] = verdict

    out = Path(args.out) if Path(args.out).is_absolute() else root / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    # write compact summary without full steps first for readability, then full
    compact = {k: v for k, v in summary.items() if k != "episodes_with_steps"}
    out.write_text(json.dumps(compact, indent=2), encoding="utf-8")
    full = out.with_name(out.stem + "_full.json")
    full.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    logger.info("VERDICT: %s", verdict)
    logger.info("Wrote %s and %s", out, full)
    print(json.dumps(compact, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
