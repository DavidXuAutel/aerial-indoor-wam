"""Imagination collision ranking helpers (runbook step B).

Compare constant arms from a fixed latent: forward (into obstacle) vs lateral
bypass. Pure scoring / verdict — no training, no yaml flips.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Sequence

import numpy as np

from experiments.aerial.rl.env.action import body_delta_limits
from experiments.aerial.rl.imagination import imagine
from experiments.aerial.rl.planner import ConstantLatentPolicy
from experiments.aerial.rl.reward import RewardConfig


# Default thresholds: collision must visibly separate crash vs slide.
MIN_MEAN_P_COLL_GAP = 0.05
MIN_RETURN_GAP = 1.0


def default_arms(step_hz: float = 5.0) -> Dict[str, np.ndarray]:
    """Deployed-box constant actions: forward / left / right / retreat."""
    lim = body_delta_limits(1.0 / float(step_hz))
    fwd, lat, up, yaw = [float(x) for x in lim]
    return {
        "forward": np.array([fwd, 0.0, 0.0, 0.0], dtype=np.float64),
        "left": np.array([0.0, lat, 0.0, 0.0], dtype=np.float64),
        "right": np.array([0.0, -lat, 0.0, 0.0], dtype=np.float64),
        "retreat": np.array([-fwd, 0.0, 0.0, 0.0], dtype=np.float64),
    }


def score_arm(
    dynamics: Any,
    z0: np.ndarray,
    action: np.ndarray,
    *,
    horizon: int,
    goal_rel0: np.ndarray,
    body_vel0: np.ndarray,
    reward_cfg: RewardConfig,
    action_limits: np.ndarray,
) -> Dict[str, float]:
    """One imagined constant-action trajectory; return sum reward + mean p_coll."""
    pol = ConstantLatentPolicy(action)
    roll = imagine(
        dynamics,
        pol,
        np.asarray(z0, dtype=np.float64).reshape(1, -1),
        int(horizon),
        reward_cfg=reward_cfg,
        goal_rel0=np.asarray(goal_rel0, dtype=np.float32).reshape(1, 4),
        body_vel0=np.asarray(body_vel0, dtype=np.float32).reshape(1, 3),
        action_limits=np.asarray(action_limits, dtype=np.float64).reshape(4),
    )
    mask = np.ones(roll.rewards.shape[1], dtype=bool)
    if roll.done.shape[1] > 1:
        mask[1:] = ~roll.done[0, :-1]
    pcs = roll.p_coll[0][mask]
    return {
        "sum_reward": float(roll.rewards[0][mask].sum()),
        "mean_p_coll": float(pcs.mean()) if pcs.size else 0.0,
        "sum_progress": float(roll.progress[0][mask].sum()),
        "n_steps": int(mask.sum()),
    }


def score_arms_at_z0(
    dynamics: Any,
    z0: np.ndarray,
    *,
    horizon: int,
    goal_rel0: np.ndarray,
    body_vel0: np.ndarray,
    reward_cfg: RewardConfig,
    step_hz: float = 5.0,
    arms: Optional[Mapping[str, np.ndarray]] = None,
) -> Dict[str, Dict[str, float]]:
    lim = body_delta_limits(1.0 / float(step_hz))
    arm_map = dict(arms) if arms is not None else default_arms(step_hz)
    return {
        name: score_arm(
            dynamics,
            z0,
            a,
            horizon=horizon,
            goal_rel0=goal_rel0,
            body_vel0=body_vel0,
            reward_cfg=reward_cfg,
            action_limits=lim,
        )
        for name, a in arm_map.items()
    }


def pairwise_gaps(arm_scores: Mapping[str, Mapping[str, float]]) -> Dict[str, Any]:
    """forward vs best lateral (left/right by sum_reward)."""
    fwd = arm_scores["forward"]
    left = arm_scores["left"]
    right = arm_scores["right"]
    best_lat_name = "left" if left["sum_reward"] >= right["sum_reward"] else "right"
    best = arm_scores[best_lat_name]
    return {
        "best_lateral": best_lat_name,
        "return_gap_lateral_minus_forward": float(best["sum_reward"] - fwd["sum_reward"]),
        "p_coll_gap_forward_minus_lateral": float(fwd["mean_p_coll"] - best["mean_p_coll"]),
        "forward_mean_p_coll": float(fwd["mean_p_coll"]),
        "lateral_mean_p_coll": float(best["mean_p_coll"]),
        "forward_sum_reward": float(fwd["sum_reward"]),
        "lateral_sum_reward": float(best["sum_reward"]),
    }


def verdict_from_gaps(
    gaps: Sequence[Mapping[str, float]],
    *,
    min_p_coll_gap: float = MIN_MEAN_P_COLL_GAP,
    min_return_gap: float = MIN_RETURN_GAP,
) -> Dict[str, Any]:
    """Aggregate over many z0.

    Step B asks whether the **collision head** separates crash vs slide.
    Return gap alone can come from progress geometry and must not pass this gate.
    ``min_return_gap`` is recorded as a secondary diagnostic only.
    """
    if not gaps:
        return {
            "useful": False,
            "label": "insufficient_empty",
            "n_z0": 0,
            "median_p_coll_gap": None,
            "median_return_gap": None,
            "note": "no z0 scored",
        }
    pc = np.asarray([g["p_coll_gap_forward_minus_lateral"] for g in gaps], dtype=np.float64)
    rg = np.asarray([g["return_gap_lateral_minus_forward"] for g in gaps], dtype=np.float64)
    med_pc = float(np.median(pc))
    med_rg = float(np.median(rg))
    useful = med_pc >= float(min_p_coll_gap)
    return_only = (not useful) and (med_rg >= float(min_return_gap))
    return {
        "useful": bool(useful),
        "label": "useful" if useful else "insufficient",
        "n_z0": int(len(gaps)),
        "median_p_coll_gap": round(med_pc, 6),
        "median_return_gap": round(med_rg, 6),
        "mean_p_coll_gap": round(float(pc.mean()), 6),
        "mean_return_gap": round(float(rg.mean()), 6),
        "return_gap_without_p_coll": bool(return_only),
        "thresholds": {
            "min_mean_p_coll_gap": float(min_p_coll_gap),
            "min_return_gap_secondary": float(min_return_gap),
        },
        "note": (
            "撞明显更差（p_coll 可区分；可训 π）"
            if useful
            else (
                "不够：p_coll 几乎无差别（回报差若有来自进展几何，不算碰撞可用）；"
                "先修碰撞头/损失，勿猛训 π"
            )
        ),
    }
