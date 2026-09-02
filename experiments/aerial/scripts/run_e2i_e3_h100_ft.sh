#!/usr/bin/env bash
# E3.2 — H100 π FT (train=eval=odom). Run ON 125 after rsync dataset.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"

STAMP="${STAMP:-20260902}"
DATA="${DATA:-experiments/aerial/rl/artifacts/dataset_indoor_e3_odom_050_${STAMP}}"
INIT_ACT="${INIT_ACT:-experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2i_e_20260901/v4_ac_latest.pt}"
INIT_WM="${INIT_WM:-experiments/aerial/rl/artifacts/wm_ckpt_indoor_encode_e2i_b_20260901/wm_step_400.pt}"
CKPT_DIR="${CKPT_DIR:-experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e3_odom_${STAMP}}"
PI_ITERS="${PI_ITERS:-400}"
H100="${H100:-h100-25}"
H100_REPO="${H100_REPO:-~/aerial-indoor-wam}"
H100_VENV="${H100_VENV:-~/aerial-wam-v2/.venv}"

n_usable=$(ls "$DATA"/episode_*.npz 2>/dev/null | wc -l | tr -d ' ')
test "$n_usable" -ge 30
test -f "$INIT_ACT" && test -f "$INIT_WM"

echo "[e3.2] sync code to H100"
bash experiments/aerial/scripts/sync_indoor_ft_to_h100.sh

echo "[e3.2] tar sync dataset ($n_usable npz) + init ckpts → H100"
ssh "$H100" "mkdir -p ${H100_REPO}/experiments/aerial/rl/artifacts ${H100_REPO}/$(dirname "$INIT_ACT") ${H100_REPO}/$(dirname "$INIT_WM")"
tar -C "$(dirname "$DATA")" -cf - "$(basename "$DATA")" | \
  ssh "$H100" "tar xf - -C ${H100_REPO}/experiments/aerial/rl/artifacts"
tar -C "$(dirname "$INIT_ACT")" -cf - "$(basename "$INIT_ACT")" | \
  ssh "$H100" "tar xf - -C ${H100_REPO}/$(dirname "$INIT_ACT")"
tar -C "$(dirname "$INIT_WM")" -cf - "$(basename "$INIT_WM")" | \
  ssh "$H100" "tar xf - -C ${H100_REPO}/$(dirname "$INIT_WM")"

ssh "$H100" "test -f ${H100_REPO}/${INIT_ACT} && test -f ${H100_REPO}/${INIT_WM} && \
  ls ${H100_REPO}/${DATA}/episode_*.npz | wc -l"

LOG="logs/e2i_e3_h100_ft_${STAMP}.log"
: >"$LOG"
echo "[e3.2] H100 FT iters=$PI_ITERS dataset=$DATA $(date -Is)" | tee -a "$LOG"

ssh "$H100" "bash -s" <<EOF
set -euo pipefail
cd ${H100_REPO}
export VENV=${H100_VENV}
source experiments/aerial/scripts/env_h100.sh
export PYTHONPATH=\$PWD
\$AERIAL_PY -u -m experiments.aerial.rl.train_v4_ac \
  --indoor --dynamics torch --device cuda \
  --wm-ckpt ${INIT_WM} \
  --actor-ckpt ${INIT_ACT} \
  --dataset ${DATA} \
  --skip-collect --no-approach-bias \
  --train-pose-source odom_from_imu_rgb \
  --success-dist-m 0.50 \
  --iters ${PI_ITERS} \
  --ckpt-dir ${CKPT_DIR} \
  2>&1 | tee logs/e2i_e3_h100_ft_${STAMP}.log
EOF

echo "[e3.2] tar sync ckpt H100 → 125"
_ckpt_name="$(basename "$CKPT_DIR")"
mkdir -p "$(dirname "$CKPT_DIR")"
ssh "$H100" "test -d ${H100_REPO}/${CKPT_DIR} && tar cf - -C ${H100_REPO}/experiments/aerial/rl/artifacts ${_ckpt_name}" | \
  tar xf - -C experiments/aerial/rl/artifacts

echo "[e3.2] done ckpt=$CKPT_DIR/v4_ac_latest.pt $(date -Is)" | tee -a "$LOG"
echo "[e3.2] next: STAMP=$STAMP bash experiments/aerial/scripts/run_e2i_e3_odom_eval.sh"
