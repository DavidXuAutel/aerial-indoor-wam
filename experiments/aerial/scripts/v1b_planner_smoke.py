#!/usr/bin/env python3
"""V1b planner smoke: mock collect with imagination scoring (no Hydra)."""
from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import yaml

from experiments.aerial.rl.train_rl import build_from_config


def main() -> int:
    cfg_path = _REPO / "configs" / "aerial_rl.yaml"
    cfg = yaml.safe_load(cfg_path.read_text())
    cfg.setdefault("env", {})
    cfg.setdefault("dynamics", {})
    cfg.setdefault("planner", {})
    cfg.setdefault("safety", {})
    cfg["env"]["backend"] = "mock"
    cfg["dynamics"]["kind"] = "stub"
    cfg["planner"]["enable"] = True
    cfg["planner"]["horizon"] = 3
    cfg["safety"]["kind"] = "depth_tau"
    cfg.setdefault("corrector", {})
    cfg["corrector"]["iterations"] = 1
    cfg["corrector"]["episodes_per_iter"] = 1
    cfg["corrector"]["max_steps"] = 5

    loop = build_from_config(cfg)
    reports = loop.run()
    steps = reports[0].collect.steps
    ok = steps >= 1
    print(f"steps={steps} SMOKE_PLANNER={'OK' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
