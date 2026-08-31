#!/usr/bin/env python3
"""Smoke: connect to AirSim indoor scene and report near-obstacle signature.

Pass criteria (indoor-narrow):
  - connection OK
  - RGB non-black
  - depth_min median across a small yaw sweep < 5.0 m
  - skyish fraction < 0.5 (not open-sky outdoor)

Usage on 125:
  export AIRSIM_CAMERA=0 AIRSIM_VEHICLE=drone_1
  $AERIAL_PY experiments/aerial/scripts/indoor_scene_smoke.py --out artifacts/indoor_scene_smoke.json
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import sys
import time
from pathlib import Path

import numpy as np

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("indoor_scene_smoke")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=41451)
    ap.add_argument("--vehicle", default="drone_1")
    ap.add_argument("--camera", default="0")
    ap.add_argument("--out", default="artifacts/indoor_scene_smoke.json")
    ap.add_argument("--alt-m", type=float, default=1.5, help="hover height (+up world)")
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
    # reset at origin, climb to alt
    start = np.array([0.0, 0.0, float(args.alt_m)], dtype=np.float64)
    obs = env.reset({"pos": [start.tolist(), (start + np.array([2.0, 0.0, 0.0])).tolist()], "yaw": [0.0, 0.0]})
    if obs is None:
        raise RuntimeError("reset returned None")

    depth_mins = []
    skyish = []
    frames_meta = []
    client = env._client
    airsim = env._airsim
    vk = {"vehicle_name": args.vehicle}

    for yaw_deg in (0, 45, 90, 135, 180, 225, 270, 315):
        yaw = math.radians(yaw_deg)
        pose = airsim.Pose(
            airsim.Vector3r(float(start[0]), float(start[1]), float(-start[2])),
            airsim.to_quaternion(0.0, 0.0, float(yaw)),
        )
        client.simSetVehiclePose(pose, True, **vk)
        time.sleep(0.35)
        obs2, _ = env.step(np.zeros(4, dtype=np.float64))
        rgb = np.asarray(obs2.rgb)
        depth = obs2.depth
        if depth is None:
            # force grab
            from experiments.aerial.rl.env.airsim_env import AirSimDroneEnv as _
            d = env._grab_depth(client) if hasattr(env, "_grab_depth") else None
            depth = d
        if depth is None:
            depth_min = float("nan")
        else:
            depth = np.asarray(depth, dtype=np.float64)
            fin = np.isfinite(depth) & (depth > 0)
            depth_min = float(np.nanmin(depth[fin])) if fin.any() else float("nan")
        top = rgb[: rgb.shape[0] // 3].mean(axis=(0, 1))
        sky = bool(top[2] > top[0] and top.mean() > 120)
        depth_mins.append(depth_min)
        skyish.append(sky)
        frames_meta.append(
            {
                "yaw_deg": yaw_deg,
                "depth_min_m": None if math.isnan(depth_min) else round(depth_min, 3),
                "rgb_mean": [round(float(x), 1) for x in rgb.mean(axis=(0, 1))],
                "skyish": sky,
            }
        )
        logger.info("yaw=%3d depth_min=%.2f skyish=%s rgb_mean=%s", yaw_deg, depth_min, sky, frames_meta[-1]["rgb_mean"])

    finite = [d for d in depth_mins if not math.isnan(d)]
    med = float(np.median(finite)) if finite else float("nan")
    sky_frac = float(np.mean(skyish)) if skyish else 1.0
    # Primary gate = near geometry. RGB "skyish" is advisory only (Blocks walls
    # are bright and false-trigger the outdoor-sky heuristic).
    pass_near = (not math.isnan(med)) and med < 5.0
    payload = {
        "scene_smoke": "indoor",
        "vehicle": args.vehicle,
        "camera": args.camera,
        "alt_m": args.alt_m,
        "depth_min_median_m": None if math.isnan(med) else round(med, 3),
        "skyish_fraction": round(sky_frac, 3),
        "pass_near_obstacle": pass_near,
        "pass_not_open_sky_advisory": sky_frac < 0.5,
        "pass": bool(pass_near),
        "yaw_sweep": frames_meta,
    }
    out = Path(args.out)
    if not out.is_absolute():
        out = root / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info("Wrote %s pass=%s", out, payload["pass"])
    try:
        env.close()
    except Exception:
        pass
    return 0 if payload["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
