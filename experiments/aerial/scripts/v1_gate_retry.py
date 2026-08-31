#!/usr/bin/env python3
"""One-off retry helpers for V1 gate partials (remote hosts)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def retry_h100_signal2(repo: Path, wm_ckpt: Path, dataset: Path, out_dir: Path) -> int:
    sys.path.insert(0, str(repo))
    import numpy as np

    from experiments.aerial.rl import dataset as ds
    from experiments.aerial.rl import v1_metrics
    from experiments.aerial.rl import wm_eval
    from experiments.aerial.rl._wm_fidelity_eval import _heldout_split, _make_windows, _recon_curve
    from experiments.aerial.rl._wm_train_validate import _load_world_model_cfg, _refuse_v0
    from experiments.aerial.rl.dynamics_torch import TorchRSSMDynamics

    out_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = repo / "configs/aerial_rl.yaml"
    wm_cfg = _load_world_model_cfg(cfg_path)
    wm_cfg.setdefault("device", "cuda")
    _refuse_v0(dataset, False)
    eps = ds.load_dataset(dataset, skip_quarantined=True)
    held = _heldout_split(eps, 0.25)
    windows = _make_windows(held, 15, 1)
    wm_cfg["image_size"] = int(np.asarray(held[0][0].obs.rgb).shape[0])
    model = TorchRSSMDynamics.from_config(wm_cfg)
    payload = model.load_checkpoint(wm_ckpt)
    out = wm_eval.evaluate(model, windows, horizon=15)
    agg, verdict = out["agg"], out["verdict"]
    recon = _recon_curve(model, windows, 15)
    passed = bool(verdict["passed"] and recon["recon_growth_ok"])
    blob = {
        "verdict": {**verdict, "passed": passed, "recon_growth_ok": recon["recon_growth_ok"]},
        "agg": agg,
        "recon": recon,
        "ckpt": str(wm_ckpt),
        "ckpt_step": payload.get("step"),
        "heldout_frac": 0.25,
    }
    (out_dir / "v1_fidelity_r60_20260815.json").write_text(json.dumps(blob, indent=2, default=str) + "\n")
    s2 = v1_metrics.check_wm_fidelity(
        blob["verdict"],
        agg=blob.get("agg"),
        recon_growth_ok=blob["verdict"].get("recon_growth_ok"),
    )
    s2["fidelity_json"] = str(out_dir / "v1_fidelity_r60_20260815.json")
    partial = {"partial": True, "signals_requested": ["2"], "ok": bool(s2.get("ok")), "signals": {"2": s2}}
    (out_dir / "v1_partial_2_r60_20260815.json").write_text(json.dumps(partial, indent=2, default=str) + "\n")
    print(json.dumps({"ok": s2.get("ok"), "reward_ok": verdict.get("reward_ok"), "coll_ok": verdict.get("coll_ok"), "done_ok": verdict.get("done_ok"), "recon_growth_ok": recon["recon_growth_ok"]}, indent=2))
    return 0 if s2.get("ok") else 1


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=("h100-s2",))
    p.add_argument("--repo", required=True)
    p.add_argument("--wm-ckpt", required=True)
    p.add_argument("--dataset", required=True)
    p.add_argument("--out-dir", required=True)
    args = p.parse_args()
    if args.mode == "h100-s2":
        return retry_h100_signal2(
            Path(args.repo).expanduser(),
            Path(args.wm_ckpt).expanduser(),
            Path(args.dataset).expanduser(),
            Path(args.out_dir).expanduser(),
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
