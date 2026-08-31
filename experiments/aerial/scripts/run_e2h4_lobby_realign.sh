#!/usr/bin/env bash
# E2h.4 — realign FT corpus to lobby contract routes, re-FT offline, re-eval @0.20
set -euo pipefail
ROOT="${AERIAL_INDOOR_ROOT:-/home/yao/aerial-indoor-wam}"
cd "$ROOT"
# shellcheck disable=SC1091
source experiments/aerial/scripts/env_4090.sh
export AIRSIM_CAMERA=0 AIRSIM_VEHICLE=drone_1
mkdir -p logs artifacts

OUT=experiments/aerial/rl/artifacts/dataset_indoor_building99_e2h_20260830
ANN=artifacts/building99_indoor_short_routes.json
CKPT_IN=experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2f_20260830/v4_ac_latest.pt
CKPT_OUT=experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2h4_20260831
TAG=20260831

test -f "$ANN"
test -f "$CKPT_IN"
PRIOR=$(ls "$OUT"/episode_*.npz 2>/dev/null | wc -l)
echo "[E2h.4] prior_npz=$PRIOR ann=$ANN"

pkill -f 'wam_phase2_traj_forensics.py' 2>/dev/null || true
if ! pgrep -f 'Building_99/Binaries' >/dev/null || ! ss -ltn | grep -q 41451; then
  bash experiments/aerial/scripts/recover_renderer_scene.sh building99
  sleep 12
fi

LOG_COL=logs/indoor_e2h4_lobby_collect_${TAG}.log
echo "[E2h.4] lobby collect append ..."
$AERIAL_PY experiments/aerial/scripts/indoor_building99_fixture_collect.py \
  --annotation "$ANN" \
  --out "$OUT" \
  --append \
  --episodes 64 \
  --segment-len-m 3.0 \
  --success-dist 0.50 \
  --max-steps 140 \
  --min-usable 1 \
  --min-usable-new 10 \
  --keep-arrived-only \
  2>&1 | tee "$LOG_COL"

N=$(ls "$OUT"/episode_*.npz 2>/dev/null | wc -l)
echo "[E2h.4] dataset npz=$N — FT offline (no new AirSim roll) ..."
$AERIAL_PY -u -m experiments.aerial.rl.train_v4_ac \
  --indoor --iters 500 --device cuda --dynamics torch \
  --wm-ckpt experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt \
  --actor-ckpt "$CKPT_IN" \
  --dataset "$OUT" \
  --skip-collect --train-pose-source gt_proxy \
  --ckpt-dir "$CKPT_OUT" \
  2>&1 | tee "logs/indoor_e2h4_ft_4090_${TAG}.log"

test -f "$CKPT_OUT/v4_ac_latest.pt"

echo "[E2h.4] contract eval assist=none @0.20 (3 seeds) ..."
for SEED in 0 1 2; do
  $AERIAL_PY experiments/aerial/scripts/indoor_mainline_baseline_eval.py \
    --actor-ckpt "$CKPT_OUT/v4_ac_latest.pt" \
    --pose-source gt_proxy --assist none \
    --annotation "$ANN" --routes 0,1,2,3,4,5,6,7 \
    --segment-len-m 3.0 --success-dist 0.20 \
    --max-steps 160 \
    --out "artifacts/indoor_mainline_baseline_e2h4_020_seed${SEED}_${TAG}.json" \
    2>&1 | tee "logs/indoor_e2h4_eval_020_seed${SEED}_${TAG}.log"
done

python3 - <<PY
import json
from pathlib import Path
root = Path("$ROOT/artifacts")
rows = []
for seed in (0, 1, 2):
    p = root / f"indoor_mainline_baseline_e2h4_020_seed{seed}_${TAG}.json"
    d = json.loads(p.read_text())
    eps = d.get("episodes") or d.get("results") or []
    ok = [e for e in eps if e.get("ok", True)]
    dens = [
        float(e.get("d_end_m_gt", e.get("d_end_m_hat", e.get("d_end_m"))))
        for e in ok
        if e.get("d_end_m_gt", e.get("d_end_m_hat", e.get("d_end_m"))) is not None
    ]
    arr = [e for e in ok if e.get("arrived_gt", e.get("arrived"))]
    rows.append({
        "seed": seed,
        "n": len(ok),
        "n_arrived_020": len(arr),
        "mean_d_end": round(sum(dens) / len(dens), 4) if dens else None,
        "min_d_end": round(min(dens), 4) if dens else None,
    })
pass_arr = sum(1 for r in rows if (r["n_arrived_020"] or 0) > 0)
pass_mean = sum(1 for r in rows if r["mean_d_end"] is not None and r["mean_d_end"] <= 0.8)
summary = {
    "protocol": "E2h4_lobby_realign_assist_none_020",
    "scene": "Building_99",
    "dataset_npz": int("$N"),
    "seeds": rows,
    "gate_pass": bool(pass_arr >= 2 or pass_mean >= 2),
    "pass_arr_seeds": pass_arr,
    "pass_mean_seeds": pass_mean,
}
out = root / "indoor_e2h4_contract_summary_${TAG}.json"
out.write_text(json.dumps(summary, indent=2))
print(json.dumps(summary, indent=2))
print("WROTE", out)
PY

echo "[E2h.4] DONE"
