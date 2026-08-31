#!/usr/bin/env python3
"""P7-diag — planner rollouts on S_diag; log C_P7 + step traces (θ undefined).

Diagnostic only (RUNBOOK §1 P7-diag). Does not score ①′/④′.

Usage (125 / 4090):
  source experiments/aerial/scripts/env_4090.sh
  $PYTHON_BIN experiments/aerial/scripts/v4_p7_diag.py \\
    --env-host 127.0.0.1 \\
    --wm-ckpt experiments/aerial/rl/artifacts/wm_ckpt_r60_rh_20260816/wm_step_1000.pt \\
    --out artifacts/v4_p7_diag_20260820.json
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np


def _repo_root(explicit: Optional[str]) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    return Path(__file__).resolve().parents[3]


def _full_min_depth(depth: Optional[np.ndarray]) -> float:
    if depth is None:
        return float("nan")
    d = np.asarray(depth, dtype=np.float64)
    finite = d[np.isfinite(d) & (d > 0)]
    return float(np.min(finite)) if finite.size else float("nan")


def _goal_dist(pos: np.ndarray, goal: np.ndarray) -> float:
    return float(np.linalg.norm(np.asarray(goal, dtype=np.float64).reshape(3) - np.asarray(pos, dtype=np.float64).reshape(3)))


def _probe_layer(
    env: Any,
    probe_policy: Any,
    epi: Dict[str, Any],
    *,
    max_steps: int,
    arrival_m: float,
    reward_cfg: Any,
) -> str:
    """Return ``open`` or ``blocked`` from shield-off heuristic probe."""
    from experiments.aerial.rl import v0_rollout_eval as rollout

    if hasattr(probe_policy, "reset"):
        probe_policy.reset()
    ep = rollout._run_one_resilient(
        env, probe_policy, epi, max_steps=int(max_steps), reward_cfg=reward_cfg, shield=None
    )
    if ep is None or not ep:
        return "invalid"
    goal = np.asarray(getattr(env, "goal"), dtype=np.float64).reshape(3)
    final = np.asarray(ep[-1].next_obs.position, dtype=np.float64)
    if _goal_dist(final, goal) <= float(arrival_m):
        return "open"
    return "blocked"


def _extract_step_trace(
    ep: Any, *, goal: np.ndarray, arrival_m: float
) -> Tuple[List[Dict[str, Any]], bool, float]:
    rows: List[Dict[str, Any]] = []
    best_d = float("inf")
    arrived = False
    for i, tr in enumerate(ep):
        obs = tr.obs
        post = tr.next_obs if tr.next_obs is not None else obs
        clearance = _full_min_depth(getattr(obs, "depth", None))
        d_hat = tr.info.get("depth_min_pred")
        tau = tr.info.get("tau_pred")
        p_coll = None
        if isinstance(tr.info.get("wm_out"), dict):
            p_coll = tr.info["wm_out"].get("p_coll")
        rows.append(
            {
                "t": i,
                "clearance_fov": round(clearance, 4) if np.isfinite(clearance) else None,
                "d_hat_fovmin": round(float(d_hat), 4) if d_hat is not None else None,
                "tau_hat": round(float(tau), 4) if tau is not None else None,
                "p_coll": round(float(p_coll), 4) if p_coll is not None else None,
                "engaged": bool(tr.info.get("intervention", False)),
                "dist_goal": round(_goal_dist(post.position, goal), 4),
                "collided": bool(getattr(post, "collided", False)),
            }
        )
        best_d = min(best_d, rows[-1]["dist_goal"])
        if rows[-1]["dist_goal"] <= float(arrival_m):
            arrived = True
    return rows, arrived, best_d


def run_p7_diag(args: argparse.Namespace) -> Dict[str, Any]:
    root = _repo_root(args.repo)
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    import yaml

    from experiments.aerial.rl import v0_rollout_eval as rollout
    from experiments.aerial.rl._v0_gate import _obstacle_candidate_positions
    from experiments.aerial.rl.buffer import ReplayBuffer
    from experiments.aerial.rl.collector import RolloutCollector
    from experiments.aerial.rl.depth_predictor import DepthMinPredictor
    from experiments.aerial.rl.reward import RewardConfig
    from experiments.aerial.rl.safety import ThresholdSafetyShield
    from experiments.aerial.rl.tau_predictor import make_tau_predictor
    from experiments.aerial.rl.train_rl import HeuristicPolicy, _build_env, _build_planner, load_torch_dynamics

    cfg = yaml.safe_load((root / args.config).read_text()) or {}
    if args.env_host:
        cfg.setdefault("env", {})["host"] = str(args.env_host)
    env = _build_env(cfg.get("env", {}) or {})
    reward_cfg = RewardConfig(**(cfg.get("reward", {}) or {})) if cfg.get("reward") else RewardConfig()
    arrival_m = float(reward_cfg.success_dist_m)

    rollout_ds = Path(args.rollout_dataset).expanduser()
    if not rollout_ds.is_absolute():
        rollout_ds = root / rollout_ds
    wm_ckpt = Path(args.wm_ckpt).expanduser()
    if not wm_ckpt.is_absolute():
        wm_ckpt = root / wm_ckpt
    depth_ckpt = Path(args.depth_ckpt).expanduser()
    if not depth_ckpt.is_absolute():
        depth_ckpt = root / depth_ckpt
    tau_ckpt = Path(args.tau_ckpt).expanduser()
    if not tau_ckpt.is_absolute():
        tau_ckpt = root / tau_ckpt

    wm_cfg = cfg.get("world_model", {}) or {}
    dynamics, wm_payload = load_torch_dynamics(
        wm_cfg, wm_ckpt, device=str(args.device), success_dist_m=arrival_m
    )
    cfg.setdefault("planner", {})["enable"] = True
    planner = _build_planner(cfg, dynamics, reward_cfg)
    depth_pred = DepthMinPredictor.from_checkpoint(depth_ckpt, device=str(args.device))
    tau_cfg = cfg.get("tau_predictor", {}) or {}
    tau_pred = make_tau_predictor(
        kind=str(tau_cfg.get("kind", "foe_calibrated")),
        ckpt=tau_ckpt,
        device=str(args.device),
        center_frac=float(tau_cfg.get("center_frac", 0.5)),
        min_closing_m_s=float(tau_cfg.get("min_closing_m_s", 0.05)),
        max_tau_s=float(tau_cfg.get("max_tau_s", 60.0)),
        dt_s=float(tau_cfg.get("dt_s", 0.1)),
        use_gt_depth=False,
    )
    shield = ThresholdSafetyShield(min_depth_m=float(args.shield_trigger_m))
    heuristic = HeuristicPolicy(goal_getter=lambda: getattr(env, "goal", None))
    zero_policy = HeuristicPolicy(goal_getter=lambda: getattr(env, "goal", None))
    # Base policy for planner path: heuristic proposes, planner replans.
    base_policy = heuristic

    cand, cand_yaw = _obstacle_candidate_positions(rollout_ds, min_altitude_m=0.0)
    goal_dist = float(getattr(args, "goal_dist_m", 30.0))

    blocked_eps, blocked_scan = rollout.make_obstacle_facing_episodes(
        env,
        int(args.target_n),
        cand,
        seed=int(args.seed),
        candidate_yaws=cand_yaw,
        goal_dist_m=goal_dist,
        obstacle_max_m=25.0,
        center_frac=0.3,
        max_scans=int(args.scan_max),
        probe_policy=heuristic,
        probe_steps=int(args.probe_steps),
        probe_near_m=1.5,
        reward_cfg=reward_cfg,
        preserve_order=True,
        log_every=25,
    )
    labeled_blocked: List[Tuple[int, str, Dict[str, Any]]] = [
        (-1, "blocked", epi) for epi in blocked_eps
    ]

    blocked = labeled_blocked
    open_: List[Tuple[int, str, Dict[str, Any]]] = []
    open_rej = {"skipped": "P7-diag only scores S_blocked for C_P7"}
    rng_diag = np.random.default_rng(int(args.diag_seed))
    diag_pick = (
        [blocked[i] for i in rng_diag.choice(len(blocked), size=min(int(args.target_n), len(blocked)), replace=False)]
        if blocked
        else []
    )

    episodes_out: List[Dict[str, Any]] = []
    c_p7: List[float] = []
    buf = ReplayBuffer(capacity_episodes=4, seed=0)

    for j, (ci, layer, epi) in enumerate(diag_pick):
        if hasattr(base_policy, "reset"):
            base_policy.reset()
        if hasattr(shield, "reset"):
            shield.reset()
        col = RolloutCollector(
            env,
            base_policy,
            buf,
            reward_cfg=reward_cfg,
            safety=shield,
            max_steps=int(args.max_steps),
            target_hz=0.0,
            depth_predictor=depth_pred,
            tau_predictor=tau_pred,
            planner=planner,
            dynamics=dynamics,
        )
        ep, stats = col.collect_episode(epi)
        if not ep:
            continue
        goal = np.asarray(getattr(env, "goal"), dtype=np.float64).reshape(3)
        trace, arrived, best_d = _extract_step_trace(ep, goal=goal, arrival_m=arrival_m)
        for row in trace:
            c = row.get("clearance_fov")
            if c is not None and np.isfinite(c):
                c_p7.append(float(c))
        episodes_out.append(
            {
                "idx": j,
                "candidate_idx": int(ci),
                "layer": layer,
                "arrived": bool(arrived),
                "best_dist_m": round(float(best_d), 4),
                "n_steps": len(trace),
                "steps": trace,
            }
        )
        print(
            f"[p7-diag] ep{j}: layer={layer} arrived={arrived} best_d={best_d:.2f} steps={len(trace)}"
        )

    q25 = float(np.percentile(c_p7, 25)) if c_p7 else float("nan")
    payload = {
        "step": "P7-diag",
        "theta": None,
        "band_lo_hi": None,
        "note": "diagnostic only; θ and band not frozen here",
        "s_diag_seed": int(args.diag_seed),
        "accept_seed_reserved": int(args.accept_seed),
        "n_blocked_pool": len(blocked),
        "n_open_pool": len(open_),
        "open_scan_rejections": open_rej,
        "blocked_scan": blocked_scan,
        "n_scored": len(episodes_out),
        "C_P7": {
            "n": len(c_p7),
            "p25": round(q25, 4) if np.isfinite(q25) else None,
            "median": round(float(np.median(c_p7)), 4) if c_p7 else None,
        },
        "episodes": episodes_out,
        "wm_ckpt": str(wm_ckpt),
        "wm_step": wm_payload.get("step"),
    }
    return payload


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--repo", default=None)
    p.add_argument("--config", default="configs/aerial_rl_rollout.yaml")
    p.add_argument("--env-host", default="127.0.0.1")
    p.add_argument("--device", default="cuda")
    p.add_argument(
        "--rollout-dataset",
        default="~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/dataset_v0_local_depth_r60_20260814",
    )
    p.add_argument(
        "--wm-ckpt",
        default="experiments/aerial/rl/artifacts/wm_ckpt_r60_rh_20260816/wm_step_1000.pt",
    )
    p.add_argument(
        "--depth-ckpt",
        default="experiments/aerial/rl/artifacts/depth_ckpt_da3_r60_20260814/depth_step_2000_da3_ft_head.pt",
    )
    p.add_argument(
        "--tau-ckpt",
        default="experiments/aerial/rl/artifacts/tau_ckpt_foe_r60_20260815/tau_foe_calibrator.pt",
    )
    p.add_argument("--target-n", type=int, default=16)
    p.add_argument("--scan-max", type=int, default=400)
    p.add_argument("--probe-steps", type=int, default=40)
    p.add_argument("--max-steps", type=int, default=200)
    p.add_argument("--goal-dist-m", type=float, default=30.0)
    p.add_argument("--shield-trigger-m", type=float, default=3.0)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--diag-seed", type=int, default=1000)
    p.add_argument("--accept-seed", type=int, default=2000)
    p.add_argument("--out", default="artifacts/v4_p7_diag_20260820.json")
    args = p.parse_args()

    payload = run_p7_diag(args)
    out = Path(args.out).expanduser()
    if not out.is_absolute():
        out = _repo_root(args.repo) / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    print(f"[p7-diag] wrote {out} n_scored={payload['n_scored']} C_P7.p25={payload['C_P7'].get('p25')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
