#!/usr/bin/env bash
# One-shot: recover AirSim if needed, wait, then TZ-3Z near-band collect+merge+eval on 125.
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME/aerial-wam-v2")"
cd "$ROOT"
LOG="${LOG:-logs/v4_three_zone_near_20260823d_retry2.log}"
exec >>"$LOG" 2>&1

_airsim_code() {
  curl -s -o /dev/null -w "%{http_code}" --connect-timeout 3 --max-time 5 \
    http://127.0.0.1:41451 2>/dev/null || echo 0
}

echo "[retry2] $(date -Iseconds) start (pid=$$)"
code="$(_airsim_code)"
echo "initial airsim=$code"
if [[ "$code" != "200" && "$code" != "401" ]]; then
  echo "[retry2] $(date -Iseconds) recover_renderer"
  bash ~/aerial_airsim_persistent/recover_renderer.sh &
  rec_pid=$!
  echo "recover_renderer pid=$rec_pid"
fi

for i in $(seq 1 60); do
  code="$(_airsim_code)"
  echo "try $i airsim=$code"
  if [[ "$code" == "200" || "$code" == "401" ]]; then
    break
  fi
  sleep 15
done

code="$(_airsim_code)"
if [[ "$code" != "200" && "$code" != "401" ]]; then
  echo "[retry2] $(date -Iseconds) FAIL: airsim not ready (code=$code)"
  exit 1
fi

# shellcheck disable=SC1091
source experiments/aerial/scripts/env_4090.sh
echo "[retry2] $(date -Iseconds) all_near"
STAMP="${STAMP:-20260823_full}"
NEAR_STAMP="${NEAR_STAMP:-20260823d}"
PER_LAYER="${PER_LAYER:-12}"
ONLY_LAYER="${ONLY_LAYER:-blocked}"
PROBE_NEAR_M="${PROBE_NEAR_M:-5.0}"
export STAMP NEAR_STAMP PER_LAYER ONLY_LAYER PROBE_NEAR_M
MODE=all_near bash experiments/aerial/scripts/v4_three_zone_branch.sh
echo "[retry2] $(date -Iseconds) DONE"
