"""Time-to-contact (τ) predictor — V1b [1d].

Phase 1 (``kind=gt_proxy``): GT depth + closing-velocity → τ = d_fwd / v_close.
  Independent of ``depth_min_pred`` / D̂ trigger path. **Not** merge-eligible.

Phase 2 (``kind=foe`` / ``foe_calibrated``): optical-flow FOE + divergence → τ.
  **No GT depth at inference** (pure-vision design §4.1d). Pseudo-labels from
  Phase-1 GT τ are allowed only for training the optional calibrator head.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional, Tuple

import numpy as np

from experiments.aerial.rl.depth_geometry import forward_min_depth
from experiments.aerial.rl.env.obs import Observation

DEFAULT_MIN_CLOSING_M_S = 0.05
DEFAULT_MAX_TAU_S = 60.0
DEFAULT_MIN_RADIAL_FLOW = 0.05  # px / frame
DEFAULT_FLOW_LEVELS = 3
DEFAULT_FLOW_WINSZ = 15


def closing_speed_m_s(obs: Observation) -> float:
    """Body-forward closing speed (m/s) from world velocity and yaw."""
    st = np.asarray(obs.state, dtype=np.float64).reshape(-1)
    vx, vy, yaw = float(st[3]), float(st[4]), float(st[6])
    fx, fy = float(np.cos(yaw)), float(np.sin(yaw))
    v_fwd = vx * fx + vy * fy
    return max(v_fwd, 0.0)


def gt_tau_from_depth_velocity(
    depth: np.ndarray,
    obs: Observation,
    *,
    center_frac: float = 0.5,
    min_closing_m_s: float = DEFAULT_MIN_CLOSING_M_S,
    max_tau_s: float = DEFAULT_MAX_TAU_S,
) -> Optional[float]:
    """Supervision / sim-only τ from GT depth + proprio (m/s → s)."""
    d_fwd = forward_min_depth(depth, center_frac=center_frac)
    if not np.isfinite(d_fwd) or d_fwd <= 0:
        return None
    v = closing_speed_m_s(obs)
    if v < min_closing_m_s:
        return max_tau_s
    return float(min(d_fwd / v, max_tau_s))


def _to_gray_u8(rgb: np.ndarray) -> np.ndarray:
    img = np.asarray(rgb)
    if img.ndim == 2:
        return img.astype(np.uint8, copy=False)
    if img.shape[-1] == 1:
        return img[..., 0].astype(np.uint8, copy=False)
    # RGB → luma (OpenCV BGR expects swap; we stay RGB-weighted).
    r = img[..., 0].astype(np.float32)
    g = img[..., 1].astype(np.float32)
    b = img[..., 2].astype(np.float32)
    gray = 0.299 * r + 0.587 * g + 0.114 * b
    return np.clip(gray, 0, 255).astype(np.uint8)


def optical_flow_farneback(
    prev_rgb: np.ndarray,
    curr_rgb: np.ndarray,
    *,
    levels: int = DEFAULT_FLOW_LEVELS,
    winsize: int = DEFAULT_FLOW_WINSZ,
) -> np.ndarray:
    """Dense Farneback flow ``[H,W,2]`` (u right, v down), prev → curr."""
    import cv2

    prev = _to_gray_u8(prev_rgb)
    curr = _to_gray_u8(curr_rgb)
    if prev.shape != curr.shape:
        curr = cv2.resize(curr, (prev.shape[1], prev.shape[0]), interpolation=cv2.INTER_AREA)
    flow = cv2.calcOpticalFlowFarneback(
        prev,
        curr,
        None,
        pyr_scale=0.5,
        levels=int(levels),
        winsize=int(winsize),
        iterations=3,
        poly_n=5,
        poly_sigma=1.2,
        flags=0,
    )
    return np.asarray(flow, dtype=np.float32)


def estimate_foe(flow: np.ndarray, *, sample_stride: int = 4) -> Tuple[float, float]:
    """Least-squares FOE from flow line intersections (sparse subsample).

    Each flow vector at ``(x,y)`` with ``(u,v)`` defines a line; FOE is the
    point that minimises perpendicular distance to those lines. Falls back to
    image centre when the system is ill-conditioned (near-static frames).
    """
    f = np.asarray(flow, dtype=np.float64)
    h, w = f.shape[:2]
    ys, xs = np.mgrid[0:h:sample_stride, 0:w:sample_stride]
    u = f[ys, xs, 0].reshape(-1)
    v = f[ys, xs, 1].reshape(-1)
    x = xs.reshape(-1).astype(np.float64)
    y = ys.reshape(-1).astype(np.float64)
    mag = np.hypot(u, v)
    keep = mag > DEFAULT_MIN_RADIAL_FLOW
    if int(np.count_nonzero(keep)) < 16:
        return float(w - 1) * 0.5, float(h - 1) * 0.5
    x, y, u, v = x[keep], y[keep], u[keep], v[keep]
    # Line: (X - x) * v - (Y - y) * u = 0  →  v X - u Y = v x - u y
    a = np.stack([v, -u], axis=1)
    b = v * x - u * y
    try:
        sol, *_ = np.linalg.lstsq(a, b, rcond=None)
        foe_x, foe_y = float(sol[0]), float(sol[1])
    except np.linalg.LinAlgError:
        return float(w - 1) * 0.5, float(h - 1) * 0.5
    if not (np.isfinite(foe_x) and np.isfinite(foe_y)):
        return float(w - 1) * 0.5, float(h - 1) * 0.5
    # Soft clamp: FOE usually near frame; wild outliers → centre.
    if foe_x < -0.5 * w or foe_x > 1.5 * w or foe_y < -0.5 * h or foe_y > 1.5 * h:
        return float(w - 1) * 0.5, float(h - 1) * 0.5
    return foe_x, foe_y


def flow_divergence(flow: np.ndarray) -> np.ndarray:
    """Central-difference divergence ``∂u/∂x + ∂v/∂y`` (px/frame per px)."""
    f = np.asarray(flow, dtype=np.float64)
    u, v = f[..., 0], f[..., 1]
    du_dx = np.gradient(u, axis=1)
    dv_dy = np.gradient(v, axis=0)
    return du_dx + dv_dy


def tau_from_foe_flow(
    flow: np.ndarray,
    *,
    foe: Optional[Tuple[float, float]] = None,
    center_frac: float = 0.5,
    dt_s: float = 1.0,
    max_tau_s: float = DEFAULT_MAX_TAU_S,
    min_radial_flow: float = DEFAULT_MIN_RADIAL_FLOW,
) -> Optional[float]:
    """τ from radial expansion about FOE (frames → seconds via ``dt_s``).

    For approach to a frontal surface, flow ≈ ``(p - FOE) / τ_frames``, so
    ``τ_frames = r / v_radial`` and ``τ_s = τ_frames * dt_s``. Also cross-checks
    centre-band divergence (``τ ≈ 2 / div`` in 2-D expansion). Returns median
    of finite estimates, or ``None`` if no expansion evidence.
    """
    f = np.asarray(flow, dtype=np.float64)
    h, w = f.shape[:2]
    if foe is None:
        foe = estimate_foe(f)
    foe_x, foe_y = float(foe[0]), float(foe[1])
    cf = float(np.clip(center_frac, 0.05, 1.0))
    dh, dw = max(int(h * cf), 1), max(int(w * cf), 1)
    r0, c0 = (h - dh) // 2, (w - dw) // 2
    ys, xs = np.mgrid[r0 : r0 + dh, c0 : c0 + dw]
    u = f[ys, xs, 0]
    v = f[ys, xs, 1]
    dx = xs.astype(np.float64) - foe_x
    dy = ys.astype(np.float64) - foe_y
    r = np.hypot(dx, dy)
    # Radial component of flow (positive = expansion away from FOE).
    vr = (dx * u + dy * v) / np.maximum(r, 1e-6)
    valid = (r > 2.0) & (vr > min_radial_flow)
    taus: List[float] = []
    if np.any(valid):
        tau_frames = r[valid] / vr[valid]
        taus.extend(tau_frames[np.isfinite(tau_frames)].tolist())

    div = flow_divergence(f)[r0 : r0 + dh, c0 : c0 + dw]
    pos = div[div > 1e-4]
    if pos.size:
        # 2-D pure expansion: div = 2 / τ_frames.
        taus.extend((2.0 / pos).tolist())

    if not taus:
        return None
    tau_frames_med = float(np.median(np.asarray(taus, dtype=np.float64)))
    if not np.isfinite(tau_frames_med) or tau_frames_med <= 0:
        return None
    dt = max(float(dt_s), 1e-3)
    return float(min(tau_frames_med * dt, max_tau_s))


def foe_flow_features(
    flow: np.ndarray,
    *,
    foe: Optional[Tuple[float, float]] = None,
    center_frac: float = 0.5,
) -> np.ndarray:
    """Compact features for the optional calibrator MLP ``[8]``."""
    f = np.asarray(flow, dtype=np.float64)
    h, w = f.shape[:2]
    if foe is None:
        foe = estimate_foe(f)
    foe_x, foe_y = float(foe[0]), float(foe[1])
    cf = float(np.clip(center_frac, 0.05, 1.0))
    dh, dw = max(int(h * cf), 1), max(int(w * cf), 1)
    r0, c0 = (h - dh) // 2, (w - dw) // 2
    crop = f[r0 : r0 + dh, c0 : c0 + dw]
    mag = np.hypot(crop[..., 0], crop[..., 1])
    div = flow_divergence(f)[r0 : r0 + dh, c0 : c0 + dw]
    tau_raw = tau_from_foe_flow(f, foe=foe, center_frac=center_frac, dt_s=1.0)
    feats = np.array(
        [
            foe_x / max(w - 1, 1),
            foe_y / max(h - 1, 1),
            float(np.median(mag)) if mag.size else 0.0,
            float(np.percentile(mag, 90)) if mag.size else 0.0,
            float(np.median(div)) if div.size else 0.0,
            float(np.mean(div > 0)) if div.size else 0.0,
            float(tau_raw) if tau_raw is not None else DEFAULT_MAX_TAU_S,
            float(np.log1p(tau_raw)) if tau_raw is not None else np.log1p(DEFAULT_MAX_TAU_S),
        ],
        dtype=np.float32,
    )
    return feats


class FoeTauCalibrator:
    """Tiny MLP: FOE features → calibrated τ (seconds). Lazy-torch."""

    def __init__(self, *, device: str = "cpu") -> None:
        self.device = device
        self._model: Any = None

    @staticmethod
    def build_module() -> Any:
        import torch.nn as nn

        return nn.Sequential(
            nn.Linear(8, 32),
            nn.ReLU(inplace=True),
            nn.Linear(32, 32),
            nn.ReLU(inplace=True),
            nn.Linear(32, 1),
            nn.Softplus(),
        )

    @classmethod
    def from_checkpoint(cls, path: Path | str, *, device: str = "cpu") -> "FoeTauCalibrator":
        import torch

        payload = torch.load(str(path), map_location="cpu")
        model = cls.build_module()
        model.load_state_dict(payload["model"], strict=True)
        model.to(device)
        model.eval()
        out = cls(device=device)
        out._model = model
        return out

    def predict(self, feats: np.ndarray, *, max_tau_s: float = DEFAULT_MAX_TAU_S) -> float:
        if self._model is None:
            raise RuntimeError("FoeTauCalibrator has no weights; call from_checkpoint")
        import torch

        x = torch.from_numpy(np.asarray(feats, dtype=np.float32).reshape(1, -1)).to(self.device)
        with torch.no_grad():
            y = float(self._model(x).reshape(-1)[0].item())
        return float(min(max(y, 1e-3), max_tau_s))


@dataclass
class TauPredictor:
    """Populate ``obs.info['tau_pred']`` for the τ leg of ``DepthTauShield``.

    ``kind``:
      * ``gt_proxy`` — Phase 1 (needs ``obs.depth``); not authoritative.
      * ``foe`` — Phase 2 classical FOE divergence (RGB pair only).
      * ``foe_calibrated`` — Phase 2 FOE + optional MLP calibrator ckpt.
    """

    kind: str = "gt_proxy"
    center_frac: float = 0.5
    min_closing_m_s: float = DEFAULT_MIN_CLOSING_M_S
    max_tau_s: float = DEFAULT_MAX_TAU_S
    use_gt_depth: bool = True  # legacy; overridden by kind when set
    dt_s: float = 0.1  # default collect rate ~10 Hz; overridden by obs.t delta
    calibrator: Optional[FoeTauCalibrator] = None
    _prev_rgb: Optional[np.ndarray] = field(default=None, repr=False)
    _prev_t: Optional[float] = field(default=None, repr=False)
    # Last |flow| mean in the forward cone (diagnostic only; not consumed by shield).
    _last_flow_mag: Optional[float] = field(default=None, repr=False)

    def reset(self) -> None:
        self._prev_rgb = None
        self._prev_t = None
        self._last_flow_mag = None

    def _resolved_kind(self) -> str:
        k = str(self.kind or "gt_proxy").lower()
        if k in ("gt", "proxy", "gt_proxy"):
            return "gt_proxy"
        if k in ("foe", "optical_flow", "flow"):
            return "foe"
        if k in ("foe_calibrated", "foe_cal", "calibrated"):
            return "foe_calibrated"
        return k

    def predict_tau(self, obs: Observation) -> Optional[float]:
        kind = self._resolved_kind()
        if kind == "gt_proxy":
            if not self.use_gt_depth or obs.depth is None:
                return None
            return gt_tau_from_depth_velocity(
                obs.depth,
                obs,
                center_frac=self.center_frac,
                min_closing_m_s=self.min_closing_m_s,
                max_tau_s=self.max_tau_s,
            )
        return self._predict_foe(obs, calibrated=(kind == "foe_calibrated"))

    def _predict_foe(self, obs: Observation, *, calibrated: bool) -> Optional[float]:
        rgb = np.asarray(obs.rgb)
        t = float(obs.t)
        prev = self._prev_rgb
        prev_t = self._prev_t
        self._prev_rgb = rgb.copy()
        self._prev_t = t
        if prev is None:
            return None
        dt = self.dt_s
        if prev_t is not None and np.isfinite(t) and np.isfinite(prev_t) and t > prev_t:
            dt = float(t - prev_t)
        flow = optical_flow_farneback(prev, rgb)
        # Cheap T-3 proxy: mean |flow| over forward cone (no second Farneback).
        try:
            h, w = int(flow.shape[0]), int(flow.shape[1])
            cf = float(np.clip(self.center_frac, 0.05, 1.0))
            ch, cw = max(1, int(round(h * cf))), max(1, int(round(w * cf)))
            y0, x0 = (h - ch) // 2, (w - cw) // 2
            crop = flow[y0 : y0 + ch, x0 : x0 + cw]
            self._last_flow_mag = float(np.mean(np.linalg.norm(crop, axis=-1)))
        except Exception:  # noqa: BLE001 — diagnostic best-effort
            self._last_flow_mag = None
        foe = estimate_foe(flow)
        if calibrated and self.calibrator is not None:
            feats = foe_flow_features(flow, foe=foe, center_frac=self.center_frac)
            # Features use τ in *frames*; fold dt into Softplus output scale.
            tau_frames = self.calibrator.predict(feats, max_tau_s=self.max_tau_s / max(dt, 1e-3))
            return float(min(tau_frames * max(dt, 1e-3), self.max_tau_s))
        return tau_from_foe_flow(
            flow,
            foe=foe,
            center_frac=self.center_frac,
            dt_s=dt,
            max_tau_s=self.max_tau_s,
        )


def make_tau_predictor(
    *,
    kind: str = "gt_proxy",
    center_frac: float = 0.5,
    min_closing_m_s: float = DEFAULT_MIN_CLOSING_M_S,
    max_tau_s: float = DEFAULT_MAX_TAU_S,
    use_gt_depth: bool = True,
    dt_s: float = 0.1,
    ckpt: Optional[Path | str] = None,
    device: str = "cpu",
) -> TauPredictor:
    """Factory used by ``train_rl`` / gate scripts."""
    k = str(kind).lower()
    if k in ("gt", "proxy"):
        k = "gt_proxy"
    cal = None
    if ckpt is not None and k in ("foe_calibrated", "foe_cal", "calibrated", "foe"):
        cal = FoeTauCalibrator.from_checkpoint(ckpt, device=device)
        if k == "foe":
            k = "foe_calibrated"
    return TauPredictor(
        kind=k,
        center_frac=center_frac,
        min_closing_m_s=min_closing_m_s,
        max_tau_s=max_tau_s,
        use_gt_depth=use_gt_depth if k == "gt_proxy" else False,
        dt_s=dt_s,
        calibrator=cal,
    )
