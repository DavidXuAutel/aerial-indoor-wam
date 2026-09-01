#!/usr/bin/env bash
# E2i.C S2.1 — near-field clean collect on primary B (assist=none, drop collide)
# Chicken-egg: B rarely reaches d<=0.5 without collide → keep d_end<=1.5 clean.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source experiments/aerial/scripts/env_4090.sh
export AIRSIM_CAMERA=0 AIRSIM_VEHICLE=drone_1
mkdir -p logs

STAMP="${STAMP:-20260901}"
ACTOR="${ACTOR:-experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2i_b_20260901/v4_ac_latest.pt}"
OUT="${OUT:-experiments/aerial/rl/artifacts/dataset_indoor_b99_s2_near_avoid_${STAMP}}"
ANN=artifacts/building99_indoor_short_routes.json
# Prefer S3-ARRIVE routes (2,3,4,6) + overweight R06=5; skip SPAWN R01=0 and weak R02=1
ROUTES="${ROUTES:-2,3,4,5,5,5,6}"
EPISODES="${EPISODES:-120}"
MIN_USABLE="${MIN_USABLE:-20}"
NEAR_M="${NEAR_M:-1.50}"
LOG=logs/e2i_c_s2_collect_${STAMP}.log

test -f "$ACTOR"
test -f "$ANN"

if ! pgrep -f 'Building_99/Binaries' >/dev/null || ! ss -ltn | grep -q 41451; then
  bash experiments/aerial/scripts/recover_renderer_scene.sh building99 || true
  sleep 12
fi

echo "[s2] collect actor=$ACTOR out=$OUT routes=$ROUTES near<=$NEAR_M" | tee "$LOG"
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

echo "[s2] count=$(ls "$OUT"/episode_*.npz 2>/dev/null | wc -l)" | tee -a "$LOG"
