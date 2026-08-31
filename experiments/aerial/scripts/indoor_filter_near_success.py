#!/usr/bin/env python3
"""Post-filter raw indoor_loop_collect output → near-success corpus (E2i.2b fallback)."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import numpy as np


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_dir", required=True, help="raw collect out-dir")
    ap.add_argument("--out", dest="out_dir", required=True, help="filtered out-dir")
    ap.add_argument("--max-d-end", type=float, default=1.0)
    ap.add_argument("--require-no-collision", action="store_true", default=True)
    ap.add_argument("--allow-collision", action="store_true", help="disable collision filter")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[3]
    in_dir = Path(args.in_dir) if Path(args.in_dir).is_absolute() else root / args.in_dir
    out_dir = Path(args.out_dir) if Path(args.out_dir).is_absolute() else root / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    summary_path = in_dir / "collection_summary.json"
    if not summary_path.is_file():
        print(f"missing {summary_path}", file=sys.stderr)
        return 1
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    episodes = summary.get("episodes") or []

    kept = []
    ep_idx = 0
    for ep in episodes:
        fname = ep.get("file") or ep.get("npz")
        if not fname:
            continue
        src = in_dir / fname
        if not src.is_file():
            continue
        d_end = ep.get("d_end_m_gt", ep.get("d_end_m"))
        if d_end is None:
            continue
        if float(d_end) > float(args.max_d_end):
            continue
        if args.require_no_collision and not args.allow_collision and ep.get("collided"):
            continue
        dst = out_dir / f"episode_{ep_idx:05d}.npz"
        shutil.copy2(src, dst)
        kept.append({**ep, "file": dst.name, "source_file": fname})
        ep_idx += 1

    out_summary = {
        **{k: v for k, v in summary.items() if k not in ("episodes", "n_usable", "n_collected")},
        "filter": {
            "max_d_end_m": float(args.max_d_end),
            "require_no_collision": bool(args.require_no_collision and not args.allow_collision),
            "source_dir": str(in_dir),
        },
        "n_usable": len(kept),
        "n_collected": len(kept),
        "episodes": kept,
    }
    (out_dir / "collection_summary.json").write_text(json.dumps(out_summary, indent=2), encoding="utf-8")
    print(json.dumps({"in": str(in_dir), "out": str(out_dir), "kept": len(kept)}, indent=2))
    return 0 if kept else 1


if __name__ == "__main__":
    sys.exit(main())
