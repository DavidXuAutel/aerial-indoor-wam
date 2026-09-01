#!/usr/bin/env bash
# E2i.D D3+D4 — mix (D2 none + D1 fixture≤25%) → π short FT → @0.20 eval
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source experiments/aerial/scripts/env_4090.sh
export AIRSIM_CAMERA=0 AIRSIM_VEHICLE=drone_1
mkdir -p logs artifacts

STAMP="${STAMP:-20260901}"
D1="${D1:-experiments/aerial/rl/artifacts/dataset_indoor_b99_fixture_avoid_${STAMP}}"
D2="${D2:-experiments/aerial/rl/artifacts/dataset_indoor_b99_none_near_d_${STAMP}}"
MIX="experiments/aerial/rl/artifacts/dataset_indoor_e2i_d_${STAMP}"
INIT_ACT=experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2i_b_20260901/v4_ac_latest.pt
INIT_WM=experiments/aerial/rl/artifacts/wm_ckpt_indoor_encode_e2i_b_20260901/wm_step_400.pt
CKPT_DIR=experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2i_d_${STAMP}
PI_ITERS="${PI_ITERS:-600}"
LOG=logs/e2i_d_ft_eval_${STAMP}.log
CFG_EVAL=configs/aerial_rl_indoor_shield_v3.yaml
ANN=artifacts/building99_indoor_short_routes.json

test -d "$D1" && test -d "$D2"
n_d1=$(ls "$D1"/episode_*.npz 2>/dev/null | wc -l | tr -d ' ')
n_d2=$(ls "$D2"/episode_*.npz 2>/dev/null | wc -l | tr -d ' ')
test "$n_d1" -ge 15
test "$n_d2" -ge 40
test -f "$INIT_ACT" && test -f "$INIT_WM"

: > "$LOG"
echo "[d] mix D2=$n_d2 (none) + D1=$n_d1 (fixture≤25%) $(date -Is)" | tee -a "$LOG"
# B1 = D2 none near (contract-isomorphic); B2 = D1 fixture avoid ≤25%
$AERIAL_PY experiments/aerial/scripts/indoor_build_e2i_a_mix.py \
  --out "$MIX" --b1 "$D2" --b2 "$D1" \
  --total 100 --b1-frac 0.75 --b2-frac 0.25 --old-frac 0.0 \
  2>&1 | tee -a "$LOG"

echo "[d] π FT iters=$PI_ITERS init=B → $CKPT_DIR" | tee -a "$LOG"
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

if ! pgrep -f 'Building_99/Binaries' >/dev/null || ! ss -ltn | grep -q 41451; then
  bash experiments/aerial/scripts/recover_renderer_scene.sh building99 || true
  sleep 12
fi

echo "[d] eval @0.20" | tee -a "$LOG"
for SEED in 0 1 2; do
  OUT="artifacts/indoor_e2i_d_020_seed${SEED}_${STAMP}.json"
  TMP="/tmp/aerial_rl_d_020_seed${SEED}.yaml"
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
    --out "artifacts/indoor_e2i_d_020_seed${SEED}_fail_split.json" \
    2>&1 | tee -a "$LOG"
done

STAMP="$STAMP" $AERIAL_PY - <<'PY'
import json, os
from pathlib import Path
stamp = os.environ["STAMP"]
rows, tot_a, tot_n, tot_c, spawn, near = [], 0, 0, 0, 0, 0
for seed in (0, 1, 2):
    p = Path(f"artifacts/indoor_e2i_d_020_seed{seed}_{stamp}.json")
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
    tot_a += arr; tot_n += len(eps); tot_c += cols; spawn += sp; near += nr
    rows.append({
        "seed": seed, "n": len(eps), "arrived": arr,
        "mean_d": (sum(dens) / len(dens)) if dens else None,
        "collision_n": cols, "spawn_n": sp, "near_coll_n": nr,
    })
mean_d = sum(r["mean_d"] for r in rows if r["mean_d"] is not None) / max(
    1, sum(1 for r in rows if r["mean_d"] is not None)
)
arr_rate = tot_a / tot_n if tot_n else 0.0
quality_pass = (mean_d <= 0.8) or (arr_rate >= 0.25)
out = {
    "protocol": "e2i_d_020",
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
Path(f"artifacts/indoor_e2i_d_020_summary_{stamp}.json").write_text(
    json.dumps(out, indent=2) + "\n"
)
print(json.dumps(out, indent=2))
PY

echo "[d] done $(date -Is)" | tee -a "$LOG"
