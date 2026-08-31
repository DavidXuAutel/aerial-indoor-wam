"""V4 two-signal gate entrypoint (frozen spec §4).

Mirrors ``_v0_gate`` / ``_v1_gate`` split/merge workflow:

    python -m experiments.aerial.rl._v4_gate --self-check

    python -m experiments.aerial.rl._v4_gate --merge \\
        v4_partial_1.json v4_partial_4.json

Does **not** flip yaml — human action only after authoritative merge exits 0.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from experiments.aerial.rl import v4_metrics as metrics

_ALL_SIGNALS = ("1", "4")


def _parse_signals(spec: Optional[str]) -> set[str]:
    if not spec:
        return set(_ALL_SIGNALS)
    req = {s.strip() for s in spec.split(",") if s.strip()}
    bad = req - set(_ALL_SIGNALS)
    if bad:
        raise SystemExit(f"[v4-gate] --signals: unknown {sorted(bad)}; pick from 1,4")
    if not req:
        raise SystemExit("[v4-gate] --signals: empty selection")
    return req


def _merge_partials(paths: List[Path]) -> Dict[str, Any]:
    signals: Dict[str, Any] = {}
    for pth in paths:
        blob = json.loads(pth.read_text())
        part = blob.get("signals") or blob.get("details") or {}
        for k, v in part.items():
            if k in signals:
                print(f"[v4-gate] WARN: signal {k} in multiple partials; {pth} wins",
                      file=sys.stderr)
            signals[k] = v
    return signals


def assemble_verdict(s1: Dict[str, Any], s4: Dict[str, Any]) -> Dict[str, Any]:
    return metrics.aggregate_v4_verdict({"1": s1, "4": s4})


def _emit(obj: Dict[str, Any], path: Optional[str]) -> None:
    text = json.dumps(obj, indent=2, default=str)
    print(text)
    if path:
        Path(path).write_text(text + "\n")
        print(f"[v4-gate] wrote {path}", file=sys.stderr)


def _self_check() -> int:
    s1 = metrics.check_progress_vs_heuristic(
        actor_progress_sums=[12.0] * 8,
        heuristic_progress_sums=[10.0] * 8,
        delta_p=0.10,
    )
    s4 = metrics.check_safety_no_regression(
        v4_coll_rate=0.05,
        v1_coll_rate=0.10,
        near_coll_rate_ratio=0.70,
    )
    verdict = assemble_verdict(s1, s4)
    if not verdict["ok"]:
        print("[v4-gate] self-check FAIL", file=sys.stderr)
        _emit(verdict, None)
        return 1
    print("[v4-gate] self-check PASS")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="V4 two-signal gate (frozen spec §4)")
    p.add_argument("--self-check", action="store_true")
    p.add_argument("--merge", nargs="+", default=None, metavar="JSON")
    p.add_argument("--emit", default=None, help="write verdict JSON")
    p.add_argument("--signals", default=None, help="subset: 1,4")
    p.add_argument(
        "--actor-progress", nargs="+", type=float, default=None,
        help="per-episode actor progress sums (signal 1)",
    )
    p.add_argument(
        "--heuristic-progress", nargs="+", type=float, default=None,
        help="per-episode heuristic progress sums (signal 1)",
    )
    p.add_argument("--v4-coll-rate", type=float, default=None, help="signal 4")
    p.add_argument("--v1-coll-rate", type=float, default=None, help="signal 4 baseline")
    p.add_argument("--near-coll-ratio", type=float, default=None, help="signal 4 ratio")
    args = p.parse_args(argv)

    if args.self_check:
        return _self_check()

    if args.merge:
        signals = _merge_partials([Path(x) for x in args.merge])
        missing = [k for k in _ALL_SIGNALS if k not in signals]
        if missing:
            print(f"[v4-gate] merge missing signals {missing}", file=sys.stderr)
            return 2
        verdict = metrics.aggregate_v4_verdict({k: signals[k] for k in _ALL_SIGNALS})
        verdict["merged_from"] = [str(x) for x in args.merge]
        _emit(verdict, args.emit)
        return 0 if verdict["ok"] else 1

    wanted = _parse_signals(args.signals)
    signals: Dict[str, Any] = {}

    if "1" in wanted:
        if not args.actor_progress or not args.heuristic_progress:
            signals["1"] = {
                "ok": False,
                "reason": "need --actor-progress and --heuristic-progress",
            }
        else:
            signals["1"] = metrics.check_progress_vs_heuristic(
                args.actor_progress, args.heuristic_progress,
            )

    if "4" in wanted:
        if args.v4_coll_rate is None or args.v1_coll_rate is None:
            signals["4"] = {
                "ok": False,
                "reason": "need --v4-coll-rate and --v1-coll-rate",
            }
        else:
            signals["4"] = metrics.check_safety_no_regression(
                args.v4_coll_rate,
                args.v1_coll_rate,
                near_coll_rate_ratio=args.near_coll_ratio,
            )

    partial_ok = all(signals[k].get("ok") is True for k in wanted)
    out = {
        "partial": True,
        "signals_requested": sorted(wanted),
        "ok": partial_ok,
        "signals": signals,
    }
    _emit(out, args.emit)
    return 0 if partial_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
