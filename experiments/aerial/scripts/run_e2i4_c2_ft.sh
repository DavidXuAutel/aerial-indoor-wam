#!/usr/bin/env bash
# E2i.4c — C2 offline FT (4090 default; set USE_H100=1 to hop)
# Mix: B2≥50% fixture@0.20 + B1≥30% near-success
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source experiments/aerial/scripts/env_4090.sh

STAMP="${STAMP:-20260831}"
ITERS="${ITERS:-1500}"
MIX_OUT="${MIX_OUT:-experiments/aerial/rl/artifacts/dataset_indoor_e2i_c2_${STAMP}}"
WM_CKPT="${WM_CKPT:-experiments/aerial/rl/artifacts/wm_ckpt_indoor_encode_e2i_a_${STAMP}/wm_step_400.pt}"
PI_PARENT="${PI_PARENT:-experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2i_a_${STAMP}/v4_ac_latest.pt}"
PI_OUT="${PI_OUT:-experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2i_c2_${STAMP}}"
LOG_DIR="${LOG_DIR:-$ROOT/logs}"
mkdir -p "$LOG_DIR"

echo "[e2i.4c] build C2 mix → $MIX_OUT"
$AERIAL_PY experiments/aerial/scripts/indoor_build_e2i_a_mix.py \
  --out "$MIX_OUT" \
  --b1 "experiments/aerial/rl/artifacts/dataset_indoor_b99_none_near_${STAMP}" \
  --b2 "experiments/aerial/rl/artifacts/dataset_indoor_b99_fixture_020_${STAMP}" \
  --total 100 \
  --b1-frac 0.35 --b2-frac 0.55 --old-frac 0.0 \
  --keep-early-collision

test -f "$WM_CKPT"
test -f "$PI_PARENT"

echo "[e2i.4c] C2 FT iters=$ITERS → $PI_OUT"
$AERIAL_PY -u -m experiments.aerial.rl.train_v4_ac \
  --indoor --dynamics torch --device cuda \
  --wm-ckpt "$WM_CKPT" \
  --actor-ckpt "$PI_PARENT" \
  --dataset "$MIX_OUT" \
  --skip-collect --no-approach-bias \
  --train-pose-source gt_proxy \
  --success-dist-m 0.20 \
  --iters "$ITERS" \
  --ckpt-dir "$PI_OUT" \
  2>&1 | tee "$LOG_DIR/e2i_c2_ft_${ITERS}_${STAMP}.log"

echo "[e2i.4c] done ckpt=$PI_OUT/v4_ac_latest.pt"
