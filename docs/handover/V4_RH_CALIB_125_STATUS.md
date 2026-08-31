# C2 RH progress calibration (125, offline, 2026-08-18)

- **status**: **DONE**
- **script**: `experiments/aerial/scripts/v4_rh_progress_calib.py`
- **inputs**: `artifacts/v4_imagine_return_decomp_c2train_a23_20260818.json` + `..._a4_...` (no renderer)
- **out**: `artifacts/v4_rh_progress_calib_c2train_20260818.json`
- **identity**: `analytic_t = goal_dist[t] − goal_dist[t+1]` ≡ batch-mean `analytic_progress(g_t, a_t[:3])` under `advance_goal_rel_body`

## Verdict

**`sign_reopen_rh_progress_head`** — curve is **not** 1:1. Pre-committed: forward |ΣRH/ΣΔ‖g‖| ≥ 2 **or** retreat RH>0 while analytic<0.

| arm | Σ RH | Σ Δ‖g‖ | ratio | MAE | trigger |
|---|---|---|---|---|---|
| (a) π | +81.64 | +12.26 | **6.66** | 4.68 | ratio≥2 |
| (b) max forward | +62.60 | +14.99 | **4.18** | 3.35 | ratio≥2 |
| (c) max retreat | +9.28 | −15.00 | −0.62 | 1.62 | **wrong sign** |
| (b3) fwd scaled | +50.72 | +11.22 | 4.52 | 2.69 | ratio≥2 |
| (c3) ret scaled | +9.59 | −11.22 | −0.85 | 1.39 | wrong sign |

a4 (`clip_actions=true`) matches a/b/c bit-for-bit (C2 clip is no-op).

**Shape**: t0–t4 near-calibrated (π t0: RH 0.62 vs analytic 0.56). From **t≈6** RH reports 6–9 m/step while geometry stays ~0.8–1.0. Retreat RH stays +0.44…+0.98 against analytic −1.0 every step.

Arm (b) has yaw ≡ 0, so the 4.18× is **not** `advance_goal_rel_body` missing yaw rotation.

This is RH vs **stub kinematics**, not vs real-world ①. Imagined ΣG ~85 ≈ RH sum; of that, ~12 m is true kinematic close and ~70 m is head inflation. Real ① ≈ −5 is a leftover world gap — **not** the next job until RH is honest.

**Do not** implement the head in this job. yaml / `enable_policy_update` untouched.

**Next job**: [`V4_RH_REOPEN_125_STATUS.md`](V4_RH_REOPEN_125_STATUS.md) — R1 analytic Δ‖g‖ in `imagine` aux path (signed 2026-08-18 HEAD `7883b89`).
