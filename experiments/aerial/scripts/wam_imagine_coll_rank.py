#!/usr/bin/env python3
"""Runbook step B — imagined collision ranking (forward vs lateral).

Offline (4090 / H100), no renderer required:

  source experiments/aerial/scripts/env_4090.sh
  $AERIAL_PY experiments/aerial/scripts/wam_imagine_coll_rank.py \\
    --dataset experiments/aerial/rl/artifacts/dataset_v0_p45_near_enrich_20260820 \\
    --wm-ckpt experiments/aerial/rl/artifacts/wm_ckpt_r60_rh_20260816/wm_step_1000.pt \\
    --out artifacts/wam_imagine_coll_rank_20260827.json

Writes numbers only. Does not train, does not flip production yaml.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import yaml


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _center_depth_m(obs: Any) -> Optional[float]:
    from experiments.aerial.rl.latent_encode_probe import center_depth_m as _fn
    return _fn(obs)


def _packed_z0(
    dynamics: Any,
    episode: Any,
    t_idx: int,
    *,
    encode_mode: str,
    window: int,
    obs: Any,
) -> np.ndarray:
    from experiments.aerial.rl.latent_encode_probe import encode_single, encode_window_packed
    if encode_mode == "window":
        return encode_window_packed(dynamics, episode, t_idx, window=window)
    if encode_mode == "single":
        return encode_single(dynamics, obs)
    raise ValueError(f"unknown encode_mode {encode_mode!r} (expected single|window)")


def main() -> int:
    root = _repo_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    p = argparse.ArgumentParser(description="Imagination collision ranking (step B)")
    p.add_argument(
        "--dataset",
        default="experiments/aerial/rl/artifacts/dataset_v0_p45_near_enrich_20260820",
    )
    p.add_argument(
        "--wm-ckpt",
        default="experiments/aerial/rl/artifacts/wm_ckpt_r60_rh_20260816/wm_step_1000.pt",
    )
    p.add_argument("--config", default="configs/aerial_rl.yaml")
    p.add_argument("--device", default="cuda")
    p.add_argument("--horizon", type=int, default=15)
    p.add_argument("--max-samples", type=int, default=32, help="Number of (episode,t) z0 to score")
    p.add_argument(
        "--max-center-depth-m",
        type=float,
        default=12.0,
        help="Prefer near-obstacle frames; skip if center depth > this (when depth present)",
    )
    p.add_argument(
        "--stride",
        type=int,
        default=5,
        help="Sample every N steps inside an episode (near frames mid-flight)",
    )
    p.add_argument(
        "--encode-mode",
        choices=("single", "window"),
        default="single",
        help="single=encode(obs) h=0; window=teacher-forced h at t (B′-2)",
    )
    p.add_argument(
        "--window",
        type=int,
        default=8,
        help="RSSM teacher-forcing window when --encode-mode=window",
    )
    p.add_argument("--out", default="artifacts/wam_imagine_coll_rank.json")
    args = p.parse_args()

    from experiments.aerial.rl import dataset as ds
    from experiments.aerial.rl.goal_features import body_vel_from_obs, goal_rel_from_obs
    from experiments.aerial.rl.imagine_coll_rank import (
        pairwise_gaps,
        score_arms_at_z0,
        verdict_from_gaps,
    )
    from experiments.aerial.rl.imagination import MAX_IMAGINATION_HORIZON
    from experiments.aerial.rl.reward import RewardConfig
    from experiments.aerial.rl.train_rl import load_torch_dynamics

    cfg_path = Path(args.config)
    if not cfg_path.is_absolute():
        cfg_path = root / cfg_path
    with cfg_path.open() as f:
        config: Dict[str, Any] = yaml.safe_load(f) or {}

    dataset = Path(args.dataset).expanduser()
    if not dataset.is_absolute():
        dataset = root / dataset
    wm_ckpt = Path(args.wm_ckpt).expanduser()
    if not wm_ckpt.is_absolute():
        wm_ckpt = root / wm_ckpt
    out_path = Path(args.out).expanduser()
    if not out_path.is_absolute():
        out_path = root / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)

    reward_cfg = (
        RewardConfig(**(config.get("reward", {}) or {}))
        if config.get("reward")
        else RewardConfig()
    )
    step_hz = float((config.get("env") or {}).get("step_hz", 5.0))
    horizon = min(int(args.horizon), int(MAX_IMAGINATION_HORIZON))
    wm_cfg = config.get("world_model", {}) or {}

    dynamics, _ = load_torch_dynamics(
        wm_cfg,
        wm_ckpt,
        device=str(args.device),
        success_dist_m=float(reward_cfg.success_dist_m),
    )

    episodes = ds.load_dataset(dataset, skip_quarantined=True)
    rows: List[Dict[str, Any]] = []
    gaps: List[Dict[str, Any]] = []
    n_skip_depth = 0
    n_skip_empty = 0
    stride = max(1, int(args.stride))

    for ep_i, ep in enumerate(episodes):
        if len(rows) >= int(args.max_samples):
            break
        if not ep:
            n_skip_empty += 1
            continue
        for t_i in range(0, len(ep), stride):
            if len(rows) >= int(args.max_samples):
                break
            tr = ep[t_i]
            d0 = _center_depth_m(tr.obs)
            if d0 is not None and d0 > float(args.max_center_depth_m):
                n_skip_depth += 1
                continue
            z0 = _packed_z0(
                dynamics,
                ep,
                t_i,
                encode_mode=str(args.encode_mode),
                window=int(args.window),
                obs=tr.obs,
            )
            goal_rel0 = goal_rel_from_obs(tr.obs)
            body_vel0 = body_vel_from_obs(tr.obs)
            arm_scores = score_arms_at_z0(
                dynamics,
                z0,
                horizon=horizon,
                goal_rel0=goal_rel0,
                body_vel0=body_vel0,
                reward_cfg=reward_cfg,
                step_hz=step_hz,
            )
            g = pairwise_gaps(arm_scores)
            gaps.append(g)
            rows.append(
                {
                    "episode_idx": int(ep_i),
                    "t_idx": int(t_i),
                    "center_depth_m": None if d0 is None else round(float(d0), 3),
                    "arms": {
                        k: {kk: round(vv, 6) for kk, vv in v.items()}
                        for k, v in arm_scores.items()
                    },
                    "gaps": {
                        kk: (vv if isinstance(vv, str) else round(float(vv), 6))
                        for kk, vv in g.items()
                    },
                }
            )

    verdict = verdict_from_gaps(gaps)
    payload = {
        "step": "B",
        "dataset": str(dataset),
        "wm_ckpt": str(wm_ckpt),
        "config": str(cfg_path),
        "horizon": horizon,
        "step_hz": step_hz,
        "reward": {
            "w_progress": float(reward_cfg.w_progress),
            "w_collision": float(reward_cfg.w_collision),
            "w_maneuver": float(reward_cfg.w_maneuver),
        },
        "n_scored": len(rows),
        "n_skip_depth": n_skip_depth,
        "n_skip_empty": n_skip_empty,
        "max_center_depth_m": float(args.max_center_depth_m),
        "stride": stride,
        "encode_mode": str(args.encode_mode),
        "window": int(args.window),
        "verdict": verdict,
        "per_z0": rows,
    }
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"out": str(out_path), "verdict": verdict}, ensure_ascii=False, indent=2))
    return 0 if rows else 2


if __name__ == "__main__":
    raise SystemExit(main())
