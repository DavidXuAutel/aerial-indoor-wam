#!/usr/bin/env python3
"""E2i.C S1 — split SPAWN / NEAR_COLL / ARRIVE in eval JSON (+ optional route drop).

Usage:
  python experiments/aerial/scripts/indoor_fail_split_report.py \\
    --in artifacts/indoor_e2i_c_s3_A050_seed0_20260901.json \\
    --out artifacts/indoor_e2i_c_s3_A050_seed0_fail_split.json

  # Build annotation without chronic SPAWN routes (e.g. drop idx 0 = R01):
  python experiments/aerial/scripts/indoor_fail_split_report.py \\
    --filter-annotation artifacts/building99_indoor_short_routes.json \\
    --drop-route-idx 0 \\
    --out-annotation artifacts/building99_indoor_short_routes_nospawn_r01.json
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List


def classify(ep: Dict[str, Any], spawn_max_steps: int = 8) -> str:
    arr = bool(ep.get("arrived") or ep.get("success") or ep.get("arrived_gt"))
    coll = bool(ep.get("collided"))
    steps = int(ep.get("steps") or 0)
    if arr:
        return "ARRIVE"
    if coll and steps <= spawn_max_steps:
        return "SPAWN"
    if coll:
        return "NEAR_COLL"
    return "MISS"


def split_eval(path: Path, spawn_max_steps: int) -> Dict[str, Any]:
    d = json.loads(path.read_text(encoding="utf-8"))
    eps = d.get("episodes") or d.get("results") or []
    rows = []
    ctr: Counter = Counter()
    for e in eps:
        kind = classify(e, spawn_max_steps)
        ctr[kind] += 1
        rows.append({
            "segment": e.get("segment_name") or e.get("route_name"),
            "kind": kind,
            "steps": e.get("steps"),
            "d_end": e.get("d_end_m_gt", e.get("d_end_m")),
            "collided": e.get("collided"),
            "arrived": e.get("arrived") or e.get("success"),
        })
    return {
        "source": str(path),
        "spawn_max_steps": spawn_max_steps,
        "counts": dict(ctr),
        "episodes": rows,
    }


def filter_annotation(src: Path, drop_idx: List[int], out: Path) -> None:
    routes = json.loads(src.read_text(encoding="utf-8"))
    if not isinstance(routes, list):
        raise SystemExit("annotation must be a JSON list of routes")
    keep = [r for i, r in enumerate(routes) if i not in set(drop_idx)]
    meta = {
        "protocol": "e2i_c_s1_nospawn_annotation",
        "source": str(src),
        "dropped_route_idx": drop_idx,
        "n_in": len(routes),
        "n_out": len(keep),
    }
    # keep list format expected by eval; write sidecar meta
    out.write_text(json.dumps(keep, indent=2) + "\n", encoding="utf-8")
    out.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(meta, indent=2))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--spawn-max-steps", type=int, default=8)
    ap.add_argument("--filter-annotation", default=None)
    ap.add_argument("--drop-route-idx", default="0", help="comma indices to drop")
    ap.add_argument("--out-annotation", default=None)
    args = ap.parse_args()

    if args.filter_annotation:
        src = Path(args.filter_annotation)
        out = Path(args.out_annotation or "artifacts/building99_indoor_short_routes_nospawn.json")
        drop = [int(x) for x in args.drop_route_idx.split(",") if x.strip() != ""]
        filter_annotation(src, drop, out)
        return 0

    if not args.in_path:
        raise SystemExit("need --in or --filter-annotation")
    rep = split_eval(Path(args.in_path), int(args.spawn_max_steps))
    out = Path(args.out or Path(args.in_path).with_name(Path(args.in_path).stem + "_fail_split.json"))
    out.write_text(json.dumps(rep, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(out), "counts": rep["counts"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
