#!/usr/bin/env bash
# Wait for dataset_v0_local_depth_r60_20260814 collection, PASS coarse check,
# tar+ssh sync to H100, print summary. Run from Mac (needs network to 4090+H100).
set -euo pipefail

DEST=dataset_v0_local_depth_r60_20260814
H100="a25689@10.239.121.26"
H100_PORT=31126
H100_PASS="${H100_PASS:-123456}"
HOST4090="yao@10.229.20.125"
HOST4090_PASS="${HOST4090_PASS:-cupcake777}"

say(){ echo "[post_collect] $*"; }

ssh4090() {
  sshpass -p "$HOST4090_PASS" ssh -o StrictHostKeyChecking=accept-new "$HOST4090" "$@"
}

ssh_h100() {
  sshpass -p "$H100_PASS" ssh -o StrictHostKeyChecking=accept-new -p "$H100_PORT" "$H100" "$@"
}

if ! command -v sshpass >/dev/null 2>&1; then
  say "ERROR: sshpass required (brew install hudochenkov/sshpass/sshpass)" >&2
  exit 1
fi

say "waiting for collect_dataset on 4090 ..."
for i in $(seq 1 240); do
  if ssh4090 "pgrep -f 'collect_dataset.*${DEST}'" >/dev/null 2>&1; then
    n=$(ssh4090 "ls ~/aerial-wam-v2/experiments/aerial/rl/artifacts/${DEST}/episode_*.npz 2>/dev/null | wc -l")
    say "poll $i: collecting, npz=$n"
    sleep 30
  else
    say "collect process finished after $i polls"
    break
  fi
done

say "=== collect log tail ==="
ssh4090 "tail -25 ~/aerial-wam-v2/artifacts/collect_v0_local_depth_r60_20260814.log"

say "=== PASS coarse check on 4090 ==="
ssh4090 "cd ~/aerial-wam-v2 && /home/yao/sim_verify/.venv/bin/python -" <<'PYCHECK'
import json, sys, statistics as st
from pathlib import Path
import numpy as np

out = Path("experiments/aerial/rl/artifacts/dataset_v0_local_depth_r60_20260814")
log = Path("artifacts/collect_v0_local_depth_r60_20260814.log").read_text()
if "[collect] OK:" not in log:
    print("WARN: log missing [collect] OK line")
manifest = json.loads((out/"manifest.json").read_text())
meta = manifest["meta"]
qs = json.loads((out/"QUALITY_SUMMARY.json").read_text())
npzs = sorted(out.glob("episode_*.npz"))
print(f"npz_count={len(npzs)}")
print(f"grab_depth={meta.get('grab_depth')} step_hz={meta.get('step_hz')} quarantine_fraction={meta.get('quarantine_fraction')}")
assert meta.get("grab_depth") is True, "FAIL grab_depth"
assert meta.get("step_hz") == 5.0, f"FAIL step_hz {meta.get('step_hz')}"
qf = meta.get("quarantine_fraction", 1)
assert qf <= 0.20, f"FAIL quarantine_fraction {qf}"
sample = np.load(npzs[0])
keys = set(sample.files)
need = {"depth", "timestamps", "vel"} | {k for k in keys if k.startswith("imu_")}
missing = need - keys
assert not missing, f"FAIL npz keys missing {missing}"
pl = qs.get("path_length_m", {}).get("mean")
print(f"path_length_m.mean={pl}")
assert pl and pl > 0, "FAIL path_length_m.mean"
ach = [e.get("achieved_hz") for e in manifest.get("episodes", []) if e.get("achieved_hz")]
if ach:
    print(f"achieved_hz median={st.median(ach):.2f} min={min(ach):.2f} max={max(ach):.2f}")
print("PASS_COARSE_OK")
PYCHECK

say "=== tar sync 4090 -> H100 ==="
ssh4090 "cd ~/aerial-wam-v2/experiments/aerial/rl/artifacts && tar cf - ${DEST}" | \
  sshpass -p "$H100_PASS" ssh -o StrictHostKeyChecking=accept-new -p "$H100_PORT" "$H100" \
  "mkdir -p ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts && tar xf - -C ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts"

say "=== verify H100 ==="
ssh_h100 "ls ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/${DEST}/episode_*.npz | wc -l; test -f ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/${DEST}/manifest.json && echo H100_MANIFEST_OK; du -sh ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/${DEST}"

say "DONE"
