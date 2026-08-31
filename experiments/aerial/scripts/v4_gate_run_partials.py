#!/usr/bin/env python3
"""Run V4 gate partials (4090 rollout) and merge (frozen spec §4).

Usage (4090 @ configs/aerial_rl_rollout.yaml):
  python experiments/aerial/scripts/v4_gate_run_partials.py rollout4090 \\
    --repo ~/aerial-wam-v2 \\
    --rollout-dataset ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/dataset_v0_local_depth_r60_20260814 \\
    --actor-ckpt experiments/aerial/rl/artifacts/v4_ac_ckpt_20260816/v4_ac_latest.pt \\
    --depth-ckpt experiments/aerial/rl/artifacts/depth_ckpt_da3_r60_20260814/depth_step_2000_da3_ft_head.pt \\
    --tau-ckpt experiments/aerial/rl/artifacts/tau_ckpt_foe_r60_20260815/tau_foe_calibrator.pt \\
    --env-host 127.0.0.1 \\
    --out-dir experiments/aerial/rl/artifacts/v4_gate_r60_20260816

  python experiments/aerial/scripts/v4_gate_run_partials.py merge \\
    --repo ~/aerial-wam-v2 \\
    --out-dir experiments/aerial/rl/artifacts/v4_gate_r60_20260816
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_PARTIAL1 = "v4_partial_1_r60_20260816.json"
_PARTIAL4 = "v4_partial_4_r60_20260816.json"
_MERGE_OUT = "v4_gate_r60_20260816.json"


def _repo_root(explicit: Optional[str]) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    return Path(__file__).resolve().parents[3]


def _emit(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str) + "\n")
    print(f"[v4-run] wrote {path}")


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

    import numpy as np
    import yaml

    from experiments.aerial.rl import v0_metrics as v0m
    from experiments.aerial.rl import v0_rollout_eval as rollout
    from experiments.aerial.rl import v4_episode_pool as epool
    from experiments.aerial.rl import v4_metrics
    from experiments.aerial.rl._v0_gate import _obstacle_candidate_positions
    from experiments.aerial.rl.actor_critic import LatentActorCritic, LatentActorDeployPolicy
    from experiments.aerial.rl.depth_predictor import DepthMinPredictor
    from experiments.aerial.rl.dynamics import StubLatentDynamics
    from experiments.aerial.rl.reward import RewardConfig
    from experiments.aerial.rl.tau_predictor import make_tau_predictor
    from experiments.aerial.rl.train_rl import HeuristicPolicy, _build_env, load_torch_dynamics

    out_dir = Path(args.out_dir).expanduser()
    if not out_dir.is_absolute():
        out_dir = root / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.spare_count is None:
        print(
            "[v4-run] --spare-count is required (RUNBOOK §3 item 11; "
            "see artifacts/V4_RUNBOOK_125_ISSUES.md)",
            file=sys.stderr,
        )
        return 2

    cfg_path = root / args.config
    cfg = yaml.safe_load(cfg_path.read_text()) or {}
    if args.env_host:
        cfg.setdefault("env", {})["host"] = str(args.env_host)
    env = _build_env(cfg.get("env", {}) or {})
    reward_cfg = RewardConfig(**(cfg.get("reward", {}) or {})) if cfg.get("reward") else None
    thr = v0m.DEFAULT_THRESHOLDS
    shield_trigger_m = float(args.shield_trigger_m)

    rollout_ds = Path(args.rollout_dataset).expanduser()
    if not rollout_ds.is_absolute():
        rollout_ds = root / rollout_ds
    if not rollout_ds.is_dir():
        print(f"[v4-run] missing rollout dataset {rollout_ds}", file=sys.stderr)
        return 2

    actor_ckpt = Path(args.actor_ckpt).expanduser()
    if not actor_ckpt.is_absolute():
        actor_ckpt = root / actor_ckpt
    if not actor_ckpt.is_file():
        print(f"[v4-run] missing actor ckpt {actor_ckpt}", file=sys.stderr)
        return 2

    depth_ckpt = Path(args.depth_ckpt).expanduser()
    if not depth_ckpt.is_absolute():
        depth_ckpt = root / depth_ckpt
    if not depth_ckpt.is_file():
        print(f"[v4-run] missing depth ckpt {depth_ckpt}", file=sys.stderr)
        return 2

    tau_cfg = cfg.get("tau_predictor", {}) or {}
    tau_kind = str(args.tau_kind or tau_cfg.get("kind") or "foe_calibrated")
    tau_ckpt = args.tau_ckpt or tau_cfg.get("ckpt")
    if tau_ckpt:
        tau_ckpt = Path(str(tau_ckpt)).expanduser()
        if not tau_ckpt.is_absolute():
            tau_ckpt = root / tau_ckpt
    if tau_ckpt and not tau_ckpt.is_file():
        print(f"[v4-run] missing tau ckpt {tau_ckpt}", file=sys.stderr)
        return 2

    heuristic = HeuristicPolicy(goal_getter=lambda: getattr(env, "goal", None))
    target_n = int(args.target_n)
    spare_count = int(args.spare_count)
    scan_n = target_n + spare_count
    cand, cand_yaw = _obstacle_candidate_positions(rollout_ds, min_altitude_m=0.0)
    starts, scan_diag = rollout.make_obstacle_facing_episodes(
        env,
        scan_n,
        cand,
        seed=int(args.seed),
        candidate_yaws=cand_yaw,
        obstacle_max_m=25.0,
        center_frac=0.3,
        probe_policy=heuristic,
        probe_near_m=float(thr.near_collision_depth_m),
        probe_steps=40,
        reward_cfg=reward_cfg,
        preserve_order=True,
        max_scans=1000,
        log_every=20,
    )
    primary, spare, spare_manifest = epool.split_primary_spare(
        starts,
        target_n=target_n,
        spare_count=spare_count,
        layer="gate",
        seed=int(args.seed),
    )
    manifest_path = out_dir / "p0c_spare_manifest.json"
    spare_manifest.write(manifest_path)
    print(
        f"[v4-run] P0c spare manifest: primary={len(primary)} spare={len(spare)} "
        f"target_n={target_n} → {manifest_path}"
    )
    if not primary:
        s1 = {"ok": False, "reason": "no obstacle-facing starts", "scan": scan_diag}
        partial1 = {"partial": True, "signals_requested": ["1"], "ok": False, "signals": {"1": s1}}
        _emit(out_dir / _PARTIAL1, partial1)
        s4 = {"ok": False, "reason": "no starts for safety eval", "scan": scan_diag}
        partial4 = {"partial": True, "signals_requested": ["4"], "ok": False, "signals": {"4": s4}}
        _emit(out_dir / _PARTIAL4, partial4)
        return 1

    probe = scan_diag.get("probe") or {}
    if int(probe.get("collided", 0)) <= 0 and not (
        probe.get("reached_fwd_m")
        and float((probe["reached_fwd_m"] or {}).get("min") or 1e9)
        < float(thr.near_collision_depth_m)
    ):
        reason = "starts not collision-bearing (probe forward-near/collided required)"
        s1 = {"ok": False, "reason": reason, "scan": scan_diag}
        partial1 = {"partial": True, "signals_requested": ["1"], "ok": False, "signals": {"1": s1}}
        _emit(out_dir / _PARTIAL1, partial1)
        s4 = {"ok": False, "reason": reason, "scan": scan_diag}
        partial4 = {"partial": True, "signals_requested": ["4"], "ok": False, "signals": {"4": s4}}
        _emit(out_dir / _PARTIAL4, partial4)
        return 1

    dyn_cfg = cfg.get("dynamics", {}) or {}
    dyn_kind = str(args.dynamics_kind or dyn_cfg.get("kind", "torch"))
    if dyn_kind == "torch":
        wm_cfg = cfg.get("world_model", {}) or {}
        wm_ckpt = args.wm_ckpt
        if not wm_ckpt:
            wm_dir = wm_cfg.get("checkpoint_dir")
            if wm_dir:
                cand = root / wm_dir / "wm_step_5000.pt"
                if cand.is_file():
                    wm_ckpt = str(cand)
        if not wm_ckpt:
            print("[v4-run] --wm-ckpt required when dynamics-kind=torch", file=sys.stderr)
            return 2
        wm_ckpt_path = Path(wm_ckpt).expanduser()
        if not wm_ckpt_path.is_absolute():
            wm_ckpt_path = root / wm_ckpt_path
        if not wm_ckpt_path.is_file():
            print(f"[v4-run] missing WM ckpt {wm_ckpt_path}", file=sys.stderr)
            return 2
        dynamics, wm_payload = load_torch_dynamics(
            wm_cfg,
            wm_ckpt_path,
            device=str(args.device),
            success_dist_m=float(reward_cfg.success_dist_m if reward_cfg else 3.0),
        )
        print(
            f"[v4-run] torch WM encode path latent_dim={dynamics.latent_dim} "
            f"ckpt={wm_ckpt_path} step={wm_payload.get('step')}"
        )
    else:
        dynamics = StubLatentDynamics(
            goal=None,
            latent_dim=int(dyn_cfg.get("latent_dim", 8)),
            collide_radius_m=float(dyn_cfg.get("collide_radius_m", 2.0)),
            success_dist_m=float(reward_cfg.success_dist_m if reward_cfg else 3.0),
        )
    actor_ac = LatentActorCritic.load_from_checkpoint(actor_ckpt, device=str(args.device))
    if int(actor_ac.config.latent_dim) != int(dynamics.latent_dim):
        print(
            f"[v4-run] actor latent_dim={actor_ac.config.latent_dim} != "
            f"WM latent_dim={dynamics.latent_dim}",
            file=sys.stderr,
        )
        return 2
    actor_policy = LatentActorDeployPolicy(
        dynamics, actor_ac, deterministic=not bool(args.actor_stochastic),
    )

    # --- V4-① progress vs Heuristic (P0c spare refill + drop counters) ---
    prog, prog_pool = epool.run_progress_eval_p0c(
        env,
        actor_policy,
        heuristic,
        primary,
        spare,
        spare_manifest,
        target_n=target_n,
        max_steps=int(args.max_steps),
        reward_cfg=reward_cfg,
    )
    s1 = v4_metrics.check_progress_vs_heuristic(
        prog["policy_progress_sums"],
        prog["random_progress_sums"],
        delta_p=float(args.delta_p),
    )
    s1["actor_progress_sums"] = prog["policy_progress_sums"]
    s1["heuristic_progress_sums"] = prog["random_progress_sums"]
    s1["actor_final_dists"] = prog["policy_final_dists"]
    s1["heuristic_final_dists"] = prog["random_final_dists"]
    s1["scan"] = scan_diag
    s1["actor_ckpt"] = str(actor_ckpt)
    s1["n_starts_scored"] = prog_pool.n_scored
    s1["target_n"] = target_n
    s1["authoritative"] = bool(prog_pool.authoritative)
    s1["p0c"] = prog_pool.drop_summary()
    s1["p0c"]["spare_manifest"] = str(manifest_path)
    if not prog_pool.authoritative:
        s1["ok"] = False
        s1.setdefault("reason", f"n_scored={prog_pool.n_scored} < target_n={target_n}")

    partial1 = {
        "partial": True,
        "signals_requested": ["1"],
        "ok": bool(s1.get("ok")),
        "signals": {"1": s1},
    }
    _emit(out_dir / _PARTIAL1, partial1)
    print(
        f"[v4-run] signal1 ok={s1.get('ok')} actor_mean={s1.get('mean_progress_actor'):.4f} "
        f"heur_mean={s1.get('mean_progress_heuristic'):.4f} target={s1.get('target_min'):.4f}"
    )

    # --- V4-④ safety (shield-on hard coll + optional V0-④ near ratio) ---
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

    def _run_arm_p0c(
        policy: Any,
        *,
        shield_on: bool,
        label: str,
    ) -> Dict[str, Any]:
        kwargs = dict(
            env=env,
            policy=policy,
            depth_predictor_on=predictor,
            primary=primary,
            spare=spare,
            manifest=spare_manifest,
            target_n=target_n,
            near_collision_depth_m=float(thr.near_collision_depth_m),
            shield_trigger_depth_m=shield_trigger_m,
            max_steps=int(args.max_steps),
            reward_cfg=reward_cfg,
        )
        if shield_on:
            masks, pool = epool.run_shield_eval_p0c(
                **kwargs, tau_predictor=tau_pred, both_arms_unshielded=False,
                dynamics=dynamics,
            )
        else:
            masks, pool = epool.run_shield_eval_p0c(
                **kwargs, tau_predictor=None, both_arms_unshielded=True,
            )
        collided_on = masks["collided_on"]
        near_on = masks["near_coll_on"]
        near_off = masks["near_coll_off"]
        hard_rate = _episode_collision_rate(collided_on)
        near_on_rate = _frame_near_coll_rate(near_on)
        near_off_rate = _frame_near_coll_rate(near_off)
        ratio = (
            float(near_on_rate / near_off_rate)
            if np.isfinite(near_on_rate) and np.isfinite(near_off_rate) and near_off_rate > 0
            else float("nan")
        )
        p0c_summary = pool.drop_summary()
        p0c_summary["spare_manifest"] = str(manifest_path)
        return {
            "label": label,
            "collision_rate": hard_rate,
            "near_coll_rate_on": near_on_rate,
            "near_coll_rate_off": near_off_rate,
            "near_coll_rate_ratio": ratio,
            "n_episodes": pool.n_scored,
            "target_n": target_n,
            "authoritative": bool(pool.authoritative),
            "p0c": p0c_summary,
            "shield_trigger_m": shield_trigger_m if shield_on else None,
            "depth_steps": masks.get("depth_steps", 0),
        }

    v4_on = _run_arm_p0c(actor_policy, shield_on=True, label="v4_actor_shield_on")
    v4_off = _run_arm_p0c(actor_policy, shield_on=False, label="v4_actor_shield_off")
    v1_on = _run_arm_p0c(heuristic, shield_on=True, label="v1_heuristic_shield_on")

    v4_coll = float(v4_on["collision_rate"])
    if args.v1_coll_rate is not None:
        v1_coll = float(args.v1_coll_rate)
        v1_source = "cli_baseline"
    else:
        v1_coll = float(v1_on["collision_rate"])
        v1_source = "remeasured_same_starts"

    near_ratio = v4_on.get("near_coll_rate_ratio")
    if not np.isfinite(near_ratio):
        near_ratio = None

    s4 = v4_metrics.check_safety_no_regression(
        v4_coll,
        v1_coll,
        near_coll_rate_ratio=near_ratio,
    )
    s4["v4_measured"] = v4_on
    s4["v4_shield_off"] = v4_off
    s4["v1_measured"] = v1_on
    s4["v1_coll_source"] = v1_source
    s4["v1_partial_baseline"] = 0.50
    s4["tau_kind"] = tau_kind
    s4["tau_ckpt"] = str(tau_ckpt) if tau_ckpt else None
    s4["scan"] = scan_diag
    s4["actor_ckpt"] = str(actor_ckpt)
    s4["depth_ckpt"] = str(depth_ckpt)
    s4["target_n"] = target_n
    s4["authoritative"] = bool(
        v4_on.get("authoritative")
        and v4_off.get("authoritative")
        and v1_on.get("authoritative")
    )
    s4["p0c"] = v4_on.get("p0c")
    if not s4["authoritative"]:
        s4["ok"] = False
        s4.setdefault(
            "reason",
            f"n_scored={v4_on.get('n_episodes')} < target_n={target_n}",
        )

    partial4 = {
        "partial": True,
        "signals_requested": ["4"],
        "ok": bool(s4.get("ok")),
        "signals": {"4": s4},
    }
    _emit(out_dir / _PARTIAL4, partial4)
    print(
        f"[v4-run] signal4 ok={s4.get('ok')} v4_hard={v4_coll:.4f} v1_hard={v1_coll:.4f} "
        f"near_ratio={near_ratio} source={v1_source}"
    )

    ok = bool(s1.get("ok")) and bool(s4.get("ok"))
    return 0 if ok else 1


def run_merge(args: argparse.Namespace) -> int:
    root = _repo_root(args.repo)
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from experiments.aerial.rl._v4_gate import _merge_partials, assemble_verdict

    out_dir = Path(args.out_dir).expanduser()
    if not out_dir.is_absolute():
        out_dir = root / out_dir
    paths = [out_dir / _PARTIAL1, out_dir / _PARTIAL4]
    for p in paths:
        if not p.exists():
            print(f"[v4-run] missing {p}", file=sys.stderr)
            return 2
    signals = _merge_partials(paths)
    verdict = assemble_verdict(signals["1"], signals["4"])
    verdict["merged_from"] = [str(p) for p in paths]
    out = out_dir / _MERGE_OUT
    _emit(out, verdict)
    return 0 if verdict.get("ok") else 1


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=("rollout4090", "merge"))
    p.add_argument("--repo", default=None)
    p.add_argument(
        "--out-dir",
        default="experiments/aerial/rl/artifacts/v4_gate_r60_20260816",
    )
    p.add_argument("--config", default="configs/aerial_rl_rollout.yaml")
    p.add_argument("--env-host", default=None, help="override env.host (e.g. 127.0.0.1)")
    p.add_argument("--device", default="cuda")
    p.add_argument(
        "--rollout-dataset",
        default="~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/dataset_v0_local_depth_r60_20260814",
    )
    p.add_argument(
        "--actor-ckpt",
        default="experiments/aerial/rl/artifacts/v4_ac_ckpt_20260816/v4_ac_latest.pt",
    )
    p.add_argument(
        "--depth-ckpt",
        default="experiments/aerial/rl/artifacts/depth_ckpt_da3_r60_20260814/depth_step_2000_da3_ft_head.pt",
    )
    p.add_argument("--tau-kind", default="foe_calibrated")
    p.add_argument(
        "--tau-ckpt",
        default="experiments/aerial/rl/artifacts/tau_ckpt_foe_r60_20260815/tau_foe_calibrator.pt",
    )
    p.add_argument(
        "--target-n",
        type=int,
        default=16,
        help="frozen n per layer (§4.6.1; do not lower)",
    )
    p.add_argument(
        "--spare-count",
        type=int,
        default=None,
        help="pre-scanned spare pool size (§3 item 11; required for rollout4090)",
    )
    p.add_argument(
        "--n-episodes",
        type=int,
        default=None,
        help="deprecated: use --target-n + --spare-count",
    )
    p.add_argument("--max-steps", type=int, default=200)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--shield-trigger-m", type=float, default=1.5)
    p.add_argument("--delta-p", type=float, default=0.10)
    p.add_argument(
        "--v1-coll-rate",
        type=float,
        default=None,
        help="V1-① authoritative baseline; default remeasure heuristic V1 arm",
    )
    p.add_argument(
        "--actor-stochastic",
        action="store_true",
        help="sample actor actions (default deterministic)",
    )
    p.add_argument(
        "--dynamics-kind",
        default="torch",
        choices=("stub", "torch"),
        help="latent encode path for actor deploy (default torch WM)",
    )
    p.add_argument(
        "--wm-ckpt",
        default=None,
        help="WM checkpoint for dynamics-kind=torch",
    )
    args = p.parse_args()
    if args.mode == "rollout4090":
        return run_rollout4090(args)
    return run_merge(args)


if __name__ == "__main__":
    raise SystemExit(main())
