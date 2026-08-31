#!/usr/bin/env python3
"""Run V1 gate partials and emit JSON (H100 offline + 4090 rollout).

Usage (H100, from repo root with venv + cuda):
  python experiments/aerial/scripts/v1_gate_run_partials.py h100 \\
    --repo ~/aerial-wam-v2 \\
    --dataset ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/dataset_v0_local_depth_r60_20260814 \\
    --wm-ckpt experiments/aerial/rl/artifacts/wm_ckpt_v1a_20260815/wm_step_500.pt \\
    --out-dir experiments/aerial/rl/artifacts/v1_gate_r60_20260815

Usage (4090 / H100→4090 renderer @ configs/aerial_rl_rollout.yaml):
  python experiments/aerial/scripts/v1_gate_run_partials.py rollout4090 \\
    --repo ~/aerial-wam-v2 \\
    --rollout-dataset experiments/aerial/rl/artifacts/dataset_v0_headon_20260811 \\
    --depth-ckpt experiments/aerial/rl/artifacts/depth_ckpt_da3_r60_20260814/depth_step_2000_da3_ft_head.pt \\
    --out-dir experiments/aerial/rl/artifacts/v1_gate_r60_20260815
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


def _repo_root(explicit: Optional[str]) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    return Path(__file__).resolve().parents[3]


def _emit(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str) + "\n")
    print(f"[v1-run] wrote {path}")


def run_h100(args: argparse.Namespace) -> int:
    root = _repo_root(args.repo)
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    out_dir = Path(args.out_dir).expanduser()
    if not out_dir.is_absolute():
        out_dir = root / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    dataset = Path(args.dataset).expanduser()
    results: Dict[str, Any] = {"host": "h100", "dataset": str(dataset)}

    # --- Signal 3: dual-channel independence (offline) ---
    from experiments.aerial.rl._v1_gate import _signal3_from_dataset

    depth_ckpt = None
    if getattr(args, "depth_ckpt", None):
        depth_ckpt = Path(args.depth_ckpt).expanduser()
        if not depth_ckpt.is_absolute():
            depth_ckpt = root / depth_ckpt
    tau_ckpt = None
    if getattr(args, "tau_ckpt", None):
        tau_ckpt = Path(args.tau_ckpt).expanduser()
        if not tau_ckpt.is_absolute():
            tau_ckpt = root / tau_ckpt

    s3 = _signal3_from_dataset(
        dataset,
        min_depth_m=float(args.min_depth_m),
        min_tau_s=float(args.min_tau_s),
        phase=str(getattr(args, "phase3", "proxy")),
        depth_ckpt=depth_ckpt,
        tau_kind=str(getattr(args, "tau_kind", "foe")),
        tau_ckpt=tau_ckpt,
        heldout_frac=float(getattr(args, "heldout_frac", 0.25)),
        device=str(args.device),
    )
    partial3 = {"partial": True, "signals_requested": ["3"], "ok": bool(s3.get("ok")), "signals": {"3": s3}}
    _emit(out_dir / "v1_partial_3_r60_20260815.json", partial3)
    results["signal3"] = s3

    # --- Signal 2: WM fidelity (held-out) ---
    s2: Dict[str, Any]
    try:
        import torch  # noqa: F401
        from experiments.aerial.rl import dataset as ds
        from experiments.aerial.rl import wm_eval
        from experiments.aerial.rl._wm_fidelity_eval import (
            _heldout_split,
            _make_windows,
            _recon_curve,
        )
        from experiments.aerial.rl._wm_train_validate import _load_world_model_cfg, _refuse_v0
        from experiments.aerial.rl.dynamics_torch import TorchRSSMDynamics

        ckpt = Path(args.wm_ckpt).expanduser()
        if not ckpt.is_absolute():
            ckpt = root / ckpt
        cfg_path = root / args.config
        wm_cfg = _load_world_model_cfg(cfg_path)
        wm_cfg.setdefault("device", args.device)
        _refuse_v0(dataset, False)
        episodes = ds.load_dataset(dataset, skip_quarantined=True)
        held = _heldout_split(episodes, float(args.heldout_frac))
        windows = _make_windows(held, int(args.horizon), int(args.n_starts))
        sample_obs = held[0][0].obs
        wm_cfg["image_size"] = int(__import__("numpy").asarray(sample_obs.rgb).shape[0])
        model = TorchRSSMDynamics.from_config(wm_cfg)
        payload = model.load_checkpoint(ckpt)
        out = wm_eval.evaluate(model, windows, horizon=int(args.horizon))
        agg, verdict = out["agg"], out["verdict"]
        recon = _recon_curve(model, windows, int(args.horizon))
        passed = bool(verdict["passed"] and recon["recon_growth_ok"])
        fidelity_blob = {
            "verdict": {**verdict, "passed": passed, "recon_growth_ok": recon["recon_growth_ok"]},
            "agg": agg,
            "recon": recon,
            "ckpt": str(ckpt),
            "ckpt_step": payload.get("step"),
            "heldout_frac": float(args.heldout_frac),
        }
        _emit(out_dir / "v1_fidelity_r60_20260815.json", fidelity_blob)
        from experiments.aerial.rl import v1_metrics

        s2 = v1_metrics.check_wm_fidelity(
            fidelity_blob["verdict"],
            agg=fidelity_blob.get("agg"),
            recon_growth_ok=fidelity_blob["verdict"].get("recon_growth_ok"),
        )
        s2["fidelity_json"] = str(out_dir / "v1_fidelity_r60_20260815.json")
    except Exception as exc:
        s2 = {"ok": False, "reason": f"fidelity eval failed: {exc}"}

    partial2 = {"partial": True, "signals_requested": ["2"], "ok": bool(s2.get("ok")), "signals": {"2": s2}}
    _emit(out_dir / "v1_partial_2_r60_20260815.json", partial2)
    results["signal2"] = s2

    _emit(out_dir / "v1_h100_run_summary.json", results)
    ok = bool(s3.get("ok")) and bool(s2.get("ok"))
    print(f"[v1-run] H100 partials ok={ok} sig3={s3.get('ok')} sig2={s2.get('ok')}")
    return 0 if ok else 1


def _episode_collision_rate(collided: List[List[bool]]) -> float:
    if not collided:
        return float("nan")
    hits = sum(1 for ep in collided if any(ep))
    return float(hits / len(collided))


def _frame_near_coll_rate(near: List[List[bool]]) -> float:
    total = sum(len(ep) for ep in near)
    if total <= 0:
        return float("nan")
    return float(sum(sum(1 for x in ep if x) for ep in near) / total)


def run_rollout4090(args: argparse.Namespace) -> int:
    root = _repo_root(args.repo)
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    import yaml

    from experiments.aerial.rl import v0_metrics as v0m
    from experiments.aerial.rl import v0_rollout_eval as rollout
    from experiments.aerial.rl import v1_metrics
    from experiments.aerial.rl.depth_predictor import DepthMinPredictor
    from experiments.aerial.rl.reward import RewardConfig
    from experiments.aerial.rl.safety import DepthTauShield, ThresholdSafetyShield
    from experiments.aerial.rl.tau_predictor import make_tau_predictor
    from experiments.aerial.rl.train_rl import HeuristicPolicy, _build_env

    out_dir = Path(args.out_dir).expanduser()
    if not out_dir.is_absolute():
        out_dir = root / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    cfg_path = root / args.config
    cfg = yaml.safe_load(cfg_path.read_text()) or {}
    env = _build_env(cfg.get("env", {}) or {})
    reward_cfg = RewardConfig(**(cfg.get("reward", {}) or {})) if cfg.get("reward") else None
    thr = v0m.DEFAULT_THRESHOLDS
    # Authoritative ①: trigger at metric-band by default so V0 hard/near can
    # leave the zero floor (standoff=3.0 often tied-zero's both arms).
    shield_trigger_m = float(args.shield_trigger_m)

    rollout_ds = Path(args.rollout_dataset).expanduser()
    if not rollout_ds.is_absolute():
        rollout_ds = root / rollout_ds
    depth_ckpt = Path(args.depth_ckpt).expanduser()
    if not depth_ckpt.is_absolute():
        depth_ckpt = root / depth_ckpt

    tau_cfg = cfg.get("tau_predictor", {}) or {}
    tau_kind = str(args.tau_kind or tau_cfg.get("kind") or "foe_calibrated")
    tau_ckpt = args.tau_ckpt or tau_cfg.get("ckpt")
    if tau_ckpt:
        tau_ckpt = Path(str(tau_ckpt)).expanduser()
        if not tau_ckpt.is_absolute():
            tau_ckpt = root / tau_ckpt
    allow_tied_zero = bool(args.allow_tied_zero)

    policy = HeuristicPolicy(goal_getter=lambda: getattr(env, "goal", None))
    from experiments.aerial.rl._v0_gate import _obstacle_candidate_positions

    cand, cand_yaw = _obstacle_candidate_positions(rollout_ds, min_altitude_m=0.0)
    starts, scan_diag = rollout.make_obstacle_facing_episodes(
        env, int(args.n_episodes), cand, seed=int(args.seed),
        candidate_yaws=cand_yaw,
        obstacle_max_m=25.0, center_frac=0.3,
        probe_policy=policy, probe_near_m=float(thr.near_collision_depth_m),
        probe_steps=40, reward_cfg=reward_cfg,
        preserve_order=True, max_scans=1000, log_every=20,
    )
    if not starts:
        s1 = {"ok": False, "reason": "no obstacle-facing starts", "scan": scan_diag}
        partial1 = {"partial": True, "signals_requested": ["1"], "ok": False, "signals": {"1": s1}}
        _emit(out_dir / "v1_partial_1_r60_20260815.json", partial1)
        return 1

    probe = scan_diag.get("probe") or {}
    if int(probe.get("collided", 0)) <= 0 and not (
        probe.get("reached_fwd_m") and float((probe["reached_fwd_m"] or {}).get("min") or 1e9) < float(thr.near_collision_depth_m)
    ):
        s1 = {
            "ok": False,
            "reason": "starts not collision-bearing (probe forward-near/collided required)",
            "scan": scan_diag,
        }
        partial1 = {"partial": True, "signals_requested": ["1"], "ok": False, "signals": {"1": s1}}
        _emit(out_dir / "v1_partial_1_r60_20260815.json", partial1)
        return 1

    predictor = DepthMinPredictor.from_checkpoint(depth_ckpt, device=args.device)
    tau_pred = make_tau_predictor(
        kind=tau_kind,
        ckpt=tau_ckpt,
        device=str(args.device),
        center_frac=float(tau_cfg.get("center_frac", 0.5)),
        min_closing_m_s=float(tau_cfg.get("min_closing_m_s", 0.05)),
        max_tau_s=float(tau_cfg.get("max_tau_s", 60.0)),
        dt_s=float(tau_cfg.get("dt_s", 0.1)),
        use_gt_depth=False,
    )

    def _run_v1_shield(shield_kind: str) -> Dict[str, Any]:
        collided_on: List[List[bool]] = []
        near_on: List[List[bool]] = []
        drop_stats: Dict[str, int] = {}
        for epi in starts:
            if hasattr(policy, "reset"):
                policy.reset()
            if hasattr(tau_pred, "reset"):
                tau_pred.reset()
            if shield_kind == "depth_tau":
                shield = DepthTauShield(
                    min_depth_m=shield_trigger_m,
                    min_tau_s=float(cfg.get("safety", {}).get("min_tau_s", 1.0)),
                )
            elif shield_kind == "off":
                shield = None
            else:
                shield = ThresholdSafetyShield(
                    min_depth_m=shield_trigger_m,
                    min_tau_s=float(cfg.get("safety", {}).get("min_tau_s", 1.0)),
                )
            ep = rollout._run_one_resilient(
                env, policy, epi, max_steps=int(args.max_steps), reward_cfg=reward_cfg,
                shield=shield, depth_predictor=predictor if shield is not None else None,
                tau_predictor=tau_pred if shield_kind == "depth_tau" else None,
                drop_stats=drop_stats,
            )
            if ep is None:
                continue
            m = rollout._episode_masks(ep, near_collision_depth_m=float(thr.near_collision_depth_m))
            collided_on.append(m["collided"])
            near_on.append(m["near"])
        hard_rate = _episode_collision_rate(collided_on)
        near_ep_rate = _episode_collision_rate(near_on)
        near_frame_rate = _frame_near_coll_rate(near_on)
        return {
            "collision_rate": hard_rate,
            "near_coll_episode_rate": near_ep_rate,
            "near_coll_rate": near_frame_rate,
            "n_episodes": len(collided_on),
            "drop_stats": drop_stats,
            "shield_kind": shield_kind,
            "shield_trigger_m": shield_trigger_m if shield_kind != "off" else None,
        }

    v0_stats = _run_v1_shield("threshold")
    v1_stats = _run_v1_shield("depth_tau")
    off_stats = _run_v1_shield("off")

    # Prefer hard episode coll_rate (design §1.2.1). If hard_v0==0, fall back to
    # episode near-coll. Tied-zero is diagnostic only unless --allow-tied-zero.
    baseline_kind = "hard_collision"
    v0_rate = float(v0_stats["collision_rate"])
    v1_rate = float(v1_stats["collision_rate"])
    off_hard = float(off_stats["collision_rate"])
    if args.v0_coll_rate is not None:
        v0_rate = float(args.v0_coll_rate)
        baseline_kind = "cli_override"
        s1 = v1_metrics.check_collision_reduction(v0_rate, v1_rate)
    elif v0_rate > 0:
        s1 = v1_metrics.check_collision_reduction(v0_rate, v1_rate)
        baseline_kind = str(s1.get("baseline_kind") or "delta_reduction")
    elif float(v0_stats["near_coll_episode_rate"]) > 0:
        v0_rate = float(v0_stats["near_coll_episode_rate"])
        v1_rate = float(v1_stats["near_coll_episode_rate"])
        baseline_kind = "near_coll_episode"
        s1 = v1_metrics.check_collision_reduction(v0_rate, v1_rate)
        s1["baseline_kind"] = baseline_kind
    else:
        baseline_kind = "tied_zero_collision_bearing"
        s1 = v1_metrics.check_collision_reduction(
            v0_rate, v1_rate,
            shield_off_coll_rate=off_hard,
            allow_tied_zero=allow_tied_zero,
        )
        baseline_kind = str(s1.get("baseline_kind") or baseline_kind)
    s1["baseline_kind"] = baseline_kind
    s1["tau_kind"] = tau_kind
    s1["tau_ckpt"] = str(tau_ckpt) if tau_ckpt else None
    s1["v0_measured"] = v0_stats
    s1["v1_measured"] = v1_stats
    s1["shield_off_measured"] = off_stats
    s1["scan"] = scan_diag
    if baseline_kind == "near_coll_episode":
        s1["note"] = (
            "hard coll_rate_v0==0; compared episode near-coll rates under "
            f"same starts / trigger={shield_trigger_m:.2f}m / tau={tau_kind}"
        )
    elif baseline_kind == "tied_zero_collision_bearing":
        s1["note"] = (
            "V0/V1 shield-on hard and near-ep rates are 0 on starts with "
            f"shield-off coll_rate={off_hard:.3f}; tied-zero "
            f"{'soft PASS' if allow_tied_zero else 'NOT authoritative (FAIL)'}"
        )

    partial1 = {"partial": True, "signals_requested": ["1"], "ok": bool(s1.get("ok")), "signals": {"1": s1}}
    _emit(out_dir / "v1_partial_1_r60_20260815.json", partial1)
    print(
        f"[v1-run] 4090 signal1 ok={s1.get('ok')} kind={baseline_kind} "
        f"auth={s1.get('authoritative')} tau={tau_kind} "
        f"v0={v0_rate:.4f} v1={v1_rate:.4f} "
        f"hard_v0={v0_stats['collision_rate']:.4f} hard_v1={v1_stats['collision_rate']:.4f} "
        f"off_hard={off_stats['collision_rate']:.4f} trigger={shield_trigger_m}"
    )
    return 0 if s1.get("ok") else 1


def _python_bin() -> str:
    import os
    return os.environ.get("PYTHON_BIN", sys.executable)


def run_merge(args: argparse.Namespace) -> int:
    root = _repo_root(args.repo)
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from experiments.aerial.rl._v1_gate import _merge_partials, assemble_verdict

    out_dir = Path(args.out_dir).expanduser()
    if not out_dir.is_absolute():
        out_dir = root / out_dir
    paths = [
        out_dir / "v1_partial_1_r60_20260815.json",
        out_dir / "v1_partial_2_r60_20260815.json",
        out_dir / "v1_partial_3_r60_20260815.json",
    ]
    for p in paths:
        if not p.exists():
            print(f"[v1-run] missing {p}", file=sys.stderr)
            return 2
    signals = _merge_partials(paths)
    verdict = assemble_verdict(signals["1"], signals["2"], signals["3"])
    verdict["merged_from"] = [str(p) for p in paths]
    out = out_dir / "v1_gate_r60_20260815.json"
    _emit(out, verdict)
    return 0 if verdict.get("ok") else 1


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=("h100", "rollout4090", "merge"))
    p.add_argument("--repo", default=None)
    p.add_argument("--out-dir", default="experiments/aerial/rl/artifacts/v1_gate_r60_20260815")
    p.add_argument("--dataset", default="~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/dataset_v0_local_depth_r60_20260814")
    p.add_argument("--wm-ckpt", default="experiments/aerial/rl/artifacts/wm_ckpt_v1a_20260815/wm_step_500.pt")
    p.add_argument(
        "--config",
        default=None,
        help="yaml config; default aerial_rl.yaml (h100) / aerial_rl_rollout.yaml (rollout4090)",
    )
    p.add_argument("--device", default="cuda")
    p.add_argument("--heldout-frac", type=float, default=0.25)
    p.add_argument("--horizon", type=int, default=15)
    p.add_argument("--n-starts", type=int, default=1)
    p.add_argument("--min-depth-m", type=float, default=1.5)
    p.add_argument("--min-tau-s", type=float, default=1.0)
    p.add_argument(
        "--phase3",
        default="proxy",
        choices=("proxy", "auth"),
        help="V1-③: proxy=GT (Phase 1) or auth=FOE+D̂_pred (Phase 2)",
    )
    p.add_argument("--tau-kind", default="foe_calibrated", help="①/③ τ: foe | foe_calibrated | gt_proxy")
    p.add_argument("--tau-ckpt", default=None, help="optional FOE calibrator ckpt")
    p.add_argument("--rollout-dataset", default="experiments/aerial/rl/artifacts/dataset_v0_local_depth_r60_20260814")
    p.add_argument("--depth-ckpt", default="experiments/aerial/rl/artifacts/depth_ckpt_da3_r60_20260814/depth_step_2000_da3_ft_head.pt")
    p.add_argument("--n-episodes", type=int, default=8)
    p.add_argument("--max-steps", type=int, default=200)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--v0-coll-rate", type=float, default=None)
    p.add_argument(
        "--shield-trigger-m",
        type=float,
        default=1.5,
        help="V0/V1 shield reaction depth (authoritative ① default=1.5 metric band; 3.0 often tied-zero)",
    )
    p.add_argument(
        "--allow-tied-zero",
        action="store_true",
        help="soft PASS when V0/V1 both 0 on collision-bearing starts (NOT merge-eligible)",
    )
    args = p.parse_args()
    if args.config is None:
        args.config = (
            "configs/aerial_rl_rollout.yaml"
            if args.mode == "rollout4090"
            else "configs/aerial_rl.yaml"
        )
    if args.mode == "h100":
        return run_h100(args)
    if args.mode == "rollout4090":
        return run_rollout4090(args)
    return run_merge(args)


if __name__ == "__main__":
    raise SystemExit(main())
