#!/usr/bin/env bash
# E2i.D D1 — fixture avoid demos: gt_pd_body + multi-waypoint detour paths (NOT loop_collect).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source experiments/aerial/scripts/env_4090.sh
export AIRSIM_CAMERA=0 AIRSIM_VEHICLE=drone_1
mkdir -p logs

STAMP="${STAMP:-20260901}"
OUT="${OUT:-experiments/aerial/rl/artifacts/dataset_indoor_b99_fixture_avoid_${STAMP}}"
ANN=artifacts/building99_indoor_avoid_routes.json
# avoid JSON idx: 0,1=R06 detour; 2=R02 arc; 3=R08 arc; 4=NE lateral
ROUTES="${ROUTES:-0,0,0,0,1,2,2,3,3,4}"
EPISODES="${EPISODES:-80}"
MIN_USABLE="${MIN_USABLE:-15}"
MIN_R06="${MIN_R06:-8}"
SUCCESS_DIST="${SUCCESS_DIST:-0.25}"
WP_REACH="${WP_REACH:-0.35}"
LOG=logs/e2i_d_d1_fixture_avoid_${STAMP}.log

test -f "$ANN"

if ! pgrep -f 'Building_99/Binaries' >/dev/null || ! ss -ltn | grep -q 41451; then
  bash experiments/aerial/scripts/recover_renderer_scene.sh building99 || true
  sleep 12
fi

echo "[d1] fixture avoid gt_pd_body out=$OUT routes=$ROUTES success<=${SUCCESS_DIST}m" | tee "$LOG"
set +e
$AERIAL_PY experiments/aerial/scripts/indoor_building99_fixture_collect.py \
  --annotation "$ANN" \
  --routes "$ROUTES" \
  --success-dist "$SUCCESS_DIST" --wp-reach-m "$WP_REACH" \
  --max-steps 200 --drop-collided \
  --keep-arrived-only \
  --bc-tag fixture_avoid_e2i_d \
  --protocol indoor_fixture_bc_E2i_d_avoid \
  --episodes "$EPISODES" --min-usable "$MIN_USABLE" \
  --out "$OUT" \
  2>&1 | tee -a "$LOG"
RC=$?
set -e

N=$(ls "$OUT"/episode_*.npz 2>/dev/null | wc -l | tr -d ' ')
echo "[d1] count=$N rc=$RC" | tee -a "$LOG"

if [[ "$N" -gt 0 ]]; then
  $AERIAL_PY - <<PY | tee -a "$LOG"
import json, sys
from pathlib import Path
from collections import Counter

out = Path("$OUT")
sm = json.loads((out / "collection_summary.json").read_text())
usable = [e for e in sm.get("episodes", []) if e.get("arrived_gt")]
r06 = sum(1 for e in usable if int(e.get("source_route_idx", -1)) == 5)
lat = [e.get("lateral_offset_m") for e in usable if e.get("lateral_offset_m") is not None]
print(f"[d1] usable={len(usable)} r06_source={r06} mean_lateral={sum(lat)/max(len(lat),1):.2f}m")
rc = Counter(e.get("route_name") for e in usable)
print(f"[d1] routes: {dict(rc)}")
if len(usable) < int("${MIN_USABLE}") or r06 < int("${MIN_R06}"):
    print(f"[d1] WARN gate: need usable>={int('${MIN_USABLE}')} r06>={int('${MIN_R06}')}", file=sys.stderr)
PY
fi

exit "$RC"
