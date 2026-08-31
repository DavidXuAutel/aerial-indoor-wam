#!/usr/bin/env bash
# E2h.2 continue round 3 — tuned hallway/F2/stair routes
set -euo pipefail
ROOT="${AERIAL_INDOOR_ROOT:-/home/yao/aerial-indoor-wam}"
cd "$ROOT"
# shellcheck disable=SC1091
source experiments/aerial/scripts/env_4090.sh
export AIRSIM_CAMERA=0 AIRSIM_VEHICLE=drone_1

OUT="${1:-experiments/aerial/rl/artifacts/dataset_indoor_building99_e2h_20260830}"
ANN="${2:-artifacts/building99_indoor_routes_ext2.json}"
EP="${3:-96}"
LOG="logs/indoor_e2h_b99_continue_r3_$(date +%Y%m%d_%H%M%S).log"
mkdir -p logs

PRIOR=$(ls "$OUT"/episode_*.npz 2>/dev/null | wc -l)
echo "[E2h.2+r3] prior=$PRIOR episodes=$EP ann=$ANN"

pkill -f 'wam_phase2_traj_forensics.py' 2>/dev/null || true
if ! pgrep -f 'Building_99/Binaries' >/dev/null || ! ss -ltn | grep -q 41451; then
  bash experiments/aerial/scripts/recover_renderer_scene.sh building99
  sleep 12
fi

START=$(date +%s)
$AERIAL_PY experiments/aerial/scripts/indoor_building99_fixture_collect.py \
  --annotation "$ANN" \
  --out "$OUT" \
  --append \
  --episodes "$EP" \
  --segment-len-m 3.0 \
  --success-dist 0.50 \
  --max-steps 140 \
  --min-usable 1 \
  --min-usable-new 12 \
  --keep-arrived-only \
  2>&1 | tee "$LOG"
END=$(date +%s)
ELAPSED=$((END - START))

echo "[E2h.2+r3] done elapsed_sec=$ELAPSED"
python3 - <<PY
import json
from pathlib import Path
from collections import Counter
p = Path("$OUT") / "collection_summary.json"
d = json.loads(p.read_text())
print("total_usable", d.get("n_usable"), "new_usable", d.get("n_usable_this_run"))
print("near_depth", d.get("near_depth_frac"), "depth_med", d.get("depth_min_median_mean"))
print("elapsed_sec", $ELAPSED)
segs = Counter(e.get("segment_name") for e in d.get("episodes") or [])
print("unique_segments", len(segs))
for name, cnt in sorted(segs.items(), key=lambda x: -x[1]):
    if "tv_hall" in name or "cabinet" in name or "floor2" in name or "stair" in name:
        print(" ", cnt, name)
PY
