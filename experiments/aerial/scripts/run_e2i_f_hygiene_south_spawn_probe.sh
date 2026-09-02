#!/usr/bin/env bash
# F-hygiene — south route spawn probe (gt_proxy · clean_sg route 1 · non-gate).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
STAMP="${STAMP:-20260902}"
PROBE_OUT="/tmp/indoor_south_spawn_probe_${STAMP}.json"
OUT="artifacts/indoor_south_spawn_probe_${STAMP}.json"
LOG="logs/e2i_f_hygiene_south_spawn_probe_${STAMP}.log"

# shellcheck disable=SC1091
source experiments/aerial/scripts/env_4090.sh
export AIRSIM_CAMERA=0 AIRSIM_VEHICLE=drone_1
ACT=experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2i_e_20260901/v4_ac_latest.pt
WM=experiments/aerial/rl/artifacts/wm_ckpt_indoor_encode_e2i_b_20260901/wm_step_400.pt
ANN=artifacts/building99_indoor_short_routes_clean_sg.json
[[ -f "$ANN" ]] || ANN="$(basename "$ANN")"
mkdir -p logs artifacts

if ! pgrep -f 'Building_99/Binaries' >/dev/null || ! ss -ltn | grep -q 41451; then
  ON_SCREEN="${ON_SCREEN:-0}" bash experiments/aerial/scripts/recover_renderer_scene.sh building99 || true
  sleep 15
fi
ss -ltn | grep -q 41451

echo "[hygiene south] probe route 1 $(date -Is)" | tee "$LOG"
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
cfg.setdefault("reward", {})["success_dist_m"] = 0.50
Path("/tmp/south_spawn_probe_cfg.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
PY
$AERIAL_PY experiments/aerial/scripts/indoor_mainline_baseline_eval.py \
  --config /tmp/south_spawn_probe_cfg.yaml \
  --actor-ckpt "$ACT" --wm-ckpt "$WM" \
  --pose-source gt_proxy --assist none \
  --annotation "$ANN" --routes 1 \
  --segment-len-m 3.0 --success-dist 0.50 --max-steps 160 \
  --out "$PROBE_OUT" 2>&1 | tee -a "$LOG"
$AERIAL_PY experiments/aerial/scripts/indoor_east_spawn_probe.py --in "$PROBE_OUT" | tee -a "$LOG"
cp "$PROBE_OUT" "$OUT"
echo "[hygiene south] done out=$OUT $(date -Is)" | tee -a "$LOG"
