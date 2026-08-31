"""Tests for τ predictor (Phase 1 GT proxy + Phase 2 FOE)."""
from __future__ import annotations

import numpy as np

from experiments.aerial.rl.env.obs import Observation
from experiments.aerial.rl.tau_predictor import (
    TauPredictor,
    estimate_foe,
    gt_tau_from_depth_velocity,
    optical_flow_farneback,
    tau_from_foe_flow,
)


def _obs(depth_val: float, vx: float, yaw: float = 0.0) -> Observation:
    depth = np.full((224, 224), depth_val, dtype=np.float32)
    state = np.array([0.0, 0.0, 5.0, vx, 0.0, 0.0, yaw], dtype=np.float32)
    return Observation(rgb=np.zeros((224, 224, 3), dtype=np.uint8), state=state, depth=depth)


def test_gt_tau_approaching():
    obs = _obs(3.0, vx=1.0)
    tau = gt_tau_from_depth_velocity(obs.depth, obs)
    assert tau is not None
    assert abs(tau - 3.0) < 0.01


def test_gt_tau_not_closing_returns_max():
    obs = _obs(2.0, vx=0.0)
    tau = gt_tau_from_depth_velocity(obs.depth, obs, max_tau_s=60.0)
    assert tau == 60.0


def test_predictor_fills_interface():
    pred = TauPredictor()
    obs = _obs(5.0, vx=2.5)
    tau = pred.predict_tau(obs)
    assert tau is not None and abs(tau - 2.0) < 0.01


def _zoom_pair(h: int = 64, w: int = 64, scale: float = 1.1) -> tuple[np.ndarray, np.ndarray]:
    """Synthetic expanding texture (approach): scale centre crop onto full frame."""
    import cv2

    yy, xx = np.mgrid[0:h, 0:w]
    base = ((xx * 3 + yy * 5) % 256).astype(np.uint8)
    base = cv2.GaussianBlur(base, (5, 5), 0)
    rgb0 = np.stack([base, base, base], axis=-1)
    # Zoom-in warp: points move away from centre.
    cx, cy = (w - 1) * 0.5, (h - 1) * 0.5
    map_x = (cx + (xx - cx) / scale).astype(np.float32)
    map_y = (cy + (yy - cy) / scale).astype(np.float32)
    warped = cv2.remap(base, map_x, map_y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    rgb1 = np.stack([warped, warped, warped], axis=-1)
    return rgb0, rgb1


def test_foe_tau_from_expanding_flow():
    """Pure zoom → finite positive τ; no GT depth involved."""
    rgb0, rgb1 = _zoom_pair(scale=1.08)
    flow = optical_flow_farneback(rgb0, rgb1)
    foe = estimate_foe(flow)
    # FOE near image centre for pure zoom.
    assert abs(foe[0] - 31.5) < 12.0
    assert abs(foe[1] - 31.5) < 12.0
    tau = tau_from_foe_flow(flow, foe=foe, dt_s=0.1, center_frac=0.6)
    assert tau is not None
    assert 0.05 < tau < 60.0


def test_foe_predictor_no_gt_depth():
    pred = TauPredictor(kind="foe", use_gt_depth=False, dt_s=0.1)
    rgb0, rgb1 = _zoom_pair(scale=1.1)
    state = np.array([0.0, 0.0, 5.0, 1.0, 0.0, 0.0, 0.0], dtype=np.float32)
    o0 = Observation(rgb=rgb0, state=state, depth=None, t=0.0)
    o1 = Observation(rgb=rgb1, state=state, depth=None, t=0.1)
    assert pred.predict_tau(o0) is None  # warm-up
    tau = pred.predict_tau(o1)
    assert tau is not None and tau > 0


def test_gt_proxy_refuses_without_depth_when_disabled():
    pred = TauPredictor(kind="gt_proxy", use_gt_depth=False)
    obs = _obs(3.0, vx=1.0)
    assert pred.predict_tau(obs) is None
