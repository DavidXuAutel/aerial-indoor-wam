#!/usr/bin/env bash
# Sync aerial-indoor-wam code + FT deps to H100 (run ON 125).
set -euo pipefail

INDOOR_ROOT="${INDOOR_ROOT:-/home/yao/aerial-indoor-wam}"
PHASE2_ROOT="${PHASE2_ROOT:-/home/yao/aerial-wam-v2}"
H100="${H100:-h100-25}"
H100_REPO="${H100_REPO:-~/aerial-indoor-wam}"

echo "[indoor-ft-sync] INDOOR_ROOT=$INDOOR_ROOT -> ${H100}:${H100_REPO}"

ssh "$H100" "mkdir -p ${H100_REPO}/experiments/aerial/rl/artifacts ${H100_REPO}/artifacts ${H100_REPO}/logs ${H100_REPO}/configs"

# Code + configs (exclude huge local artifacts)
tar -C "$INDOOR_ROOT" -cf - \
  --exclude='.git' \
  --exclude='**/__pycache__' \
  --exclude='artifacts/videos' \
  --exclude='experiments/aerial/rl/artifacts/*.pt' \
  --exclude='experiments/aerial/rl/artifacts/dataset_*' \
  configs experiments docs WORKSPACE_IDENTITY.md README.md 2>/dev/null \
  | ssh "$H100" "tar xf - -C ${H100_REPO}"

# Symlink heavy assets from phase2 tree on H100 (same layout as 125 bootstrap)
ssh "$H100" "bash -s" <<EOF
set -euo pipefail
P2="\${PHASE2_ROOT:-\$HOME/aerial-wam-v2}"
R="${H100_REPO}"
link() {
  local src="\$1" dst="\$2"
  mkdir -p "\$(dirname "\$dst")"
  if [[ -e "\$src" ]]; then ln -sfn "\$src" "\$dst"; echo "  link \$dst"; fi
}
link "\$P2/artifacts/seen_airsim16_m1a20.json" "\$R/artifacts/seen_airsim16_m1a20.json"
for d in wm_ckpt_d_full_20260828 v4_ac_ckpt_step_e_20260828 dataset_v0_d_full_20260828; do
  link "\$P2/experiments/aerial/rl/artifacts/\$d" "\$R/experiments/aerial/rl/artifacts/\$d"
done
echo "[indoor-ft-sync] H100 links OK under \$R"
EOF

echo "[indoor-ft-sync] DONE"
