#!/usr/bin/env bash
# Poll east spawn (gt_proxy probe); when green → east odom re-eval (clean_sg route 2).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
STAMP="${STAMP:-20260902_velfix}"
INTERVAL="${INTERVAL:-300}"
MAX_ROUNDS="${MAX_ROUNDS:-48}"
PROBE_OUT="/tmp/indoor_east_spawn_probe_${STAMP}.json"
LOG="logs/e2i_e3_east_spawn_watch_${STAMP}.nohup.log"
TAG=e3_odom_east_sg_velfix_050

# shellcheck disable=SC1091
source experiments/aerial/scripts/env_4090.sh
export AIRSIM_CAMERA=0 AIRSIM_VEHICLE=drone_1
ACT=experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2i_e_20260901/v4_ac_latest.pt
WM=experiments/aerial/rl/artifacts/wm_ckpt_indoor_encode_e2i_b_20260901/wm_step_400.pt
ANN=artifacts/building99_indoor_short_routes_clean_sg.json
[[ -f "$ANN" ]] || ANN="$(basename "$ANN")"

_ensure_renderer() {
  if ! pgrep -f 'Building_99/Binaries' >/dev/null || ! ss -ltn | grep -q 41451; then
    echo "[watch] recover renderer $(date -Is)" | tee -a "$LOG"
    ON_SCREEN="${ON_SCREEN:-0}" bash experiments/aerial/scripts/recover_renderer_scene.sh building99 || true
    sleep 15
  fi
  ss -ltn | grep -q 41451
}

_probe_once() {
  _ensure_renderer
  python3 - <<'PY'
import yaml
from pathlib import Path
cfg = yaml.safe_load(Path("configs/aerial_rl_indoor_shield_v3.yaml").read_text()) or {}
env = cfg.setdefault("env", {})
env["seed"] = 0
env["spawn_retry_max"] = 6
env["spawn_min_z_m"] = 1.4
env["spawn_z_bump_m"] = 0.15
env["spawn_settle_s"] = 0.50
env["spawn_hold"] = True
env["spawn_xy_nudge_m"] = 0.30
env["spawn_z_raise_m"] = 0.0
env["spawn_z_floor_cmd_m"] = 1.8
cfg.setdefault("reward", {})["success_dist_m"] = 0.50
Path("/tmp/east_spawn_probe_cfg.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
PY
  $AERIAL_PY experiments/aerial/scripts/indoor_mainline_baseline_eval.py \
    --config /tmp/east_spawn_probe_cfg.yaml \
    --actor-ckpt "$ACT" --wm-ckpt "$WM" \
    --pose-source gt_proxy --assist none \
    --annotation "$ANN" --routes 2 \
    --segment-len-m 3.0 --success-dist 0.50 --max-steps 160 \
    --out "$PROBE_OUT"
  $AERIAL_PY experiments/aerial/scripts/indoor_east_spawn_probe.py --in "$PROBE_OUT"
}

_run_odom_eval() {
  _ensure_renderer
  echo "[watch] odom east re-eval clean_sg route 2 $(date -Is)" | tee -a "$LOG"
  for SEED in 0 1 2; do
    python3 - <<PY
import yaml
from pathlib import Path
cfg = yaml.safe_load(Path("configs/aerial_rl_indoor_shield_v3.yaml").read_text()) or {}
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
Path("/tmp/east_odom_seed${SEED}.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
PY
    OUT="artifacts/indoor_e2i_${TAG}_seed${SEED}_${STAMP}.json"
    $AERIAL_PY experiments/aerial/scripts/indoor_mainline_baseline_eval.py \
      --config "/tmp/east_odom_seed${SEED}.yaml" \
      --actor-ckpt "$ACT" --wm-ckpt "$WM" \
      --pose-source odom_from_imu_rgb --assist none \
      --annotation "$ANN" --routes 2 \
      --segment-len-m 3.0 --success-dist 0.50 --max-steps 160 \
      --out "$OUT" | tee -a "$LOG"
    $AERIAL_PY experiments/aerial/scripts/indoor_fail_split_report.py \
      --in "$OUT" --out "artifacts/indoor_e2i_${TAG}_seed${SEED}_fail_split.json" | tee -a "$LOG"
  done
  GATE_MODE=cap TAG="$TAG" STAMP="$STAMP" PROTOCOL=e3_odom_east_sg_velfix \
    ANN="$ANN" ROUTES=2 \
    $AERIAL_PY experiments/aerial/scripts/indoor_e2i_f_summary.py \
    --tag "$TAG" --stamp "$STAMP" --protocol e3_odom_east_sg_velfix \
    --ann "$ANN" --routes 2 --success-dist 0.50 --gate-mode cap \
    --out "artifacts/indoor_e2i_${TAG}_summary_${STAMP}.json" | tee -a "$LOG"
}

echo "[watch] start interval=${INTERVAL}s max=$MAX_ROUNDS $(date -Is)" | tee "$LOG"
round=0
while [[ "$round" -lt "$MAX_ROUNDS" ]]; do
  round=$((round + 1))
  echo "[watch] probe $round/$MAX_ROUNDS $(date -Is)" | tee -a "$LOG"
  if _probe_once >>"$LOG" 2>&1; then
    echo "[watch] spawn GREEN $(date -Is)" | tee -a "$LOG"
    _run_odom_eval >>"$LOG" 2>&1
    echo "[watch] eval done summary=artifacts/indoor_e2i_${TAG}_summary_${STAMP}.json $(date -Is)" | tee -a "$LOG"
    exit 0
  fi
  echo "[watch] SPAWN, sleep ${INTERVAL}s" | tee -a "$LOG"
  sleep "$INTERVAL"
done
echo "[watch] max rounds exceeded" | tee -a "$LOG"
exit 1
