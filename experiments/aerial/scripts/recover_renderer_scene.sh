#!/bin/bash
# Start / stop AirSim with a selectable scene under aerial_airsim_persistent/scene/.
#
# Usage:
#   bash experiments/aerial/scripts/recover_renderer_scene.sh blocks
#   bash experiments/aerial/scripts/recover_renderer_scene.sh building99
#   bash experiments/aerial/scripts/recover_renderer_scene.sh outdoor   # env_airsim_16
#   bash experiments/aerial/scripts/recover_renderer_scene.sh stop
#
# Env:
#   AIRSIM_PERSISTENT  default /home/yao/aerial_airsim_persistent
#   AIRSIM_PORT        default 41451 (informational; set in settings)
set -euo pipefail

ROOT="${AIRSIM_PERSISTENT:-/home/yao/aerial_airsim_persistent}"
PIDFILE="$ROOT/airsim.pid"
LOG="$ROOT/airsim.log"
SETTINGS_DIR="$ROOT/AirSim"
SCENE_ARG="${1:-blocks}"

resolve_scene() {
  case "$1" in
    stop) echo stop; return ;;
    outdoor|env_airsim_16|airvln)
      echo "$ROOT/scene/env_airsim_16/LinuxNoEditor"
      ;;
    blocks|Blocks)
      # v1.8.0-linux unzip layout varies; find Blocks.sh
      local d
      d=$(find "$ROOT/scene/Blocks" -name 'Blocks.sh' 2>/dev/null | head -1)
      if [ -z "$d" ]; then
        echo "Blocks.sh not found under $ROOT/scene/Blocks" >&2
        exit 1
      fi
      dirname "$d"
      ;;
    building99|Building_99|building_99)
      local d
      d=$(find "$ROOT/scene/Building_99" -name 'Building_99.sh' -o -name 'Building99.sh' 2>/dev/null | head -1)
      if [ -z "$d" ]; then
        echo "Building_99.sh not found under $ROOT/scene/Building_99" >&2
        exit 1
      fi
      dirname "$d"
      ;;
    *)
      echo "unknown scene '$1' (outdoor|blocks|building99|stop)" >&2
      exit 1
      ;;
  esac
}

stop_renderer() {
  [ -f "$PIDFILE" ] || return 0
  local pid
  pid=$(cat "$PIDFILE" 2>/dev/null || true)
  if [ -n "${pid:-}" ] && kill -0 "$pid" 2>/dev/null; then
    kill -- "-$pid" 2>/dev/null || kill "$pid" 2>/dev/null || true
    sleep 3
    kill -9 "$pid" 2>/dev/null || true
  fi
  # also kill leftover Shipping binaries on 41451 consumers
  pkill -f 'AirVLN-Linux-Shipping|Blocks/Binaries|Building_99/Binaries|Building99/Binaries' 2>/dev/null || true
  rm -f "$PIDFILE"
}

if [ "$SCENE_ARG" = "stop" ]; then
  stop_renderer
  echo "stopped"
  exit 0
fi

SCENE=$(resolve_scene "$SCENE_ARG")
LAUNCH=""
if [ -x "$SCENE/start.sh" ]; then
  LAUNCH=./start.sh
elif [ -x "$SCENE/Blocks.sh" ]; then
  LAUNCH=./Blocks.sh
elif [ -x "$SCENE/Building_99.sh" ]; then
  LAUNCH=./Building_99.sh
elif [ -x "$SCENE/Building99.sh" ]; then
  LAUNCH=./Building99.sh
else
  echo "no launcher in $SCENE" >&2
  ls -la "$SCENE" >&2 || true
  exit 1
fi

# Indoor scenes use dedicated settings (vehicle=drone_1, camera=0).
mkdir -p "$SETTINGS_DIR" /home/yao/Documents/AirSim
case "$SCENE_ARG" in
  outdoor|env_airsim_16|airvln)
    ln -sfn "$SETTINGS_DIR/settings.json" /home/yao/Documents/AirSim/settings.json
    ;;
  *)
    if [ -f "$SETTINGS_DIR/settings_indoor.json" ]; then
      ln -sfn "$SETTINGS_DIR/settings_indoor.json" /home/yao/Documents/AirSim/settings.json
    else
      ln -sfn "$SETTINGS_DIR/settings.json" /home/yao/Documents/AirSim/settings.json
    fi
    ;;
esac

export VK_ICD_FILENAMES="${VK_ICD_FILENAMES:-/usr/share/vulkan/icd.d/nvidia_icd.json}"
nvidia-smi --query-gpu=name,driver_version --format=csv,noheader || true

# ON_SCREEN=1 → show UE window on local GNOME (:1). Default remains offscreen for headless agents.
ON_SCREEN="${ON_SCREEN:-0}"
EXTRA_FLAGS=(-Vulkan -windowed -ResX=1920 -ResY=1080 -nosound)
if [[ "$ON_SCREEN" == "1" ]]; then
  export DISPLAY="${DISPLAY:-:1}"
  if [[ -z "${XAUTHORITY:-}" ]]; then
    if [[ -f /run/user/1000/gdm/Xauthority ]]; then
      export XAUTHORITY=/run/user/1000/gdm/Xauthority
    elif [[ -f "$HOME/.Xauthority" ]]; then
      export XAUTHORITY="$HOME/.Xauthority"
    fi
  fi
  echo "ON_SCREEN=1 DISPLAY=$DISPLAY XAUTHORITY=${XAUTHORITY:-none}"
else
  EXTRA_FLAGS+=(-RenderOffScreen)
fi

stop_renderer
cd "$SCENE"
nohup setsid env DISPLAY="${DISPLAY:-}" XAUTHORITY="${XAUTHORITY:-}" "$LAUNCH" \
  "${EXTRA_FLAGS[@]}" >"$LOG" 2>&1 </dev/null &
pid=$!
echo "$pid" >"$PIDFILE"

sleep 20
if ! kill -0 "$pid" 2>/dev/null; then
  echo "AirSim failed to stay running; inspect $LOG" >&2
  tail -40 "$LOG" >&2 || true
  exit 1
fi

echo "scene=$SCENE_ARG launcher=$LAUNCH pid=$pid cwd=$SCENE log=$LOG"
