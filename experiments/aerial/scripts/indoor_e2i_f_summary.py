#!/usr/bin/env python3
"""Aggregate E2i.F eval seeds into summary JSON with legacy + cap gates."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _is_spawn(ep: Dict[str, Any], spawn_max_steps: int = 8) -> bool:
    if not bool(ep.get("collided")):
        return False
    return int(ep.get("steps") or 0) <= spawn_max_steps


def _episode_metrics(eps: List[Dict[str, Any]], spawn_max_steps: int) -> Dict[str, Any]:
    dens_all: List[float] = []
    scored: List[Dict[str, Any]] = []
    spawn_n = 0
    near_n = 0
    arr_all = 0
    coll_all = 0
    arr_collided = 0

    for e in eps:
        arrived = bool(e.get("arrived") or e.get("success"))
        collided = bool(e.get("collided"))
        if arrived:
            arr_all += 1
            if collided:
                arr_collided += 1
        v = e.get("d_end_m_gt", e.get("d_end_m"))
        if v is not None:
            dens_all.append(float(v))
        if collided:
            coll_all += 1
            if _is_spawn(e, spawn_max_steps):
                spawn_n += 1
            else:
                near_n += 1
        if not _is_spawn(e, spawn_max_steps):
            scored.append(e)

    dens_scored = [
        float(e.get("d_end_m_gt", e.get("d_end_m")))
        for e in scored
        if e.get("d_end_m_gt", e.get("d_end_m")) is not None
    ]
    arr_scored = sum(1 for e in scored if e.get("arrived") or e.get("success"))
    coll_scored = sum(1 for e in scored if e.get("collided"))
    arr_coll_scored = sum(
        1 for e in scored
        if (e.get("arrived") or e.get("success")) and e.get("collided")
    )

    n = len(eps)
    n_scored = len(scored)
    mean_all = (sum(dens_all) / len(dens_all)) if dens_all else None
    mean_scored = (sum(dens_scored) / len(dens_scored)) if dens_scored else None

    return {
        "n": n,
        "n_scored": n_scored,
        "n_spawn_excluded": spawn_n,
        "arrived_all": arr_all,
        "arrived_scored": arr_scored,
        "mean_d_all": mean_all,
        "mean_d_scored": mean_scored,
        "collision_n": coll_all,
        "collision_scored_n": coll_scored,
        "spawn_n": spawn_n,
        "near_coll_n": near_n,
        "arrived_but_collided": arr_collided,
        "arrived_but_collided_scored": arr_coll_scored,
        "arrival_rate_all": arr_all / n if n else 0.0,
        "arrival_rate_scored": arr_scored / n_scored if n_scored else 0.0,
        "collision_rate_all": coll_all / n if n else 0.0,
        "collision_rate_scored": coll_scored / n_scored if n_scored else 0.0,
        "spawn_rate": spawn_n / n if n else 0.0,
    }


def compute_gates(tot: Dict[str, Any], *, use_cap: bool) -> Tuple[Dict[str, bool], bool]:
    if use_cap:
        n_den = tot["n_scored"]
        arr_rate = tot["arrival_rate_scored"]
        mean_d = tot["mean_d_scored"]
        coll_rate = tot["collision_rate_scored"]
        arr_coll = tot["arrived_but_collided_scored"]
        # require at least one scored episode so empty run does not vacuously pass
        g1 = n_den > 0 and arr_rate >= 0.50
        g2 = n_den > 0 and mean_d is not None and mean_d <= 1.0
        g3 = n_den > 0 and coll_rate <= 0.50 and arr_coll == 0
    else:
        n_den = tot["n"]
        arr_rate = tot["arrival_rate_all"]
        mean_d = tot["mean_d_all"]
        coll_rate = tot["collision_rate_all"]
        arr_coll = tot["arrived_but_collided"]
        g1 = arr_rate >= 0.50
        g2 = mean_d is not None and mean_d <= 1.0
        g3 = coll_rate <= 0.50 and arr_coll == 0

    g4 = True
    gates = {
        "G1_arrival_ge_0.50": g1,
        "G2_mean_d_le_1.0": g2,
        "G3_coll_le_0.50_and_arrived_clean": g3,
        "G4_fail_split_written": g4,
    }
    return gates, all(gates.values())


def summarize_eval(
    *,
    tag: str,
    stamp: str,
    protocol: str,
    ann: str,
    routes: str,
    success_dist_m: float,
    gate_mode: str = "cap",
    spawn_max_steps: int = 8,
    meta: Dict[str, Any] | None = None,
    extra: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    seed_rows = []
    tot = {
        "n": 0,
        "n_scored": 0,
        "n_spawn_excluded": 0,
        "arrived_all": 0,
        "arrived_scored": 0,
        "collision_n": 0,
        "collision_scored_n": 0,
        "spawn_n": 0,
        "near_coll_n": 0,
        "arrived_but_collided": 0,
        "arrived_but_collided_scored": 0,
    }
    mean_d_all_vals: List[float] = []
    mean_d_scored_vals: List[float] = []

    for seed in (0, 1, 2):
        p = Path(f"artifacts/indoor_e2i_{tag}_seed{seed}_{stamp}.json")
        d = json.loads(p.read_text(encoding="utf-8"))
        eps = d.get("episodes") or d.get("results") or []
        m = _episode_metrics(eps, spawn_max_steps)
        seed_rows.append({"seed": seed, **m})
        for k in tot:
            tot[k] += m[k]
        if m["mean_d_all"] is not None:
            mean_d_all_vals.append(m["mean_d_all"])
        if m["mean_d_scored"] is not None:
            mean_d_scored_vals.append(m["mean_d_scored"])

    n = tot["n"]
    n_scored = tot["n_scored"]
    tot["mean_d_all"] = sum(mean_d_all_vals) / len(mean_d_all_vals) if mean_d_all_vals else None
    tot["mean_d_scored"] = sum(mean_d_scored_vals) / len(mean_d_scored_vals) if mean_d_scored_vals else None
    tot["arrival_rate_all"] = tot["arrived_all"] / n if n else 0.0
    tot["arrival_rate_scored"] = tot["arrived_scored"] / n_scored if n_scored else 0.0
    tot["collision_rate_all"] = tot["collision_n"] / n if n else 0.0
    tot["collision_rate_scored"] = tot["collision_scored_n"] / n_scored if n_scored else 0.0
    tot["spawn_rate"] = tot["spawn_n"] / n if n else 0.0

    use_cap = gate_mode == "cap"
    legacy_gates, legacy_pass = compute_gates(tot, use_cap=False)
    cap_gates, cap_pass = compute_gates(tot, use_cap=True)

    out: Dict[str, Any] = {
        "protocol": protocol,
        "contract": "INDOOR_E2I_F_PLAN_20260901.md §1.1 F-cap",
        "gate_mode": gate_mode,
        "spawn_max_steps": spawn_max_steps,
        "spawn_excluded_from_primary": use_cap,
        "success_dist_m": success_dist_m,
        "pose_source": "gt_proxy",
        "pose_note": "probe only",
        "annotation": ann,
        "annotation_meta": meta or {},
        "routes": routes,
        "mean_d_end_m": tot["mean_d_scored"] if use_cap else tot["mean_d_all"],
        "mean_d_end_m_all": tot["mean_d_all"],
        "mean_d_end_m_scored": tot["mean_d_scored"],
        "arrival_rate": tot["arrival_rate_scored"] if use_cap else tot["arrival_rate_all"],
        "arrival_rate_all": tot["arrival_rate_all"],
        "arrival_rate_scored": tot["arrival_rate_scored"],
        "total_arrived": tot["arrived_scored"] if use_cap else tot["arrived_all"],
        "total_n": n_scored if use_cap else n,
        "total_n_all": n,
        "total_n_scored": n_scored,
        "total_collision": tot["collision_scored_n"] if use_cap else tot["collision_n"],
        "collision_rate": tot["collision_rate_scored"] if use_cap else tot["collision_rate_all"],
        "collision_rate_all": tot["collision_rate_all"],
        "collision_rate_scored": tot["collision_rate_scored"],
        "spawn_collision_n": tot["spawn_n"],
        "spawn_rate": tot["spawn_rate"],
        "near_collision_n": tot["near_coll_n"],
        "arrived_but_collided_n": tot["arrived_but_collided_scored"] if use_cap else tot["arrived_but_collided"],
        "gates": cap_gates if use_cap else legacy_gates,
        "gates_legacy_all_eps": legacy_gates,
        "gates_cap_spawn_excluded": cap_gates,
        "primary_gate_pass": cap_pass if use_cap else legacy_pass,
        "primary_gate_pass_legacy": legacy_pass,
        "primary_gate_pass_cap": cap_pass,
        "seeds": seed_rows,
    }
    if extra:
        out.update(extra)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--stamp", required=True)
    ap.add_argument("--protocol", default="e2i_f_eval")
    ap.add_argument("--ann", required=True)
    ap.add_argument("--routes", required=True)
    ap.add_argument("--success-dist", type=float, default=0.50)
    ap.add_argument("--gate-mode", choices=["cap", "legacy"], default="cap")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    meta = {}
    ann_base = Path(args.ann).name
    for mp in (
        Path("artifacts") / f"{ann_base.replace('.json', '.meta.json')}",
        Path(ann_base.replace(".json", ".meta.json")),
    ):
        if mp.is_file():
            meta = json.loads(mp.read_text(encoding="utf-8"))
            break

    out = summarize_eval(
        tag=args.tag,
        stamp=args.stamp,
        protocol=args.protocol,
        ann=args.ann,
        routes=args.routes,
        success_dist_m=args.success_dist,
        gate_mode=args.gate_mode,
        meta=meta,
    )
    out_path = Path(args.out) if args.out else Path(f"artifacts/indoor_e2i_{args.tag}_summary_{args.stamp}.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
