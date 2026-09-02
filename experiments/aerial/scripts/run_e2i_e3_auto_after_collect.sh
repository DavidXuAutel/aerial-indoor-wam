#!/usr/bin/env bash
# Wait for E3.1 collect, then E3.2 H100 FT + E3.3 odom eval.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
STAMP="${STAMP:-20260902}"
DATA="experiments/aerial/rl/artifacts/dataset_indoor_e3_odom_050_${STAMP}"
LOG="logs/e2i_e3_auto_ft_eval_${STAMP}.nohup.log"

echo "[e3-auto] waiting for collect $(date -Is)" | tee "$LOG"
while pgrep -f "indoor_loop_collect.py.*dataset_indoor_e3_odom_050_${STAMP}" >/dev/null; do
  n=$(ls "$DATA"/episode_*.npz 2>/dev/null | wc -l | tr -d ' ')
  echo "[e3-auto] collect running usable=$n $(date -Is)" | tee -a "$LOG"
  sleep 45
done

n=$(ls "$DATA"/episode_*.npz 2>/dev/null | wc -l | tr -d ' ')
echo "[e3-auto] collect done usable=$n $(date -Is)" | tee -a "$LOG"
test "$n" -ge 30

echo "[e3-auto] E3.2 H100 FT $(date -Is)" | tee -a "$LOG"
STAMP="$STAMP" bash experiments/aerial/scripts/run_e2i_e3_h100_ft.sh 2>&1 | tee -a "$LOG"

echo "[e3-auto] E3.3 odom eval $(date -Is)" | tee -a "$LOG"
STAMP="$STAMP" bash experiments/aerial/scripts/run_e2i_e3_odom_eval.sh 2>&1 | tee -a "$LOG"

echo "[e3-auto] E3 full done $(date -Is)" | tee -a "$LOG"
