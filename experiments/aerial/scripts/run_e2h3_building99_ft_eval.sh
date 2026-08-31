#!/usr/bin/env bash
# E2h.3 — Building_99: FT on indoor fixture + assist=none contract (original Stick scheme)
set -euo pipefail
ROOT="${AERIAL_INDOOR_ROOT:-/home/yao/aerial-indoor-wam}"
cd "$ROOT"
# shellcheck disable=SC1091
source experiments/aerial/scripts/env_4090.sh
export AIRSIM_CAMERA=0 AIRSIM_VEHICLE=drone_1
mkdir -p logs artifacts

DATASET=experiments/aerial/rl/artifacts/dataset_indoor_building99_e2h_20260830
CKPT_IN=experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2f_20260830/v4_ac_latest.pt
CKPT_OUT=experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2h_20260831
ANN=artifacts/building99_indoor_short_routes.json
ROUTES=0,1,2,3,4,5,6,7

test -f "$DATASET/collection_summary.json"
test -f "$CKPT_IN"
test -f "$ANN"
N=$(ls "$DATASET"/episode_*.npz 2>/dev/null | wc -l)
echo "[E2h.3] dataset npz=$N ckpt_in=$CKPT_IN"

# Ensure Building_99 owns :41451 (do not share with Phase-2 outdoor forensics).
pkill -f 'experiments/aerial/scripts/wam_phase2_traj_forensics.py' 2>/dev/null || true
if ! pgrep -f 'Building_99/Binaries' >/dev/null || ! ss -ltn | grep -q 41451; then
  bash experiments/aerial/scripts/recover_renderer_scene.sh building99
  sleep 12
fi

echo "[E2h.3] FT @4090 on Building_99 fixture ..."
$AERIAL_PY -u -m experiments.aerial.rl.train_v4_ac \
  --indoor --iters 500 --device cuda --dynamics torch \
  --wm-ckpt experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt \
  --actor-ckpt "$CKPT_IN" \
  --dataset "$DATASET" \
  --skip-collect --train-pose-source gt_proxy \
  --ckpt-dir "$CKPT_OUT" \
  2>&1 | tee logs/indoor_e2h_ft_4090_20260831.log

test -f "$CKPT_OUT/v4_ac_latest.pt"

echo "[E2h.3] contract eval assist=none @0.20 (3 seeds) on Building_99 ..."
for SEED in 0 1 2; do
  echo "[E2h.3] eval seed=$SEED ..."
  $AERIAL_PY experiments/aerial/scripts/indoor_mainline_baseline_eval.py \
    --actor-ckpt "$CKPT_OUT/v4_ac_latest.pt" \
    --pose-source gt_proxy --assist none \
    --annotation "$ANN" --routes "$ROUTES" \
    --segment-len-m 3.0 --success-dist 0.20 \
    --max-steps 160 \
    --out "artifacts/indoor_mainline_baseline_e2h_020_seed${SEED}_20260831.json" \
    2>&1 | tee "logs/indoor_e2h_eval_020_seed${SEED}_20260831.log"
done

echo "[E2h.3] also @0.50 reference seed0 ..."
$AERIAL_PY experiments/aerial/scripts/indoor_mainline_baseline_eval.py \
  --actor-ckpt "$CKPT_OUT/v4_ac_latest.pt" \
  --pose-source gt_proxy --assist none \
  --annotation "$ANN" --routes "$ROUTES" \
  --segment-len-m 3.0 --success-dist 0.50 \
  --max-steps 160 \
  --out "artifacts/indoor_mainline_baseline_e2h_050_seed0_20260831.json" \
  2>&1 | tee "logs/indoor_e2h_eval_050_seed0_20260831.log"

echo "[E2h.3] summarize"
python3 - <<'PY'
import json
from pathlib import Path
root = Path("/home/yao/aerial-indoor-wam/artifacts")
rows = []
for seed in (0, 1, 2):
    p = root / f"indoor_mainline_baseline_e2h_020_seed{seed}_20260831.json"
    d = json.loads(p.read_text())
    eps = d.get("episodes") or d.get("results") or []
    # normalize keys
    if not eps and isinstance(d.get("per_route"), list):
        eps = d["per_route"]
    ok = [e for e in eps if e.get("ok", True)]
    dens = [e.get("d_end_m_gt", e.get("d_end_m_hat", e.get("d_end_m"))) for e in ok]
    dens = [float(x) for x in dens if x is not None]
    arr = [e for e in ok if e.get("arrived_gt", e.get("arrived"))]
    rows.append({
        "seed": seed,
        "n": len(ok),
        "n_arrived_020": len(arr),
        "mean_d_end": round(sum(dens)/len(dens), 4) if dens else None,
        "min_d_end": round(min(dens), 4) if dens else None,
    })
    print("seed", seed, rows[-1], "keys_sample", list(d.keys())[:12])
summary = {"protocol": "E2h.3_assist_none_020", "scene": "Building_99", "seeds": rows}
# gate like E2g.3: >=2/3 seeds with arrival OR mean<=0.8
pass_arr = sum(1 for r in rows if (r["n_arrived_020"] or 0) > 0)
pass_mean = sum(1 for r in rows if r["mean_d_end"] is not None and r["mean_d_end"] <= 0.8)
gate = pass_arr >= 2 or pass_mean >= 2
summary["gate_pass"] = bool(gate)
summary["pass_arr_seeds"] = pass_arr
summary["pass_mean_seeds"] = pass_mean
# 0.50 ref
p50 = root / "indoor_mainline_baseline_e2h_050_seed0_20260831.json"
if p50.is_file():
    d = json.loads(p50.read_text())
    eps = d.get("episodes") or d.get("results") or []
    ok = [e for e in eps if e.get("ok", True)]
    dens = [float(e.get("d_end_m_gt", e.get("d_end_m_hat", e.get("d_end_m")))) for e in ok if e.get("d_end_m_gt", e.get("d_end_m_hat", e.get("d_end_m"))) is not None]
    arr = [e for e in ok if e.get("arrived_gt", e.get("arrived"))]
    summary["ref_050_seed0"] = {
        "n": len(ok), "n_arrived": len(arr),
        "mean_d_end": round(sum(dens)/len(dens), 4) if dens else None,
    }
out = root / "indoor_e2h3_contract_summary_20260831.json"
out.write_text(json.dumps(summary, indent=2))
print("SUMMARY", json.dumps(summary, indent=2))
print("WROTE", out)
PY

echo "[E2h.3] DONE"
