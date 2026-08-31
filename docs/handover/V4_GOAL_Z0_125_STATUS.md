# V4 goal + z0 alignment STATUS (125)

- **status**: **done** — Phases 0–3 complete; merge **FAIL** (① worse; ④ PASS)
- **started**: 2026-08-17T08:59:00+08:00
- **finished**: 2026-08-17T09:28:00+08:00
- **agent**: composer-2.5-fast
- **prompt**: docs/handover/V4_GOAL_Z0_125_PROMPT.md
- **log**: `logs/v4_goal_z0_gate_rollout.log`
- **HEAD**: `c0d1572` (+ doc finalize commit pending)
- **sleep-safe**: **yes**
- **access**: `cursor-125` direct LAN — see `ACCESS.md` (NOT `cursor-125-public`)

## Goal checklist
1. ✅ Phase 0 — diagnose: log mean|goal_rel|, mean imagined progress, mean_return (expect ≈0 under mock+null)
2. ✅ Phase 1 — inject goals into train_v4_ac; H100 AC retrain → `v4_ac_ckpt_20260817_wm_rh_goal_rgb/`
3. ✅ Phase 2 — align z0 with real RGB (offline encode headon, `--dataset --skip-collect`)
4. ✅ Phase 3 — re-gate ①/④ on 125; honest FAIL/PASS; update V4_GATE_STATUS
5. ⏸ Phase 4 — deferred (① still short; see notes below)
6. ✅ `enable_policy_update` still **false**

## Phase plan
| Phase | Work | Host |
|---|---|---|
| **0** | Probe train_v4_ac metrics under current mock+annotation:null | 125 |
| **1** | Goal inject + H100 AC w/ frozen `wm_ckpt_r60_rh_20260816/wm_step_1000.pt` | H100 |
| **2** | Real-RGB z0 (headon offline encode) | H100 |
| **3** | Gate ①/④ + merge | 125 renderer :41451 |
| **4** | Escalations only if ① still short | as needed |

## Phase 0 — diagnose
| Metric | Value | Notes |
|---|---|---|
| mean\|goal_rel\| | **0.0** | mock+annotation:null (probe `logs/v4_goal_z0_phase0_probe.log`) |
| mean imagined progress | **0.651** | RH still emits progress w/o goal aux |
| mean_return | **3.14** | misleadingly nonzero despite goal_rel≈0 |

## Phase 1 — goal inject + AC
| Field | Value |
|---|---|
| goal source | `_mock_goal_episode` (start→[30,0,5]) injected in `train_v4_ac` |
| wm ckpt | `wm_ckpt_r60_rh_20260816/wm_step_1000.pt` |
| actor ckpt | `v4_ac_ckpt_20260817_wm_rh_goal_rgb/v4_ac_latest.pt` |
| iters | **300** (H100) |
| post-fix mean\|goal_rel\| | **3.05** (train avg) |
| post-fix mean_progress | **6.27** |
| post-fix mean_return | **92.35** |
| mean_actor_loss | **−0.0141** |
| log | H100 `artifacts/v4_ac_train_h100_wm_rh_goal_rgb.log` |

## Phase 2 — z0 RGB align
| Field | Value |
|---|---|
| method | offline encode (headon real RGB, `--dataset --skip-collect`) |
| dataset / buffer | `dataset_v0_headon_20260811` (34 eps, goals via end-proprio proxy) |
| probe mean\|goal_rel\| | **64.96** (4090 2-iter probe) |
| probe mean_progress | **0.715** |
| actor ckpt | `v4_ac_ckpt_20260817_wm_rh_goal_rgb/v4_ac_latest.pt` |
| log | `logs/v4_goal_z0_phase2_rgb_probe.log` |

## Phase 3 — gate
| Signal | Result | Numbers |
|---|---|---|
| **V4-①** | ❌ FAIL | actor_mean **−8.74** vs heur **8.42** (target **9.26**); n=7 |
| **V4-④** | ✅ PASS | v4_hard **0.000** ≤ v1 **0.429** (remeasured same starts) |
| **Merge** | ❌ FAIL | `{1: false, 4: true}` |

Artifacts: `experiments/aerial/rl/artifacts/v4_gate_r60_20260817_wm_rh_goal/v4_gate_r60_20260816.json`

### vs reward-head baseline (2026-08-16)
| | RH only (`*_wm_rh`) | goal+RGB z0 (`*_wm_rh_goal_rgb`) |
|---|---|---|
| ① actor_mean | **−3.17** vs heur 7.44 | **−8.74** vs heur 8.42 ❌ (regressed) |
| ④ v4_hard | 0.143 vs v1 0.25 ✅ | 0.000 vs v1 0.429 ✅ |
| train goal_rel | ≈0 (mock, no inject) | **3.05** avg (nonzero) |
| z0 source | mock encode | headon real RGB |

Goal inject + RGB z0 fixed the train/deploy conditioning gap (nonzero goal_rel, real RGB latents), but ① **regressed** on deploy. **2026-08-18 根因**：规格 `π(a|z)` 无 goal + 300 iter 单 `_mock_goal_episode`；M5d 变差是预测方向。**不要** Phase-4 longer train。见 [`V4_SIGNAL1_STRUCTURAL_REFREEZE_PROPOSAL.md`](V4_SIGNAL1_STRUCTURAL_REFREEZE_PROPOSAL.md)。

## Prior baseline (reward-head, 2026-08-16)
| Signal | Result |
|---|---|
| ① | ❌ actor −3.17 vs heur 7.44 |
| ④ | ✅ 0.143 ≤ v1 0.25 |
| merge | ❌ |

## enable_policy_update
**false** in `configs/aerial_rl.yaml` (verified post-run).

## How to check on return
```bash
ssh cursor-125
cd ~/aerial-wam-v2
cat docs/handover/V4_GOAL_Z0_125_STATUS.md
tail -50 logs/v4_goal_z0_gate_rollout.log
grep enable_policy_update configs/aerial_rl.yaml
```
