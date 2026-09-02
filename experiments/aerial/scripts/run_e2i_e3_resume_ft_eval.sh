#!/usr/bin/env bash
# Resume E3.2 H100 FT + E3.3 eval after collect done (or auto-chain failure).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
STAMP="${STAMP:-20260902}"
LOG="logs/e2i_e3_resume_ft_eval_${STAMP}.nohup.log"

echo "[e3-resume] E3.2 H100 FT $(date -Is)" | tee "$LOG"
STAMP="$STAMP" bash experiments/aerial/scripts/run_e2i_e3_h100_ft.sh 2>&1 | tee -a "$LOG"

echo "[e3-resume] E3.3 odom eval $(date -Is)" | tee -a "$LOG"
STAMP="$STAMP" bash experiments/aerial/scripts/run_e2i_e3_odom_eval.sh 2>&1 | tee -a "$LOG"

echo "[e3-resume] done $(date -Is)" | tee -a "$LOG"
