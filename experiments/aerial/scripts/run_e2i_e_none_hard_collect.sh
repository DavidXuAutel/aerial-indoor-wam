#!/usr/bin/env bash
# E2i.E E1 — assist=none hard near-field (d_end<=0.25, no collide); overweight ARRIVE routes.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source experiments/aerial/scripts/env_4090.sh
export AIRSIM_CAMERA=0 AIRSIM_VEHICLE=drone_1
mkdir -p logs

STAMP="${STAMP:-20260901}"
OUT="${OUT:-experiments/aerial/rl/artifacts/dataset_indoor_b99_none_hard_e_${STAMP}}"
ACTOR="${ACTOR:-experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2i_b_20260901/v4_ac_latest.pt}"
ANN=artifacts/building99_indoor_short_routes.json
# overweight R04=3, R05=4, R07=6; light R03=2; skip R01=0,R02=1,R06=5,R08=7
ROUTES="${ROUTES:-3,3,3,4,4,4,4,6,6,6,2}"
EPISODES="${EPISODES:-300}"
MIN_USABLE="${MIN_USABLE:-40}"
NEAR_M="${NEAR_M:-0.25}"
LOG=logs/e2i_e_e1_none_hard_${STAMP}.log

test -f "$ACTOR"
test -f "$ANN"

if ! pgrep -f 'Building_99/Binaries' >/dev/null || ! ss -ltn | grep -q 41451; then
  bash experiments/aerial/scripts/recover_renderer_scene.sh building99 || true
  sleep 12
fi

echo "[e1] none hard out=$OUT routes=$ROUTES near<=${NEAR_M}m episodes=$EPISODES" | tee "$LOG"
set +e
$AERIAL_PY experiments/aerial/scripts/indoor_loop_collect.py \
  --config configs/aerial_rl_indoor_shield_v3.yaml \
  --annotation "$ANN" \
  --routes "$ROUTES" \
  --pose-source gt_proxy --assist none \
  --segment-len-m 3.0 --success-dist 0.50 --max-steps 180 \
  --keep-near-success --near-success-max-m "$NEAR_M" --drop-collided \
  --episodes "$EPISODES" --min-usable "$MIN_USABLE" \
  --actor-ckpt "$ACTOR" \
  --out "$OUT" \
  2>&1 | tee -a "$LOG"
RC=$?
set -e

N=$(ls "$OUT"/episode_*.npz 2>/dev/null | wc -l | tr -d ' ')
echo "[e1] count=$N rc=$RC" | tee -a "$LOG"

if [[ "$N" -gt 0 ]]; then
  $AERIAL_PY - <<PY | tee -a "$LOG"
import json
from pathlib import Path
out = Path("$OUT")
sm = json.loads((out / "collection_summary.json").read_text())
eps = sm.get("episodes") or []
dens = [float(e["d_end_m_gt"]) for e in eps if e.get("d_end_m_gt") is not None]
n20 = sum(1 for x in dens if x <= 0.20)
mean = sum(dens) / max(len(dens), 1)
print(f"[e1] usable={len(dens)} mean_d={mean:.3f} n_le_0.20={n20}")
PY
fi

exit "$RC"
