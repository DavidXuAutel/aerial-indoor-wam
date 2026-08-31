# Reopen RH progress head — R1 analytic Δ‖g‖ in imagine (125)

- **status**: **DONE** (R1 + calib PASS + H100 retrain + ① re-gate; merge still FAIL)
- **prompt**: `docs/handover/V4_RH_REOPEN_125_PROMPT.md`
- **started**: 2026-08-18
- **finished**: 2026-08-18
- **agent**: composer-2.5-fast on 125
- **renderer**: `127.0.0.1:41451`
- **enable_policy_update**: must stay **false** (unchanged)

Pre-committed: sign §5 「重开 RH progress 头」= **R1** (`imagine` aux progress = `analytic_progress(g, a[:3])`, keep RH `p_coll` / z). **Not** RH retrain. **Not** yaw rotation. **Not** §4 In-table. **Not** warm-start C2 π.

## Phase 0 — sign

- **DONE** 2026-08-18 — §5 「重开 RH progress 头」= **[x]**，裁定 **重开并落地 R1**；HEAD `7883b89` → `d96da1d`；`advance_goal_rel_body` yaw **unchecked**.

## Phase 1 — code

- **DONE** — `imagination.py` aux path: `progs` + `reward_terms` use `analytic_progress(goal_rel_t, a[:3])` (no maneuver in progress); `dynamics.step` unchanged for `p_coll` / z.
- Tests rewritten: `test_imagination_aux.py` (analytic ±1.0, zero-action, p_coll from step).
- **292 passed** (`test_imagination_aux` + stub + action_space); full suite on 125: **292 passed**.

## Phase 2 — calib on R1 (old C2 ckpt)

- **PASS** — accept table: arm (b) ratio **1.00** ∈ [0.8, 1.2]; arm (c) **same sign** (−15.00 / −15.00).
- JSON: `artifacts/v4_imagine_return_decomp_c2train_a23_r1_20260818.json`, `..._a4_r1_...`, `artifacts/v4_rh_progress_calib_c2train_r1_20260818.json`.
- Baseline 20260818 JSON **not overwritten**.

| arm | Σ progress (R1) | Σ Δ‖g‖ | ratio |
|---|---|---|---|
| (a) π | +12.26 | +12.26 | **1.00** |
| (b) max forward | +14.99 | +14.99 | **1.00** |
| (c) max retreat | −15.00 | −15.00 | **1.00** |

## Phase 3 — H100 from-scratch AC

- **DONE** — bundle `HEAD` → H100; `train_v4_ac` 300 iter, **no** warm-start C2.
- ckpt: `experiments/aerial/rl/artifacts/v4_ac_ckpt_20260818_c2_analytic_progress/v4_ac_latest.pt`
- Log: `policy_class=tanh_bounded_v1`, `mean_return=1.40`, `mean_abs_goal_rel=3.05`, zero `n_action_clipped` warn.

### Post-train §A (new subsection; old C2 table untouched)

| Arm | Σ progress | λ G0 | a0 x | n_clip | ‖goal‖ 30→ |
|---|---|---|---|---|---|
| (a) analytic π | +5.72 | **−0.72** | +0.745 | **0** | 24.3 |
| (b) max forward | +14.99 | +4.77 | +1.0 | **0** | 15.0 |
| (c) max retreat | −15.00 | −16.17 | −1.0 | **0** | 45.0 |

JSON: `artifacts/v4_imagine_return_decomp_analytic_a23_20260818.json`, `..._a4_...`.

## Phase 4 — ① re-gate (renderer)

Renderer **UP** (`127.0.0.1:41451`). Both seeds; **n=5 scored** each (requested 10 / 8) ⇒ `authoritative=false`. **Do not** lower `n`. yaml untouched.

| run | n scored | actor mean | heur | target | ① | ④ v4_hard vs v1 |
|---|---|---|---|---|---|---|
| seed=0 | 5 | **−2.65** | 7.89 | 8.68 | **FAIL** | 0.143 vs 0.429 **PASS** |
| seed=1 | 5 | **−1.38** | 9.85 | 10.83 | **FAIL** | 0.167 vs 0.400 **PASS** |

Dirs: `v4_gate_r60_20260818_analytic` / `..._analytic_n8`.

`v4_progress_diag.py` (`--imagine-horizon 15`, new ckpt):

| run | n scored | mean cos(first_act) | imagΣG mean | in_table |
|---|---|---|---|---|
| seed=0 | 3 | **+0.982** | **+4.34** | do_not_sign |
| seed=1 | 4 | **+0.972** | **+4.17** | do_not_sign |

JSON: `artifacts/v4_progress_diag_analytic_seed{0,1}_20260818.json`. Imagined ΣG collapsed from C2 ~85 → ~4 (R1 honest); ① still FAIL; **不签** §4 In 表.

## Verdict

- **R1 identity: PASS** (calib 1:1 on old π probe).
- **V4 merge: FAIL** — ① non-authoritative FAIL both seeds; ④ PASS.
- **enable_policy_update**: **false** (unchanged).
