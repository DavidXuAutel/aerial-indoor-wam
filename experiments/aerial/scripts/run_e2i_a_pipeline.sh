#!/usr/bin/env bash
# E2i.A pipeline on 125: success mix → WM encode FT → π re-C1 → @0.50 eval
# Usage: bash experiments/aerial/scripts/run_e2i_a_pipeline.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source experiments/aerial/scripts/env_4090.sh

STAMP="${STAMP:-20260831}"
LOG_DIR="${LOG_DIR:-$ROOT/logs}"
mkdir -p "$LOG_DIR"

WM_INIT="${WM_INIT:-experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt}"
WM_OUT="${WM_OUT:-experiments/aerial/rl/artifacts/wm_ckpt_indoor_encode_e2i_a_${STAMP}}"
WM_STEPS="${WM_STEPS:-400}"
PI_PARENT="${PI_PARENT:-experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2i_c1_${STAMP}/v4_ac_latest.pt}"
PI_OUT="${PI_OUT:-experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2i_a_${STAMP}}"
PI_ITERS="${PI_ITERS:-500}"
MIX_OUT="${MIX_OUT:-experiments/aerial/rl/artifacts/dataset_indoor_e2i_a_${STAMP}}"
CFG="${CFG:-configs/aerial_rl_indoor_c1_050.yaml}"
PHASE="${1:-all}"  # mix|wm|pi|eval|all

echo "[e2i.a] ROOT=$ROOT PHASE=$PHASE"

if [[ "$PHASE" == "mix" || "$PHASE" == "all" ]]; then
  echo "[e2i.a] build π mix → $MIX_OUT"
  $AERIAL_PY experiments/aerial/scripts/indoor_build_e2i_a_mix.py \
    --out "$MIX_OUT" \
    --total 100 \
    --b1-frac 0.65 --b2-frac 0.25 --old-frac 0.0
fi

if [[ "$PHASE" == "wm" || "$PHASE" == "all" ]]; then
  echo "[e2i.a] WM encode FT → $WM_OUT (${WM_STEPS} steps)"
  # Prefer B1-heavy encode mix; fallback to raw B1 then π mix
  ENC_DS="experiments/aerial/rl/artifacts/dataset_indoor_e2i_a_encode_${STAMP}"
  if [[ ! -d "$ENC_DS" ]]; then
    ENC_DS="experiments/aerial/rl/artifacts/dataset_indoor_b99_none_near_${STAMP}"
  fi
  if [[ ! -d "$ENC_DS" ]]; then
    ENC_DS="$MIX_OUT"
  fi
  $AERIAL_PY experiments/aerial/rl/_wm_train_validate.py \
    --config "$CFG" \
    --dataset "$ENC_DS" \
    --init-ckpt "$WM_INIT" \
    --checkpoint-dir "$WM_OUT" \
    --steps "$WM_STEPS" --window 12 --wm-batch 8 \
    --device cuda --save-ckpt --skip-gate \
    2>&1 | tee "$LOG_DIR/e2i_a_wm_encode_${WM_STEPS}_${STAMP}.log"
fi

WM_CKPT="$WM_OUT/wm_step_${WM_STEPS}.pt"
if [[ "$PHASE" == "pi" || "$PHASE" == "all" ]]; then
  if [[ ! -f "$WM_CKPT" ]]; then
    echo "[e2i.a] missing WM ckpt: $WM_CKPT" >&2
    exit 1
  fi
  echo "[e2i.a] π C1 FT → $PI_OUT"
  # train_v4_ac reads configs/aerial_rl.yaml; indoor overrides via --indoor CLI
  $AERIAL_PY -u -m experiments.aerial.rl.train_v4_ac \
    --indoor --dynamics torch --device cuda \
    --wm-ckpt "$WM_CKPT" \
    --actor-ckpt "$PI_PARENT" \
    --dataset "$MIX_OUT" \
    --skip-collect --no-approach-bias \
    --train-pose-source gt_proxy \
    --success-dist-m 0.50 \
    --iters "$PI_ITERS" \
    --ckpt-dir "$PI_OUT" \
    2>&1 | tee "$LOG_DIR/e2i_a_pi_c1_${PI_ITERS}_${STAMP}.log"
fi

if [[ "$PHASE" == "eval" || "$PHASE" == "all" ]]; then
  ACTOR="$PI_OUT/v4_ac_latest.pt"
  if [[ ! -f "$ACTOR" ]]; then
    echo "[e2i.a] missing actor: $ACTOR" >&2
    exit 1
  fi
  echo "[e2i.a] @0.50 eval (needs Building_99 AirSim)"
  export AIRSIM_CAMERA=0 AIRSIM_VEHICLE=drone_1
  ANN=artifacts/building99_indoor_short_routes.json
  ROUTES=0,1,2,3,4,5,6,7
  for SEED in 0 1 2; do
    OUT="artifacts/indoor_e2i_a_eval_050_seed${SEED}_a_${STAMP}.json"
    TMP_CFG="/tmp/aerial_rl_indoor_c1_050_seed${SEED}.yaml"
    python3 - <<PY
import yaml
from pathlib import Path
cfg = yaml.safe_load(Path("$CFG").read_text()) or {}
cfg.setdefault("env", {})["seed"] = int("$SEED")
Path("$TMP_CFG").write_text(yaml.safe_dump(cfg, sort_keys=False))
PY
    $AERIAL_PY experiments/aerial/scripts/indoor_mainline_baseline_eval.py \
      --config "$TMP_CFG" \
      --actor-ckpt "$ACTOR" \
      --wm-ckpt "$WM_CKPT" \
      --pose-source gt_proxy --assist none \
      --annotation "$ANN" --routes "$ROUTES" \
      --segment-len-m 3.0 --success-dist 0.50 --max-steps 160 \
      --out "$OUT" \
      2>&1 | tee -a "$LOG_DIR/e2i_a_eval_050_${STAMP}.log"
  done
  STAMP="$STAMP" $AERIAL_PY - <<'PY'
import json, os
from pathlib import Path
stamp = os.environ["STAMP"]
rows = []
for seed in (0, 1, 2):
    p = Path(f"artifacts/indoor_e2i_a_eval_050_seed{seed}_a_{stamp}.json")
    if not p.is_file():
        continue
    d = json.loads(p.read_text())
    eps = d.get("episodes") or d.get("results") or []
    arrived = sum(1 for e in eps if e.get("arrived") or e.get("success"))
    dens = []
    for e in eps:
        v = e.get("d_end_m_gt", e.get("d_end_m"))
        if v is not None:
            dens.append(float(v))
    rows.append({
        "seed": seed,
        "file": str(p),
        "n": len(eps),
        "arrived": arrived,
        "mean_d": (sum(dens) / len(dens)) if dens else None,
    })
seeds_with = sum(1 for r in rows if r["arrived"] > 0)
all_d = [r["mean_d"] for r in rows if r["mean_d"] is not None]
mean_d = (sum(all_d) / len(all_d)) if all_d else None
gate = seeds_with >= 2 or (mean_d is not None and mean_d <= 1.0)
out = {
    "protocol": "e2i_a_c1_050",
    "seeds_with_arrival": seeds_with,
    "mean_d_end_m": mean_d,
    "gate_pass": gate,
    "seeds": rows,
}
Path(f"artifacts/indoor_e2i_a_eval_050_summary_a_{stamp}.json").write_text(
    json.dumps(out, indent=2) + "\n"
)
print(json.dumps(out, indent=2))
PY
fi

echo "[e2i.a] done PHASE=$PHASE"
