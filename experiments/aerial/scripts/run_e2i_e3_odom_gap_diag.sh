#!/usr/bin/env bash
# E3.4 — gt vs hat gap diagnostic on baseline + post-FT eval (+ collect replay).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
STAMP="${STAMP:-20260902}"
OUT="artifacts/indoor_e2i_e3_odom_gap_diag_${STAMP}.json"
DATA="experiments/aerial/rl/artifacts/dataset_indoor_e3_odom_050_${STAMP}"
GLOB="artifacts/indoor_e2i_e3_odom_*_050_seed*_${STAMP}.json"

python3 experiments/aerial/scripts/indoor_e3_odom_gap_diag.py \
  --eval-glob "$GLOB" \
  --dataset "$DATA" \
  --success-dist 0.50 \
  --out "$OUT"

echo "[e3.4] wrote $OUT"
