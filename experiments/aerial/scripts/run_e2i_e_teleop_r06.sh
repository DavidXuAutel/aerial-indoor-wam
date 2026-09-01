#!/usr/bin/env bash
# E2i.E — optional human teleop on 125 LOCAL seat (REACHABLE open goals).
# R06 NW goal ABANDONED (furniture / clear~0.17m). Do NOT nohup / plain SSH.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source experiments/aerial/scripts/env_4090.sh
export AIRSIM_CAMERA=0 AIRSIM_VEHICLE=drone_1
# Local seat at 125 / VNC into GNOME :1
if [[ -z "${DISPLAY:-}" ]]; then
  if [[ -S /tmp/.X11-unix/X1 ]]; then
    export DISPLAY=:1
  else
    export DISPLAY=:0
  fi
fi
if [[ -z "${XAUTHORITY:-}" ]]; then
  if [[ -f /run/user/1000/gdm/Xauthority ]]; then
    export XAUTHORITY=/run/user/1000/gdm/Xauthority
  elif [[ -f "$HOME/.Xauthority" ]]; then
    export XAUTHORITY="$HOME/.Xauthority"
  fi
fi

STAMP="${STAMP:-20260901}"
OUT="${OUT:-experiments/aerial/rl/artifacts/dataset_indoor_b99_teleop_reachable_e_${STAMP}}"
ANN="${ANN:-artifacts/building99_indoor_teleop_reachable.json}"
ROUTE_IDX="${ROUTE_IDX:-0}"
SUCCESS_DIST="${SUCCESS_DIST:-0.25}"
MIN_USABLE="${MIN_USABLE:-8}"
GOAL_PULLBACK_M="${GOAL_PULLBACK_M:-0}"

test -f "$ANN"
if ! ss -ltn | grep -q 41451; then
  echo "AirSim 41451 not up — start Building_99 renderer first"
  exit 1
fi

if [[ -z "${DISPLAY:-}" ]]; then
  echo "ERROR: DISPLAY unset — sit at 125 GNOME and export DISPLAY=:1"
  exit 1
fi

cat <<EOF
============================================================
  TELEOP @ 125 — REACHABLE open goals (R06 ABANDONED)
  - Route: $ANN idx=$ROUTE_IDX
  - Window: opencv_control (DISPLAY=$DISPLAY)
  Out: $OUT   target usable>=${MIN_USABLE}
============================================================
EOF

exec $AERIAL_PY experiments/aerial/scripts/indoor_teleop_collect.py \
  --annotation "$ANN" \
  --route-idx "$ROUTE_IDX" \
  --success-dist "$SUCCESS_DIST" \
  --min-usable "$MIN_USABLE" \
  --goal-pullback-m "$GOAL_PULLBACK_M" \
  --bc-tag teleop_reachable_e2i_e \
  --out "$OUT"
