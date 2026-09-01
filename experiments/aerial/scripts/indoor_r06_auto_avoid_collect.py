#!/usr/bin/env python3
"""Auto R06 avoid collector — depth-reactive stand-in for human teleop.

Cannot keyboard-fly remotely; this script flies R06 with body-PD + depth
strafe (prefer right) and writes the same NPZ schema as fixture/teleop.

Declared assist=depth_reactive — NOT mainline assist=none completion.
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("r06_auto_avoid")

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def body_pd(pos: np.ndarray, yaw: float, goal: np.ndarray, limits: np.ndarray) -> np.ndarray:
    c, s = math.cos(yaw), math.sin(yaw)
    R = np.array([[c, s, 0], [-s, c, 0], [0, 0, 1]], dtype=np.float64)
    rel = R @ (goal - pos)
    a = 0.45 * rel
    a = np.array([a[0], a[1], a[2], 0.0], dtype=np.float64)
    lim = np.asarray(limits, dtype=np.float64)
    a[:3] = np.clip(a[:3], -lim[:3], lim[:3])
    a[3] = float(np.clip(0.5 * math.atan2(rel[1], max(rel[0], 1e-3)), -lim[3], lim[3]))
    return a


def depth_bands(depth: Optional[np.ndarray]) -> Tuple[float, float, float]:
    """Return (front_min, left_min, right_min) in meters; nan if missing."""
    if depth is None:
        return float("nan"), float("nan"), float("nan")
    d = np.asarray(depth, dtype=np.float64)
    if d.ndim != 2:
        return float("nan"), float("nan"), float("nan")
    h, w = d.shape
    fin = np.isfinite(d) & (d > 0.05) & (d < 40.0)
    if not fin.any():
        return float("nan"), float("nan"), float("nan")

    def _min(roi: np.ndarray) -> float:
        m = roi[np.isfinite(roi) & (roi > 0.05) & (roi < 40.0)]
        return float(np.min(m)) if m.size else float("nan")

    y0, y1 = int(0.35 * h), int(0.75 * h)
    front = _min(d[y0:y1, int(0.35 * w) : int(0.65 * w)])
    left = _min(d[y0:y1, int(0.05 * w) : int(0.35 * w)])
    right = _min(d[y0:y1, int(0.65 * w) : int(0.95 * w)])
    return front, left, right


class ReactivePilot:
    """Seek goal; if stuck in front of obstacle, force a lateral detour waypoint."""

    def __init__(
        self,
        *,
        danger_m: float = 2.4,
        stop_m: float = 1.2,
        prefer_right: bool = True,
        stuck_steps: int = 20,
        detour_steps: int = 50,
        detour_m: float = 2.2,
    ) -> None:
        self.danger_m = danger_m
        self.stop_m = stop_m
        self.prefer_right = prefer_right
        self.stuck_steps = stuck_steps
        self.detour_steps = detour_steps
        self.detour_m = detour_m
        self._best_d = float("inf")
        self._no_progress = 0
        self._detour_left = 0
        self._detour_goal: Optional[np.ndarray] = None

    def reset(self) -> None:
        self._best_d = float("inf")
        self._no_progress = 0
        self._detour_left = 0
        self._detour_goal = None

    def act(
        self,
        pos: np.ndarray,
        yaw: float,
        goal: np.ndarray,
        depth: Optional[np.ndarray],
        limits: np.ndarray,
    ) -> np.ndarray:
        lim = np.asarray(limits, dtype=np.float64)
        d_goal = float(np.linalg.norm(goal - pos))
        if d_goal + 0.05 < self._best_d:
            self._best_d = d_goal
            self._no_progress = 0
        else:
            self._no_progress += 1

        front, left, right = depth_bands(depth)
        blocked = (not math.isnan(front)) and front < self.danger_m

        go_right = self.prefer_right
        if not math.isnan(left) and not math.isnan(right):
            go_right = right >= left - 0.15  # slight right bias
        elif not math.isnan(left) and math.isnan(right):
            go_right = False
        elif math.isnan(left) and not math.isnan(right):
            go_right = True

        # Enter forced detour if blocked and not making progress
        if (
            self._detour_left <= 0
            and blocked
            and self._no_progress >= self.stuck_steps
            and d_goal > 0.8
        ):
            c, s = math.cos(yaw), math.sin(yaw)
            # body right = (+sin? in ENU body: x fwd, y left typically for our body_pd)
            # body_pd uses R = [[c,s,0],[-s,c,0]] so body y = left. Right = -body_y world.
            right_world = np.array([s, -c, 0.0], dtype=np.float64)  # body -y
            if not go_right:
                right_world = -right_world
            fwd_world = np.array([c, s, 0.0], dtype=np.float64)
            self._detour_goal = pos + self.detour_m * right_world + 0.6 * fwd_world
            self._detour_goal[2] = goal[2]
            self._detour_left = self.detour_steps
            self._no_progress = 0
            logger.info(
                "force detour -> %s (front=%.2f d_goal=%.2f side=%s)",
                np.round(self._detour_goal, 2).tolist(),
                front,
                d_goal,
                "R" if go_right else "L",
            )

        target = goal
        if self._detour_left > 0 and self._detour_goal is not None:
            target = self._detour_goal
            self._detour_left -= 1
            if float(np.linalg.norm(self._detour_goal - pos)) < 0.45:
                self._detour_left = 0
                self._detour_goal = None

        a = body_pd(pos, yaw, target, limits)

        if blocked and self._detour_left <= 0:
            scale = max(0.0, (front - self.stop_m) / max(self.danger_m - self.stop_m, 1e-3))
            a[0] = float(np.clip(a[0] * scale, -lim[0], lim[0]))
            if front < self.stop_m:
                a[0] = float(-0.6 * lim[0])
            strafe = lim[1] if go_right else -lim[1]
            a[1] = float(np.clip(0.35 * a[1] + 0.85 * strafe, -lim[1], lim[1]))
            a[3] = float(
                np.clip(a[3] + (0.55 * lim[3] if go_right else -0.55 * lim[3]), -lim[3], lim[3])
            )

        # While on forced detour, keep some forward if open
        if self._detour_left > 0 and not math.isnan(front) and front > self.stop_m:
            a[0] = float(np.clip(max(a[0], 0.45 * lim[0]), -lim[0], lim[0]))

        return a


def _lateral_offset_m(traj: np.ndarray, start: np.ndarray, goal: np.ndarray) -> float:
    if len(traj) < 2:
        return 0.0
    chord = goal - start
    chord_len = float(np.linalg.norm(chord[:2]))
    if chord_len < 1e-3:
        return 0.0
    u = chord[:2] / chord_len
    perp = np.array([-u[1], u[0]], dtype=np.float64)
    offsets = [abs(float(perp @ (p[:2] - start[:2]))) for p in traj]
    return float(max(offsets)) if offsets else 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--annotation", default="artifacts/building99_indoor_short_routes.json")
    ap.add_argument("--route-idx", type=int, default=5)
    ap.add_argument("--out", required=True)
    ap.add_argument("--episodes", type=int, default=80)
    ap.add_argument("--success-dist", type=float, default=0.25)
    ap.add_argument("--max-steps", type=int, default=280)
    ap.add_argument("--min-usable", type=int, default=8)
    ap.add_argument("--danger-m", type=float, default=2.4)
    ap.add_argument("--stop-m", type=float, default=1.2)
    ap.add_argument("--bc-tag", default="depth_reactive_r06_e2i_e")
    ap.add_argument("--prefer-left", action="store_true")
    args = ap.parse_args()

    from experiments.aerial.rl import dataset as ds
    from experiments.aerial.rl.buffer import Transition
    from experiments.aerial.rl.env.airsim_env import AirSimDroneEnv, AirSimEnvConfig
    from experiments.aerial.rl.reward import NavigationReward, RewardConfig

    root = _ROOT
    ann = Path(args.annotation) if Path(args.annotation).is_absolute() else root / args.annotation
    routes = json.loads(ann.read_text(encoding="utf-8"))
    r = routes[args.route_idx]
    pos = np.asarray(r["pos"], dtype=np.float64)
    yaw = np.asarray(r["yaw"], dtype=np.float64).reshape(-1)
    start, goal = pos[0], pos[-1]
    seg = {
        "source_route_idx": args.route_idx,
        "route_name": r.get("trajectory_id", f"R{args.route_idx+1:02d}"),
        "segment_name": f"AutoAvoid_{r.get('trajectory_id', f'R{args.route_idx+1:02d}')}",
        "pos": [start.tolist(), goal.tolist()],
        "yaw": [float(yaw[0]), float(yaw[min(len(yaw) - 1, len(pos) - 1)])],
        "d0_m": round(float(np.linalg.norm(goal - start)), 3),
        "gpt_instruction": r.get("gpt_instruction", "R06 auto avoid"),
    }

    cfg = AirSimEnvConfig(
        host="127.0.0.1",
        port=41451,
        vehicle=os.environ.get("AIRSIM_VEHICLE", "drone_1"),
        camera=os.environ.get("AIRSIM_CAMERA", "0"),
        grab_depth=True,
        step_hz=5.0,
        health_check=False,
    )
    env = AirSimDroneEnv(cfg)
    limits = np.array([0.12, 0.10, 0.06, 0.12], dtype=np.float64)  # slightly more lateral
    reward_cfg = RewardConfig(success_dist_m=float(args.success_dist))
    out_dir = Path(args.out) if Path(args.out).is_absolute() else root / args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest: List[Dict[str, Any]] = []
    reports: List[Dict[str, Any]] = []
    quality: List[Dict[str, Any]] = []
    ep_idx = 0
    skipped = 0
    prefer_right = not args.prefer_left
    pilot = ReactivePilot(
        danger_m=args.danger_m,
        stop_m=args.stop_m,
        prefer_right=prefer_right,
        stuck_steps=18,
        detour_steps=55,
        detour_m=2.4,
    )

    try:
        for i in range(args.episodes):
            obs = env.reset(
                {"pos": seg["pos"], "yaw": seg["yaw"], "gpt_instruction": seg["gpt_instruction"]}
            )
            if obs is None or getattr(obs, "rgb", None) is None:
                skipped += 1
                continue
            obs.info["goal"] = goal.tolist()
            reward_fn = NavigationReward(goal, reward_cfg)
            reward_fn.reset(goal, obs.position)
            transitions: List[Any] = []
            positions = [np.asarray(obs.position, dtype=np.float64).copy()]
            pilot.reset()
            step_i = 0
            for step_i in range(args.max_steps):
                action = pilot.act(
                    np.asarray(obs.position, dtype=np.float64),
                    float(obs.yaw),
                    goal,
                    getattr(obs, "depth", None),
                    limits,
                )
                next_obs, info = env.step(action)
                next_obs.info["goal"] = goal.tolist()
                rwd, done, terms = reward_fn.step(next_obs, action)
                transitions.append(
                    Transition(
                        obs=obs,
                        action=action,
                        reward=rwd,
                        done=done,
                        next_obs=next_obs,
                        info={
                            **info,
                            **terms,
                            "intervention": False,
                            "goal": goal.tolist(),
                            "assist": "depth_reactive",
                        },
                    )
                )
                obs = next_obs
                positions.append(np.asarray(obs.position, dtype=np.float64).copy())
                d = float(np.linalg.norm(np.asarray(obs.position) - goal))
                if d <= args.success_dist or bool(getattr(obs, "collided", False)):
                    break

            d_end = float(np.linalg.norm(np.asarray(obs.position) - goal))
            coll = bool(getattr(obs, "collided", False))
            arrived = d_end <= args.success_dist and not coll
            lat = _lateral_offset_m(np.asarray(positions), start, goal)
            if not arrived:
                skipped += 1
                logger.info(
                    "drop i=%d d_end=%.2f coll=%s lateral=%.2f steps=%d",
                    i,
                    d_end,
                    coll,
                    lat,
                    step_i + 1,
                )
                continue

            path = ds.write_episode(out_dir, ep_idx, transitions)
            qrep = ds.quality_report(transitions)
            usable = not ds.assert_nontrivial(qrep) and not ds.quarantine_reasons(qrep)
            rep = {
                "ok": True,
                "segment_name": seg["segment_name"],
                "route_name": seg["route_name"],
                "source_route_idx": seg["source_route_idx"],
                "steps": step_i + 1,
                "d0_m": seg["d0_m"],
                "d_end_m_gt": round(d_end, 4),
                "arrived_gt": True,
                "collided": False,
                "lateral_offset_m": round(lat, 3),
                "assist": "depth_reactive",
                "bc_tag": args.bc_tag,
                "scene": "Building_99",
                "pose_source": "gt_proxy",
            }
            logger.info(
                "SAVE ep %d d_end=%.2f lateral=%.2f usable=%s -> %s",
                ep_idx,
                d_end,
                lat,
                usable,
                path.name,
            )
            manifest.append(
                {
                    "file": path.name,
                    "steps": qrep["steps"],
                    "segment_name": rep["segment_name"],
                    "route_name": rep["route_name"],
                    "source_route_idx": rep["source_route_idx"],
                    "d_end_m_gt": rep["d_end_m_gt"],
                    "arrived_gt": True,
                    "lateral_offset_m": rep["lateral_offset_m"],
                    "usable": usable,
                }
            )
            quality.append(qrep)
            reports.append({**qrep, **rep})
            ep_idx += 1
            if sum(1 for m in manifest if m.get("usable")) >= args.min_usable:
                logger.info("hit min_usable=%d early stop", args.min_usable)
                break
    finally:
        try:
            env.close()
        except Exception:
            pass

    usable_n = sum(1 for m in manifest if m.get("usable"))
    meta = {
        "protocol": "indoor_depth_reactive_E2i_e_r06",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "scene": "Building_99",
        "annotation": str(ann),
        "route_idx": args.route_idx,
        "assist": "depth_reactive",
        "bc_tag": args.bc_tag,
        "pose_source": "gt_proxy",
        "success_dist_m": args.success_dist,
        "n_requested": args.episodes,
        "n_collected": len(manifest),
        "n_usable": usable_n,
        "skipped": skipped,
        "note": "Auto depth-reactive R06 avoid; stand-in for human teleop. NOT assist=none completion.",
    }
    ds.write_manifest(out_dir, manifest, meta=meta)
    ds.write_quality_summary(out_dir, quality)
    summary = {
        **meta,
        "arrival_rate_gt": round(usable_n / max(usable_n + skipped, 1), 4),
        "mean_d_end_gt": round(float(np.mean([r["d_end_m_gt"] for r in reports])), 4) if reports else None,
        "mean_lateral_offset_m": round(float(np.mean([r["lateral_offset_m"] for r in reports])), 4)
        if reports
        else None,
        "episodes": reports,
    }
    (out_dir / "collection_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    logger.info("done usable=%d skipped=%d -> %s", usable_n, skipped, out_dir)
    return 0 if usable_n >= args.min_usable else 2


if __name__ == "__main__":
    raise SystemExit(main())
