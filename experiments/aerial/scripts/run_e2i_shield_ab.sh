#!/usr/bin/env bash
# E2i.1 — shield A/B: same ckpt, old vs new yaml spec (requires AirSim + building99).
set -euo pipefail
ROOT="${AERIAL_INDOOR_ROOT:-/home/yao/aerial-indoor-wam}"
cd "$ROOT"
# shellcheck disable=SC1091
source experiments/aerial/scripts/env_4090.sh
export AIRSIM_CAMERA=0 AIRSIM_VEHICLE=drone_1
mkdir -p logs artifacts

bash experiments/aerial/scripts/check_airsim_indoor_ready.sh || {
  echo "[E2i.1] ABORT: AirSim not ready for indoor — resolve occupancy first" >&2
  exit 2
}

CKPT="${1:-experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2h4_20260831/v4_ac_latest.pt}"
CFG_OLD="${2:-configs/aerial_rl_indoor_shield_e2h_baseline.yaml}"
CFG_NEW="${3:-configs/aerial_rl_indoor_lossless.yaml}"
ANN=artifacts/building99_indoor_short_routes.json
ROUTES=0,1,2,3,4,5,6,7
TAG="${4:-20260831}"

test -f "$CKPT"
test -f "$CFG_OLD"
test -f "$CFG_NEW"
test -f "$ANN"

pkill -f 'wam_phase2_traj_forensics.py' 2>/dev/null || true
if ! pgrep -f 'Building_99/Binaries' >/dev/null || ! ss -ltn | grep -q 41451; then
  bash experiments/aerial/scripts/recover_renderer_scene.sh building99
  sleep 12
fi

for ARM in old new; do
  CFG=$CFG_OLD
  [[ "$ARM" == "new" ]] && CFG=$CFG_NEW
  echo "[E2i.1] shield A/B arm=$ARM config=$CFG"
  for SEED in 0 1 2; do
    $AERIAL_PY experiments/aerial/scripts/indoor_mainline_baseline_eval.py \
      --config "$CFG" \
      --actor-ckpt "$CKPT" \
      --pose-source gt_proxy --assist none \
      --annotation "$ANN" --routes "$ROUTES" \
      --segment-len-m 3.0 --success-dist 0.20 --max-steps 160 \
      --out "artifacts/indoor_shield_ab_${ARM}_020_seed${SEED}_${TAG}.json" \
      2>&1 | tee "logs/indoor_shield_ab_${ARM}_020_seed${SEED}_${TAG}.log"
  done
done

python3 - <<PY
import json
from pathlib import Path
root = Path("$ROOT/artifacts")
rows = {}
for arm in ("old", "new"):
    seeds = []
    for seed in (0, 1, 2):
        p = root / f"indoor_shield_ab_{arm}_020_seed{seed}_${TAG}.json"
        d = json.loads(p.read_text())
        eps = [e for e in d.get("episodes") or [] if e.get("ok")]
        dens = [float(e["d_end_m_gt"]) for e in eps if e.get("d_end_m_gt") is not None]
        irs = [float(e.get("intervention_rate", 0)) for e in eps]
        col = sum(1 for e in eps if e.get("collided"))
        seeds.append({
            "seed": seed,
            "mean_d_end_gt": round(sum(dens)/len(dens), 4) if dens else None,
            "mean_intervention": round(sum(irs)/len(irs), 4) if irs else None,
            "collision_n": col,
        })
    rows[arm] = seeds
old_mean = sum(s["mean_d_end_gt"] for s in rows["old"] if s["mean_d_end_gt"]) / 3
new_mean = sum(s["mean_d_end_gt"] for s in rows["new"] if s["mean_d_end_gt"]) / 3
old_ir = sum(s["mean_intervention"] for s in rows["old"] if s["mean_intervention"]) / 3
new_ir = sum(s["mean_intervention"] for s in rows["new"] if s["mean_intervention"]) / 3
improve_pct = round(100 * (old_mean - new_mean) / old_mean, 1) if old_mean else None
summary = {
    "protocol": "E2i1_shield_ab",
    "ckpt": "$CKPT",
    "cfg_old": "$CFG_OLD",
    "cfg_new": "$CFG_NEW",
    "arms": rows,
    "old_mean_d_end_avg": round(old_mean, 4),
    "new_mean_d_end_avg": round(new_mean, 4),
    "d_end_improve_pct": improve_pct,
    "old_intervention_avg": round(old_ir, 4),
    "new_intervention_avg": round(new_ir, 4),
    "gate_intervention_lt_0_5": new_ir < 0.5,
    "gate_d_end_improve_gt_30pct": improve_pct is not None and improve_pct > 30,
}
out = root / "indoor_shield_ab_summary_${TAG}.json"
out.write_text(json.dumps(summary, indent=2))
print(json.dumps(summary, indent=2))
PY

echo "[E2i.1] shield A/B DONE"
