"""V1 three-signal gate entrypoint (frozen spec §V1).

Mirrors ``_v0_gate`` split/merge workflow:

    # metric self-check (no GPU):
    python -m experiments.aerial.rl._v1_gate --self-check

    # merge partials from H100 (②, ③) + 4090 (①):
    python -m experiments.aerial.rl._v1_gate --merge \\
        v1_partial_coll.json v1_partial_wm.json v1_partial_tau_depth.json

Does **not** flip yaml — human action only after authoritative merge exits 0.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from experiments.aerial.rl import v1_metrics as metrics
from experiments.aerial.rl.env.obs import Observation

_ALL_SIGNALS = ("1", "2", "3")


def _parse_signals(spec: Optional[str]) -> set[str]:
    if not spec:
        return set(_ALL_SIGNALS)
    req = {s.strip() for s in spec.split(",") if s.strip()}
    bad = req - set(_ALL_SIGNALS)
    if bad:
        raise SystemExit(f"[v1-gate] --signals: unknown {sorted(bad)}; pick from 1,2,3")
    if not req:
        raise SystemExit("[v1-gate] --signals: empty selection")
    return req


def _merge_partials(paths: List[Path]) -> Dict[str, Any]:
    signals: Dict[str, Any] = {}
    for pth in paths:
        blob = json.loads(pth.read_text())
        part = blob.get("signals") or blob.get("details") or {}
        for k, v in part.items():
            if k in signals:
                print(f"[v1-gate] WARN: signal {k} in multiple partials; {pth} wins",
                      file=sys.stderr)
            signals[k] = v
    return signals


def assemble_verdict(s1: Dict[str, Any], s2: Dict[str, Any], s3: Dict[str, Any]) -> Dict[str, Any]:
    return metrics.aggregate_v1_verdict({"1": s1, "2": s2, "3": s3})


def _emit(obj: Dict[str, Any], path: Optional[str]) -> None:
    text = json.dumps(obj, indent=2, default=str)
    print(text)
    if path:
        Path(path).write_text(text + "\n")
        print(f"[v1-gate] wrote {path}", file=sys.stderr)


def _self_check() -> int:
    s1 = metrics.check_collision_reduction(0.10, 0.07, delta=0.20)
    s2 = metrics.check_wm_fidelity(
        {"ok": True, "reward_ok": True, "done_ok": True, "recon_growth_ok": True},
        agg={"coll_traj_pos": 0, "latent_norm_max": 19.0},
        recon_growth_ok=True,
    )
    # Auth-shaped ③ (Phase 2): low co-trigger + tau_only + MAE within bound.
    d = np.array([True, False, True, False, False, False, False, False] * 20)
    t = np.array([False, True, False, False, False, False, False, False] * 20)
    s3 = metrics.check_dual_channel_independence(
        d, t, phase="auth", tau_mae_s=1.0, depth_pred_vs_gt_both_fail_frac=0.05
    )
    verdict = assemble_verdict(s1, s2, s3)
    if not verdict["ok"]:
        print("[v1-gate] self-check FAIL", file=sys.stderr)
        _emit(verdict, None)
        return 1
    print("[v1-gate] self-check PASS")
    return 0


def _signal3_from_dataset(
    dataset_root: Path,
    *,
    min_depth_m: float,
    min_tau_s: float,
    max_frames: int = 5000,
    phase: str = "proxy",
    depth_ckpt: Optional[Path] = None,
    tau_kind: str = "gt_proxy",
    tau_ckpt: Optional[Path] = None,
    heldout_frac: float = 0.25,
    device: str = "cpu",
    nav_band_max_tau_s: float = 10.0,
) -> Dict[str, Any]:
    """Offline V1-③.

    * ``phase=proxy`` — GT depth min + GT τ (Phase 1; not merge-eligible).
    * ``phase=auth`` — ``DepthMinPredictor`` D̂ + FOE τ (no GT depth at τ
      inference); MAE vs GT τ on navigation-band frames; both_fail ≤ 0.20.
    """
    from experiments.aerial.rl import dataset as ds
    from experiments.aerial.rl.depth_geometry import forward_min_depth
    from experiments.aerial.rl.tau_predictor import (
        gt_tau_from_depth_velocity,
        make_tau_predictor,
    )

    root = dataset_root.expanduser().resolve()
    episodes = ds.load_dataset(root)
    phase_l = str(phase).lower()
    if phase_l not in ("proxy", "auth"):
        return {"ok": False, "reason": f"unknown phase {phase!r}; use proxy|auth"}

    if phase_l == "proxy":
        depth_breach: List[bool] = []
        tau_breach: List[bool] = []
        for ep in episodes:
            for tr in ep:
                obs = tr.obs
                if obs.depth is None:
                    continue
                d_hat = obs.info.get("depth_min_pred")
                if d_hat is None:
                    d_hat = forward_min_depth(obs.depth, center_frac=0.5)
                tau = obs.info.get("tau_pred")
                if tau is None:
                    tau = gt_tau_from_depth_velocity(obs.depth, obs)
                if d_hat is None or tau is None:
                    continue
                depth_breach.append(float(d_hat) < min_depth_m)
                tau_breach.append(float(tau) < min_tau_s)
                if len(depth_breach) >= max_frames:
                    break
            if len(depth_breach) >= max_frames:
                break
        if not depth_breach:
            return {"ok": False, "reason": "no depth frames with τ/D̂ fields"}
        return metrics.check_dual_channel_independence(
            np.asarray(depth_breach, dtype=bool),
            np.asarray(tau_breach, dtype=bool),
            phase="proxy",
        )

    # --- Phase 2 authoritative ---
    if depth_ckpt is None:
        return {"ok": False, "reason": "auth phase needs --depth-ckpt (DepthMinPredictor)"}
    from experiments.aerial.rl.depth_predictor import DepthMinPredictor

    predictor = DepthMinPredictor.from_checkpoint(depth_ckpt, device=device)
    tau_pred = make_tau_predictor(
        kind=tau_kind if tau_kind != "gt_proxy" else "foe",
        use_gt_depth=False,
        ckpt=tau_ckpt,
        device=device,
    )

    n_ep = len(episodes)
    hold_start = int(n_ep * (1.0 - float(heldout_frac))) if n_ep else 0
    held = episodes[hold_start:] if hold_start < n_ep else episodes
    if not held:
        held = episodes

    depth_breach = []
    tau_breach = []
    gt_depth_breach: List[bool] = []
    tau_err: List[float] = []
    for ep in held:
        predictor.reset()
        tau_pred.reset()
        for tr in ep:
            obs = tr.obs
            if obs.depth is None:
                continue
            d_pred = predictor.predict_min(obs)
            # FOE path must not read obs.depth — strip for predict_tau.
            depth_gt = obs.depth
            obs_rgb = Observation(
                rgb=obs.rgb,
                state=obs.state,
                collided=obs.collided,
                depth=None,
                imu=obs.imu,
                t=obs.t,
                info=dict(obs.info),
            )
            tau = tau_pred.predict_tau(obs_rgb)
            if d_pred is None or tau is None:
                continue
            d_gt = forward_min_depth(depth_gt, center_frac=0.5)
            depth_breach.append(float(d_pred) < min_depth_m)
            tau_breach.append(float(tau) < min_tau_s)
            gt_depth_breach.append(float(d_gt) < min_depth_m)
            tau_gt = gt_tau_from_depth_velocity(depth_gt, obs)
            if (
                tau_gt is not None
                and np.isfinite(tau_gt)
                and float(tau_gt) <= float(nav_band_max_tau_s)
            ):
                tau_err.append(abs(float(tau) - float(tau_gt)))
            if len(depth_breach) >= max_frames:
                break
        if len(depth_breach) >= max_frames:
            break

    if not depth_breach:
        return {"ok": False, "reason": "auth: no frames with D̂_pred + FOE τ"}

    # D̂_pred vs GT-depth trigger both-fail (design §1.2.3 Phase 2 D̂ row).
    d_pred_arr = np.asarray(depth_breach, dtype=bool)
    d_gt_arr = np.asarray(gt_depth_breach, dtype=bool)
    depth_vs_gt_both = float(np.mean(d_pred_arr & d_gt_arr)) if d_pred_arr.size else 1.0

    tau_mae = float(np.mean(tau_err)) if tau_err else float("nan")
    out = metrics.check_dual_channel_independence(
        d_pred_arr,
        np.asarray(tau_breach, dtype=bool),
        phase="auth",
        tau_mae_s=tau_mae if tau_err else None,
        depth_pred_vs_gt_both_fail_frac=depth_vs_gt_both,
    )
    out["tau_kind"] = tau_pred._resolved_kind()
    out["depth_ckpt"] = str(Path(depth_ckpt).expanduser().resolve())
    out["heldout_frac"] = float(heldout_frac)
    out["n_tau_mae_frames"] = int(len(tau_err))
    out["v0_reproj_note"] = (
        "D̂ median reproj must still satisfy V0 ③ ≤0.25 on same depth ckpt "
        "(cite v0_gate_r60_20260814 / depth_ckpt_da3_r60_20260814)"
    )
    return out


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="V1 three-signal gate (frozen spec §V1)")
    p.add_argument("--self-check", action="store_true")
    p.add_argument("--merge", nargs="+", default=None, metavar="JSON")
    p.add_argument("--emit", default=None, help="write verdict JSON")
    p.add_argument("--signals", default=None, help="subset: 1,2,3")
    p.add_argument("--dataset", default=None, help="for offline signal 3")
    p.add_argument("--v0-coll-rate", type=float, default=None, help="V0 baseline for signal 1")
    p.add_argument("--v1-coll-rate", type=float, default=None, help="V1 measured coll rate")
    p.add_argument("--fidelity-json", default=None, help="wm_eval fidelity verdict blob")
    p.add_argument("--min-depth-m", type=float, default=1.5)
    p.add_argument("--min-tau-s", type=float, default=1.0)
    p.add_argument(
        "--phase3",
        default="proxy",
        choices=("proxy", "auth"),
        help="V1-③ Phase 1 proxy (GT) vs Phase 2 auth (FOE + D̂_pred)",
    )
    p.add_argument("--depth-ckpt", default=None, help="DepthMinPredictor ckpt (auth ③)")
    p.add_argument(
        "--tau-kind",
        default="foe",
        help="auth τ kind: foe | foe_calibrated (ignored for proxy)",
    )
    p.add_argument("--tau-ckpt", default=None, help="optional FOE calibrator ckpt")
    p.add_argument("--heldout-frac", type=float, default=0.25)
    p.add_argument("--device", default="cpu")
    args = p.parse_args(argv)

    if args.self_check:
        return _self_check()

    if args.merge:
        signals = _merge_partials([Path(x) for x in args.merge])
        missing = [k for k in _ALL_SIGNALS if k not in signals]
        if missing:
            print(f"[v1-gate] merge missing signals {missing}", file=sys.stderr)
            return 2
        verdict = metrics.aggregate_v1_verdict({k: signals[k] for k in _ALL_SIGNALS})
        verdict["merged_from"] = [str(x) for x in args.merge]
        _emit(verdict, args.emit)
        return 0 if verdict["ok"] else 1

    wanted = _parse_signals(args.signals)
    signals: Dict[str, Any] = {}

    if "1" in wanted:
        if args.v0_coll_rate is None or args.v1_coll_rate is None:
            signals["1"] = {"ok": False, "reason": "need --v0-coll-rate and --v1-coll-rate"}
        else:
            signals["1"] = metrics.check_collision_reduction(args.v0_coll_rate, args.v1_coll_rate)

    if "2" in wanted:
        if not args.fidelity_json:
            signals["2"] = {"ok": False, "reason": "need --fidelity-json from _wm_fidelity_eval"}
        else:
            blob = json.loads(Path(args.fidelity_json).read_text())
            signals["2"] = metrics.check_wm_fidelity(
                blob.get("verdict") or blob,
                agg=blob.get("agg"),
                recon_growth_ok=(blob.get("verdict") or blob).get("recon_growth_ok"),
            )

    if "3" in wanted:
        if not args.dataset:
            signals["3"] = {"ok": False, "reason": "need --dataset for dual-channel eval"}
        else:
            depth_ckpt = Path(args.depth_ckpt).expanduser() if args.depth_ckpt else None
            tau_ckpt = Path(args.tau_ckpt).expanduser() if args.tau_ckpt else None
            signals["3"] = _signal3_from_dataset(
                Path(args.dataset),
                min_depth_m=float(args.min_depth_m),
                min_tau_s=float(args.min_tau_s),
                phase=str(args.phase3),
                depth_ckpt=depth_ckpt,
                tau_kind=str(args.tau_kind),
                tau_ckpt=tau_ckpt,
                heldout_frac=float(args.heldout_frac),
                device=str(args.device),
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
