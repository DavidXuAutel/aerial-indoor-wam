#!/usr/bin/env bash
# Wait until 125 has no competing aerial jobs, then verify VIO frame-align.
#
# Phase A — offline OpenVINS (CPU; does NOT touch AirSim :41451)
# Phase B — closed-loop smoke (needs :41451 free of other clients)
#
# Usage:
#   nohup bash experiments/aerial/scripts/run_indoor_vio_align_when_idle.sh &
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source experiments/aerial/scripts/env_4090.sh 2>/dev/null || true

STAMP="${STAMP:-$(date +%Y%m%d_%H%M%S)}"
LOG="logs/indoor_vio_align_idle_${STAMP}.log"
mkdir -p logs artifacts
exec > >(tee -a "$LOG") 2>&1

POLL_S="${POLL_S:-30}"
LOAD_MAX="${LOAD_MAX:-12}"
IDLE_STREAK_NEED="${IDLE_STREAK_NEED:-2}"  # consecutive idle polls before start

echo "[vio_align_idle] start $(date -Is) poll=${POLL_S}s load_max=${LOAD_MAX}"

busy_procs() {
  pgrep -af 'indoor_mainline_baseline|indoor_loop_collect|run_e2i_|run_indoor_vio_closed|train_v4|wam_phase2|ov_euroc_offline|ov_stream_online' \
    2>/dev/null | grep -v "run_indoor_vio_align_when_idle\|pgrep\|grep" || true
}

load1() {
  awk '{print $1}' /proc/loadavg
}

is_idle() {
  local busy load
  busy="$(busy_procs)"
  if [[ -n "$busy" ]]; then
    echo "[vio_align_idle] busy procs:"
    echo "$busy" | head -8
    return 1
  fi
  load="$(load1)"
  python3 - <<PY
load=float("$load"); mx=float("$LOAD_MAX")
raise SystemExit(0 if load <= mx else 1)
PY
}

streak=0
while true; do
  if is_idle; then
    streak=$((streak + 1))
    echo "[vio_align_idle] idle streak $streak/$IDLE_STREAK_NEED load=$(load1) $(date -Is)"
    if [[ "$streak" -ge "$IDLE_STREAK_NEED" ]]; then
      break
    fi
  else
    streak=0
    echo "[vio_align_idle] waiting… load=$(load1) $(date -Is)"
  fi
  sleep "$POLL_S"
done

# --- env for OpenVINS ---
if [[ -f "${HOME}/src/open_vins/OPENVINS_BIN.env" ]]; then
  # shellcheck disable=SC1090
  source "${HOME}/src/open_vins/OPENVINS_BIN.env"
fi
export OPENVINS_BIN="${OPENVINS_BIN:-$ROOT/experiments/aerial/vio_probe/cpp/build/ov_euroc_offline}"
export OPENVINS_STREAM_BIN="${OPENVINS_STREAM_BIN:-$ROOT/experiments/aerial/vio_probe/cpp/build/ov_stream_online}"
test -x "$OPENVINS_BIN"

NPZ="${NPZ:-experiments/aerial/rl/artifacts/dataset_indoor_fixture_bc_e2f_20260830/episode_00000.npz}"
OUT_OFF="artifacts/vio_probe/ov_align_${STAMP}"
mkdir -p "$OUT_OFF"

echo "[vio_align_idle] PHASE A thrifty S2: hover IMU + gt-init + imu-only → $OUT_OFF"
python3 -m experiments.aerial.vio_probe.run_isolated_probe \
  --npz "$NPZ" \
  --out "$OUT_OFF" \
  --run-openvins --openvins-bin "$OPENVINS_BIN" \
  --gt-init --imu-only --imu-mode hover \
  | tee "$OUT_OFF/run.log"

python3 - <<PY
import json
from pathlib import Path
from experiments.aerial.vio_probe.frames import SIM_ATE_RMSE_MAX_M, SIM_CLOSED_D_HAT_MAX_M
p=Path("$OUT_OFF/summary.json")
d=json.loads(p.read_text()) if p.is_file() else {}
ate=(d.get("ate") or {})
ov=(d.get("openvins") or {})
rmse=ate.get("ate_rmse_m")
gate_a = (ov.get("ok") is True) and (rmse is not None) and (float(rmse) <= SIM_ATE_RMSE_MAX_M)
print(json.dumps({
  "phase": "A_offline",
  "ok": d.get("ok"),
  "ov_ok": ov.get("ok"),
  "ate_rmse_m": rmse,
  "gate_S2_ate_max_m": SIM_ATE_RMSE_MAX_M,
  "gate_S2_pass": gate_a,
  "n_pairs": ate.get("n_pairs"),
  "out": str(p),
}, indent=2))
Path("$OUT_OFF/gate_s2.json").write_text(json.dumps({"pass": gate_a, "ate_rmse_m": rmse}, indent=2))
PY

# --- Phase B optional (AirSim). Thrifty default skips — ZOH live IMU not in scope.
if [[ "${SKIP_CLOSED:-1}" == "1" ]]; then
  echo "[vio_align_idle] PHASE B skipped (SKIP_CLOSED=1; thrifty S2 only)"
  python3 - <<PY
import json
from pathlib import Path
from experiments.aerial.vio_probe.frames import SIM_ATE_RMSE_MAX_M
off=Path("$OUT_OFF/gate_s2.json")
s2=json.loads(off.read_text()) if off.is_file() else {"pass": False}
summary={
  "thrifty_sim_gates": {
    "S2_ate_rmse_m": s2.get("ate_rmse_m"),
    "S2_max_m": SIM_ATE_RMSE_MAX_M,
    "S2_pass": bool(s2.get("pass")),
    "S3_skipped": True,
    "overall_pass": bool(s2.get("pass")),
  },
  "note": "Thrifty: GT-consistent IMU + gt-init + imu-only. Not AirSim-ZOH VIO / not robot calib.",
}
Path(f"artifacts/vio_probe/thrifty_gate_{STAMP}.json").write_text(json.dumps(summary, indent=2))
print(json.dumps(summary, indent=2))
PY
  echo "[vio_align_idle] done $(date -Is) log=$LOG"
  exit 0
fi

echo "[vio_align_idle] PHASE B closed smoke"
export AERIAL_VIO_LIVE=1 AERIAL_VIO_GT_SEED=1 AIRSIM_FANOUT_RGB=1
export TAG="vio_align_closed" STAMP
bash experiments/aerial/scripts/run_indoor_vio_closed_smoke.sh \
  || echo "[vio_align_idle] PHASE B exited non-zero (see smoke log)"

python3 - <<PY
import json
from pathlib import Path
from experiments.aerial.vio_probe.frames import SIM_ATE_RMSE_MAX_M, SIM_CLOSED_D_HAT_MAX_M
off=Path("$OUT_OFF/gate_s2.json")
s2=json.loads(off.read_text()) if off.is_file() else {"pass": False}
# find closed artifact
cands=sorted(Path("artifacts").glob(f"indoor_vio_align_closed_{STAMP}.json"))
d_hat=None
if cands:
  d=json.loads(cands[-1].read_text())
  d_hat=d.get("mean_d_end_hat_m")
s3 = d_hat is not None and float(d_hat) <= SIM_CLOSED_D_HAT_MAX_M
summary={
  "thrifty_sim_gates": {
    "S2_ate_rmse_m": s2.get("ate_rmse_m"),
    "S2_max_m": SIM_ATE_RMSE_MAX_M,
    "S2_pass": bool(s2.get("pass")),
    "S3_closed_d_hat_m": d_hat,
    "S3_max_m": SIM_CLOSED_D_HAT_MAX_M,
    "S3_pass": bool(s3),
    "overall_pass": bool(s2.get("pass")) and bool(s3),
  },
  "note": "Thrifty sim self-consistency only — not robot calib / not F-cap.",
}
Path(f"artifacts/vio_probe/thrifty_gate_{STAMP}.json").write_text(json.dumps(summary, indent=2))
print(json.dumps(summary, indent=2))
PY

echo "[vio_align_idle] done $(date -Is) log=$LOG"
