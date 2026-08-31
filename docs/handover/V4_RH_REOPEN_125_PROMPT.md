# Reopen RH progress head (R1: analytic Δ‖g‖ in imagine) — run on 125

Living status (update as you go): `docs/handover/V4_RH_REOPEN_125_STATUS.md`.  
Context: `docs/handover/V4_GATE_STATUS.md` §1, `V4_RH_CALIB_125_STATUS.md`, `V4_SIGNAL1_STRUCTURAL_REFREEZE_PROPOSAL.md` §5.  
Access: `docs/handover/ACCESS.md` — on-campus **`cursor-125`**. You are ON **125** (`/home/yao/aerial-wam-v2`). Renderer: `127.0.0.1:41451`. Python: `source experiments/aerial/scripts/env_4090.sh` → `$PYTHON_BIN`. H100: `ssh h100-25` (`source experiments/aerial/scripts/env_h100.sh`).

## Hard rules

- **Do NOT** flip `enable_policy_update` (must stay `false`). Do **not** change `δ_p` / `n` / yaml gate switches.
- **Do NOT** push GitHub; only `git push origin main` (bare on 125).
- Never modify Franka / robot network; never use `10.229.66.70`.
- **Do NOT** implement §4 In-table (goal concat into actor/critic). Cos ≥ 0 already said **do not sign**.
- **Do NOT** retrain the current C2 π (`v4_ac_ckpt_20260818_c2_fromscratch`). After R1, AC **from-scratch** only (new ckpt dir). **No** warm-start of any `v4_ac_ckpt_20260818_*`.
- **Do NOT** change `advance_goal_rel_body` yaw rotation this job (rewrites every §A number; separate checkbox).
- **Do NOT** retrain `reward_head` / `train_reward_head.py` this job (see R1 vs R2 below).
- **Do NOT** change `reward.py` / `w_progress` / `w_maneuver`.
- **Do NOT** use `sync_pull.sh` on H100 (H100 `origin` is GitHub, 几十 commits behind). Sync H100 with a **git bundle from 125**.
- Honest FAIL is OK. Do **not** lower `n`. One agent only — kill duplicates before launching long jobs.

## Why this job exists

C2 ① still FAIL. Cos diag **do not sign** In-table. RH calib curve (**DONE**, offline) vs stub kinematics:

| arm | Σ RH | Σ Δ‖g‖ | ratio |
|---|---|---|---|
| (a) C2 π | +81.64 | +12.26 | **6.66×** |
| (b) max forward, yaw≡0 | +62.60 | +14.99 | **4.18×** |
| (c) max retreat | +9.28 | −15.00 | **wrong sign** |

Shape: t0–t4 near-calibrated; **from t≈6 RH reports 6–9 m/step** while geometry stays ~1. Arm (b) yaw≡0 ⇒ not `advance_goal_rel_body` missing yaw. This is RH vs **stub kinematics**, not vs real ①.

`out.progress` in `TorchRSSMDynamics.step` is the reward-head **symexp two-hot readout** (`dynamics_torch.py:1279`), not Δ‖g‖. Actor trains via `imagine()` → `reward_terms(out.progress, …)` (`imagination.py:153-155`). Stub already uses `prev_dist − new_dist` (`dynamics.py:144-146`).

Retraining the head on **teacher-forced real windows** does not constrain imagined **prior** z after t≈6. So this job does **not** run another 1000-step `train_reward_head`.

## Pre-committed decision (do not renegotiate)

**Sign** proposal §5 「重开 RH progress 头」= **重开，落地 R1**（不是「不重开」）.

**R1 (this job):** when `imagine(..., goal_rel0=…)` is on the aux path, **replace** the progress used for `progs` and `reward_terms` with **pure kinematic Δ‖g‖**:

```
analytic_progress(goal_rel_t[b], a[:3])   # NO action= / NO w_maneuver
```

That identity is already proven in calib: `analytic_t = goal_dist[t]−goal_dist[t+1]` ≡ batch-mean `analytic_progress(g_t, a_t[:3])` under `advance_goal_rel_body`.

Still call `dynamics.step(..., goal_rel=…, body_vel=…)` so **z_next / p_coll** stay the WM. Ignore `out.progress` on the aux path. **Do not** subtract maneuver inside progress — `reward_terms` already applies `w_maneuver * ‖a‖`. Double-counting would silently retune the 100:1 weights.

When `goal_rel0 is None` (no aux): keep `out.progress` (stub tests / legacy).

**Do not** patch `TorchRSSMDynamics.step` itself (wm_eval fidelity of the head must remain measurable).

### Calib accept / reject (Phase 2, **old** C2 ckpt — measures imagine(), not π quality)

Re-run decomp + `v4_rh_progress_calib.py`. Pre-committed:

| result | meaning | next |
|---|---|---|
| arm (b) \|Σprogress / ΣΔ‖g‖\| **∈ [0.8, 1.2]** **and** arm (c) Σprogress **same sign** as ΣΔ‖g‖ | R1 did its job | Phase 3 H100 from-scratch AC |
| otherwise | R1 incomplete / identity broken | **stop**, STATUS honest FAIL, **no** H100 train |

Arm (a) should also collapse toward 1× (progress becomes geometry). Do **not** require λG0(a) vs λG0(b) here — old π was trained on the lying head.

## Artifacts to start from

```
experiments/aerial/rl/artifacts/v4_ac_ckpt_20260818_c2_fromscratch/v4_ac_latest.pt
experiments/aerial/rl/artifacts/wm_ckpt_r60_rh_20260816/wm_step_1000.pt
dataset: ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/dataset_v0_headon_20260811
yaml: configs/aerial_rl.yaml / configs/aerial_rl_rollout.yaml   # do not edit flags
calib JSON (baseline, do not overwrite): artifacts/v4_rh_progress_calib_c2train_20260818.json
```

125 HEAD may still be `36be2d3`. **First command:** `git pull origin main` (need `ccf901d` + this prompt).

## Work

### Phase 0 — pull + sign (docs only, before code)

1. `git pull origin main`.
2. Fill proposal §5 checkbox 「重开 RH progress 头」: **[x]**, 裁定 = **重开并落地 R1**（`imagine` aux 路径 progress = `analytic_progress(g, a[:3])`；RH `p_coll` / z 不动；**不**重训 `reward_head`；**不**修 yaw）。Date 2026-08-18 + HEAD.
3. Leave 「`advance_goal_rel_body` 漏转 yaw」**unchecked**.
4. Changelog living docs (`YYYY-MM-DD —— 改了什么(为什么/依据)`). **Do not rewrite** old A.2 / A.3 / A.4 numbers — mark superseded. Files: this STATUS, `V4_GATE_STATUS.md` §1+§3, `V4_RH_CALIB_125_STATUS.md` (next=this job), `LIVING_DOCS.md` 2f + §E, `PROJECT_STATUS.md` §2.

Commit + `git push origin main` after the sign **or** after R1 code — either is fine as long as origin has the sign before H100.

### Phase 1 — R1 code + tests

Edit `experiments/aerial/rl/imagination.py` only (plus tests). Import `analytic_progress` from `goal_features`.

**Existing test that MUST be rewritten:** `test_imagine_nonzero_goal_rel_changes_progress_vs_zeros` (`test_imagination_aux.py`) uses `_ZeroPolicy`. After R1, Δ‖g‖ of a=0 is **0** for any goal, so the old assert dies. Replace with:

- `a = [+1,0,0,0]`, `goal_rel0 = [10,0,0,10]` → `progress[0,0] ≈ 1.0`
- `a = [-1,0,0,0]`, same goal → `progress[0,0] ≈ -1.0` (retreat)
- `a = 0` → `progress ≈ 0` regardless of goal

Keep a test that **p_coll** still comes from `dynamics.step` (not overwritten).

On 125: `source env_4090.sh` then the usual torch unit tests + new imagine tests. Record pass counts in STATUS.

### Phase 2 — re-run §A decomp + calib (125 GPU, **no renderer**)

Same C2 actor as calib baseline (`v4_ac_ckpt_20260818_c2_fromscratch`). New JSON names (`*_r1_*`); **do not overwrite** 20260818 baseline.

```bash
cd ~/aerial-wam-v2
source experiments/aerial/scripts/env_4090.sh
mkdir -p artifacts logs

$PYTHON_BIN experiments/aerial/scripts/v4_imagine_return_decomp.py \
  --repo ~/aerial-wam-v2 \
  --dataset ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/dataset_v0_headon_20260811 \
  --actor-ckpt experiments/aerial/rl/artifacts/v4_ac_ckpt_20260818_c2_fromscratch/v4_ac_latest.pt \
  --wm-ckpt experiments/aerial/rl/artifacts/wm_ckpt_r60_rh_20260816/wm_step_1000.pt \
  --out artifacts/v4_imagine_return_decomp_c2train_a23_r1_20260818.json
```

Then `--clip-actions --seed 0` → `..._a4_r1_...`. Then:

```bash
$PYTHON_BIN experiments/aerial/scripts/v4_rh_progress_calib.py \
  --a23 artifacts/v4_imagine_return_decomp_c2train_a23_r1_20260818.json \
  --a4  artifacts/v4_imagine_return_decomp_c2train_a4_r1_20260818.json \
  --out artifacts/v4_rh_progress_calib_c2train_r1_20260818.json
```

Apply the accept table. If FAIL → stop.

### Phase 3 — H100 from-scratch AC (only if Phase 2 PASS)

Bundle from 125 (example; adapt if a known recipe exists on disk):

```bash
git bundle create /tmp/aerial-wam-v2.bundle origin/main
scp /tmp/aerial-wam-v2.bundle h100-25:/tmp/aerial-wam-v2.bundle
ssh h100-25 'cd ~/aerial-wam-v2 && git fetch /tmp/aerial-wam-v2.bundle main:bundle-main && git checkout main && git merge --ff-only bundle-main'
```

On H100 (`source env_h100.sh`):

```bash
python -m experiments.aerial.rl.train_v4_ac \
  --iters 300 --device cuda --imagine-horizon 15 --dynamics torch \
  --wm-ckpt experiments/aerial/rl/artifacts/wm_ckpt_r60_rh_20260816/wm_step_1000.pt \
  --skip-collect --dataset <headon RGB dataset on H100, same as C2 from-scratch> \
  --backend mock \
  --ckpt-dir experiments/aerial/rl/artifacts/v4_ac_ckpt_20260818_c2_analytic_progress
```

**No** `--ckpt` / no load of `v4_ac_ckpt_20260818_c2_fromscratch`. New dir only. Log `policy_class=tanh_bounded_v1`. Stage `v4_ac_latest.pt` back to 125.

Then on 125, **re-run §A** (a23 + a4) against the **new** actor. Record λG0 / Σprogress / ‖goal‖ 30→ / `n_action_clipped` (must stay 0). Do **not** rewrite the old C2 table; new subsection.

### Phase 4 — 125 ① re-gate (renderer)

Renderer `127.0.0.1:41451`. If down, `experiments/aerial/scripts/recover_renderer.sh` then continue. If AirSim dead, record and stop.

Same harness as C2 (`configs/aerial_rl_rollout.yaml`, **do not edit**). Both seeds. `n≥8` requested; if scored n=5 again, **non-authoritative**, still record numbers. **Do not** lower `n`. **Do not** flip yaml even if ① PASS.

Also run `v4_progress_diag.py --imagine-horizon 15` on the **new** actor (both seeds) so first-act cos / imagΣG vs real are on the same page. Do **not** sign In-table from this (harness 洞 4 still holds).

### Docs + push

Changelog style. Files: this STATUS (verdict + numbers), `V4_GATE_STATUS.md` §1+§3, `V4_SIGNAL1_SA_DIAG_STATUS.md` new subsection, `LIVING_DOCS.md`, `PROJECT_STATUS.md`. Commit + `git push origin main`.

If renderer/H100/scan fails: document and stop honestly.
