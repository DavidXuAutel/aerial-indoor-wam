#!/usr/bin/env python3
"""Indoor corridor long-route demo: Two-Phase WAM+IBVS closed loop + videos.

Runs a longer near-structure micro-corridor segment under the indoor two-phase
controller (cruise + near-field IBVS + altitude lock), and saves:
  * first-person HUD MP4
  * top-down trajectory map MP4
  * dual-view dashboard MP4
  * JSON telemetry summary

Usage on 125 (prefer public SSH host cursor-125-public):
  source experiments/aerial/scripts/env_4090.sh
  $AERIAL_PY experiments/aerial/scripts/indoor_corridor_demo.py \
    --route-priority 6,12,13 \
    --success-dist 0.20 \
    --max-steps 160 \
    --out-dir artifacts/videos/indoor_corridor
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
import yaml

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("indoor_corridor")


def _goal_dist(pos: np.ndarray, goal: np.ndarray) -> float:
    return float(np.linalg.norm(np.asarray(goal, dtype=np.float64).reshape(3) - np.asarray(pos, dtype=np.float64).reshape(3)))


def _write_frames_ffmpeg(frames: List[np.ndarray], out_mp4: Path, *, fps: float = 5.0) -> None:
    if not frames:
        raise ValueError("no frames to encode")
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    h, w = frames[0].shape[:2]
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "bgr24",
        "-s", f"{w}x{h}", "-r", str(fps),
        "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-preset", "veryfast", str(out_mp4),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    assert proc.stdin is not None
    for fr in frames:
        if fr.shape[:2] != (h, w):
            fr = cv2.resize(fr, (w, h), interpolation=cv2.INTER_LINEAR)
        if fr.dtype != np.uint8:
            fr = np.clip(fr, 0, 255).astype(np.uint8)
        proc.stdin.write(np.ascontiguousarray(fr).tobytes())
    proc.stdin.close()
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"ffmpeg failed rc={rc} for {out_mp4}")


def build_corridor_segments(
    routes: List[Dict[str, Any]],
    priority: List[int],
    target_len_m: float = 24.0,
    max_routes: int = 3,
) -> List[Dict[str, Any]]:
    segments: List[Dict[str, Any]] = []
    for idx in priority:
        if idx >= len(routes) or len(segments) >= max_routes:
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
            "segment_name": f"Corridor_{len(segments)+1:02d}_Route_{idx+1:02d}",
            "pos": [seg_start.tolist(), seg_goal.tolist()],
            "yaw": [float(yaw_list[0]), float(yaw_list[end_idx])],
            "astar_pos": pos_list[: end_idx + 1].tolist(),
            "d0_m": round(_goal_dist(seg_start, seg_goal), 3),
            "path_len_m": round(cum, 3),
            "gpt_instruction": (r.get("gpt_instruction", "")[:100] + " (corridor demo)"),
        })
    return segments


def _draw_ego_hud(
    rgb: np.ndarray,
    *,
    step: int,
    d_goal: float,
    phase: str,
    z: float,
    intervened: bool,
    progress: float,
    arrived: bool,
) -> np.ndarray:
    frame = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR) if rgb.shape[-1] == 3 else rgb.copy()
    h, w = frame.shape[:2]
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 72), (20, 20, 20), -1)
    cv2.rectangle(overlay, (0, h - 36), (w, h), (20, 20, 20), -1)
    frame = cv2.addWeighted(overlay, 0.55, frame, 0.45, 0)
    phase_col = (80, 220, 120) if "SERVO" in phase else (80, 180, 255)
    cv2.putText(frame, f"STEP {step:03d}  |  d={d_goal:.2f}m  |  z={z:.2f}m", (12, 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (240, 240, 240), 1, cv2.LINE_AA)
    cv2.putText(frame, phase, (12, 56), cv2.FONT_HERSHEY_SIMPLEX, 0.55, phase_col, 2, cv2.LINE_AA)
    if intervened:
        cv2.putText(frame, "SHIELD", (w - 120, 56), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (40, 40, 255), 2, cv2.LINE_AA)
    bar_w = int((w - 24) * max(0.0, min(1.0, progress)))
    cv2.rectangle(frame, (12, h - 24), (w - 12, h - 12), (60, 60, 60), -1)
    cv2.rectangle(frame, (12, h - 24), (12 + bar_w, h - 12), (60, 200, 90), -1)
    if arrived:
        cv2.putText(frame, "ARRIVED", (w // 2 - 70, h // 2), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (40, 230, 90), 3, cv2.LINE_AA)
    return frame


def _render_map(
    flown: np.ndarray,
    astar: np.ndarray,
    goal: np.ndarray,
    size: Tuple[int, int] = (720, 720),
) -> np.ndarray:
    w, h = size
    canvas = np.full((h, w, 3), 28, dtype=np.uint8)
    pts = np.vstack([astar, flown, goal.reshape(1, 3)]) if flown.size else np.vstack([astar, goal.reshape(1, 3)])
    xy = pts[:, :2]
    mn = xy.min(axis=0) - 2.0
    mx = xy.max(axis=0) + 2.0
    span = np.maximum(mx - mn, 1e-3)

    def proj(p: np.ndarray) -> Tuple[int, int]:
        u = int((p[0] - mn[0]) / span[0] * (w - 40) + 20)
        v = int((1.0 - (p[1] - mn[1]) / span[1]) * (h - 40) + 20)
        return u, v

    # grid
    for g in range(0, w, 40):
        cv2.line(canvas, (g, 0), (g, h), (40, 40, 40), 1)
    for g in range(0, h, 40):
        cv2.line(canvas, (0, g), (w, g), (40, 40, 40), 1)

    if len(astar) >= 2:
        poly = np.array([proj(p) for p in astar], dtype=np.int32)
        cv2.polylines(canvas, [poly], False, (90, 90, 90), 2, cv2.LINE_AA)
    if len(flown) >= 2:
        poly = np.array([proj(p) for p in flown], dtype=np.int32)
        cv2.polylines(canvas, [poly], False, (60, 200, 255), 2, cv2.LINE_AA)
        cv2.circle(canvas, proj(flown[-1]), 7, (40, 180, 255), -1, cv2.LINE_AA)
    cv2.circle(canvas, proj(astar[0]), 8, (80, 220, 120), -1, cv2.LINE_AA)
    cv2.circle(canvas, proj(goal), 10, (40, 40, 255), 2, cv2.LINE_AA)
    cv2.putText(canvas, "TOP-DOWN CORRIDOR MAP", (16, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (220, 220, 220), 1, cv2.LINE_AA)
    return canvas


def _compose_dual(ego: np.ndarray, mp: np.ndarray, out_size: Tuple[int, int] = (1440, 720)) -> np.ndarray:
    ow, oh = out_size
    half = ow // 2
    left = cv2.resize(ego, (half, oh), interpolation=cv2.INTER_LINEAR)
    right = cv2.resize(mp, (ow - half, oh), interpolation=cv2.INTER_LINEAR)
    return np.concatenate([left, right], axis=1)


class TwoPhasePolicyWrapper:
    def __init__(self, base_policy: Any, max_dz: float = 0.08, step_hz: float = 5.0, d_switch: float = 1.2):
        self.base_policy = base_policy
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
        self.goal_yaw = float(target_yaw)
        from experiments.aerial.rl.env.obs import Observation
        if isinstance(initial_obs, Observation):
            self.two_phase_ctrl.reset(initial_obs, self.goal_pos)

    def act(self, view: Any) -> np.ndarray:
        raw_wam = self.base_policy.act(view)
        from experiments.aerial.rl.env.obs import Observation
        cur_state = np.array(
            [view.proprio[0], view.proprio[1], view.proprio[2], 0, 0, 0, view.proprio[3]],
            dtype=np.float32,
        )
        full_obs = Observation(rgb=view.rgb, state=cur_state, t=view.t)
        assert self.goal_pos is not None
        final_action, phase, _dist = self.two_phase_ctrl.arbitrate_action(
            obs=full_obs,
            wam_action=raw_wam,
            goal_pos=self.goal_pos,
            goal_yaw=self.goal_yaw,
            action_limits=self.action_limits,
            step_hz=self.step_hz,
            assist="none",
            forbid_gt_world_pose_control=True,
        )
        self.last_phase = phase
        return final_action


def run_corridor_episode(
    env: Any,
    policy_wrap: TwoPhasePolicyWrapper,
    depth_pred: Any,
    shield: Any,
    planner: Any,
    dynamics: Any,
    seg: Dict[str, Any],
    *,
    max_steps: int,
    success_dist: float,
    step_hz: float,
    action_limits: np.ndarray,
) -> Dict[str, Any]:
    from experiments.aerial.rl.collector import act_delta, clip_body_delta
    from experiments.aerial.rl.goal_features import body_vel_from_obs, goal_rel_from_obs

    goal_pos = np.asarray(seg["pos"][1], dtype=np.float64)
    goal_yaw = float(seg["yaw"][1])
    d0 = float(seg["d0_m"])
    astar = np.asarray(seg["astar_pos"], dtype=np.float64)

    obs = env.reset({"pos": seg["pos"], "yaw": seg["yaw"], "gpt_instruction": seg["gpt_instruction"]})
    if obs is None or bool(getattr(obs, "collided", False)):
        return {"ok": False, "reason": "spawn_collision"}

    policy_wrap.reset(obs, target_pos=goal_pos, target_yaw=goal_yaw)
    policy_wrap.action_limits = action_limits
    if hasattr(shield, "reset"):
        shield.reset()
    latent = np.asarray(dynamics.encode(obs), dtype=np.float64)

    ego_frames: List[np.ndarray] = []
    map_frames: List[np.ndarray] = []
    dual_frames: List[np.ndarray] = []
    flown = [obs.position.copy()]
    phases: List[str] = []
    n_interv = 0
    arrived = False

    for step_i in range(max_steps):
        action = act_delta(policy_wrap, obs, seg["gpt_instruction"], action_limits)
        if planner is not None and "SERVO" not in policy_wrap.last_phase:
            if callable(getattr(planner, "set_goal", None)):
                planner.set_goal(goal_pos)
            action = np.asarray(planner.plan(obs, action), dtype=np.float64).reshape(4)
            action = clip_body_delta(action, action_limits)
            # Re-apply altitude / phase arbitration after planner
            action, phase, _ = policy_wrap.two_phase_ctrl.arbitrate_action(
                obs=obs,
                wam_action=action,
                goal_pos=goal_pos,
                goal_yaw=goal_yaw,
                action_limits=action_limits,
                step_hz=step_hz,
                assist="none",
                forbid_gt_world_pose_control=True,
            )
            policy_wrap.last_phase = phase

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
        out = dynamics.step(
            latent, action,
            goal_rel=goal_rel_from_obs(obs),
            body_vel=body_vel_from_obs(obs),
        )
        latent = np.asarray(out.z_next, dtype=np.float64)
        flown.append(next_obs.position.copy())
        phases.append(policy_wrap.last_phase)

        d_now = _goal_dist(next_obs.position, goal_pos)
        prog = (d0 - d_now) / max(d0, 1e-3)
        arrived_now = d_now <= success_dist
        ego = _draw_ego_hud(
            next_obs.rgb,
            step=step_i + 1,
            d_goal=d_now,
            phase=policy_wrap.last_phase,
            z=float(next_obs.position[2]),
            intervened=intervened,
            progress=prog,
            arrived=arrived_now,
        )
        mp = _render_map(np.asarray(flown), astar, goal_pos)
        dual = _compose_dual(ego, mp)
        ego_frames.append(ego)
        map_frames.append(mp)
        dual_frames.append(dual)

        obs = next_obs
        if arrived_now:
            arrived = True
            break
        if bool(getattr(next_obs, "collided", False)):
            break

    d_end = _goal_dist(obs.position, goal_pos)
    d_min = min(_goal_dist(p, goal_pos) for p in flown)
    if d_min <= success_dist or d_end <= success_dist:
        arrived = True
    n_servo = sum(1 for p in phases if "SERVO" in p)
    return {
        "ok": True,
        "segment_name": seg["segment_name"],
        "steps": len(ego_frames),
        "d0_m": d0,
        "path_len_m": seg["path_len_m"],
        "d_end_m": round(d_end, 4),
        "d_min_m": round(d_min, 4),
        "arrived": bool(arrived),
        "intervention_rate": round(n_interv / max(len(ego_frames), 1), 4),
        "servo_ratio": round(n_servo / max(len(phases), 1), 4),
        "collided": bool(getattr(obs, "collided", False)),
        "ego_frames": ego_frames,
        "map_frames": map_frames,
        "dual_frames": dual_frames,
        "flown": np.asarray(flown),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Indoor corridor two-phase demo + video")
    parser.add_argument("--config", default="configs/aerial_rl_indoor_lossless.yaml")
    parser.add_argument("--wm-ckpt", default="experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt")
    parser.add_argument("--actor-ckpt", default="experiments/aerial/rl/artifacts/v4_ac_ckpt_step_e_20260828/v4_ac_latest.pt")
    parser.add_argument("--depth-ckpt", default="experiments/aerial/rl/artifacts/depth_ckpt_p45mid_s8j_20260825/depth_best_holdout_da3_ft_head.pt")
    parser.add_argument("--annotation", default="artifacts/seen_airsim16_m1a20.json")
    parser.add_argument("--route-priority", default="6,12,13", help="0-based route indices")
    parser.add_argument("--segment-len-m", type=float, default=24.0)
    parser.add_argument("--max-routes", type=int, default=2)
    parser.add_argument("--max-steps", type=int, default=160)
    parser.add_argument("--success-dist", type=float, default=0.20)
    parser.add_argument("--fps", type=float, default=5.0)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--out-dir", default="artifacts/videos/indoor_corridor")
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

    ann_path = Path(args.annotation)
    if not ann_path.is_absolute():
        ann_path = root / ann_path
    routes = json.loads(ann_path.read_text(encoding="utf-8"))
    priority = [int(x) for x in args.route_priority.split(",") if x.strip()]
    segments = build_corridor_segments(routes, priority, target_len_m=args.segment_len_m, max_routes=args.max_routes)
    logger.info("Built %d corridor segments (~%.1fm)", len(segments), args.segment_len_m)

    cfg = yaml.safe_load((root / args.config).read_text()) or {}
    cfg.setdefault("env", {})["backend"] = "airsim"
    cfg["env"]["step_hz"] = 5.0
    cfg["env"]["grab_depth"] = True
    env = _build_env(cfg["env"])

    reward_cfg = RewardConfig(**(cfg.get("reward") or {}))
    reward_cfg.success_dist_m = float(args.success_dist)

    wm_path = Path(args.wm_ckpt) if Path(args.wm_ckpt).is_absolute() else root / args.wm_ckpt
    dynamics, _ = load_torch_dynamics(
        cfg.get("world_model") or {}, str(wm_path),
        device=str(args.device), success_dist_m=float(args.success_dist),
    )
    actor_path = Path(args.actor_ckpt) if Path(args.actor_ckpt).is_absolute() else root / args.actor_ckpt
    actor_ac = LatentActorCritic.load_from_checkpoint(actor_path, device=str(args.device))
    base_policy = LatentActorDeployPolicy(dynamics, actor_ac, deterministic=True)

    depth_path = Path(args.depth_ckpt) if Path(args.depth_ckpt).is_absolute() else root / args.depth_ckpt
    depth_pred = DepthMinPredictor.from_checkpoint(depth_path, device=str(args.device)) if depth_path.is_file() else None

    indoor_limits = np.array([0.15, 0.08, 0.08, 0.10], dtype=np.float64)
    shield = ThreeZoneSpeedShield(
        zone=ThreeZoneSpec(l1_m=1.5, l2_m=0.8, l3_m=0.4, v1_m_s=0.6, v2_m_s=0.3, v_stop_m_s=0.05, v_cruise_m_s=1.0, dt_s=0.2),
        retreat_step_m=0.3,
        min_tau_s=0.5,
    )
    planner = ImaginationPlanner(
        dynamics=dynamics, horizon=5, reward_cfg=reward_cfg,
        action_limits=indoor_limits,
    )
    policy_wrap = TwoPhasePolicyWrapper(base_policy, max_dz=0.08, step_hz=5.0, d_switch=1.2)

    out_dir = Path(args.out_dir) if Path(args.out_dir).is_absolute() else root / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    summaries = []

    for seg in segments:
        logger.info("=== %s d0=%.1fm path=%.1fm ===", seg["segment_name"], seg["d0_m"], seg["path_len_m"])
        result = run_corridor_episode(
            env, policy_wrap, depth_pred, shield, planner, dynamics, seg,
            max_steps=args.max_steps, success_dist=args.success_dist,
            step_hz=5.0, action_limits=indoor_limits,
        )
        if not result.get("ok"):
            logger.warning("%s skipped: %s", seg["segment_name"], result.get("reason"))
            continue

        stem = seg["segment_name"].lower()
        ego_path = out_dir / f"{stem}_ego.mp4"
        map_path = out_dir / f"{stem}_map.mp4"
        dual_path = out_dir / f"{stem}_dual.mp4"
        _write_frames_ffmpeg(result["ego_frames"], ego_path, fps=args.fps)
        _write_frames_ffmpeg(result["map_frames"], map_path, fps=args.fps)
        _write_frames_ffmpeg(result["dual_frames"], dual_path, fps=args.fps)
        logger.info(
            "%s done: steps=%d d_end=%.3fm d_min=%.3fm arrived=%s servo=%.0f%% -> %s",
            seg["segment_name"], result["steps"], result["d_end_m"], result["d_min_m"],
            result["arrived"], 100 * result["servo_ratio"], dual_path,
        )
        summary = {
            k: v for k, v in result.items()
            if k not in ("ego_frames", "map_frames", "dual_frames", "flown")
        }
        summary["ego_mp4"] = str(ego_path)
        summary["map_mp4"] = str(map_path)
        summary["dual_mp4"] = str(dual_path)
        summaries.append(summary)

    report = {
        "title": "Indoor Corridor Two-Phase Demo",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "success_dist_m": args.success_dist,
        "n_episodes": len(summaries),
        "arrival_rate": round(sum(1 for s in summaries if s["arrived"]) / max(len(summaries), 1), 4),
        "episodes": summaries,
    }
    report_path = out_dir / "indoor_corridor_demo_20260828.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("Report: %s | arrival=%.0f%%", report_path, 100 * report["arrival_rate"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
