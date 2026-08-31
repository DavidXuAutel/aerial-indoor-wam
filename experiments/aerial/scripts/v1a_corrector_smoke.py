#!/usr/bin/env python3
"""V1a corrector smoke: mock collect + WM update (no Hydra)."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import yaml

from experiments.aerial.rl.train_rl import build_from_config

logging.basicConfig(level=logging.INFO)


def main() -> int:
    repo = Path(__file__).resolve().parents[3]
    cfg_path = repo / "configs" / "aerial_rl.yaml"
    cfg = yaml.safe_load(cfg_path.read_text())
    cfg.setdefault("corrector", {})
    cfg.setdefault("env", {})
    cfg["corrector"]["iterations"] = 3
    cfg["corrector"]["episodes_per_iter"] = 2
    cfg["corrector"]["wm_batch"] = 8
    cfg["env"]["backend"] = "mock"

    loop = build_from_config(cfg)
    reports = loop.run()
    for i, r in enumerate(reports):
        print(f"iter{i}: wm={r.wm} rl={r.rl} steps={r.collect.steps}")
    ok = all(r.wm.get("status") == "updated" for r in reports)
    print(f"SMOKE_WM_UPDATED={'OK' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
