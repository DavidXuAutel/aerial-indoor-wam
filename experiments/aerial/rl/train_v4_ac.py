#!/usr/bin/env python3
"""V4 pure-imagination AC short train entrypoint (H100 or local CPU smoke).

Does **not** modify ``configs/aerial_rl.yaml`` — pass overrides on CLI or edit
the in-memory cfg dict only.

    python -m experiments.aerial.rl.train_v4_ac --iters 5 --device cuda

On H100 after bundle/pull, run with ``dynamics.kind=torch`` and a loaded WM ckpt.
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict

import numpy as np
import yaml

from experiments.aerial.rl.collect_dataset import (
    _mock_goal_episode,
    approach_bias_episodes,
    approach_bias_transition_episodes,
)
from experiments.aerial.rl.goal_features import attach_goal, resolve_episode_goal, stamp_train_pose_source
from experiments.aerial.rl.train_rl import build_from_config, load_torch_dynamics

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _load_cfg(repo: Path) -> Dict[str, Any]:
    cfg_path = repo / "configs" / "aerial_rl.yaml"
    return yaml.safe_load(cfg_path.read_text())


def main() -> int:
    p = argparse.ArgumentParser(description="V4 imagination AC short train")
    p.add_argument("--iters", type=int, default=5)
    p.add_argument("--episodes-per-iter", type=int, default=2)
    p.add_argument("--imagine-batch", type=int, default=16)
    p.add_argument("--imagine-horizon", type=int, default=15)
    p.add_argument("--device", default="cpu", help="cpu | cuda")
    p.add_argument("--ckpt-dir", default=None, help="write actor ckpt dir")
    p.add_argument("--backend", default="mock", choices=("mock", "airsim"))
    p.add_argument(
        "--dynamics",
        default=None,
        choices=("stub", "torch"),
        help="dynamics.kind override (default: stub for mock backend, else yaml)",
    )
    p.add_argument(
        "--wm-ckpt",
        default=None,
        help="WM checkpoint path when --dynamics torch (required for serious train)",
    )
    p.add_argument(
        "--annotation",
        default=None,
        help="OpenFly annotation JSON for start→goal episodes (real or mock collect)",
    )
    p.add_argument(
        "--approach-bias",
        action="store_true",
        help="rewrite goals to start+dist along start yaw (matches collect_dataset)",
    )
    p.add_argument(
        "--no-approach-bias",
        action="store_true",
        help="keep dataset/annotation goals as collected (E2 closed-loop)",
    )
    p.add_argument(
        "--approach-dist-m",
        type=float,
        default=25.0,
        help="goal distance along start heading when --approach-bias",
    )
    p.add_argument(
        "--dataset",
        default=None,
        help="preload real RGB replay episodes for z0 encode (offline RGB align)",
    )
    p.add_argument(
        "--skip-collect",
        action="store_true",
        help="skip env collect each iter (use with --dataset for offline z0 AC)",
    )
    p.add_argument(
        "--success-dist-m",
        type=float,
        default=None,
        help="override reward.success_dist_m (indoor default 0.20 when --indoor)",
    )
    p.add_argument(
        "--action-limits",
        default=None,
        help="comma-separated max_dx,max_dy,max_dz,max_dyaw per step (indoor: 0.15,0.08,0.08,0.10)",
    )
    p.add_argument(
        "--indoor",
        action="store_true",
        help="indoor FT preset: success_dist=0.20, micro action box, approach 12m",
    )
    p.add_argument(
        "--actor-ckpt",
        default=None,
        help="warm-start actor/critic from v4_ac_latest.pt (e.g. step_e outdoor ckpt)",
    )
    p.add_argument(
        "--train-pose-source",
        default="gt_proxy",
        choices=("gt_proxy", "odom_from_imu_rgb", "vio_est"),
        help="pose stub stamped on offline dataset for imagination goal_rel (declared in FT protocol)",
    )
    p.add_argument(
        "--max-episodes",
        type=int,
        default=None,
        help="cap annotation episodes (default: all routes when --indoor)",
    )
    args = p.parse_args()

    if args.indoor:
        if args.success_dist_m is None:
            args.success_dist_m = 0.20
        if args.action_limits is None:
            args.action_limits = "0.15,0.08,0.08,0.10"
        if args.no_approach_bias:
            args.approach_bias = False
        elif not args.approach_bias:
            args.approach_bias = True
        if args.approach_dist_m == 25.0:
            args.approach_dist_m = 12.0

    repo = Path(__file__).resolve().parents[3]
    cfg = _load_cfg(repo)
    cfg.setdefault("corrector", {})
    cfg.setdefault("env", {})
    cfg.setdefault("imagination", {})
    cfg.setdefault("v4", {})
    cfg.setdefault("dynamics", {})
    cfg.setdefault("tau_predictor", {})
    cfg["corrector"]["iterations"] = int(args.iters)
    cfg["corrector"]["episodes_per_iter"] = int(args.episodes_per_iter)
    cfg["corrector"]["enable_policy_update"] = True
    cfg["corrector"]["enable_wm_update"] = False
    cfg["imagination"]["horizon"] = int(args.imagine_horizon)
    cfg["imagination"]["batch"] = int(args.imagine_batch)
    cfg["env"]["backend"] = str(args.backend)
    if args.success_dist_m is not None:
        cfg.setdefault("reward", {})["success_dist_m"] = float(args.success_dist_m)
    if args.annotation:
        cfg["annotation"] = str(args.annotation)
    if args.max_episodes is not None:
        cfg["max_episodes"] = int(args.max_episodes)
    elif args.indoor and args.annotation:
        cfg["max_episodes"] = 20
    if args.skip_collect:
        cfg["corrector"]["episodes_per_iter"] = 0
    if args.dynamics is not None:
        dyn_kind = str(args.dynamics)
    elif args.backend == "mock":
        dyn_kind = "stub"
    else:
        dyn_kind = str(cfg["dynamics"].get("kind", "stub"))
    cfg["dynamics"]["kind"] = dyn_kind
    cfg["tau_predictor"]["enable"] = False if args.backend == "mock" else cfg["tau_predictor"].get("enable", False)
    cfg["v4"]["device"] = str(args.device)

    wm_ckpt_path = None
    if dyn_kind == "torch":
        wm_ckpt_path = args.wm_ckpt
        if not wm_ckpt_path:
            wm_dir = cfg.get("world_model", {}).get("checkpoint_dir")
            if wm_dir:
                cand = repo / wm_dir / "wm_step_5000.pt"
                if cand.is_file():
                    wm_ckpt_path = str(cand)
        if not wm_ckpt_path:
            logger.error("--wm-ckpt required when --dynamics torch")
            return 1
        cfg.setdefault("world_model", {})["device"] = str(args.device)

    loop = build_from_config(cfg)

    action_limits_tuple = None
    if args.action_limits:
        parts = [float(x.strip()) for x in str(args.action_limits).split(",")]
        if len(parts) != 4 or min(parts) <= 0:
            logger.error("--action-limits must be 4 positive floats, got %r", args.action_limits)
            return 1
        action_limits_tuple = tuple(parts)

    if args.actor_ckpt:
        from experiments.aerial.rl.actor_critic import LatentActorCritic

        ac_path = Path(args.actor_ckpt)
        if not ac_path.is_file():
            ac_path = repo / args.actor_ckpt
        if not ac_path.is_file():
            logger.error("--actor-ckpt not found: %s", args.actor_ckpt)
            return 1
        loaded_ac = LatentActorCritic.load_from_checkpoint(ac_path, device=str(args.device))
        if action_limits_tuple is not None:
            loaded_ac.config.action_limits = action_limits_tuple
            import torch

            loaded_ac._limits = torch.as_tensor(
                np.asarray(action_limits_tuple, dtype=np.float32), device=loaded_ac._device,
            )
        loop.actor_critic = loaded_ac
        logger.info("warm-started actor from %s", ac_path)

    elif action_limits_tuple is not None and loop.actor_critic is not None:
        loop.actor_critic.config.action_limits = action_limits_tuple
        import torch

        loop.actor_critic._limits = torch.as_tensor(
            np.asarray(action_limits_tuple, dtype=np.float32),
            device=loop.actor_critic._device,
        )

    # Mock dry-run with no annotation: inject a goal so imagined progress / RH
    # aux are non-trivial (collect_dataset does the same for mock collect).
    if args.backend == "mock" and loop.episodes is None:
        loop.episodes = [_mock_goal_episode()]
        logger.info("mock backend: injected synthetic start→goal episode")
    if args.approach_bias and loop.episodes is not None:
        loop.episodes = approach_bias_episodes(
            loop.episodes, dist_m=float(args.approach_dist_m),
        )
        logger.info(
            "approach-bias ON: goals -> start + %.1f m along start yaw (%d eps)",
            float(args.approach_dist_m), len(loop.episodes),
        )
    if args.dataset:
        from experiments.aerial.rl import dataset as ds
        from experiments.aerial.rl.goal_features import attach_goal, resolve_episode_goal

        ds_path = Path(args.dataset)
        if not ds_path.is_dir():
            logger.error("--dataset %s is not a directory", ds_path)
            return 1
        loaded = ds.load_dataset(ds_path, skip_quarantined=True)
        if args.approach_bias:
            loaded = approach_bias_transition_episodes(
                loaded, dist_m=float(args.approach_dist_m),
            )
            logger.info(
                "approach-bias ON (dataset): goals -> start + %.1f m (%d eps)",
                float(args.approach_dist_m), len(loaded),
            )
        stamped = 0
        for ep in loaded:
            stamp_train_pose_source(ep, pose_source=str(args.train_pose_source))
            goal = resolve_episode_goal(ep, allow_end_proxy=True)
            if goal is not None:
                attach_goal(ep, goal)
                stamped += 1
            loop.buffer.add_episode(ep)
        logger.info(
            "preloaded %d episodes (%d with goals) from %s for real-RGB z0",
            len(loaded), stamped, ds_path,
        )
    if dyn_kind == "torch" and wm_ckpt_path:
        wm_cfg = cfg.get("world_model", {})
        success_dist_m = float(cfg.get("reward", {}).get("success_dist_m", 3.0))
        dynamics, wm_payload = load_torch_dynamics(
            wm_cfg,
            wm_ckpt_path,
            device=str(args.device),
            success_dist_m=success_dist_m,
        )
        loop.dynamics = dynamics
        if loop.actor_critic is not None:
            ac_dim = int(loop.actor_critic.config.latent_dim)
            if ac_dim != int(dynamics.latent_dim):
                logger.error(
                    "actor latent_dim=%d != WM latent_dim=%d — rebuild with matching config",
                    ac_dim,
                    int(dynamics.latent_dim),
                )
                return 1
        logger.info(
            "loaded WM ckpt %s step=%s latent_dim=%d",
            wm_ckpt_path,
            wm_payload.get("step"),
            int(dynamics.latent_dim),
        )
    if loop.actor_critic is None:
        logger.error("actor_critic not built — install torch")
        return 1
    ac_cfg = loop.actor_critic.config
    if not loop.actor_critic.bounded:
        # Red line (C2, 2026-08-18): the pre-C2 unbounded policy class is
        # invalidated; it may be replayed for audit but never trained.
        logger.error(
            "refusing to train policy_class=%s — retrain from scratch (proposal §4.1)",
            ac_cfg.policy_class,
        )
        return 1
    logger.info(
        "policy: class=%s action_limits=%s (step_hz=%.3f) action_scale=%.3f",
        ac_cfg.policy_class, ac_cfg.action_limits, ac_cfg.step_hz, ac_cfg.action_scale,
    )

    reports = loop.run()
    losses = []
    diag_goal_rel: list[float] = []
    diag_progress: list[float] = []
    diag_return: list[float] = []
    for i, r in enumerate(reports):
        rl = r.rl
        logger.info("iter %d rl=%s", i, rl)
        if rl.get("status") == "updated":
            losses.append(float(rl.get("actor_loss", float("nan"))))
            if "mean_abs_goal_rel" in rl:
                diag_goal_rel.append(float(rl["mean_abs_goal_rel"]))
            if "mean_progress" in rl:
                diag_progress.append(float(rl["mean_progress"]))
            if "mean_return" in rl:
                diag_return.append(float(rl["mean_return"]))

    meta = {
        "iters": len(reports),
        "losses": losses,
        "mean_actor_loss": float(sum(losses) / len(losses)) if losses else None,
        "mean_abs_goal_rel": float(sum(diag_goal_rel) / len(diag_goal_rel)) if diag_goal_rel else None,
        "mean_progress": float(sum(diag_progress) / len(diag_progress)) if diag_progress else None,
        "mean_return": float(sum(diag_return) / len(diag_return)) if diag_return else None,
        "policy_class": str(ac_cfg.policy_class),
        "action_limits": [float(x) for x in ac_cfg.action_limits],
        "action_scale": float(ac_cfg.action_scale),
        "step_hz": float(ac_cfg.step_hz),
        "device": str(args.device),
        "dynamics_kind": dyn_kind,
        "wm_ckpt": wm_ckpt_path,
        "latent_dim": int(getattr(loop.dynamics, "latent_dim", 8)),
        "dataset": args.dataset,
        "skip_collect": bool(args.skip_collect),
        "success_dist_m": float(cfg.get("reward", {}).get("success_dist_m", 3.0)),
        "approach_bias": bool(args.approach_bias),
        "approach_dist_m": float(args.approach_dist_m) if args.approach_bias else None,
        "train_pose_source": str(args.train_pose_source),
        "actor_ckpt_in": str(args.actor_ckpt) if args.actor_ckpt else None,
        "indoor_preset": bool(args.indoor),
        "mock_goal_injected": bool(args.backend == "mock" and args.annotation is None),
    }
    print(json.dumps(meta, indent=2))

    if args.ckpt_dir:
        ckpt_dir = Path(args.ckpt_dir)
        ckpt_dir.mkdir(parents=True, exist_ok=True)
        try:
            import torch

            ac = loop.actor_critic
            torch.save(
                {
                    "actor": ac._actor.state_dict(),
                    "critic": ac._critic.state_dict(),
                    "log_std": ac._log_std.detach().cpu(),
                    "config": ac.config.__dict__,
                },
                ckpt_dir / "v4_ac_latest.pt",
            )
            logger.info("wrote %s", ckpt_dir / "v4_ac_latest.pt")
            (ckpt_dir / "train_meta.json").write_text(json.dumps(meta, indent=2) + "\n")
            logger.info("wrote %s", ckpt_dir / "train_meta.json")
        except Exception as exc:
            logger.warning("ckpt save skipped: %s", exc)

    ok = any(r.rl.get("status") == "updated" for r in reports)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
