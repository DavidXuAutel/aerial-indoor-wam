#!/usr/bin/env python3
"""Quick east spawn probe — gt_proxy 1 ep, returns exit 0 if non-SPAWN scored."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True, help="eval JSON from mainline_baseline")
    ap.add_argument("--spawn-max-steps", type=int, default=8)
    args = ap.parse_args()
    data = json.loads(Path(args.inp).read_text())
    eps = data.get("episodes") or data.get("results") or []
    if not eps:
        print("FAIL: no episodes")
        return 1
    e = eps[0]
    spawn = bool(e.get("collided")) and int(e.get("steps") or 0) <= args.spawn_max_steps
    out = {
        "spawn": spawn,
        "steps": e.get("steps"),
        "collided": e.get("collided"),
        "arrived_gt": e.get("arrived_gt"),
        "arrived_hat": e.get("arrived_hat"),
        "d_end_m_gt": e.get("d_end_m_gt"),
        "d_end_m_hat": e.get("d_end_m_hat"),
    }
    print(json.dumps(out))
    return 1 if spawn else 0


if __name__ == "__main__":
    sys.exit(main())
