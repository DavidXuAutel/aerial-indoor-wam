# V4 reward-head fix STATUS (125)

- **status**: **done** — Phase 1–3 complete; merge **FAIL** (① still below heur; ④ PASS)
- **started**: 2026-08-16T22:02:00+08:00
- **finished**: 2026-08-16T22:26:00+08:00
- **agent**: composer-2.5-fast
- **prompt**: docs/handover/V4_REWARD_HEAD_125_PROMPT.md
- **log**: `logs/v4_reward_head_gate_rollout.log`
- **HEAD**: `bc0c2d8` (+ doc finalize commit pending)
- **sleep-safe**: **yes**

## Goal checklist
1. ✅ Phase 1 — RH finetune + imagine aux; `load_skipped` empty for reward_head
2. ✅ Phase 2 — H100 AC retrain → `v4_ac_ckpt_20260816_wm_rh/`
3. ✅ Phase 3 — Gate ①/④ re-run + merge + docs (honest FAIL/PASS)
4. ✅ `enable_policy_update` still **false**

## Phase 1A — RH finetune ✅ (H100)
| Field | Value |
|---|---|
| backbone | `wm_ckpt_r60_20260814/wm_step_5000.pt` |
| steps | 1000 |
| loss_reward | 1.8611 → **0.7047** |
| new ckpt | `wm_ckpt_r60_rh_20260816/wm_step_1000.pt` |
| load_skipped (reward) | **[]** ✅ |
| log | H100 `artifacts/v4_rh_finetune_h100.log` |

## Phase 1B — imagine aux ✅
- `imagine(goal_rel0, body_vel0)` + `advance_goal_rel_body`
- `corrector._update_policy` passes obs-derived aux
- `TorchRSSMDynamics.set_imagination_aux` cache fallback

## Phase 2 — H100 AC retrain ✅
| Field | Value |
|---|---|
| iters | 300 |
| wm ckpt | `wm_ckpt_r60_rh_20260816/wm_step_1000.pt` |
| actor ckpt | `v4_ac_ckpt_20260816_wm_rh/v4_ac_latest.pt` |
| mean_actor_loss | **−0.0087** |
| latent_dim | **1536** |
| log | H100 `artifacts/v4_ac_train_h100_wm_rh.log` |

## Phase 3 — gate ✅ (honest partial FAIL)

| Signal | Result | Numbers |
|---|---|---|
| **V4-①** | ❌ FAIL | actor_mean **−3.17** vs heur **7.44** (target **8.18**); n=5 |
| **V4-④** | ✅ PASS | v4_hard **0.143** ≤ v1 **0.250** (remeasured same starts) |
| **Merge** | ❌ FAIL | `{1: false, 4: true}` |

Artifacts: `experiments/aerial/rl/artifacts/v4_gate_r60_20260816_wm_rh/v4_gate_r60_20260816.json`

### vs encode-train (broken RH)
| | encode-train | reward-head fix |
|---|---|---|
| ① actor_mean | **−68.88** | **−3.17** (much better, still FAIL) |
| ④ v4_hard | 0.143 vs v1 **0.00** ❌ | 0.143 vs v1 **0.25** ✅ |
| RH load_skipped | non-empty | **[]** |

RH fix + imagine aux resolved the garbage-reward regression; ① still needs stronger AC / longer train (mock-collector AC vs real 4090 deploy gap).

**Follow-on (2026-08-17)**: goal + z0 alignment track — see `docs/handover/V4_GOAL_Z0_125_STATUS.md`. Result: goal inject + RGB z0 fixed train conditioning but ① regressed (−3.17→−8.74); ④ PASS. Phase 4 escalations deferred. This reward-head track stays **done**.

## enable_policy_update
**false** in `configs/aerial_rl.yaml` (verified post-run).

## How to check on return
```bash
cd ~/aerial-wam-v2
cat docs/handover/V4_REWARD_HEAD_125_STATUS.md
tail -20 logs/v4_reward_head_gate_rollout.log
grep enable_policy_update configs/aerial_rl.yaml
```


## Access note (2026-08-17)
On-campus again: use `cursor-125` / `origin`→direct; offsite fallback remains `cursor-125-public`. See `docs/handover/ACCESS.md`.
