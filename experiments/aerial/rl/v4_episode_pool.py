"""P0c: eval-period episode drop accounting + spare-start refill (§4.6 / RUNBOOK P0c).

Three mutually exclusive counters (never merge into a single "drops" bucket):
  * ``n_invalid_spawn`` — spawn-in-collision or proprio teleport-jitter after retries
  * ``n_none_returned`` — transient health/reset failure (_run_one_resilient → None)
  * ``n_pair_broken`` — one arm of a paired eval returned a episode, the other None

Spare starts are drawn from a pre-scanned pool (same candidate_positions source);
consume order is frozen in a manifest **before** any scored rollout begins.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

from experiments.aerial.rl import v0_rollout_eval as rollout

# Frozen §4.6.1: n per layer = 16; do not lower.
FROZEN_N_PER_LAYER = 16

_INVALID_SPAWN_KINDS = frozenset({"spawn_collision", "proprio_jitter"})


@dataclass
class EpisodeDropCounters:
    """Mutually exclusive drop counters for P0c (§4.6.1 / RUNBOOK §5)."""

    n_invalid_spawn: int = 0
    n_none_returned: int = 0
    n_pair_broken: int = 0

    def to_dict(self) -> Dict[str, int]:
        return asdict(self)

    def record_invalid_spawn(self) -> None:
        self.n_invalid_spawn += 1

    def record_none_returned(self) -> None:
        self.n_none_returned += 1

    def record_pair_broken(self) -> None:
        self.n_pair_broken += 1


def classify_resilient_drop_kind(drop_kind: str) -> str:
    """Map ``_run_one_resilient`` drop_stats key → counter field name."""
    if drop_kind in _INVALID_SPAWN_KINDS:
        return "n_invalid_spawn"
    return "n_none_returned"


def run_one_resilient_classified(
    env: Any,
    policy: Any,
    episode: Dict[str, np.ndarray],
    *,
    max_steps: int,
    reward_cfg: Any = None,
    shield: Any = None,
    depth_predictor: Any = None,
    tau_predictor: Any = None,
    dynamics: Any = None,
    retries: int = 2,
    retry_sleep_s: float = 0.5,
    max_step_travel_m: float = rollout._MAX_STEP_TRAVEL_M,
) -> Tuple[Optional[rollout.Episode], Optional[str]]:
    """Run ``_run_one_resilient`` and return ``(episode, drop_kind_or_none)``."""
    drop_stats: Dict[str, int] = {}
    ep = rollout._run_one_resilient(
        env,
        policy,
        episode,
        max_steps=max_steps,
        reward_cfg=reward_cfg,
        shield=shield,
        depth_predictor=depth_predictor,
        tau_predictor=tau_predictor,
        dynamics=dynamics,
        retries=retries,
        retry_sleep_s=retry_sleep_s,
        drop_stats=drop_stats,
        max_step_travel_m=max_step_travel_m,
    )
    if ep is not None:
        return ep, None
    # Exactly one kind is incremented when resilient gives up.
    for kind in ("spawn_collision", "proprio_jitter", "health"):
        if drop_stats.get(kind, 0) > 0:
            return None, kind
    return None, "health"


@dataclass
class SpareManifest:
    """Frozen spare pool: primary indices, spare indices, consume order."""

    layer: str
    target_n: int
    primary_indices: List[int]
    spare_indices: List[int]
    consume_order: List[int]
    frozen_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2) + "\n")


def split_primary_spare(
    episodes: Sequence[Dict[str, np.ndarray]],
    *,
    target_n: int,
    spare_count: int,
    layer: str = "gate",
    seed: int = 0,
) -> Tuple[List[Dict[str, np.ndarray]], List[Dict[str, np.ndarray]], SpareManifest]:
    """Split a pre-scanned episode list into primary (first ``target_n``) and spare."""
    n_primary = min(int(target_n), len(episodes))
    primary = list(episodes[:n_primary])
    spare = list(episodes[n_primary : n_primary + int(spare_count)])
    primary_idx = list(range(n_primary))
    spare_idx = list(range(n_primary, n_primary + len(spare)))
    # Consume order: deterministic shuffle of spare indices (frozen before run).
    rng = np.random.default_rng(int(seed))
    order = spare_idx.copy()
    rng.shuffle(order)
    manifest = SpareManifest(
        layer=str(layer),
        target_n=int(target_n),
        primary_indices=primary_idx,
        spare_indices=spare_idx,
        consume_order=order,
    )
    return primary, spare, manifest


def _episode_queue(
    primary: Sequence[Dict[str, np.ndarray]],
    spare: Sequence[Dict[str, np.ndarray]],
    manifest: SpareManifest,
) -> List[Dict[str, np.ndarray]]:
    """Primary list followed by spares in frozen consume order."""
    all_eps = list(primary) + list(spare)
    out: List[Dict[str, np.ndarray]] = list(primary)
    for idx in manifest.consume_order:
        rel = idx - len(manifest.primary_indices)
        if 0 <= rel < len(spare):
            out.append(spare[rel])
        elif idx < len(all_eps):
            out.append(all_eps[idx])
    return out


@dataclass
class PairedEvalResult:
    """Outcome of a paired eval loop with spare refill."""

    scored_episodes: List[Dict[str, np.ndarray]]
    n_scored: int
    target_n: int
    counters: EpisodeDropCounters
    authoritative: bool
    spare_consumed: int

    def drop_summary(self) -> Dict[str, Any]:
        return {
            "n_scored": self.n_scored,
            "target_n": self.target_n,
            "authoritative": self.authoritative,
            "spare_consumed": self.spare_consumed,
            **self.counters.to_dict(),
        }


def run_paired_two_arm(
    env: Any,
    episode: Dict[str, np.ndarray],
    *,
    run_arm_a: Callable[[], Tuple[Optional[rollout.Episode], Optional[str]]],
    run_arm_b: Callable[[], Tuple[Optional[rollout.Episode], Optional[str]]],
    counters: EpisodeDropCounters,
) -> Tuple[Optional[rollout.Episode], Optional[rollout.Episode], bool]:
    """Run paired arms; return (ep_a, ep_b, scored_ok).

    On arm-a drop: record invalid/none counter, return (None, None, False).
    On arm-b drop after arm-a ok: record pair_broken, return (None, None, False).
    """
    ep_a, drop_a = run_arm_a()
    if ep_a is None:
        if drop_a is not None:
            field_name = classify_resilient_drop_kind(drop_a)
            if field_name == "n_invalid_spawn":
                counters.record_invalid_spawn()
            else:
                counters.record_none_returned()
        else:
            counters.record_none_returned()
        return None, None, False

    ep_b, drop_b = run_arm_b()
    if ep_b is None:
        counters.record_pair_broken()
        return None, None, False

    return ep_a, ep_b, True


def fill_to_target_n(
    env: Any,
    primary: Sequence[Dict[str, np.ndarray]],
    spare: Sequence[Dict[str, np.ndarray]],
    manifest: SpareManifest,
    *,
    target_n: int,
    score_one: Callable[
        [Dict[str, np.ndarray], EpisodeDropCounters],
        bool,
    ],
) -> PairedEvalResult:
    """Try primary then spare starts until ``target_n`` scored or queue exhausted."""
    counters = EpisodeDropCounters()
    queue = _episode_queue(primary, spare, manifest)
    scored: List[Dict[str, np.ndarray]] = []
    spare_consumed = 0
    n_primary = len(primary)

    for i, epi in enumerate(queue):
        if len(scored) >= int(target_n):
            break
        if score_one(epi, counters):
            scored.append(epi)
        if i >= n_primary:
            spare_consumed += 1

    n_scored = len(scored)
    authoritative = n_scored >= int(target_n)
    return PairedEvalResult(
        scored_episodes=scored,
        n_scored=n_scored,
        target_n=int(target_n),
        counters=counters,
        authoritative=authoritative,
        spare_consumed=spare_consumed,
    )


def _goal_of(env: Any) -> Optional[np.ndarray]:
    goal = getattr(env, "goal", None)
    if goal is not None:
        return np.asarray(goal, dtype=np.float64)
    return None


def _progress_from_episode(
    env: Any,
    ep: rollout.Episode,
) -> Tuple[float, float]:
    goal = _goal_of(env)
    if goal is None or not ep:
        return 0.0, float("nan")
    start_pos = np.asarray(ep[0].obs.position, dtype=np.float64)
    final_pos = np.asarray(ep[-1].next_obs.position, dtype=np.float64)
    init_d = float(np.linalg.norm(goal - start_pos))
    final_d = float(np.linalg.norm(goal - final_pos))
    return init_d - final_d, final_d


def run_progress_eval_p0c(
    env: Any,
    policy: Any,
    random_policy: Any,
    primary: Sequence[Dict[str, np.ndarray]],
    spare: Sequence[Dict[str, np.ndarray]],
    manifest: SpareManifest,
    *,
    target_n: int = FROZEN_N_PER_LAYER,
    max_steps: int = 200,
    reward_cfg: Any = None,
    retry_sleep_s: float = 0.5,
) -> Tuple[Dict[str, List[float]], PairedEvalResult]:
    """Signal ①/② progress eval with P0c spare refill and drop counters."""
    out: Dict[str, List[float]] = {
        "policy_progress_sums": [],
        "random_progress_sums": [],
        "policy_final_dists": [],
        "random_final_dists": [],
    }
    pending: List[Tuple[float, float, float, float]] = []

    def score_one(epi: Dict[str, np.ndarray], counters: EpisodeDropCounters) -> bool:
        if hasattr(policy, "reset"):
            policy.reset()
        if hasattr(random_policy, "reset"):
            random_policy.reset()

        def run_arm_a() -> Tuple[Optional[rollout.Episode], Optional[str]]:
            return run_one_resilient_classified(
                env, policy, epi, max_steps=max_steps, reward_cfg=reward_cfg,
                retry_sleep_s=retry_sleep_s,
            )

        def run_arm_b() -> Tuple[Optional[rollout.Episode], Optional[str]]:
            return run_one_resilient_classified(
                env, random_policy, epi, max_steps=max_steps, reward_cfg=reward_cfg,
                retry_sleep_s=retry_sleep_s,
            )

        ep_a, ep_b, ok = run_paired_two_arm(
            env, epi, run_arm_a=run_arm_a, run_arm_b=run_arm_b, counters=counters,
        )
        if not ok or ep_a is None or ep_b is None:
            return False
        p_prog, p_final = _progress_from_episode(env, ep_a)
        r_prog, r_final = _progress_from_episode(env, ep_b)
        pending.append((p_prog, r_prog, p_final, r_final))
        return True

    result = fill_to_target_n(
        env, primary, spare, manifest, target_n=target_n, score_one=score_one,
    )
    for p_prog, r_prog, p_final, r_final in pending:
        out["policy_progress_sums"].append(p_prog)
        out["random_progress_sums"].append(r_prog)
        out["policy_final_dists"].append(p_final)
        out["random_final_dists"].append(r_final)
    return out, result


def run_shield_eval_p0c(
    env: Any,
    policy: Any,
    depth_predictor_on: Any,
    primary: Sequence[Dict[str, np.ndarray]],
    spare: Sequence[Dict[str, np.ndarray]],
    manifest: SpareManifest,
    *,
    target_n: int = FROZEN_N_PER_LAYER,
    near_collision_depth_m: float = 1.5,
    shield_trigger_depth_m: float = 3.0,  # legacy V0; V4 deploy uses three_zone (ignored)
    max_steps: int = 200,
    reward_cfg: Any = None,
    tau_predictor: Any = None,
    dynamics: Any = None,
    retry_sleep_s: float = 0.5,
    max_step_travel_m: float = rollout._MAX_STEP_TRAVEL_M,
    both_arms_unshielded: bool = False,
) -> Tuple[Dict[str, Any], PairedEvalResult]:
    """Signal ④ shield eval with P0c spare refill and drop counters."""
    from experiments.aerial.rl.safety import ThreeZoneSpeedShield
    from experiments.aerial.rl.three_zone import ThreeZoneSpec

    _ = shield_trigger_depth_m  # V0 legacy; V4 uses three-zone governor
    shield = None if both_arms_unshielded else ThreeZoneSpeedShield(zone=ThreeZoneSpec())
    interventions_on: List[List[bool]] = []
    collided_on: List[List[bool]] = []
    near_coll_on: List[List[bool]] = []
    near_coll_off: List[List[bool]] = []
    depth_steps = 0

    def score_one(epi: Dict[str, np.ndarray], counters: EpisodeDropCounters) -> bool:
        nonlocal depth_steps
        if hasattr(policy, "reset"):
            policy.reset()
        if shield is not None and hasattr(shield, "reset"):
            shield.reset()
        if tau_predictor is not None and hasattr(tau_predictor, "reset"):
            tau_predictor.reset()

        def run_arm_on() -> Tuple[Optional[rollout.Episode], Optional[str]]:
            return run_one_resilient_classified(
                env, policy, epi, max_steps=max_steps, reward_cfg=reward_cfg,
                shield=shield,
                depth_predictor=depth_predictor_on if shield is not None else None,
                tau_predictor=tau_predictor if shield is not None else None,
                dynamics=dynamics if shield is not None else None,
                retry_sleep_s=retry_sleep_s,
                max_step_travel_m=max_step_travel_m,
            )

        def run_arm_off() -> Tuple[Optional[rollout.Episode], Optional[str]]:
            if hasattr(policy, "reset"):
                policy.reset()
            return run_one_resilient_classified(
                env, policy, epi, max_steps=max_steps, reward_cfg=reward_cfg,
                shield=None, depth_predictor=None, tau_predictor=None,
                retry_sleep_s=retry_sleep_s, max_step_travel_m=max_step_travel_m,
            )

        ep_on, ep_off, ok = run_paired_two_arm(
            env, epi, run_arm_a=run_arm_on, run_arm_b=run_arm_off, counters=counters,
        )
        if not ok or ep_on is None or ep_off is None:
            return False

        m_on = rollout._episode_masks(
            ep_on, near_collision_depth_m=float(near_collision_depth_m),
        )
        interventions_on.append(m_on["intervention"])
        collided_on.append(m_on["collided"])
        near_coll_on.append(m_on["near"])
        depth_steps += int(m_on["depth_steps"])

        m_off = rollout._episode_masks(
            ep_off, near_collision_depth_m=float(near_collision_depth_m),
        )
        near_coll_off.append(m_off["near"])
        depth_steps += int(m_off["depth_steps"])
        return True

    result = fill_to_target_n(
        env, primary, spare, manifest, target_n=target_n, score_one=score_one,
    )
    masks = {
        "interventions_on": interventions_on,
        "collided_on": collided_on,
        "near_coll_on": near_coll_on,
        "near_coll_off": near_coll_off,
        "depth_steps": depth_steps,
    }
    return masks, result
