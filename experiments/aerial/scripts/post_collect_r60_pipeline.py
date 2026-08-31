#!/usr/bin/env python3
"""Wait for r60 collection, PASS coarse check, tar sync to H100."""
from __future__ import annotations

import base64
import json
import sys
import time
from pathlib import Path

import pexpect

DEST = "dataset_v0_local_depth_r60_20260814"
HOST4090 = "yao@10.229.20.125"
PASS4090 = "cupcake777"
H100 = "a25689@10.239.121.26"
H100_PORT = "31126"
PASS_H100 = "123456"
REPO4090 = "~/aerial-wam-v2"
OUT4090 = f"{REPO4090}/experiments/aerial/rl/artifacts/{DEST}"
H100_DEST = f"~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/{DEST}"
RESULT_PATH = Path("/tmp/pass_coarse_result_r60.json")


def ssh4090(cmd: str, timeout: int = 120) -> str:
    child = pexpect.spawn(
        f"ssh -o StrictHostKeyChecking=accept-new {HOST4090} {cmd!r}",
        encoding="utf-8",
        timeout=timeout,
    )
    if child.expect([r"password:", pexpect.EOF]) == 0:
        child.sendline(PASS4090)
        child.expect(pexpect.EOF, timeout=timeout)
    return child.before.strip()


def ssh_h100(cmd: str, timeout: int = 600) -> str:
    child = pexpect.spawn(
        f"ssh -o StrictHostKeyChecking=accept-new -p {H100_PORT} {H100} {cmd!r}",
        encoding="utf-8",
        timeout=timeout,
    )
    if child.expect([r"[Pp]assword:", pexpect.EOF]) == 0:
        child.sendline(PASS_H100)
        child.expect(pexpect.EOF, timeout=timeout)
    return child.before.strip()


def wait_collection(max_polls: int = 240, interval: int = 30) -> None:
    for i in range(1, max_polls + 1):
        out = ssh4090(
            f"pgrep -f 'collect_dataset.*{DEST}' >/dev/null && echo RUNNING || echo DONE; "
            f"ls {OUT4090}/episode_*.npz 2>/dev/null | wc -l"
        )
        lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
        status = next((ln for ln in lines if ln in ("RUNNING", "DONE")), "?")
        count = lines[-1] if lines else "?"
        print(f"[wait] {i}: status={status} npz={count}", flush=True)
        if status == "DONE":
            return
        time.sleep(interval)
    raise SystemExit("TIMEOUT waiting for collection")


def pass_coarse_check() -> dict:
    check_py = r'''
import json, statistics as st
from pathlib import Path
import numpy as np
out = Path("experiments/aerial/rl/artifacts/dataset_v0_local_depth_r60_20260814")
log = Path("artifacts/collect_v0_local_depth_r60_20260814.log").read_text()
manifest = json.loads((out/"manifest.json").read_text())
meta = manifest["meta"]
qs = json.loads((out/"QUALITY_SUMMARY.json").read_text())
npzs = sorted(out.glob("episode_*.npz"))
result = {
    "npz_count": len(npzs),
    "grab_depth": meta.get("grab_depth"),
    "step_hz": meta.get("step_hz"),
    "quarantine_fraction": meta.get("quarantine_fraction"),
    "path_length_m_mean": qs.get("path_length_m", {}).get("mean"),
    "collect_ok": "[collect] OK:" in log,
}
ach = [e.get("achieved_hz") for e in manifest.get("episodes", []) if e.get("achieved_hz")]
if ach:
    result["achieved_hz_median"] = round(float(st.median(ach)), 3)
    result["achieved_hz_min"] = round(float(min(ach)), 3)
sample = np.load(npzs[0])
keys = set(sample.files)
need = {"depth", "timestamps", "vel"} | {k for k in keys if k.startswith("imu_")}
result["npz_keys_ok"] = not (need - keys)
errors = []
if meta.get("grab_depth") is not True: errors.append("grab_depth")
if meta.get("step_hz") != 5.0: errors.append("step_hz")
if meta.get("quarantine_fraction", 1) > 0.20: errors.append("quarantine_fraction")
if not result["path_length_m_mean"]: errors.append("path_length_m.mean")
if not result["npz_keys_ok"]: errors.append("npz_keys")
if not result["collect_ok"]: errors.append("collect_exit")
result["pass"] = not errors
result["errors"] = errors
print(json.dumps(result))
'''
    b64 = base64.b64encode(check_py.encode()).decode()
    out = ssh4090(
        f"cd {REPO4090} && echo {b64} | base64 -d | /home/yao/sim_verify/.venv/bin/python",
        timeout=180,
    )
    for line in reversed(out.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    raise SystemExit(f"PASS check failed to parse output:\n{out}")


def tar_sync_via_expect() -> str:
    expect_script = f"""#!/usr/bin/expect -f
set timeout 3600
spawn bash -c "cd {REPO4090}/experiments/aerial/rl/artifacts && tar cf - {DEST} | ssh -o StrictHostKeyChecking=accept-new -p {H100_PORT} {H100} 'mkdir -p ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts && tar xf - -C ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts'"
expect {{
    -re {{(?i)password:}} {{ send "{PASS_H100}\\r"; exp_continue }}
    eof
}}
"""
    eb64 = base64.b64encode(expect_script.encode()).decode()
    ssh4090(
        f"echo {eb64} | base64 -d > /tmp/sync_r60.exp && chmod +x /tmp/sync_r60.exp && /usr/bin/expect /tmp/sync_r60.exp",
        timeout=3600,
    )
    return ssh_h100(
        f"ls {H100_DEST}/episode_*.npz | wc -l; test -f {H100_DEST}/manifest.json && echo H100_MANIFEST_OK; du -sh {H100_DEST}"
    )


def main() -> None:
    print("=== wait collection ===", flush=True)
    wait_collection()
    print(ssh4090("tail -20 ~/aerial-wam-v2/artifacts/collect_v0_local_depth_r60_20260814.log"))
    print("=== PASS coarse ===", flush=True)
    result = pass_coarse_check()
    print(json.dumps(result, indent=2), flush=True)
    RESULT_PATH.write_text(json.dumps(result, indent=2))
    if not result.get("pass"):
        raise SystemExit(f"PASS coarse FAILED: {result.get('errors')}")
    print("=== tar sync ===", flush=True)
    verify = tar_sync_via_expect()
    print(verify, flush=True)
    print(verify, flush=True)
    print("PIPELINE_OK", flush=True)
    # Write machine-readable summary for doc update
    summary = {
        "dest": DEST,
        "h100_path": H100_DEST,
        "pass_result": result,
        "h100_verify": verify,
        "status": "SYNCED",
    }
    Path("/tmp/r60_pipeline_summary.json").write_text(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
