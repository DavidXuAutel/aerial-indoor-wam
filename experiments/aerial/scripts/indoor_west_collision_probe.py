#!/usr/bin/env python3
"""Per-step west-route collision probe (Building_99 B99_lobby_west_3m).

Logs pose, collision object, depth, and policy actions to isolate whether
west failures are spawn-embedded, ground latch, lateral planter strike, or
altitude drop.

Usage (125):
  source experiments/aerial/scripts/env_4090.sh
  export AIRSIM_CAMERA=0 AIRSIM_VEHICLE=drone_1
  $AERIAL_PY experiments/aerial/scripts/indoor_west_collision_probe.py \\
    --out artifacts/indoor_west_collision_probe_20260902.json
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def _collision_detail(client, vk: dict) -> Dict[str, Any]:
    try:
        ci = client.simGetCollisionInfo(**vk)
        return {
            "has_collided": bool(ci.has_collided),
            "object_id": str(getattr(ci, "object_id", "")),
            "object_name": str(getattr(ci, "object_name", "")),
            "impact_point": [
                float(ci.impact_point.x_val),
                float(ci.impact_point.y_val),
                float(-ci.impact_point.z_val),
            ],
            "position": [
                float(ci.position.x_val),
                float(ci.position.y_val),
                float(-ci.position.z_val),
            ],
        }
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


def _depth_min(depth: Optional[np.ndarray]) -> Optional[float]:
    if depth is None:
        return None
    d = np.asarray(depth, dtype=np.float64)
    fin = np.isfinite(d) & (d > 0) & (d < 100)
    if not fin.any():
        return None
    return float(np.min(d[fin]))


def _state_row(env, client, vk, label: str, obs, extra: Optional[dict] = None) -> Dict[str, Any]:
    st = env.observe_state()
    row = {
        "label": label,
        "pos": [round(float(st[i]), 4) for i in range(3)],
        "vel": [round(float(st[i]), 4) for i in range(3, 6)],
        "yaw_deg": round(math.degrees(float(st[6])), 2),
        "collided_obs": bool(getattr(obs, "collided", False)),
        "depth_min_m": _depth_min(getattr(obs, "depth", None)),
        "baro_alt": getattr(obs, "baro_alt", None),
        "collision": _collision_detail(client, vk),
    }
    if extra:
        row.update(extra)
    return row


def _run_physics_sweep(env, client, airsim, vk, seg: dict) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    obs = env.reset({"pos": seg["pos"], "yaw": seg["yaw"], "gpt_instruction": seg.get("gpt_instruction", "")})
    rows.append(_state_row(env, client, vk, "reset", obs))

    probes = [
        ("hover_x5", np.zeros(4)),
        ("fwd_nudge_0.12", np.array([0.12, 0.0, 0.0, 0.0])),
        ("fwd_nudge_0.12_b", np.array([0.12, 0.0, 0.0, 0.0])),
        ("left_nudge_dy+0.12", np.array([0.0, 0.12, 0.0, 0.0])),
        ("right_nudge_dy-0.12", np.array([0.0, -0.12, 0.0, 0.0])),
        ("down_nudge_dz-0.08", np.array([0.0, 0.0, -0.08, 0.0])),
        ("fwd_large_0.15", np.array([0.15, 0.0, 0.0, 0.0])),
    ]
    for name, action in probes:
        if name == "hover_x5":
            for i in range(5):
                obs, info = env.step(np.zeros(4))
                rows.append(_state_row(env, client, vk, f"hover_{i}", obs, {"cmd": info.get("cmd")}))
                if bool(getattr(obs, "collided", False)):
                    break
            continue
        obs, info = env.step(action)
        rows.append(
            _state_row(
                env, client, vk, name, obs,
                {"cmd": info.get("cmd"), "vx": info.get("vx"), "vy": info.get("vy"), "vz_ned": info.get("vz_ned")},
            )
        )
        if bool(getattr(obs, "collided", False)):
            break
    return rows


def _yaw_sweep_depth(env, client, airsim, vehicle: str, xyz: np.ndarray) -> List[Dict[str, Any]]:
    vk = {"vehicle_name": vehicle}
    rows = []
    for deg in (0, 45, 90, 135, 180, 225, 270, 315):
        yaw = math.radians(deg)
        pose = airsim.Pose(
            airsim.Vector3r(float(xyz[0]), float(xyz[1]), float(-xyz[2])),
            airsim.to_quaternion(0.0, 0.0, float(yaw)),
        )
        client.simSetVehiclePose(pose, True, **vk)
        obs, _ = env.step(np.zeros(4))
        rows.append({
            "yaw_deg": deg,
            "depth_min_m": _depth_min(getattr(obs, "depth", None)),
            "collided": bool(getattr(obs, "collided", False)),
        })
    return rows


def _run_policy_steps(env, policy_stack, seg: dict, client, vk, n_steps: int = 5) -> List[Dict[str, Any]]:
    from experiments.aerial.rl.collector import act_delta, clip_body_delta
    from experiments.aerial.rl.goal_features import body_vel_from_obs, goal_rel_from_obs

    policy, dynamics, depth_pred, shield, planner, limits = policy_stack
    goal_pos = np.asarray(seg["pos"][1], dtype=np.float64)
    goal_yaw = float(seg["yaw"][1])

    obs = env.reset({"pos": seg["pos"], "yaw": seg["yaw"], "gpt_instruction": seg.get("gpt_instruction", "")})
    obs.info["goal"] = goal_pos.tolist()
    policy.reset(obs, target_pos=goal_pos, target_yaw=goal_yaw)
    if hasattr(shield, "reset"):
        shield.reset()
    latent = np.asarray(dynamics.encode(obs), dtype=np.float64)

    rows = [_state_row(env, client, vk, "policy_reset", obs)]
    for step_i in range(n_steps):
        wam = act_delta(policy, obs, seg.get("gpt_instruction", ""), limits)
        action = np.asarray(wam, dtype=np.float64).copy()
        if planner is not None:
            if callable(getattr(planner, "set_goal", None)):
                planner.set_goal(goal_pos)
            action = np.asarray(planner.plan(obs, action), dtype=np.float64).reshape(4)
            action = clip_body_delta(action, limits)
        action = policy.arbitrate(obs, action)
        wam_after = action.copy()

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
                action, intervened = apply_fn(action, obs, wm_out=wm_out, limits=limits)
            elif shield.should_override(obs, wm_out=wm_out):
                action = clip_body_delta(shield.override_action(obs), limits)
                intervened = True

        obs, info = env.step(action)
        obs.info["goal"] = goal_pos.tolist()
        policy.post_step(obs, action)
        out = dynamics.step(
            latent, action,
            goal_rel=goal_rel_from_obs(obs),
            body_vel=body_vel_from_obs(obs),
        )
        latent = np.asarray(out.z_next, dtype=np.float64)

        rows.append(
            _state_row(
                env, client, vk, f"policy_step_{step_i}",
                obs,
                {
                    "wam_action": [round(float(x), 4) for x in wam_after],
                    "final_action": [round(float(x), 4) for x in action],
                    "intervened": intervened,
                    "phase": getattr(policy, "last_phase", None),
                    "cmd": info.get("cmd"),
                },
            )
        )
        if bool(getattr(obs, "collided", False)):
            break
    return rows


def _load_policy_stack(args) -> tuple:
    from experiments.aerial.rl.actor_critic import LatentActorCritic, LatentActorDeployPolicy
    from experiments.aerial.rl.depth_predictor import DepthMinPredictor
    from experiments.aerial.rl.planner import ImaginationPlanner
    from experiments.aerial.rl.pose_estimate import make_pose_estimator
    from experiments.aerial.rl.reward import RewardConfig
    from experiments.aerial.rl.train_rl import load_torch_dynamics
    from experiments.aerial.scripts.indoor_mainline_baseline_eval import MainlineIndoorPolicyWrapper
    from experiments.aerial.scripts.indoor_shield_config import build_indoor_shield

    cfg = yaml.safe_load((ROOT / args.config).read_text()) or {}
    reward_cfg = RewardConfig(**(cfg.get("reward") or {}))

    wm_path = ROOT / args.wm_ckpt
    dynamics, _ = load_torch_dynamics(
        cfg.get("world_model") or {},
        str(wm_path),
        device="cuda",
        success_dist_m=float(reward_cfg.success_dist_m),
    )
    actor_path = ROOT / args.actor_ckpt
    actor_ac = LatentActorCritic.load_from_checkpoint(actor_path, device="cuda")
    base_policy = LatentActorDeployPolicy(dynamics, actor_ac, deterministic=True)

    depth_ckpt = cfg.get("depth_ckpt") or "experiments/aerial/rl/artifacts/depth_ckpt_p45mid_s8j_20260825/depth_best_holdout_da3_ft_head.pt"
    depth_path = ROOT / depth_ckpt
    depth_pred = DepthMinPredictor.from_checkpoint(depth_path, device="cuda") if depth_path.is_file() else None

    limits = np.array([0.15, 0.08, 0.08, 0.10], dtype=np.float64)
    shield = build_indoor_shield(cfg, shield_off=False)
    planner = ImaginationPlanner(
        dynamics=dynamics, horizon=5, reward_cfg=reward_cfg, action_limits=limits, policy=actor_ac,
    )
    pose_est = make_pose_estimator(args.pose_source)
    policy = MainlineIndoorPolicyWrapper(
        base_policy, pose_est, max_dz=0.08, step_hz=5.0,
        assist=args.assist, forbid_gt_world_pose_control=True,
    )
    policy.action_limits = limits
    return (policy, dynamics, depth_pred, shield, planner, limits)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="artifacts/indoor_west_collision_probe_20260902.json")
    ap.add_argument("--config", default="configs/aerial_rl_indoor_shield_v3.yaml")
    ap.add_argument("--actor-ckpt", default="experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2i_e_20260901/v4_ac_latest.pt")
    ap.add_argument("--wm-ckpt", default="experiments/aerial/rl/artifacts/wm_ckpt_indoor_encode_e2i_b_20260901/wm_step_400.pt")
    ap.add_argument("--pose-source", default="gt_proxy")
    ap.add_argument("--assist", default="none")
    ap.add_argument("--policy-steps", type=int, default=5)
    args = ap.parse_args()

    from experiments.aerial.rl.env.airsim_env import AirSimDroneEnv, AirSimEnvConfig

    ann_path = ROOT / "building99_indoor_short_routes_clean_sg.json"
    if not ann_path.is_file():
        ann_path = ROOT / "artifacts/building99_indoor_short_routes_clean_sg.json"
    ann = json.loads(ann_path.read_text())
    west = ann[0]
    east = ann[2]  # same start [1,0,1.5], yaw 0

    cfg = AirSimEnvConfig(camera="0", vehicle="drone_1", width=224, height=224, step_hz=5.0)
    env = AirSimDroneEnv(cfg)
    client = env._connect()
    airsim = env._airsim
    vk = env._vk

    report: Dict[str, Any] = {
        "protocol": "indoor_west_collision_probe",
        "west_seg": west,
        "east_seg": east,
    }

    try:
        start_xyz = np.asarray(west["pos"][0], dtype=np.float64)
        report["west_yaw_sweep_at_start"] = _yaw_sweep_depth(env, client, airsim, cfg.vehicle, start_xyz)
        report["west_physics"] = _run_physics_sweep(env, client, airsim, vk, west)
        report["east_physics_same_start"] = _run_physics_sweep(env, client, airsim, vk, east)

        policy_stack = _load_policy_stack(args)
        report["west_policy"] = _run_policy_steps(env, policy_stack, west, client, vk, args.policy_steps)
        report["east_policy"] = _run_policy_steps(env, policy_stack, east, client, vk, args.policy_steps)
    finally:
        env.close()

    out = Path(args.out) if Path(args.out).is_absolute() else ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k.endswith("_seg") or k in ("west_physics", "west_policy")}, indent=2)[:8000])
    print(f"[probe] wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
