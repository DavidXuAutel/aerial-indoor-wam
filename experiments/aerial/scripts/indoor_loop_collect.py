#!/usr/bin/env python3
"""Indoor mainline closed-loop collection (RUNBOOK §8.1 E1).

Contract:
  * WAM π + depth shield (ON); assist=none
  * pose_source explicit (default gt_proxy for E1)
  * Short segments 8–15 m; full route distribution
  * Writes NPZ episodes + manifest for offline FT (E2)

Usage (125):
  source experiments/aerial/scripts/env_4090.sh
  $AERIAL_PY experiments/aerial/scripts/indoor_loop_collect.py \\
    --pose-source gt_proxy --episodes 30 \\
    --out experiments/aerial/rl/artifacts/dataset_indoor_loop_e1_gtproxy_20260829

Dry-run (mock, no renderer):
  $AERIAL_PY experiments/aerial/scripts/indoor_loop_collect.py \\
    --backend mock --episodes 3 --out /tmp/indoor_loop_mock
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import yaml

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("indoor_loop_collect")

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from experiments.aerial.scripts.indoor_mainline_baseline_eval import (  # noqa: E402
    MainlineIndoorPolicyWrapper,
    build_segments,
    _goal_dist,
)


def collect_episode(
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
    reward_cfg: Any,
) -> Tuple[Dict[str, Any], List[Any]]:
    from experiments.aerial.rl.buffer import Transition
    from experiments.aerial.rl.collector import act_delta, clip_body_delta
    from experiments.aerial.rl.goal_features import body_vel_from_obs, goal_rel_from_obs
    from experiments.aerial.rl.indoor_controller import controller_attribution_from_counts, mainline_sensors_used
    from experiments.aerial.rl.pose_estimate import mainline_report_fields
    from experiments.aerial.rl.reward import NavigationReward

    goal_pos = np.asarray(seg["pos"][1], dtype=np.float64)
    goal_yaw = float(seg["yaw"][1])
    d0 = float(seg["d0_m"])

    obs = env.reset({"pos": seg["pos"], "yaw": seg["yaw"], "gpt_instruction": seg["gpt_instruction"]})
    if obs is None or getattr(obs, "rgb", None) is None:
        return {"ok": False, "segment_name": seg["segment_name"], "reason": "reset_failed"}, []
    # Stale collision after teleport is common in Building_99; only abort on dead RGB.
    if float(np.asarray(obs.rgb).mean()) < 1.0:
        return {"ok": False, "segment_name": seg["segment_name"], "reason": "black_rgb"}, []

    obs.info["goal"] = goal_pos.tolist()
    policy.reset(obs, target_pos=goal_pos, target_yaw=goal_yaw)
    if hasattr(shield, "reset"):
        shield.reset()
    latent = np.asarray(dynamics.encode(obs), dtype=np.float64)

    reward_fn = NavigationReward(goal_pos, reward_cfg)
    reward_fn.reset(goal_pos, obs.position)
    transitions: List[Transition] = []
    n_interv = 0
    step_i = 0
    depth_mins: List[float] = []

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

        next_obs, info = env.step(action)
        next_obs.info["goal"] = goal_pos.tolist()
        policy.post_step(next_obs, action)
        depth = getattr(next_obs, "depth", None)
        if depth is not None:
            darr = np.asarray(depth, dtype=np.float64)
            fin = np.isfinite(darr) & (darr > 0)
            if fin.any():
                depth_mins.append(float(np.nanmin(darr[fin])))
        out = dynamics.step(
            latent, action,
            goal_rel=goal_rel_from_obs(obs),
            body_vel=body_vel_from_obs(obs),
        )
        latent = np.asarray(out.z_next, dtype=np.float64)

        r, done, terms = reward_fn.step(next_obs, action)
        ep_info = {**info, **terms, "intervention": intervened, "goal": goal_pos.tolist()}
        if obs.info.get("depth_min_pred") is not None:
            ep_info["depth_min_pred"] = obs.info["depth_min_pred"]
        transitions.append(
            Transition(obs=obs, action=action, reward=r, done=done, next_obs=next_obs, info=ep_info)
        )
        obs = next_obs

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
        "collided": bool(getattr(obs, "collided", False)),
        "intervention_rate": round(n_interv / max(step_i + 1, 1), 4),
        "depth_min_median_m": round(float(np.median(depth_mins)), 3) if depth_mins else None,
        "near_depth_frac": round(float(np.mean([x < 5.0 for x in depth_mins])), 3) if depth_mins else None,
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
    return report, transitions


def _mock_segments(n: int, target_len_m: float = 12.0) -> List[Dict[str, Any]]:
    segs: List[Dict[str, Any]] = []
    for i in range(n):
        yaw = 0.1 * i
        start = np.array([float(i * 3), 0.0, -2.0], dtype=np.float64)
        goal = start + target_len_m * np.array([np.cos(yaw), np.sin(yaw), 0.0], dtype=np.float64)
        segs.append({
            "source_route_idx": i,
            "route_name": f"Mock_Route_{i + 1:02d}",
            "segment_name": f"Mock_Seg_{i + 1:02d}",
            "pos": [start.tolist(), goal.tolist()],
            "yaw": [float(yaw), float(yaw)],
            "d0_m": round(_goal_dist(start, goal), 3),
            "gpt_instruction": f"mock indoor segment {i + 1}",
        })
    return segs


def _cycle_segments(segments: List[Dict[str, Any]], n: int) -> List[Dict[str, Any]]:
    if not segments:
        return []
    return [segments[i % len(segments)] for i in range(n)]


def main() -> int:
    parser = argparse.ArgumentParser(description="Indoor mainline closed-loop collect (phase E1)")
    parser.add_argument("--backend", choices=["airsim", "mock"], default="airsim")
    parser.add_argument("--config", default="configs/aerial_rl_indoor_lossless.yaml")
    parser.add_argument("--wm-ckpt", default="experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt")
    parser.add_argument("--actor-ckpt", default="experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_c_20260829/v4_ac_latest.pt")
    parser.add_argument("--depth-ckpt", default="experiments/aerial/rl/artifacts/depth_ckpt_p45mid_s8j_20260825/depth_best_holdout_da3_ft_head.pt")
    parser.add_argument("--annotation", default="artifacts/seen_airsim16_m1a20.json")
    parser.add_argument("--routes", default="all", help="0-based indices comma-sep, or 'all' for 20 routes")
    parser.add_argument("--segment-len-m", type=float, default=12.0)
    parser.add_argument("--max-steps", type=int, default=120)
    parser.add_argument("--success-dist", type=float, default=0.20)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--pose-source", default="gt_proxy", choices=["odom_from_imu_rgb", "gt_proxy", "vio_est"])
    parser.add_argument("--assist", choices=["none", "gt_pd"], default="none")
    parser.add_argument(
        "--allow-gt-assist",
        action="store_true",
        help="E2f fixture BC only: set forbid_gt_world_pose_control=False so assist=gt_pd can engage",
    )
    parser.add_argument(
        "--keep-arrived-only",
        action="store_true",
        help="Only write NPZ when arrived_gt (fixture success demos)",
    )
    parser.add_argument(
        "--max-intervention-rate",
        type=float,
        default=None,
        help="Drop episode if shield intervention_rate exceeds this (E2g: prefer learnable near-field)",
    )
    parser.add_argument(
        "--keep-near-success",
        action="store_true",
        help="Keep episodes with d_end_m_gt <= --near-success-max-m (E2i B1)",
    )
    parser.add_argument(
        "--near-success-max-m",
        type=float,
        default=1.0,
        help="Max terminal distance for --keep-near-success (default 1.0 m)",
    )
    parser.add_argument(
        "--drop-collided",
        action="store_true",
        help="Drop episodes that ended in collision (E2i B1)",
    )
    parser.add_argument(
        "--bc-tag",
        default="",
        help="Optional meta tag e.g. fixture_gt_pd (declared non-mainline BC source)",
    )
    parser.add_argument(
        "--min-usable",
        type=int,
        default=30,
        help="Fail if usable < this (fixture BC often uses lower bar e.g. 15)",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append to existing out-dir (keep prior NPZ; merge manifest/summary)",
    )
    parser.add_argument("--episodes", type=int, default=30)
    parser.add_argument("--out", default="experiments/aerial/rl/artifacts/dataset_indoor_loop_e1_gtproxy_20260829")
    args = parser.parse_args()

    if args.assist == "gt_pd" and not args.allow_gt_assist:
        raise SystemExit(
            "assist=gt_pd requires --allow-gt-assist (fixture BC only; not mainline eval)"
        )
    if args.allow_gt_assist and args.assist != "gt_pd":
        logger.warning("--allow-gt-assist set but assist=%s (no IBVS will run)", args.assist)

    root = Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from experiments.aerial.rl import dataset as ds
    from experiments.aerial.rl.actor_critic import LatentActorCritic, LatentActorDeployPolicy
    from experiments.aerial.rl.depth_predictor import DepthMinPredictor
    from experiments.aerial.rl.planner import ImaginationPlanner
    from experiments.aerial.rl.pose_estimate import make_pose_estimator
    from experiments.aerial.rl.reward import RewardConfig
    from experiments.aerial.scripts.indoor_shield_config import build_indoor_shield, shield_spec_summary
    from experiments.aerial.rl.train_rl import _build_env, load_torch_dynamics

    ann_path = Path(args.annotation) if Path(args.annotation).is_absolute() else root / args.annotation
    if args.backend == "mock":
        segments = _mock_segments(max(args.episodes, 3), target_len_m=args.segment_len_m)
    else:
        routes = json.loads(ann_path.read_text(encoding="utf-8"))
        if args.routes.strip().lower() == "all":
            route_indices = list(range(len(routes)))
        else:
            route_indices = [int(x) for x in args.routes.split(",") if x.strip()]
        segments = build_segments(routes, route_indices, target_len_m=args.segment_len_m)
    plan = _cycle_segments(segments, args.episodes)
    logger.info(
        "E1 collect: %d episodes, %d route segments, pose=%s assist=%s backend=%s",
        len(plan), len(segments), args.pose_source, args.assist, args.backend,
    )

    cfg = yaml.safe_load((root / args.config).read_text()) or {}
    cfg.setdefault("env", {})["backend"] = args.backend
    cfg["env"]["step_hz"] = 5.0
    cfg["env"]["grab_depth"] = args.backend == "airsim"
    # Indoor Building_99 walls can be locally flat → depth-span health gate false-fails.
    cfg["env"]["health_check"] = False
    import os as _os
    cfg["env"]["camera"] = _os.environ.get("AIRSIM_CAMERA", cfg["env"].get("camera", "0"))
    cfg["env"]["vehicle"] = _os.environ.get("AIRSIM_VEHICLE", cfg["env"].get("vehicle", "drone_1"))
    cfg["env"]["spawn_retry_max"] = int(cfg["env"].get("spawn_retry_max", 6))
    cfg["env"]["spawn_min_z_m"] = float(cfg["env"].get("spawn_min_z_m", 1.4))
    cfg["env"]["spawn_z_bump_m"] = float(cfg["env"].get("spawn_z_bump_m", 0.15))
    cfg["env"]["spawn_settle_s"] = float(cfg["env"].get("spawn_settle_s", 0.50))
    cfg["env"]["spawn_hold"] = bool(cfg["env"].get("spawn_hold", True))
    cfg["env"]["spawn_xy_nudge_m"] = float(cfg["env"].get("spawn_xy_nudge_m", 0.30))
    cfg["env"]["spawn_z_raise_m"] = float(cfg["env"].get("spawn_z_raise_m", 0.0))
    cfg["env"]["spawn_z_floor_cmd_m"] = float(cfg["env"].get("spawn_z_floor_cmd_m", 1.8))
    if args.backend == "mock":
        cfg["env"]["host"] = "127.0.0.1"
    env = _build_env(cfg["env"])

    reward_cfg = RewardConfig(**(cfg.get("reward") or {}))
    reward_cfg.success_dist_m = float(args.success_dist)

    wm_path = Path(args.wm_ckpt) if Path(args.wm_ckpt).is_absolute() else root / args.wm_ckpt
    dynamics, _ = load_torch_dynamics(
        cfg.get("world_model") or {}, str(wm_path), device=str(args.device),
        success_dist_m=float(args.success_dist),
    )
    actor_path = Path(args.actor_ckpt) if Path(args.actor_ckpt).is_absolute() else root / args.actor_ckpt
    actor_ac = LatentActorCritic.load_from_checkpoint(actor_path, device=str(args.device))
    base_policy = LatentActorDeployPolicy(dynamics, actor_ac, deterministic=True)
    depth_path = Path(args.depth_ckpt) if Path(args.depth_ckpt).is_absolute() else root / args.depth_ckpt
    depth_pred = (
        DepthMinPredictor.from_checkpoint(depth_path, device=str(args.device))
        if args.backend == "airsim" and depth_path.is_file()
        else None
    )

    limits = np.array([0.15, 0.08, 0.08, 0.10], dtype=np.float64)
    shield = build_indoor_shield(cfg)
    logger.info("shield spec: %s", shield_spec_summary(cfg))
    planner = ImaginationPlanner(dynamics=dynamics, horizon=5, reward_cfg=reward_cfg, action_limits=limits, policy=actor_ac)

    pose_est = make_pose_estimator(args.pose_source)
    forbid_gt = not bool(args.allow_gt_assist)
    policy = MainlineIndoorPolicyWrapper(
        base_policy, pose_est, max_dz=0.08, step_hz=5.0,
        assist=args.assist, forbid_gt_world_pose_control=forbid_gt,
    )
    policy.action_limits = limits

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
    failures: List[str] = []
    quarantined: List[str] = []
    skipped = 0

    try:
        for seg in plan:
            logger.info("--- collect %s d0=%.1fm ---", seg["segment_name"], seg["d0_m"])
            rep, transitions = collect_episode(
                env, policy, dynamics, depth_pred, shield, planner, seg,
                max_steps=args.max_steps, success_dist=args.success_dist,
                action_limits=limits, reward_cfg=reward_cfg,
            )
            if not rep.get("ok"):
                skipped += 1
                logger.warning("%s skipped: %s", seg["segment_name"], rep.get("reason"))
                continue
            if not transitions:
                skipped += 1
                continue
            if args.keep_arrived_only and not rep.get("arrived_gt"):
                skipped += 1
                logger.info(
                    "drop non-arrived %s d_end_gt=%.2f",
                    seg["segment_name"], rep["d_end_m_gt"],
                )
                continue
            if args.keep_near_success:
                d_end = float(rep.get("d_end_m_gt", 999.0))
                if d_end > float(args.near_success_max_m):
                    skipped += 1
                    logger.info(
                        "drop far-end %s d_end_gt=%.2f > %.2f",
                        seg["segment_name"], d_end, float(args.near_success_max_m),
                    )
                    continue
            if args.drop_collided and rep.get("collided"):
                skipped += 1
                logger.info(
                    "drop collided %s d_end_gt=%.2f",
                    seg["segment_name"], rep.get("d_end_m_gt"),
                )
                continue
            max_ir = args.max_intervention_rate
            if max_ir is not None and float(rep.get("intervention_rate", 0.0)) > float(max_ir):
                skipped += 1
                logger.info(
                    "drop high-intervention %s rate=%.3f > %.3f d_end_gt=%.2f",
                    seg["segment_name"],
                    float(rep.get("intervention_rate", 0.0)),
                    float(max_ir),
                    rep["d_end_m_gt"],
                )
                continue

            path = ds.write_episode(out_dir, ep_idx, transitions)
            qrep = ds.quality_report(transitions)
            bad = ds.assert_nontrivial(qrep)
            quar = ds.quarantine_reasons(qrep)
            status = "BAD" if bad else ("QUARANTINE" if quar else "OK")
            logger.info(
                "ep %d: %s steps=%d d_end_gt=%.2f arrived_gt=%s %s | %s",
                ep_idx, seg["segment_name"], rep["steps"], rep["d_end_m_gt"],
                rep["arrived_gt"], status, path.name,
            )
            for f in bad:
                failures.append(f"ep{ep_idx}: {f}")
            for q in quar:
                quarantined.append(f"ep{ep_idx}: {q}")
            manifest.append({
                "file": path.name,
                "steps": qrep["steps"],
                "return": qrep["reward_sum"],
                "segment_name": rep["segment_name"],
                "route_name": rep["route_name"],
                "d_end_m_gt": rep["d_end_m_gt"],
                "arrived_gt": rep["arrived_gt"],
                "nontrivial": not bad,
                "quarantined": bool(quar),
                "usable": not bad and not quar,
            })
            quality_reports.append(qrep)
            reports.append({**qrep, **rep})
            ep_idx += 1
    finally:
        close = getattr(env, "close", None)
        if callable(close):
            close()

    all_manifest = prior_manifest + manifest
    all_reports = prior_reports + reports
    all_quality = prior_quality + quality_reports
    n = len(all_manifest)
    usable = sum(1 for m in all_manifest if m.get("usable"))
    usable_new = sum(1 for m in manifest if m.get("usable"))
    meta = {
        "protocol": (
            "indoor_fixture_bc_E2h_building99"
            if (args.bc_tag and "building99" in str(args.bc_tag).lower())
            else (
            "indoor_fixture_bc_E2g"
            if (args.bc_tag and "020" in str(args.bc_tag))
            else ("indoor_fixture_bc_E2f" if args.bc_tag or args.allow_gt_assist else "indoor_mainline_E1")
            )
        ),
        "annotation": str(args.annotation),
        "scene": "Building_99" if "building99" in str(args.annotation).lower() else None,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "pose_source": args.pose_source,
        "train_pose_source": args.pose_source,
        "eval_pose_source": args.pose_source,
        "assist": args.assist,
        "shield_spec": shield_spec_summary(cfg),
        "forbid_gt_world_pose_control": forbid_gt,
        "bc_tag": args.bc_tag or None,
        "bc_from": args.bc_tag or ("fixture_gt_pd" if args.allow_gt_assist else None),
        "keep_arrived_only": bool(args.keep_arrived_only),
        "keep_near_success": bool(args.keep_near_success),
        "near_success_max_m": float(args.near_success_max_m) if args.keep_near_success else None,
        "drop_collided": bool(args.drop_collided),
        "max_intervention_rate": args.max_intervention_rate,
        "success_dist_m": args.success_dist,
        "segment_len_m": args.segment_len_m,
        "action_limits": limits.tolist(),
        "shield": "ThreeZoneSpeedShield ON",
        "sensors_used": ["rgb", "imu", "height", "depth_pred"],
        "backend": args.backend,
        "step_hz": 5.0,
        "max_steps": args.max_steps,
        "n_requested": args.episodes,
        "n_collected": n,
        "n_usable": usable,
        "n_usable_new": usable_new,
        "append": bool(args.append),
        "skipped_spawn_collision": skipped,
        "actor_ckpt": str(args.actor_ckpt),
        "wm_ckpt": str(args.wm_ckpt),
        "note": (
            "Fixture BC bootstrap: actions may include GT-PD/IBVS near-field; "
            "NOT mainline completion. Eval must use assist=none."
            if args.allow_gt_assist else None
        ),
    }
    ds.write_manifest(out_dir, all_manifest, meta=meta)
    ds.write_quality_summary(out_dir, all_quality)

    summary_path = out_dir / "collection_summary.json"
    summary_path.write_text(json.dumps({
        "meta": meta,
        "n_usable": usable,
        "n_collected": n,
        "n_usable_new": usable_new,
        "arrival_rate_gt": round(
            sum(1 for r in all_reports if r.get("arrived_gt")) / max(n, 1), 4
        ),
        "mean_d_end_gt": round(
            float(np.mean([r["d_end_m_gt"] for r in all_reports if r.get("d_end_m_gt") is not None])), 4
        ) if all_reports else None,
        "episodes": [{k: r[k] for k in (
            "segment_name", "route_name", "steps", "d_end_m_gt", "d_end_m_hat",
            "arrived_gt", "collided", "intervention_rate", "pose_source",
        ) if k in r} for r in all_reports],
    }, indent=2), encoding="utf-8")
    logger.info(
        "Wrote %d episodes (%d usable, +%d new) -> %s",
        n, usable, usable_new, out_dir,
    )

    if failures:
        for f in failures:
            logger.error("FAIL: %s", f)
        return 1
    if n == 0:
        logger.error("FAIL: 0 episodes collected")
        return 1
    if usable < int(args.min_usable) and args.backend == "airsim":
        logger.error("FAIL: n_usable=%d < %d gate", usable, args.min_usable)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
