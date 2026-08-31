# V1 collision-rich held-out collect STATUS (125 / 4090)

- **status**: **DONE** (collect finished; dataset synced to H100; diagnostic eval claimed — see [`V1_COLL_HELDOUT_DIAGNOSTIC_STATUS.md`](V1_COLL_HELDOUT_DIAGNOSTIC_STATUS.md))
- **started**: 2026-08-17T16:05:40+08:00 (restart; see aborted attempt below)
- **finished**: 2026-08-17 ~16:34+08:00
- **host**: `cursor-125` / `10.229.20.125` (4090)
- **HEAD at launch**: `0541c74` (STATUS commits may be ahead)
- **PID**: `1146088` (exited)
- **log**: `logs/v1_coll_heldout_collect_20260817.log`
- **dataset**: `experiments/aerial/rl/artifacts/dataset_v1_coll_heldout_20260817`
- **purpose**: WM-unseen collision-rich held-out for cleaner V1-②-coll claim (unique collision episodes **≥3**; r60 diagnostic had unique held-out coll ep=2). Does **not** rewrite 08-15 merge; `enable_policy_update` stays **false**.

## Collect result

| 项 | 值 |
|---|---|
| episodes written | **69** |
| quarantined | **4** (instant crash ≤2 steps; spawn) |
| usable | **65** |
| `total_collisions` (QUALITY) | **12** |
| usable collision episodes | **8** (12 raw − 4 quarantine; exceeds unique-coll≥3) |
| QUALITY / manifest | present |

Usable collision files (not quarantine): `episode_00016/00017/00033/00034/00050/00051/00067/00068.npz`.

## Command (ran)

```bash
cd ~/aerial-wam-v2
source experiments/aerial/scripts/env_4090.sh
OUT=experiments/aerial/rl/artifacts/dataset_v1_coll_heldout_20260817
nohup "$PYTHON_BIN" -m experiments.aerial.rl.collect_dataset \
  --backend airsim --host 127.0.0.1 --port 41451 \
  --camera front_custom --vehicle drone_1 \
  --annotation "$ANNOTATION" \
  --episodes 80 --max-steps 200 --step-hz 5.0 \
  --grab-depth \
  --out "$OUT" \
  > logs/v1_coll_heldout_collect_20260817.log 2>&1 &
```

(Stopped after 69 written + QUALITY; spawn-collision skips consumed the rest of the 80 budget.)

## Design notes

| Choice | Why |
|---|---|
| **no** `--approach-bias` | Abort of approach-d18 (below) got only **1/22** coll — early goal success. Plain r60 recipe historically **9/51** coll |
| `--episodes 80` | Margin over r60’s 60 so unique coll ep≥3 is realistic |
| `--grab-depth --step-hz 5.0` | Schema-v2 / `_refuse_v0` / fidelity-eval compatible |
| manifest via `collect_dataset` | Avoid approach_merged / near_merged “no manifest” failure mode |

## Aborted attempt (same day)

- PID `1134097`, `--approach-bias --approach-dist-m 18 --episodes 60`
- Early sample **1/22** coll; episodes ~17–26 steps (goal reached before obstacles)
- Artifacts kept under `dataset_v1_coll_heldout_20260817_abort_approach_d18_*` + matching log

## H100 transfer

- **method**: `tar | ssh h100-25` (H100 has no `rsync` in PATH)
- **dest**: `~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/dataset_v1_coll_heldout_20260817`
- **verified**: 950M, 69 `episode_*.npz`, manifest + QUALITY_SUMMARY match 125

## Next

1. ~~Confirm manifest + usable collision count~~ ✅ usable coll ep=**8**
2. ~~Tar+ssh to H100~~ ✅
3. ~~H100 V1-②-coll fidelity diagnostic~~ ✅ claimed — [`V1_COLL_HELDOUT_DIAGNOSTIC_STATUS.md`](V1_COLL_HELDOUT_DIAGNOSTIC_STATUS.md)
4. Do **not** rewrite 08-15 merge JSON (`coll_ok` stays null on merge)

## Unchanged (do not flip)

- `enable_policy_update: false`
- 08-15 V1 merge JSON / yaml gate flags
- No Desk API / Franka network changes
