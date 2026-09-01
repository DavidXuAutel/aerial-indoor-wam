#!/usr/bin/env bash
# E2i.4 — @0.20 contract probe / C2 eval (Building_99, shield ON)
# Usage:
#   bash experiments/aerial/scripts/run_e2i4_020_eval.sh          # probe e2i_a head
#   ACTOR=... WM=... TAG=c2_020 bash experiments/aerial/scripts/run_e2i4_020_eval.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source experiments/aerial/scripts/env_4090.sh
export AIRSIM_CAMERA=0 AIRSIM_VEHICLE=drone_1
mkdir -p logs artifacts

STAMP="${STAMP:-20260831}"
TAG="${TAG:-e2i_a_020_probe}"
ACTOR="${ACTOR:-experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2i_a_${STAMP}/v4_ac_latest.pt}"
WM_CKPT="${WM_CKPT:-experiments/aerial/rl/artifacts/wm_ckpt_indoor_encode_e2i_a_${STAMP}/wm_step_400.pt}"
CFG="${CFG:-configs/aerial_rl_indoor_shield_v3.yaml}"
ANN=artifacts/building99_indoor_short_routes.json
ROUTES=0,1,2,3,4,5,6,7
LOG="logs/${TAG}_${STAMP}.log"

test -f "$ACTOR"
test -f "$WM_CKPT"
test -f "$ANN"

echo "[e2i.4] @0.20 eval actor=$ACTOR wm=$WM_CKPT" | tee "$LOG"

for SEED in 0 1 2; do
  OUT="artifacts/indoor_${TAG}_seed${SEED}_${STAMP}.json"
  TMP_CFG="/tmp/aerial_rl_indoor_v3_seed${SEED}_${TAG}.yaml"
  python3 - <<PY
import yaml
from pathlib import Path
cfg = yaml.safe_load(Path("$CFG").read_text()) or {}
cfg.setdefault("env", {})["seed"] = int("$SEED")
cfg.setdefault("reward", {})["success_dist_m"] = 0.20
Path("$TMP_CFG").write_text(yaml.safe_dump(cfg, sort_keys=False))
PY
  $AERIAL_PY experiments/aerial/scripts/indoor_mainline_baseline_eval.py \
    --config "$TMP_CFG" \
    --actor-ckpt "$ACTOR" \
    --wm-ckpt "$WM_CKPT" \
    --pose-source gt_proxy --assist none \
    --annotation "$ANN" --routes "$ROUTES" \
    --segment-len-m 3.0 --success-dist 0.20 --max-steps 160 \
    --out "$OUT" \
    2>&1 | tee -a "$LOG"
done

STAMP="$STAMP" TAG="$TAG" $AERIAL_PY - <<'PY'
import json, os
from pathlib import Path
stamp = os.environ["STAMP"]
tag = os.environ["TAG"]
rows = []
for seed in (0, 1, 2):
    p = Path(f"artifacts/indoor_{tag}_seed{seed}_{stamp}.json")
    if not p.is_file():
        continue
    d = json.loads(p.read_text())
    eps = d.get("episodes") or d.get("results") or []
    arrived = sum(1 for e in eps if e.get("arrived") or e.get("success"))
    dens = []
    cols = 0
    for e in eps:
        v = e.get("d_end_m_gt", e.get("d_end_m"))
        if v is not None:
            dens.append(float(v))
        if e.get("collided"):
            cols += 1
    rows.append({
        "seed": seed,
        "file": str(p),
        "n": len(eps),
        "arrived": arrived,
        "mean_d": (sum(dens) / len(dens)) if dens else None,
        "collision_n": cols,
    })
seeds_with = sum(1 for r in rows if r["arrived"] > 0)
all_d = [r["mean_d"] for r in rows if r["mean_d"] is not None]
mean_d = (sum(all_d) / len(all_d)) if all_d else None
gate = seeds_with >= 2 or (mean_d is not None and mean_d <= 0.8)
out = {
    "protocol": "e2i4_contract_020",
    "tag": tag,
    "seeds_with_arrival": seeds_with,
    "mean_d_end_m": mean_d,
    "gate_pass": gate,
    "gate_rule": "seeds_with_arrival>=2/3 OR mean_d<=0.8",
    "seeds": rows,
}
path = Path(f"artifacts/indoor_{tag}_summary_{stamp}.json")
path.write_text(json.dumps(out, indent=2) + "\n")
print(json.dumps(out, indent=2))
print(f"summary → {path}")
PY

echo "[e2i.4] done tag=$TAG"
