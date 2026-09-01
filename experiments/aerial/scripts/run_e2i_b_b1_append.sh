#!/usr/bin/env bash
# E2i.B — near-field B1 append (assist=none, drop collide, keep d_end<=0.5 preferred)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source experiments/aerial/scripts/env_4090.sh
export AIRSIM_CAMERA=0 AIRSIM_VEHICLE=drone_1
mkdir -p logs

STAMP="${STAMP:-20260901}"
ACTOR="${ACTOR:-experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2i_a_20260831/v4_ac_latest.pt}"
OUT="${OUT:-experiments/aerial/rl/artifacts/dataset_indoor_b99_none_near_20260831}"
ANN=artifacts/building99_indoor_short_routes.json
# Prefer routes that historically ARRIVE / NEAR (skip chronic SPAWN R01=0 if SKIP_SPAWN_ROUTES=1)
ROUTES="${ROUTES:-1,2,3,4,5,6,7}"  # drop index 0 = Mainline_Route_01 spawn magnet
EPISODES="${EPISODES:-80}"
MIN_USABLE="${MIN_USABLE:-40}"
NEAR_M="${NEAR_M:-0.50}"

test -f "$ACTOR"
test -f "$ANN"

if ! pgrep -f 'Building_99/Binaries' >/dev/null || ! ss -ltn | grep -q 41451; then
  bash experiments/aerial/scripts/recover_renderer_scene.sh building99 || true
  sleep 12
fi

echo "[e2i.b] B1 append actor=$ACTOR out=$OUT routes=$ROUTES near<=$NEAR_M"
$AERIAL_PY experiments/aerial/scripts/indoor_loop_collect.py \
  --config configs/aerial_rl_indoor_shield_v3.yaml \
  --annotation "$ANN" \
  --routes "$ROUTES" \
  --pose-source gt_proxy --assist none \
  --segment-len-m 3.0 --success-dist 0.50 --max-steps 120 \
  --max-intervention-rate 0.55 \
  --keep-near-success --near-success-max-m "$NEAR_M" --drop-collided \
  --append --episodes "$EPISODES" --min-usable "$MIN_USABLE" \
  --actor-ckpt "$ACTOR" \
  --out "$OUT" \
  2>&1 | tee "logs/e2i_b_b1_append_${STAMP}.log"

echo "[e2i.b] B1 count=$(ls "$OUT"/episode_*.npz 2>/dev/null | wc -l)"
