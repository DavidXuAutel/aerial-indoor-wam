#!/usr/bin/env bash
# E2i.C S3 — A vs B @0.50 regression (same protocol, Building_99)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source experiments/aerial/scripts/env_4090.sh
export AIRSIM_CAMERA=0 AIRSIM_VEHICLE=drone_1
mkdir -p logs artifacts

STAMP="${STAMP:-20260901}"
CFG="${CFG:-configs/aerial_rl_indoor_c1_050.yaml}"
ANN=artifacts/building99_indoor_short_routes.json
ROUTES=0,1,2,3,4,5,6,7
WM_A=experiments/aerial/rl/artifacts/wm_ckpt_indoor_encode_e2i_a_20260831/wm_step_400.pt
ACT_A=experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2i_a_20260831/v4_ac_latest.pt
WM_B=experiments/aerial/rl/artifacts/wm_ckpt_indoor_encode_e2i_b_20260901/wm_step_400.pt
ACT_B=experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2i_b_20260901/v4_ac_latest.pt
LOG=logs/e2i_c_s3_050_${STAMP}.log

test -f "$ACT_A" && test -f "$WM_A"
test -f "$ACT_B" && test -f "$WM_B"
test -f "$ANN"

if ! pgrep -f 'Building_99/Binaries' >/dev/null || ! ss -ltn | grep -q 41451; then
  bash experiments/aerial/scripts/recover_renderer_scene.sh building99 || true
  sleep 12
fi

run_head() {
  local TAG="$1" ACTOR="$2" WM="$3"
  echo "[s3] eval $TAG @0.50 actor=$ACTOR" | tee -a "$LOG"
  for SEED in 0 1 2; do
    OUT="artifacts/indoor_e2i_c_s3_${TAG}_seed${SEED}_${STAMP}.json"
    TMP="/tmp/aerial_rl_s3_${TAG}_seed${SEED}.yaml"
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
      --actor-ckpt "$ACTOR" \
      --wm-ckpt "$WM" \
      --pose-source gt_proxy --assist none \
      --annotation "$ANN" --routes "$ROUTES" \
      --segment-len-m 3.0 --success-dist 0.50 --max-steps 160 \
      --out "$OUT" \
      2>&1 | tee -a "$LOG"
  done
  TAG="$TAG" STAMP="$STAMP" $AERIAL_PY - <<'PY'
import json, os
from pathlib import Path
tag, stamp = os.environ["TAG"], os.environ["STAMP"]
rows, tot_a, tot_n, tot_c, spawn, near = [], 0, 0, 0, 0, 0
for seed in (0, 1, 2):
    p = Path(f"artifacts/indoor_e2i_c_s3_{tag}_seed{seed}_{stamp}.json")
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
    "protocol": "e2i_c_s3_050",
    "tag": tag,
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
Path(f"artifacts/indoor_e2i_c_s3_{tag}_summary_{stamp}.json").write_text(json.dumps(out, indent=2) + "\n")
print(json.dumps(out, indent=2))
PY
}

: > "$LOG"
echo "[s3] start $(date -Is)" | tee -a "$LOG"
run_head A050 "$ACT_A" "$WM_A"
run_head B050 "$ACT_B" "$WM_B"

STAMP="$STAMP" $AERIAL_PY - <<'PY'
import json, os
from pathlib import Path
stamp = os.environ["STAMP"]
a = json.loads(Path(f"artifacts/indoor_e2i_c_s3_A050_summary_{stamp}.json").read_text())
b = json.loads(Path(f"artifacts/indoor_e2i_c_s3_B050_summary_{stamp}.json").read_text())
# prefer A if B mean worse by >0.3 or arrival_rate lower by >0.1
prefer_a = (b["mean_d_end_m"] - a["mean_d_end_m"] > 0.3) or (a["arrival_rate"] - b["arrival_rate"] > 0.10)
cmp = {
    "protocol": "e2i_c_s3_compare_050",
    "A": a,
    "B": b,
    "delta_mean_d_B_minus_A": b["mean_d_end_m"] - a["mean_d_end_m"],
    "delta_arrival_rate_A_minus_B": a["arrival_rate"] - b["arrival_rate"],
    "recommend_primary_head": "A" if prefer_a else "tie_or_B",
    "rule": "prefer A if B mean worse by >0.3m OR A arrival_rate higher by >0.10",
}
Path(f"artifacts/indoor_e2i_c_s3_compare_050_{stamp}.json").write_text(json.dumps(cmp, indent=2) + "\n")
print(json.dumps({k: cmp[k] for k in ("delta_mean_d_B_minus_A", "delta_arrival_rate_A_minus_B", "recommend_primary_head")}, indent=2))
PY

echo "[s3] done $(date -Is)" | tee -a "$LOG"
