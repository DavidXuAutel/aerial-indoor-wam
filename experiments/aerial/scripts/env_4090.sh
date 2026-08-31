#!/usr/bin/env bash
# Aerial WAM — 4090 collection / loopback probe environment.
# SOURCE on the 4090 renderer host before running collect_v1.sh or
# collect_dataset.py against the local AirSim RPC (127.0.0.1:41451).
#
#   source experiments/aerial/scripts/env_4090.sh
#
# Renderer lifecycle is separate — see ~/aerial_airsim_persistent/recover_renderer.sh
# (persistent Unreal scene, NOT OpenFly env_bridge on this host).
set -euo pipefail

_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_INDOOR_ROOT="$(cd "$_SCRIPT_DIR/../../.." && pwd)"
ROOT="${REPO_ROOT:-$(git -C "$_INDOOR_ROOT" rev-parse --show-toplevel 2>/dev/null || echo "$_INDOOR_ROOT")}"
export REPO_ROOT="$ROOT"
export PYTHONPATH="$ROOT:${PYTHONPATH:-}"
export PYTHON_BIN="${PYTHON_BIN:-/home/yao/sim_verify/.venv/bin/python}"
export AERIAL_PY="$PYTHON_BIN"
export AIRSIM_HOST=127.0.0.1
export AIRSIM_PORT=41451
export AIRSIM_CAMERA=front_custom
export AIRSIM_VEHICLE=drone_1
export ANNOTATION="${ANNOTATION:-$ROOT/artifacts/seen_airsim16_m1a20.json}"
export AERIAL_PERSIST_ROOT="${AERIAL_PERSIST_ROOT:-/home/yao/aerial_airsim_persistent}"

echo "[env_4090] REPO_ROOT=$REPO_ROOT"
echo "[env_4090] PYTHON_BIN=$PYTHON_BIN ($("$PYTHON_BIN" --version 2>&1))"
echo "[env_4090] ANNOTATION=$ANNOTATION"
echo "[env_4090] renderer: $AERIAL_PERSIST_ROOT/recover_renderer.sh"
