# V4 H100 train STATUS (encode + longer + reward-head)

- **date**: 2026-08-16
- **125→H100 key**: `~/.ssh/id_ed25519_h100` / SSH Host `h100-25` → `a25689@10.239.121.25:31126` ✅
- **H100 code sync**: scp (origin-only push; H100 github pull not used)

## Encode-train (superseded by RH track for deploy)

| Field | Value |
|---|---|
| wm ckpt | `wm_ckpt_r60_20260814/wm_step_5000.pt` (legacy RH skipped) |
| actor ckpt | `v4_ac_ckpt_20260816_wm/v4_ac_latest.pt` |
| mean_actor_loss | **−0.0005** |
| gate ①/④ | FAIL / FAIL (see `V4_ENCODE_TRAIN_125_STATUS.md`) |

## Reward-head finetune (Phase 1A)

```bash
python -m experiments.aerial.rl.train_reward_head \
  --dataset /home/a25689/aerial-rl-skeleton/.../dataset_v0_local_depth_r60_20260814 \
  --wm-ckpt /home/a25689/aerial-rl-skeleton/.../wm_ckpt_r60_20260814/wm_step_5000.pt \
  --steps 1000 --device cuda \
  --checkpoint-dir experiments/aerial/rl/artifacts/wm_ckpt_r60_rh_20260816
```

- **result**: PASS — loss_reward 1.86→0.70; `load_skipped` reward **[]**
- **ckpt**: `~/aerial-wam-v2/experiments/aerial/rl/artifacts/wm_ckpt_r60_rh_20260816/wm_step_1000.pt`
- **log**: `~/aerial-wam-v2/artifacts/v4_rh_finetune_h100.log`

## AC retrain with RH WM (Phase 2) ✅

```bash
python -m experiments.aerial.rl.train_v4_ac \
  --iters 300 --device cuda --imagine-horizon 15 --dynamics torch \
  --wm-ckpt experiments/aerial/rl/artifacts/wm_ckpt_r60_rh_20260816/wm_step_1000.pt \
  --ckpt-dir experiments/aerial/rl/artifacts/v4_ac_ckpt_20260816_wm_rh
```

| Field | Value |
|---|---|
| mean_actor_loss | **−0.0087** |
| latent_dim | **1536** |
| actor ckpt | `v4_ac_ckpt_20260816_wm_rh/v4_ac_latest.pt` |
| log | `artifacts/v4_ac_train_h100_wm_rh.log` |

## Gate (Phase 3 on 125)

- merge **FAIL** (① −3.17 vs heur 7.44; ④ PASS) — see `V4_REWARD_HEAD_125_STATUS.md`
- **enable_policy_update**: still **false** (yaml unchanged)

## Follow-on — goal + z0 (2026-08-17) ✅

- Track: `docs/handover/V4_GOAL_Z0_125_STATUS.md`
- H100 AC: `v4_ac_ckpt_20260817_wm_rh_goal_rgb/` (300 iters, headon RGB z0, frozen RH WM)
- Gate: merge **FAIL** (① −8.74 vs heur 8.42; ④ PASS 0.000 vs v1 0.429)
- Train metrics: mean|goal_rel|=3.05, mean_return=92.35 (imagined; does not transfer to deploy)
- Phase 4 deferred: longer train / RH fidelity / vel=0 / actor concat goal_rel

## Verification

```bash
ssh h100-25 'ls -la ~/aerial-wam-v2/experiments/aerial/rl/artifacts/wm_ckpt_r60_rh_20260816/wm_step_1000.pt'
ssh h100-25 'tail -5 ~/aerial-wam-v2/artifacts/v4_ac_train_h100_wm_rh.log'
```
