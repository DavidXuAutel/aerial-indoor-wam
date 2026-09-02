#!/usr/bin/env python3
"""Audit Building_99 short-route start/goal clearance; emit a clean annotation.

Drops:
  * start: collide after teleport, or forward depth_min < --min-start-clearance-m
  * goal:  min depth over yaw sweep < --min-goal-clearance-m (endpoint too near wall)

Usage (125):
  source experiments/aerial/scripts/env_4090.sh
  $AERIAL_PY experiments/aerial/scripts/indoor_route_clearance_audit.py \\
    --annotation artifacts/building99_indoor_short_routes.json \\
    --out-annotation artifacts/building99_indoor_short_routes_clean_sg.json \\
    --out-report artifacts/building99_route_clearance_audit_20260901.json
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("route_clearance_audit")


def _depth_min(env, client, airsim, vehicle: str) -> Tuple[float, bool]:
    vk = {"vehicle_name": vehicle}
    # zero step to refresh obs
    obs, _ = env.step(np.zeros(4, dtype=np.float64))
    coll = bool(getattr(obs, "collided", False))
    depth = getattr(obs, "depth", None)
    if depth is None and hasattr(env, "_grab_depth"):
        depth = env._grab_depth(client)
    if depth is None:
        return float("nan"), coll
    d = np.asarray(depth, dtype=np.float64)
    fin = np.isfinite(d) & (d > 0) & (d < 100)
    if not fin.any():
        return float("nan"), coll
    return float(np.min(d[fin])), coll


def _set_pose(client, airsim, vehicle: str, xyz: np.ndarray, yaw: float) -> None:
    pose = airsim.Pose(
        airsim.Vector3r(float(xyz[0]), float(xyz[1]), float(-xyz[2])),
        airsim.to_quaternion(0.0, 0.0, float(yaw)),
    )
    client.simSetVehiclePose(pose, True, vehicle_name=vehicle)
    time.sleep(0.4)


def audit_start_reset(
    env,
    start: np.ndarray,
    yaw0: float,
    *,
    nudge_forward: bool = False,
) -> Dict[str, Any]:
    """Reset via env (spawn retry) and optional forward micro-nudge."""
    start = np.asarray(start, dtype=np.float64).reshape(3)
    obs = env.reset({
        "pos": [start.tolist(), start.tolist()],
        "yaw": [float(yaw0), float(yaw0)],
        "gpt_instruction": "clearance audit",
    })
    z = float(np.asarray(obs.position, dtype=np.float64).reshape(3)[2])
    coll = bool(getattr(obs, "collided", False))
    depth = getattr(obs, "depth", None)
    dmin = _depth_min(depth)
    nudge_coll = False
    if nudge_forward and not coll:
        obs, _ = env.step(np.array([0.12, 0.0, 0.0, 0.0], dtype=np.float64))
        nudge_coll = bool(getattr(obs, "collided", False))
        if not nudge_coll:
            obs, _ = env.step(np.array([0.12, 0.0, 0.0, 0.0], dtype=np.float64))
            nudge_coll = bool(getattr(obs, "collided", False))
        d2 = getattr(obs, "depth", None)
        if d2 is not None:
            dmin2 = _depth_min(d2)
            if dmin2 is not None and (dmin is None or dmin2 < dmin):
                dmin = dmin2
    return {
        "depth_min_m": None if dmin is None else round(dmin, 3),
        "collided": bool(coll or nudge_coll),
        "spawn_collided": bool(coll),
        "spawn_z_m": round(z, 3),
        "nudge_collided": bool(nudge_coll),
    }


def audit_point(
    env,
    client,
    airsim,
    vehicle: str,
    xyz: np.ndarray,
    yaw: float,
    *,
    yaw_sweep: bool,
    nudge_forward: bool = False,
) -> Dict[str, Any]:
    if yaw_sweep:
        mins = []
        coll_any = False
        for deg in (0, 45, 90, 135, 180, 225, 270, 315):
            _set_pose(client, airsim, vehicle, xyz, math.radians(deg))
            dmin, coll = _depth_min(env, client, airsim, vehicle)
            mins.append(dmin)
            coll_any = coll_any or coll
        finite = [m for m in mins if math.isfinite(m)]
        return {
            "depth_min_m": round(min(finite), 3) if finite else None,
            "depth_by_yaw": [None if math.isnan(m) else round(m, 3) for m in mins],
            "collided": bool(coll_any),
        }
    _set_pose(client, airsim, vehicle, xyz, yaw)
    dmin, coll = _depth_min(env, client, airsim, vehicle)
    nudge_coll = False
    if nudge_forward and not coll:
        # one micro forward step — catches "SPAWN on first move" that static depth misses
        obs, _ = env.step(np.array([0.12, 0.0, 0.0, 0.0], dtype=np.float64))
        nudge_coll = bool(getattr(obs, "collided", False))
        if not nudge_coll:
            obs, _ = env.step(np.array([0.12, 0.0, 0.0, 0.0], dtype=np.float64))
            nudge_coll = bool(getattr(obs, "collided", False))
    return {
        "depth_min_m": None if math.isnan(dmin) else round(dmin, 3),
        "collided": bool(coll or nudge_coll),
        "nudge_collided": bool(nudge_coll),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--annotation", default="artifacts/building99_indoor_short_routes.json")
    ap.add_argument("--out-annotation", default="artifacts/building99_indoor_short_routes_clean_sg.json")
    ap.add_argument("--out-report", default="artifacts/building99_route_clearance_audit_20260901.json")
    ap.add_argument("--min-start-clearance-m", type=float, default=1.0)
    ap.add_argument("--min-goal-clearance-m", type=float, default=1.0)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=41451)
    ap.add_argument("--vehicle", default="drone_1")
    ap.add_argument("--camera", default="0")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(root))
    from experiments.aerial.rl.env.airsim_env import AirSimDroneEnv, AirSimEnvConfig

    ann_path = Path(args.annotation) if Path(args.annotation).is_absolute() else root / args.annotation
    routes: List[Dict[str, Any]] = json.loads(ann_path.read_text(encoding="utf-8"))

    cfg = AirSimEnvConfig(
        host=args.host,
        port=args.port,
        vehicle=args.vehicle,
        camera=args.camera,
        grab_depth=True,
        step_hz=5.0,
        health_check=False,
        spawn_retry_max=6,
        spawn_min_z_m=1.4,
        spawn_z_bump_m=0.15,
        spawn_settle_s=0.50,
        spawn_hold=True,
        spawn_xy_nudge_m=0.30,
    )
    env = AirSimDroneEnv(cfg)
    # warm reset
    env.reset({"pos": [[0.0, 0.0, 1.5], [2.0, 0.0, 1.5]], "yaw": [0.0, 0.0]})
    client = env._client
    airsim = env._airsim

    rows = []
    keep = []
    for i, r in enumerate(routes):
        pos = np.asarray(r["pos"], dtype=np.float64)
        yaw = np.asarray(r["yaw"], dtype=np.float64)
        start, goal = pos[0], pos[-1]
        yaw0, yawg = float(yaw[0]), float(yaw[-1])
        tid = r.get("trajectory_id", f"route_{i}")

        start_rep = audit_start_reset(env, start, yaw0, nudge_forward=True)
        goal_rep = audit_point(env, client, airsim, args.vehicle, goal, yawg, yaw_sweep=True)

        start_ok = (not start_rep["collided"]) and (
            start_rep["depth_min_m"] is not None and start_rep["depth_min_m"] >= float(args.min_start_clearance_m)
        ) and (start_rep.get("spawn_z_m") is None or start_rep["spawn_z_m"] >= float(start[2]) - 0.12)
        goal_ok = (not goal_rep["collided"]) and (
            goal_rep["depth_min_m"] is not None and goal_rep["depth_min_m"] >= float(args.min_goal_clearance_m)
        )
        drop_reasons = []
        if start_rep.get("spawn_collided"):
            drop_reasons.append("start_spawn_collided")
        if start_rep["collided"]:
            drop_reasons.append(
                "start_collide_nudge" if start_rep.get("nudge_collided") else "start_collide"
            )
        elif start_rep["depth_min_m"] is None or start_rep["depth_min_m"] < float(args.min_start_clearance_m):
            drop_reasons.append(f"start_clearance<{args.min_start_clearance_m}")
        if goal_rep["collided"]:
            drop_reasons.append("goal_collide")
        elif goal_rep["depth_min_m"] is None or goal_rep["depth_min_m"] < float(args.min_goal_clearance_m):
            drop_reasons.append(f"goal_clearance<{args.min_goal_clearance_m}")

        keep_flag = start_ok and goal_ok
        row = {
            "idx": i,
            "trajectory_id": tid,
            "start": start.tolist(),
            "goal": goal.tolist(),
            "yaw0": yaw0,
            "start_audit": start_rep,
            "goal_audit": goal_rep,
            "keep": keep_flag,
            "drop_reasons": drop_reasons,
        }
        rows.append(row)
        logger.info(
            "%s idx=%d keep=%s start_d=%s coll=%s goal_d=%s reasons=%s",
            tid,
            i,
            keep_flag,
            start_rep.get("depth_min_m"),
            start_rep.get("collided"),
            goal_rep.get("depth_min_m"),
            drop_reasons,
        )
        if keep_flag:
            keep.append(r)

    report = {
        "protocol": "building99_route_clearance_audit",
        "source": str(ann_path),
        "min_start_clearance_m": float(args.min_start_clearance_m),
        "min_goal_clearance_m": float(args.min_goal_clearance_m),
        "n_in": len(routes),
        "n_keep": len(keep),
        "kept_ids": [r.get("trajectory_id") for r in keep],
        "dropped": [row for row in rows if not row["keep"]],
        "rows": rows,
    }
    out_rep = Path(args.out_report) if Path(args.out_report).is_absolute() else root / args.out_report
    out_ann = Path(args.out_annotation) if Path(args.out_annotation).is_absolute() else root / args.out_annotation
    out_rep.parent.mkdir(parents=True, exist_ok=True)
    out_ann.parent.mkdir(parents=True, exist_ok=True)
    out_rep.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    out_ann.write_text(json.dumps(keep, indent=2) + "\n", encoding="utf-8")
    out_ann.with_suffix(".meta.json").write_text(
        json.dumps(
            {
                "protocol": "building99_clean_start_goal",
                "source": str(ann_path),
                "min_start_clearance_m": float(args.min_start_clearance_m),
                "min_goal_clearance_m": float(args.min_goal_clearance_m),
                "n_in": len(routes),
                "n_out": len(keep),
                "report": str(out_rep),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"out_annotation": str(out_ann), "n_keep": len(keep), "kept_ids": report["kept_ids"]}, indent=2))
    try:
        env.close()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
