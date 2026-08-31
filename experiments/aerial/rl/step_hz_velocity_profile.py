"""5 Hz closed-loop velocity profile on AirSim (or mock for CI).

Measures achieved step rate and realized body-forward velocity when commanding
max-forward / coast / max-reverse body deltas at ``step_hz``. Intended to
calibrate ``a_max`` for three-zone kinematic budgets (RUNBOOK §4-1, declare #28).

    # 4090 loopback (after: source experiments/aerial/scripts/env_4090.sh)
    python -m experiments.aerial.rl.step_hz_velocity_profile \\
        --backend airsim --step-hz 5 --grab-depth \\
        --emit artifacts/step_hz_profile_5hz_depth_20260823.json

``authoritative=false`` until shield-on path is also measured.
"""
from __future__ import annotations

import argparse
import json
import math
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from experiments.aerial.rl.env.action import body_delta_limits


@dataclass(frozen=True)
class PhaseSpec:
    name: str
    action: Tuple[float, float, float, float]
    n_steps: int


DEFAULT_PHASES = (
    PhaseSpec("accel", (1.0, 0.0, 0.0, 0.0), 15),
    PhaseSpec("cruise", (1.0, 0.0, 0.0, 0.0), 10),
    PhaseSpec("coast", (0.0, 0.0, 0.0, 0.0), 20),
    PhaseSpec("brake", (-1.0, 0.0, 0.0, 0.0), 15),
)


def body_fwd_velocity(state: np.ndarray) -> float:
    """Body-frame forward speed (m/s) from ``observe_state`` 7-vector."""
    s = np.asarray(state, dtype=np.float64).reshape(-1)
    vx, vy, yaw = float(s[3]), float(s[4]), float(s[6])
    c, sn = math.cos(yaw), math.sin(yaw)
    return c * vx + sn * vy


def summarize_steps(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    if not rows:
        return {"n": 0}
    wall = np.array([r["wall_dt_s"] for r in rows], dtype=np.float64)
    vfwd = np.array([r["v_fwd_m_s"] for r in rows], dtype=np.float64)
    cmd = np.array([r["cmd_fwd_m"] for r in rows], dtype=np.float64)
    achieved = np.array([r["achieved_fwd_m"] for r in rows], dtype=np.float64)

    hz = 1.0 / wall[wall > 0] if np.any(wall > 0) else np.array([0.0])
    accel = np.diff(vfwd) / np.maximum(wall[1:], 1e-6)

    def _phase_slice(name: str) -> np.ndarray:
        idx = [i for i, r in enumerate(rows) if r["phase"] == name]
        return vfwd[idx] if idx else np.array([], dtype=np.float64)

    cruise = _phase_slice("cruise")
    coast = _phase_slice("coast")
    brake = _phase_slice("brake")

    coast_decel = []
    for i in range(1, len(rows)):
        if rows[i]["phase"] != "coast" or rows[i - 1]["phase"] != "coast":
            continue
        dt = rows[i]["wall_dt_s"]
        if dt > 0:
            coast_decel.append((rows[i - 1]["v_fwd_m_s"] - rows[i]["v_fwd_m_s"]) / dt)

    brake_decel = []
    for i in range(1, len(rows)):
        if rows[i]["phase"] != "brake" or rows[i - 1]["phase"] != "brake":
            continue
        dt = rows[i]["wall_dt_s"]
        if dt > 0:
            brake_decel.append((rows[i - 1]["v_fwd_m_s"] - rows[i]["v_fwd_m_s"]) / dt)

    return {
        "n_steps": len(rows),
        "wall_dt_median_s": round(float(np.median(wall)), 4),
        "wall_dt_p90_s": round(float(np.percentile(wall, 90)), 4),
        "achieved_hz_median": round(float(np.median(hz)), 3),
        "achieved_hz_p10": round(float(np.percentile(hz, 10)), 3),
        "v_fwd_max_m_s": round(float(np.max(vfwd)), 3),
        "v_fwd_cruise_median_m_s": round(float(np.median(cruise)), 3) if cruise.size else None,
        "v_fwd_coast_end_m_s": round(float(coast[-1]), 3) if coast.size else None,
        "cmd_fwd_max_m": round(float(np.max(cmd)), 4),
        "achieved_fwd_max_m": round(float(np.max(achieved)), 4),
        "tracking_ratio_median": round(
            float(np.median(achieved[cmd > 1e-6] / np.maximum(cmd[cmd > 1e-6], 1e-6))),
            3,
        )
        if np.any(cmd > 1e-6)
        else None,
        "accel_phase_peak_m_s2": round(float(np.max(accel)), 3) if accel.size else None,
        "coast_decel_median_m_s2": round(float(np.median(coast_decel)), 3) if coast_decel else None,
        "coast_decel_p90_m_s2": round(float(np.percentile(coast_decel, 90)), 3) if coast_decel else None,
        "brake_decel_median_m_s2": round(float(np.median(brake_decel)), 3) if brake_decel else None,
        "brake_decel_p90_m_s2": round(float(np.percentile(brake_decel, 90)), 3) if brake_decel else None,
        "a_max_recommend_m_s2": round(
            float(max(
                np.percentile(brake_decel, 90) if brake_decel else 0.0,
                np.percentile(coast_decel, 90) if coast_decel else 0.0,
            )),
            3,
        ),
    }


def run_profile(
    env: Any,
    *,
    phases: Sequence[PhaseSpec] = DEFAULT_PHASES,
    step_hz: float = 5.0,
    shield: Optional[Any] = None,
    inject_gt_depth_pred: bool = False,
) -> Dict[str, Any]:
    from experiments.aerial.rl.depth_geometry import forward_min_depth

    dt_nom = 1.0 / float(step_hz)
    limits = body_delta_limits(dt_nom)
    last_obs = env.reset()
    rows: List[Dict[str, Any]] = []
    prev_pos: Optional[np.ndarray] = None

    for phase in phases:
        action = np.array(phase.action, dtype=np.float64)
        action = np.clip(action * limits, -limits, limits)
        for _ in range(phase.n_steps):
            t0 = time.perf_counter()
            state_before = env.observe_state()
            pos_before = np.asarray(state_before[:3], dtype=np.float64)
            raw_action = action.copy()
            if shield is not None:
                obs = last_obs if last_obs is not None else env.observe()
                if inject_gt_depth_pred:
                    depth = getattr(obs, "depth", None)
                    if depth is not None:
                        dmin = forward_min_depth(np.asarray(depth, dtype=np.float64), center_frac=0.5)
                        obs.info = dict(obs.info or {})
                        obs.info["depth_min_pred"] = float(dmin)
                raw_action, _ = shield.apply_action(raw_action, obs, limits=limits)
            obs, info = env.step(raw_action)
            last_obs = obs
            wall = time.perf_counter() - t0
            state_after = env.observe_state()
            pos_after = np.asarray(state_after[:3], dtype=np.float64)
            delta = pos_after - (prev_pos if prev_pos is not None else pos_before)
            yaw = float(state_after[6])
            c, sn = math.cos(yaw), math.sin(yaw)
            achieved_fwd = c * delta[0] + sn * delta[1]
            rows.append(
                {
                    "phase": phase.name,
                    "wall_dt_s": round(wall, 5),
                    "v_fwd_m_s": round(body_fwd_velocity(state_after), 4),
                    "cmd_fwd_m": round(float(raw_action[0]), 4),
                    "achieved_fwd_m": round(float(achieved_fwd), 4),
                    "cmd_vel_m_s": round(float(raw_action[0]) / dt_nom, 4),
                }
            )
            prev_pos = pos_after.copy()

    summary = summarize_steps(rows)
    return {
        "step_hz_commanded": float(step_hz),
        "dt_nominal_s": dt_nom,
        "body_delta_limits": limits.tolist(),
        "phases": [asdict(p) for p in phases],
        "steps": rows,
        "summary": summary,
    }


def _make_env(backend: str, step_hz: float, grab_depth: bool) -> Any:
    if backend == "mock":
        from experiments.aerial.rl.env.mock_env import MockAirSimDroneEnv, MockEnvConfig

        return MockAirSimDroneEnv(MockEnvConfig(step_hz=step_hz))
    if backend == "airsim":
        from experiments.aerial.rl.env.airsim_env import AirSimDroneEnv, AirSimEnvConfig

        return AirSimDroneEnv(
            AirSimEnvConfig(step_hz=step_hz, grab_depth=grab_depth, health_check=True)
        )
    raise ValueError(f"unknown backend: {backend}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--backend", choices=("mock", "airsim"), default="mock")
    p.add_argument("--step-hz", type=float, default=5.0)
    p.add_argument("--grab-depth", action="store_true")
    p.add_argument(
        "--shield",
        choices=("none", "three_zone"),
        default="none",
        help="apply ThreeZoneSpeedShield (uses GT depth as D̂ when --inject-gt-depth-pred)",
    )
    p.add_argument(
        "--inject-gt-depth-pred",
        action="store_true",
        help="feed forward GT min depth as depth_min_pred each step (harness only)",
    )
    p.add_argument("--emit", type=Path, default=None)
    args = p.parse_args(argv)

    shield = None
    if args.shield == "three_zone":
        from experiments.aerial.rl.safety import ThreeZoneSpeedShield
        from experiments.aerial.rl.three_zone import ThreeZoneSpec

        shield = ThreeZoneSpeedShield(zone=ThreeZoneSpec())

    env = _make_env(args.backend, args.step_hz, args.grab_depth)
    try:
        out = run_profile(
            env,
            step_hz=args.step_hz,
            shield=shield,
            inject_gt_depth_pred=bool(args.inject_gt_depth_pred),
        )
    finally:
        env.close()

    out["meta"] = {
        "backend": args.backend,
        "grab_depth": bool(args.grab_depth),
        "shield": args.shield,
        "inject_gt_depth_pred": bool(args.inject_gt_depth_pred),
        "authoritative": False,
        "note": "shield-on uses GT D̂ proxy unless wired to depth head",
    }
    payload = json.dumps(out, indent=2)
    if args.emit:
        args.emit.parent.mkdir(parents=True, exist_ok=True)
        args.emit.write_text(payload + "\n")
        print(f"[step_hz_profile] wrote {args.emit}")
    else:
        print(payload)
    s = out["summary"]
    print(
        f"[step_hz_profile] achieved_hz={s.get('achieved_hz_median')} "
        f"v_cruise={s.get('v_fwd_cruise_median_m_s')} "
        f"a_brake_p90={s.get('brake_decel_p90_m_s2')} "
        f"a_recommend={s.get('a_max_recommend_m_s2')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
