#!/usr/bin/env bash
# E2i.E E2 auto — depth-reactive R06 collect (agent fly; no human keyboard).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source experiments/aerial/scripts/env_4090.sh
export AIRSIM_CAMERA=0 AIRSIM_VEHICLE=drone_1
mkdir -p logs

STAMP="${STAMP:-20260901}"
OUT="${OUT:-experiments/aerial/rl/artifacts/dataset_indoor_b99_teleop_r06_e_${STAMP}}"
EPISODES="${EPISODES:-100}"
MIN_USABLE="${MIN_USABLE:-8}"
SUCCESS_DIST="${SUCCESS_DIST:-0.25}"
LOG=logs/e2i_e_e2_auto_r06_${STAMP}.log

if ! pgrep -f 'Building_99/Binaries' >/dev/null || ! ss -ltn | grep -q 41451; then
  bash experiments/aerial/scripts/recover_renderer_scene.sh building99 || true
  sleep 12
fi

echo "[e2-auto] depth-reactive R06 out=$OUT success<=${SUCCESS_DIST}m" | tee "$LOG"
set +e
$AERIAL_PY experiments/aerial/scripts/indoor_r06_auto_avoid_collect.py \
  --route-idx 5 \
  --success-dist "$SUCCESS_DIST" \
  --episodes "$EPISODES" --min-usable "$MIN_USABLE" \
  --danger-m 2.5 --stop-m 1.25 \
  --out "$OUT" \
  2>&1 | tee -a "$LOG"
RC=$?
set -e
echo "[e2-auto] count=$(ls "$OUT"/episode_*.npz 2>/dev/null | wc -l | tr -d ' ') rc=$RC" | tee -a "$LOG"
exit "$RC"
