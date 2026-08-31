"""Hard safety shield (spec §2#6, §4.5) — interface + null stub.

The shield sits ABOVE the learned policy: if inflated predicted depth ``D̂``,
time-to-contact ``τ``, or world-model collision probability ``p_coll`` breaches a
threshold, it overrides the policy's action with a conservative one (brake /
hover / retreat). It is a *hard* override, not a learned behaviour — so it lives
outside the RL graph.

Only the contract is fixed here. ``NullSafetyShield`` never overrides (V0/V1
default). A real ``DepthTauShield`` is deferred until the perception heads that
produce ``D̂`` / ``τ`` exist (V2+); ``ThresholdSafetyShield`` shows the intended
trigger wiring against fields that may not be populated yet.

**Three-zone deploy (2026-08-23)**: ``ThreeZoneSpeedShield`` replaces the single
3 m depth latch with a graduated speed governor (8/5/1.5 m @ 2/1/0.2 m/s).
τ / p_coll emergencies still latch + retreat.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Protocol, runtime_checkable

import numpy as np

from experiments.aerial.rl.env.action import MAX_BODY_VELOCITY, clip_body_delta
from experiments.aerial.rl.env.obs import Observation
from experiments.aerial.rl.three_zone import ThreeZoneSpec, planned_speed_m_s
from experiments.aerial.rl.tau_predictor import (
    DEFAULT_MIN_CLOSING_M_S,
    closing_speed_m_s,
)


@runtime_checkable
class SafetyShield(Protocol):
    def should_override(self, obs: Observation, wm_out: Optional[Any] = None) -> bool: ...

    def override_action(self, obs: Observation) -> np.ndarray: ...


class NullSafetyShield:
    """No-op shield: never intervenes. Default until D̂/τ heads exist."""

    def should_override(self, obs: Observation, wm_out: Optional[Any] = None) -> bool:
        return False

    def override_action(self, obs: Observation) -> np.ndarray:
        return np.zeros(4, dtype=np.float64)

    def apply_action(
        self,
        action: np.ndarray,
        obs: Observation,
        wm_out: Optional[Any] = None,
        limits: Optional[np.ndarray] = None,
    ) -> tuple[np.ndarray, bool]:
        lim = limits
        return clip_body_delta(action, lim), False


@dataclass
class ThresholdSafetyShield:
    """Trigger contract for D̂ ∪ τ ∪ p_coll (fields wired at V2+).

    **Standoff semantics (v5, 2026-08-22)** — ``min_depth_m`` is the boundary of
    the *stable-hover zone*, not the distance at which braking *starts*. The
    vehicle must bleed closing speed **before** crossing the standoff so it is
    near-stationary **inside** ``min_depth_m``. Kinematic engage when::

        D̂ < min_depth_m + v_fwd * min_tau_s

    (same ``min_tau_s`` reaction budget as the τ leg; thresholds unchanged).

    Override uses **graduated body −x** scaled to ``v_fwd`` (capped by
    ``retreat_step_m``), including while still **outside** the standoff but
    inside the braking envelope — not a step function at 3 m.

    Prior latch + bounded retreat history (晚¹⁰–¹²) remains; v5 fixes the
    high-speed “coast into 3 m then panic” failure mode.

    **Legacy** — superseded for deploy by :class:`ThreeZoneSpeedShield`.
    """

    # Reaction standoff outer boundary — must be stable/hovering inside, not enter at cruise.
    min_depth_m: float = 3.0
    min_tau_s: float = 1.0            # τ breach + kinematic depth braking horizon (s)
    max_p_coll: float = 0.5           # brake if WM collision prob > this
    min_closing_m_s: float = DEFAULT_MIN_CLOSING_M_S
    brake_gain: float = 1.0           # retreat dx ≈ v_fwd * brake_gain per step (then clipped)
    retreat_step_m: float = 3.0       # max |body −x| per override step
    _engaged: bool = field(default=False, init=False, repr=False)

    def reset(self) -> None:
        """Clear the per-episode latch (the shield instance is reused across episodes)."""
        self._engaged = False

    def _kinematic_standoff_limit_m(self, v_fwd: float) -> float:
        """Outer engage surface: standoff + distance closed in ``min_tau_s`` at ``v_fwd``."""
        return float(self.min_depth_m) + max(float(v_fwd), 0.0) * float(self.min_tau_s)

    def _depth_channel_breach(self, d_hat: float, v_fwd: float) -> bool:
        d = float(d_hat)
        if d < float(self.min_depth_m):
            return True
        if v_fwd > float(self.min_closing_m_s):
            return d < self._kinematic_standoff_limit_m(v_fwd)
        return False

    def _needs_speed_bleed(self, obs: Observation) -> bool:
        d_hat = obs.info.get("depth_min_pred")
        if d_hat is None:
            return False
        v = closing_speed_m_s(obs)
        return self._depth_channel_breach(float(d_hat), v)

    def _breached(self, obs: Observation, wm_out: Optional[Any] = None) -> bool:
        d_hat = obs.info.get("depth_min_pred")
        tau = obs.info.get("tau_pred")
        p_coll = None
        if wm_out is not None:
            p_coll = getattr(wm_out, "p_coll", None)
        if d_hat is not None and self._depth_channel_breach(
            float(d_hat), closing_speed_m_s(obs)
        ):
            return True
        if tau is not None and float(tau) < self.min_tau_s:
            return True
        if p_coll is not None and float(p_coll) > self.max_p_coll:
            return True
        return False

    def should_override(self, obs: Observation, wm_out: Optional[Any] = None) -> bool:
        if self._engaged:
            return True
        if self._breached(obs, wm_out):
            self._engaged = True
            return True
        return False

    def override_action(self, obs: Observation) -> np.ndarray:
        if not self._needs_speed_bleed(obs):
            return np.zeros(4, dtype=np.float64)
        v = closing_speed_m_s(obs)
        # Graduated −x: bleed closing speed before/at standoff; collector clips to rate cap.
        mag = min(
            float(self.retreat_step_m),
            max(float(v), float(self.min_closing_m_s)) * float(self.brake_gain),
        )
        return np.array([-abs(mag), 0.0, 0.0, 0.0], dtype=np.float64)

    def apply_action(
        self,
        action: np.ndarray,
        obs: Observation,
        wm_out: Optional[Any] = None,
        limits: Optional[np.ndarray] = None,
    ) -> tuple[np.ndarray, bool]:
        if self.should_override(obs, wm_out):
            return clip_body_delta(self.override_action(obs), limits), True
        return clip_body_delta(action, limits), False


@dataclass
class DepthTauShield(ThresholdSafetyShield):
    """τ/D̂ dual-channel hard shield (frozen spec V1).

    Same trigger/override contract as :class:`ThresholdSafetyShield`, but records
    which independent channel(s) breached for V1-③ diagnostics. Writes
    ``obs.info['shield_channels']`` on the step the latch engages.

    **Legacy** — deploy uses :class:`ThreeZoneSpeedShield`.
    """

    _last_channels: tuple[str, ...] = field(default=(), init=False, repr=False)

    @property
    def last_channels(self) -> tuple[str, ...]:
        return self._last_channels

    def reset(self) -> None:
        super().reset()
        self._last_channels = ()

    def _channels_breached(self, obs: Observation, wm_out: Optional[Any] = None) -> tuple[str, ...]:
        out: list[str] = []
        d_hat = obs.info.get("depth_min_pred")
        tau = obs.info.get("tau_pred")
        p_coll = None
        if wm_out is not None:
            p_coll = getattr(wm_out, "p_coll", None)
        if d_hat is not None and self._depth_channel_breach(
            float(d_hat), closing_speed_m_s(obs)
        ):
            out.append("depth")
        if tau is not None and float(tau) < self.min_tau_s:
            out.append("tau")
        if p_coll is not None and float(p_coll) > self.max_p_coll:
            out.append("p_coll")
        return tuple(out)

    def should_override(self, obs: Observation, wm_out: Optional[Any] = None) -> bool:
        if self._engaged:
            return True
        channels = self._channels_breached(obs, wm_out)
        if channels:
            self._engaged = True
            self._last_channels = channels
            obs.info["shield_channels"] = list(channels)
            return True
        return False


@dataclass
class ThreeZoneSpeedShield:
    """Graduated speed governor from ``D̂_fwd`` + τ/p_coll emergency latch.

  * **Depth**: cap body +x to ``planned_speed(D̂) * dt`` — **no episode latch**.
  * **τ / p_coll**: latch + graduated −x retreat (same as v5 threshold shield).

  Default zones: **8 / 5 / 1.5 m @ 2 / 1 / 0.2 m/s**, cruise 5 m/s,
  engage ≈ **12.2 m** — replaces the problematic single **3 m** depth trigger.
    """

    zone: ThreeZoneSpec = field(default_factory=ThreeZoneSpec)
    min_tau_s: float = 1.0
    max_p_coll: float = 0.5
    min_closing_m_s: float = DEFAULT_MIN_CLOSING_M_S
    brake_gain: float = 1.0
    retreat_step_m: float = 3.0
    _emergency_engaged: bool = field(default=False, init=False, repr=False)
    _last_channels: tuple[str, ...] = field(default=(), init=False, repr=False)

    @property
    def last_channels(self) -> tuple[str, ...]:
        return self._last_channels

    def reset(self) -> None:
        self._emergency_engaged = False
        self._last_channels = ()

    def _emergency_channels(self, obs: Observation, wm_out: Optional[Any] = None) -> tuple[str, ...]:
        out: list[str] = []
        tau = obs.info.get("tau_pred")
        p_coll = None
        if wm_out is not None:
            p_coll = getattr(wm_out, "p_coll", None)
        if tau is not None and float(tau) < self.min_tau_s:
            out.append("tau")
        if p_coll is not None and float(p_coll) > self.max_p_coll:
            out.append("p_coll")
        return tuple(out)

    def _emergency_override(self, obs: Observation) -> np.ndarray:
        v = closing_speed_m_s(obs)
        mag = min(
            float(self.retreat_step_m),
            max(float(v), float(self.min_closing_m_s)) * float(self.brake_gain),
        )
        return np.array([-abs(mag), 0.0, 0.0, 0.0], dtype=np.float64)

    def _dt_from_limits(self, limits: Optional[np.ndarray]) -> float:
        """Convert speed caps → per-step body deltas.

        Prefer ``limits[0] / zone.v_cruise_m_s`` so cruise ``max_dx == limits[0]``.
        Do not divide indoor micro-limits by outdoor MAX_BODY_VELOCITY (E2i diag).
        """
        dt_zone = float(self.zone.dt_s)
        if limits is None or float(limits[0]) <= 0:
            return dt_zone
        v_ref = float(self.zone.v_cruise_m_s)
        if v_ref <= 1e-9:
            return dt_zone
        return float(limits[0]) / v_ref

    def _cap_forward(self, action: np.ndarray, obs: Observation, limits: Optional[np.ndarray]) -> tuple[np.ndarray, bool]:
        d_hat = obs.info.get("depth_min_pred")
        if d_hat is None:
            return action, False
        v_cap = planned_speed_m_s(float(d_hat), self.zone)
        obs.info["three_zone_speed_cap_m_s"] = round(v_cap, 4)
        dt = self._dt_from_limits(limits)
        max_dx = v_cap * dt
        capped = np.asarray(action, dtype=np.float64).reshape(4).copy()
        if capped[0] > max_dx + 1e-6:
            capped[0] = max_dx
            return capped, True
        return capped, False

    def apply_action(
        self,
        action: np.ndarray,
        obs: Observation,
        wm_out: Optional[Any] = None,
        limits: Optional[np.ndarray] = None,
    ) -> tuple[np.ndarray, bool]:
        action = np.asarray(action, dtype=np.float64).reshape(4)
        if self._emergency_engaged:
            return clip_body_delta(self._emergency_override(obs), limits), True
        channels = self._emergency_channels(obs, wm_out)
        if channels:
            self._emergency_engaged = True
            self._last_channels = channels
            obs.info["shield_channels"] = list(channels)
            return clip_body_delta(self._emergency_override(obs), limits), True

        capped, changed = self._cap_forward(action, obs, limits)
        if changed:
            ch = list(obs.info.get("shield_channels") or [])
            if "three_zone" not in ch:
                ch.append("three_zone")
            obs.info["shield_channels"] = ch
        return clip_body_delta(capped, limits), changed

    def should_override(self, obs: Observation, wm_out: Optional[Any] = None) -> bool:
        """Backward-compat: true only for τ/p_coll emergency latch."""
        if self._emergency_engaged:
            return True
        return bool(self._emergency_channels(obs, wm_out))

    def override_action(self, obs: Observation) -> np.ndarray:
        return self._emergency_override(obs)
