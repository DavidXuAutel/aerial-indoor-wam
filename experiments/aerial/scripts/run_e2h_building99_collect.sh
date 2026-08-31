#!/usr/bin/env bash
# E2h.2 — Building_99 body-PD fixture NPZ collect (near-obstacle corpus)
set -euo pipefail
ROOT="${AERIAL_INDOOR_ROOT:-/home/yao/aerial-indoor-wam}"
cd "$ROOT"
# shellcheck disable=SC1091
source experiments/aerial/scripts/env_4090.sh

export AIRSIM_CAMERA=0 AIRSIM_VEHICLE=drone_1

# Restart scene only if port down; else reuse.
if ! ss -ltn | grep -q 41451; then
  bash experiments/aerial/scripts/recover_renderer_scene.sh building99
  sleep 12
fi
# Confirm Building_99 binary is the listener owner
if ! pgrep -f 'Building_99/Binaries' >/dev/null; then
  bash experiments/aerial/scripts/recover_renderer_scene.sh building99
  sleep 12
fi

OUT="${1:-experiments/aerial/rl/artifacts/dataset_indoor_building99_e2h_20260830}"
LOG="logs/indoor_e2h_b99_fixture_$(date +%Y%m%d_%H%M%S).log"
mkdir -p logs
rm -rf "$OUT"
mkdir -p "$OUT"

ANN=artifacts/building99_indoor_short_routes.json
test -f "$ANN"

echo "[E2h.2] Building_99 body-PD fixture -> $OUT"
$AERIAL_PY experiments/aerial/scripts/indoor_building99_fixture_collect.py \
  --annotation "$ANN" \
  --out "$OUT" \
  --episodes 40 \
  --segment-len-m 3.0 \
  --success-dist 0.50 \
  --max-steps 120 \
  --min-usable 10 \
  --keep-arrived-only \
  2>&1 | tee "$LOG"

echo "[E2h.2] done"
python3 - <<PY
import json
from pathlib import Path
p = Path("$OUT") / "collection_summary.json"
d = json.loads(p.read_text())
print("n_collected", d.get("n_collected"), "n_usable", d.get("n_usable"))
print("arrival_rate_gt", d.get("arrival_rate_gt"), "mean_d_end_gt", d.get("mean_d_end_gt"))
print("near_depth_frac", d.get("near_depth_frac"), "depth_med_mean", d.get("depth_min_median_mean"))
PY
