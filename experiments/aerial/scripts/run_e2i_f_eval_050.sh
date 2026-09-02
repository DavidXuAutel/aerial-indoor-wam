#!/usr/bin/env bash
# Shared E2i.F @0.50 eval driver (spawn-retry enabled). Set TAG, ROUTES, ANN, STAMP.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source experiments/aerial/scripts/env_4090.sh
export AIRSIM_CAMERA=0 AIRSIM_VEHICLE=drone_1
mkdir -p logs artifacts

STAMP="${STAMP:-20260902}"
SUCCESS_DIST="${SUCCESS_DIST:-0.50}"
TAG="${TAG:?set TAG}"
ROUTES="${ROUTES:-}"
ANN="${ANN:-artifacts/building99_indoor_short_routes_clean_sg.json}"
if [[ ! -f "$ANN" ]]; then
  fb="$(basename "$ANN")"
  [[ -f "$fb" ]] && ANN="$fb" || ANN="building99_indoor_short_routes_clean_sg.json"
fi
CFG_EVAL=configs/aerial_rl_indoor_shield_v3.yaml
WM=experiments/aerial/rl/artifacts/wm_ckpt_indoor_encode_e2i_b_20260901/wm_step_400.pt
ACT="${ACT:-experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2i_e_20260901/v4_ac_latest.pt}"
LOG="logs/e2i_${TAG}_${STAMP}.log"
PROTOCOL="${PROTOCOL:-e2i_f_eval}"

test -f "$ACT" && test -f "$WM" && test -f "$ANN"

if [[ -z "$ROUTES" ]]; then
  ROUTES="$($AERIAL_PY - <<PY
import json
from pathlib import Path
n=len(json.loads(Path("$ANN").read_text()))
print(",".join(str(i) for i in range(n)))
PY
)"
fi

python3 - <<'PY'
import json
from pathlib import Path
p = Path("/home/yao/aerial_airsim_persistent/AirSim/settings_indoor.json")
if not p.is_file():
    raise SystemExit("missing settings_indoor.json")
d = json.loads(p.read_text())
changed = False

def fix(caps):
    global changed
    for c in caps:
        if int(c.get("ImageType", -1)) == 0:
            # Single-cam capture 640×480; fan-out after grab → WAM 224 / VIO / YOLO.
            if c.get("Width") != 640 or c.get("Height") != 480:
                c["Width"] = 640
                c["Height"] = 480
                changed = True

fix(d["CameraDefaults"]["CaptureSettings"])
for cam in d["Vehicles"]["drone_1"]["Cameras"].values():
    fix(cam["CaptureSettings"])
if changed:
    p.write_text(json.dumps(d, indent=2) + "\n")
    print("[f_eval] settings Scene capture forced 640×480 (fan-out after grab)")
PY

if ! pgrep -f 'Building_99/Binaries' >/dev/null || ! ss -ltn | grep -q 41451; then
  ON_SCREEN="${ON_SCREEN:-0}" bash experiments/aerial/scripts/recover_renderer_scene.sh building99 || true
  sleep 15
fi
ss -ltn | grep -q 41451

: >"$LOG"
{
  echo "[$TAG] @0.50 act=$ACT routes=$ROUTES ann=$ANN spawn_retry=6 hold=1 $(date -Is)"
} | tee -a "$LOG"

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
cfg.setdefault("reward", {})["success_dist_m"] = float("$SUCCESS_DIST")
Path("$TMP").write_text(yaml.safe_dump(cfg, sort_keys=False))
PY
  $AERIAL_PY experiments/aerial/scripts/indoor_mainline_baseline_eval.py \
    --config "$TMP" \
    --actor-ckpt "$ACT" \
    --wm-ckpt "$WM" \
    --pose-source gt_proxy --assist none \
    --annotation "$ANN" --routes "$ROUTES" \
    --segment-len-m 3.0 --success-dist "$SUCCESS_DIST" --max-steps 160 \
    --out "$OUT" \
    2>&1 | tee -a "$LOG"
  $AERIAL_PY experiments/aerial/scripts/indoor_fail_split_report.py \
    --in "$OUT" \
    --out "artifacts/indoor_e2i_${TAG}_seed${SEED}_fail_split.json" \
    2>&1 | tee -a "$LOG"
done

STAMP="$STAMP" SUCCESS_DIST="$SUCCESS_DIST" TAG="$TAG" ROUTES="$ROUTES" ANN="$ANN" PROTOCOL="$PROTOCOL" GATE_MODE="${GATE_MODE:-cap}" $AERIAL_PY experiments/aerial/scripts/indoor_e2i_f_summary.py \
  --tag "$TAG" --stamp "$STAMP" --protocol "$PROTOCOL" --ann "$ANN" --routes "$ROUTES" \
  --success-dist "$SUCCESS_DIST" --gate-mode "$GATE_MODE" \
  --out "artifacts/indoor_e2i_${TAG}_summary_${STAMP}.json" \
  2>&1 | tee -a "$LOG"

echo "[$TAG] done $(date -Is)" | tee -a "$LOG"
