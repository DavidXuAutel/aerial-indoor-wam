#!/usr/bin/env bash
# Wait until AirSim :41451 has no competing Python eval/collect clients.
# Usage: bash experiments/aerial/scripts/wait_airsim_idle.sh [--timeout-sec N]
set -euo pipefail
TIMEOUT="${1:-7200}"
if [[ "${1:-}" == "--timeout-sec" ]]; then
  TIMEOUT="${2:-7200}"
fi
PORT="${AIRSIM_PORT:-41451}"
PATTERN='wam_phase2_long_eval|indoor_loop_collect|indoor_mainline_baseline|indoor_multiwaypoint|indoor_lossless|indoor_two_phase'

echo "[wait_airsim] port=$PORT timeout=${TIMEOUT}s pattern=$PATTERN"
start=$(date +%s)
while true; do
  now=$(date +%s)
  if (( now - start > TIMEOUT )); then
    echo "[wait_airsim] TIMEOUT after ${TIMEOUT}s" >&2
    exit 1
  fi
  # competing python clients (exclude this wait script and cursor agent argv noise)
  comps=$(pgrep -af "$PATTERN" 2>/dev/null \
    | grep -v wait_airsim_idle \
    | grep -v '\.local/bin/agent' \
    | grep -v 'cursor-agent' \
    | grep -v "grep" || true)
  # only count real eval/collect runners (python/bash invoking scripts)
  if [[ -n "$comps" ]]; then
    comps=$(echo "$comps" | grep -E 'python|indoor_loop_collect|indoor_mainline|wam_phase2_long_eval' || true)
  fi
  # AirSim process listening
  listening=0
  if ss -lntp 2>/dev/null | grep -q ":${PORT} "; then
    listening=1
  elif netstat -lntp 2>/dev/null | grep -q ":${PORT} "; then
    listening=1
  fi
  if [[ -z "$comps" && "$listening" -eq 1 ]]; then
    echo "[wait_airsim] IDLE (no competing clients; port $PORT up) elapsed=$((now-start))s"
    exit 0
  fi
  n=$(echo "$comps" | grep -c . || true)
  echo "[wait_airsim] busy comps=$n listening=$listening elapsed=$((now-start))s"
  if [[ -n "$comps" ]]; then
    echo "$comps" | head -3 | sed 's/^/  /'
  fi
  sleep 30
done
