#!/usr/bin/env python3
"""Merge usable-only P4.5 episode dirs into one corpus."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", action="append", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("episode_*.npz"):
        old.unlink()

    prov = []
    idx = 0
    layer_counts: dict[str, int] = {"open": 0, "blocked": 0, "unknown": 0}
    for src in args.src:
        sdir = Path(src)
        man = json.loads((sdir / "manifest.json").read_text())
        by_file = {e["file"]: e for e in (man.get("episodes") or []) if "file" in e}
        files = sorted(sdir.glob("episode_*.npz"))
        kept = 0
        for ep in files:
            meta = by_file.get(ep.name, {})
            if meta.get("quarantined") or meta.get("usable") is False:
                print(f"[skip] {sdir.name}/{ep.name}")
                continue
            dst = out / f"episode_{idx:05d}.npz"
            shutil.copy2(ep, dst)
            layer = str(meta.get("layer", "unknown"))
            layer_counts[layer] = layer_counts.get(layer, 0) + 1
            prov.append(
                {"index": idx, "src": str(sdir), "orig": ep.name, "layer": layer}
            )
            idx += 1
            kept += 1
        print(f"[merge] {sdir.name}: kept {kept}/{len(files)}")

    (out / "merge_manifest.json").write_text(
        json.dumps(
            {
                "sources": list(args.src),
                "total": idx,
                "layer_counts": layer_counts,
                "episodes": prov,
            },
            indent=2,
        )
        + "\n"
    )
    man_eps = []
    for e in prov:
        fname = f"episode_{e['index']:05d}.npz"
        man_eps.append(
            {
                "file": fname,
                "layer": e["layer"],
                "usable": True,
                "quarantined": False,
            }
        )
    (out / "manifest.json").write_text(
        json.dumps(
            {
                "meta": {
                    "grab_depth": True,
                    "step_hz": 5.0,
                    "approach_bias": True,
                    "merged_from_p45": True,
                    "layer_counts": layer_counts,
                },
                "episodes": man_eps,
            },
            indent=2,
        )
        + "\n"
    )
    print(f"[merge] TOTAL usable={idx} layers={layer_counts} -> {out}")
    return 0 if idx > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
