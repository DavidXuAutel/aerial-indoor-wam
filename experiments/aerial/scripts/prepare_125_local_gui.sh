#!/usr/bin/env bash
# Prepare LOCAL GUI on 125 for teleop (no VNC / no remote desktop).
# - Ensures GNOME :1 is alive
# - Unlocks screensaver if possible
# - Restarts Building_99 ON_SCREEN on the local monitor
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"

export DISPLAY="${DISPLAY:-:1}"
if [[ -z "${XAUTHORITY:-}" ]]; then
  if [[ -f /run/user/1000/gdm/Xauthority ]]; then
    export XAUTHORITY=/run/user/1000/gdm/Xauthority
  elif [[ -f "$HOME/.Xauthority" ]]; then
    export XAUTHORITY="$HOME/.Xauthority"
  fi
fi

if [[ ! -S /tmp/.X11-unix/X1 ]]; then
  echo "ERROR: GNOME/X :1 not running. Log in locally on 125 seat0 first."
  exit 1
fi

echo "[gui] DISPLAY=$DISPLAY XAUTHORITY=${XAUTHORITY:-none}"
xdpyinfo >/dev/null
xrandr | head -8 || true

# Best-effort unlock / wake
loginctl unlock-session 8 2>/dev/null || true
DISPLAY=$DISPLAY XAUTHORITY=$XAUTHORITY xset s reset 2>/dev/null || true
DISPLAY=$DISPLAY XAUTHORITY=$XAUTHORITY xset dpms force on 2>/dev/null || true
DISPLAY=$DISPLAY XAUTHORITY=$XAUTHORITY gnome-screensaver-command -d 2>/dev/null || true

# Stop any leftover auto/vnc noise for a clean teleop seat
pkill -f indoor_r06_auto_avoid_collect.py 2>/dev/null || true
pkill -f "x11vnc.*rfbport" 2>/dev/null || true

echo "[gui] restart Building_99 ON_SCREEN=1 ..."
ON_SCREEN=1 DISPLAY=$DISPLAY XAUTHORITY=$XAUTHORITY \
  bash experiments/aerial/scripts/recover_renderer_scene.sh building99

sleep 3
if ss -ltn | grep -q 41451; then
  echo "[gui] AirSim 41451 OK"
else
  echo "[gui] WARN: 41451 not listening yet — check renderer log"
fi

cat <<EOF
============================================================
  125 LOCAL GUI ready (no remote desktop)
  - Monitor: DP-0 1920x1080 on GNOME :1
  - Building_99 should be a visible window on that screen

  Sit at 125, open Terminal on the desktop, run:
    cd ~/aerial-indoor-wam
    source experiments/aerial/scripts/env_4090.sh
    export DISPLAY=:1
    export XAUTHORITY=/run/user/1000/gdm/Xauthority
    bash experiments/aerial/scripts/run_e2i_e_teleop_r06.sh

  Focus teleop_ego window: START/END buttons + on-screen keys.
============================================================
EOF
