#!/usr/bin/env bash
# E2g.1 — new-spec fixture BC @ success=0.20 (human order 2026-08-30)
set -euo pipefail
ROOT="${AERIAL_INDOOR_ROOT:-/home/yao/aerial-indoor-wam}"
cd "$ROOT"
# shellcheck disable=SC1091
source experiments/aerial/scripts/env_4090.sh

bash experiments/aerial/scripts/wait_airsim_idle.sh --timeout-sec 7200

OUT=experiments/aerial/rl/artifacts/dataset_indoor_fixture_bc_e2g_020_20260830
LOG="logs/indoor_e2g_collect_020_$(date +%Y%m%d_%H%M%S).log"
mkdir -p logs

echo "[E2g.1] collecting -> $OUT (log $LOG)"
$AERIAL_PY experiments/aerial/scripts/indoor_loop_collect.py \
  --pose-source gt_proxy --assist gt_pd --allow-gt-assist --keep-arrived-only \
  --success-dist 0.20 --max-intervention-rate 0.55 \
  --bc-tag fixture_gt_pd_020 \
  --routes 6,12 --segment-len-m 6 --max-steps 200 \
  --episodes 60 --min-usable 15 \
  --actor-ckpt experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2f_20260830/v4_ac_latest.pt \
  --out "$OUT" \
  2>&1 | tee "$LOG"

echo "[E2g.1] done. summary:"
python3 - <<'PY'
import json
from pathlib import Path
p = Path("experiments/aerial/rl/artifacts/dataset_indoor_fixture_bc_e2g_020_20260830/collection_summary.json")
if p.is_file():
    d = json.loads(p.read_text())
    print("n_collected", d.get("n_collected"), "n_usable", d.get("n_usable"))
    print("arrival_rate_gt", d.get("arrival_rate_gt"), "mean_d_end_gt", d.get("mean_d_end_gt"))
    irs = [e.get("intervention_rate") for e in d.get("episodes") or [] if e.get("intervention_rate") is not None]
    if irs:
        print("intervention_rate mean", round(sum(irs)/len(irs), 4), "max", round(max(irs), 4))
else:
    print("MISSING", p)
PY
