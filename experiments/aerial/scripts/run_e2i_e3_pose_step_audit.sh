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

ANN=artifacts/building99_indoor_short_routes_clean_sg.json
WM=experiments/aerial/rl/artifacts/wm_ckpt_indoor_encode_e2i_b_20260901/wm_step_400.pt
ACT=experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2i_e_20260901/v4_ac_latest.pt
CFG=configs/aerial_rl_indoor_shield_v3.yaml
OUT=artifacts/indoor_e2i_e3_pose_step_audit_${STAMP}.json
LOG=logs/e2i_e3_pose_step_audit_${STAMP}.log

test -f "$ANN" && test -f "$WM" && test -f "$ACT"

if ! pgrep -f 'Building_99/Binaries' >/dev/null || ! ss -ltn | grep -q 41451; then
  ON_SCREEN="${ON_SCREEN:-0}" bash experiments/aerial/scripts/recover_renderer_scene.sh building99 || true
  sleep 12
fi
ss -ltn | grep -q 41451

echo "[e3.5] pose step audit routes=1,2 seeds=0,1,2 $(date -Is)" | tee "$LOG"
$AERIAL_PY experiments/aerial/scripts/indoor_e3_pose_step_audit.py \
  --config "$CFG" \
  --wm-ckpt "$WM" \
  --actor-ckpt "$ACT" \
  --annotation "$ANN" \
  --routes 1,2 \
  --seeds 0,1,2 \
  --segment-len-m 3.0 \
  --success-dist 0.50 \
  --max-steps 160 \
  --out "$OUT" \
  2>&1 | tee -a "$LOG"

echo "[e3.5] done out=$OUT $(date -Is)" | tee -a "$LOG"
