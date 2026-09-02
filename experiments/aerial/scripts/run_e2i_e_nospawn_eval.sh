#!/usr/bin/env bash
# E2i.E E4b — SPAWN diagnosis: @0.20 eval on nospawn set (drop R01 + drop R06).
# Uses E4 ckpt; Scene capture 640×480; fan-out → WAM 224. No FT.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source experiments/aerial/scripts/env_4090.sh
export AIRSIM_CAMERA=0 AIRSIM_VEHICLE=drone_1
mkdir -p logs artifacts

STAMP="${STAMP:-20260901}"
CFG_EVAL=configs/aerial_rl_indoor_shield_v3.yaml
WM=experiments/aerial/rl/artifacts/wm_ckpt_indoor_encode_e2i_b_20260901/wm_step_400.pt
ACT=experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2i_e_${STAMP}/v4_ac_latest.pt
# Drop classic R01; also drop R06 (abandoned) from the filtered file.
ANN=artifacts/building99_indoor_short_routes_nospawn_r01.json
# nospawn file order = original idx 1..7 → local 0..6; original R06=idx5 → local idx4 → skip
ROUTES="${ROUTES:-0,1,2,3,5,6}"
LOG=logs/e2i_e_e4b_nospawn_020_${STAMP}.log

test -f "$ACT" && test -f "$WM" && test -f "$ANN"

# Ensure indoor Scene capture 640×480
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
    print("[e4b] settings Scene capture forced 640×480 (fan-out after grab)")
else:
    print("[e4b] settings Scene capture already 640×480")
PY

if ! pgrep -f 'Building_99/Binaries' >/dev/null || ! ss -ltn | grep -q 41451; then
  ON_SCREEN="${ON_SCREEN:-0}" bash experiments/aerial/scripts/recover_renderer_scene.sh building99 || true
  sleep 15
fi
ss -ltn | grep -q 41451

: >"$LOG"
{
  echo "[e4b] nospawn @0.20 act=$ACT routes=$ROUTES (no R01, no R06) $(date -Is)"
} | tee -a "$LOG"

for SEED in 0 1 2; do
  OUT="artifacts/indoor_e2i_e_020_nospawn_seed${SEED}_${STAMP}.json"
  TMP="/tmp/aerial_rl_e_020_nospawn_seed${SEED}.yaml"
  python3 - <<PY
import yaml
from pathlib import Path
cfg = yaml.safe_load(Path("$CFG_EVAL").read_text()) or {}
cfg.setdefault("env", {})["seed"] = int("$SEED")
cfg.setdefault("reward", {})["success_dist_m"] = 0.20
Path("$TMP").write_text(yaml.safe_dump(cfg, sort_keys=False))
PY
  $AERIAL_PY experiments/aerial/scripts/indoor_mainline_baseline_eval.py \
    --config "$TMP" \
    --actor-ckpt "$ACT" \
    --wm-ckpt "$WM" \
    --pose-source gt_proxy --assist none \
    --annotation "$ANN" --routes "$ROUTES" \
    --segment-len-m 3.0 --success-dist 0.20 --max-steps 160 \
    --out "$OUT" \
    2>&1 | tee -a "$LOG"
  $AERIAL_PY experiments/aerial/scripts/indoor_fail_split_report.py \
    --in "$OUT" \
    --out "artifacts/indoor_e2i_e_020_nospawn_seed${SEED}_fail_split.json" \
    2>&1 | tee -a "$LOG"
done

STAMP="$STAMP" $AERIAL_PY - <<'PY'
import json, os
from pathlib import Path
stamp = os.environ["STAMP"]
rows, tot_a, tot_n, tot_c, spawn, near = [], 0, 0, 0, 0, 0
for seed in (0, 1, 2):
    p = Path(f"artifacts/indoor_e2i_e_020_nospawn_seed{seed}_{stamp}.json")
    d = json.loads(p.read_text())
    eps = d.get("episodes") or d.get("results") or []
    dens, arr, cols, sp, nr = [], 0, 0, 0, 0
    for e in eps:
        if e.get("arrived") or e.get("success"):
            arr += 1
        v = e.get("d_end_m_gt", e.get("d_end_m"))
        if v is not None:
            dens.append(float(v))
        if e.get("collided"):
            cols += 1
            st = int(e.get("steps") or 0)
            if st <= 8:
                sp += 1
            else:
                nr += 1
    tot_a += arr
    tot_n += len(eps)
    tot_c += cols
    spawn += sp
    near += nr
    rows.append({
        "seed": seed,
        "n": len(eps),
        "arrived": arr,
        "mean_d": (sum(dens) / len(dens)) if dens else None,
        "collision_n": cols,
        "spawn_n": sp,
        "near_coll_n": nr,
    })
mean_d = sum(r["mean_d"] for r in rows if r["mean_d"] is not None) / max(
    1, sum(1 for r in rows if r["mean_d"] is not None)
)
arr_rate = tot_a / tot_n if tot_n else 0.0
out = {
    "protocol": "e2i_e_020_nospawn",
    "annotation": "building99_indoor_short_routes_nospawn_r01.json",
    "dropped": "R01 + R06",
    "routes": "0,1,2,3,5,6",
    "scene_wh": [640, 480],
    "r06": "abandoned",
    "seeds_with_arrival": sum(1 for r in rows if r["arrived"] > 0),
    "mean_d_end_m": mean_d,
    "arrival_rate": arr_rate,
    "total_arrived": tot_a,
    "total_n": tot_n,
    "total_collision": tot_c,
    "spawn_collision_n": spawn,
    "near_collision_n": near,
    "quality_gate_pass": (mean_d <= 0.8) or (arr_rate >= 0.25),
    "quality_rule": "mean_d<=0.8 OR arrival_rate>=0.25",
    "compare_to_e4_full8": {
        "note": "E4 full8 was 0/24 arr mean_d~3.50 SPAWN~23",
    },
    "seeds": rows,
}
Path(f"artifacts/indoor_e2i_e_020_nospawn_summary_{stamp}.json").write_text(
    json.dumps(out, indent=2) + "\n"
)
print(json.dumps(out, indent=2))
PY

echo "[e4b] done $(date -Is)" | tee -a "$LOG"
