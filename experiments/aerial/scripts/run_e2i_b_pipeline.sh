#!/usr/bin/env bash
# E2i.B chain: mix → WM encode → π FT → @0.20 eval (quality read)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source experiments/aerial/scripts/env_4090.sh
export AIRSIM_CAMERA=0 AIRSIM_VEHICLE=drone_1
mkdir -p logs artifacts

STAMP="${STAMP:-20260901}"
PHASE="${1:-all}"  # mix|wm|pi|eval|all
B1="experiments/aerial/rl/artifacts/dataset_indoor_b99_none_near_20260831"
B2="experiments/aerial/rl/artifacts/dataset_indoor_b99_fixture_020_20260831"
MIX="experiments/aerial/rl/artifacts/dataset_indoor_e2i_b_${STAMP}"
ENC_MIX="experiments/aerial/rl/artifacts/dataset_indoor_e2i_b_encode_${STAMP}"
WM_INIT="experiments/aerial/rl/artifacts/wm_ckpt_indoor_encode_e2i_a_20260831/wm_step_400.pt"
WM_OUT="experiments/aerial/rl/artifacts/wm_ckpt_indoor_encode_e2i_b_${STAMP}"
WM_STEPS="${WM_STEPS:-400}"
PI_PARENT="experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2i_a_20260831/v4_ac_latest.pt"
PI_OUT="experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2i_b_${STAMP}"
PI_ITERS="${PI_ITERS:-800}"
CFG_EVAL="configs/aerial_rl_indoor_shield_v3.yaml"
CHAIN_LOG="logs/e2i_b_chain_${STAMP}.log"

echo "[e2i.b] PHASE=$PHASE $(date -Is)" | tee -a "$CHAIN_LOG"

if [[ "$PHASE" == "mix" || "$PHASE" == "all" ]]; then
  echo "[e2i.b] build π mix (B1-heavy) + encode mix" | tee -a "$CHAIN_LOG"
  $AERIAL_PY experiments/aerial/scripts/indoor_build_e2i_a_mix.py \
    --out "$MIX" --b1 "$B1" --b2 "$B2" \
    --total 100 --b1-frac 0.75 --b2-frac 0.25 --old-frac 0.0 \
    2>&1 | tee -a "$CHAIN_LOG"
  $AERIAL_PY experiments/aerial/scripts/indoor_build_e2i_a_mix.py \
    --out "$ENC_MIX" --b1 "$B1" --b2 "$B2" \
    --encode-only --total 80 \
    2>&1 | tee -a "$CHAIN_LOG"
fi

if [[ "$PHASE" == "wm" || "$PHASE" == "all" ]]; then
  test -f "$WM_INIT"
  echo "[e2i.b] WM encode FT → $WM_OUT" | tee -a "$CHAIN_LOG"
  $AERIAL_PY experiments/aerial/rl/_wm_train_validate.py \
    --config configs/aerial_rl_indoor_c1_050.yaml \
    --dataset "$ENC_MIX" \
    --init-ckpt "$WM_INIT" \
    --checkpoint-dir "$WM_OUT" \
    --steps "$WM_STEPS" --window 12 --wm-batch 8 \
    --device cuda --save-ckpt --skip-gate \
    2>&1 | tee "logs/e2i_b_wm_encode_${WM_STEPS}_${STAMP}.log" | tee -a "$CHAIN_LOG"
fi

WM_CKPT="$WM_OUT/wm_step_${WM_STEPS}.pt"

if [[ "$PHASE" == "pi" || "$PHASE" == "all" ]]; then
  test -f "$WM_CKPT"
  test -f "$PI_PARENT"
  echo "[e2i.b] π FT iters=$PI_ITERS → $PI_OUT" | tee -a "$CHAIN_LOG"
  $AERIAL_PY -u -m experiments.aerial.rl.train_v4_ac \
    --indoor --dynamics torch --device cuda \
    --wm-ckpt "$WM_CKPT" \
    --actor-ckpt "$PI_PARENT" \
    --dataset "$MIX" \
    --skip-collect --no-approach-bias \
    --train-pose-source gt_proxy \
    --success-dist-m 0.20 \
    --iters "$PI_ITERS" \
    --ckpt-dir "$PI_OUT" \
    2>&1 | tee "logs/e2i_b_pi_${PI_ITERS}_${STAMP}.log" | tee -a "$CHAIN_LOG"
fi

if [[ "$PHASE" == "eval" || "$PHASE" == "all" ]]; then
  ACTOR="$PI_OUT/v4_ac_latest.pt"
  test -f "$ACTOR"
  test -f "$WM_CKPT"
  if ! pgrep -f 'Building_99/Binaries' >/dev/null || ! ss -ltn | grep -q 41451; then
    bash experiments/aerial/scripts/recover_renderer_scene.sh building99 || true
    sleep 12
  fi
  TAG="e2i_b_020"
  ANN=artifacts/building99_indoor_short_routes.json
  ROUTES=0,1,2,3,4,5,6,7
  echo "[e2i.b] @0.20 eval" | tee -a "$CHAIN_LOG"
  for SEED in 0 1 2; do
    OUT="artifacts/indoor_${TAG}_seed${SEED}_${STAMP}.json"
    TMP_CFG="/tmp/aerial_rl_indoor_v3_seed${SEED}_${TAG}.yaml"
    python3 - <<PY
import yaml
from pathlib import Path
cfg = yaml.safe_load(Path("$CFG_EVAL").read_text()) or {}
cfg.setdefault("env", {})["seed"] = int("$SEED")
cfg.setdefault("reward", {})["success_dist_m"] = 0.20
Path("$TMP_CFG").write_text(yaml.safe_dump(cfg, sort_keys=False))
PY
    $AERIAL_PY experiments/aerial/scripts/indoor_mainline_baseline_eval.py \
      --config "$TMP_CFG" \
      --actor-ckpt "$ACTOR" \
      --wm-ckpt "$WM_CKPT" \
      --pose-source gt_proxy --assist none \
      --annotation "$ANN" --routes "$ROUTES" \
      --segment-len-m 3.0 --success-dist 0.20 --max-steps 160 \
      --out "$OUT" \
      2>&1 | tee -a "logs/e2i_b_eval_020_${STAMP}.log" | tee -a "$CHAIN_LOG"
  done
  STAMP="$STAMP" TAG="$TAG" $AERIAL_PY - <<'PY'
import json, os
from pathlib import Path
stamp = os.environ["STAMP"]
tag = os.environ["TAG"]
rows = []
total_arrived = 0
total_n = 0
total_coll = 0
for seed in (0, 1, 2):
    p = Path(f"artifacts/indoor_{tag}_seed{seed}_{stamp}.json")
    if not p.is_file():
        continue
    d = json.loads(p.read_text())
    eps = d.get("episodes") or d.get("results") or []
    arrived = sum(1 for e in eps if e.get("arrived") or e.get("success"))
    dens = []
    cols = 0
    spawn = near = 0
    for e in eps:
        v = e.get("d_end_m_gt", e.get("d_end_m"))
        if v is not None:
            dens.append(float(v))
        if e.get("collided"):
            cols += 1
            steps = int(e.get("steps") or 0)
            if steps <= 8:
                spawn += 1
            else:
                near += 1
    total_arrived += arrived
    total_n += len(eps)
    total_coll += cols
    rows.append({
        "seed": seed, "n": len(eps), "arrived": arrived,
        "mean_d": (sum(dens)/len(dens)) if dens else None,
        "collision_n": cols, "spawn_n": spawn, "near_coll_n": near,
    })
seeds_with = sum(1 for r in rows if r["arrived"] > 0)
all_d = [r["mean_d"] for r in rows if r["mean_d"] is not None]
mean_d = (sum(all_d)/len(all_d)) if all_d else None
arrival_rate = (total_arrived / total_n) if total_n else 0.0
legacy_gate = seeds_with >= 2 or (mean_d is not None and mean_d <= 0.8)
quality_gate = (mean_d is not None and mean_d <= 0.8) or arrival_rate >= 0.25
out = {
    "protocol": "e2i_b_contract_020",
    "tag": tag,
    "seeds_with_arrival": seeds_with,
    "mean_d_end_m": mean_d,
    "arrival_rate": arrival_rate,
    "total_arrived": total_arrived,
    "total_n": total_n,
    "total_collision": total_coll,
    "legacy_gate_pass": legacy_gate,
    "quality_gate_pass": quality_gate,
    "quality_rule": "mean_d<=0.8 OR arrival_rate>=0.25",
    "seeds": rows,
}
path = Path(f"artifacts/indoor_{tag}_summary_{stamp}.json")
path.write_text(json.dumps(out, indent=2) + "\n")
print(json.dumps(out, indent=2))
print(f"summary → {path}")
PY
fi

echo "[e2i.b] done PHASE=$PHASE $(date -Is)" | tee -a "$CHAIN_LOG"
