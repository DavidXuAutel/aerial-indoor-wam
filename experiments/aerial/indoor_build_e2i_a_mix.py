#!/usr/bin/env python3
"""Build E2i.A success-weighted indoor mix (symlink) for WM encode / π re-C1.

Default buckets (π mix):
  B1 ≥60%  near-success assist=none, prefer low d_end, drop early collision
  B2 ≤25%  fixture@0.20
  old ≤15% optional e2h101 (default 0 for A)

Encode-only mode (--encode-only): B1-heavy (≥80%), B2≤20%, no old.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _art() -> Path:
    return _repo_root() / "experiments" / "aerial" / "rl" / "artifacts"


def _load_summary(ds: Path) -> List[Dict[str, Any]]:
    for name in ("collection_summary.json", "mix_meta.json", "manifest.json"):
        p = ds / name
        if not p.is_file():
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        eps = data.get("episodes") or []
        if eps:
            return eps
    # fallback: glob only
    return [{"file": p.name} for p in sorted(ds.glob("episode_*.npz"))]


def _d_end(ep: Dict[str, Any]) -> float:
    for k in ("d_end_m_gt", "d_end_m", "min_d_end_m"):
        if ep.get(k) is not None:
            try:
                return float(ep[k])
            except (TypeError, ValueError):
                pass
    return 99.0


def _early_collision(npz_path: Path, max_steps: int = 8) -> bool:
    """True if collision flag in first max_steps frames (spawn junk)."""
    try:
        z = np.load(npz_path, allow_pickle=False)
    except OSError:
        return True
    if "collided" not in z.files:
        return False
    c = np.asarray(z["collided"]).reshape(-1)
    n = min(int(max_steps), c.shape[0])
    return bool(np.any(c[:n]))


def _rank_b1(eps: List[Dict[str, Any]], src: Path, drop_early_coll: bool) -> List[Tuple[float, Path, Dict[str, Any]]]:
    ranked: List[Tuple[float, Path, Dict[str, Any]]] = []
    for ep in eps:
        fname = ep.get("file") or ep.get("npz")
        if not fname:
            continue
        path = src / fname
        if not path.is_file():
            continue
        if ep.get("collided") and drop_early_coll:
            # keep if late collision only? A prefers clean; drop any collided when flagged
            if bool(ep.get("collided")):
                continue
        if drop_early_coll and _early_collision(path):
            continue
        ranked.append((_d_end(ep), path, ep))
    ranked.sort(key=lambda t: t[0])
    return ranked


def _pick(paths: List[Path], n: int, rng: random.Random) -> List[Path]:
    if n <= 0 or not paths:
        return []
    if len(paths) <= n:
        return list(paths)
    return rng.sample(paths, n)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="experiments/aerial/rl/artifacts/dataset_indoor_e2i_a_20260831")
    ap.add_argument("--b1", default="experiments/aerial/rl/artifacts/dataset_indoor_b99_none_near_20260831")
    ap.add_argument("--b2", default="experiments/aerial/rl/artifacts/dataset_indoor_b99_fixture020_20260831")
    ap.add_argument("--old", default="", help="optional old e2h dir; empty = skip")
    ap.add_argument("--total", type=int, default=100)
    ap.add_argument("--b1-frac", type=float, default=0.65)
    ap.add_argument("--b2-frac", type=float, default=0.25)
    ap.add_argument("--old-frac", type=float, default=0.0)
    ap.add_argument("--encode-only", action="store_true", help="B1≥0.85 B2≤0.15 old=0")
    ap.add_argument("--seed", type=int, default=31)
    ap.add_argument("--keep-early-collision", action="store_true")
    args = ap.parse_args()

    root = _repo_root()
    if args.encode_only:
        args.b1_frac, args.b2_frac, args.old_frac = 0.85, 0.15, 0.0

    out = Path(args.out) if Path(args.out).is_absolute() else root / args.out
    b1 = Path(args.b1) if Path(args.b1).is_absolute() else root / args.b1
    b2 = Path(args.b2) if Path(args.b2).is_absolute() else root / args.b2
    old: Optional[Path] = None
    if args.old:
        old = Path(args.old) if Path(args.old).is_absolute() else root / args.old

    if not b1.is_dir():
        print(f"missing B1: {b1}", file=sys.stderr)
        return 1

    rng = random.Random(int(args.seed))
    drop = not bool(args.keep_early_collision)

    b1_ranked = _rank_b1(_load_summary(b1), b1, drop)
    b1_paths = [p for _, p, _ in b1_ranked]
    b2_paths = sorted(b2.glob("episode_*.npz")) if b2.is_dir() else []
    old_paths = sorted(old.glob("episode_*.npz")) if old and old.is_dir() else []

    n_total = int(args.total)
    n_b1 = max(1, int(round(n_total * float(args.b1_frac))))
    n_b2 = int(round(n_total * float(args.b2_frac))) if b2_paths else 0
    n_old = int(round(n_total * float(args.old_frac))) if old_paths else 0
    # Prefer filling with B1 if others short
    while n_b1 + n_b2 + n_old > n_total and n_old > 0:
        n_old -= 1
    while n_b1 + n_b2 + n_old > n_total and n_b2 > 0:
        n_b2 -= 1
    if n_b1 + n_b2 + n_old < n_total:
        n_b1 += n_total - (n_b1 + n_b2 + n_old)

    # B1: take best (lowest d_end) first, then pad randomly if needed
    chosen_b1 = b1_paths[:n_b1]
    if len(chosen_b1) < n_b1:
        print(f"WARN: B1 only {len(chosen_b1)} after filter (wanted {n_b1})", file=sys.stderr)
    chosen_b2 = _pick(b2_paths, n_b2, rng)
    chosen_old = _pick(old_paths, n_old, rng)

    if out.exists():
        for p in out.glob("episode_*.npz"):
            p.unlink()
    out.mkdir(parents=True, exist_ok=True)

    episodes_meta: List[Dict[str, Any]] = []
    idx = 0

    def _link(src: Path, bucket: str) -> None:
        nonlocal idx
        dst = out / f"episode_{idx:05d}.npz"
        if dst.exists() or dst.is_symlink():
            dst.unlink()
        dst.symlink_to(src.resolve())
        episodes_meta.append({"file": dst.name, "source": str(src), "bucket": bucket})
        idx += 1

    for p in chosen_b1:
        _link(p, "b1")
    for p in chosen_b2:
        _link(p, "b2")
    for p in chosen_old:
        _link(p, "old")

    meta = {
        "protocol": "e2i_a_mix",
        "encode_only": bool(args.encode_only),
        "total": idx,
        "fracs": {"b1": args.b1_frac, "b2": args.b2_frac, "old": args.old_frac},
        "counts": {
            "b1": len(chosen_b1),
            "b2": len(chosen_b2),
            "old": len(chosen_old),
        },
        "drop_early_collision": drop,
        "sources": {"b1": str(b1), "b2": str(b2), "old": str(old) if old else None},
        "episodes": episodes_meta,
        "seed": int(args.seed),
    }
    (out / "mix_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    # Lightweight manifest for _refuse_v0 (step_hz=5 indoor)
    (out / "manifest.json").write_text(
        json.dumps(
            {
                "meta": {"step_hz": 5.0, "grab_depth": True, "protocol": "e2i_a_mix"},
                "episodes": [{"file": e["file"]} for e in episodes_meta],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps({k: meta[k] for k in ("total", "counts", "fracs", "drop_early_collision")}, indent=2))
    print(f"out={out}")
    return 0 if idx > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
