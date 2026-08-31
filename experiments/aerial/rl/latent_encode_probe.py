"""B′ helpers: latent packing, window encode, depth labels, ridge probe."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from experiments.aerial.rl.buffer import Episode
from experiments.aerial.rl.depth_geometry import forward_min_depth


def center_depth_m(obs: Any) -> Optional[float]:
    depth = getattr(obs, "depth", None)
    if depth is None:
        return None
    arr = np.asarray(depth, dtype=np.float64)
    if arr.ndim != 2 or arr.size == 0:
        return None
    h, w = arr.shape
    y0, y1 = h // 3, 2 * h // 3
    x0, x1 = w // 3, 2 * w // 3
    patch = arr[y0:y1, x0:x1]
    finite = patch[np.isfinite(patch) & (patch > 0)]
    if finite.size == 0:
        return None
    return float(np.median(finite))


def forward_depth_m(obs: Any, *, center_frac: float = 0.5) -> Optional[float]:
    depth = getattr(obs, "depth", None)
    if depth is None:
        return None
    arr = np.asarray(depth, dtype=np.float64)
    if arr.ndim != 2 or arr.size == 0:
        return None
    d = forward_min_depth(arr, center_frac=float(center_frac))
    return None if not np.isfinite(d) else float(d)


def encode_single(dynamics: Any, obs: Any) -> np.ndarray:
    return np.asarray(dynamics.encode(obs), dtype=np.float64).reshape(-1)


def encode_window_packed(
    dynamics: Any,
    episode: Episode,
    t_idx: int,
    *,
    window: int = 8,
) -> np.ndarray:
    """Teacher-forced ``[h‖z]`` at ``episode[t_idx]`` (pre-action, matches coll head)."""
    import torch

    t0 = max(0, int(t_idx) - int(window) + 1)
    sl = episode[t0 : int(t_idx) + 1]
    if not sl:
        raise ValueError("empty episode slice")

    dev = dynamics.device
    dtype = dynamics.torch_dtype
    h = dynamics.rssm.initial_h(1, dev, dtype)
    z_flat = torch.zeros(1, dynamics.z_flat, device=dev, dtype=dtype)
    feat_last = None

    with torch.no_grad():
        dynamics.eval()
        for local_t, tr in enumerate(sl):
            obs = tr.obs
            rgb = torch.from_numpy(np.ascontiguousarray(obs.rgb)).unsqueeze(0).to(dev)
            proprio = torch.from_numpy(np.ascontiguousarray(obs.proprio4())).to(dtype)
            proprio = proprio.unsqueeze(0).to(dev)
            embed = dynamics._embed(rgb, proprio)
            post_p = dynamics.rssm.post_probs(h, embed)
            z_flat = dynamics.rssm._sample(post_p)
            feat_last = torch.cat([h, z_flat], dim=-1)
            if local_t < len(sl) - 1:
                act = torch.from_numpy(
                    np.ascontiguousarray(tr.action, dtype=np.float32)
                ).reshape(1, 4).to(dev, dtype)
                h = dynamics.rssm.advance_h(h, z_flat, act)

    assert feat_last is not None
    return feat_last.squeeze(0).float().cpu().numpy()


def ridge_fit_predict(
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_test: np.ndarray,
    *,
    alpha: float = 1.0,
) -> Tuple[np.ndarray, Dict[str, float]]:
    """Closed-form ridge; returns test predictions + train metrics."""
    x_tr = np.asarray(x_train, dtype=np.float64)
    y_tr = np.asarray(y_train, dtype=np.float64).reshape(-1)
    x_te = np.asarray(x_test, dtype=np.float64)
    mu = x_tr.mean(axis=0, keepdims=True)
    sig = x_tr.std(axis=0, keepdims=True)
    sig = np.where(sig < 1e-8, 1.0, sig)
    x_tr_n = (x_tr - mu) / sig
    x_te_n = (x_te - mu) / sig
  # (X'X + aI)^{-1} X'y
    n_feat = x_tr_n.shape[1]
    xtx = x_tr_n.T @ x_tr_n + float(alpha) * np.eye(n_feat)
    w = np.linalg.solve(xtx, x_tr_n.T @ y_tr)
    b = float(y_tr.mean() - (x_tr_n.mean(axis=0) @ w))
    pred_tr = x_tr_n @ w + b
    pred_te = x_te_n @ w + b
    ss_res = float(np.sum((y_tr - pred_tr) ** 2))
    ss_tot = float(np.sum((y_tr - y_tr.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 1e-12 else 0.0
    mae = float(np.mean(np.abs(y_tr - pred_tr)))
    return pred_te, {"r2_train": r2, "mae_train_m": mae}


def probe_depth_from_features(
    features: np.ndarray,
    depths_m: np.ndarray,
    *,
    heldout_frac: float = 0.25,
    alpha: float = 1.0,
    seed: int = 0,
) -> Dict[str, Any]:
    x = np.asarray(features, dtype=np.float64)
    y = np.asarray(depths_m, dtype=np.float64).reshape(-1)
    if x.shape[0] != y.shape[0] or x.shape[0] < 8:
        return {
            "n": int(x.shape[0]),
            "r2_holdout": None,
            "mae_holdout_m": None,
            "verdict": "insufficient_n",
        }
    rng = np.random.default_rng(int(seed))
    idx = rng.permutation(x.shape[0])
    n_test = max(1, int(round(x.shape[0] * float(heldout_frac))))
    te, tr = idx[:n_test], idx[n_test:]
    if tr.size < 4:
        tr, te = idx[n_test:], idx[:n_test]
    _, train_stats = ridge_fit_predict(x[tr], y[tr], x[tr], alpha=alpha)
    pred_te, _ = ridge_fit_predict(x[tr], y[tr], x[te], alpha=alpha)
    y_te = y[te]
    ss_res = float(np.sum((y_te - pred_te) ** 2))
    ss_tot = float(np.sum((y_te - y_te.mean()) ** 2))
    r2_ho = 1.0 - ss_res / ss_tot if ss_tot > 1e-12 else 0.0
    mae_ho = float(np.mean(np.abs(y_te - pred_te)))
    has_geometry = bool(r2_ho >= 0.3 and mae_ho < 2.0)
    return {
        "n": int(x.shape[0]),
        "n_holdout": int(te.size),
        "r2_holdout": round(r2_ho, 4),
        "mae_holdout_m": round(mae_ho, 4),
        "r2_train": round(float(train_stats["r2_train"]), 4),
        "mae_train_m": round(float(train_stats["mae_train_m"]), 4),
        "alpha": float(alpha),
        "verdict": "has_geometry" if has_geometry else "weak_geometry",
    }


def iter_near_depth_samples(
    episodes: Sequence[Episode],
    *,
    max_samples: int,
    stride: int,
    max_center_depth_m: float,
) -> List[Tuple[int, int, float, Optional[float]]]:
    """(ep_i, t_i, center_depth, forward_min_depth)."""
    rows: List[Tuple[int, int, float, Optional[float]]] = []
    stride = max(1, int(stride))
    for ep_i, ep in enumerate(episodes):
        if len(rows) >= int(max_samples):
            break
        if not ep:
            continue
        for t_i in range(0, len(ep), stride):
            if len(rows) >= int(max_samples):
                break
            d0 = center_depth_m(ep[t_i].obs)
            if d0 is None or d0 > float(max_center_depth_m):
                continue
            df = forward_depth_m(ep[t_i].obs)
            rows.append((int(ep_i), int(t_i), float(d0), df))
    return rows
