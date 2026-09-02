#!/usr/bin/env bash
# E3.1 — odom closed-loop collect on clean_sg (west/south/east @0.50).
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
OUT="${OUT:-experiments/aerial/rl/artifacts/dataset_indoor_e3_odom_050_${STAMP}}"
ANN=artifacts/building99_indoor_short_routes_clean_sg.json
ROUTES="${ROUTES:-0,1,2}"
EPISODES="${EPISODES:-120}"
MIN_USABLE="${MIN_USABLE:-30}"
LOG=logs/e2i_e3_odom_collect_${STAMP}.log

test -f "$ACTOR" && test -f "$WM" && test -f "$ANN"

if ! pgrep -f 'Building_99/Binaries' >/dev/null || ! ss -ltn | grep -q 41451; then
  ON_SCREEN="${ON_SCREEN:-0}" bash experiments/aerial/scripts/recover_renderer_scene.sh building99 || true
  sleep 12
fi
ss -ltn | grep -q 41451

echo "[e3.1] odom collect clean_sg routes=$ROUTES eps=$EPISODES min=$MIN_USABLE" | tee "$LOG"
$AERIAL_PY experiments/aerial/scripts/indoor_loop_collect.py \
  --config configs/aerial_rl_indoor_shield_v3.yaml \
  --wm-ckpt "$WM" \
  --annotation "$ANN" \
  --routes "$ROUTES" \
  --pose-source odom_from_imu_rgb --assist none \
  --segment-len-m 3.0 --success-dist 0.50 --max-steps 160 \
  --keep-arrived-only --drop-collided \
  --episodes "$EPISODES" --min-usable "$MIN_USABLE" \
  --actor-ckpt "$ACTOR" \
  --out "$OUT" \
  2>&1 | tee -a "$LOG"

echo "[e3.1] npz=$(ls "$OUT"/episode_*.npz 2>/dev/null | wc -l)" | tee -a "$LOG"
