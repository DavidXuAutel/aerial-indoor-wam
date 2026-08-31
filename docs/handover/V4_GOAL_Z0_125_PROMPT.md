# V4 goal + z0 alignment — run on 125 (offline / Mac sleep-safe)

Prior track (done, merge FAIL on ①): `docs/handover/V4_REWARD_HEAD_125_STATUS.md`.  
Living status (update continuously): `docs/handover/V4_GOAL_Z0_125_STATUS.md`.  
Access: `docs/handover/ACCESS.md` — on-campus use **`cursor-125`** / `origin` direct LAN (NOT `cursor-125-public`).

You are ON **125** (`/home/yao/aerial-wam-v2`). Renderer: `127.0.0.1:41451`. H100: `ssh h100-25`. Python on 125: `source experiments/aerial/scripts/env_4090.sh`.

## Hard rules
- **Do NOT** flip `enable_policy_update` in `configs/aerial_rl.yaml` (must stay `false`).
- **Do NOT** push GitHub; only `git push origin main` (bare on 125 / `cursor-125`).
- Never modify Franka/robot network; never use `10.229.66.70` for robot.
- Honest FAIL is OK — record numbers; no threshold gaming.
- Prefer existing patterns: `train_v4_ac.py`, `collect_dataset._mock_goal_episode` / `--approach-bias`, `dynamics_torch.py`, `imagination.py`, `v4_gate_run_partials.py`, `wm_data.py`.
- Update living docs throughout: this STATUS + `V4_GATE_STATUS.md` + `V4_H100_TRAIN_STATUS.md` + brief note in `V4_REWARD_HEAD_125_STATUS.md`.

## Root cause (cite — do not rediscover from scratch)

Reward-head + imagine-aux fixed garbage progress (−68.88 → −3.17), but **V4-① still FAIL** (actor −3.17 vs heur 7.44; ④ PASS).

Two remaining train/deploy gaps (analysis 089e4166 / 583ccf12):

1. **Goal-less mock AC train** — `train_v4_ac --backend mock` builds corrector with `annotation: null` → no episodes → mock env has **no goal** → `goal_rel≈0` → imagined `progress≈0` / tiny `mean_return` even with fixed RH WM. Contrast: `collect_dataset` injects `_mock_goal_episode()` for mock dry-run; AC path does **not**.

2. **z0 domain gap** — AC imagination starts from mock / non-RGB latents; gate ①/④ encode **real** AirSim RGB via torch WM. Prefer offline encode from r60/headon real RGB windows **with goals**, or short 4090 collect → H100 imagine AC. Do **not** treat goal-less mock as the serious train path.

RH WM to keep frozen: `wm_ckpt_r60_rh_20260816/wm_step_1000.pt` (load_skipped reward **[]**).

---

## Experiment order (follow strictly)

### Phase 0 — Diagnose (quick)

In `train_v4_ac` (or a tiny probe / few iters), log:
- `mean|goal_rel|` (L1 or L2 over batch / horizon starts)
- mean imagined **progress**
- `mean_return` (from actor_critic train stats)

**Expect** under current mock + annotation null: `goal_rel≈0`, progress≈0. Record numbers in STATUS before changing code.

### Phase 1 — Minimal fix + H100 retrain

1. Inject goals into `train_v4_ac` / corrector build path, aligned with:
   - `collect_dataset._mock_goal_episode` (start→goal), and/or
   - real `--annotation` JSON, and/or
   - `approach-bias` rewrite (start + dist along yaw)
2. Keep `--dynamics torch` + frozen RH WM ckpt above.
3. H100 AC retrain; new ckpt dir e.g.:
   - `experiments/aerial/rl/artifacts/v4_ac_ckpt_20260817_wm_rh_goal/`
   - or `*_wm_rh_goal`
4. Log diagnose metrics again post-fix (goal_rel should be nonzero; progress/return should move).
5. Commit + `git push origin main`. Sync code + actor ckpt to H100/125 as needed.

### Phase 2 — Align z0 with real RGB (priority over blind longer train)

Prefer **one** of:
- **A)** Offline: sample z0 by encoding r60 / headon real RGB windows that include goals (`wm_data` / dataset windows), then imagination AC on H100.
- **B)** Short 4090 collect buffer (renderer `:41451`) with annotation/goals → stage to H100 → imagine AC.

Do **not** spend the main budget on goal-less mock longer train.

New ckpt dir should make the z0 source obvious in STATUS (e.g. `*_wm_rh_goal_rgb` / note dataset path).

### Phase 3 — Re-gate ①/④ on 125

Stage new actor (+ same RH WM) to 125, then:

```bash
cd ~/aerial-wam-v2
source experiments/aerial/scripts/env_4090.sh
mkdir -p logs experiments/aerial/rl/artifacts/v4_gate_r60_20260817_wm_rh_goal

$PYTHON_BIN experiments/aerial/scripts/v4_gate_run_partials.py rollout4090 \
  --repo ~/aerial-wam-v2 \
  --rollout-dataset ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/dataset_v0_headon_20260811 \
  --actor-ckpt experiments/aerial/rl/artifacts/<NEW_GOAL_AC_CKPT>/v4_ac_latest.pt \
  --wm-ckpt experiments/aerial/rl/artifacts/wm_ckpt_r60_rh_20260816/wm_step_1000.pt \
  --dynamics-kind torch \
  --depth-ckpt experiments/aerial/rl/artifacts/depth_ckpt_da3_r60_20260814/depth_step_2000_da3_ft_head.pt \
  --tau-ckpt experiments/aerial/rl/artifacts/tau_ckpt_foe_r60_20260815/tau_foe_calibrator.pt \
  --env-host 127.0.0.1 --device cuda \
  --out-dir experiments/aerial/rl/artifacts/v4_gate_r60_20260817_wm_rh_goal \
  2>&1 | tee logs/v4_goal_z0_gate_rollout.log

$PYTHON_BIN experiments/aerial/scripts/v4_gate_run_partials.py merge \
  --repo ~/aerial-wam-v2 \
  --out-dir experiments/aerial/rl/artifacts/v4_gate_r60_20260817_wm_rh_goal
```

- Honest FAIL/PASS in `V4_GATE_STATUS.md` + this STATUS.
- Commit + `git push origin main`.

### Phase 4 — Only if still short after 2–3

In order of last resort (do not jump here early):
- longer train
- RH fidelity checks
- deploy vel=0 fix
- actor concat `goal_rel`

---

## Pitfalls
- In-memory `enable_policy_update=True` inside `train_v4_ac` is OK for the train script; **yaml file must stay false**.
- Use `env_4090.sh` on 125 / `env_h100.sh` on H100.
- Kill only stale duplicates of **this** goal/z0 job or hung prior V4 `agent --print`; do not kill vscode/cursor UI or unrelated services.
- Prefer headon corpus if r60 scan fails on this host.

## Done when
1. Phase 0 numbers recorded (baseline goal_rel/progress/return).
2. Goals injected (or real annotation); H100 AC ckpt under `*_wm_rh_goal*` (and preferably RGB-aligned z0).
3. Gate ①/④ re-run; artifacts + STATUS updated; origin pushed.
4. `enable_policy_update` still **false**.

Start by reading `train_v4_ac.py`, `collect_dataset.py` (`_mock_goal_episode`), `corrector.py` (`_update_policy` / goal_rel), `imagination.py`, `wm_data.py`, prior `V4_REWARD_HEAD_125_STATUS.md`, then Phase 0→1→2→3.
