#!/usr/bin/env python3
"""Indoor multi-waypoint corridor chain (30–50 m) under Two-Phase WAM+IBVS.

Chains successive ~10–12 m legs along a low-altitude OpenFly route without
teleporting between legs. Records continuous ego / map / dual videos.

Usage on 125 (public SSH preferred):
  source experiments/aerial/scripts/env_4090.sh
  $AERIAL_PY experiments/aerial/scripts/indoor_multiwaypoint_demo.py \
    --route-idx 6 \
    --target-path-m 40 \
    --leg-len-m 10 \
    --success-dist 0.20 \
    --out-dir artifacts/videos/indoor_multiwaypoint
"""
from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
import yaml

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("indoor_multiwaypoint")


def _goal_dist(pos: np.ndarray, goal: np.ndarray) -> float:
    return float(np.linalg.norm(np.asarray(goal, dtype=np.float64).reshape(3) - np.asarray(pos, dtype=np.float64).reshape(3)))


def _write_frames_ffmpeg(frames: List[np.ndarray], out_mp4: Path, *, fps: float = 5.0) -> None:
    if not frames:
        raise ValueError("no frames")
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
        proc.stdin.write(np.ascontiguousarray(fr.astype(np.uint8)).tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError(f"ffmpeg failed for {out_mp4}")


def build_waypoints(
    route: Dict[str, Any],
    *,
    leg_len_m: float = 10.0,
    target_path_m: float = 40.0,
) -> Dict[str, Any]:
    """Dense waypoints: resample A* path every ``leg_len_m`` along arc length."""
    pos = np.asarray(route["pos"], dtype=np.float64)
    yaw = np.asarray(route["yaw"], dtype=np.float64)
    # densify to ~1 m samples for stable arc-length resampling
    sample_m = 1.0
    dense_pos: List[np.ndarray] = [pos[0].copy()]
    dense_yaw: List[float] = [float(yaw[0])]
    for i in range(1, len(pos)):
        a, b = pos[i - 1], pos[i]
        ya, yb = float(yaw[i - 1]), float(yaw[i])
        edge = float(np.linalg.norm(b - a))
        n_div = max(1, int(np.ceil(edge / sample_m)))
        dy = yb - ya
        dy = (dy + np.pi) % (2 * np.pi) - np.pi
        for k in range(1, n_div + 1):
            t = k / n_div
            dense_pos.append((1.0 - t) * a + t * b)
            dense_yaw.append(ya + t * dy)
    # arc-length waypoints
    wps: List[np.ndarray] = [dense_pos[0].copy()]
    wyaws: List[float] = [dense_yaw[0]]
    since = 0.0
    total = 0.0
    for i in range(1, len(dense_pos)):
        step = float(np.linalg.norm(dense_pos[i] - dense_pos[i - 1]))
        since += step
        total += step
        if since >= leg_len_m or i == len(dense_pos) - 1:
            wps.append(dense_pos[i].copy())
            wyaws.append(float(dense_yaw[i]))
            since = 0.0
        if total >= target_path_m and len(wps) >= 3:
            if not np.allclose(wps[-1], dense_pos[i]):
                wps.append(dense_pos[i].copy())
                wyaws.append(float(dense_yaw[i]))
            break
    if len(wps) < 3:
        mid = min(len(dense_pos) - 1, max(1, len(dense_pos) // 2))
        wps = [dense_pos[0], dense_pos[mid], dense_pos[-1]]
        wyaws = [dense_yaw[0], dense_yaw[mid], dense_yaw[-1]]
    path_len = float(sum(np.linalg.norm(b - a) for a, b in zip(wps[:-1], wps[1:])))
    return {
        "waypoints": [p.tolist() for p in wps],
        "yaws": wyaws,
        "n_legs": len(wps) - 1,
        "path_len_m": round(path_len, 3),
        "astar_pos": pos.tolist(),
        "gpt_instruction": (route.get("gpt_instruction", "")[:100] + " (multi-waypoint)"),
    }


def _draw_ego_hud(
    rgb: np.ndarray,
    *,
    step: int,
    leg: int,
    n_legs: int,
    d_goal: float,
    phase: str,
    z: float,
    intervened: bool,
    path_progress: float,
    leg_arrived: bool,
) -> np.ndarray:
    frame = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR) if rgb.shape[-1] == 3 else rgb.copy()
    h, w = frame.shape[:2]
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 78), (20, 20, 20), -1)
    cv2.rectangle(overlay, (0, h - 36), (w, h), (20, 20, 20), -1)
    frame = cv2.addWeighted(overlay, 0.55, frame, 0.45, 0)
    phase_col = (80, 220, 120) if "SERVO" in phase else (80, 180, 255)
    cv2.putText(frame, f"STEP {step:03d} | LEG {leg}/{n_legs} | d={d_goal:.2f}m | z={z:.2f}m",
                (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (240, 240, 240), 1, cv2.LINE_AA)
    cv2.putText(frame, phase, (12, 58), cv2.FONT_HERSHEY_SIMPLEX, 0.55, phase_col, 2, cv2.LINE_AA)
    if intervened:
        cv2.putText(frame, "SHIELD", (w - 120, 58), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (40, 40, 255), 2, cv2.LINE_AA)
    bar_w = int((w - 24) * max(0.0, min(1.0, path_progress)))
    cv2.rectangle(frame, (12, h - 24), (w - 12, h - 12), (60, 60, 60), -1)
    cv2.rectangle(frame, (12, h - 24), (12 + bar_w, h - 12), (60, 200, 90), -1)
    if leg_arrived:
        cv2.putText(frame, f"WP{leg} OK", (w // 2 - 60, h // 2), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (40, 230, 90), 3, cv2.LINE_AA)
    return frame


def _render_map(
    flown: np.ndarray,
    astar: np.ndarray,
    waypoints: np.ndarray,
    active_goal: np.ndarray,
    size: Tuple[int, int] = (720, 720),
) -> np.ndarray:
    w, h = size
    canvas = np.full((h, w, 3), 28, dtype=np.uint8)
    pts = [astar, waypoints, active_goal.reshape(1, 3)]
    if flown.size:
        pts.append(flown)
    xy = np.vstack(pts)[:, :2]
    mn = xy.min(axis=0) - 2.0
    mx = xy.max(axis=0) + 2.0
    span = np.maximum(mx - mn, 1e-3)

    def proj(p: np.ndarray) -> Tuple[int, int]:
        u = int((p[0] - mn[0]) / span[0] * (w - 40) + 20)
        v = int((1.0 - (p[1] - mn[1]) / span[1]) * (h - 40) + 20)
        return u, v

    for g in range(0, w, 40):
        cv2.line(canvas, (g, 0), (g, h), (40, 40, 40), 1)
    for g in range(0, h, 40):
        cv2.line(canvas, (0, g), (w, g), (40, 40, 40), 1)
    if len(astar) >= 2:
        poly = np.array([proj(p) for p in astar], dtype=np.int32)
        cv2.polylines(canvas, [poly], False, (70, 70, 70), 2, cv2.LINE_AA)
    if len(waypoints) >= 2:
        poly = np.array([proj(p) for p in waypoints], dtype=np.int32)
        cv2.polylines(canvas, [poly], False, (180, 180, 80), 2, cv2.LINE_AA)
    for i, wp in enumerate(waypoints):
        col = (80, 220, 120) if i == 0 else ((40, 40, 255) if i == len(waypoints) - 1 else (200, 160, 40))
        cv2.circle(canvas, proj(wp), 8, col, -1 if i in (0, len(waypoints) - 1) else 2, cv2.LINE_AA)
        cv2.putText(canvas, f"W{i}", (proj(wp)[0] + 6, proj(wp)[1] - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, col, 1, cv2.LINE_AA)
    if len(flown) >= 2:
        poly = np.array([proj(p) for p in flown], dtype=np.int32)
        cv2.polylines(canvas, [poly], False, (60, 200, 255), 2, cv2.LINE_AA)
        cv2.circle(canvas, proj(flown[-1]), 7, (40, 180, 255), -1, cv2.LINE_AA)
    cv2.circle(canvas, proj(active_goal), 12, (40, 40, 255), 2, cv2.LINE_AA)
    cv2.putText(canvas, "MULTI-WAYPOINT MAP", (16, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (220, 220, 220), 1, cv2.LINE_AA)
    return canvas


def _compose_dual(ego: np.ndarray, mp: np.ndarray, out_size: Tuple[int, int] = (1440, 720)) -> np.ndarray:
    ow, oh = out_size
    half = ow // 2
    return np.concatenate([
        cv2.resize(ego, (half, oh)),
        cv2.resize(mp, (ow - half, oh)),
    ], axis=1)


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
        self.last_phase = "INIT"
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

    def set_goal(self, target_pos: np.ndarray, target_yaw: float, obs: Any) -> None:
        self.goal_pos = np.asarray(target_pos, dtype=np.float64)
        self.goal_yaw = float(target_yaw)
        # retarget altitude lock to new waypoint height without wiping odom tracker
        self.two_phase_ctrl.alt_ctrl.reset(float(self.goal_pos[2]))

    def act(self, view: Any) -> np.ndarray:
        raw_wam = self.base_policy.act(view)
        from experiments.aerial.rl.env.obs import Observation
        cur_state = np.array(
            [view.proprio[0], view.proprio[1], view.proprio[2], 0, 0, 0, view.proprio[3]],
            dtype=np.float32,
        )
        full_obs = Observation(rgb=view.rgb, state=cur_state, t=view.t)
        assert self.goal_pos is not None
        final_action, phase, _ = self.two_phase_ctrl.arbitrate_action(
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Indoor multi-waypoint corridor chain demo")
    parser.add_argument("--config", default="configs/aerial_rl_indoor_lossless.yaml")
    parser.add_argument("--wm-ckpt", default="experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt")
    parser.add_argument("--actor-ckpt", default="experiments/aerial/rl/artifacts/v4_ac_ckpt_step_e_20260828/v4_ac_latest.pt")
    parser.add_argument("--depth-ckpt", default="experiments/aerial/rl/artifacts/depth_ckpt_p45mid_s8j_20260825/depth_best_holdout_da3_ft_head.pt")
    parser.add_argument("--annotation", default="artifacts/seen_airsim16_m1a20.json")
    parser.add_argument("--route-idx", type=int, default=6, help="0-based route index (6=Route07)")
    parser.add_argument("--leg-len-m", type=float, default=10.0)
    parser.add_argument("--target-path-m", type=float, default=40.0)
    parser.add_argument("--max-steps-per-leg", type=int, default=200)
    parser.add_argument("--success-dist", type=float, default=0.20)
    parser.add_argument("--fps", type=float, default=5.0)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--out-dir", default="artifacts/videos/indoor_multiwaypoint")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from experiments.aerial.rl.actor_critic import LatentActorCritic, LatentActorDeployPolicy
    from experiments.aerial.rl.collector import act_delta, clip_body_delta
    from experiments.aerial.rl.depth_predictor import DepthMinPredictor
    from experiments.aerial.rl.goal_features import body_vel_from_obs, goal_rel_from_obs
    from experiments.aerial.rl.planner import ImaginationPlanner
    from experiments.aerial.rl.reward import RewardConfig
    from experiments.aerial.rl.safety import ThreeZoneSpeedShield
    from experiments.aerial.rl.three_zone import ThreeZoneSpec
    from experiments.aerial.rl.train_rl import _build_env, load_torch_dynamics

    ann_path = Path(args.annotation) if Path(args.annotation).is_absolute() else root / args.annotation
    routes = json.loads(ann_path.read_text(encoding="utf-8"))
    route = routes[int(args.route_idx)]
    mission = build_waypoints(route, leg_len_m=args.leg_len_m, target_path_m=args.target_path_m)
    wps = np.asarray(mission["waypoints"], dtype=np.float64)
    wyaws = mission["yaws"]
    astar = np.asarray(mission["astar_pos"], dtype=np.float64)
    n_legs = int(mission["n_legs"])
    logger.info("Route %02d -> %d waypoints / %d legs / path=%.1fm",
                args.route_idx + 1, len(wps), n_legs, mission["path_len_m"])

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

    limits = np.array([0.15, 0.08, 0.08, 0.10], dtype=np.float64)
    shield = ThreeZoneSpeedShield(
        zone=ThreeZoneSpec(l1_m=1.5, l2_m=0.8, l3_m=0.4, v1_m_s=0.6, v2_m_s=0.3, v_stop_m_s=0.05, v_cruise_m_s=1.0, dt_s=0.2),
        retreat_step_m=0.3, min_tau_s=0.5,
    )
    planner = ImaginationPlanner(dynamics=dynamics, horizon=5, reward_cfg=reward_cfg, action_limits=limits)
    policy = TwoPhasePolicyWrapper(base_policy, max_dz=0.08, step_hz=5.0, d_switch=1.2)
    policy.action_limits = limits

    # Spawn at first waypoint
    ep0 = {
        "pos": [wps[0].tolist(), wps[1].tolist()],
        "yaw": [wyaws[0], wyaws[1]],
        "gpt_instruction": mission["gpt_instruction"],
    }
    obs = env.reset(ep0)
    if obs is None or bool(getattr(obs, "collided", False)):
        logger.error("spawn collision at start")
        return 1
    # ensure goal info for reward/goal_rel
    obs.info["goal"] = wps[1].tolist()
    policy.reset(obs, target_pos=wps[1], target_yaw=wyaws[1])
    if hasattr(shield, "reset"):
        shield.reset()
    latent = np.asarray(dynamics.encode(obs), dtype=np.float64)

    ego_frames: List[np.ndarray] = []
    map_frames: List[np.ndarray] = []
    dual_frames: List[np.ndarray] = []
    flown = [obs.position.copy()]
    leg_reports: List[Dict[str, Any]] = []
    total_steps = 0
    n_interv = 0
    n_servo = 0
    collided = False
    legs_arrived = 0
    path_total = float(mission["path_len_m"])
    path_done = 0.0

    for leg_i in range(1, len(wps)):
        goal = wps[leg_i]
        goal_yaw = float(wyaws[leg_i])
        policy.set_goal(goal, goal_yaw, obs)
        obs.info["goal"] = goal.tolist()
        if hasattr(env, "_goal"):
            env._goal = goal.copy()
        if hasattr(shield, "reset"):
            shield.reset()
        d0 = _goal_dist(obs.position, goal)
        leg_start_steps = total_steps
        arrived = False
        logger.info("=== LEG %d/%d  d0=%.2fm ===", leg_i, n_legs, d0)

        for step_i in range(args.max_steps_per_leg):
            total_steps += 1
            action = act_delta(policy, obs, mission["gpt_instruction"], limits)
            if planner is not None and "SERVO" not in policy.last_phase:
                if callable(getattr(planner, "set_goal", None)):
                    planner.set_goal(goal)
                action = np.asarray(planner.plan(obs, action), dtype=np.float64).reshape(4)
                action = clip_body_delta(action, limits)
                action, phase, _ = policy.two_phase_ctrl.arbitrate_action(
                    obs=obs, wam_action=action, goal_pos=goal, goal_yaw=goal_yaw,
                    action_limits=limits, step_hz=5.0,
                    assist="none", forbid_gt_world_pose_control=True,
                )
                policy.last_phase = phase

            if depth_pred is not None:
                d_min = depth_pred.predict_min(obs)
                if d_min is not None:
                    obs.info["depth_min_pred"] = float(d_min)

            wm_out = dynamics.step(latent, action, goal_rel=goal_rel_from_obs(obs), body_vel=body_vel_from_obs(obs))
            intervened = False
            if shield is not None:
                apply_fn = getattr(shield, "apply_action", None)
                if callable(apply_fn):
                    action, intervened = apply_fn(action, obs, wm_out=wm_out, limits=limits)
                elif shield.should_override(obs, wm_out=wm_out):
                    action = clip_body_delta(shield.override_action(obs), limits)
                    intervened = True
            if intervened:
                n_interv += 1
            if "SERVO" in policy.last_phase:
                n_servo += 1

            next_obs, _ = env.step(action)
            next_obs.info["goal"] = goal.tolist()
            out = dynamics.step(latent, action, goal_rel=goal_rel_from_obs(obs), body_vel=body_vel_from_obs(obs))
            latent = np.asarray(out.z_next, dtype=np.float64)
            flown.append(next_obs.position.copy())

            d_now = _goal_dist(next_obs.position, goal)
            path_progress = min(1.0, (path_done + max(0.0, d0 - d_now)) / max(path_total, 1e-3))
            arrived_now = d_now <= args.success_dist
            ego = _draw_ego_hud(
                next_obs.rgb, step=total_steps, leg=leg_i, n_legs=n_legs,
                d_goal=d_now, phase=policy.last_phase, z=float(next_obs.position[2]),
                intervened=intervened, path_progress=path_progress, leg_arrived=arrived_now,
            )
            mp = _render_map(np.asarray(flown), astar, wps, goal)
            dual = _compose_dual(ego, mp)
            ego_frames.append(ego)
            map_frames.append(mp)
            dual_frames.append(dual)
            obs = next_obs

            if arrived_now:
                arrived = True
                # hold banner a few frames
                for _ in range(3):
                    ego_frames.append(ego)
                    map_frames.append(mp)
                    dual_frames.append(dual)
                break
            if bool(getattr(next_obs, "collided", False)):
                collided = True
                break

        d_end = _goal_dist(obs.position, goal)
        if d_end <= args.success_dist:
            arrived = True
        if arrived:
            legs_arrived += 1
            path_done += d0
        leg_reports.append({
            "leg": leg_i,
            "d0_m": round(d0, 3),
            "d_end_m": round(d_end, 4),
            "steps": total_steps - leg_start_steps,
            "arrived": bool(arrived),
        })
        logger.info("LEG %d done: d_end=%.3fm arrived=%s steps=%d",
                    leg_i, d_end, arrived, total_steps - leg_start_steps)
        if collided or not arrived:
            break

    out_dir = Path(args.out_dir) if Path(args.out_dir).is_absolute() else root / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"mw_route{args.route_idx + 1:02d}"
    ego_path = out_dir / f"{stem}_ego.mp4"
    map_path = out_dir / f"{stem}_map.mp4"
    dual_path = out_dir / f"{stem}_dual.mp4"
    if ego_frames:
        _write_frames_ffmpeg(ego_frames, ego_path, fps=args.fps)
        _write_frames_ffmpeg(map_frames, map_path, fps=args.fps)
        _write_frames_ffmpeg(dual_frames, dual_path, fps=args.fps)

    report = {
        "title": "Indoor Multi-Waypoint Corridor Chain",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "route_idx": args.route_idx,
        "success_dist_m": args.success_dist,
        "n_legs": n_legs,
        "path_len_m": mission["path_len_m"],
        "legs_arrived": legs_arrived,
        "leg_arrival_rate": round(legs_arrived / max(n_legs, 1), 4),
        "mission_complete": bool(legs_arrived == n_legs and not collided),
        "total_steps": total_steps,
        "intervention_rate": round(n_interv / max(total_steps, 1), 4),
        "servo_ratio": round(n_servo / max(total_steps, 1), 4),
        "collided": bool(collided),
        "final_d_to_last_wp_m": round(_goal_dist(obs.position, wps[-1]), 4),
        "legs": leg_reports,
        "ego_mp4": str(ego_path),
        "map_mp4": str(map_path),
        "dual_mp4": str(dual_path),
    }
    report_path = out_dir / f"{stem}_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("Mission complete=%s leg_arrival=%.0f%% steps=%d -> %s",
                report["mission_complete"], 100 * report["leg_arrival_rate"], total_steps, dual_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
