#!/usr/bin/env python3
"""C1 ckpt route ego-video probe (assist=none, shield ON) — visual audit, not gate.

Records HUD ego mp4 for selected Building_99 short routes so humans can verify
JSON metrics (arrival / collide / drift) instead of trusting tables alone.

Usage on 125:
  source experiments/aerial/scripts/env_4090.sh
  export AIRSIM_CAMERA=0 AIRSIM_VEHICLE=drone_1
  $AERIAL_PY experiments/aerial/scripts/indoor_c1_route_vid.py \\
    --routes 0,3,4,5 --seed 0 \\
    --out-dir artifacts/videos/indoor_c1_route_vid_20260831
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2
import numpy as np
import yaml

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("c1_route_vid")


def _write_mp4(frames: List[np.ndarray], path: Path, fps: float = 5.0) -> None:
    if not frames:
        raise ValueError("no frames")
    path.parent.mkdir(parents=True, exist_ok=True)
    h, w = frames[0].shape[:2]
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "bgr24",
        "-s", f"{w}x{h}", "-r", str(fps),
        "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-preset", "veryfast", str(path),
    ]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    assert p.stdin is not None
    for fr in frames:
        if fr.shape[:2] != (h, w):
            fr = cv2.resize(fr, (w, h))
        p.stdin.write(np.ascontiguousarray(fr).tobytes())
    p.stdin.close()
    if p.wait() != 0:
        raise RuntimeError(f"ffmpeg failed {path}")


def _hud(
    rgb: np.ndarray,
    *,
    step: int,
    d_gt: float,
    d_hat: float,
    depth_min: Optional[float],
    intervened: bool,
    channels: Any,
    collided: bool,
    success_dist: float,
) -> np.ndarray:
    bgr = np.asarray(rgb[..., ::-1], dtype=np.uint8).copy()
    if max(bgr.shape[:2]) < 400:
        bgr = cv2.resize(bgr, (bgr.shape[1] * 3, bgr.shape[0] * 3), interpolation=cv2.INTER_NEAREST)
    h, w = bgr.shape[:2]
    ch = ",".join(channels) if isinstance(channels, (list, tuple)) else str(channels or "-")
    dmin_s = f"{depth_min:.2f}" if depth_min is not None else "na"
    lines = [
        f"C1vid step={step:03d} d_gt={d_gt:.2f} d_hat={d_hat:.2f} depth={dmin_s}",
        f"interv={'Y' if intervened else 'n'} ch={ch[:40]} col={'Y' if collided else 'n'}",
    ]
    for i, t in enumerate(lines):
        cv2.putText(bgr, t, (10, 26 + 26 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (240, 240, 240), 2, cv2.LINE_AA)
    if d_gt <= success_dist:
        cv2.putText(bgr, "ARRIVED", (w // 2 - 70, h // 2), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (40, 230, 90), 3, cv2.LINE_AA)
    elif collided:
        cv2.putText(bgr, "COLLIDED", (w // 2 - 80, h // 2), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (40, 40, 240), 3, cv2.LINE_AA)
    return bgr


def _goal_dist(pos: np.ndarray, goal: np.ndarray) -> float:
    return float(np.linalg.norm(np.asarray(goal, dtype=np.float64).reshape(3) - np.asarray(pos, dtype=np.float64).reshape(3)))


def run_episode_vid(
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

    goal_pos = np.asarray(seg["pos"][1], dtype=np.float64)
    goal_yaw = float(seg["yaw"][1])
    obs = env.reset({"pos": seg["pos"], "yaw": seg["yaw"], "gpt_instruction": seg["gpt_instruction"]})
    if obs is None or getattr(obs, "rgb", None) is None:
        return {"ok": False, "segment_name": seg["segment_name"], "reason": "reset_failed", "frames": []}
    if float(np.asarray(obs.rgb).mean()) < 1.0:
        return {"ok": False, "segment_name": seg["segment_name"], "reason": "black_rgb", "frames": []}

    obs.info["goal"] = goal_pos.tolist()
    policy.reset(obs, target_pos=goal_pos, target_yaw=goal_yaw)
    if hasattr(shield, "reset"):
        shield.reset()
    latent = np.asarray(dynamics.encode(obs), dtype=np.float64)

    frames: List[np.ndarray] = []
    n_interv = 0
    step_i = 0
    for step_i in range(max_steps):
        action = act_delta(policy, obs, seg["gpt_instruction"], action_limits)
        if planner is not None:
            if callable(getattr(planner, "set_goal", None)):
                planner.set_goal(goal_pos)
            action = np.asarray(planner.plan(obs, action), dtype=np.float64).reshape(4)
            action = clip_body_delta(action, action_limits)
        action = policy.arbitrate(obs, action)

        depth_min = None
        if depth_pred is not None:
            d_min = depth_pred.predict_min(obs)
            if d_min is not None:
                depth_min = float(d_min)
                obs.info["depth_min_pred"] = depth_min

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

        pe = obs.info.get("pose_estimate") if isinstance(obs.info, dict) else None
        d_hat = _goal_dist(np.asarray(pe.get("p_hat")), goal_pos) if isinstance(pe, dict) and pe.get("p_hat") is not None else float("nan")
        d_gt = _goal_dist(obs.position, goal_pos)
        frames.append(
            _hud(
                obs.rgb,
                step=step_i,
                d_gt=d_gt,
                d_hat=d_hat,
                depth_min=depth_min,
                intervened=intervened,
                channels=obs.info.get("shield_channels") if isinstance(obs.info, dict) else None,
                collided=bool(getattr(obs, "collided", False)),
                success_dist=success_dist,
            )
        )

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

        d_gt = _goal_dist(obs.position, goal_pos)
        if d_gt <= success_dist or bool(getattr(obs, "collided", False)):
            # final frame after terminal
            pe = obs.info.get("pose_estimate") if isinstance(obs.info, dict) else None
            d_hat = _goal_dist(np.asarray(pe.get("p_hat")), goal_pos) if isinstance(pe, dict) and pe.get("p_hat") is not None else float("nan")
            frames.append(
                _hud(
                    obs.rgb,
                    step=step_i + 1,
                    d_gt=d_gt,
                    d_hat=d_hat,
                    depth_min=None,
                    intervened=False,
                    channels=None,
                    collided=bool(getattr(obs, "collided", False)),
                    success_dist=success_dist,
                )
            )
            break

    d_end_gt = _goal_dist(obs.position, goal_pos)
    return {
        "ok": True,
        "segment_name": seg["segment_name"],
        "route_name": seg["route_name"],
        "source_route_idx": seg["source_route_idx"],
        "steps": step_i + 1,
        "d_end_m_gt": round(d_end_gt, 4),
        "arrived_gt": bool(d_end_gt <= success_dist),
        "collided": bool(getattr(obs, "collided", False)),
        "intervention_rate": round(n_interv / max(step_i + 1, 1), 4),
        "frames": frames,
        "n_frames": len(frames),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/aerial_rl_indoor_c1_050.yaml")
    ap.add_argument("--actor-ckpt", default="experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2i_c1_20260831/v4_ac_latest.pt")
    ap.add_argument("--wm-ckpt", default="experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt")
    ap.add_argument("--depth-ckpt", default="experiments/aerial/rl/artifacts/depth_ckpt_p45mid_s8j_20260825/depth_best_holdout_da3_ft_head.pt")
    ap.add_argument("--annotation", default="artifacts/building99_indoor_short_routes.json")
    ap.add_argument("--routes", default="0,3,4,5", help="0-based indices: R01/R04/R05/R06")
    ap.add_argument("--segment-len-m", type=float, default=3.0)
    ap.add_argument("--max-steps", type=int, default=160)
    ap.add_argument("--success-dist", type=float, default=0.50)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out-dir", default="artifacts/videos/indoor_c1_route_vid_20260831")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from experiments.aerial.rl.actor_critic import LatentActorCritic, LatentActorDeployPolicy
    from experiments.aerial.rl.depth_predictor import DepthMinPredictor
    from experiments.aerial.rl.planner import ImaginationPlanner
    from experiments.aerial.rl.pose_estimate import make_pose_estimator
    from experiments.aerial.rl.reward import RewardConfig
    from experiments.aerial.scripts.indoor_mainline_baseline_eval import (
        MainlineIndoorPolicyWrapper,
        build_segments,
    )
    from experiments.aerial.scripts.indoor_shield_config import build_indoor_shield, shield_spec_summary
    from experiments.aerial.rl.train_rl import _build_env, load_torch_dynamics

    np.random.seed(int(args.seed))

    out_dir = Path(args.out_dir) if Path(args.out_dir).is_absolute() else root / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    route_indices = [int(x) for x in args.routes.split(",") if x.strip()]
    ann_path = Path(args.annotation) if Path(args.annotation).is_absolute() else root / args.annotation
    routes = json.loads(ann_path.read_text(encoding="utf-8"))
    segments = build_segments(routes, route_indices, target_len_m=args.segment_len_m)

    cfg = yaml.safe_load((root / args.config).read_text()) or {}
    cfg.setdefault("env", {})["backend"] = "airsim"
    cfg["env"]["step_hz"] = 5.0
    cfg["env"]["grab_depth"] = True
    cfg["env"]["health_check"] = False
    cfg["env"]["seed"] = int(args.seed)
    cfg["env"]["camera"] = os.environ.get("AIRSIM_CAMERA", cfg["env"].get("camera", "0"))
    cfg["env"]["vehicle"] = os.environ.get("AIRSIM_VEHICLE", cfg["env"].get("vehicle", "drone_1"))
    env = _build_env(cfg["env"])

    reward_cfg = RewardConfig(**(cfg.get("reward") or {}))
    reward_cfg.success_dist_m = float(args.success_dist)
    wm_path = Path(args.wm_ckpt) if Path(args.wm_ckpt).is_absolute() else root / args.wm_ckpt
    dynamics, _ = load_torch_dynamics(
        cfg.get("world_model") or {}, str(wm_path), device=str(args.device), success_dist_m=float(args.success_dist),
    )
    actor_path = Path(args.actor_ckpt) if Path(args.actor_ckpt).is_absolute() else root / args.actor_ckpt
    actor_ac = LatentActorCritic.load_from_checkpoint(actor_path, device=str(args.device))
    base_policy = LatentActorDeployPolicy(dynamics, actor_ac, deterministic=True)
    depth_path = Path(args.depth_ckpt) if Path(args.depth_ckpt).is_absolute() else root / args.depth_ckpt
    depth_pred = DepthMinPredictor.from_checkpoint(depth_path, device=str(args.device)) if depth_path.is_file() else None

    limits = np.array([0.15, 0.08, 0.08, 0.10], dtype=np.float64)
    shield = build_indoor_shield(cfg, shield_off=False)
    logger.info("shield spec: %s", shield_spec_summary(cfg))
    planner = ImaginationPlanner(
        dynamics=dynamics, horizon=5, reward_cfg=reward_cfg, action_limits=limits, policy=actor_ac,
    )
    pose_est = make_pose_estimator("gt_proxy")
    policy = MainlineIndoorPolicyWrapper(
        base_policy, pose_est, max_dz=0.08, step_hz=5.0,
        assist="none", forbid_gt_world_pose_control=True,
    )
    policy.action_limits = limits

    reports: List[Dict[str, Any]] = []
    try:
        for seg in segments:
            logger.info("--- VID %s ---", seg["segment_name"])
            rep = run_episode_vid(
                env, policy, dynamics, depth_pred, shield, planner, seg,
                max_steps=args.max_steps, success_dist=args.success_dist, action_limits=limits,
            )
            frames = rep.pop("frames", [])
            if rep.get("ok") and frames:
                mp4 = out_dir / f"{seg['segment_name']}_seed{args.seed}_ego.mp4"
                _write_mp4(frames, mp4, fps=5.0)
                # stills: start / mid / end
                for tag, idx in (("start", 0), ("mid", len(frames) // 2), ("end", len(frames) - 1)):
                    still = out_dir / f"{seg['segment_name']}_seed{args.seed}_{tag}.png"
                    cv2.imwrite(str(still), frames[idx])
                rep["ego_mp4"] = str(mp4)
                rep["n_frames"] = len(frames)
                logger.info(
                    "%s d_end=%.2f arrived=%s col=%s interv=%.2f -> %s",
                    seg["segment_name"], rep["d_end_m_gt"], rep["arrived_gt"],
                    rep["collided"], rep["intervention_rate"], mp4.name,
                )
            else:
                logger.warning("%s failed: %s", seg["segment_name"], rep.get("reason"))
            reports.append(rep)
    finally:
        close = getattr(env, "close", None)
        if callable(close):
            close()

    summary = {
        "protocol": "C1_route_vid_probe",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "ckpt": str(args.actor_ckpt),
        "config": str(args.config),
        "seed": int(args.seed),
        "success_dist_m": float(args.success_dist),
        "assist": "none",
        "pose_source": "gt_proxy",
        "routes": route_indices,
        "episodes": reports,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    logger.info("wrote %s", out_dir / "summary.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
