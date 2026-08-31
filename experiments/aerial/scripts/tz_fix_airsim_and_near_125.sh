#!/usr/bin/env bash
# Fix zombie AirSim on 125 and launch TZ-3Z all_near. Run ON 125.
set -u
LOG="${LOG:-$HOME/aerial-wam-v2/logs/v4_three_zone_near_20260823d_retry2.log}"
exec >>"$LOG" 2>&1

_airsim_up() {
  python3 -c "import socket;socket.create_connection(('127.0.0.1',41451),3).close()" 2>/dev/null && echo up || echo down
}

echo "[fix3] $(date -Iseconds) begin"
pkill -f tz_near_retry_125 2>/dev/null || true
pkill -f tz_fix_airsim_and_near_125 2>/dev/null || true
sleep 1

if [[ "$(_airsim_up)" != "up" ]]; then
  pkill -f "start.sh -Vulkan" 2>/dev/null || true
  pkill -f AirVLN-Linux-Shipping 2>/dev/null || true
  sleep 2
  fuser -k 41451/tcp 2>/dev/null || true
  sleep 2
  bash "$HOME/aerial_airsim_persistent/recover_renderer.sh" || true
fi

for i in $(seq 1 60); do
  st="$(_airsim_up)"
  echo "fix3_wait $i airsim=$st"
  [[ "$st" == "up" ]] && break
  sleep 10
done

if [[ "$(_airsim_up)" != "up" ]]; then
  echo "[fix3] FAIL airsim not reachable on :41451"; exit 1
fi

cd "$HOME/aerial-wam-v2"
# shellcheck disable=SC1091
source experiments/aerial/scripts/env_4090.sh
echo "[fix3] $(date -Iseconds) all_near"
STAMP=20260823_full NEAR_STAMP=20260823d PER_LAYER=12 ONLY_LAYER=blocked PROBE_NEAR_M=5.0 \
  MODE=all_near bash experiments/aerial/scripts/v4_three_zone_branch.sh
echo "[fix3] $(date -Iseconds) DONE"
