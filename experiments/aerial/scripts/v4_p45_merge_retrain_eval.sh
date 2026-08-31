#!/usr/bin/env bash
# P4.5 next: merge usable corpora → depth FT → WM train → re-P3 → re-P1
set -euo pipefail
cd "$(dirname "$0")/../../.."
source experiments/aerial/scripts/env_4090.sh
export PYTHONPATH="${PWD}${PYTHONPATH:+:$PYTHONPATH}"

LOG="${1:-logs/v4_p45_merge_retrain_eval_20260821.log}"
mkdir -p logs
exec > >(tee -a "$LOG") 2>&1

DATA=experiments/aerial/rl/artifacts/dataset_v0_p45_merged_20260821
DEPTH_OUT=experiments/aerial/rl/artifacts/depth_ckpt_p45_merged_20260821
WM_OUT=experiments/aerial/rl/artifacts/wm_ckpt_p45_merged_20260821
INIT_DEPTH=experiments/aerial/rl/artifacts/depth_ckpt_da3_r60_20260814/depth_step_2000_da3_ft_head.pt
TAU=experiments/aerial/rl/artifacts/tau_ckpt_foe_r60_20260815/tau_foe_calibrator.pt

echo "[pipeline] start $(date -Iseconds)"

echo "[pipeline] MERGE"
"$PYTHON_BIN" experiments/aerial/scripts/v4_p45_merge_usable.py \
  --src experiments/aerial/rl/artifacts/dataset_v0_p45_balanced_20260820 \
  --src experiments/aerial/rl/artifacts/dataset_v0_p45_topup_open_20260820 \
  --src experiments/aerial/rl/artifacts/dataset_v0_p45_near_enrich_20260820 \
  --out "$DATA"

echo "[pipeline] DEPTH FT (2000 steps, init r60 da3)"
"$PYTHON_BIN" -m experiments.aerial.rl.train_depth_head \
  --dataset "$DATA" \
  --config configs/aerial_rl.yaml \
  --steps 2000 --wm-batch 8 --window 8 --device cuda \
  --backbone da3 \
  --init-ckpt "$INIT_DEPTH" \
  --lr 3e-5 \
  --holdout-frac 0.2 \
  --checkpoint-dir "$DEPTH_OUT" \
  --save-ckpt \
  --eval-every 200

DEPTH_CKPT=$(ls -1 "$DEPTH_OUT"/depth_step_*_da3_ft*.pt 2>/dev/null | sort | tail -1)
if [[ -z "${DEPTH_CKPT}" ]]; then
  DEPTH_CKPT=$(ls -1 "$DEPTH_OUT"/depth_step_*.pt 2>/dev/null | sort | tail -1)
fi
echo "[pipeline] DEPTH_CKPT=$DEPTH_CKPT"
test -n "${DEPTH_CKPT}" && test -f "$DEPTH_CKPT"

echo "[pipeline] WM train (500 steps, heldout 0.25)"
"$PYTHON_BIN" -m experiments.aerial.rl._wm_train_validate \
  --dataset "$DATA" \
  --config configs/aerial_rl.yaml \
  --steps 500 --device cuda \
  --heldout-frac 0.25 \
  --checkpoint-dir "$WM_OUT" \
  --save-ckpt

WM_CKPT="$WM_OUT/wm_step_500.pt"
test -f "$WM_CKPT"

echo "[pipeline] P3 v4-zero"
set +e
"$PYTHON_BIN" -m experiments.aerial.rl.v4_zero_eval \
  --dataset "$DATA" \
  --depth-ckpt "$DEPTH_CKPT" \
  --tau-ckpt "$TAU" \
  --device cuda \
  --heldout-frac 0.2 \
  --split-seed 0 \
  --emit artifacts/v4_zero_p3_p45_merged_20260821.json
P3_EC=$?
set -e
echo "[pipeline] P3 exit=$P3_EC (continue to P1 even if FAIL; heldout seeded seed=0 matches depth FT)"

echo "[pipeline] P1 fidelity"
set +e
"$PYTHON_BIN" -m experiments.aerial.rl._wm_fidelity_eval \
  --dataset "$DATA" \
  --ckpt "$WM_CKPT" \
  --config configs/aerial_rl.yaml \
  --heldout-frac 0.25 \
  --device cuda \
  | tee logs/v4_p1_p45_merged_20260821.log
P1_EC=$?
set -e
echo "[pipeline] P1 exit=$P1_EC"

echo "[pipeline] DONE $(date -Iseconds)"
echo "DATA=$DATA"
echo "DEPTH=$DEPTH_CKPT"
echo "WM=$WM_CKPT"
echo "P3=artifacts/v4_zero_p3_p45_merged_20260821.json (exit=$P3_EC)"
echo "P1=logs/v4_p1_p45_merged_20260821.log (exit=$P1_EC)"
exit 0
