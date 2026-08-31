"""Backfill ``goal`` into episode npz by rematching an OpenFly annotation.

r60 (and other V0 corpora) were collected with ``--annotation`` but never
persisted ``env.goal`` into the npz. This script nearest-neighbour matches each
episode's start proprio to an annotation ``pos[0]`` and writes ``goal=pos[-1]``
as an additive key (legacy loaders ignore unknown keys; V0 governance untouched).

    python -m experiments.aerial.rl.backfill_episode_goals \
        --dataset .../dataset_v0_local_depth_r60_20260814 \
        --annotation .../seen_airsim16_m1a20.json \
        --max-match-m 5.0
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np


def _load_annotation_goals(path: Path) -> Tuple[np.ndarray, np.ndarray]:
    raw: Any = json.loads(path.read_text())
    if isinstance(raw, dict):
        items = raw.get("data") or raw.get("episodes") or raw.get("trajectories")
        if items is None:
            raise SystemExit(f"unrecognized annotation dict keys: {list(raw.keys())}")
    else:
        items = raw
    starts: List[np.ndarray] = []
    goals: List[np.ndarray] = []
    for it in items:
        if "pos" not in it:
            raise SystemExit(f"annotation item missing pos: keys={list(it.keys())}")
        pos = np.asarray(it["pos"], dtype=np.float64).reshape(-1, 3)
        if pos.shape[0] < 2:
            raise SystemExit("annotation pos must have start and goal")
        starts.append(pos[0])
        goals.append(pos[-1])
    return np.stack(starts, axis=0), np.stack(goals, axis=0)


def backfill(
    dataset: Path,
    annotation: Path,
    *,
    max_match_m: float = 5.0,
    dry_run: bool = False,
) -> Dict[str, Any]:
    starts, goals = _load_annotation_goals(annotation)
    paths = sorted(dataset.glob("episode_*.npz"))
    if not paths:
        raise SystemExit(f"no episode_*.npz under {dataset}")
    matched = 0
    skipped = 0
    dists: List[float] = []
    for path in paths:
        raw = dict(np.load(path))
        proprio = np.asarray(raw["proprio"], dtype=np.float64)
        start = proprio[0, :3]
        d = np.linalg.norm(starts - start[None, :], axis=1)
        j = int(np.argmin(d))
        dist = float(d[j])
        dists.append(dist)
        if dist > float(max_match_m):
            skipped += 1
            continue
        goal = goals[j].astype(np.float32)
        if not dry_run:
            raw["goal"] = goal
            # np.savez_compressed appends ``.npz`` if missing — keep a real
            # ``*.npz`` temp name so replace is atomic and finds the file.
            tmp = path.with_name(path.stem + ".goalbackfill.npz")
            np.savez_compressed(tmp, **raw)
            tmp.replace(path)
        matched += 1
    return {
        "episodes": len(paths),
        "matched": matched,
        "skipped": skipped,
        "match_dist_m_median": float(np.median(dists)) if dists else None,
        "match_dist_m_max": float(np.max(dists)) if dists else None,
        "dry_run": bool(dry_run),
        "annotation": str(annotation),
        "dataset": str(dataset),
    }


def main(argv: List[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dataset", required=True, type=Path)
    p.add_argument("--annotation", required=True, type=Path)
    p.add_argument("--max-match-m", type=float, default=5.0)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)
    report = backfill(
        args.dataset, args.annotation,
        max_match_m=args.max_match_m, dry_run=args.dry_run,
    )
    print(json.dumps(report, indent=2))
    return 0 if report["skipped"] == 0 else 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
