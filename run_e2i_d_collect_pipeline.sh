#!/usr/bin/env bash
# E2i.D — D1 fixture avoid → D2 none near (collect only; FT 待人令)
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source experiments/aerial/scripts/env_4090.sh
mkdir -p logs

STAMP="${STAMP:-20260901}"
LOG=logs/e2i_d_collect_${STAMP}.log

: > "$LOG"
echo "[e2i.d] start $(date -Is) STAMP=$STAMP" | tee -a "$LOG"

D1_RC=0
D2_RC=0
STAMP="$STAMP" bash experiments/aerial/scripts/run_e2i_d_fixture_avoid_collect.sh 2>&1 | tee -a "$LOG" || D1_RC=$?
STAMP="$STAMP" bash experiments/aerial/scripts/run_e2i_d_none_near_collect.sh 2>&1 | tee -a "$LOG" || D2_RC=$?

STAMP="$STAMP" $AERIAL_PY - <<'PY' | tee -a "$LOG"
import json
from pathlib import Path
from collections import Counter

stamp = __import__("os").environ["STAMP"]
for tag, rel in [
    ("D1_fixture", f"experiments/aerial/rl/artifacts/dataset_indoor_b99_fixture_avoid_{stamp}"),
    ("D2_none", f"experiments/aerial/rl/artifacts/dataset_indoor_b99_none_near_d_{stamp}"),
]:
    p = Path(rel)
    sm = p / "collection_summary.json"
    n = len(list(p.glob("episode_*.npz"))) if p.is_dir() else 0
    print(f"[e2i.d] {tag} npz={n}", end="")
    if sm.is_file():
        d = json.loads(sm.read_text())
        print(f" usable={d.get('n_usable')} arrival_gt={d.get('arrival_rate_gt')} mean_d={d.get('mean_d_end_gt')}")
        rc = Counter()
        for e in d.get("episodes") or []:
            rn = e.get("route_name") or e.get("segment_name") or "?"
            rc[rn] += 1
        if rc:
            print(f"  routes: {dict(rc)}")
    else:
        print(" (no summary yet)")
PY

echo "[e2i.d] done $(date -Is) D1_RC=$D1_RC D2_RC=$D2_RC" | tee -a "$LOG"
if [[ "$D1_RC" -ne 0 && "$D2_RC" -ne 0 ]]; then
  exit 1
fi
exit 0
