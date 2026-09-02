#!/usr/bin/env bash
# F1d (south+east primary) then F1e (clean_sg + spawn retry incl. west). No FT.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
STAMP="${STAMP:-20260902}"
export STAMP

echo "[batch] F1d south+east @0.50 $(date -Is)"
TAG=f1d_050_se PROTOCOL=e2i_f1d_se ROUTES=0,1 \
  ANN=artifacts/building99_indoor_short_routes_clean_se.json \
  bash experiments/aerial/scripts/run_e2i_f_eval_050.sh

echo "[batch] F1e clean_sg + spawn retry @0.50 $(date -Is)"
TAG=f1e_050_sgclean_spawnfix PROTOCOL=e2i_f1e_sgclean_spawnfix ROUTES=0,1,2 \
  ANN=artifacts/building99_indoor_short_routes_clean_sg.json \
  bash experiments/aerial/scripts/run_e2i_f_eval_050.sh

echo "[batch] all done $(date -Is)"
