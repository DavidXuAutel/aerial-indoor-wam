#!/usr/bin/env python3
"""HER / hindsight subgoal relabel for indoor WAM closed-loop npz.

Takes WAM-collected episodes (actions unchanged) and emits sliced windows whose
``goal`` is a *visited* future proprio position. By construction the window ends
at the goal → synthetic arrival demos without GT-PD / clamp / shield-off.

    python experiments/aerial/scripts/indoor_her_relabel.py \
      --sources <ds1> <ds2> \
      --out experiments/aerial/rl/artifacts/dataset_indoor_her_e2d_20260829 \
      --d0-min 2.0 --d0-max 6.0 --stride 10 --max-per-ep 8
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

import numpy as np

ARRAY_KEYS = (
    "rgb",
    "proprio",
    "actions",
    "rewards",
    "dones",
    "collided",
    "vel",
    "imu_ang_vel",
    "imu_lin_acc",
    "imu_present",
    "timestamps",
    "depth",
)


def _path_len(proprio: np.ndarray, i: int, j: int) -> float:
    p = proprio[i : j + 1, :3].astype(np.float64)
    if p.shape[0] < 2:
        return 0.0
    return float(np.linalg.norm(np.diff(p, axis=0), axis=1).sum())


def _progress_rewards(
    proprio: np.ndarray,
    actions: np.ndarray,
    goal: np.ndarray,
    *,
    w_maneuver: float = 0.01,
    success_bonus: float = 10.0,
    success_dist: float = 0.2,
) -> np.ndarray:
    """Dense Δdist reward on the sliced window (matches NavigationReward spirit)."""
    pos = proprio[:, :3].astype(np.float64)
    goal = np.asarray(goal, dtype=np.float64).reshape(3)
    dist = np.linalg.norm(pos - goal[None, :], axis=1)
    n = int(pos.shape[0])
    r = np.zeros(n, dtype=np.float32)
    for t in range(n - 1):
        prog = float(dist[t] - dist[t + 1])
        man = float(np.linalg.norm(actions[t].astype(np.float64)))
        r[t] = np.float32(prog - w_maneuver * man)
    # terminal
    if dist[-1] <= success_dist:
        r[-1] = np.float32(success_bonus)
    else:
        r[-1] = np.float32(0.0)
    return r


def _slice_episode(
    raw: Dict[str, np.ndarray],
    i: int,
    j: int,
    *,
    success_dist: float,
) -> Dict[str, np.ndarray]:
    out: Dict[str, np.ndarray] = {}
    for k in ARRAY_KEYS:
        if k not in raw:
            continue
        arr = np.asarray(raw[k])
        out[k] = np.asarray(arr[i : j + 1])
    goal = np.asarray(raw["proprio"][j, :3], dtype=np.float32).reshape(3)
    out["goal"] = goal
    out["rewards"] = _progress_rewards(
        out["proprio"], out["actions"], goal, success_dist=success_dist
    )
    dones = np.zeros(j - i + 1, dtype=bool)
    dones[-1] = True
    out["dones"] = dones
    # keep collided slice as-is (honest)
    return out


def relabel_dataset(
    sources: Sequence[Path],
    out_dir: Path,
    *,
    d0_min: float = 2.0,
    d0_max: float = 6.0,
    min_steps: int = 8,
    max_steps: int = 80,
    stride: int = 10,
    max_per_ep: int = 8,
    success_dist: float = 0.2,
    seed: int = 0,
) -> Dict[str, Any]:
    rng = np.random.default_rng(seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    skipped_src = 0
    cand_stats: List[float] = []
    manifest_eps: List[Dict[str, Any]] = []

    src_files: List[Tuple[Path, Path]] = []
    for src in sources:
        src = Path(src)
        files = sorted(src.glob("episode_*.npz"))
        if not files:
            raise SystemExit(f"no episode_*.npz under {src}")
        for f in files:
            src_files.append((src, f))

    for src, path in src_files:
        raw = dict(np.load(path, allow_pickle=True))
        if "proprio" not in raw or "actions" not in raw:
            skipped_src += 1
            continue
        proprio = np.asarray(raw["proprio"], dtype=np.float32)
        n = int(proprio.shape[0])
        if n < min_steps + 1:
            skipped_src += 1
            continue

        candidates: List[Tuple[int, int, float]] = []
        for i in range(0, n - min_steps, max(1, stride)):
            for j in range(i + min_steps, min(n, i + max_steps)):
                d0 = float(np.linalg.norm(proprio[i, :3] - proprio[j, :3]))
                if d0 < d0_min or d0 > d0_max:
                    continue
                # prefer windows that actually moved along path
                if _path_len(proprio, i, j) < 0.5 * d0:
                    continue
                candidates.append((i, j, d0))

        if not candidates:
            continue
        rng.shuffle(candidates)
        take = candidates[: max(1, int(max_per_ep))]
        for k, (i, j, d0) in enumerate(take):
            sliced = _slice_episode(raw, i, j, success_dist=success_dist)
            # by construction terminal dist == 0
            d_end = float(
                np.linalg.norm(sliced["proprio"][-1, :3] - sliced["goal"].reshape(3))
            )
            out_name = f"episode_{written:05d}.npz"
            out_path = out_dir / out_name
            meta = {
                "her": True,
                "source_dataset": str(src),
                "source_file": path.name,
                "i": int(i),
                "j": int(j),
                "d0_m": round(d0, 4),
                "d_end_m": round(d_end, 6),
                "arrived_by_construction": d_end <= success_dist + 1e-5,
                "n_steps": int(j - i + 1),
            }
            # stash meta JSON alongside; npz gets a small sidecar key if possible
            np.savez_compressed(out_path, **sliced)
            cand_stats.append(d0)
            manifest_eps.append({"file": out_name, **meta})
            written += 1

    summary = {
        "protocol": "indoor_her_relabel_E2d",
        "sources": [str(s) for s in sources],
        "n_source_files": len(src_files),
        "n_written": written,
        "skipped_src_eps": skipped_src,
        "d0_min": d0_min,
        "d0_max": d0_max,
        "success_dist_m": success_dist,
        "mean_d0": float(np.mean(cand_stats)) if cand_stats else None,
        "n_arrived_by_construction": sum(
            1 for e in manifest_eps if e.get("arrived_by_construction")
        ),
        "note": "actions unchanged WAM; goal=visited future proprio; not GT-PD/clamp",
    }
    (out_dir / "her_summary.json").write_text(
        json.dumps({"meta": summary, "episodes": manifest_eps}, indent=2), encoding="utf-8"
    )
    (out_dir / "collection_summary.json").write_text(
        json.dumps(
            {
                "meta": summary,
                "n_usable": written,
                "n_collected": written,
                "arrival_rate_gt": 1.0 if written else 0.0,
                "mean_d_end_gt": 0.0,
                "episodes": manifest_eps,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2))
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sources", nargs="+", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--d0-min", type=float, default=2.0)
    ap.add_argument("--d0-max", type=float, default=6.0)
    ap.add_argument("--min-steps", type=int, default=8)
    ap.add_argument("--max-steps", type=int, default=80)
    ap.add_argument("--stride", type=int, default=10)
    ap.add_argument("--max-per-ep", type=int, default=8)
    ap.add_argument("--success-dist", type=float, default=0.2)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    relabel_dataset(
        args.sources,
        args.out,
        d0_min=args.d0_min,
        d0_max=args.d0_max,
        min_steps=args.min_steps,
        max_steps=args.max_steps,
        stride=args.stride,
        max_per_ep=args.max_per_ep,
        success_dist=args.success_dist,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
