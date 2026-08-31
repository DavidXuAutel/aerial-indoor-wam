# Aerial WAM v2

Pure-vision aerial world model (DreamerV3 RSSM) for OpenFly/AirSim.

**V0 gate: ✅ PASS** (2026-08-14) — four-signal merge `v0_gate_r60_20260814.json`; flags flipped: `depth_head.enable`, `safety.kind: threshold`.

**Current phase: V1** — WM live loop → τ + imagination planner → V4 model-based RL. See [V1/V4 design](docs/design/2026-08-15-v1-v4-design.md).

This repository is a **clean extraction** from the `aerial-rl-skeleton` worktree of `robomaster-tt-control`. It contains the full `experiments/aerial/` tree (V0 RL/gate, sim_verify, B0/B1 orchestration, collapse_fix, OpenFly eval helpers) plus V0 specs/runbooks — **not** the FastWAM `src/` training stack or Tello flight control.

## Quick links

| Doc | Purpose |
|---|---|
| [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md) | **Current state, formulas, V1/V4 roadmap** |
| [docs/handover/V0_GATE_STATUS.md](docs/handover/V0_GATE_STATUS.md) | V0 merge record (PASS) |
| [docs/handover/V1_GATE_STATUS.md](docs/handover/V1_GATE_STATUS.md) | V1 gate progress |
| [docs/design/2026-08-15-v1-v4-design.md](docs/design/2026-08-15-v1-v4-design.md) | V1/V4 design |
| [experiments/aerial/RUNBOOK_v0.md](experiments/aerial/RUNBOOK_v0.md) | Top-level runbook (living doc) |
| [docs/superpowers/specs/2026-08-04-aerial-wam-v2-frozen-spec.md](docs/superpowers/specs/2026-08-04-aerial-wam-v2-frozen-spec.md) | Frozen thresholds (§4.1) |
| [experiments/aerial/scripts/RUNBOOK_sync_and_env.md](experiments/aerial/scripts/RUNBOOK_sync_and_env.md) | Mac / H100 / 4090 sync & env |

## Machines

| Role | Host |
|---|---|
| Dev (Mac) | This repo |
| Train + offline gate (①③) + rollout client (②④) | `a25689@10.239.121.25:31126` |
| AirSim renderer | `10.229.20.125:41451` |

Artifacts (checkpoints, datasets) live on H100 under `~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/` — **not in git**.

## Minimal setup (H100)

```bash
INSTALL=1 source experiments/aerial/scripts/env_h100.sh
source experiments/aerial/scripts/env_h100.sh
```

## V0 gate (completed)

```bash
python -m experiments.aerial.rl._v0_gate --merge \
  artifacts/v0_partial_1_r60_20260814.json \
  artifacts/v0_partial_3_r60_20260814.json \
  artifacts/v0_partial_24_r60_20260814.json \
  --emit artifacts/v0_gate_r60_20260814.json
```

Exit 0 → V0 flags flipped in `configs/aerial_rl.yaml`. V1/V4 flags remain OFF until their gates pass.
