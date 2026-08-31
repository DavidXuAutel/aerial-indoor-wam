# V4 encode + longer train STATUS (125)

- **status**: **done** — encode path fixed, H100 train + gate re-run complete (merge **FAIL**)
- **started**: 2026-08-16T16:38:00+08:00
- **finished**: 2026-08-16T17:15:00+08:00
- **prompt**: docs/handover/V4_ENCODE_TRAIN_125_PROMPT.md
- **HEAD**: `2065f76` (+ ckpt load fixes `8692475`, `9282adc`)
- **sleep-safe**: **yes**

## Goal checklist
1. ✅ Train + deploy torch WM encode (latent_dim=1536, not stub proprio4)
2. ✅ H100 300-iter AC train → `v4_ac_ckpt_20260816_wm/v4_ac_latest.pt`
3. ✅ Gate ①/④ re-run + merge + docs updated
4. ✅ `enable_policy_update` still **false**

## Phase A — encode path ✅
- Shared `load_torch_dynamics()`; `--dynamics torch` + `--wm-ckpt` on train and gate
- Legacy ckpt load: shape-filter + optimizer skip (`dynamics_torch.py`)
- Tests PASSED; pushed origin

## Phase B — H100 longer train ✅
| Field | Value |
|---|---|
| iters | 300 |
| imagine_horizon | 15 |
| dynamics | torch |
| wm ckpt | `wm_ckpt_r60_20260814/wm_step_5000.pt` step=5000 |
| latent_dim | **1536** |
| mean_actor_loss | **−0.0005** |
| actor ckpt | `v4_ac_ckpt_20260816_wm/v4_ac_latest.pt` (~3.5MB) |
| log | H100 `artifacts/v4_ac_train_h100_wm.log` |

## Phase C — gate on 125 ✅ (honest FAIL)

**Command** (torch WM encode deploy):
```bash
source experiments/aerial/scripts/env_4090.sh
$PYTHON_BIN experiments/aerial/scripts/v4_gate_run_partials.py rollout4090 \
  --repo ~/aerial-wam-v2 \
  --rollout-dataset ~/aerial-rl-skeleton/.../dataset_v0_headon_20260811 \
  --actor-ckpt experiments/aerial/rl/artifacts/v4_ac_ckpt_20260816_wm/v4_ac_latest.pt \
  --wm-ckpt experiments/aerial/rl/artifacts/wm_ckpt_r60_20260814/wm_step_5000.pt \
  --dynamics-kind torch \
  --depth-ckpt experiments/aerial/rl/artifacts/depth_ckpt_da3_r60_20260814/depth_step_2000_da3_ft_head.pt \
  --tau-ckpt experiments/aerial/rl/artifacts/tau_ckpt_foe_r60_20260815/tau_foe_calibrator.pt \
  --env-host 127.0.0.1 --device cuda \
  --out-dir experiments/aerial/rl/artifacts/v4_gate_r60_20260816_wm
# merge → v4_gate_r60_20260816.json ok=false
```

| Signal | Result | Numbers |
|---|---|---|
| **V4-①** | ❌ FAIL | actor_mean **−68.88** vs heur **10.66** (target 11.72); n=6 |
| **V4-④** | ❌ FAIL | v4_hard **0.143** > v1_hard **0.00** |
| **Merge** | ❌ FAIL | `{1: false, 4: false}` |

Log: `logs/v4_encode_gate_rollout.log` (~26 min). Deploy log confirms: `torch WM encode path latent_dim=1536`.

## vs M5 (stub encode)
| | M5 stub | This run torch WM |
|---|---|---|
| ① actor_mean | −13.54 | **−68.88** (worse) |
| ④ v4_hard | 0.00 ✅ | **0.143** ❌ |
| latent_dim | 8 | **1536** |

Encode path is fixed; actor still regresses — imagination reward-head mismatch (legacy ckpt `reward_head.0` shape skipped) + `imagine()` missing `goal_rel`/`body_vel`.

**Follow-on (2026-08-16)**: reward-head track — see `docs/handover/V4_REWARD_HEAD_125_PROMPT.md` / `V4_REWARD_HEAD_125_STATUS.md` (finetune RH frozen backbone → AC retrain → re-gate). Phase 1 code landed: `train_reward_head.py`, `imagine()` aux pass-through, corrector goal_rel/body_vel from obs. This encode-train track stays **done**.

## enable_policy_update
**false** in `configs/aerial_rl.yaml` (verified post-run).

## Artifacts (gitignored, on disk)
- `experiments/aerial/rl/artifacts/v4_ac_ckpt_20260816_wm/`
- `experiments/aerial/rl/artifacts/wm_ckpt_r60_20260814/` (staged from H100)
- `experiments/aerial/rl/artifacts/v4_gate_r60_20260816_wm/`
