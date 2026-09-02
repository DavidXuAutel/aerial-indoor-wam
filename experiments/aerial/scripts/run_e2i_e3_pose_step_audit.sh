#!/usr/bin/env bash
# E3.5 — per-step odom audit on clean_sg south+east (routes 1,2).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
STAMP="${STAMP:-20260902}"
# shellcheck disable=SC1091
source experiments/aerial/scripts/env_4090.sh
export AIRSIM_CAMERA=0 AIRSIM_VEHICLE=drone_1
mkdir -p logs artifacts

ANN="${ANN:-artifacts/building99_indoor_short_routes_clean_e.json}"
[[ -f "$ANN" ]] || ANN="$(basename "$ANN")"
ROUTES="${ROUTES:-0}"
OUT=artifacts/indoor_e2i_e3_pose_step_audit_east_${STAMP}.json
LOG=logs/e2i_e3_pose_step_audit_east_${STAMP}.log

test -f "$ANN" && test -f "$WM" && test -f "$ACT"

if ! pgrep -f 'Building_99/Binaries' >/dev/null || ! ss -ltn | grep -q 41451; then
  ON_SCREEN="${ON_SCREEN:-0}" bash experiments/aerial/scripts/recover_renderer_scene.sh building99 || true
  sleep 12
fi
ss -ltn | grep -q 41451

echo "[e3.5] pose step audit east routes=$ROUTES seeds=0,1,2 $(date -Is)" | tee "$LOG"
$AERIAL_PY experiments/aerial/scripts/indoor_e3_pose_step_audit.py \
  --config "$CFG" \
  --wm-ckpt "$WM" \
  --actor-ckpt "$ACT" \
  --annotation "$ANN" \
  --routes "$ROUTES" \
  --seeds 0,1,2 \
  --segment-len-m 3.0 \
  --success-dist 0.50 \
  --max-steps 160 \
  --out "$OUT" \
  2>&1 | tee -a "$LOG"

echo "[e3.5] done out=$OUT $(date -Is)" | tee -a "$LOG"
