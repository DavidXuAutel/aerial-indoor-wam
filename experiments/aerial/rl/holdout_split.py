"""Shared episode holdout split for depth train and V4-⓪ eval (declare v2 / #19).

Both sides MUST call :func:`split_holdout_indices` with the same ``frac`` and
``seed``. Deterministic tail cuts are forbidden for depth⇄⓪ pairing on merged
corpora (source-ordered near-enrich lands in the tail — RUNBOOK §3 #20).
"""
from __future__ import annotations

from typing import Any, Dict, List, Sequence, Tuple

import numpy as np


def split_holdout_indices(
    n: int, *, frac: float, seed: int
) -> Tuple[List[int], List[int], Dict[str, Any]]:
    """Seeded permutation split.

    Returns ``(train_indices, holdout_indices, meta)``.
    ``frac<=0`` or ``n==0`` → train=all, holdout=[] (eval scores all).
    ``n==1`` → train=[0], holdout=[] (no real holdout).
    Holdout size = ``round(n*frac)`` clamped to ``[1, n-1]`` when ``n>=2``.
    """
    n = int(n)
    frac = float(frac)
    seed = int(seed)
    if n <= 0:
        meta = {
            "heldout_frac": frac,
            "split_seed": seed,
            "n_total": 0,
            "n_train": 0,
            "n_holdout": 0,
            "regime": "empty",
            "train_indices": [],
            "holdout_indices": [],
        }
        return [], [], meta
    if frac <= 0.0 or n < 2:
        idx_all = list(range(n))
        meta = {
            "heldout_frac": 0.0 if frac <= 0.0 else frac,
            "split_seed": seed,
            "n_total": n,
            "n_train": n,
            "n_holdout": 0,
            "regime": "all_episodes",
            "train_indices": idx_all,
            "holdout_indices": [],
        }
        return idx_all, [], meta

    rng = np.random.default_rng(seed)
    perm = rng.permutation(n)
    n_hold = max(1, int(round(n * frac)))
    n_hold = min(n_hold, n - 1)
    hold = [int(i) for i in perm[:n_hold]]
    train = [int(i) for i in perm[n_hold:]]
    hold_sorted = sorted(hold)
    train_sorted = sorted(train)
    meta = {
        "heldout_frac": frac,
        "split_seed": seed,
        "n_total": n,
        "n_train": len(train),
        "n_holdout": len(hold),
        "regime": "seeded_holdout",
        "train_indices": train_sorted,
        "holdout_indices": hold_sorted,
    }
    return train, hold, meta


def apply_indices(episodes: Sequence[Any], indices: Sequence[int]) -> List[Any]:
    return [episodes[int(i)] for i in indices]


def assert_same_holdout(
    meta_a: Dict[str, Any], meta_b: Dict[str, Any], *, label_a: str, label_b: str
) -> None:
    """Raise if two split metas disagree on holdout index sets."""
    a = list(meta_a.get("holdout_indices") or [])
    b = list(meta_b.get("holdout_indices") or [])
    if a != b:
        raise AssertionError(
            f"holdout index mismatch {label_a}={a} vs {label_b}={b} "
            f"(frac/seed must match; see RUNBOOK §3 #19)"
        )


def summarize_merge_sources(dataset_dir, holdout_indices: Sequence[int]) -> Dict[str, Any]:
    """Optional provenance from ``merge_manifest.json`` (declare v2 / #20)."""
    from pathlib import Path

    man_path = Path(dataset_dir) / "merge_manifest.json"
    if not man_path.is_file():
        return {"available": False}
    man = __import__("json").loads(man_path.read_text())
    eps = man.get("episodes") or []
    by_src: Dict[str, int] = {}
    by_layer: Dict[str, int] = {}
    for i in holdout_indices:
        if i < 0 or i >= len(eps):
            continue
        e = eps[i]
        src = str(e.get("src", "?"))
        # basename only for stable keys
        src_key = Path(src).name
        by_src[src_key] = by_src.get(src_key, 0) + 1
        layer = str(e.get("layer", "unknown"))
        by_layer[layer] = by_layer.get(layer, 0) + 1
    return {
        "available": True,
        "sources_order": man.get("sources"),
        "holdout_by_src": by_src,
        "holdout_by_layer": by_layer,
        "n_holdout_listed": len(holdout_indices),
    }
