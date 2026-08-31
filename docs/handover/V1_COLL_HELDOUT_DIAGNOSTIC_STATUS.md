# V1-②-coll held-out diagnostic STATUS (H100)

> **独立诊断** — does **not** rewrite 2026-08-15 V1 merge (`coll_ok=null` on merge JSON stays).  
> Cleaner WM-unseen held-out than r60 tail (which had unique held-out coll ep=2).

- **status**: **CLAIMED** (`coll_claimed=true`, `coll_ok=true`)
- **date**: 2026-08-17
- **host**: `h100-25` (via `cursor-125`)
- **code**: worktree `~/aerial-wam-v2-coll-eval` @ `0f94856` (includes `0541c74` hole-close); venv from `~/aerial-wam-v2/.venv`

## Dataset / ckpt

| 项 | 值 |
|---|---|
| dataset | `~/aerial-rl-skeleton/.../artifacts/dataset_v1_coll_heldout_20260817` |
| size / eps | 950M; 69 npz; usable **65**; quarantine 4 |
| raw / usable collision eps | **12** / **8** |
| ckpt | `wm_ckpt_v1_heldout_goalvel_20260815/wm_step_5000.pt` (same as prior r60 diagnostic) |

## Eval choice: `--heldout-frac 1.0`

This dataset is **entirely** WM-unseen (never in goalvel train split). Using `--heldout-frac 0.25` would incorrectly treat 75% as “train-seen” and shrink the collision window pool. `_wm_fidelity_eval._heldout_split` with `frac=1.0` → `k=ceil(1.0*N)=N` → **all 65 usable episodes** evaluated as held-out. Logged: `held-out split: 65/65 episodes (tail)`.

## Command

```bash
cd ~/aerial-wam-v2-coll-eval
source ~/aerial-wam-v2/experiments/aerial/scripts/env_h100.sh
export PYTHONPATH=$PWD
DS=~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/dataset_v1_coll_heldout_20260817
CKPT=~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/wm_ckpt_v1_heldout_goalvel_20260815/wm_step_5000.pt
nohup "$AERIAL_PY" -m experiments.aerial.rl._wm_fidelity_eval \
  --dataset "$DS" --ckpt "$CKPT" --config configs/aerial_rl.yaml \
  --heldout-frac 1.0 --horizon 15 --n-starts 4 --device cuda \
  > ~/aerial-wam-v2/artifacts/v1_coll_heldout_fidelity_20260817.log 2>&1 &
```

- **PID**: `34877` (finished)
- **log**: `~/aerial-wam-v2/artifacts/v1_coll_heldout_fidelity_20260817.log`
- **JSON**: `~/aerial-wam-v2/artifacts/v1_coll_heldout_diagnostic_20260817.json`

## Metrics (from log + wrap)

| 项 | 值 |
|---|---|
| windows | **260** (65 ep × n-starts=4) |
| `coll_traj_pos` / neg | **20** / 240 |
| `coll_auroc` | **0.977** (≥0.65) |
| reward beat / recon / latent | 1.00 / growth_ok / 21.65 |
| unique usable collision episodes | **8** |
| `coll_ok` / `coll_claimed` | **true** / **true** |
| fidelity overall | **PASS** |

```json
{
  "kind": "v1_2_coll_heldout_diagnostic",
  "not_a_merge_rewrite": true,
  "dataset": "dataset_v1_coll_heldout_20260817",
  "heldout_frac": 1.0,
  "n_starts": 4,
  "coll_traj_pos": 20,
  "coll_traj_neg": 240,
  "coll_auroc": 0.977,
  "unique_usable_collision_episodes": 8,
  "coll_claimed": true,
  "coll_ok": true
}
```

## vs prior r60 diagnostic (§4.1)

| | r60 held-out tail | this held-out set |
|---|---|---|
| split | `--heldout-frac 0.25` (12/48) | `--heldout-frac 1.0` (65/65) |
| unique held-out coll ep | **2** | **8** |
| `coll_traj_pos` | 5 | **20** |
| AUROC | 0.972 | **0.977** |
| claim | diagnostic PASS | diagnostic PASS (cleaner) |

## Honesty

- Quarantine instant-crash eps (**4**) are **not** counted in usable-collision gate language.
- 08-15 merge JSON **unchanged** (`coll_ok=null`).
- `enable_policy_update` stays **false**.
