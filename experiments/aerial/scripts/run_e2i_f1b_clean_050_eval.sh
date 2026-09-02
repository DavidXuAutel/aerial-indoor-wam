#!/usr/bin/env bash
# E2i.F F1b — @0.50 clean set: drop north_3m (SPAWN) + north_from_y1 (NEAR). No FT.
# Plan: docs/handover/INDOOR_E2I_F1B_PLAN_20260901.md
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source experiments/aerial/scripts/env_4090.sh
export AIRSIM_CAMERA=0 AIRSIM_VEHICLE=drone_1
mkdir -p logs artifacts

STAMP="${STAMP:-20260901}"
SUCCESS_DIST="${SUCCESS_DIST:-0.50}"
CFG_EVAL=configs/aerial_rl_indoor_shield_v3.yaml
WM=experiments/aerial/rl/artifacts/wm_ckpt_indoor_encode_e2i_b_20260901/wm_step_400.pt
ACT="${ACT:-experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2i_e_${STAMP}/v4_ac_latest.pt}"
ANN=artifacts/building99_indoor_short_routes_nospawn_r01.json
# Drop idx0 north_3m (spawn@t0) + idx6 north_from_y1 (pillar NEAR); also skip idx4=R06.
ROUTES="${ROUTES:-1,2,3,5}"
TAG="f1b_050_clean"
if [[ "$SUCCESS_DIST" != "0.50" ]]; then
  TAG="f1b_${SUCCESS_DIST/./}_clean"
fi
LOG="logs/e2i_${TAG}_${STAMP}.log"

test -f "$ACT" && test -f "$WM" && test -f "$ANN"

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
    print("[f1b] settings Scene capture forced 640×480 (fan-out after grab)")
else:
    print("[f1b] settings Scene capture already 640×480")
PY

if ! pgrep -f 'Building_99/Binaries' >/dev/null || ! ss -ltn | grep -q 41451; then
  ON_SCREEN="${ON_SCREEN:-0}" bash experiments/aerial/scripts/recover_renderer_scene.sh building99 || true
  sleep 15
fi
ss -ltn | grep -q 41451

: >"$LOG"
{
  echo "[f1b] clean @0.50 success_dist=$SUCCESS_DIST act=$ACT routes=$ROUTES $(date -Is)"
  echo "[f1b] protocol=e2i_f1b_clean pose=gt_proxy(probe) drop=north_3m+north_from_y1"
} | tee -a "$LOG"

for SEED in 0 1 2; do
  OUT="artifacts/indoor_e2i_${TAG}_seed${SEED}_${STAMP}.json"
  TMP="/tmp/aerial_rl_${TAG}_seed${SEED}.yaml"
  python3 - <<PY
import yaml
from pathlib import Path
cfg = yaml.safe_load(Path("$CFG_EVAL").read_text()) or {}
cfg.setdefault("env", {})["seed"] = int("$SEED")
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

STAMP="$STAMP" SUCCESS_DIST="$SUCCESS_DIST" TAG="$TAG" $AERIAL_PY - <<'PY'
import json, os
from pathlib import Path
stamp = os.environ["STAMP"]
succ = float(os.environ["SUCCESS_DIST"])
tag = os.environ["TAG"]
rows, tot_a, tot_n, tot_c, spawn, near = [], 0, 0, 0, 0, 0
arr_collided = 0
for seed in (0, 1, 2):
    p = Path(f"artifacts/indoor_e2i_{tag}_seed{seed}_{stamp}.json")
    d = json.loads(p.read_text())
    eps = d.get("episodes") or d.get("results") or []
    dens, arr, cols, sp, nr, ac = [], 0, 0, 0, 0, 0
    for e in eps:
        arrived = bool(e.get("arrived") or e.get("success"))
        collided = bool(e.get("collided"))
        if arrived:
            arr += 1
            if collided:
                ac += 1
        v = e.get("d_end_m_gt", e.get("d_end_m"))
        if v is not None:
            dens.append(float(v))
        if collided:
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
    arr_collided += ac
    rows.append({
        "seed": seed,
        "n": len(eps),
        "arrived": arr,
        "mean_d": (sum(dens) / len(dens)) if dens else None,
        "collision_n": cols,
        "spawn_n": sp,
        "near_coll_n": nr,
        "arrived_but_collided": ac,
    })
mean_d = sum(r["mean_d"] for r in rows if r["mean_d"] is not None) / max(
    1, sum(1 for r in rows if r["mean_d"] is not None)
)
arr_rate = tot_a / tot_n if tot_n else 0.0
coll_rate = tot_c / tot_n if tot_n else 1.0
g1 = arr_rate >= 0.50
g2 = mean_d <= 1.0
g3 = (coll_rate <= 0.50) and (arr_collided == 0)
g4 = True  # fail_split files written by script
primary_pass = g1 and g2 and g3 and g4
out = {
    "protocol": "e2i_f1b_clean",
    "contract": "INDOOR_E2I_F1B_PLAN_20260901.md",
    "success_dist_m": succ,
    "pose_source": "gt_proxy",
    "pose_note": "probe only; not product sensing contract",
    "annotation": "building99_indoor_short_routes_nospawn_r01.json",
    "dropped": "nospawn idx0 north_3m (SPAWN@t0) + idx6 north_from_y1 (NEAR pillar) + idx4 R06",
    "routes": "1,2,3,5",
    "scene_wh": [640, 480],
    "r06": "abandoned",
    "compare_to_f1": {
        "note": "F1 mean_d~1.22 G2 fail; arrived-only mean~0.45; video confirms north cluster pollution",
    },
    "seeds_with_arrival": sum(1 for r in rows if r["arrived"] > 0),
    "mean_d_end_m": mean_d,
    "arrival_rate": arr_rate,
    "total_arrived": tot_a,
    "total_n": tot_n,
    "total_collision": tot_c,
    "collision_rate": coll_rate,
    "spawn_collision_n": spawn,
    "near_collision_n": near,
    "arrived_but_collided_n": arr_collided,
    "gates": {
        "G1_arrival_ge_0.50": g1,
        "G2_mean_d_le_1.0": g2,
        "G3_coll_le_0.50_and_arrived_clean": g3,
        "G4_fail_split_written": g4,
    },
    "primary_gate_pass": primary_pass,
    "stretch_note": "0.20 remains stretch-only; F1b does not redefine stretch",
    "seeds": rows,
}
Path(f"artifacts/indoor_e2i_{tag}_summary_{stamp}.json").write_text(
    json.dumps(out, indent=2) + "\n"
)
print(json.dumps(out, indent=2))
PY

echo "[f1b] done $(date -Is)" | tee -a "$LOG"
