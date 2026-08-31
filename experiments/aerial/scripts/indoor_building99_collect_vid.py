#!/usr/bin/env python3
"""Collect short indoor flights on Building_99 with ego videos + near-depth gate.

Declared fixture assist: gt_pd (not mainline completion). For E2h scene/data preview only.
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
from typing import Any, Dict, List

import cv2
import numpy as np

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("b99_collect")


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


def _overlay(rgb: np.ndarray, *, step: int, d: float, dmin: float, phase: str) -> np.ndarray:
    bgr = rgb[..., ::-1].copy()
    if max(bgr.shape[:2]) < 400:
        bgr = cv2.resize(bgr, (bgr.shape[1] * 3, bgr.shape[0] * 3), interpolation=cv2.INTER_NEAREST)
    h, w = bgr.shape[:2]
    cv2.putText(
        bgr,
        f"Building99  step={step:03d}  d={d:.2f}m  depth_min={dmin:.2f}m",
        (10, 26),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (240, 240, 240),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(bgr, phase, (10, 52), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (80, 200, 255), 2, cv2.LINE_AA)
    if d <= 0.5:
        cv2.putText(
            bgr,
            "NEAR GOAL",
            (w // 2 - 80, h // 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (40, 230, 90),
            3,
            cv2.LINE_AA,
        )
    return bgr


def _depth_min(env, obs) -> float:
    depth = getattr(obs, "depth", None)
    if depth is None:
        try:
            client = env._client or env._connect()
            depth = env._grab_depth(client)
        except Exception:
            return float("nan")
    if depth is None:
        return float("nan")
    d = np.asarray(depth, dtype=np.float64)
    fin = np.isfinite(d) & (d > 0)
    return float(np.nanmin(d[fin])) if fin.any() else float("nan")


def build_segments(n: int, alt: float = 1.5, leg: float = 3.0) -> List[Dict[str, Any]]:
    """Procedural short legs near Building_99 spawn (hallway-safe offsets)."""
    # Prefer lateral/forward starts that previously avoided wall-embed spawn.
    starts = [
        (0.0, 0.0, 0.0),
        (0.0, 1.0, math.pi / 2),
        (1.0, 0.0, 0.0),
        (0.0, -1.0, -math.pi / 2),
        (-0.5, 0.5, math.pi / 4),
        (0.5, -0.5, -math.pi / 4),
    ]
    segs = []
    for i in range(n):
        sx, sy, yaw = starts[i % len(starts)]
        c, s = math.cos(yaw), math.sin(yaw)
        start = np.array([sx, sy, alt], dtype=np.float64)
        goal = start + np.array([leg * c, leg * s, 0.0])
        segs.append(
            {
                "segment_name": f"B99_leg_{i:02d}",
                "pos": [start.tolist(), goal.tolist()],
                "yaw": [yaw, yaw],
                "d0_m": round(float(np.linalg.norm(goal - start)), 3),
                "gpt_instruction": f"indoor Building_99 short leg {i}",
            }
        )
    return segs


def body_pd(pos, yaw, goal, limits) -> np.ndarray:
    c, s = math.cos(yaw), math.sin(yaw)
    R = np.array([[c, s, 0], [-s, c, 0], [0, 0, 1]], dtype=np.float64)
    rel_body = R @ (goal - pos)
    a = 0.35 * rel_body
    a = np.array([a[0], a[1], a[2], 0.0], dtype=np.float64)
    lim = np.asarray(limits, dtype=np.float64)
    a[:3] = np.clip(a[:3], -lim[:3], lim[:3])
    a[3] = float(np.clip(0.4 * math.atan2(rel_body[1], max(rel_body[0], 1e-3)), -lim[3], lim[3]))
    return a


def run_ep(env, seg, *, max_steps, success_dist, limits) -> Dict[str, Any]:
    goal = np.asarray(seg["pos"][1], dtype=np.float64)
    obs = env.reset({"pos": seg["pos"], "yaw": seg["yaw"], "gpt_instruction": seg["gpt_instruction"]})
    if obs is None or getattr(obs, "rgb", None) is None:
        return {"ok": False, "reason": "reset_failed", "segment_name": seg["segment_name"], "frames": []}
    # Stale collision flag on teleport is common; only abort if RGB is dead-black.
    rgb0 = np.asarray(obs.rgb)
    if float(rgb0.mean()) < 1.0:
        return {"ok": False, "reason": "black_rgb", "segment_name": seg["segment_name"], "frames": []}

    frames: List[np.ndarray] = []
    dmins: List[float] = []
    step_i = 0
    for step_i in range(max_steps):
        pos = np.asarray(obs.position, dtype=np.float64)
        yaw = float(obs.yaw)
        action = body_pd(pos, yaw, goal, limits)
        next_obs, _ = env.step(action)
        obs = next_obs
        d = float(np.linalg.norm(np.asarray(obs.position) - goal))
        dmin = _depth_min(env, obs)
        dmins.append(dmin)
        frames.append(
            _overlay(
                np.asarray(obs.rgb),
                step=step_i,
                d=d,
                dmin=dmin if not math.isnan(dmin) else -1,
                phase="gt_pd_indoor",
            )
        )
        if d <= success_dist or bool(getattr(obs, "collided", False)):
            break

    d_end = float(np.linalg.norm(np.asarray(obs.position) - goal))
    finite = [x for x in dmins if not math.isnan(x)]
    return {
        "ok": True,
        "segment_name": seg["segment_name"],
        "steps": step_i + 1,
        "d0_m": seg["d0_m"],
        "d_end_m": round(d_end, 4),
        "arrived": d_end <= success_dist,
        "collided": bool(getattr(obs, "collided", False)),
        "depth_min_median_m": round(float(np.median(finite)), 3) if finite else None,
        "near_depth_frac": round(float(np.mean([x < 3.0 for x in finite])), 3) if finite else None,
        "frames": frames,
        "assist": "gt_pd_declared",
        "scene": "Building_99",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--episodes", type=int, default=4)
    ap.add_argument("--success-dist", type=float, default=0.50)
    ap.add_argument("--max-steps", type=int, default=120)
    ap.add_argument("--leg-m", type=float, default=3.0)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=41451)
    ap.add_argument("--vehicle", default="drone_1")
    ap.add_argument("--camera", default="0")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(root))
    from experiments.aerial.rl.env.airsim_env import AirSimDroneEnv, AirSimEnvConfig

    cfg = AirSimEnvConfig(
        host=args.host,
        port=args.port,
        vehicle=args.vehicle,
        camera=args.camera,
        grab_depth=True,
        step_hz=5.0,
        health_check=False,
    )
    env = AirSimDroneEnv(cfg)
    limits = np.array([0.15, 0.08, 0.08, 0.10], dtype=np.float64)
    segs = build_segments(args.episodes, alt=1.5, leg=args.leg_m)
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = root / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for seg in segs:
        logger.info("--- %s ---", seg["segment_name"])
        rep = run_ep(env, seg, max_steps=args.max_steps, success_dist=args.success_dist, limits=limits)
        frames = rep.pop("frames", [])
        if rep.get("ok") and frames:
            mp4 = out_dir / f"{seg['segment_name']}_ego.mp4"
            _write_mp4(frames, mp4, fps=5.0)
            rep["ego_mp4"] = str(mp4)
            logger.info(
                "%s d_end=%.3f arrived=%s depth_med=%s -> %s",
                seg["segment_name"],
                rep["d_end_m"],
                rep["arrived"],
                rep.get("depth_min_median_m"),
                mp4,
            )
        else:
            logger.warning("%s fail: %s", seg["segment_name"], rep.get("reason"))
        results.append(rep)

    summary = {
        "title": "Building_99 indoor short collect + video",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "n": len(results),
        "n_ok": sum(1 for r in results if r.get("ok")),
        "n_arrived": sum(1 for r in results if r.get("arrived")),
        "episodes": results,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    logger.info("summary %s", out_dir / "summary.json")
    try:
        env.close()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
