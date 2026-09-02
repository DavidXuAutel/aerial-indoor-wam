#!/usr/bin/env bash
# E3.5′ — odom @0.50 east-only re-eval after pose_estimate velfix.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
STAMP="${STAMP:-20260902_velfix}"
export STAMP GATE_MODE=cap
TAG=e3_odom_east_velfix_050
PROTOCOL=e3_odom_east_velfix_cap
ACT="${ACT:-experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2i_e_20260901/v4_ac_latest.pt}"
ANN=artifacts/building99_indoor_short_routes_clean_e.json
ROUTES=0

# shellcheck disable=SC1091
source experiments/aerial/scripts/env_4090.sh
export AIRSIM_CAMERA=0 AIRSIM_VEHICLE=drone_1
mkdir -p logs artifacts

WM=experiments/aerial/rl/artifacts/wm_ckpt_indoor_encode_e2i_b_20260901/wm_step_400.pt
CFG_EVAL=configs/aerial_rl_indoor_shield_v3.yaml
LOG="logs/e2i_${TAG}_${STAMP}.log"

test -f "$ACT" && test -f "$WM" && test -f "$ANN"

if ! pgrep -f 'Building_99/Binaries' >/dev/null || ! ss -ltn | grep -q 41451; then
  ON_SCREEN="${ON_SCREEN:-0}" bash experiments/aerial/scripts/recover_renderer_scene.sh building99 || true
  sleep 12
fi
ss -ltn | grep -q 41451

: >"$LOG"
echo "[$TAG] odom east-only @0.50 act=$ACT $(date -Is)" | tee -a "$LOG"

for SEED in 0 1 2; do
  OUT="artifacts/indoor_e2i_${TAG}_seed${SEED}_${STAMP}.json"
  TMP="/tmp/aerial_rl_${TAG}_seed${SEED}.yaml"
  python3 - <<PY
import yaml
from pathlib import Path
cfg = yaml.safe_load(Path("$CFG_EVAL").read_text()) or {}
env = cfg.setdefault("env", {})
env["seed"] = int("$SEED")
env["spawn_retry_max"] = 6
env["spawn_min_z_m"] = 1.4
env["spawn_z_bump_m"] = 0.15
env["spawn_settle_s"] = 0.50
env["spawn_hold"] = True
env["spawn_xy_nudge_m"] = 0.30
env["spawn_z_raise_m"] = 0.0
env["spawn_z_floor_cmd_m"] = 1.8
cfg.setdefault("reward", {})["success_dist_m"] = 0.50
Path("$TMP").write_text(yaml.safe_dump(cfg, sort_keys=False))
PY
  $AERIAL_PY experiments/aerial/scripts/indoor_mainline_baseline_eval.py \
    --config "$TMP" \
    --actor-ckpt "$ACT" \
    --wm-ckpt "$WM" \
    --pose-source odom_from_imu_rgb --assist none \
    --annotation "$ANN" --routes "$ROUTES" \
    --segment-len-m 3.0 --success-dist 0.50 --max-steps 160 \
    --out "$OUT" \
    2>&1 | tee -a "$LOG"
  $AERIAL_PY experiments/aerial/scripts/indoor_fail_split_report.py \
    --in "$OUT" \
    --out "artifacts/indoor_e2i_${TAG}_seed${SEED}_fail_split.json" \
    2>&1 | tee -a "$LOG"
done

GATE_MODE=cap TAG="$TAG" STAMP="$STAMP" PROTOCOL="$PROTOCOL" ANN="$ANN" ROUTES="$ROUTES" \
  $AERIAL_PY experiments/aerial/scripts/indoor_e2i_f_summary.py \
  --tag "$TAG" --stamp "$STAMP" --protocol "$PROTOCOL" \
  --ann "$ANN" --routes "$ROUTES" --success-dist 0.50 --gate-mode cap \
  --pose-source odom_from_imu_rgb --pose-note "E3 formal; arrived_hat is primary" \
  --out "artifacts/indoor_e2i_${TAG}_summary_${STAMP}.json" \
  2>&1 | tee -a "$LOG"

echo "[$TAG] done $(date -Is)" | tee -a "$LOG"
