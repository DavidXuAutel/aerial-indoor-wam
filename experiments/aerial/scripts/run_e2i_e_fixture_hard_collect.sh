#!/usr/bin/env bash
# E2i.E E1b — fixture hard near-field: gt_pd_body @0.20 on easy B99 routes (NOT none).
# Declared fixture; mix ≤25%. Replaces failed none@0.25 yield≈0 path.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source experiments/aerial/scripts/env_4090.sh
export AIRSIM_CAMERA=0 AIRSIM_VEHICLE=drone_1
mkdir -p logs

STAMP="${STAMP:-20260901}"
OUT="${OUT:-experiments/aerial/rl/artifacts/dataset_indoor_b99_fixture_hard_e_${STAMP}}"
ANN=artifacts/building99_indoor_short_routes.json
# Easy lobby: R04 south=3, R05 diag_ne=4, R07 east_from1=6, R03 west=2, R08 north_from1=7; skip R01=0 SPAWN
ROUTES="${ROUTES:-3,3,4,4,4,6,6,6,2,7}"
EPISODES="${EPISODES:-80}"
MIN_USABLE="${MIN_USABLE:-40}"
SUCCESS_DIST="${SUCCESS_DIST:-0.20}"
LOG=logs/e2i_e_e1b_fixture_hard_${STAMP}.log

test -f "$ANN"

if ! pgrep -f 'Building_99/Binaries' >/dev/null || ! ss -ltn | grep -q 41451; then
  bash experiments/aerial/scripts/recover_renderer_scene.sh building99 || true
  sleep 12
fi

echo "[e1b] fixture hard gt_pd_body out=$OUT routes=$ROUTES success<=${SUCCESS_DIST}m" | tee "$LOG"
set +e
$AERIAL_PY experiments/aerial/scripts/indoor_building99_fixture_collect.py \
  --annotation "$ANN" \
  --routes "$ROUTES" \
  --success-dist "$SUCCESS_DIST" \
  --segment-len-m 3.0 --max-steps 160 \
  --drop-collided --keep-arrived-only \
  --bc-tag fixture_hard_e2i_e \
  --protocol indoor_fixture_bc_E2i_e_hard020 \
  --episodes "$EPISODES" --min-usable "$MIN_USABLE" \
  --out "$OUT" \
  2>&1 | tee -a "$LOG"
RC=$?
set -e

N=$(ls "$OUT"/episode_*.npz 2>/dev/null | wc -l | tr -d ' ')
echo "[e1b] count=$N rc=$RC" | tee -a "$LOG"

if [[ "$N" -gt 0 ]]; then
  $AERIAL_PY - <<PY | tee -a "$LOG"
import json
from pathlib import Path
from collections import Counter
out = Path("$OUT")
sm = json.loads((out / "collection_summary.json").read_text())
eps = [e for e in sm.get("episodes") or [] if e.get("arrived_gt")]
dens = [float(e["d_end_m_gt"]) for e in eps]
n20 = sum(1 for x in dens if x <= 0.20)
print(f"[e1b] usable={len(eps)} mean_d={sum(dens)/max(len(dens),1):.3f} all_le_0.20={n20}")
print(f"[e1b] routes: {dict(Counter(e.get('route_name') for e in eps))}")
PY
fi

exit "$RC"
