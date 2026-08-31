# V4 reward-head fix — run on 125 (offline / Mac sleep-safe)

Design: `docs/superpowers/specs/2026-08-16-v4-mvp-design.md`.  
Prior encode-train FAIL: `docs/handover/V4_ENCODE_TRAIN_125_STATUS.md`.  
Living status (update continuously): `docs/handover/V4_REWARD_HEAD_125_STATUS.md`.

You are ON **125** (`/home/yao/aerial-wam-v2`). Renderer: `127.0.0.1:41451`. H100: `ssh h100-25`. Python on 125: `source experiments/aerial/scripts/env_4090.sh`.

## Hard rules
- **Do NOT** flip `enable_policy_update` in `configs/aerial_rl.yaml` (must stay `false`).
- **Do NOT** push GitHub; only `git push origin main` (bare on 125 / `cursor-125`).
- Never modify Franka/robot network; never use `10.229.66.70` for robot.
- Honest FAIL is OK — record numbers; no threshold gaming.
- Prefer existing patterns: `dynamics_torch.py`, `imagination.py`, `train_v4_ac.py`, `v4_gate_run_partials.py`, depth-head `--freeze-encoder` freeze idiom.
- Update living docs throughout: this STATUS + `V4_GATE_STATUS.md` + `V4_H100_TRAIN_STATUS.md` + brief note in `V4_ENCODE_TRAIN_125_STATUS.md`.

## Root cause (cite — do not rediscover from scratch)

Encode path is fixed (latent_dim=1536), but V4 gate **regressed**:

| Signal | M5 stub | Encode-train torch WM |
|---|---|---|
| **①** | actor −13.54 vs heur 9.71 ❌ | actor **−68.88** vs heur **10.66** ❌ |
| **④** | v4_hard 0.00 ✅ | v4_hard **0.143** vs v1 **0.00** ❌ |

Two compounding bugs:

1. **`reward_head` load skip** — `wm_ckpt_r60_20260814/wm_step_5000.pt` has legacy `reward_head.0.weight` shape **(256, 1536)**; live model expects **(256, 76)** (`reward_feat_proj` 64 + action 4 + `reward_aux` 8). `_filter_compatible_state_dict` skips the mismatch → **random** `reward_feat_proj` + `reward_head` while encoder/RSSM load correctly → imagination `progress` is noise → AC trains on garbage reward.

2. **`imagine()` / torch `step` missing aux** — `imagination.imagine()` calls `dynamics.step(z, a)` with **no** `goal_rel` / `body_vel`. Torch path zeros aux → even a correctly trained aux-conditioned head sees zeros at train time. Need pass-through (or `set_goal` equivalent) so the new head gets aux features during imagination.

## Recommended fix path (pick this — most correct vs repo)

**Do NOT** temporary-match old architecture just to load (256,1536) weights (abandons V1-② aux design).  
**Do NOT** invent a shape-mismatched weight adapter as the primary fix (1536→76 is not a meaningful transplant).

**DO**: keep current aux-conditioned architecture; **finetune `reward_feat_proj` + `reward_head` on r60** with **encoder / RSSM / decoder / continue / coll frozen**; save a new WM ckpt (or overlay) where `load_skipped` for reward_head is empty. Mirror freeze patterns from `train_depth_head.py` (`--freeze-encoder`).

Then wire imagination aux, retrain AC, re-gate.

---

## Phase 1 — Reward head adapt/align (highest priority)

### 1A) Finetune reward head (frozen backbone)

1. Inspect `wm_step_5000.pt` load on current `TorchRSSMDynamics`: log `load_skipped` / `load_missing` (expect reward_head + reward_feat_proj skipped/missing today).
2. Add a small train entrypoint **or** extend existing WM train CLI so you can:
   - Load r60 WM ckpt with shape-filter (encoder/RSSM OK).
   - Freeze everything except `reward_feat_proj` + `reward_head` (and optimizer over those params only).
   - Train on r60 (or headon if r60 scan fails on host) windows that include `goal_rel` / `body_vel` / `reward` (see `wm_data.py`).
   - Prefer H100 (`ssh h100-25`) for the finetune if 125 GPU is busy with renderer; stage dataset/ckpt as encode-train did.
3. Save new dated ckpt, e.g.:
   - `experiments/aerial/rl/artifacts/wm_ckpt_r60_rh_20260816/wm_step_<N>.pt`
   - Document absolute path on H100 vs staged path on 125.
4. **Assert**: after load of the **new** ckpt, `load_skipped` for `reward_head*` / `reward_feat_proj*` is **empty** (or only keys you explicitly document as expected). Log the full `load_skipped` list in STATUS.
5. Cheap tests: extend `test_dynamics_torch.py` / imagination tests — load path + `load_skipped` empty for matching shapes; imagine passes aux (see 1B).

### 1B) Imagination aux wiring (required)

1. Extend `imagine()` (and call sites in `actor_critic` / `train_v4_ac` / corrector) so torch `step` receives `goal_rel` / `body_vel`, **or** add `TorchRSSMDynamics.set_goal` (+ body_vel cache) used when step kwargs omitted — pick the approach that matches `StubLatentDynamics.set_goal` / existing tests (`test_followups.py` already mentions corrector sets goal before imagine).
2. For AC imagination from encoded starts: derive goal_rel/body_vel from the start obs / trajectory windows used to sample `z0` (same features as WM train). Do **not** leave permanent zeros.
3. Unit/smoke where cheap: imagine with nonzero goal_rel changes progress vs zeros (reuse `test_reward_head_is_action_goal_and_vel_conditioned` spirit).

Commit Phase 1; `git push origin main`. Sync code + new WM ckpt to H100.

---

## Phase 2 — Retrain AC on H100 (frozen fixed WM)

```bash
ssh h100-25
cd ~/aerial-wam-v2
source experiments/aerial/scripts/env_h100.sh   # if present
export PYTHONPATH=$PWD
python -m experiments.aerial.rl.train_v4_ac \
  --iters 300 --device cuda --imagine-horizon 15 \
  --dynamics torch \
  --wm-ckpt <NEW_RH_FINETUNED_WM_CKPT> \
  --ckpt-dir experiments/aerial/rl/artifacts/v4_ac_ckpt_20260816_wm_rh \
  2>&1 | tee artifacts/v4_ac_train_h100_wm_rh.log
```

- New dated dir: **`v4_ac_ckpt_YYYYMMDD_wm_rh/`** (today → `v4_ac_ckpt_20260816_wm_rh/` if still 2026-08-16; else use actual date).
- Record in `docs/handover/V4_H100_TRAIN_STATUS.md`: iters, wm ckpt path (rh-finetuned), actor ckpt, mean losses, HEAD, latent_dim.
- Freeze WM during AC (`enable_wm_update=false` in-memory OK).

---

## Phase 3 — Re-run V4 gate ①/④ on 125

Stage new WM + AC ckpts to 125 (scp via `h100-25`), then:

```bash
cd ~/aerial-wam-v2
source experiments/aerial/scripts/env_4090.sh
mkdir -p logs experiments/aerial/rl/artifacts/v4_gate_r60_20260816_wm_rh

$PYTHON_BIN experiments/aerial/scripts/v4_gate_run_partials.py rollout4090 \
  --repo ~/aerial-wam-v2 \
  --rollout-dataset ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/dataset_v0_headon_20260811 \
  --actor-ckpt experiments/aerial/rl/artifacts/v4_ac_ckpt_20260816_wm_rh/v4_ac_latest.pt \
  --wm-ckpt experiments/aerial/rl/artifacts/wm_ckpt_r60_rh_20260816/wm_step_<N>.pt \
  --dynamics-kind torch \
  --depth-ckpt experiments/aerial/rl/artifacts/depth_ckpt_da3_r60_20260814/depth_step_2000_da3_ft_head.pt \
  --tau-ckpt experiments/aerial/rl/artifacts/tau_ckpt_foe_r60_20260815/tau_foe_calibrator.pt \
  --env-host 127.0.0.1 --device cuda \
  --out-dir experiments/aerial/rl/artifacts/v4_gate_r60_20260816_wm_rh \
  2>&1 | tee logs/v4_reward_head_gate_rollout.log

$PYTHON_BIN experiments/aerial/scripts/v4_gate_run_partials.py merge \
  --repo ~/aerial-wam-v2 \
  --out-dir experiments/aerial/rl/artifacts/v4_gate_r60_20260816_wm_rh
```

- Update `docs/handover/V4_GATE_STATUS.md` with honest ①/④ + merge.
- Finalize `V4_REWARD_HEAD_125_STATUS.md` (HEAD, cmds, numbers, yaml still false, sleep-safe).
- Commit + `git push origin main`.

---

## Pitfalls
- Use `env_4090.sh` / sim_verify venv on 125 — bare python lacks airsim.
- Prefer **headon** corpus if r60 scan fails on this host.
- Kill only stale duplicates of **this** reward-head job / prior encode-train agent; do not kill unrelated work.
- Do not warm-start from invalidated pre-r60 single-pillar shortcuts; r60 + rh-finetune only.

## Done when
1. New WM ckpt loads with empty (or documented-empty) reward_head `load_skipped`; imagination passes aux.
2. H100 AC retrain finished under `v4_ac_ckpt_*_wm_rh/`.
3. Gate ①/④ re-run; artifacts + STATUS docs updated; origin pushed.
4. `enable_policy_update` still **false**.

Start by reading `dynamics_torch.py` (`_reward_logits`, `load_checkpoint`, `_filter_compatible_state_dict`), `imagination.py`, `train_v4_ac.py`, `wm_data.py`, `train_depth_head.py` freeze pattern, then implement Phase 1→2→3.
