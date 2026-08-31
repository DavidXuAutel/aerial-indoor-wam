#!/usr/bin/env python3
"""P4.5 — balanced corpus collection (S_open:S_blocked ≈ 1:1, near-band enrichment).

Scans live renderer for layer-tagged start/goal episodes, applies approach-bias
(shorter goals → more near-band frames for ⓪b), then runs serial collect_dataset.

Usage (4090):
  source experiments/aerial/scripts/env_4090.sh
  $PYTHON_BIN experiments/aerial/scripts/v4_p45_collect.py \\
    --host 127.0.0.1 --per-layer 24 \\
    --out experiments/aerial/rl/artifacts/dataset_v0_p45_balanced_20260820
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


def _repo_root(explicit: Optional[str]) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    return Path(__file__).resolve().parents[3]


def _goal_dist(pos: np.ndarray, goal: np.ndarray) -> float:
    return float(
        np.linalg.norm(
            np.asarray(goal, dtype=np.float64).reshape(3)
            - np.asarray(pos, dtype=np.float64).reshape(3)
        )
    )


def _probe_open(
    env: Any,
    probe_policy: Any,
    epi: Dict[str, Any],
    *,
    max_steps: int,
    arrival_m: float,
    reward_cfg: Any,
) -> bool:
    from experiments.aerial.rl import v0_rollout_eval as rollout

    if hasattr(probe_policy, "reset"):
        probe_policy.reset()
    ep = rollout._run_one_resilient(
        env, probe_policy, epi, max_steps=int(max_steps), reward_cfg=reward_cfg, shield=None
    )
    if ep is None or not ep:
        return False
    goal = np.asarray(getattr(env, "goal"), dtype=np.float64).reshape(3)
    final = np.asarray(ep[-1].next_obs.position, dtype=np.float64)
    return _goal_dist(final, goal) <= float(arrival_m)


def _scan_open_episodes(
    env: Any,
    cand: np.ndarray,
    cand_yaw: Optional[np.ndarray],
    *,
    n: int,
    seed: int,
    goal_dist_m: float,
    probe_policy: Any,
    reward_cfg: Any,
    probe_steps: int,
    arrival_m: float,
    obstacle_max_m: float,
    start_clearance_m: float,
    center_frac: float,
    max_scans: int,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    from experiments.aerial.rl import v0_rollout_eval as rollout

    rng = np.random.default_rng(int(seed))
    idx = rng.permutation(len(cand))
    episodes: List[Dict[str, Any]] = []
    rej: Dict[str, int] = {
        "spawn_collision": 0,
        "too_close": 0,
        "not_open_ahead": 0,
        "probe_blocked": 0,
        "reset_error": 0,
    }
    n_scanned = 0
    for ci in idx.tolist():
        if len(episodes) >= int(n) or n_scanned >= int(max_scans):
            break
        n_scanned += 1
        pos = np.asarray(cand[ci], dtype=np.float64).reshape(3)
        yaw = float(cand_yaw[ci]) if cand_yaw is not None else 0.0
        goal = pos + np.array(
            [goal_dist_m * math.cos(yaw), goal_dist_m * math.sin(yaw), 0.0],
            dtype=np.float64,
        )
        epi = {"pos": np.stack([pos, goal]), "yaw": np.array([yaw, yaw], dtype=np.float64)}
        try:
            obs = env.reset(epi)
        except Exception:  # noqa: BLE001
            rej["reset_error"] += 1
            continue
        if getattr(obs, "collided", False):
            rej["spawn_collision"] += 1
            continue
        depth = getattr(obs, "depth", None)
        if depth is None:
            rej["reset_error"] += 1
            continue
        fwd = rollout._forward_min_depth(depth, center_frac=center_frac)
        if fwd < float(start_clearance_m):
            rej["too_close"] += 1
            continue
        if fwd <= float(obstacle_max_m):
            rej["not_open_ahead"] += 1
            continue
        if not _probe_open(
            env,
            probe_policy,
            epi,
            max_steps=int(probe_steps),
            arrival_m=arrival_m,
            reward_cfg=reward_cfg,
        ):
            rej["probe_blocked"] += 1
            continue
        epi["layer"] = "open"
        episodes.append(epi)
    return episodes, {"requested": int(n), "accepted": len(episodes), "scanned": n_scanned, "rejections": rej}


def build_episode_pool(args: argparse.Namespace) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    root = _repo_root(args.repo)
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    import yaml

    from experiments.aerial.rl import v0_rollout_eval as rollout
    from experiments.aerial.rl._v0_gate import _obstacle_candidate_positions
    from experiments.aerial.rl.reward import RewardConfig
    from experiments.aerial.rl.train_rl import HeuristicPolicy, _build_env

    cfg = yaml.safe_load((root / args.config).read_text()) or {}
    if args.host:
        cfg.setdefault("env", {})
        cfg["env"]["host"] = str(args.host)
        cfg["env"]["port"] = int(args.port)
        cfg["env"]["backend"] = "airsim"
        cfg["env"]["grab_depth"] = True
        cfg["env"].setdefault("camera", str(args.camera))
        cfg["env"].setdefault("vehicle", str(args.vehicle))
        cfg["env"].setdefault("step_hz", float(args.step_hz))
    env = _build_env(cfg.get("env", {}) or {})
    reward_cfg = RewardConfig(**(cfg.get("reward", {}) or {})) if cfg.get("reward") else RewardConfig()
    arrival_m = float(reward_cfg.success_dist_m)
    heuristic = HeuristicPolicy(goal_getter=lambda: getattr(env, "goal", None))

    rollout_ds = Path(args.rollout_dataset).expanduser()
    if not rollout_ds.is_absolute():
        rollout_ds = root / rollout_ds
    cand, cand_yaw = _obstacle_candidate_positions(rollout_ds, min_altitude_m=0.0)

    only = str(getattr(args, "only_layer", "both") or "both").strip().lower()
    if only not in {"both", "open", "blocked"}:
        raise ValueError(f"--only-layer must be both|open|blocked, got {only!r}")

    blocked: List[Dict[str, Any]] = []
    blocked_diag: Dict[str, Any] = {"skipped": True}
    open_: List[Dict[str, Any]] = []
    open_diag: Dict[str, Any] = {"skipped": True}

    if only in {"both", "blocked"}:
        blocked, blocked_diag = rollout.make_obstacle_facing_episodes(
            env,
            int(args.per_layer),
            cand,
            seed=int(args.blocked_seed),
            candidate_yaws=cand_yaw,
            goal_dist_m=float(args.goal_dist_m),
            obstacle_max_m=float(args.obstacle_max_m),
            center_frac=float(args.center_frac),
            max_scans=int(args.blocked_scan_max),
            probe_policy=heuristic,
            probe_steps=int(args.probe_steps),
            probe_near_m=float(args.probe_near_m),
            reward_cfg=reward_cfg,
            preserve_order=True,
            log_every=50,
        )
        for e in blocked:
            e["layer"] = "blocked"

    if only in {"both", "open"}:
        open_, open_diag = _scan_open_episodes(
            env,
            cand,
            cand_yaw,
            n=int(args.per_layer),
            seed=int(args.open_seed),
            goal_dist_m=float(args.goal_dist_m),
            probe_policy=heuristic,
            reward_cfg=reward_cfg,
            probe_steps=int(args.probe_steps),
            arrival_m=arrival_m,
            obstacle_max_m=float(args.obstacle_max_m),
            start_clearance_m=float(args.start_clearance_m),
            center_frac=float(args.center_frac),
            max_scans=int(args.open_scan_max),
        )

    close = getattr(env, "close", None)
    if callable(close):
        close()

    pool = blocked + open_
    diag = {
        "per_layer": int(args.per_layer),
        "only_layer": only,
        "blocked": blocked_diag,
        "open": open_diag,
        "total": len(pool),
        "goal_dist_m": float(args.goal_dist_m),
        "approach_dist_m": float(args.approach_dist_m),
    }
    return pool, diag


def collect_pool(args: argparse.Namespace, pool: List[Dict[str, Any]], scan_diag: Dict[str, Any]) -> int:
    root = _repo_root(args.repo)
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from experiments.aerial.rl import dataset as ds
    from experiments.aerial.rl.collect_dataset import approach_bias_episodes
    from experiments.aerial.rl.train_rl import build_from_config

    out_dir = Path(args.out).expanduser()
    if not out_dir.is_absolute():
        out_dir = root / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    episodes = approach_bias_episodes(pool, dist_m=float(args.approach_dist_m))
    for ep in episodes:
        ep.setdefault("p45_meta", {})
        ep["p45_meta"]["approach_dist_m"] = float(args.approach_dist_m)
        ep["p45_meta"]["layer"] = ep.get("layer", "unknown")

    from experiments.aerial.rl.collect_dataset import _deep_update

    cfg: dict = {
        "env": {
            "backend": "airsim",
            "host": args.host,
            "port": int(args.port),
            "camera": args.camera,
            "vehicle": args.vehicle,
            "grab_depth": True,
            "step_hz": float(args.step_hz),
        },
        "dynamics": {"kind": "stub", "latent_dim": 8},
        "corrector": {
            "iterations": len(episodes),
            "episodes_per_iter": 1,
            "max_steps": int(args.max_steps),
        },
    }
    cfg_path = Path(args.config).expanduser()
    if not cfg_path.is_absolute():
        cfg_path = root / cfg_path
    if cfg_path.is_file():
        import yaml

        yaml_cfg = yaml.safe_load(cfg_path.read_text()) or {}
        cfg = _deep_update(yaml_cfg, cfg)

    manifest: list[dict] = []
    reports: list[dict] = []
    failures: list[str] = []
    quarantined: list[str] = []

    def _sink(transitions, stats) -> None:
        idx = len(manifest)
        path = ds.write_episode(out_dir, idx, transitions)
        rep = ds.quality_report(transitions)
        rep["achieved_hz"] = round(stats.achieved_hz, 2)
        bad = ds.assert_nontrivial(rep)
        quar = ds.quarantine_reasons(rep)
        status = "BAD" if bad else ("QUARANTINE" if quar else "OK")
        layer = episodes[idx].get("layer", "unknown") if idx < len(episodes) else "unknown"
        logger.info(
            "ep %d layer=%s: %d steps @ %.1f Hz | path %.2f m | %s | %s",
            idx,
            layer,
            rep["steps"],
            stats.achieved_hz,
            rep["path_length_m"],
            status,
            path.name,
        )
        for f in bad:
            failures.append(f"ep{idx}: {f}")
        for q in quar:
            quarantined.append(f"ep{idx}: {q}")
        manifest.append(
            {
                "file": path.name,
                "steps": rep["steps"],
                "return": rep["reward_sum"],
                "achieved_hz": rep["achieved_hz"],
                "layer": layer,
                "nontrivial": not bad,
                "quarantined": bool(quar),
                "usable": not bad and not quar,
            }
        )
        reports.append(rep)

    loop = build_from_config(cfg)
    loop.collector.on_episode = _sink
    loop.episodes = episodes
    try:
        stats = loop.collector.collect(len(episodes), episodes=episodes)
    finally:
        close = getattr(loop.collector.env, "close", None)
        if callable(close):
            close()

    n = len(manifest)
    quar_frac = (len(quarantined) / n) if n else 0.0
    layer_counts = {"open": 0, "blocked": 0, "unknown": 0}
    for m in manifest:
        layer_counts[str(m.get("layer", "unknown"))] = layer_counts.get(str(m.get("layer", "unknown")), 0) + 1

    ds.write_manifest(
        out_dir,
        manifest,
        meta={
            "backend": "airsim",
            "step_hz": float(args.step_hz),
            "max_steps": int(args.max_steps),
            "grab_depth": True,
            "approach_bias": True,
            "approach_dist_m": float(args.approach_dist_m),
            "p45_scan": scan_diag,
            "layer_counts": layer_counts,
            "skipped_reset_collision": stats.skipped,
            "quarantined": len(quarantined),
            "quarantine_fraction": round(quar_frac, 3),
        },
    )
    summary_path = ds.write_quality_summary(out_dir, reports)
    scan_path = out_dir / "p45_scan_diag.json"
    scan_path.write_text(json.dumps(scan_diag, indent=2, default=str) + "\n")
    logger.info("wrote %d episodes + %s (skipped %d spawn-collision)", n, summary_path.name, stats.skipped)

    if failures:
        for f in failures:
            print(f"[p45-collect] FAIL: {f}", file=sys.stderr)
        return 1
    if quarantined and quar_frac > ds.MAX_QUARANTINE_FRACTION:
        print(f"[p45-collect] too many quarantined ({quar_frac:.0%})", file=sys.stderr)
        return 1
    if n == 0:
        print("[p45-collect] FAIL: 0 episodes", file=sys.stderr)
        return 1
    usable = n - len(quarantined)
    if usable == 0:
        print("[p45-collect] FAIL: 0 usable episodes", file=sys.stderr)
        return 1
    print(f"[p45-collect] OK: {usable}/{n} usable in {out_dir} layers={layer_counts}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--repo", default=None)
    p.add_argument("--config", default="configs/aerial_rl_rollout.yaml")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=41451)
    p.add_argument("--camera", default="front_custom")
    p.add_argument("--vehicle", default="drone_1")
    p.add_argument("--step-hz", type=float, default=5.0)
    p.add_argument("--max-steps", type=int, default=200)
    p.add_argument("--per-layer", type=int, default=24, help="episodes per requested layer")
    p.add_argument(
        "--only-layer",
        choices=("both", "open", "blocked"),
        default="both",
        help="top-up one layer without rewriting the other (default: both)",
    )
    p.add_argument("--goal-dist-m", type=float, default=30.0)
    p.add_argument("--approach-dist-m", type=float, default=20.0, help="shorter goals for near-band")
    p.add_argument("--obstacle-max-m", type=float, default=25.0)
    p.add_argument("--start-clearance-m", type=float, default=3.0)
    p.add_argument("--center-frac", type=float, default=0.3)
    p.add_argument("--probe-steps", type=int, default=40)
    p.add_argument("--probe-near-m", type=float, default=1.5)
    p.add_argument("--blocked-seed", type=int, default=100)
    p.add_argument("--open-seed", type=int, default=200)
    p.add_argument("--blocked-scan-max", type=int, default=800)
    p.add_argument("--open-scan-max", type=int, default=400)
    p.add_argument(
        "--rollout-dataset",
        default="~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/dataset_v0_local_depth_r60_20260814",
    )
    p.add_argument(
        "--out",
        default="experiments/aerial/rl/artifacts/dataset_v0_p45_balanced_20260820",
    )
    p.add_argument("--scan-only", action="store_true", help="build episode pool JSON only")
    p.add_argument("--pool-json", default=None, help="reuse pre-scanned episode pool")
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="[p45-collect] %(message)s")

    if args.pool_json:
        pool_path = Path(args.pool_json).expanduser()
        if not pool_path.is_absolute():
            pool_path = _repo_root(args.repo) / pool_path
        payload = json.loads(pool_path.read_text())
        pool = payload["episodes"]
        scan_diag = payload.get("scan_diag", {})
    else:
        pool, scan_diag = build_episode_pool(args)
        if args.scan_only:
            out = Path(args.out).expanduser()
            if not out.is_absolute():
                out = _repo_root(args.repo) / out
            out.parent.mkdir(parents=True, exist_ok=True)
            pool_path = out.parent / "p45_episode_pool.json"
            pool_path.write_text(
                json.dumps({"episodes": pool, "scan_diag": scan_diag}, indent=2, default=str) + "\n"
            )
            print(f"[p45-collect] scan-only wrote {pool_path} n={len(pool)}")
            return 0

    only = str(args.only_layer).strip().lower()
    target = int(args.per_layer) if only != "both" else 2 * int(args.per_layer)
    if len(pool) < target:
        print(
            f"[p45-collect] WARN: pool size {len(pool)} < target {target} (only_layer={only})",
            file=sys.stderr,
        )
    return collect_pool(args, pool, scan_diag)


if __name__ == "__main__":
    raise SystemExit(main())
