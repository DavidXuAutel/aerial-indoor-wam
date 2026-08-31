#!/usr/bin/env bash
# One-time: configure cursor-125 → H100 SSH for TZ-3Z branch (run ON 125).
#
#   export H100_PASS='…'   # do not commit
#   bash experiments/aerial/scripts/setup_h100_ssh_from_125.sh
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/aerial-wam-v2")"
cd "$ROOT"

H100_USER="${H100_USER:-a25689}"
H100_HOST="${H100_HOST:-10.239.121.26}"
H100_PORT="${H100_PORT:-31126}"
H100_REPO="${H100_REPO:-/home/a25689/aerial-wam-v2}"
KEY="${H100_SSH_KEY:-$HOME/.ssh/id_ed25519_aerial_h100}"
ENV_OUT="${ROOT}/experiments/aerial/scripts/env_h100_from_125.sh"

if [[ -z "${H100_PASS:-}" ]]; then
  echo "ERROR: set H100_PASS (not stored in git)" >&2
  exit 1
fi

if ! command -v sshpass >/dev/null 2>&1; then
  echo "[setup-h100] installing sshpass ..."
  sudo apt-get update -qq && sudo apt-get install -y -qq sshpass
fi

mkdir -p "$HOME/.ssh"
chmod 700 "$HOME/.ssh"
if [[ ! -f "$KEY" ]]; then
  ssh-keygen -t ed25519 -N "" -f "$KEY" -C "aerial-125-to-h100"
fi

TARGET="${H100_USER}@${H100_HOST}"
echo "[setup-h100] probing ${TARGET}:${H100_PORT} ..."
sshpass -p "$H100_PASS" ssh \
  -o StrictHostKeyChecking=accept-new \
  -o PreferredAuthentications=password \
  -o PubkeyAuthentication=no \
  -o NumberOfPasswordPrompts=1 \
  -p "$H100_PORT" "$TARGET" "echo H100_OK && hostname"

echo "[setup-h100] installing pubkey ..."
sshpass -p "$H100_PASS" ssh-copy-id \
  -o StrictHostKeyChecking=accept-new \
  -o PreferredAuthentications=password \
  -o PubkeyAuthentication=no \
  -i "$KEY" -p "$H100_PORT" "$TARGET"

echo "[setup-h100] passwordless check ..."
REMOTE_HOME=$(ssh -i "$KEY" -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new \
  -p "$H100_PORT" "$TARGET" 'echo "$HOME"')
for candidate in "${H100_REPO}" "${REMOTE_HOME}/aerial-wam-v2" "${REMOTE_HOME}/aerial-rl-skeleton"; do
  if ssh -i "$KEY" -o IdentitiesOnly=yes -p "$H100_PORT" "$TARGET" "test -d ${candidate}" 2>/dev/null; then
    H100_REPO="${candidate}"
    break
  fi
done
ssh -i "$KEY" -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new \
  -p "$H100_PORT" "$TARGET" "echo KEY_OK && test -d ${H100_REPO} && echo REPO_OK=${H100_REPO} || echo REPO_MISSING"

cat > "$ENV_OUT" <<EOF
# Local only — gitignored. Sourced by v4_three_zone_branch.sh on 125.
export H100_USER=${H100_USER}
export H100_HOST=${H100_HOST}
export H100_PORT=${H100_PORT}
export H100_REPO=${H100_REPO}
export H100_SSH_KEY=${KEY}
export H100_PASS='${H100_PASS}'
EOF
chmod 600 "$ENV_OUT"

echo "[setup-h100] wrote ${ENV_OUT}"
echo "[setup-h100] DONE — run: source experiments/aerial/scripts/env_4090.sh && MODE=eval bash experiments/aerial/scripts/v4_three_zone_branch.sh"
