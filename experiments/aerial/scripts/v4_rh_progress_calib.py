#!/usr/bin/env python3
"""RH progress-head calibration from existing §A decomp JSON (offline).

For each imagined arm, compare per-step ``out.progress`` (reward-head readout)
to geometric ``analytic_progress`` = Δ‖goal_rel‖ reconstructed from the stored
``per_step.goal_dist`` series.

``goal_dist[t] - goal_dist[t+1]`` equals batch-mean
``analytic_progress(g_t, a_t[:3])`` because imagination advances
``g[:3] -= a[:3]`` (``advance_goal_rel_body`` / ``_goal_dist_traj``). Maneuver
is NOT included: ``out.progress`` is the progress channel only.

This is RH vs **stub kinematics**, not vs real-world displacement.

Usage (125, no renderer):
  $PYTHON_BIN experiments/aerial/scripts/v4_rh_progress_calib.py \\
    --a23 artifacts/v4_imagine_return_decomp_c2train_a23_20260818.json \\
    --a4  artifacts/v4_imagine_return_decomp_c2train_a4_20260818.json \\
    --out artifacts/v4_rh_progress_calib_c2train_20260818.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np


def _repo_root(explicit: Optional[str]) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    return Path(__file__).resolve().parents[3]


def _ols(x: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
    x = np.asarray(x, dtype=np.float64).reshape(-1)
    y = np.asarray(y, dtype=np.float64).reshape(-1)
    if x.size < 2 or float(np.std(x)) < 0.05:
        return {
            "slope": None,
            "intercept": float(np.mean(y)),
            "r": None,
            "note": "degenerate: analytic nearly constant (constant-action arm)",
        }
    xm, ym = float(np.mean(x)), float(np.mean(y))
    cov = float(np.sum((x - xm) * (y - ym)))
    varx = float(np.sum((x - xm) ** 2))
    slope = cov / varx
    intercept = ym - slope * xm
    r = float(np.corrcoef(x, y)[0, 1]) if x.size >= 3 else None
    return {"slope": slope, "intercept": intercept, "r": r}


def _arm_calib(name: str, arm: Dict[str, Any]) -> Dict[str, Any]:
    ps = arm["per_step"]
    rh = np.asarray(ps["progress"], dtype=np.float64).reshape(-1)
    gdist = np.asarray(ps["goal_dist"], dtype=np.float64).reshape(-1)
    if gdist.size != rh.size + 1:
        raise ValueError(f"{name}: goal_dist len {gdist.size} != progress len {rh.size}+1")
    analytic = gdist[:-1] - gdist[1:]
    residual = rh - analytic
    ols = _ols(analytic, rh)
    sum_rh = float(np.sum(rh))
    sum_an = float(np.sum(analytic))
    ratio = float(sum_rh / sum_an) if abs(sum_an) > 1e-9 else None
    return {
        "arm": name,
        "horizon": int(rh.size),
        "goal_dist_0": float(gdist[0]),
        "goal_dist_T": float(gdist[-1]),
        "sum_rh_progress": sum_rh,
        "sum_analytic": sum_an,
        "ratio_rh_over_analytic": ratio,
        "mean_rh": float(np.mean(rh)),
        "mean_analytic": float(np.mean(analytic)),
        "mean_residual": float(np.mean(residual)),
        "mae": float(np.mean(np.abs(residual))),
        "ols_rh_on_analytic": ols,
        "wrong_sign": bool(np.mean(rh) > 0.0 and np.mean(analytic) < 0.0),
        "per_step": {
            "t": list(range(int(rh.size))),
            "rh_progress": rh.tolist(),
            "analytic_progress": analytic.tolist(),
            "residual": residual.tolist(),
            "goal_dist": gdist.tolist(),
            "act_norm3": list(ps.get("act_norm3") or []),
        },
    }


def _file_calib(path: Path) -> Dict[str, Any]:
    d = json.loads(path.read_text())
    arms = {k: _arm_calib(k, v) for k, v in d["arms"].items()}
    return {
        "source": str(path),
        "seed": d.get("seed"),
        "clip_actions": d.get("clip_actions"),
        "horizon": d.get("horizon"),
        "goal_rel0": d.get("goal_rel0"),
        "policy_class": d.get("policy_class"),
        "n_action_clipped": d.get("n_action_clipped"),
        "actor_ckpt": d.get("actor_ckpt"),
        "wm_ckpt": d.get("wm_ckpt"),
        "arms": arms,
    }


def _verdict(files: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Pre-committed 2026-08-18 rule (RH vs stub geometry, not vs real env).

    reopen_rh if ANY of:
      - forward-like arm (a_pi / b_forward / b3_*) has |ratio| >= 2
      - retreat-like arm has wrong_sign (RH mean>0 while analytic mean<0)
    else calibrated (do not reopen from this curve).
    """
    triggers: List[str] = []
    for rec in files:
        src = Path(rec["source"]).name
        for name, arm in rec["arms"].items():
            ratio = arm["ratio_rh_over_analytic"]
            fwd = name.startswith(("a_pi", "b_forward", "b3_"))
            ret = name.startswith(("c_retreat", "c3_"))
            if fwd and ratio is not None and abs(ratio) >= 2.0:
                triggers.append(f"{src}:{name} ratio={ratio:.2f}")
            if ret and arm["wrong_sign"]:
                triggers.append(
                    f"{src}:{name} wrong_sign rh={arm['mean_rh']:+.3f} "
                    f"an={arm['mean_analytic']:+.3f}"
                )
    reopen = bool(triggers)
    return {
        "reopen_rh": reopen,
        "rule": (
            "forward |ratio|>=2 or retreat RH>0 while analytic<0 → reopen_rh; "
            "else RH matches stub kinematics, do not reopen from this curve"
        ),
        "triggers": triggers,
        "disposition": (
            "sign_reopen_rh_progress_head"
            if reopen
            else "do_not_reopen_rh_from_this_curve"
        ),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--repo", default=None)
    p.add_argument(
        "--a23",
        default="artifacts/v4_imagine_return_decomp_c2train_a23_20260818.json",
    )
    p.add_argument(
        "--a4",
        default="artifacts/v4_imagine_return_decomp_c2train_a4_20260818.json",
    )
    p.add_argument("--out", default="artifacts/v4_rh_progress_calib_c2train_20260818.json")
    args = p.parse_args()

    root = _repo_root(args.repo)
    paths = []
    for rel in (args.a23, args.a4):
        path = Path(rel).expanduser()
        if not path.is_absolute():
            path = root / path
        if not path.is_file():
            print(f"missing {path}", flush=True)
            return 2
        paths.append(path)

    files = [_file_calib(path) for path in paths]
    verdict = _verdict(files)
    out = {"verdict": verdict, "files": files}
    out_path = Path(args.out).expanduser()
    if not out_path.is_absolute():
        out_path = root / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2) + "\n")

    print(json.dumps(verdict, indent=2))
    for rec in files:
        print(f"\n# {Path(rec['source']).name} clip={rec['clip_actions']}")
        print(
            f"{'arm':<22} {'ΣRH':>8} {'ΣΔ‖g‖':>8} {'ratio':>7} {'MAE':>7} "
            f"{'slope':>7} {'wrong':>5}"
        )
        for name, arm in rec["arms"].items():
            ratio = arm["ratio_rh_over_analytic"]
            slope = arm["ols_rh_on_analytic"]["slope"]
            slope_s = f"{slope:7.3f}" if slope is not None else "    n/a"
            print(
                f"{name:<22} {arm['sum_rh_progress']:+8.2f} "
                f"{arm['sum_analytic']:+8.2f} "
                f"{(ratio if ratio is not None else float('nan')):7.2f} "
                f"{arm['mae']:7.3f} {slope_s} "
                f"{str(arm['wrong_sign']):>5}"
            )
    print(f"\n[calib] wrote {out_path}")
    return 0 if not verdict["reopen_rh"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
