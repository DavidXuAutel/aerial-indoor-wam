# V4 M5 STATUS (125 offline)

- **handoff_checked**: 2026-08-16T16:24:16+08:00

- **started**: 2026-08-16T12:35:19+08:00
- **finished**: 2026-08-16T13:05:19+08:00
- **agent**: composer-2.5-fast (completed; stale hung PIDs 1035845/1043095/1551733 cleaned 2026-08-16T16:24:16+08:00)
- **prompt**: docs/handover/V4_M5_125_PROMPT.md
- **HEAD**: 4ebdfb8
- **renderer**: 127.0.0.1:41451 ✅ (AirSim RPC up)
- **python**: `source experiments/aerial/scripts/env_4090.sh` → `/home/yao/sim_verify/.venv/bin/python` (airsim + torch 2.13+cu130 + einops/addict/timm for DA3 depth head)
- **log**: `artifacts/v4_m5_125_rollout.log`

## Mac sleep

**Yes — Mac may sleep.** M5 gate eval already finished and committed; no live agent required.

## How to check on return

```bash
ssh cursor-125  # offsite: cursor-125-public
cd ~/aerial-wam-v2
cat docs/handover/V4_M5_125_STATUS.md
tail -50 artifacts/v4_m5_125_rollout.log
git log -3 --oneline
pgrep -af "agent --print" || echo no_agent
```

## enable_policy_update

**Still `false`** in `configs/aerial_rl.yaml` (verified post-run; not flipped per gate rules).

## Commands

```bash
cd ~/aerial-wam-v2
source experiments/aerial/scripts/env_4090.sh

# rollout (4090 loopback; headon corpus — r60 scan fails on this host)
$PYTHON_BIN experiments/aerial/scripts/v4_gate_run_partials.py rollout4090 \
  --repo ~/aerial-wam-v2 \
  --rollout-dataset ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/dataset_v0_headon_20260811 \
  --actor-ckpt experiments/aerial/rl/artifacts/v4_ac_ckpt_20260816/v4_ac_latest.pt \
  --depth-ckpt experiments/aerial/rl/artifacts/depth_ckpt_da3_r60_20260814/depth_step_2000_da3_ft_head.pt \
  --tau-ckpt experiments/aerial/rl/artifacts/tau_ckpt_foe_r60_20260815/tau_foe_calibrator.pt \
  --env-host 127.0.0.1 \
  --device cuda \
  --out-dir experiments/aerial/rl/artifacts/v4_gate_r60_20260816 \
  2>&1 | tee artifacts/v4_m5_125_rollout.log

# merge
$PYTHON_BIN experiments/aerial/scripts/v4_gate_run_partials.py merge \
  --repo ~/aerial-wam-v2 \
  --out-dir experiments/aerial/rl/artifacts/v4_gate_r60_20260816
```

**Pitfalls**:
- `/usr/bin/python3` and bare `anaconda3/bin/python3` lack `airsim` → scan `reset_error=1000`.
- `dataset_v0_local_depth_r60_20260814` scan also fails here; use **headon** corpus (same harness as V1-①).
- sim_verify venv needed `einops`, `addict`, `timm` (via `pip install timm`) for DA3 depth ckpt load.

**Ckpt staging** (from H100 via `ssh h100-25`): actor `v4_ac_latest.pt`, depth r60 DA3 head, tau foe_calibrated.

## M5 results (authoritative partials + merge)

| Signal | Criterion | Result | Numbers |
|---|---|---|---|
| **V4-①** | actor progress ≥ heuristic × 1.10 | ❌ **FAIL** | actor_mean **−13.54** vs heur **9.71** (target **10.68**); n=6 scored / 8 scan accepted |
| **V4-④** | v4 hard coll ≤ v1 baseline; near ratio ≤ 0.80 | ✅ **PASS** | v4_hard **0.00** vs v1_hard **0.00** (remeasured same starts; auth baseline **0.50**); near_ratio **0.00** |

**Merge**: ❌ **FAIL** (`ok=false`; passed `{1: false, 4: true}`)

Artifacts (gitignored, on disk):

- `experiments/aerial/rl/artifacts/v4_gate_r60_20260816/v4_partial_1_r60_20260816.json`
- `experiments/aerial/rl/artifacts/v4_gate_r60_20260816/v4_partial_4_r60_20260816.json`
- `experiments/aerial/rl/artifacts/v4_gate_r60_20260816/v4_gate_r60_20260816.json`

### V4-④ detail

| Arm | hard coll | near on | near off | near ratio | n |
|---|---|---|---|---|---|
| v4 actor shield-on | 0.00 | 0.000 | 0.018 | 0.00 | 8 |
| v4 actor shield-off | 0.125 | 0.021 | 0.051 | 0.41 | 8 |
| v1 heuristic shield-on (remeasured) | 0.00 | 0.194 | 0.101 | 1.91 | 5 |

V1-① authoritative baseline **0.50** documented for reference; comparison used **remeasured** heuristic on same starts (0.00 this run; 3 spawn drops).

## Code delivered

- `experiments/aerial/scripts/v4_gate_run_partials.py` — rollout4090 + merge
- `experiments/aerial/rl/actor_critic.py` — `load_from_checkpoint`, `LatentActorDeployPolicy`

## Next

- M6 flip `enable_policy_update` **blocked** (merge FAIL on ①).
- Actor negative progress on obstacle-facing starts — needs longer H100 imagination training and/or torch-WM encode deploy path (current rollout uses stub `encode(proprio4)` matching H100 mock short-train).

## Cleanup (2026-08-16 ~16:20+08)

- M5 merge already **DONE** (finished 13:05; gate `ok=false`).
- Killed leftover detached agents: **1035845 / 1043095 / 1551733** (do not restart).
- **sleep-safe: yes** — no M5 agent should be running; renderer :41451 unrelated.
- Gate artifact: `experiments/aerial/rl/artifacts/v4_gate_r60_20260816/v4_gate_r60_20260816.json`
