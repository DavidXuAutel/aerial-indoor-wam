#!/usr/bin/env python3
"""Runbook B′-1 — ridge probe: does packed latent predict near-field depth?

  source experiments/aerial/scripts/env_4090.sh
  $AERIAL_PY experiments/aerial/scripts/wam_latent_depth_probe.py \\
    --dataset experiments/aerial/rl/artifacts/dataset_v0_p45_merged_20260821 \\
    --wm-ckpt experiments/aerial/rl/artifacts/wm_ckpt_coll_full_20260827/wm_step_1000.pt \\
    --out artifacts/wam_latent_depth_probe_20260827.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import yaml


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def main() -> int:
    root = _repo_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    p = argparse.ArgumentParser(description="B′-1 latent depth ridge probe")
    p.add_argument(
        "--dataset",
        default="experiments/aerial/rl/artifacts/dataset_v0_p45_merged_20260821",
    )
    p.add_argument(
        "--wm-ckpt",
        default="experiments/aerial/rl/artifacts/wm_ckpt_coll_full_20260827/wm_step_1000.pt",
    )
    p.add_argument("--config", default="configs/aerial_rl.yaml")
    p.add_argument("--device", default="cuda")
    p.add_argument("--max-samples", type=int, default=32)
    p.add_argument("--max-center-depth-m", type=float, default=12.0)
    p.add_argument("--stride", type=int, default=2)
    p.add_argument("--window", type=int, default=8)
    p.add_argument("--ridge-alpha", type=float, default=1.0)
    p.add_argument("--heldout-frac", type=float, default=0.25)
    p.add_argument("--out", default="artifacts/wam_latent_depth_probe.json")
    args = p.parse_args()

    from experiments.aerial.rl import dataset as ds
    from experiments.aerial.rl.latent_encode_probe import (
        encode_single,
        encode_window_packed,
        iter_near_depth_samples,
        probe_depth_from_features,
    )
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
    wm_cfg = config.get("world_model", {}) or {}
    dynamics, _ = load_torch_dynamics(
        wm_cfg,
        wm_ckpt,
        device=str(args.device),
        success_dist_m=float(reward_cfg.success_dist_m),
    )

    episodes = ds.load_dataset(dataset, skip_quarantined=True)
    picks = iter_near_depth_samples(
        episodes,
        max_samples=int(args.max_samples),
        stride=int(args.stride),
        max_center_depth_m=float(args.max_center_depth_m),
    )
    if not picks:
        payload = {
            "step": "B_prime_1",
            "error": "no_near_depth_samples",
            "dataset": str(dataset),
            "wm_ckpt": str(wm_ckpt),
        }
        out_path.write_text(json.dumps(payload, indent=2) + "\n")
        print(json.dumps(payload, indent=2))
        return 2

    feats_single: List[np.ndarray] = []
    feats_window: List[np.ndarray] = []
    center: List[float] = []
    feats_fwd: List[np.ndarray] = []
    fwd_depths: List[float] = []
    rows_meta = []
    for ep_i, t_i, d0, df in picks:
        ep = episodes[ep_i]
        obs = ep[t_i].obs
        z_win = encode_window_packed(dynamics, ep, t_i, window=int(args.window))
        z_single = encode_single(dynamics, obs)
        feats_single.append(z_single)
        feats_window.append(z_win)
        center.append(d0)
        if df is not None and np.isfinite(df):
            feats_fwd.append(z_win)
            fwd_depths.append(float(df))
        rows_meta.append(
            {
                "episode_idx": ep_i,
                "t_idx": t_i,
                "center_depth_m": round(d0, 3),
                "forward_min_depth_m": None if df is None else round(float(df), 3),
            }
        )

    x_single = np.stack(feats_single, axis=0)
    x_window = np.stack(feats_window, axis=0)
    y_center = np.asarray(center, dtype=np.float64)

    probe_single_center = probe_depth_from_features(
        x_single,
        y_center,
        heldout_frac=float(args.heldout_frac),
        alpha=float(args.ridge_alpha),
    )
    probe_window_center = probe_depth_from_features(
        x_window,
        y_center,
        heldout_frac=float(args.heldout_frac),
        alpha=float(args.ridge_alpha),
    )
    probe_fwd = None
    if len(fwd_depths) >= 8:
        probe_fwd = probe_depth_from_features(
            np.stack(feats_fwd, axis=0),
            np.asarray(fwd_depths, dtype=np.float64),
            heldout_frac=float(args.heldout_frac),
            alpha=float(args.ridge_alpha),
        )

    payload = {
        "step": "B_prime_1",
        "dataset": str(dataset),
        "wm_ckpt": str(wm_ckpt),
        "n_samples": len(picks),
        "max_center_depth_m": float(args.max_center_depth_m),
        "stride": int(args.stride),
        "window": int(args.window),
        "ridge_alpha": float(args.ridge_alpha),
        "heldout_frac": float(args.heldout_frac),
        "thresholds": {"r2_holdout_min": 0.3, "mae_holdout_max_m": 2.0},
        "center_depth": {
            "encode_single": probe_single_center,
            "encode_window": probe_window_center,
        },
        "forward_min_depth": probe_fwd,
        "samples": rows_meta,
        "readout": (
            "has_geometry"
            if probe_window_center.get("verdict") == "has_geometry"
            or probe_single_center.get("verdict") == "has_geometry"
            else "weak_geometry"
        ),
    }
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"out": str(out_path), "readout": payload["readout"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
