#!/usr/bin/env python3
"""V1b τ channel smoke: mock collect fills obs.info['tau_pred'] (no Hydra)."""
from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import yaml

from experiments.aerial.rl.buffer import ReplayBuffer
from experiments.aerial.rl.collector import RolloutCollector
from experiments.aerial.rl.reward import RewardConfig
from experiments.aerial.rl.safety import ThresholdSafetyShield
from experiments.aerial.rl.tau_predictor import TauPredictor
from experiments.aerial.rl.train_rl import HeuristicPolicy, _build_env


def main() -> int:
    repo = Path(__file__).resolve().parents[3]
    cfg = yaml.safe_load((repo / "configs" / "aerial_rl.yaml").read_text())
    cfg.setdefault("env", {})
    cfg["env"]["backend"] = "mock"

    env = _build_env(cfg["env"])
    buffer = ReplayBuffer(capacity_episodes=4, seed=0)
    collector = RolloutCollector(
        env,
        HeuristicPolicy(goal_getter=lambda: getattr(env, "goal", None)),
        buffer,
        reward_cfg=RewardConfig(),
        safety=ThresholdSafetyShield(min_depth_m=999.0, min_tau_s=1.0),
        max_steps=5,
        tau_predictor=TauPredictor(),
    )
    _, stats = collector.collect_episode()
    if stats.episodes != 1 or stats.steps < 1:
        print("SMOKE_TAU_PRED=FAIL (no steps collected)")
        return 1

    ep = buffer._episodes[-1]
    taus = [
        float(t.obs.info["tau_pred"])
        for t in ep
        if "tau_pred" in t.obs.info
    ]
    ok = len(taus) == stats.steps and all(t > 0 for t in taus)
    print(f"steps={stats.steps} tau_steps={len(taus)} SMOKE_TAU_PRED={'OK' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
