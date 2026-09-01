#!/usr/bin/env bash
# E2i.D D2 — assist=none near-field self-collect (d_end<=0.30, no collide); skip SPAWN routes.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source experiments/aerial/scripts/env_4090.sh
export AIRSIM_CAMERA=0 AIRSIM_VEHICLE=drone_1
mkdir -p logs

STAMP="${STAMP:-20260901}"
OUT="${OUT:-experiments/aerial/rl/artifacts/dataset_indoor_b99_none_near_d_${STAMP}}"
ACTOR="${ACTOR:-experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2i_b_20260901/v4_ac_latest.pt}"
ANN=artifacts/building99_indoor_short_routes.json
# R03–R07 idx 2,3,4,6,7 — skip R01=0, R02=1 (SPAWN-heavy), R06=5 (fixture D1)
ROUTES="${ROUTES:-2,3,4,6,7}"
EPISODES="${EPISODES:-120}"
MIN_USABLE="${MIN_USABLE:-50}"
NEAR_M="${NEAR_M:-0.30}"
LOG=logs/e2i_d_d2_none_near_${STAMP}.log

test -f "$ACTOR"
test -f "$ANN"

if ! pgrep -f 'Building_99/Binaries' >/dev/null || ! ss -ltn | grep -q 41451; then
  bash experiments/aerial/scripts/recover_renderer_scene.sh building99 || true
  sleep 12
fi

echo "[d2] none near out=$OUT routes=$ROUTES near<=${NEAR_M}m" | tee "$LOG"
$AERIAL_PY experiments/aerial/scripts/indoor_loop_collect.py \
  --config configs/aerial_rl_indoor_shield_v3.yaml \
  --annotation "$ANN" \
  --routes "$ROUTES" \
  --pose-source gt_proxy --assist none \
  --segment-len-m 3.0 --success-dist 0.50 --max-steps 160 \
  --keep-near-success --near-success-max-m "$NEAR_M" --drop-collided \
  --episodes "$EPISODES" --min-usable "$MIN_USABLE" \
  --actor-ckpt "$ACTOR" \
  --out "$OUT" \
  2>&1 | tee -a "$LOG"

echo "[d2] count=$(ls "$OUT"/episode_*.npz 2>/dev/null | wc -l)" | tee -a "$LOG"
