"""Train FOE τ calibrator on r60 with GT depth+vel pseudo-labels (Phase 2).

Inference never reads GT depth — only RGB optical flow features. Labels come
from ``gt_tau_from_depth_velocity`` (design §1.2.3 allows pseudo-labels).

    python -m experiments.aerial.rl.train_tau_foe \\
      --dataset ~/aerial-rl-skeleton/.../dataset_v0_local_depth_r60_20260814 \\
      --out-dir ~/aerial-rl-skeleton/.../tau_ckpt_foe_r60_20260815 \\
      --steps 2000 --device cuda

Does **not** flip yaml ``tau_predictor.kind`` — human flips to ``foe_calibrated``
after auth ③ PASS.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


def _collect_pairs(
    dataset: Path,
    *,
    heldout_frac: float,
    max_pairs: int,
    nav_band_max_tau_s: float,
    center_frac: float,
) -> Tuple[List[np.ndarray], List[float], List[np.ndarray], List[float]]:
    from experiments.aerial.rl import dataset as ds
    from experiments.aerial.rl.tau_predictor import (
        estimate_foe,
        foe_flow_features,
        gt_tau_from_depth_velocity,
        optical_flow_farneback,
    )

    episodes = ds.load_dataset(dataset, skip_quarantined=True)
    n_ep = len(episodes)
    split = int(n_ep * (1.0 - heldout_frac)) if n_ep else 0
    train_eps = episodes[:split] if split > 0 else episodes
    held_eps = episodes[split:] if split < n_ep else []

    def _harvest(eps: List[Any], limit: int) -> Tuple[List[np.ndarray], List[float]]:
        xs: List[np.ndarray] = []
        ys: List[float] = []
        for ep in eps:
            if len(xs) >= limit:
                break
            for i in range(1, len(ep)):
                if len(xs) >= limit:
                    break
                prev, curr = ep[i - 1].obs, ep[i].obs
                if curr.depth is None:
                    continue
                tau_gt = gt_tau_from_depth_velocity(
                    curr.depth, curr, center_frac=center_frac
                )
                if tau_gt is None or not np.isfinite(tau_gt):
                    continue
                if float(tau_gt) > float(nav_band_max_tau_s):
                    continue
                dt = float(curr.t) - float(prev.t)
                if not np.isfinite(dt) or dt <= 1e-4:
                    dt = 0.1
                flow = optical_flow_farneback(prev.rgb, curr.rgb)
                foe = estimate_foe(flow)
                feats = foe_flow_features(flow, foe=foe, center_frac=center_frac)
                # Calibrator predicts τ in *frames*; label = τ_s / dt.
                xs.append(feats)
                ys.append(float(tau_gt) / max(dt, 1e-3))
        return xs, ys

    x_tr, y_tr = _harvest(train_eps, max_pairs)
    x_va, y_va = _harvest(held_eps, max(max_pairs // 4, 64))
    return x_tr, y_tr, x_va, y_va


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Train FOE τ calibrator (Phase 2)")
    p.add_argument("--dataset", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--steps", type=int, default=2000)
    p.add_argument("--batch", type=int, default=64)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--heldout-frac", type=float, default=0.25)
    p.add_argument("--max-pairs", type=int, default=8000)
    p.add_argument("--nav-band-max-tau-s", type=float, default=10.0)
    p.add_argument("--center-frac", type=float, default=0.5)
    p.add_argument("--device", default="cuda")
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args(argv)

    import torch

    dataset = Path(args.dataset).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[tau-foe] harvesting flow features from {dataset} ...", flush=True)
    t0 = time.time()
    x_tr, y_tr, x_va, y_va = _collect_pairs(
        dataset,
        heldout_frac=float(args.heldout_frac),
        max_pairs=int(args.max_pairs),
        nav_band_max_tau_s=float(args.nav_band_max_tau_s),
        center_frac=float(args.center_frac),
    )
    print(
        f"[tau-foe] train={len(y_tr)} held={len(y_va)} "
        f"harvest_s={time.time() - t0:.1f}",
        flush=True,
    )
    if len(y_tr) < 32:
        print("[tau-foe] FAIL: too few training pairs (need approaching frames)", flush=True)
        return 2

    from experiments.aerial.rl.tau_predictor import FoeTauCalibrator

    device = str(args.device)
    if device.startswith("cuda") and not torch.cuda.is_available():
        print("[tau-foe] WARN: cuda unavailable; falling back to cpu", flush=True)
        device = "cpu"

    torch.manual_seed(int(args.seed))
    model = FoeTauCalibrator.build_module().to(device)
    opt = torch.optim.Adam(model.parameters(), lr=float(args.lr))
    x_t = torch.from_numpy(np.stack(x_tr).astype(np.float32))
    y_t = torch.from_numpy(np.asarray(y_tr, dtype=np.float32)).reshape(-1, 1)
    x_v = (
        torch.from_numpy(np.stack(x_va).astype(np.float32))
        if x_va
        else None
    )
    y_v = (
        torch.from_numpy(np.asarray(y_va, dtype=np.float32)).reshape(-1, 1)
        if y_va
        else None
    )

    log_path = out_dir / "tau_foe_train.jsonl"
    n = len(y_tr)
    batch = min(int(args.batch), n)
    t_train0 = time.time()
    model.train()
    with log_path.open("w") as logf:
        for step in range(1, int(args.steps) + 1):
            idx = np.random.randint(0, n, size=batch)
            xb = x_t[idx].to(device)
            yb = y_t[idx].to(device)
            pred = model(xb)
            loss = torch.mean(torch.abs(pred - yb))
            opt.zero_grad(set_to_none=True)
            loss.backward()
            opt.step()
            if step == 1 or step % 100 == 0 or step == int(args.steps):
                row: Dict[str, Any] = {
                    "step": step,
                    "loss_mae_frames": float(loss.item()),
                }
                if x_v is not None and y_v is not None and len(y_va) > 0:
                    model.eval()
                    with torch.no_grad():
                        pv = model(x_v.to(device))
                        row["held_mae_frames"] = float(torch.mean(torch.abs(pv - y_v.to(device))).item())
                    model.train()
                logf.write(json.dumps(row) + "\n")
                logf.flush()
                print(f"[tau-foe] {row}", flush=True)

    ckpt = out_dir / "tau_foe_calibrator.pt"
    payload = {
        "model": model.state_dict(),
        "kind": "foe_calibrator",
        "feature_dim": 8,
        "steps": int(args.steps),
        "dataset": str(dataset),
        "n_train": len(y_tr),
        "n_held": len(y_va),
        "train_wall_s": time.time() - t_train0,
    }
    torch.save(payload, ckpt)
    meta = {k: v for k, v in payload.items() if k != "model"}
    (out_dir / "tau_foe_meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(f"[tau-foe] wrote {ckpt}", flush=True)
    print(f"[tau-foe] ETA done; wall_train_s={meta['train_wall_s']:.1f}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
