#!/usr/bin/env python3
"""Set the **single** indoor AirSim CaptureSettings WH (default 640×480).

One camera. Downstream fan-out (VIO native / WAM 224 / YOLO) is in
``experiments.aerial.rl.indoor_capture.fanout_rgb`` — not extra cameras.

  python3 experiments/aerial/scripts/patch_indoor_capture_res.py \\
    --settings /path/to/settings_indoor.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from experiments.aerial.rl.indoor_capture import indoor_capture_wh  # noqa: E402


def patch_settings(path: Path, *, width: int, height: int) -> bool:
    d = json.loads(path.read_text())
    changed = False

    def fix(caps: list) -> None:
        nonlocal changed
        for c in caps:
            if "Width" in c and int(c.get("Width", -1)) != width:
                c["Width"] = width
                changed = True
            if "Height" in c and int(c.get("Height", -1)) != height:
                c["Height"] = height
                changed = True

    if "CameraDefaults" in d and "CaptureSettings" in d["CameraDefaults"]:
        fix(d["CameraDefaults"]["CaptureSettings"])
    vehicles = d.get("Vehicles") or {}
    for veh in vehicles.values():
        for cam in (veh.get("Cameras") or {}).values():
            if "CaptureSettings" in cam:
                fix(cam["CaptureSettings"])
    if changed:
        path.write_text(json.dumps(d, indent=2) + "\n")
    return changed


def main() -> int:
    w0, h0 = indoor_capture_wh()
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--settings", type=Path, required=True)
    p.add_argument("--w", type=int, default=w0)
    p.add_argument("--h", type=int, default=h0)
    args = p.parse_args()
    if not args.settings.is_file():
        print(f"missing {args.settings}", file=sys.stderr)
        return 2
    changed = patch_settings(args.settings, width=int(args.w), height=int(args.h))
    print(
        f"{'updated' if changed else 'already'} {args.settings} "
        f"capture={args.w}x{args.h} (fan-out after grab → WAM/VIO/YOLO)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
