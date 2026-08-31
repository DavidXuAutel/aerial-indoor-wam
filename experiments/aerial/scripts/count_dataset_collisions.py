#!/usr/bin/env python3
"""Count episodes with any collided==True in dataset_v0* artifacts.

Counts raw npz ``collided`` flags (includes quarantined spawn-crashes).
Usable vs held-out splits need ``dataset.load_dataset(skip_quarantined=True)``.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import numpy as np


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, required=True)
    args = p.parse_args()
    root = args.root
    if not root.exists():
        raise SystemExit(f"missing {root}")
    for d in sorted(root.glob("dataset_v0*")):
        if not d.is_dir():
            continue
        npzs = sorted(d.glob("*.npz"))
        n_ep = 0
        n_coll = 0
        for path in npzs:
            try:
                z = np.load(path, allow_pickle=True)
            except Exception:
                continue
            if "collided" not in z.files:
                continue
            n_ep += 1
            if int(np.asarray(z["collided"]).sum()) > 0:
                n_coll += 1
        print(f"{d.name}\tnpz={len(npzs)}\tscanned={n_ep}\tcoll_eps={n_coll}")


if __name__ == "__main__":
    main()
