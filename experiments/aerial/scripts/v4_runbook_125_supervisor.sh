#!/usr/bin/env bash
# Keep relaunching cursor-agent until RUNBOOK reaches P8 / BLOCKED / §6 stop.
set -euo pipefail
REPO="${REPO:-$HOME/aerial-wam-v2}"
AGENT="${AGENT:-$HOME/.local/bin/agent}"
MODEL="${MODEL:-composer-2.5-fast}"
PROMPT_FILE="$REPO/artifacts/V4_RUNBOOK_125_PROMPT.md"
STATUS_FILE="$REPO/docs/handover/V4_RUNBOOK_125_STATUS.md"
LOG_DIR="$REPO/logs"
mkdir -p "$LOG_DIR"
cd "$REPO"

terminal_state() {
  [[ -f "$STATUS_FILE" ]] || return 1
  # P8 done
  if grep -qE '\[x\].*P8|P8.*(DONE|complete|✅)|state:.*P8.*(DONE|complete)' "$STATUS_FILE"; then
    echo "P8_DONE"
    return 0
  fi
  if grep -qiE 'state:.*\*\*BLOCKED\*\*|state:.*BLOCKED' "$STATUS_FILE"; then
    echo "BLOCKED"
    return 0
  fi
  if grep -qiE 'P7-accept.*S_blocked.*FAIL|§6 stop|下车站' "$STATUS_FILE" && \
     grep -qiE 'do not enter P8|不进 P8|no P8' "$STATUS_FILE"; then
    echo "SECTION6_STOP"
    return 0
  fi
  return 1
}

wait_for_pid() {
  local pid="$1"
  while kill -0 "$pid" 2>/dev/null; do
    sleep 30
  done
}

echo "[supervisor] start $(date -Iseconds) tip=$(git rev-parse --short HEAD)"
ROUND=0
while true; do
  if ST=$(terminal_state); then
    echo "[supervisor] terminal=$ST — exiting supervisor"
    exit 0
  fi
  ROUND=$((ROUND + 1))
  git fetch origin >/dev/null 2>&1 || true
  git reset --hard origin/main >/dev/null 2>&1 || true
  OUT="$LOG_DIR/v4_runbook_125_supervise_$(date +%Y%m%d_%H%M%S)_r${ROUND}.out"
  echo "[supervisor] round=$ROUND launching agent → $OUT"
  nohup "$AGENT" --print --force --model "$MODEL" "$(cat "$PROMPT_FILE")" >"$OUT" 2>&1 &
  PID=$!
  echo "$PID" > "$LOG_DIR/v4_runbook_125_supervisor_agent.pid"
  echo "[supervisor] agent_pid=$PID"
  wait_for_pid "$PID"
  echo "[supervisor] agent_pid=$PID exited $(date -Iseconds)"
  if ST=$(terminal_state); then
    echo "[supervisor] terminal=$ST after agent exit — done"
    exit 0
  fi
  echo "[supervisor] not terminal yet — sleep 15s then relaunch"
  sleep 15
done
