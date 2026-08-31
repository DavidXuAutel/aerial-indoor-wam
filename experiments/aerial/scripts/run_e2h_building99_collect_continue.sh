#!/usr/bin/env bash
# E2h.2 continue — append hallway/stair/upper-floor legs to existing B99 fixture corpus
set -euo pipefail
ROOT="${AERIAL_INDOOR_ROOT:-/home/yao/aerial-indoor-wam}"
cd "$ROOT"
# shellcheck disable=SC1091
source experiments/aerial/scripts/env_4090.sh

export AIRSIM_CAMERA=0 AIRSIM_VEHICLE=drone_1

OUT="${1:-experiments/aerial/rl/artifacts/dataset_indoor_building99_e2h_20260830}"
ANN="${2:-artifacts/building99_indoor_routes_ext.json}"
LOG="logs/indoor_e2h_b99_continue_$(date +%Y%m%d_%H%M%S).log"
mkdir -p logs

test -f "$ANN"
PRIOR=$(ls "$OUT"/episode_*.npz 2>/dev/null | wc -l)
echo "[E2h.2+] prior_npz=$PRIOR append -> $OUT ann=$ANN"

pkill -f 'wam_phase2_traj_forensics.py' 2>/dev/null || true
if ! pgrep -f 'Building_99/Binaries' >/dev/null || ! ss -ltn | grep -q 41451; then
  bash experiments/aerial/scripts/recover_renderer_scene.sh building99
  sleep 12
fi

$AERIAL_PY experiments/aerial/scripts/indoor_building99_fixture_collect.py \
  --annotation "$ANN" \
  --out "$OUT" \
  --append \
  --episodes 72 \
  --segment-len-m 3.0 \
  --success-dist 0.50 \
  --max-steps 140 \
  --min-usable 1 \
  --min-usable-new 12 \
  --keep-arrived-only \
  2>&1 | tee "$LOG"

echo "[E2h.2+] done"
python3 - <<PY
import json
from pathlib import Path
from collections import Counter
p = Path("$OUT") / "collection_summary.json"
d = json.loads(p.read_text())
print("total n_usable", d.get("n_usable"), "n_collected", d.get("n_collected"))
print("this_run new", d.get("n_usable_this_run"), "/", d.get("n_collected_this_run"))
print("near_depth_frac", d.get("near_depth_frac"), "depth_med_mean", d.get("depth_min_median_mean"))
segs = Counter(e.get("segment_name") for e in d.get("episodes") or [])
print("unique_segments", len(segs))
for name, cnt in sorted(segs.items(), key=lambda x: -x[1])[:20]:
    print(f"  {cnt:2d} {name}")
PY
