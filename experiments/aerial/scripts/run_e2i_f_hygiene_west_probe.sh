#!/usr/bin/env bash
# F-hygiene — west route per-step collision attribution (non-gate).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
STAMP="${STAMP:-20260902}"
OUT="artifacts/indoor_west_collision_probe_${STAMP}.json"
LOG="logs/e2i_f_hygiene_west_probe_${STAMP}.log"

# shellcheck disable=SC1091
source experiments/aerial/scripts/env_4090.sh
export AIRSIM_CAMERA=0 AIRSIM_VEHICLE=drone_1
mkdir -p logs artifacts

if ! pgrep -f 'Building_99/Binaries' >/dev/null || ! ss -ltn | grep -q 41451; then
  ON_SCREEN="${ON_SCREEN:-0}" bash experiments/aerial/scripts/recover_renderer_scene.sh building99 || true
  sleep 15
fi
ss -ltn | grep -q 41451

echo "[hygiene west] start $(date -Is)" | tee "$LOG"
$AERIAL_PY experiments/aerial/scripts/indoor_west_collision_probe.py \
  --out "$OUT" 2>&1 | tee -a "$LOG"
echo "[hygiene west] done out=$OUT $(date -Is)" | tee -a "$LOG"
