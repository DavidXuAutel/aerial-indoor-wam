"""H100 offline finetune for V1-② aux-conditioned ``reward_feat_proj`` + ``reward_head``.

Loads the authoritative r60 WM backbone from ``wm_ckpt_r60_20260814`` (shape-filter
skips legacy ``reward_head.0 (256,1536)``), freezes encoder/RSSM/decoder/cont/coll,
and trains only the reward head stack on r60 windows with ``goal_rel`` / ``body_vel``.

    python -m experiments.aerial.rl.train_reward_head \\
        --dataset ~/aerial-rl-skeleton/.../dataset_v0_local_depth_r60_20260814 \\
        --wm-ckpt ~/aerial-rl-skeleton/.../wm_ckpt_r60_20260814/wm_step_5000.pt \\
        --config configs/aerial_rl.yaml --steps 1000 --device cuda \\
        --checkpoint-dir experiments/aerial/rl/artifacts/wm_ckpt_r60_rh_20260816

Writes ``rh_train.jsonl`` + ``wm_step_<N>.pt`` under ``--checkpoint-dir``.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import torch
import yaml

from experiments.aerial.rl._wm_train_validate import (
    _load_buffer,
    _load_world_model_cfg,
    _refuse_v0,
    _write_train_meta,
)
from experiments.aerial.rl.dynamics_torch import TorchRSSMDynamics


def _git_sha() -> Optional[str]:
    import subprocess

    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() or None


def _assert_reward_head_load_clean(model: TorchRSSMDynamics, ckpt_path: Path) -> None:
    payload = model.load_checkpoint(str(ckpt_path))
    skipped = payload.get("load_skipped") or []
    rh_skip = [s for s in skipped if "reward" in s]
    if rh_skip:
        print(
            f"[rh-train] FAIL: reward-head load_skipped not empty: {rh_skip}",
            file=sys.stderr,
        )
        raise SystemExit(1)
    print(f"[rh-train] load_skipped (reward): [] — ok for {ckpt_path}")


def main(argv: List[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dataset", required=True)
    p.add_argument("--wm-ckpt", required=True, help="backbone ckpt (legacy RH skipped)")
    p.add_argument("--config", default="configs/aerial_rl.yaml")
    p.add_argument("--steps", type=int, default=1000)
    p.add_argument("--wm-batch", type=int, default=8)
    p.add_argument("--window", type=int, default=8)
    p.add_argument("--device", default="cuda")
    p.add_argument("--lr", type=float, default=1e-4)
    p.add_argument("--allow-v0-desync", action="store_true")
    p.add_argument(
        "--checkpoint-dir",
        default="experiments/aerial/rl/artifacts/wm_ckpt_r60_rh_20260816",
    )
    p.add_argument("--heldout-frac", type=float, default=0.0)
    args = p.parse_args(argv)

    root = Path(args.dataset)
    _refuse_v0(root, args.allow_v0_desync)
    buf = _load_buffer(root, args.window, heldout_frac=float(args.heldout_frac))

    wm_cfg = _load_world_model_cfg(Path(args.config))
    wm_cfg.setdefault("device", args.device)
    wm_cfg["checkpoint_dir"] = str(args.checkpoint_dir)
    sample_obs = buf.sample_windows(1, 1)[0][0].obs
    wm_cfg["image_size"] = int(np.asarray(sample_obs.rgb).shape[0])

    model = TorchRSSMDynamics.from_config(wm_cfg)
    wm_path = Path(args.wm_ckpt).expanduser().resolve()
    if not wm_path.is_file():
        print(f"[rh-train] FAIL: wm ckpt not found: {wm_path}", file=sys.stderr)
        raise SystemExit(1)
    load_payload = model.load_checkpoint(str(wm_path))
    rh_skip = [s for s in (load_payload.get("load_skipped") or []) if "reward" in s]
    print(
        f"[rh-train] backbone load from {wm_path} | "
        f"reward load_skipped={rh_skip or '[] (fresh head)'}"
    )

    trainable = model.apply_freeze_backbone_train_reward_head()
    if not trainable:
        print("[rh-train] FAIL: no trainable reward-head params", file=sys.stderr)
        raise SystemExit(1)
    opt = torch.optim.AdamW(trainable, lr=float(args.lr), betas=(0.9, 0.95))
    print(
        f"[rh-train] frozen backbone | trainable params={sum(p.numel() for p in trainable)}"
    )

    ckpt_dir = Path(args.checkpoint_dir)
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    log_path = ckpt_dir / "rh_train.jsonl"
    if log_path.exists():
        log_path.unlink()
    meta_path = _write_train_meta(
        ckpt_dir,
        root=root,
        args=args,
        buf=buf,
        image_size=wm_cfg["image_size"],
    )
    meta = json.loads(meta_path.read_text())
    meta["finetune"] = "reward_head_only"
    meta["backbone_wm_ckpt"] = str(wm_path)
    meta["git_sha"] = _git_sha()
    meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n")

    losses: List[float] = []
    for i in range(int(args.steps)):
        windows = buf.sample_windows(int(args.wm_batch), int(args.window))
        out = model.update_reward_head(windows, optimizer=opt)
        losses.append(float(out["loss_reward"]))
        row = {
            "step": i,
            "loss_reward": float(out["loss_reward"]),
            "grad_norm": float(out.get("grad_norm", float("nan"))),
        }
        with log_path.open("a") as f:
            f.write(json.dumps(row) + "\n")
        if i % max(1, args.steps // 10) == 0:
            print(
                f"[rh-train] step {i:4d} | loss_reward={out['loss_reward']:.4f} "
                f"|g|={out.get('grad_norm', float('nan')):.1f}"
            )

    if not all(np.isfinite(losses)):
        print("[rh-train] FAIL: non-finite reward loss", file=sys.stderr)
        return 1

    ckpt_path = ckpt_dir / f"wm_step_{args.steps}.pt"
    model.save_checkpoint(str(ckpt_path), optimizer=opt, step=int(args.steps))
    _assert_reward_head_load_clean(model, ckpt_path)
    k = max(1, len(losses) // 10)
    print(
        f"[rh-train] PASS: loss_reward {np.mean(losses[:k]):.4f}→{np.mean(losses[-k:]):.4f} | "
        f"ckpt → {ckpt_path.resolve()}"
    )
    print(f"[rh-train] log → {log_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
