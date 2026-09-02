#!/usr/bin/env bash
# F-collect — gt_proxy closed-loop on F-cap route (east_from_1 @0.50).
# NOT E3. Drops collided; keeps arrived @0.50. Builds toward multi-route corpus later.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source experiments/aerial/scripts/env_4090.sh
export AIRSIM_CAMERA=0 AIRSIM_VEHICLE=drone_1
mkdir -p logs

STAMP="${STAMP:-20260902}"
ACTOR="${ACTOR:-experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2i_e_20260901/v4_ac_latest.pt}"
WM="${WM:-experiments/aerial/rl/artifacts/wm_ckpt_indoor_encode_e2i_b_20260901/wm_step_400.pt}"
OUT="${OUT:-experiments/aerial/rl/artifacts/dataset_indoor_f_collect_east_050_${STAMP}}"
ANN=artifacts/building99_indoor_short_routes_clean_e.json
ROUTES="${ROUTES:-0}"
EPISODES="${EPISODES:-80}"
MIN_USABLE="${MIN_USABLE:-20}"
LOG=logs/e2i_f_collect_east_${STAMP}.log

test -f "$ACTOR" && test -f "$WM" && test -f "$ANN"

if ! pgrep -f 'Building_99/Binaries' >/dev/null || ! ss -ltn | grep -q 41451; then
  ON_SCREEN="${ON_SCREEN:-0}" bash experiments/aerial/scripts/recover_renderer_scene.sh building99 || true
  sleep 12
fi
ss -ltn | grep -q 41451

echo "[f-collect] east @0.50 gt_proxy actor=$ACTOR out=$OUT eps=$EPISODES" | tee "$LOG"
$AERIAL_PY experiments/aerial/scripts/indoor_loop_collect.py \
  --config configs/aerial_rl_indoor_shield_v3.yaml \
  --wm-ckpt "$WM" \
  --annotation "$ANN" \
  --routes "$ROUTES" \
  --pose-source gt_proxy --assist none \
  --segment-len-m 3.0 --success-dist 0.50 --max-steps 160 \
  --keep-arrived-only --drop-collided \
  --episodes "$EPISODES" --min-usable "$MIN_USABLE" \
  --actor-ckpt "$ACTOR" \
  --out "$OUT" \
  2>&1 | tee -a "$LOG"

echo "[f-collect] npz=$(ls "$OUT"/episode_*.npz 2>/dev/null | wc -l)" | tee -a "$LOG"
