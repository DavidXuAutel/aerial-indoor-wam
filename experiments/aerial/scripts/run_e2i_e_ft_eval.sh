#!/usr/bin/env bash
# E2i.E E4 — π short FT on E3 mix → @0.20 eval (assist=none). R06 abandoned.
# Human-ordered 2026-09-01. Run ON 125 (4090).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source experiments/aerial/scripts/env_4090.sh
export AIRSIM_CAMERA=0 AIRSIM_VEHICLE=drone_1
mkdir -p logs artifacts

STAMP="${STAMP:-20260901}"
MIX="${MIX:-experiments/aerial/rl/artifacts/dataset_indoor_e2i_e_${STAMP}}"
# Prefer D actor (nearest prior); WM from B encode (shared indoor encode)
INIT_ACT="${INIT_ACT:-experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2i_d_${STAMP}/v4_ac_latest.pt}"
INIT_WM="${INIT_WM:-experiments/aerial/rl/artifacts/wm_ckpt_indoor_encode_e2i_b_20260901/wm_step_400.pt}"
CKPT_DIR="${CKPT_DIR:-experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2i_e_${STAMP}}"
PI_ITERS="${PI_ITERS:-600}"
LOG="logs/e2i_e_ft_eval_${STAMP}.log"
CFG_EVAL=configs/aerial_rl_indoor_shield_v3.yaml
ANN=artifacts/building99_indoor_short_routes.json

test -d "$MIX"
n_mix=$(ls "$MIX"/episode_*.npz 2>/dev/null | wc -l | tr -d ' ')
test "$n_mix" -ge 80
test -f "$INIT_ACT" && test -f "$INIT_WM"
test -f "$MIX/mix_meta.json"
python3 - <<PY
import json
from pathlib import Path
m = json.loads(Path("$MIX/mix_meta.json").read_text())
frac = float(m.get("fixture_frac") or 1.0)
assert frac <= 0.2500001, frac
print(f"mix_ok n=$n_mix fixture_frac={frac} protocol={m.get('protocol')}")
PY

: >"$LOG"
{
  echo "[e4] FT iters=$PI_ITERS mix=$MIX init_act=$INIT_ACT $(date -Is)"
  echo "[e4] ckpt_dir=$CKPT_DIR"
} | tee -a "$LOG"

echo "[e4] π FT start $(date -Is)" | tee -a "$LOG"
$AERIAL_PY -u -m experiments.aerial.rl.train_v4_ac \
  --indoor --dynamics torch --device cuda \
  --wm-ckpt "$INIT_WM" \
  --actor-ckpt "$INIT_ACT" \
  --dataset "$MIX" \
  --skip-collect --no-approach-bias \
  --train-pose-source gt_proxy \
  --success-dist-m 0.20 \
  --iters "$PI_ITERS" \
  --ckpt-dir "$CKPT_DIR" \
  2>&1 | tee -a "$LOG"

ACTOR="$CKPT_DIR/v4_ac_latest.pt"
test -f "$ACTOR"

# Eval needs renderer; prefer ON_SCREEN=0 for headless speed unless already up
if ! ss -ltn | grep -q 41451; then
  echo "[e4] starting Building_99 renderer" | tee -a "$LOG"
  bash experiments/aerial/scripts/recover_renderer_scene.sh building99 || true
  sleep 15
fi
ss -ltn | grep -q 41451

echo "[e4] eval @0.20 assist=none $(date -Is)" | tee -a "$LOG"
for SEED in 0 1 2; do
  OUT="artifacts/indoor_e2i_e_020_seed${SEED}_${STAMP}.json"
  TMP="/tmp/aerial_rl_e_020_seed${SEED}.yaml"
  python3 - <<PY
import yaml
from pathlib import Path
cfg = yaml.safe_load(Path("$CFG_EVAL").read_text()) or {}
cfg.setdefault("env", {})["seed"] = int("$SEED")
cfg.setdefault("reward", {})["success_dist_m"] = 0.20
Path("$TMP").write_text(yaml.safe_dump(cfg, sort_keys=False))
PY
  $AERIAL_PY experiments/aerial/scripts/indoor_mainline_baseline_eval.py \
    --config "$TMP" \
    --actor-ckpt "$ACTOR" \
    --wm-ckpt "$INIT_WM" \
    --pose-source gt_proxy --assist none \
    --annotation "$ANN" --routes 0,1,2,3,4,5,6,7 \
    --segment-len-m 3.0 --success-dist 0.20 --max-steps 160 \
    --out "$OUT" \
    2>&1 | tee -a "$LOG"
  $AERIAL_PY experiments/aerial/scripts/indoor_fail_split_report.py \
    --in "$OUT" \
    --out "artifacts/indoor_e2i_e_020_seed${SEED}_fail_split.json" \
    2>&1 | tee -a "$LOG"
done

STAMP="$STAMP" $AERIAL_PY - <<'PY'
import json, os
from pathlib import Path
stamp = os.environ["STAMP"]
rows, tot_a, tot_n, tot_c, spawn, near = [], 0, 0, 0, 0, 0
for seed in (0, 1, 2):
    p = Path(f"artifacts/indoor_e2i_e_020_seed{seed}_{stamp}.json")
    d = json.loads(p.read_text())
    eps = d.get("episodes") or d.get("results") or []
    dens, arr, cols, sp, nr = [], 0, 0, 0, 0
    for e in eps:
        if e.get("arrived") or e.get("success"):
            arr += 1
        v = e.get("d_end_m_gt", e.get("d_end_m"))
        if v is not None:
            dens.append(float(v))
        if e.get("collided"):
            cols += 1
            st = int(e.get("steps") or 0)
            if st <= 8:
                sp += 1
            else:
                nr += 1
    tot_a += arr
    tot_n += len(eps)
    tot_c += cols
    spawn += sp
    near += nr
    rows.append({
        "seed": seed,
        "n": len(eps),
        "arrived": arr,
        "mean_d": (sum(dens) / len(dens)) if dens else None,
        "collision_n": cols,
        "spawn_n": sp,
        "near_coll_n": nr,
    })
mean_d = sum(r["mean_d"] for r in rows if r["mean_d"] is not None) / max(
    1, sum(1 for r in rows if r["mean_d"] is not None)
)
arr_rate = tot_a / tot_n if tot_n else 0.0
quality_pass = (mean_d <= 0.8) or (arr_rate >= 0.25)
out = {
    "protocol": "e2i_e_020",
    "r06": "abandoned",
    "seeds_with_arrival": sum(1 for r in rows if r["arrived"] > 0),
    "mean_d_end_m": mean_d,
    "arrival_rate": arr_rate,
    "total_arrived": tot_a,
    "total_n": tot_n,
    "total_collision": tot_c,
    "spawn_collision_n": spawn,
    "near_collision_n": near,
    "quality_gate_pass": quality_pass,
    "quality_rule": "mean_d<=0.8 OR arrival_rate>=0.25",
    "seeds": rows,
}
Path(f"artifacts/indoor_e2i_e_020_summary_{stamp}.json").write_text(
    json.dumps(out, indent=2) + "\n"
)
print(json.dumps(out, indent=2))
PY

echo "[e4] done $(date -Is)" | tee -a "$LOG"
