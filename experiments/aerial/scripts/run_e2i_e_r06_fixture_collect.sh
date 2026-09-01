#!/usr/bin/env bash
# E2i.E E2 — R06 fixture avoid: gt_pd_body multi-waypoint detours (NOT straight BC).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source experiments/aerial/scripts/env_4090.sh
export AIRSIM_CAMERA=0 AIRSIM_VEHICLE=drone_1
mkdir -p logs

STAMP="${STAMP:-20260901}"
OUT="${OUT:-experiments/aerial/rl/artifacts/dataset_indoor_b99_fixture_r06_e_${STAMP}}"
ANN=artifacts/building99_indoor_r06_avoid_routes.json
# all 5 R06 detour variants, overweight ones that may work
ROUTES="${ROUTES:-0,0,1,1,1,2,2,2,3,3,4,4}"
EPISODES="${EPISODES:-60}"
MIN_USABLE="${MIN_USABLE:-8}"
SUCCESS_DIST="${SUCCESS_DIST:-0.25}"
WP_REACH="${WP_REACH:-0.40}"
LOG=logs/e2i_e_e2_r06_fixture_${STAMP}.log

test -f "$ANN"

if ! pgrep -f 'Building_99/Binaries' >/dev/null || ! ss -ltn | grep -q 41451; then
  bash experiments/aerial/scripts/recover_renderer_scene.sh building99 || true
  sleep 12
fi

echo "[e2] R06 fixture avoid out=$OUT routes=$ROUTES success<=${SUCCESS_DIST}m" | tee "$LOG"
set +e
$AERIAL_PY experiments/aerial/scripts/indoor_building99_fixture_collect.py \
  --annotation "$ANN" \
  --routes "$ROUTES" \
  --success-dist "$SUCCESS_DIST" --wp-reach-m "$WP_REACH" \
  --max-steps 240 --drop-collided \
  --keep-arrived-only \
  --bc-tag fixture_r06_avoid_e2i_e \
  --protocol indoor_fixture_bc_E2i_e_r06 \
  --episodes "$EPISODES" --min-usable "$MIN_USABLE" \
  --out "$OUT" \
  2>&1 | tee -a "$LOG"
RC=$?
set -e

N=$(ls "$OUT"/episode_*.npz 2>/dev/null | wc -l | tr -d ' ')
echo "[e2] count=$N rc=$RC" | tee -a "$LOG"

if [[ "$N" -gt 0 ]]; then
  $AERIAL_PY - <<PY | tee -a "$LOG"
import json
from pathlib import Path
from collections import Counter
out = Path("$OUT")
sm = json.loads((out / "collection_summary.json").read_text())
eps = [e for e in sm.get("episodes") or [] if e.get("arrived_gt")]
r06 = sum(1 for e in eps if int(e.get("source_route_idx", -1)) == 5)
lats = [e.get("lateral_offset_m") for e in eps if e.get("lateral_offset_m") is not None]
print(f"[e2] usable={len(eps)} r06_source={r06} mean_lateral={sum(lats)/max(len(lats),1):.2f}")
print(f"[e2] routes: {dict(Counter(e.get('route_name') for e in eps))}")
PY
fi

exit "$RC"
