#!/usr/bin/env bash
# E2h shield-off diagnostic — compare π reachability without ThreeZoneSpeedShield clamp
set -euo pipefail
ROOT="${AERIAL_INDOOR_ROOT:-/home/yao/aerial-indoor-wam}"
cd "$ROOT"
# shellcheck disable=SC1091
source experiments/aerial/scripts/env_4090.sh
export AIRSIM_CAMERA=0 AIRSIM_VEHICLE=drone_1
mkdir -p logs artifacts

CKPT="${1:-experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2h4_20260831/v4_ac_latest.pt}"
ANN=artifacts/building99_indoor_short_routes.json
ROUTES=0,1,2,3,4,5,6,7
TAG=20260831

test -f "$CKPT"
test -f "$ANN"

pkill -f 'wam_phase2_traj_forensics.py' 2>/dev/null || true
if ! pgrep -f 'Building_99/Binaries' >/dev/null || ! ss -ltn | grep -q 41451; then
  bash experiments/aerial/scripts/recover_renderer_scene.sh building99
  sleep 12
fi

echo "[shield-off diag] ckpt=$CKPT — 3 seeds @0.20, shield OFF ..."
for SEED in 0 1 2; do
  echo "[shield-off] seed=$SEED"
  $AERIAL_PY experiments/aerial/scripts/indoor_mainline_baseline_eval.py \
    --actor-ckpt "$CKPT" \
    --pose-source gt_proxy --assist none --shield-off \
    --annotation "$ANN" --routes "$ROUTES" \
    --segment-len-m 3.0 --success-dist 0.20 \
    --max-steps 160 \
    --out "artifacts/indoor_shield_off_e2h4_020_seed${SEED}_${TAG}.json" \
    2>&1 | tee "logs/indoor_shield_off_e2h4_020_seed${SEED}_${TAG}.log"
done

python3 - <<PY
import json
from pathlib import Path
root = Path("$ROOT/artifacts")
rows = []
for seed in (0, 1, 2):
    p = root / f"indoor_shield_off_e2h4_020_seed{seed}_${TAG}.json"
    d = json.loads(p.read_text())
    eps = d.get("episodes") or []
    ok = [e for e in eps if e.get("ok")]
    dens_gt = [float(e["d_end_m_gt"]) for e in ok if e.get("d_end_m_gt") is not None]
    dens_hat = [float(e["d_end_m_hat"]) for e in ok if e.get("d_end_m_hat") is not None]
    arr_gt = [e for e in ok if e.get("arrived_gt")]
    arr_hat = [e for e in ok if e.get("arrived_hat")]
    rows.append({
        "seed": seed,
        "n": len(ok),
        "n_arrived_gt_020": len(arr_gt),
        "n_arrived_hat_020": len(arr_hat),
        "mean_d_end_gt": round(sum(dens_gt) / len(dens_gt), 4) if dens_gt else None,
        "mean_d_end_hat": round(sum(dens_hat) / len(dens_hat), 4) if dens_hat else None,
        "min_d_end_gt": round(min(dens_gt), 4) if dens_gt else None,
        "max_intervention_rate": max((e.get("intervention_rate", 0) for e in ok), default=0),
    })
summary = {
    "protocol": "E2h_shield_off_diag_assist_none_020",
    "scene": "Building_99",
    "ckpt": "$CKPT",
    "shield": "off",
    "seeds": rows,
    "any_arrival_gt": any(r["n_arrived_gt_020"] > 0 for r in rows),
}
out = root / "indoor_shield_off_diag_summary_${TAG}.json"
out.write_text(json.dumps(summary, indent=2))
print(json.dumps(summary, indent=2))
print("WROTE", out)
PY

echo "[shield-off diag] DONE"
