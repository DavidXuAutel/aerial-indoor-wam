#!/usr/bin/env bash
# Check whether :41451 is free for indoor E2i work (Building_99, no Phase-2).
# Exit 0 = ready to switch/start building99; Exit 1 = busy (print reason).
set -euo pipefail
PORT="${AIRSIM_PORT:-41451}"

phase2=$(pgrep -af 'wam_phase2_traj_forensics|wam_phase2_long_eval' 2>/dev/null | grep -v check_airsim || true)
indoor_py=$(pgrep -af 'indoor_loop_collect|indoor_mainline_baseline|indoor_building99_fixture|run_e2i' 2>/dev/null | grep python | grep -v check_airsim || true)
b99=$(pgrep -af 'Building_99/Binaries' 2>/dev/null || true)
outdoor=$(pgrep -af 'env_airsim_16|AirVLN-Linux' 2>/dev/null | grep -v check_airsim || true)
listening=0
ss -ltn 2>/dev/null | grep -q ":${PORT} " && listening=1

echo "[check_indoor] port_${PORT}_listening=$listening"
echo "[check_indoor] phase2=$([[ -n "$phase2" ]] && echo RUNNING || echo none)"
echo "[check_indoor] indoor_python=$([[ -n "$indoor_py" ]] && echo RUNNING || echo none)"
echo "[check_indoor] building99=$([[ -n "$b99" ]] && echo UP || echo none)"
echo "[check_indoor] outdoor_renderer=$([[ -n "$outdoor" ]] && echo UP || echo none)"

if [[ -n "$phase2" || -n "$indoor_py" ]]; then
  echo "[check_indoor] BLOCKED: competing eval/collect job"
  echo "$phase2$indoor_py" | head -5 | sed 's/^/  /'
  exit 1
fi

if [[ "$listening" -eq 1 && -n "$outdoor" && -z "$b99" ]]; then
  echo "[check_indoor] BLOCKED: outdoor scene owns :${PORT} — need recover_renderer_scene.sh building99 (stops outdoor)"
  echo "$outdoor" | head -2 | sed 's/^/  /'
  exit 1
fi

if [[ "$listening" -eq 1 && -n "$b99" ]]; then
  echo "[check_indoor] READY: Building_99 on :${PORT}, no competing jobs"
  exit 0
fi

if [[ "$listening" -eq 0 ]]; then
  echo "[check_indoor] READY: port free — run recover_renderer_scene.sh building99"
  exit 0
fi

echo "[check_indoor] READY: port up, unknown scene — verify manually before indoor work"
exit 0
