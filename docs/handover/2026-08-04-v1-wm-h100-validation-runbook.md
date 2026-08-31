# V1 World-Model H100 Validation Runbook

**Date:** 2026-08-04 (rev 2026-08-15 — r60 assets) · **Branch:** `main` @ `5b301ea+`

Goal: validate the torch DreamerV3 RSSM world model
([`dynamics_torch.py`](../../experiments/aerial/rl/dynamics_torch.py)) on the H100
against **r60 authoritative corpus**, then — only if it passes — flip the `enable_wm_update` gate.
Everything below runs **on the 8×H100 box** (torch `2.7.1+cu128`); none of it runs
on the GPU-less dev host, where the torch tests skip by design.

> **Note:** This runbook covers **V1a** (WM live loop floor). Full **V1b** (τ + imagination + dual-channel shield) is defined in [V1/V4 design](../design/2026-08-15-v1-v4-design.md).

## 0. Preconditions

- Host: H100 `.25` — `a25689@10.239.121.25:31126`
- **Data (authoritative)**: `dataset_v0_local_depth_r60_20260814` — 51 npz / 48 usable,
  `step_hz=5.0`, `grab_depth=true`, at
  `~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/dataset_v0_local_depth_r60_20260814`
- **WM warm-start (optional)**: `wm_ckpt_r60_20260814/wm_step_5000.pt` (V0 authoritative)
- Repo synced to latest `main`; `export PYTHONPATH="$PWD"` from repo root.
- V0 flags already ON: `depth_head.enable`, `safety.kind=threshold`

## 1. Unit tests (primitives + smoke) — must be green first

```bash
python -m pytest experiments/aerial/rl/tests/test_dynamics_torch.py -q
```

**PASS:** all tests pass (they no longer skip once torch is present). These pin the
torch primitives (symlog / two-hot / categorical-KL) to the `dreamer_recipe` numpy
reference and smoke build→loss→backward→update→encode/step→checkpoint.
**If red:** stop — a primitive diverging from the numpy reference is a §1.5
violation; fix before training.

## 2. Real training + non-divergence validation (the V1 gate)

```bash
python -m experiments.aerial.rl._wm_train_validate \
  --dataset ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/dataset_v0_local_depth_r60_20260814 \
  --config configs/aerial_rl.yaml \
  --steps 500 --wm-batch 8 --window 8 --horizon 15 \
  --checkpoint-dir experiments/aerial/rl/artifacts/wm_ckpt_r60_v1a_<date>
```

This trains the real WM and checks the two design-doc criteria. **PASS requires
both** (script exits 0 and prints `PASS`):

| Criterion | Check | Pass condition |
|---|---|---|
| **A. Learning** | total `update()` loss trend | last-10% mean < first-10% mean × 0.98 (≥2% drop), all finite |
| **A. Recon** | `recon_err` trend | recon not worse at the end than the start |
| **A. No collapse (§2.3)** | min `post_entropy_frac` over training | ≥ `collapse_entropy_frac` (0.10); no collapse-watch warnings |
| **B. Non-divergence (§9)** | open-loop H=15 rollout from real starts | latents finite, `p_coll∈[0,1]`, packed-latent norm not exploding (< 50× start) |

**Tuning notes (NOT the paper's, per §1.5):** 500 steps is a first look; if loss is
still visibly dropping at the end, raise `--steps` (H100 is fast). Do NOT import
DreamerV3's T=16 / reward-threshold 50.0 — this is the 4-D kinematic SEARCH regime.
`--horizon` stays ≤ `MAX_IMAGINATION_HORIZON` (15); the script rejects more.

**If A fails:** likely lr / capacity / window length — tune the `world_model:` block
in [`configs/aerial_rl.yaml`](../../configs/aerial_rl.yaml), not the recipe math.
**If B fails (divergence):** the multi-step gate is not met — keep the gate OFF,
shorten the effective horizon, and investigate before any imagination-RL work.

## 3. Longer training + checkpoint (once §2 passes)

Re-run §2 with `--steps 5000` (or until the loss plateaus) to get a checkpoint-worthy
model. The trainer writes to `world_model.checkpoint_dir`
(`experiments/aerial/rl/artifacts/wm_ckpt`); `save_checkpoint(path, step=)` stores
`{model, optimizer, step, torch_dtype}`. Keep the run log — the loss/recon/entropy
trace is the evidence the V1 gate was met.

## 4. Flip the gate + corrector smoke (only after §2–§3 pass)

Editing [`configs/aerial_rl.yaml`](../../configs/aerial_rl.yaml):

```yaml
dynamics:
  kind: torch          # was: stub
corrector:
  enable_wm_update: true   # GATE V1 — flip ON only now
```

Then run a few corrector iterations against the mock env (or airsim if the renderer
is up) to confirm the gate wiring end-to-end:

```bash
python -m experiments.aerial.rl.train_rl \
  dynamics.kind=torch corrector.enable_wm_update=true corrector.iterations=3
```

**PASS:** each iteration logs `wm=updated` (NOT `skipped`/`noop`) — i.e.
`_update_world_model` saw a real training step with no `skipped` key. `w_man=` in the
log stays at its start value unless a curriculum is configured (default is a no-op).

**Do NOT** enable `enable_policy_update` (V4) here — imagination actor-critic,
online `h`-threading, and goal-conditioned imagined progress are the next milestone.

## Rollback

Revert the two YAML edits (`kind: stub`, `enable_wm_update: false`) — the stub V0
loop is torch-free and always runnable. No code rollback needed; `kind='torch'` is
purely opt-in and lazily imported.
