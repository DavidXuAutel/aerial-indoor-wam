"""V4-⓿ v2 eval (P4) — imagined vs analytic ranking consistency.

Authority = RUNBOOK §2.2 / criteria §4.6.5.

Offline rank eval (H100 or 4090 GPU):
    python -m experiments.aerial.rl.v4_rho_eval \\
        --dataset ~/aerial-rl-skeleton/.../dataset_v0_local_depth_r60_20260814 \\
        --wm-ckpt experiments/aerial/rl/artifacts/wm_ckpt_r60_rh_20260816/wm_step_1000.pt \\
        --emit artifacts/v4_rho_p4_20260820.json

Teleport z0 reproducibility (125 renderer, ⓿e):
    python -m experiments.aerial.rl.v4_rho_eval --mode z0e \\
        --env-host 127.0.0.1 \\
        --wm-ckpt ... --n-z0e 8 \\
        --emit-z0e artifacts/v4_rho_p4_z0e_20260820.json

Exits 0 when scored sub-items PASS; 1 otherwise. No §6 stop on ⓿ FAIL (R-16).
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from experiments.aerial.rl.env.action import body_delta_limits
from experiments.aerial.rl.goal_features import (
    advance_goal_rel_body,
    analytic_progress,
    body_vel_from_obs,
    goal_rel_from_obs,
)
from experiments.aerial.rl.imagination import MAX_IMAGINATION_HORIZON, imagine
from experiments.aerial.rl.planner import ConstantLatentPolicy
from experiments.aerial.rl.reward import RewardConfig, reward_terms


HORIZON_DEFAULT = MAX_IMAGINATION_HORIZON
N_Z0_MIN = 8
K_CANDIDATES_MIN = 8
RHO_MEDIAN_MIN = 0.50
TOP1_MIN = 0.50
TOP_QUANTILE = 0.25
Z0E_REL_L2_MAX = 0.05  # median relative L2 between re-teleport encodes


@dataclass(frozen=True)
class RhoThresholds:
    horizon: int = HORIZON_DEFAULT
    n_z0_min: int = N_Z0_MIN
    k_min: int = K_CANDIDATES_MIN
    rho_median_min: float = RHO_MEDIAN_MIN
    top1_min: float = TOP1_MIN
    z0e_rel_l2_max: float = Z0E_REL_L2_MAX


def rankdata(x: Sequence[float]) -> np.ndarray:
    """Average ranks for ties (1-based)."""
    arr = np.asarray(x, dtype=np.float64).reshape(-1)
    n = arr.size
    order = np.argsort(arr, kind="mergesort")
    ranks = np.empty(n, dtype=np.float64)
    i = 0
    while i < n:
        j = i
        while j + 1 < n and arr[order[j + 1]] == arr[order[i]]:
            j += 1
        avg = 0.5 * (i + j) + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def spearman_rho(x: Sequence[float], y: Sequence[float]) -> float:
    """Spearman rank correlation (Pearson on ranks). Returns nan if degenerate."""
    rx = rankdata(x)
    ry = rankdata(y)
    if rx.size < 2:
        return float("nan")
    if float(np.std(rx)) < 1e-12 or float(np.std(ry)) < 1e-12:
        return float("nan")
    return float(np.corrcoef(rx, ry)[0, 1])


def default_candidate_actions(limits: np.ndarray) -> List[np.ndarray]:
    """K >= 8 candidates spanning the deployed action box (RUNBOOK §1.2)."""
    lim = np.abs(np.asarray(limits, dtype=np.float64).reshape(4))
    fwd, lat, up, yaw = lim.tolist()
    raw = [
        [fwd, 0.0, 0.0, 0.0],
        [-fwd, 0.0, 0.0, 0.0],
        [0.0, lat, 0.0, 0.0],
        [0.0, -lat, 0.0, 0.0],
        [0.0, 0.0, up, 0.0],
        [0.0, 0.0, -up, 0.0],
        [0.0, 0.0, 0.0, yaw],
        [0.0, 0.0, 0.0, 0.0],
        [fwd, lat, 0.0, 0.0],
        [fwd, -lat, 0.0, 0.0],
        [-fwd, lat, 0.0, 0.0],
        [fwd, 0.0, up, 0.0],
    ]
    out: List[np.ndarray] = []
    seen: set = set()
    for row in raw:
        a = np.clip(np.asarray(row, dtype=np.float64), -lim, lim)
        key = tuple(np.round(a, 6).tolist())
        if key not in seen:
            seen.add(key)
            out.append(a)
    if len(out) < K_CANDIDATES_MIN:
        raise ValueError(f"candidate generator produced {len(out)} < {K_CANDIDATES_MIN}")
    return out


def analytic_sum_g(
    goal_rel0: np.ndarray,
    action: np.ndarray,
    *,
    horizon: int,
    reward_cfg: RewardConfig,
) -> float:
    """⓿d real side: sum analytic progress over H steps (pure geometry)."""
    g = np.asarray(goal_rel0, dtype=np.float64).reshape(4).copy()
    a = np.asarray(action, dtype=np.float64).reshape(4)
    total = 0.0
    for _ in range(int(horizon)):
        prog = analytic_progress(g, a[:3], a, w_maneuver=float(reward_cfg.w_maneuver))
        total += float(prog)
        g = advance_goal_rel_body(g, a)
    return total


def imagined_sum_g(
    dynamics: Any,
    z0: np.ndarray,
    action: np.ndarray,
    *,
    horizon: int,
    goal_rel0: np.ndarray,
    body_vel0: np.ndarray,
    reward_cfg: RewardConfig,
    action_limits: Optional[np.ndarray],
) -> Tuple[float, int]:
    """Imagined side: model Σ reward over H (not Pearson / not mixed horizon)."""
    pol = ConstantLatentPolicy(action)
    roll = imagine(
        dynamics,
        pol,
        np.asarray(z0, dtype=np.float64).reshape(1, -1),
        int(horizon),
        reward_cfg=reward_cfg,
        goal_rel0=np.asarray(goal_rel0, dtype=np.float32).reshape(1, 4),
        body_vel0=np.asarray(body_vel0, dtype=np.float32).reshape(1, 3),
        action_limits=action_limits,
    )
    return float(roll.rewards.sum()), int(roll.n_action_clipped)


def top1_in_real_top_quarter(
    real_scores: Sequence[float],
    imag_scores: Sequence[float],
    *,
    quantile: float = TOP_QUANTILE,
) -> bool:
    """⓿b: imagined argmax lies in real top ``quantile`` fraction."""
    real = np.asarray(real_scores, dtype=np.float64)
    imag = np.asarray(imag_scores, dtype=np.float64)
    k = int(real.size)
    if k == 0:
        return False
    top_n = max(1, int(np.ceil(k * float(quantile))))
    real_order = np.argsort(-real, kind="mergesort")
    top_set = set(real_order[:top_n].tolist())
    imag_best = int(np.argmax(imag))
    return imag_best in top_set


def check_rho_a(
    rhos: Sequence[float],
    *,
    thr: RhoThresholds,
) -> Dict[str, Any]:
    arr = np.asarray(rhos, dtype=np.float64)
    arr = arr[np.isfinite(arr)]
    n = int(arr.size)
    med = float(np.median(arr)) if n else float("nan")
    ok = n >= thr.n_z0_min and np.isfinite(med) and med >= thr.rho_median_min
    return {
        "ok": bool(ok),
        "median_spearman": round(med, 4) if np.isfinite(med) else None,
        "n_z0": n,
        "n_z0_min": thr.n_z0_min,
        "threshold": thr.rho_median_min,
        "metric": "spearman_only",
    }


def check_rho_b(
    top1_hits: Sequence[bool],
    *,
    thr: RhoThresholds,
) -> Dict[str, Any]:
    hits = [bool(x) for x in top1_hits]
    n = len(hits)
    rate = float(np.mean(hits)) if n else float("nan")
    ok = n >= thr.n_z0_min and np.isfinite(rate) and rate >= thr.top1_min
    return {
        "ok": bool(ok),
        "top1_hit_rate": round(rate, 4) if np.isfinite(rate) else None,
        "n_z0": n,
        "threshold": thr.top1_min,
        "top_quantile": TOP_QUANTILE,
    }


def check_rho_c(*, horizon: int, used_pearson: bool, mixed_horizon: bool) -> Dict[str, Any]:
    ok = not used_pearson and not mixed_horizon
    return {
        "ok": bool(ok),
        "horizon": int(horizon),
        "used_pearson": bool(used_pearson),
        "mixed_horizon": bool(mixed_horizon),
        "note": "⓿c protocol guard — Spearman only, fixed H",
    }


def check_rho_d(*, real_side: str, imag_side: str) -> Dict[str, Any]:
    ok = real_side == "analytic_progress_sum" and imag_side == "imagine_reward_sum"
    return {
        "ok": bool(ok),
        "real_side_G": real_side,
        "imag_side_G": imag_side,
    }


def check_rho_e(z0e: Dict[str, Any], *, thr: RhoThresholds) -> Dict[str, Any]:
    med_rel = z0e.get("median_rel_l2")
    ok = bool(z0e.get("ok")) and med_rel is not None and float(med_rel) <= thr.z0e_rel_l2_max
    return {
        "ok": bool(ok),
        "median_rel_l2": med_rel,
        "threshold_rel_l2": thr.z0e_rel_l2_max,
        "n_poses": z0e.get("n_poses"),
        "z0_source": z0e.get("z0_source"),
        "detail": z0e,
    }


def aggregate_verdict(sub: Dict[str, Any]) -> Dict[str, Any]:
    keys = ("a", "b", "c", "d", "e")
    ok_map = {k: bool(sub.get(k, {}).get("ok", False)) for k in keys}
    # ⓿e failure marks non-authoritative but merge keys are a/b for signal.
    merge_keys = ("a", "b", "c", "d")
    ok_merge = all(ok_map[k] for k in merge_keys)
    return {
        "ok": bool(ok_merge and ok_map["e"]),
        "ok_merge_abcd": ok_merge,
        "sub": ok_map,
    }


def _encode_obs(dynamics: Any, obs: Any) -> np.ndarray:
    view = obs.policy_view()
    enc_state = np.array(
        [
            view.proprio[0],
            view.proprio[1],
            view.proprio[2],
            0.0,
            0.0,
            0.0,
            view.proprio[3],
        ],
        dtype=np.float32,
    )
    from experiments.aerial.rl.env.obs import Observation

    return np.asarray(
        dynamics.encode(
            Observation(rgb=view.rgb, state=enc_state, t=float(view.t)),
        ),
        dtype=np.float64,
    ).reshape(-1)


def run_z0e(
    *,
    wm_ckpt: Path,
    device: str,
    config: Dict[str, Any],
    env_host: str,
    n_poses: int,
    rollout_dataset: Optional[Path],
    seed: int,
) -> Dict[str, Any]:
    """⓿e: AirSim teleport → encode → re-teleport → encode; compare latents."""
    import yaml

    from experiments.aerial.rl._v0_gate import _obstacle_candidate_positions
    from experiments.aerial.rl.train_rl import _build_env, load_torch_dynamics

    cfg = dict(config)
    cfg.setdefault("env", {})["host"] = str(env_host)
    env = _build_env(cfg.get("env", {}) or {})
    reward_cfg = RewardConfig(**(cfg.get("reward", {}) or {})) if cfg.get("reward") else RewardConfig()
    wm_cfg = cfg.get("world_model", {}) or {}
    dynamics, _ = load_torch_dynamics(
        wm_cfg,
        wm_ckpt,
        device=str(device),
        success_dist_m=float(reward_cfg.success_dist_m),
    )

    ds = rollout_dataset
    if ds is None:
        ds = Path(
            "~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/dataset_v0_local_depth_r60_20260814"
        ).expanduser()
    cand, cand_yaw = _obstacle_candidate_positions(ds, min_altitude_m=0.0)
    rng = np.random.default_rng(int(seed))
    idx = rng.choice(len(cand), size=min(int(n_poses), len(cand)), replace=False)

    rows: List[Dict[str, Any]] = []
    rel_l2: List[float] = []
    goal_dist = float((config.get("reward") or {}).get("goal_dist_m", 30.0))
    for i, ci in enumerate(idx.tolist()):
        pos = np.asarray(cand[ci], dtype=np.float64).reshape(3)
        yaw = float(cand_yaw[ci]) if cand_yaw is not None else 0.0
        # OpenFly episode shape: pos[0]=start, pos[-1]=goal along +x body heading.
        goal = pos + np.array(
            [goal_dist * np.cos(yaw), goal_dist * np.sin(yaw), 0.0],
            dtype=np.float64,
        )
        epi = {
            "pos": np.stack([pos, goal]),
            "yaw": np.array([yaw, yaw], dtype=np.float64),
        }
        env.reset(epi)
        z1 = _encode_obs(dynamics, env.observe())
        env.reset(epi)
        z2 = _encode_obs(dynamics, env.observe())
        denom = max(float(np.linalg.norm(z1)), 1e-9)
        rl2 = float(np.linalg.norm(z1 - z2) / denom)
        rel_l2.append(rl2)
        rows.append(
            {
                "idx": int(i),
                "candidate_idx": int(ci),
                "rel_l2": round(rl2, 6),
                "abs_l2": round(float(np.linalg.norm(z1 - z2)), 6),
                "cosine": round(float(np.dot(z1, z2) / (denom * max(np.linalg.norm(z2), 1e-9))), 6),
            }
        )

    med = float(np.median(rel_l2)) if rel_l2 else float("nan")
    return {
        "ok": bool(rel_l2) and np.isfinite(med) and med <= Z0E_REL_L2_MAX,
        "median_rel_l2": round(med, 6) if np.isfinite(med) else None,
        "n_poses": len(rel_l2),
        "z0_source": "candidate_positions_double_teleport",
        "poses": rows,
    }


def run_eval(
    *,
    dataset: Path,
    wm_ckpt: Path,
    device: str,
    config: Dict[str, Any],
    max_episodes: int,
    horizon: int,
    z0e_result: Optional[Dict[str, Any]],
    emit: Optional[Path],
) -> Dict[str, Any]:
    from experiments.aerial.rl import dataset as ds
    from experiments.aerial.rl.train_rl import load_torch_dynamics

    reward_cfg = RewardConfig(**(config.get("reward", {}) or {})) if config.get("reward") else RewardConfig()
    wm_cfg = config.get("world_model", {}) or {}
    thr = RhoThresholds(horizon=int(horizon))
    step_hz = float((config.get("env") or {}).get("step_hz", 5.0))
    limits = body_delta_limits(1.0 / step_hz)
    candidates = default_candidate_actions(limits)
    cand_labels = [f"c{j}" for j in range(len(candidates))]

    dynamics, wm_payload = load_torch_dynamics(
        wm_cfg,
        wm_ckpt,
        device=str(device),
        success_dist_m=float(reward_cfg.success_dist_m),
    )

    episodes = ds.load_dataset(dataset, skip_quarantined=True)
    if max_episodes > 0:
        episodes = episodes[: int(max_episodes)]

    per_z0: List[Dict[str, Any]] = []
    rhos: List[float] = []
    top1_hits: List[bool] = []
    n_clip_total = 0

    for ep_i, ep in enumerate(episodes):
        if not ep:
            continue
        t0 = ep[0]
        z0 = dynamics.encode(t0.obs)
        goal_rel0 = goal_rel_from_obs(t0.obs)
        body_vel0 = body_vel_from_obs(t0.obs)

        real_scores: List[float] = []
        imag_scores: List[float] = []
        n_clip = 0
        for a in candidates:
            real_scores.append(
                analytic_sum_g(goal_rel0, a, horizon=thr.horizon, reward_cfg=reward_cfg)
            )
            ig, nc = imagined_sum_g(
                dynamics,
                z0,
                a,
                horizon=thr.horizon,
                goal_rel0=goal_rel0,
                body_vel0=body_vel0,
                reward_cfg=reward_cfg,
                action_limits=limits,
            )
            imag_scores.append(ig)
            n_clip += nc
        n_clip_total += n_clip

        rho = spearman_rho(real_scores, imag_scores)
        t1 = top1_in_real_top_quarter(real_scores, imag_scores)
        if np.isfinite(rho):
            rhos.append(float(rho))
        top1_hits.append(bool(t1))
        per_z0.append(
            {
                "episode_idx": ep_i,
                "spearman": round(float(rho), 4) if np.isfinite(rho) else None,
                "top1_hit": bool(t1),
                "real_scores": [round(x, 4) for x in real_scores],
                "imag_scores": [round(x, 4) for x in imag_scores],
                "candidates": [a.tolist() for a in candidates],
                "goal_rel0": np.asarray(goal_rel0, dtype=float).tolist(),
            }
        )

    sub_a = check_rho_a(rhos, thr=thr)
    sub_b = check_rho_b(top1_hits, thr=thr)
    sub_c = check_rho_c(horizon=thr.horizon, used_pearson=False, mixed_horizon=False)
    sub_d = check_rho_d(real_side="analytic_progress_sum", imag_side="imagine_reward_sum")
    z0e_stub = z0e_result or {"ok": False, "note": "z0e not run — authoritative=false"}
    sub_e = check_rho_e(z0e_stub, thr=thr)

    sub = {"a": sub_a, "b": sub_b, "c": sub_c, "d": sub_d, "e": sub_e}
    verdict = aggregate_verdict(sub)
    if not sub_e.get("ok"):
        verdict["authoritative"] = False
        verdict.setdefault("reason", "⓿e teleport z0 reproducibility failed or missing")
    else:
        verdict["authoritative"] = bool(sub_a.get("n_z0", 0) >= thr.n_z0_min)

    payload: Dict[str, Any] = {
        "step": "P4",
        "signal": "V4-⓿-v2",
        "dataset": str(dataset),
        "wm_ckpt": str(wm_ckpt),
        "wm_step": wm_payload.get("step"),
        "horizon": thr.horizon,
        "n_candidates": len(candidates),
        "candidate_labels": cand_labels,
        "body_delta_limits": limits.tolist(),
        "step_hz": step_hz,
        "per_z0": per_z0,
        "n_action_clipped_total": int(n_clip_total),
        "sub": sub,
        "verdict": verdict,
    }
    if emit is not None:
        emit.parent.mkdir(parents=True, exist_ok=True)
        emit.write_text(json.dumps(payload, indent=2, default=str) + "\n")
        print(f"[v4-rho] wrote {emit}")
    return payload


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description="V4-⓿ v2 (P4) imagine ranking eval")
    p.add_argument("--mode", choices=("rank", "z0e", "full"), default="full")
    p.add_argument("--config", default="configs/aerial_rl.yaml")
    p.add_argument(
        "--dataset",
        default="~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/dataset_v0_local_depth_r60_20260814",
    )
    p.add_argument(
        "--wm-ckpt",
        default="experiments/aerial/rl/artifacts/wm_ckpt_r60_rh_20260816/wm_step_1000.pt",
    )
    p.add_argument("--device", default="cuda")
    p.add_argument("--max-episodes", type=int, default=16)
    p.add_argument("--horizon", type=int, default=HORIZON_DEFAULT)
    p.add_argument("--env-host", default="127.0.0.1")
    p.add_argument("--n-z0e", type=int, default=8)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--emit", default="artifacts/v4_rho_p4_20260820.json")
    p.add_argument("--emit-z0e", default="artifacts/v4_rho_p4_z0e_20260820.json")
    p.add_argument("--z0e-json", default=None, help="precomputed ⓿e artifact for rank-only mode")
    args = p.parse_args(list(argv) if argv is not None else None)

    root = Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    import yaml

    cfg = yaml.safe_load((root / args.config).read_text()) or {}
    dataset = Path(args.dataset).expanduser()
    if not dataset.is_absolute():
        dataset = root / dataset
    wm_ckpt = Path(args.wm_ckpt).expanduser()
    if not wm_ckpt.is_absolute():
        wm_ckpt = root / wm_ckpt

    z0e_result: Optional[Dict[str, Any]] = None
    if args.mode in ("z0e", "full"):
        z0e_result = run_z0e(
            wm_ckpt=wm_ckpt,
            device=str(args.device),
            config=cfg,
            env_host=str(args.env_host),
            n_poses=int(args.n_z0e),
            rollout_dataset=dataset,
            seed=int(args.seed),
        )
        z0e_path = Path(args.emit_z0e).expanduser()
        if not z0e_path.is_absolute():
            z0e_path = root / z0e_path
        z0e_path.parent.mkdir(parents=True, exist_ok=True)
        z0e_path.write_text(json.dumps(z0e_result, indent=2, default=str) + "\n")
        print(f"[v4-rho] wrote {z0e_path}")
        if args.mode == "z0e":
            return 0 if z0e_result.get("ok") else 1

    if args.z0e_json:
        z0e_path = Path(args.z0e_json).expanduser()
        if not z0e_path.is_absolute():
            z0e_path = root / z0e_path
        z0e_result = json.loads(z0e_path.read_text())

    if args.mode in ("rank", "full"):
        emit = Path(args.emit).expanduser()
        if not emit.is_absolute():
            emit = root / emit
        payload = run_eval(
            dataset=dataset,
            wm_ckpt=wm_ckpt,
            device=str(args.device),
            config=cfg,
            max_episodes=int(args.max_episodes),
            horizon=int(args.horizon),
            z0e_result=z0e_result,
            emit=emit,
        )
        ok = bool(payload.get("verdict", {}).get("ok"))
        print(f"[v4-rho] verdict ok={ok} sub={payload['verdict'].get('sub')}")
        return 0 if ok else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
