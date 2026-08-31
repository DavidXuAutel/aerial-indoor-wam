#!/usr/bin/env python3
"""V4 actor-critic smoke: mock collect + imagination AC update (no Hydra).

Temporarily enables ``enable_policy_update`` in-process only — production yaml
stays ``enable_policy_update: false``.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import yaml

from experiments.aerial.rl.train_rl import build_from_config

logging.basicConfig(level=logging.INFO)


def main() -> int:
    repo = _REPO
    cfg_path = repo / "configs" / "aerial_rl.yaml"
    cfg = yaml.safe_load(cfg_path.read_text())
    cfg.setdefault("corrector", {})
    cfg.setdefault("env", {})
    cfg.setdefault("imagination", {})
    cfg.setdefault("v4", {})
    cfg.setdefault("dynamics", {})
    cfg.setdefault("tau_predictor", {})
    cfg.setdefault("safety", {})
    cfg["corrector"]["iterations"] = 2
    cfg["corrector"]["episodes_per_iter"] = 2
    cfg["corrector"]["enable_policy_update"] = True  # in-process only
    cfg["corrector"]["enable_wm_update"] = False      # isolate AC path
    cfg["corrector"]["imagine_batch"] = 4
    cfg["imagination"]["horizon"] = 5
    cfg["imagination"]["batch"] = 4
    cfg["env"]["backend"] = "mock"
    cfg["dynamics"]["kind"] = "stub"
    cfg["tau_predictor"]["enable"] = False
    cfg["safety"]["kind"] = "null"
    cfg["v4"]["device"] = "cpu"

    loop = build_from_config(cfg)
    if loop.actor_critic is None:
        print("SMOKE_AC_FAIL: actor_critic not built (torch missing?)")
        return 1
    if loop.imagination_policy is None:
        print("SMOKE_AC_FAIL: imagination_policy not wired")
        return 1

    reports = loop.run()
    ok = True
    for i, r in enumerate(reports):
        print(f"iter{i}: rl={r.rl} steps={r.collect.steps}")
        if r.rl.get("status") != "updated":
            ok = False
    print(f"SMOKE_AC_UPDATED={'OK' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
