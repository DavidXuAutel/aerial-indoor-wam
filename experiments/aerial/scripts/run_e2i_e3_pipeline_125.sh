#!/usr/bin/env bash
# E3 full pipeline on 125: baseline odom eval → odom collect (H100 FT is separate).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
STAMP="${STAMP:-20260902}"
export STAMP

echo "[e3] E3.0 odom baseline @0.50 $(date -Is)"
BASELINE=1 bash experiments/aerial/scripts/run_e2i_e3_odom_eval.sh

echo "[e3] E3.1 odom collect clean_sg $(date -Is)"
bash experiments/aerial/scripts/run_e2i_e3_odom_collect.sh

echo "[e3] 125 phase done. Run H100 FT then E3.3:"
echo "  STAMP=$STAMP bash experiments/aerial/scripts/run_e2i_e3_h100_ft.sh"
echo "  STAMP=$STAMP bash experiments/aerial/scripts/run_e2i_e3_odom_eval.sh"
