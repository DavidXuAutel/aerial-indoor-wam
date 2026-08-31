"""Load indoor ThreeZoneSpeedShield from yaml (E2i.0w — no hardcoded spec in callers)."""
from __future__ import annotations

from typing import Any, Dict, Optional

from experiments.aerial.rl.safety import ThreeZoneSpeedShield
from experiments.aerial.rl.three_zone import ThreeZoneSpec


def indoor_safety_cfg(cfg: Dict[str, Any]) -> Dict[str, Any]:
    return dict(cfg.get("safety") or {})


def build_indoor_shield(cfg: Dict[str, Any], *, shield_off: bool = False) -> Optional[ThreeZoneSpeedShield]:
    if shield_off:
        return None
    safety = indoor_safety_cfg(cfg)
    zone = ThreeZoneSpec.from_mapping(safety)
    return ThreeZoneSpeedShield(
        zone=zone,
        min_tau_s=float(safety.get("min_tau_s", 0.5)),
        max_p_coll=float(safety.get("max_p_coll", 0.5)),
        retreat_step_m=float(safety.get("retreat_step_m", 0.3)),
    )


def shield_spec_summary(cfg: Dict[str, Any]) -> Dict[str, Any]:
    safety = indoor_safety_cfg(cfg)
    zone = ThreeZoneSpec.from_mapping(safety)
    return {
        "kind": safety.get("kind", "three_zone"),
        **{k: getattr(zone, k) for k in (
            "l1_m", "l2_m", "l3_m", "v1_m_s", "v2_m_s", "v_stop_m_s", "v_cruise_m_s",
        )},
        "retreat_step_m": float(safety.get("retreat_step_m", 0.3)),
        "min_tau_s": float(safety.get("min_tau_s", 0.5)),
    }
