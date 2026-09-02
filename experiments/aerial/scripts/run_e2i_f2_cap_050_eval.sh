#!/usr/bin/env bash
# F2-cap — F-primary @0.50 on east_from_1; SPAWN excluded from gate denominator.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
STAMP="${STAMP:-20260902}"
export STAMP GATE_MODE=cap
TAG=f2_cap_050_east PROTOCOL=e2i_f2_cap_east ROUTES=0 \
  ANN=artifacts/building99_indoor_short_routes_clean_e.json \
  bash experiments/aerial/scripts/run_e2i_f_eval_050.sh
