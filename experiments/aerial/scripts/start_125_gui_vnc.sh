#!/usr/bin/env bash
# Start/stop localhost x11vnc against the existing GNOME session on 125 (:1).
# Access from Mac via SSH tunnel (see printed instructions). Never expose 5901 publicly.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
mkdir -p logs
ACTION="${1:-start}"
DISPLAY_NUM="${DISPLAY_NUM:-:1}"
RFBPORT="${RFBPORT:-5901}"
XAUTH="${XAUTH:-/run/user/1000/gdm/Xauthority}"
LOG=logs/x11vnc_125.log
PIDFILE=logs/x11vnc_125.pid

if [[ ! -S /tmp/.X11-unix/X${DISPLAY_NUM#:} ]]; then
  echo "ERROR: no X socket for $DISPLAY_NUM — is GNOME logged in on seat0?"
  exit 1
fi
if [[ ! -f "$XAUTH" ]]; then
  XAUTH="$HOME/.Xauthority"
fi

stop_vnc() {
  if [[ -f "$PIDFILE" ]]; then
    kill "$(cat "$PIDFILE")" 2>/dev/null || true
    rm -f "$PIDFILE"
  fi
  pkill -f "x11vnc.*rfbport ${RFBPORT}" 2>/dev/null || true
  echo "x11vnc stopped"
}

case "$ACTION" in
  stop)
    stop_vnc
    exit 0
    ;;
  status)
    pgrep -af "x11vnc.*rfbport ${RFBPORT}" | grep -v pgrep || echo "not running"
    ss -ltn | grep "${RFBPORT}" || echo "port ${RFBPORT} closed"
    exit 0
    ;;
  start)
    stop_vnc
    # -localhost: only reachable via SSH tunnel
    # -nopw: tunnel already authenticates; add -passwdfile if you want a 2nd factor
    nohup x11vnc \
      -display "$DISPLAY_NUM" \
      -auth "$XAUTH" \
      -rfbport "$RFBPORT" \
      -localhost \
      -shared \
      -forever \
      -noxdamage \
      -wait 10 \
      -defer 10 \
      -o "$ROOT/$LOG" \
      >/dev/null 2>&1 &
    echo $! >"$PIDFILE"
    sleep 1
    if ! kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
      echo "x11vnc failed — see $LOG"
      exit 1
    fi
    cat <<EOF
============================================================
  125 GUI ready (GNOME $DISPLAY_NUM via x11vnc)
  Port: 127.0.0.1:${RFBPORT}  (localhost only)

  On your Mac (keep this tunnel open):
    ssh -o ProxyJump=a26125-110-public \\
      -i ~/.ssh/cursor_webbridge_125 -o IdentitiesOnly=yes \\
      -L ${RFBPORT}:127.0.0.1:${RFBPORT} -N yao@10.229.20.125

  Then open VNC Viewer →  localhost:${RFBPORT}

  In the VNC desktop, open Terminal and run teleop:
    cd ~/aerial-indoor-wam
    source experiments/aerial/scripts/env_4090.sh
    export DISPLAY=${DISPLAY_NUM}
    export XAUTHORITY=${XAUTH}
    bash experiments/aerial/scripts/run_e2i_e_teleop_r06.sh
============================================================
EOF
    ;;
  *)
    echo "usage: $0 {start|stop|status}"
    exit 2
    ;;
esac
