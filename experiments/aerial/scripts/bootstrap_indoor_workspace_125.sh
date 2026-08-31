#!/usr/bin/env bash
# Bootstrap independent indoor workspace on 125 (separate from aerial-wam-v2 / phase2).
# Run ON 125, or via: ssh ... 'bash -s' < this_script
set -euo pipefail

INDOOR_ROOT="${INDOOR_ROOT:-/home/yao/aerial-indoor-wam}"
PHASE2_ROOT="${PHASE2_ROOT:-/home/yao/aerial-wam-v2}"

echo "[indoor-ws] INDOOR_ROOT=$INDOOR_ROOT"
echo "[indoor-ws] PHASE2_ROOT=$PHASE2_ROOT (read-only share for ckpts/data)"

if [[ ! -d "$PHASE2_ROOT" ]]; then
  echo "missing phase2 tree $PHASE2_ROOT" >&2
  exit 1
fi

mkdir -p "$INDOOR_ROOT"

# If empty or no .git, seed from phase2 tree then overlay will come from Mac scp/rsync
if [[ ! -f "$INDOOR_ROOT/experiments/aerial/RUNBOOK_indoor_0xm.md" ]]; then
  echo "[indoor-ws] seeding code skeleton from phase2 (one-time rsync, exclude huge artifacts)"
  rsync -a --delete \
    --exclude '.git' \
    --exclude 'artifacts/**' \
    --exclude 'experiments/aerial/rl/artifacts/**' \
    --exclude '**/__pycache__' \
    --exclude '.venv' \
    --exclude 'runs' \
    "$PHASE2_ROOT/" "$INDOOR_ROOT/"
fi

mkdir -p \
  "$INDOOR_ROOT/artifacts" \
  "$INDOOR_ROOT/artifacts/videos" \
  "$INDOOR_ROOT/experiments/aerial/rl/artifacts" \
  "$INDOOR_ROOT/docs/handover"

# Shared heavy assets (do NOT duplicate)
link_or_echo() {
  local src="$1" dst="$2"
  if [[ -e "$dst" || -L "$dst" ]]; then
    echo "  keep $dst"
    return
  fi
  if [[ -e "$src" ]]; then
    ln -s "$src" "$dst"
    echo "  link $dst -> $src"
  else
    echo "  skip missing $src"
  fi
}

echo "[indoor-ws] linking shared ckpts / annotation from phase2"
# annotation
link_or_echo "$PHASE2_ROOT/artifacts/seen_airsim16_m1a20.json" \
  "$INDOOR_ROOT/artifacts/seen_airsim16_m1a20.json"

# common ckpt dirs used by indoor demos
for d in \
  wm_ckpt_d_full_20260828 \
  v4_ac_ckpt_step_e_20260828 \
  depth_ckpt_p45mid_s8j_20260825 \
  wm_ckpt_coll_full_20260827 \
  depth_ckpt_p45_merged_20260821
  do
  link_or_echo "$PHASE2_ROOT/experiments/aerial/rl/artifacts/$d" \
    "$INDOOR_ROOT/experiments/aerial/rl/artifacts/$d"
done

# also link top-level rl artifacts catch-all if indoor paths expect flat files
if [[ -d "$PHASE2_ROOT/experiments/aerial/rl/artifacts" ]]; then
  # soft: ensure PYTHON can find sibling ckpts via INDOOR tree only
  true
fi

# Marker so agents know this is NOT phase2
cat > "$INDOOR_ROOT/WORKSPACE_IDENTITY.md" << 'EOF'
# Workspace identity

**This tree is `aerial-indoor-wam` — indoor mainline only.**

- Do **not** run phase-2 long-horizon work here.
- Phase-2 / outdoor imagination lives in `/home/yao/aerial-wam-v2`.
- Shared: AirSim renderer, Python venv, symlinked ckpts/annotation only.
- Authority: `experiments/aerial/RUNBOOK_indoor_0xm.md`
EOF

# env helper: prefer this repo root
if [[ -f "$INDOOR_ROOT/experiments/aerial/scripts/env_4090.sh" ]]; then
  # ensure default ROOT fallback mentions indoor when sourced from this tree (git root)
  true
fi

echo "[indoor-ws] DONE. Agent workspace must be: $INDOOR_ROOT"
ls -la "$INDOOR_ROOT/WORKSPACE_IDENTITY.md" "$INDOOR_ROOT/experiments/aerial/RUNBOOK_indoor_0xm.md" 2>&1 | head -10
