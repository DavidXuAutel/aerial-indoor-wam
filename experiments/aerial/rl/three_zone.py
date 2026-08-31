"""Three-zone speed governor — shared kinematics for shield + offline eval.

Default profile: **8 / 5 / 1.5 m @ 2 / 1 / 0.2 m/s** with cruise 5 m/s,
``a_max=2.5 m/s²``, engage outer ≈ **12.2 m** (see declare 20260823).
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple

# Recommended deploy profile (Mac kinematics + 4090 hold035 PASS).
DEFAULT_L1 = 8.0
DEFAULT_L2 = 5.0
DEFAULT_L3 = 1.5
DEFAULT_V1 = 2.0
DEFAULT_V2 = 1.0
DEFAULT_V_STOP = 0.2
DEFAULT_V_CRUISE = 5.0
DEFAULT_A_MAX = 2.5
DEFAULT_DT = 0.2
DEFAULT_DELAY_S = 0.2


@dataclass(frozen=True)
class ThreeZoneSpec:
    l1_m: float = DEFAULT_L1
    l2_m: float = DEFAULT_L2
    l3_m: float = DEFAULT_L3
    v1_m_s: float = DEFAULT_V1
    v2_m_s: float = DEFAULT_V2
    v_stop_m_s: float = DEFAULT_V_STOP
    v_cruise_m_s: float = DEFAULT_V_CRUISE
    a_max_m_s2: float = DEFAULT_A_MAX
    dt_s: float = DEFAULT_DT
    delay_s: float = DEFAULT_DELAY_S

    @property
    def engage_outer_m(self) -> float:
        return self.l1_m + need(self.v_cruise_m_s, self.v1_m_s, self.a_max_m_s2)

    @classmethod
    def from_mapping(cls, cfg: Any) -> "ThreeZoneSpec":
        g = cfg if isinstance(cfg, dict) else {}
        return cls(
            l1_m=float(g.get("l1_m", DEFAULT_L1)),
            l2_m=float(g.get("l2_m", DEFAULT_L2)),
            l3_m=float(g.get("l3_m", DEFAULT_L3)),
            v1_m_s=float(g.get("v1_m_s", DEFAULT_V1)),
            v2_m_s=float(g.get("v2_m_s", DEFAULT_V2)),
            v_stop_m_s=float(g.get("v_stop_m_s", DEFAULT_V_STOP)),
            v_cruise_m_s=float(g.get("v_cruise_m_s", DEFAULT_V_CRUISE)),
            a_max_m_s2=float(g.get("a_max_m_s2", DEFAULT_A_MAX)),
            dt_s=float(g.get("dt_s", DEFAULT_DT)),
            delay_s=float(g.get("delay_s", DEFAULT_DELAY_S)),
        )


def need(v0: float, v1: float, a: float) -> float:
    if v0 <= v1:
        return 0.0
    return (v0 * v0 - v1 * v1) / (2.0 * max(a, 1e-9))


def planned_speed_m_s(d_hat: float, spec: ThreeZoneSpec) -> float:
    """Instantaneous speed cap from predicted forward depth (no perception delay)."""
    d = float(d_hat)
    if d > spec.engage_outer_m:
        return float(spec.v_cruise_m_s)
    if d > spec.l1_m:
        return math.sqrt(max(0.0, spec.v1_m_s ** 2 + 2.0 * spec.a_max_m_s2 * (d - spec.l1_m)))
    if d > spec.l2_m:
        return min(
            spec.v1_m_s,
            math.sqrt(max(0.0, spec.v2_m_s ** 2 + 2.0 * spec.a_max_m_s2 * (d - spec.l2_m))),
        )
    if d > spec.l3_m:
        return min(
            spec.v2_m_s,
            math.sqrt(max(0.0, spec.v_stop_m_s ** 2 + 2.0 * spec.a_max_m_s2 * (d - spec.l3_m))),
        )
    return float(spec.v_stop_m_s)


def simulate_three_zone(
    spec: ThreeZoneSpec,
    *,
    d0: float = 20.0,
    v0: Optional[float] = None,
    engage_delay_m: float = 0.0,
) -> Tuple[bool, List[Tuple[float, float, float]], List[str]]:
    """Bang-bang decel profile; optional constant engage delay (m) after true engage."""
    v0 = float(spec.v_cruise_m_s if v0 is None else v0)
    d, v, t = float(d0), v0, 0.0
    traj: List[Tuple[float, float, float]] = []
    violations: List[str] = []
    engaged = False
    true_eng = spec.engage_outer_m

    if spec.delay_s > 0:
        d -= v * spec.delay_s
        t += spec.delay_s

    while t < 40.0:
        if not engaged and d <= true_eng + engage_delay_m:
            engaged = True
        if engaged:
            v_plan = planned_speed_m_s(d, spec)
            if v > v_plan + 1e-3:
                v = max(v_plan, v - spec.a_max_m_s2 * spec.dt_s)
        traj.append((t, d, v))
        if d <= spec.l1_m and d > spec.l2_m and v > spec.v1_m_s + 0.05:
            violations.append("z1")
        if d <= spec.l2_m and d > spec.l3_m and v > spec.v2_m_s + 0.05:
            violations.append("z2")
        if d <= spec.l3_m and v > spec.v_stop_m_s + 0.05:
            violations.append("z3")
        t += spec.dt_s
        d -= v * spec.dt_s
        if d <= spec.l3_m and v <= spec.v_stop_m_s + 0.05:
            return len(violations) == 0, traj, violations
        if d <= 0:
            return False, traj, violations + ["collision"]
    return False, traj, violations + ["timeout"]


def max_engage_delay_m(spec: ThreeZoneSpec, *, d0: float = 20.0) -> float:
    """Binary search: max extra engage delay (m) that still passes zone caps."""
    lo, hi = 0.0, 3.0
    for _ in range(24):
        mid = 0.5 * (lo + hi)
        ok, _, _ = simulate_three_zone(spec, d0=d0, engage_delay_m=mid)
        if ok:
            lo = mid
        else:
            hi = mid
    return lo


def kinematic_budget(spec: ThreeZoneSpec) -> Dict[str, Any]:
    """Per-boundary depth under-read budget (D̂ − GT > 0 ⇒ late engage)."""
    ok, _, _ = simulate_three_zone(spec)
    eng = spec.engage_outer_m
    delay_budget = max_engage_delay_m(spec)
    m_outer = eng - need(spec.v_cruise_m_s, spec.v1_m_s, spec.a_max_m_s2) - spec.l1_m
    m_mid = (spec.l1_m - spec.l2_m) - need(spec.v1_m_s, spec.v2_m_s, spec.a_max_m_s2)
    m_inner = (spec.l2_m - spec.l3_m) - need(spec.v2_m_s, spec.v_stop_m_s, spec.a_max_m_s2)
    return {
        "spec": asdict(spec),
        "feasible_nominal": ok,
        "engage_outer_m": round(eng, 3),
        "max_engage_delay_m": round(delay_budget, 3),
        "max_underread_at_engage_m": round(delay_budget, 3),
        "segment_margin_m": {
            "outer_to_l1": round(m_outer, 3),
            "l1_to_l2": round(m_mid, 3),
            "l2_to_l3": round(m_inner, 3),
        },
        "required_sigma_rel_at_l1": round(delay_budget / max(spec.l1_m, 1e-6), 4),
        "required_sigma_rel_at_l2": round(
            min(m_mid, delay_budget) / max(spec.l2_m, 1e-6), 4
        ),
        "required_sigma_rel_at_l3": round(
            min(m_inner, delay_budget) / max(spec.l3_m, 1e-6), 4
        ),
    }
