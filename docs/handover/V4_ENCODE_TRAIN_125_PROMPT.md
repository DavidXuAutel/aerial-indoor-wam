# V4 encode + longer train — run on 125 (offline / Mac sleep-safe)

Design: `docs/superpowers/specs/2026-08-16-v4-mvp-design.md`.  
Prior FAIL: `docs/handover/V4_M5_125_STATUS.md` — ① actor −13.54 vs heur 9.71; root cause stub `encode(proprio4)` on both H100 mock train and M5 deploy.

You are ON **125** (`/home/yao/aerial-wam-v2`). Renderer: `127.0.0.1:41451`. H100: `ssh h100-25`. Python on 125: `source experiments/aerial/scripts/env_4090.sh`.

## Hard rules
- **Do NOT** flip `enable_policy_update` in `configs/aerial_rl.yaml` (must stay `false`).
- **Do NOT** push GitHub; only `git push origin main` (bare on 125 / `cursor-125`).
- Never modify Franka/robot network; never use `10.229.66.70` for robot.
- Honest FAIL is OK — record numbers; no threshold gaming.
- Keep DepthTauShield / safety on for full-system arms; progress gate ① may stay shield-off as designed.
- Prefer existing patterns: `dynamics_torch.TorchRSSMDynamics`, `train_v4_ac`, `v4_gate_run_partials.py`, `v1_gate_run_partials` style.
- Update living STATUS continuously: `docs/handover/V4_ENCODE_TRAIN_125_STATUS.md`.

## Root cause (must fix)
- `train_v4_ac.py` with `--backend mock` forces `dynamics.kind=stub` → actor trained on stub latent dim 8.
- `v4_gate_run_partials.py` hardcodes `StubLatentDynamics` for `LatentActorDeployPolicy`.
- Real WM: `TorchRSSMDynamics.encode(obs)` → packed RSSM `[h‖z]` (latent_dim ≈ 512+32×32=1536). Train and deploy **must** share this encode path and latent width.

## A) Real WM encode path (train + deploy aligned)

1. **Train path** — extend `train_v4_ac` (or equivalent CLI) so imagination AC uses **torch WM**, not stub:
   - Do **not** leave the mock→stub shortcut as the only path for serious train.
   - Add flags as needed (e.g. `--dynamics torch`, `--wm-ckpt`, keep `--backend mock` for env if needed but **dynamics.kind=torch**).
   - Load existing WM weights. Prefer project standard on H100:
     - Primary: `/home/a25689/aerial-rl-skeleton/experiments/aerial/rl/artifacts/wm_ckpt_r60_20260814/wm_step_5000.pt`
     - YAML default dir: `wm_ckpt_v1a_20260815` (also under aerial-rl-skeleton on H100).
     - If missing under `~/aerial-wam-v2`, symlink/copy from aerial-rl-skeleton or document the absolute path used.
   - Actor `latent_dim` must match `TorchRSSMDynamics.latent_dim` (via `build_from_config` / dynamics).
   - Freeze WM during AC train (`enable_wm_update=false` in-memory OK); only train actor/critic.
   - Cheap smoke: unit/integration test that deploy encode ≠ stub proprio4 when kind=torch (extend existing tests if cheap).

2. **Deploy/eval path** — fix `v4_gate_run_partials.py` / `LatentActorDeployPolicy`:
   - Build `TorchRSSMDynamics` from config + load WM ckpt (same as train).
   - **Remove** hardcode `StubLatentDynamics` for the V4 actor arm.
   - Heuristic arm unchanged; shield/depth/τ paths keep existing DepthTauShield behavior.

3. Commit encode-path fixes; `git push origin main`. Sync code to H100 (bundle/rsync/`git` as usual).

## B) Longer H100 imagination AC train

After encode path works:

```bash
ssh h100-25
cd ~/aerial-wam-v2   # or synced tree
source experiments/aerial/scripts/env_h100.sh   # if present
export PYTHONPATH=$PWD
# Example — choose a sensible longer budget (NOT 10-iter mock):
# e.g. --iters 200–500 OR wall-clock ~1–3h; document actual choice.
python -m experiments.aerial.rl.train_v4_ac \
  --iters <N> --device cuda --imagine-horizon 15 \
  --ckpt-dir experiments/aerial/rl/artifacts/v4_ac_ckpt_20260816_wm \
  <torch-wm flags you added> \
  2>&1 | tee artifacts/v4_ac_train_h100_wm.log
```

- New ckpt dir: **`v4_ac_ckpt_YYYYMMDD_wm/`** (today → `v4_ac_ckpt_20260816_wm/`).
- Record in `docs/handover/V4_H100_TRAIN_STATUS.md`: iters, lr (from yaml/v4), backend/dynamics kind, wm ckpt path, actor ckpt path, mean losses, HEAD.
- Also update `docs/handover/V4_ENCODE_TRAIN_125_STATUS.md`.

## C) Re-run M5-style gate on 125

After new ckpt exists on H100, stage to 125 (scp via `h100-25`), then:

```bash
cd ~/aerial-wam-v2
source experiments/aerial/scripts/env_4090.sh
mkdir -p logs experiments/aerial/rl/artifacts/v4_gate_r60_20260816_wm

$PYTHON_BIN experiments/aerial/scripts/v4_gate_run_partials.py rollout4090 \
  --repo ~/aerial-wam-v2 \
  --rollout-dataset ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/dataset_v0_headon_20260811 \
  --actor-ckpt experiments/aerial/rl/artifacts/v4_ac_ckpt_20260816_wm/v4_ac_latest.pt \
  --depth-ckpt experiments/aerial/rl/artifacts/depth_ckpt_da3_r60_20260814/depth_step_2000_da3_ft_head.pt \
  --tau-ckpt experiments/aerial/rl/artifacts/tau_ckpt_foe_r60_20260815/tau_foe_calibrator.pt \
  --env-host 127.0.0.1 --device cuda \
  --out-dir experiments/aerial/rl/artifacts/v4_gate_r60_20260816_wm \
  2>&1 | tee logs/v4_encode_gate_rollout.log

$PYTHON_BIN experiments/aerial/scripts/v4_gate_run_partials.py merge \
  --repo ~/aerial-wam-v2 \
  --out-dir experiments/aerial/rl/artifacts/v4_gate_r60_20260816_wm
```

(Pass WM ckpt flags if you added them to the partials CLI.)

- Update `docs/handover/V4_GATE_STATUS.md` with new ①/④ numbers and merge ok?.
- Finalize `docs/handover/V4_ENCODE_TRAIN_125_STATUS.md` (HEAD, cmds, numbers, yaml still false, sleep-safe).
- Commit + `git push origin main`.

## Pitfalls (from M5)
- Use `env_4090.sh` / sim_verify venv — bare python lacks airsim.
- Prefer **headon** corpus if r60 scan fails on this host.
- Depth/τ ckpts may live under aerial-rl-skeleton — stage or symlink as M5 did.
- Kill duplicate hung `agent --print` for this task only if you are sure they are stale duplicates of **this** encode-train job; do not kill unrelated work.

## Done when
1. Train+deploy use torch WM encode (documented + verified).
2. Longer H100 train finished; ckpt under `v4_ac_ckpt_*_wm/`.
3. Gate ①/④ re-run; artifacts + STATUS + V4_GATE_STATUS updated; origin pushed.
4. `enable_policy_update` still **false**.

Start by reading `train_v4_ac.py`, `train_rl.py` `_build_dynamics`, `dynamics_torch.py` `encode`, `v4_gate_run_partials.py`, `actor_critic.py` `LatentActorDeployPolicy`, then implement A→B→C.
