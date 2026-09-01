#!/usr/bin/env bash
# E2i.C S1 — SPAWN bookkeeping: eval primary head on routes w/o R01 (idx 0)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source experiments/aerial/scripts/env_4090.sh
export AIRSIM_CAMERA=0 AIRSIM_VEHICLE=drone_1
mkdir -p logs artifacts

STAMP="${STAMP:-20260901}"
CFG="${CFG:-configs/aerial_rl_indoor_c1_050.yaml}"
# Primary from S3 compare (B not worse @0.50)
WM=experiments/aerial/rl/artifacts/wm_ckpt_indoor_encode_e2i_b_20260901/wm_step_400.pt
ACT=experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2i_b_20260901/v4_ac_latest.pt
ANN=artifacts/building99_indoor_short_routes_nospawn_r01.json
# Original idx 1..7 → 7 routes in filtered file = indices 0..6
ROUTES=0,1,2,3,4,5,6
LOG=logs/e2i_c_s1_nospawn_b050_${STAMP}.log

test -f "$ACT" && test -f "$WM" && test -f "$ANN"

if ! pgrep -f 'Building_99/Binaries' >/dev/null || ! ss -ltn | grep -q 41451; then
  bash experiments/aerial/scripts/recover_renderer_scene.sh building99 || true
  sleep 12
fi

: > "$LOG"
echo "[s1] start $(date -Is) primary=B nospawn_r01" | tee -a "$LOG"

for SEED in 0 1 2; do
  OUT="artifacts/indoor_e2i_c_s1_B050_nospawn_seed${SEED}_${STAMP}.json"
  TMP="/tmp/aerial_rl_s1_B050_seed${SEED}.yaml"
  python3 - <<PY
import yaml
from pathlib import Path
cfg = yaml.safe_load(Path("$CFG").read_text()) or {}
cfg.setdefault("env", {})["seed"] = int("$SEED")
cfg.setdefault("reward", {})["success_dist_m"] = 0.50
Path("$TMP").write_text(yaml.safe_dump(cfg, sort_keys=False))
PY
  $AERIAL_PY experiments/aerial/scripts/indoor_mainline_baseline_eval.py \
    --config "$TMP" \
    --actor-ckpt "$ACT" \
    --wm-ckpt "$WM" \
    --pose-source gt_proxy --assist none \
    --annotation "$ANN" --routes "$ROUTES" \
    --segment-len-m 3.0 --success-dist 0.50 --max-steps 160 \
    --out "$OUT" \
    2>&1 | tee -a "$LOG"
  $AERIAL_PY experiments/aerial/scripts/indoor_fail_split_report.py \
    --in "$OUT" \
    --out "artifacts/indoor_e2i_c_s1_B050_nospawn_seed${SEED}_fail_split.json" \
    2>&1 | tee -a "$LOG"
done

STAMP="$STAMP" $AERIAL_PY - <<'PY'
import json, os
from pathlib import Path
stamp = os.environ["STAMP"]
rows, tot_a, tot_n, tot_c, spawn, near = [], 0, 0, 0, 0, 0
for seed in (0, 1, 2):
    p = Path(f"artifacts/indoor_e2i_c_s1_B050_nospawn_seed{seed}_{stamp}.json")
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
        "mean_d": (sum(dens)/len(dens)) if dens else None,
        "collision_n": cols, "spawn_n": sp, "near_coll_n": nr,
    })
mean_d = sum(r["mean_d"] for r in rows if r["mean_d"] is not None) / max(1, sum(1 for r in rows if r["mean_d"] is not None))
out = {
    "protocol": "e2i_c_s1_B050_nospawn",
    "annotation": "building99_indoor_short_routes_nospawn_r01.json",
    "dropped": "R01 idx0",
    "seeds_with_arrival": sum(1 for r in rows if r["arrived"] > 0),
    "mean_d_end_m": mean_d,
    "arrival_rate": tot_a / tot_n if tot_n else 0.0,
    "total_arrived": tot_a,
    "total_n": tot_n,
    "total_collision": tot_c,
    "spawn_collision_n": spawn,
    "near_collision_n": near,
    "seeds": rows,
}
Path(f"artifacts/indoor_e2i_c_s1_B050_nospawn_summary_{stamp}.json").write_text(json.dumps(out, indent=2) + "\n")
print(json.dumps(out, indent=2))
PY

echo "[s1] done $(date -Is)" | tee -a "$LOG"
