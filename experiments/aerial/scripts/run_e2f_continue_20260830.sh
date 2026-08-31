#!/usr/bin/env bash
# E2f continue: wait AirSim idle → fixture BC collect → FT@4090 → assist=none multi-eval @0.20
set -euo pipefail
REPO=/home/yao/aerial-indoor-wam
cd "$REPO"
source experiments/aerial/scripts/env_4090.sh
mkdir -p logs artifacts

echo "[e2f] E2f.0 wait AirSim idle (no kill Phase-2) ..."
bash experiments/aerial/scripts/wait_airsim_idle.sh --timeout-sec 7200

echo "[e2f] recover renderer after Phase-2 long eval ..."
bash "${AERIAL_PERSIST_ROOT:-/home/yao/aerial_airsim_persistent}/recover_renderer.sh" | tail -5
sleep 15

DATASET=experiments/aerial/rl/artifacts/dataset_indoor_fixture_bc_e2f_20260830
CKPT_IN=experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2d_20260829/v4_ac_latest.pt
CKPT_OUT=experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2f_20260830
PRIOR=$(ls "$DATASET"/episode_*.npz 2>/dev/null | wc -l)
NEED=$((15 - PRIOR))
if (( NEED < 1 )); then NEED=1; fi
# enough attempts to reach 15 arrived total (fixture yield ~5–15%)
EPISODES=$((NEED * 12))
if (( EPISODES < 50 )); then EPISODES=50; fi

echo "[e2f] E2f.1 collect fixture BC (prior arrived=$PRIOR, episodes=$EPISODES) ..."
$AERIAL_PY -u experiments/aerial/scripts/indoor_loop_collect.py \
  --pose-source gt_proxy --assist gt_pd --allow-gt-assist --keep-arrived-only \
  --bc-tag fixture_gt_pd \
  --routes 6,12 --segment-len-m 6 --success-dist 0.50 \
  --max-steps 200 --episodes "$EPISODES" --min-usable 15 \
  --actor-ckpt "$CKPT_IN" \
  --out "$DATASET" \
  2>&1 | tee -a logs/indoor_e2f_fixture_collect_20260830.log

ARRIVED=$(ls "$DATASET"/episode_*.npz 2>/dev/null | wc -l)
echo "[e2f] arrived npz count=$ARRIVED"
if (( ARRIVED < 15 )); then
  echo "[e2f] FAIL: n_arrived=$ARRIVED < 15 gate" >&2
  exit 1
fi

echo "[e2f] E2f.2 FT @4090 ..."
$AERIAL_PY -u -m experiments.aerial.rl.train_v4_ac \
  --indoor --iters 500 --device cuda --dynamics torch \
  --wm-ckpt experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt \
  --actor-ckpt "$CKPT_IN" \
  --dataset "$DATASET" \
  --skip-collect --train-pose-source gt_proxy \
  --ckpt-dir "$CKPT_OUT" \
  2>&1 | tee logs/indoor_e2f_ft_4090_20260830.log

echo "[e2f] E2f.3 contract eval assist=none @0.20 (3 seeds) ..."
for SEED in 0 1 2; do
  echo "[e2f] eval seed=$SEED ..."
  $AERIAL_PY experiments/aerial/scripts/indoor_mainline_baseline_eval.py \
    --actor-ckpt "$CKPT_OUT/v4_ac_latest.pt" \
    --pose-source gt_proxy --assist none \
    --routes 6,12 --segment-len-m 6 --success-dist 0.20 \
    --max-steps 200 \
    --out "artifacts/indoor_mainline_baseline_e2f_020_seed${SEED}_20260830.json" \
    2>&1 | tee "logs/indoor_e2f_eval_020_seed${SEED}_20260830.log"
done

echo "[e2f] DONE pipeline"
