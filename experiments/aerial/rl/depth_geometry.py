"""Shared depth-map geometry for forward cones and directional clearances.

Row/col semantics match :func:`min_depth_pixel_loc` (and the ④ contact dumps):
``(0, 0)`` = top-left; ``row`` increases downward; ``col`` increases rightward.
``col`` near 0/1 ⇒ lateral edges; ``row`` near 1 ⇒ ground below.

Used by the depth predictor (P0a ``predict_cones``), V0 rollout eval / gate
forensics, and depth-vs-GT diagnostics — one definition, no drift.
"""
from __future__ import annotations

from typing import Dict, Optional

import numpy as np

# Canonical keys returned by :func:`cone_clearances` / ``predict_cones``.
CONE_KEYS = ("forward", "left", "right", "up", "down")


def _min_finite_positive(region: np.ndarray) -> float:
    finite = np.asarray(region, dtype=np.float64)
    finite = finite[np.isfinite(finite) & (finite > 0)]
    return float(np.min(finite)) if finite.size else float("inf")


def forward_min_depth(depth: np.ndarray, *, center_frac: float) -> float:
    """Min finite+positive depth over the central ``center_frac`` box (forward).

    The front camera faces body-forward (the episode yaw), so the image centre
    is the flight direction. Restricting the obstacle test to a centre crop is
    what makes "is there something *ahead*" distinct from "is there ground far
    below / a wall off to the side" — a full-field min at cruise altitude is
    almost always the ground, which never triggers a 1.5 m near-collision.
    """
    h, w = depth.shape[-2], depth.shape[-1]
    cf = float(np.clip(center_frac, 0.05, 1.0))
    # Match forward_min_depth_torch: at least 1 px per axis (int(h*cf) alone can be 0).
    dh, dw = max(1, int(h * cf)), max(1, int(w * cf))
    r0, c0 = (h - dh) // 2, (w - dw) // 2
    crop = np.asarray(depth[r0 : r0 + dh, c0 : c0 + dw], dtype=np.float64)
    return _min_finite_positive(crop)


def forward_min_depth_torch(
    depth, *, center_frac: float, softmin_temperature_m: float = 0.0
):
    """Batched forward-crop min — same crop as :func:`forward_min_depth`.

    ``depth``: ``[B,H,W]`` or ``[H,W]``. Non-finite / non-positive → +inf.

    ``softmin_temperature_m<=0`` → hard min (eval ⓪d / sampling).
    ``softmin_temperature_m>0`` → softmin ``-T logΣ exp(-x/T)`` over finite
    crop pixels (declare v3 A″; T frozen at 0.05 m in recipe).
    """
    import torch

    d = depth if depth.ndim == 3 else depth.unsqueeze(0)
    b, h, w = d.shape
    cf = float(max(0.05, min(1.0, center_frac)))
    dh, dw = max(1, int(h * cf)), max(1, int(w * cf))
    r0, c0 = (h - dh) // 2, (w - dw) // 2
    crop = d[:, r0 : r0 + dh, c0 : c0 + dw]
    valid = torch.isfinite(crop) & (crop > 0)
    T = float(softmin_temperature_m)
    if T <= 0.0:
        filled = crop.masked_fill(~valid, float("inf"))
        mins = filled.reshape(b, -1).min(dim=-1).values
    else:
        neg = torch.where(valid, -crop / T, torch.full_like(crop, float("-inf")))
        lse = torch.logsumexp(neg.reshape(b, -1), dim=-1)
        mins = torch.where(
            torch.isfinite(lse),
            -T * lse,
            torch.full_like(lse, float("inf")),
        )
    return mins if depth.ndim == 3 else mins[0]


def full_min_depth(depth: np.ndarray) -> float:
    d = np.asarray(depth, dtype=np.float64)
    return _min_finite_positive(d)


def min_depth_pixel_loc(depth: Optional[np.ndarray]) -> Optional[Dict[str, float]]:
    """Normalised (row, col) of the nearest finite+positive depth pixel.

    Read-only. This is the forensic that separates a FRONTAL obstacle (nearest
    pixel near image centre) from a LATERAL/rear blind-spot hit (nearest pixel at
    the left/right edge) or GROUND (bottom rows). ``row``/``col`` ∈ [0,1] with
    (0,0)=top-left; ``col`` near 0/1 ⇒ side, ``row`` near 1 ⇒ below. A forward-only
    depth shield structurally cannot react to a min that is not near the centre.
    """
    if depth is None:
        return None
    d = np.asarray(depth, dtype=np.float64)
    if d.ndim != 2:
        return None
    mask = np.isfinite(d) & (d > 0)
    if not mask.any():
        return None
    dd = np.where(mask, d, np.inf)
    r, c = np.unravel_index(int(np.argmin(dd)), dd.shape)
    h, w = dd.shape
    return {
        "row": round(float(r) / max(h - 1, 1), 3),
        "col": round(float(c) / max(w - 1, 1), 3),
        "val": round(float(dd[r, c]), 3),
    }


def cone_clearances(depth: np.ndarray, *, center_frac: float = 0.5) -> Dict[str, float]:
    """Five-direction min clearances on a 2-D depth map.

    Regions (``H×W`` depth, row↓ col→):

    * **forward** — central ``center_frac`` box (same as :func:`forward_min_depth`)
    * **left** — left half ``[:, :W//2]`` (``col`` near 0)
    * **right** — right half ``[:, W//2:]`` (``col`` near 1)
    * **up** — top half ``[:H//2, :]`` (``row`` near 0)
    * **down** — bottom half ``[H//2:, :]`` (``row`` near 1, ground)

    Empty / invalid regions return ``inf`` (no finite positive depth seen).
    """
    d = np.asarray(depth, dtype=np.float64)
    if d.ndim != 2:
        raise ValueError(f"cone_clearances expects 2-D depth, got shape {d.shape}")
    h, w = d.shape
    mid_r, mid_c = h // 2, w // 2
    return {
        "forward": forward_min_depth(d, center_frac=center_frac),
        "left": _min_finite_positive(d[:, :mid_c]),
        "right": _min_finite_positive(d[:, mid_c:]),
        "up": _min_finite_positive(d[:mid_r, :]),
        "down": _min_finite_positive(d[mid_r:, :]),
    }
