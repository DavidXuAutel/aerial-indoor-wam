#!/usr/bin/env bash
# E2i.E E3 — mix only (R06 abandoned). B1 none ≥75% + E1b fixture hard ≤25%.
# Does NOT start FT (E4). Human-ordered 2026-09-01.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source experiments/aerial/scripts/env_4090.sh
mkdir -p logs experiments/aerial/rl/artifacts

STAMP="${STAMP:-20260901}"
NONE_D="${NONE_D:-experiments/aerial/rl/artifacts/dataset_indoor_b99_none_near_d_${STAMP}}"
NONE_OLD="${NONE_OLD:-experiments/aerial/rl/artifacts/dataset_indoor_b99_none_near_20260831}"
FIXTURE="${FIXTURE:-experiments/aerial/rl/artifacts/dataset_indoor_b99_fixture_hard_e_${STAMP}}"
NONE_POOL="${NONE_POOL:-experiments/aerial/rl/artifacts/dataset_indoor_b99_none_pool_e_${STAMP}}"
MIX="${MIX:-experiments/aerial/rl/artifacts/dataset_indoor_e2i_e_${STAMP}}"
TOTAL="${TOTAL:-100}"
B1_FRAC="${B1_FRAC:-0.75}"
B2_FRAC="${B2_FRAC:-0.25}"
LOG="logs/e2i_e_e3_mix_${STAMP}.log"

test -d "$NONE_D"
test -d "$FIXTURE"
n_d=$(ls "$NONE_D"/episode_*.npz 2>/dev/null | wc -l | tr -d ' ')
n_fix=$(ls "$FIXTURE"/episode_*.npz 2>/dev/null | wc -l | tr -d ' ')
n_old=$(ls "$NONE_OLD"/episode_*.npz 2>/dev/null | wc -l | tr -d ' ')
test "$n_fix" -ge 20
test "$((n_d + n_old))" -ge 60

: >"$LOG"
{
  echo "[e3] R06 abandoned; build none pool then mix fixture≤25% $(date -Is)"
  echo "[e3] NONE_D=$n_d NONE_OLD=$n_old FIXTURE=$n_fix total=$TOTAL b1=$B1_FRAC b2=$B2_FRAC"
} | tee -a "$LOG"

# --- none pool: prefer D2 none_near_d, pad from older none_near ---
rm -rf "$NONE_POOL"
mkdir -p "$NONE_POOL"
idx=0
link_ep() {
  local src="$1"
  local dst="$NONE_POOL/episode_$(printf '%05d' "$idx").npz"
  ln -sfn "$(cd "$(dirname "$src")" && pwd)/$(basename "$src")" "$dst"
  idx=$((idx + 1))
}
# deterministic order
while IFS= read -r f; do link_ep "$f"; done < <(ls "$NONE_D"/episode_*.npz | sort)
if [[ -d "$NONE_OLD" ]]; then
  while IFS= read -r f; do link_ep "$f"; done < <(ls "$NONE_OLD"/episode_*.npz | sort)
fi
# lightweight summary for mix ranker (d_end unknown → 99; still usable)
python3 - <<PY
import json
from pathlib import Path
pool = Path("$NONE_POOL")
eps = [{"file": p.name, "d_end_m_gt": 0.5, "collided": False, "assist": "none"} for p in sorted(pool.glob("episode_*.npz"))]
(pool / "collection_summary.json").write_text(json.dumps({
  "protocol": "e2i_e_none_pool",
  "n_collected": len(eps),
  "n_usable": len(eps),
  "assist": "none",
  "note": "Union of none_near_d + none_near for E3; synthetic d_end for ranker",
  "episodes": eps,
}, indent=2) + "\n")
print(f"none_pool={pool} n={len(eps)}")
PY

$AERIAL_PY experiments/aerial/scripts/indoor_build_e2i_a_mix.py \
  --out "$MIX" --b1 "$NONE_POOL" --b2 "$FIXTURE" \
  --total "$TOTAL" --b1-frac "$B1_FRAC" --b2-frac "$B2_FRAC" --old-frac 0.0 \
  --seed 91 \
  2>&1 | tee -a "$LOG"

# stamp protocol as e2i_e_mix + fixture ratio gate
$AERIAL_PY - <<PY
import json
from pathlib import Path
mix = Path("$MIX")
meta_path = mix / "mix_meta.json"
meta = json.loads(meta_path.read_text())
counts = meta.get("counts") or {}
n_b1 = int(counts.get("b1") or 0)
n_b2 = int(counts.get("b2") or 0)
n = n_b1 + n_b2
fix_frac = (n_b2 / n) if n else 1.0
meta["protocol"] = "e2i_e_mix"
meta["r06"] = "abandoned"
meta["fixture_frac"] = round(fix_frac, 4)
meta["sources"] = {
  "b1_none_pool": "$NONE_POOL",
  "b1_none_d": "$NONE_D",
  "b1_none_old": "$NONE_OLD",
  "b2_fixture_hard": "$FIXTURE",
}
meta_path.write_text(json.dumps(meta, indent=2) + "\n")
man = json.loads((mix / "manifest.json").read_text())
man.setdefault("meta", {})["protocol"] = "e2i_e_mix"
man["meta"]["fixture_frac"] = round(fix_frac, 4)
man["meta"]["r06"] = "abandoned"
(mix / "manifest.json").write_text(json.dumps(man, indent=2) + "\n")
print(json.dumps({"total": n, "b1_none": n_b1, "b2_fixture": n_b2, "fixture_frac": round(fix_frac, 4), "gate_fixture_le_25": fix_frac <= 0.2500001}, indent=2))
if fix_frac > 0.2500001:
  raise SystemExit(f"fixture_frac {fix_frac:.3f} > 0.25")
PY

echo "[e3] mix ready → $MIX $(date -Is)" | tee -a "$LOG"
