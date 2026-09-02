#!/usr/bin/env bash
# Indoor closed-loop smoke with pose_source=vio_est (live OpenVINS stream).
#
# NOT F-cap / E3-cap. Default uses AERIAL_VIO_GT_SEED=1 (sim probe) because
# AirSim auto-init still fails (P1b). Reports must declare vio_gt_seed.
#
# Usage (125, AirSim idle on :41451):
#   bash experiments/aerial/scripts/run_indoor_vio_closed_smoke.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source experiments/aerial/scripts/env_4090.sh
export AIRSIM_CAMERA=0 AIRSIM_VEHICLE=drone_1
export AIRSIM_FANOUT_RGB=1
export INDOOR_CAPTURE_W="${INDOOR_CAPTURE_W:-640}"
export INDOOR_CAPTURE_H="${INDOOR_CAPTURE_H:-480}"
export AERIAL_VIO_LIVE=1
export AERIAL_VIO_GT_SEED="${AERIAL_VIO_GT_SEED:-1}"

mkdir -p logs artifacts
STAMP="${STAMP:-$(date +%Y%m%d_%H%M%S)}"
TAG="${TAG:-vio_closed_smoke}"
SUCCESS_DIST="${SUCCESS_DIST:-0.50}"
ANN="${ANN:-artifacts/building99_indoor_short_routes_clean_sg.json}"
if [[ ! -f "$ANN" ]]; then
  fb="$(basename "$ANN")"
  [[ -f "$fb" ]] && ANN="$fb" || ANN="building99_indoor_short_routes_clean_sg.json"
fi
# east_from_1 only if present; else route 0
ROUTES="${ROUTES:-}"
CFG_EVAL=configs/aerial_rl_indoor_shield_v3.yaml
WM=experiments/aerial/rl/artifacts/wm_ckpt_indoor_encode_e2i_b_20260901/wm_step_400.pt
ACT="${ACT:-experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2i_e_20260901/v4_ac_latest.pt}"
LOG="logs/indoor_${TAG}_${STAMP}.log"
OUT="artifacts/indoor_${TAG}_${STAMP}.json"

test -f "$ACT" && test -f "$WM" && test -f "$ANN"

# Prefer stream binary next to offline runner
if [[ -z "${OPENVINS_STREAM_BIN:-}" ]]; then
  if [[ -x experiments/aerial/vio_probe/cpp/build/ov_stream_online ]]; then
    export OPENVINS_STREAM_BIN="$ROOT/experiments/aerial/vio_probe/cpp/build/ov_stream_online"
  elif [[ -f "${HOME}/src/open_vins/OPENVINS_BIN.env" ]]; then
    # shellcheck disable=SC1090
    source "${HOME}/src/open_vins/OPENVINS_BIN.env"
    if [[ -n "${OPENVINS_BIN:-}" ]]; then
      sib="$(dirname "$OPENVINS_BIN")/ov_stream_online"
      [[ -x "$sib" ]] && export OPENVINS_STREAM_BIN="$sib"
    fi
  fi
fi
test -x "${OPENVINS_STREAM_BIN:?set OPENVINS_STREAM_BIN}"

# Ensure single-cam capture 640×480 (fan-out after grab)
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
            if c.get("Width") != 640 or c.get("Height") != 480:
                c["Width"] = 640
                c["Height"] = 480
                changed = True
fix(d["CameraDefaults"]["CaptureSettings"])
for cam in d["Vehicles"]["drone_1"]["Cameras"].values():
    fix(cam["CaptureSettings"])
# drop mistaken dual-cam front_vio if present
cams = d["Vehicles"]["drone_1"]["Cameras"]
if "front_vio" in cams:
    del cams["front_vio"]
    changed = True
if changed:
    p.write_text(json.dumps(d, indent=2) + "\n")
    print("[vio_closed] settings capture→640×480 (restart AirSim if just changed)")
else:
    print("[vio_closed] settings capture already 640×480")
PY

if [[ -z "$ROUTES" ]]; then
  ROUTES="$($AERIAL_PY - <<PY
import json
from pathlib import Path
ann=json.loads(Path("$ANN").read_text())
idx=None
for i,r in enumerate(ann):
    blob=" ".join(str(r.get(k) or "") for k in ("trajectory_id","route_name","name","id","gpt_instruction"))
    if "east" in blob.lower():
        idx=i; break
print(idx if idx is not None else 0)
PY
)"
fi

ss -ltn | grep -q 41451 || {
  echo "[vio_closed] AirSim :41451 not listening" >&2
  exit 3
}

: >"$LOG"
{
  echo "[$TAG] pose_source=vio_est live gt_seed=$AERIAL_VIO_GT_SEED routes=$ROUTES $(date -Is)"
} | tee -a "$LOG"

TMP="/tmp/aerial_rl_${TAG}.yaml"
$AERIAL_PY - <<PY
import yaml
from pathlib import Path
cfg = yaml.safe_load(Path("$CFG_EVAL").read_text()) or {}
env = cfg.setdefault("env", {})
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
  --pose-source vio_est --assist none \
  --annotation "$ANN" --routes "$ROUTES" \
  --segment-len-m 3.0 --success-dist "$SUCCESS_DIST" --max-steps 80 \
  --out "$OUT" \
  2>&1 | tee -a "$LOG"

$AERIAL_PY - <<PY
import json
from pathlib import Path
p=Path("$OUT")
d=json.loads(p.read_text()) if p.is_file() else {}
print(json.dumps({
  "out": str(p),
  "pose_source": d.get("pose_source"),
  "n": len(d.get("episodes") or d.get("results") or []),
  "keys": sorted(d.keys())[:20],
}, indent=2))
PY

echo "[vio_closed] done out=$OUT log=$LOG"
echo "[vio_closed] NOTE: gt_seed=$AERIAL_VIO_GT_SEED — not product VIO; not F-cap."
