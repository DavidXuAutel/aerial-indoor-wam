"""H100 offline trainer for the [1b] multi-frame DepthHead (frozen §6 Step 3).

Trains ``_DepthHead`` on schema-v2 episodes via ``perception_data`` (GT depth /
IMU stay off the WM/policy graph). Does **not** flip
``world_model.depth_head.enable`` — that flag stays false until ``_v0_gate``
four-signal PASS (frozen §4).

    python -m experiments.aerial.rl.train_depth_head \
        --dataset experiments/aerial/rl/artifacts/dataset_v0_local_depth \
        --config configs/aerial_rl.yaml --steps 2000 --device cuda --save-ckpt

Writes a jsonl learning log (for ①d / gate) next to the checkpoint.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch
import yaml

from experiments.aerial.rl import dataset as ds
from experiments.aerial.rl.buffer import Episode, ReplayBuffer
from experiments.aerial.rl.depth_geometry import forward_min_depth
from experiments.aerial.rl.dynamics_torch import (
    DA3DepthHead,
    _DepthHead,
    build_depth_head,
    depth_delta_scale_loss,
    depth_head_loss,
)
from experiments.aerial.rl.perception_data import windows_to_perception_arrays
from experiments.aerial.rl.v0_metrics import DEFAULT_THRESHOLDS, depth_absrel


def _load_depth_cfg(config_path: Path) -> Dict[str, Any]:
    cfg = yaml.safe_load(config_path.read_text()) or {}
    wm = dict(cfg.get("world_model", {}) or {})
    dh = dict(wm.get("depth_head", {}) or {})
    # Sensible defaults when the block is only partially filled.
    dh.setdefault("n_frames", 4)
    dh.setdefault("base", 32)
    dh.setdefault("lr", 1.0e-4)
    dh.setdefault("grad_clip", 5.0)
    dh.setdefault("absrel_weight", 1.0)
    dh.setdefault("silog_weight", 0.5)  # historical; v3 P1 → 0
    dh.setdefault("nll_weight", 0.1)
    # Near-band emphasis so close forward obstacles are not averaged away by the
    # many mid/far pixels (diag 2026-08-11: forward GT<1.5 m → D̂ p50 6.4 m, shield
    # never fires). Added training term; ①d gate metric/threshold unchanged.
    dh.setdefault("near_weight", 3.0)
    dh.setdefault("near_focus_m", 5.0)
    # V4-⓪ v1 (archived) — off by default.
    dh.setdefault("near_overread_hinge_weight", 0.0)
    dh.setdefault("near_absrel_pinball_weight", 0.0)
    dh.setdefault("near_absrel_pinball_tau", 0.9)
    # V4-⓪ declare v2.
    dh.setdefault("fwd_overread_hinge_weight", 0.0)
    dh.setdefault("near_absrel_p90_weight", 0.0)
    dh.setdefault("near_absrel_p90_tau", 0.9)
    # V4-⓪ declare v3.
    dh.setdefault("near_fwd_absrel_pinball_weight", 0.0)
    dh.setdefault("near_fwd_absrel_pinball_tau", 0.9)
    dh.setdefault("softmin_temperature_m", 0.0)
    dh.setdefault("min_n_fwd_trigger", 0)
    dh.setdefault("min_steps_before_saturate", 0)
    dh.setdefault("center_frac", 0.5)  # frozen = eval / tau default (declare D-2)
    dh.setdefault("trigger_m", 3.0)
    dh.setdefault("fwd_hinge_saturate_eps", 1.0e-4)
    dh.setdefault("fwd_hinge_saturate_patience", 50)
    dh.setdefault("absrel_lr_drop_on_saturate", 10.0)
    # Keep delta << AbsRel/SILog: delta_weight=1.0 from-scratch collapsed AbsRel
    # (0.98 / 0.70 archived 2026-08-05). Prefer finetune from canonical PASS ckpt.
    dh.setdefault("delta_weight", 0.1)
    dh.setdefault("delta_min_gt_m", 0.5)  # approach gate: ŝ_gt ≥ this
    dh.setdefault("delta_support_ratio", 0.6)  # match §4.1 scale_support_ratio
    dh.setdefault("approach_oversample", 4)  # candidate pool / batch for Δ bias
    dh.setdefault("max_depth_m", 200.0)
    dh.setdefault("scale_depth_min_m", 1.0)
    dh.setdefault("scale_depth_max_m", 40.0)
    # Decoder-only / freeze-encoder Δ-finetune: keep AbsRel-good encoder features
    # fixed; train decoder (depth head) only so scale can move without AbsRel
    # regression. CLI --freeze-encoder overrides; yaml default stays false.
    dh.setdefault("freeze_encoder", False)
    # ③ architecture levers (2026-08-05 dead-Δ diagnose). Both default false so
    # every existing checkpoint keeps loading and every prior recipe reproduces;
    # they change parameter shapes, so a run that sets them cannot warm-start
    # from a plain ckpt with strict=True.
    dh.setdefault("motion_channels", False)
    dh.setdefault("scale_factorized", False)
    dh.setdefault("new_param_lr", None)  # None → same lr as the trunk
    dh.setdefault("image_size", int((cfg.get("env") or {}).get("width", 224)))
    dh.setdefault(
        "checkpoint_dir",
        "experiments/aerial/rl/artifacts/depth_ckpt",
    )
    dh.setdefault("enable", False)
    return dh


def _apply_freeze_encoder(model: _DepthHead, freeze: bool) -> list:
    """Freeze ``model.encoder`` and return the AdamW param list.

    When ``freeze`` is True, encoder ``requires_grad=False`` and only
    ``model.decoder`` params are returned (structurally blocks encoder AbsRel
    drift). When False, all parameters remain trainable and are returned.

    The Δ-scale pathway (``stem_motion`` / ``scale_mlp``) counts as head, not
    encoder — even though ``stem_motion`` sits at the input. Freezing it would
    make decoder-only Δ finetuning a no-op for ③, which is the one thing that
    mode exists to do.
    """
    if not freeze:
        for p in model.parameters():
            p.requires_grad = True
        return list(model.parameters())
    for p in model.encoder.parameters():
        p.requires_grad = False
    head = list(model.decoder.parameters()) + model.new_pathway_parameters()
    for p in head:
        p.requires_grad = True
    return [p for p in head if p.requires_grad]


def _adapt_state_dict(
    state: Dict[str, Any], model: _DepthHead
) -> Tuple[Dict[str, Any], list]:
    """Fit a plain-``_DepthHead`` state dict into a motion/scale-factorized net.

    Returns ``(adapted_state, notes)``. The shared trunk is copied verbatim —
    the motion pathway is its own stem, so the pretrained RGB stem keeps its
    shape — and only the zero-initialised new tensors (``stem_motion``,
    ``scale_mlp``) are filled in from the fresh model. Both contribute nothing
    at step 0, so a warm start reproduces the source checkpoint exactly.

    Any *other* missing or mismatched key is left for ``load_state_dict`` to
    reject: this is a targeted adapter, not a shape coercer.
    """
    tgt = model.state_dict()
    adapted = dict(state)
    notes: list = []
    for key, want in tgt.items():
        if not (key.startswith("scale_mlp.") or key.startswith("stem_motion.")):
            continue
        if key not in adapted:
            adapted[key] = want.clone()
            notes.append(f"{key}: fresh zero-init (contributes nothing at step 0)")
    return adapted, notes


def _refuse_bad_corpus(root: Path, allow: bool) -> None:
    """Same floor policy as ``_wm_train_validate._refuse_v0`` for depth corpora."""
    from experiments.aerial.rl._wm_train_validate import _refuse_v0

    _refuse_v0(root, allow)


def _usable_episodes(root: Path, window: int) -> List[Any]:
    """Episodes long enough for a window AND carrying per-frame GT depth."""
    episodes = ds.load_dataset(root, skip_quarantined=True)
    episodes = [ep for ep in episodes if len(ep) >= window]
    if not episodes:
        print(f"[depth-train] FAIL: no episode >= {window} steps", file=sys.stderr)
        raise SystemExit(1)
    with_depth = [ep for ep in episodes if all(t.obs.depth is not None for t in ep)]
    if not with_depth:
        print("[depth-train] FAIL: no usable episode carries per-frame depth", file=sys.stderr)
        raise SystemExit(1)
    return with_depth


def _split_train_holdout(
    episodes: List[Any], *, holdout_frac: float, seed: int
) -> tuple[List[Any], List[Any], Dict[str, Any]]:
    """Episode-level split — MUST match ``v4_zero_eval`` (holdout_split / §3 #19)."""
    from experiments.aerial.rl.holdout_split import apply_indices, split_holdout_indices

    train_idx, hold_idx, meta = split_holdout_indices(
        len(episodes), frac=float(holdout_frac), seed=int(seed)
    )
    return apply_indices(episodes, train_idx), apply_indices(episodes, hold_idx), meta


def _buffer_from(episodes: List[Any], *, tag: str, window: int) -> ReplayBuffer:
    buf = ReplayBuffer(capacity_episodes=len(episodes) + 1, seed=0)
    for ep in episodes:
        buf.add_episode(ep)
    print(
        f"[depth-train] {tag} buffer: {buf.num_episodes} eps / {buf.num_transitions} "
        f"steps (window>={window}, depth present)"
    )
    return buf


def _holdout_windows(episodes: List[Any], window: int) -> List[Any]:
    """Deterministic non-overlapping (stride=window) windows from held-out eps."""
    windows: List[Any] = []
    for ep in episodes:
        for start in range(0, len(ep) - window + 1, window):
            windows.append(ep[start : start + window])
    return windows


def _band_mean_np(
    depth: np.ndarray, *, min_depth_m: float, max_depth_m: float
) -> np.ndarray:
    """Numpy sibling of ``_band_spatial_mean`` for approach scoring (no torch)."""
    flat = np.asarray(depth, dtype=np.float64).reshape(depth.shape[0], -1)
    valid = np.isfinite(flat) & (flat >= float(min_depth_m)) & (flat <= float(max_depth_m))
    masked = np.where(valid, flat, np.nan)
    with np.errstate(all="ignore"):
        return np.nanmean(masked, axis=-1).astype(np.float32)


def _sample_approach_biased_windows(
    buf: ReplayBuffer,
    batch: int,
    window: int,
    *,
    oversample: int,
    min_depth_m: float,
    max_depth_m: float,
    min_gt_delta_m: float,
    support_ratio: float,
    n_frames: int = 1,
) -> List[Any]:
    """Prefer windows with alive GT ŝ_D (approach geometry for Δ-depth).

    Draws ``batch * oversample`` candidates, ranks by GT |Δ band-mean|, and
    keeps the top ``batch`` that pass the approach gate when possible. Falls
    back to uniform sampling when the pool has no approach-alive windows so
    AbsRel training never stalls.

    Scoring uses the same depth endpoints as ``depth_delta_scale_loss`` in the
    train loop: ``depth[:, n_frames-1]`` vs ``depth[:, -1]`` (not ``[:, 0]``).
    """
    batch = int(batch)
    oversample = max(1, int(oversample))
    n_cand = max(batch, batch * oversample)
    candidates = buf.sample_windows(n_cand, int(window))
    if oversample <= 1 or n_cand == batch:
        return candidates[:batch]
    arrays = windows_to_perception_arrays(candidates)
    # Approach-bias needs both GT depth (to score |Δ|) and position (to gate on
    # motion). If either is absent, fall back to a uniform sample so AbsRel still
    # trains rather than KeyError-ing on the missing field.
    if "depth" not in arrays or "position" not in arrays:
        return candidates[:batch]
    depth = arrays["depth"]
    # Align with Δ-loss: pred_first = predict(rgb[:, :n_f]) → GT [:, n_f-1] vs [:, -1].
    n_f = max(1, min(int(n_frames), int(window)))
    g0 = _band_mean_np(depth[:, n_f - 1], min_depth_m=min_depth_m, max_depth_m=max_depth_m)
    g1 = _band_mean_np(depth[:, -1], min_depth_m=min_depth_m, max_depth_m=max_depth_m)
    s_gt = np.abs(g1.astype(np.float64) - g0.astype(np.float64))
    pos = arrays["position"]
    # Match the Δ-loss motion interval [n_f-1, -1] (not the full window) so the
    # sampler's support gate agrees with depth_delta_scale_loss's.
    motion = np.linalg.norm(pos[:, -1] - pos[:, n_f - 1], axis=-1).astype(np.float64)
    alive = np.isfinite(s_gt) & (s_gt >= float(min_gt_delta_m))
    if float(support_ratio) > 0.0:
        alive &= np.isfinite(motion) & (s_gt >= float(support_ratio) * motion)
    scores = np.where(alive, s_gt, -1.0)
    order = np.argsort(-scores)
    picked = [candidates[int(i)] for i in order[:batch]]
    if not any(scores[int(i)] >= 0.0 for i in order[:batch]):
        # No approach-alive candidates — keep uniform so AbsRel still trains.
        return candidates[:batch]
    return picked


def build_fwd_hard_window_cache(
    episodes: List[Any],
    *,
    window: int,
    center_frac: float,
    trigger_m: float,
) -> List[Episode]:
    """Windows whose last-frame hard ``forward_min(GT) ≤ trigger`` (declare v3 S′)."""
    out: List[Episode] = []
    w = int(window)
    trig = float(trigger_m)
    cf = float(center_frac)
    for ep in episodes:
        if len(ep) < w:
            continue
        for start in range(0, len(ep) - w + 1):
            win = ep[start : start + w]
            depth = getattr(win[-1].obs, "depth", None)
            if depth is None:
                continue
            gf = forward_min_depth(np.asarray(depth), center_frac=cf)
            if np.isfinite(gf) and float(gf) <= trig and float(gf) > 1e-6:
                out.append(win)
    return out


def sample_fwd_hard_windows(
    cache: List[Episode],
    *,
    batch: int,
    min_n_fwd: int,
    rng: np.random.Generator,
) -> List[Episode]:
    """With-replacement sample from hard cache. Cache size < ``min_n_fwd`` → error."""
    if len(cache) < int(min_n_fwd):
        raise ValueError(
            f"fwd hard cache size={len(cache)} < min_n_fwd={min_n_fwd} "
            "(declare v3 S′: refuse silent uniform fallback)"
        )
    if not cache:
        raise ValueError("fwd hard cache is empty")
    idx = rng.integers(0, len(cache), size=int(batch))
    return [cache[int(i)] for i in idx]


def _holdout_absrel(
    model: _DepthHead,
    holdout_eps: List[Any],
    *,
    wm_batch: int,
    window: int,
    device: torch.device,
    max_depth_m: float = 200.0,
) -> float:
    """Median AbsRel over ALL held-out windows (not a random resample of train).

    Enumerates fixed windows so the number is stable across runs, and predicts in
    ``wm_batch`` chunks; pred/GT are pooled before a single ``depth_absrel`` so the
    median-over-pixels semantics match the gate scorer.
    """
    windows = _holdout_windows(holdout_eps, window)
    if not windows:
        return float("nan")
    model.eval()
    preds: List[np.ndarray] = []
    gts: List[np.ndarray] = []
    for i in range(0, len(windows), int(wm_batch)):
        chunk = windows[i : i + int(wm_batch)]
        arrays = windows_to_perception_arrays(chunk)
        if "depth" not in arrays:
            return float("nan")
        rgb = torch.from_numpy(np.ascontiguousarray(arrays["rgb"])).to(device)
        gt = torch.from_numpy(np.ascontiguousarray(arrays["depth"])).to(device)
        with torch.no_grad():
            pred, _ = model.predict_from_window(rgb)
        preds.append(pred.cpu().numpy())
        gts.append(gt[:, -1].cpu().numpy())
    return float(
        depth_absrel(
            np.concatenate(preds, axis=0),
            np.concatenate(gts, axis=0),
            max_depth_m=float(max_depth_m),
        )
    )


def _fetch_da3_metric_state(source: str, device: torch.device) -> Dict[str, Any]:
    """Fetch DA3METRIC-LARGE pretrained state for warm-starting DA3DepthHead.

    Training-machine only (never imported at gate/runtime). ``source`` is either
    an HF repo id (e.g. ``depth-anything/DA3METRIC-LARGE``) or a local path to a
    ``.safetensors`` / ``.pt`` file. Returns the raw upstream state dict whose
    keys are prefixed ``model.backbone.*`` / ``model.head.*``; DA3DepthHead's
    ``load_da3_pretrained`` strips the prefixes and loads strict=False.
    """
    path = Path(source)
    if path.is_file():
        weights = path
    elif path.is_dir():
        cands = sorted(path.glob("*.safetensors")) or sorted(path.glob("*.pt"))
        if not cands:
            raise FileNotFoundError(
                f"--da3-weights dir {path} has no .safetensors/.pt weights"
            )
        weights = cands[0]
    else:
        # Treat as an HF repo id and download the metric weights once.
        from huggingface_hub import hf_hub_download

        weights = Path(
            hf_hub_download(repo_id=source, filename="model.safetensors")
        )
    if str(weights).endswith(".safetensors"):
        from safetensors.torch import load_file

        state = load_file(str(weights), device="cpu")
    else:
        blob = torch.load(str(weights), map_location="cpu", weights_only=False)
        state = blob["model"] if isinstance(blob, dict) and "model" in blob else blob
    print(f"[depth-train] DA3 warm-start: loaded {len(state)} tensors from {weights}")
    return state


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dataset", required=True, type=Path)
    p.add_argument("--config", type=Path, default=Path("configs/aerial_rl.yaml"))
    p.add_argument("--steps", type=int, default=2000)
    p.add_argument("--wm-batch", type=int, default=8)
    p.add_argument("--window", type=int, default=8)
    p.add_argument("--device", default="cuda")
    p.add_argument("--save-ckpt", action="store_true")
    p.add_argument("--allow-v0-desync", action="store_true")
    p.add_argument("--log-every", type=int, default=50)
    p.add_argument(
        "--eval-every",
        type=int,
        default=0,
        help="Compute and log holdout_absrel every N train steps (0 disables). "
             "Uses the same deterministic _holdout_absrel scorer as gate ①d.",
    )
    p.add_argument("--holdout-frac", type=float, default=0.2, help="episode fraction reserved for ①d AbsRel")
    p.add_argument("--split-seed", type=int, default=0)
    p.add_argument(
        "--near-weight",
        type=float,
        default=None,
        help="Override yaml near_weight (symmetric near AbsRel). V4-⓪ FT: set 0 "
             "when using overread hinge / pinball (see declare 20260821).",
    )
    p.add_argument(
        "--near-overread-hinge-weight",
        type=float,
        default=None,
        help="Near-band one-sided hinge on (pred-gt)/gt_+ (⓪d). Declare FT: 3.0.",
    )
    p.add_argument(
        "--near-absrel-pinball-weight",
        type=float,
        default=None,
        help="Near-band pinball on signed relative error (⓪c surrogate). Declare FT: 2.0.",
    )
    p.add_argument(
        "--near-absrel-pinball-tau",
        type=float,
        default=None,
        help="Pinball τ (default 0.9). >0.5 emphasises over-read.",
    )
    p.add_argument(
        "--fwd-overread-hinge-weight",
        type=float,
        default=None,
        help="Declare v2 A′: forward-crop min over-read hinge (eval ⓪d geometry).",
    )
    p.add_argument(
        "--near-absrel-p90-weight",
        type=float,
        default=None,
        help="Declare v2 B′: near-band AbsRel tail weight (not signed pinball).",
    )
    p.add_argument(
        "--near-absrel-p90-tau",
        type=float,
        default=None,
        help="AbsRel p90 tail τ (default 0.9).",
    )
    p.add_argument(
        "--declare-id",
        type=str,
        default="",
        help="Print/record declare id at train start (e.g. v2-20260821).",
    )
    p.add_argument(
        "--absrel-weight",
        type=float,
        default=None,
        help="Override yaml absrel_weight (declare v3 P1: 0).",
    )
    p.add_argument(
        "--silog-weight",
        type=float,
        default=None,
        help="Override silog coefficient (default 0.5; declare v3 P1: 0).",
    )
    p.add_argument(
        "--nll-weight",
        type=float,
        default=None,
        help="Override nll_weight (declare v3 P1: 0.05).",
    )
    p.add_argument(
        "--fwd-softmin-temp",
        type=float,
        default=None,
        help="Declare v3 softmin T in metres (recipe 0.05); 0=hard min.",
    )
    p.add_argument(
        "--near-fwd-absrel-pinball-weight",
        type=float,
        default=None,
        help="Declare v3 B″: AbsRel pinball on forward crop ∩ near.",
    )
    p.add_argument(
        "--near-fwd-absrel-pinball-tau",
        type=float,
        default=None,
        help="Declare v3 B″ pinball τ (default 0.9).",
    )
    p.add_argument(
        "--min-n-fwd-trigger",
        type=int,
        default=None,
        help="Declare v3 S′: require fwd hard cache size ≥ K (recipe 4).",
    )
    p.add_argument(
        "--fwd-hard-cache",
        action="store_true",
        help="Declare v3 S′: sample train batches from hard-forward window cache.",
    )
    p.add_argument(
        "--min-steps-before-saturate",
        type=int,
        default=None,
        help="Declare v3 C″: ignore hinge saturation until this step (recipe 100).",
    )
    p.add_argument(
        "--skip-p2",
        action="store_true",
        help="Declare v3: never enter AbsRel P2 (default recipe).",
    )
    p.add_argument(
        "--early-stop-on-fwd-saturate",
        action="store_true",
        help="Declare v2 C′: stop when fwd_overread_hinge stays below eps for patience steps.",
    )
    p.add_argument(
        "--drop-absrel-lr-on-fwd-saturate",
        action="store_true",
        help="Declare v2 C′: instead of stop, drop AbsRel-group lr by absrel_lr_drop_on_saturate.",
    )
    p.add_argument(
        "--init-ckpt",
        type=Path,
        default=None,
        help="Finetune from an existing DepthHead ckpt (prefer canonical AbsRel-PASS)",
    )
    p.add_argument(
        "--checkpoint-dir",
        type=Path,
        default=None,
        help="Override yaml checkpoint_dir (write FAIL candidates outside canonical)",
    )
    p.add_argument(
        "--lr",
        type=float,
        default=None,
        help="Override yaml lr (finetune often uses 3e-5)",
    )
    p.add_argument(
        "--motion-channels",
        action="store_true",
        help="Feed the n_frames-1 frame differences alongside RGB. Changes the "
             "stem conv shape; combine with --adapt-init to warm-start from a "
             "plain checkpoint.",
    )
    p.add_argument(
        "--scale-factorized",
        action="store_true",
        help="Predict a scalar log-scale per call and multiply the depth map by "
             "it, giving the Δ objective one low-variance DOF.",
    )
    p.add_argument(
        "--new-param-lr",
        type=float,
        default=None,
        help="Separate lr for the zero-init Δ-scale pathway (stem_motion / "
             "scale_mlp). They start at zero, so the trunk's lr leaves them "
             "there while a uniform larger lr destroys the trunk's AbsRel.",
    )
    p.add_argument(
        "--adapt-init",
        action="store_true",
        help="Allow --init-ckpt from a plain checkpoint into a motion/scale-"
             "factorized net: new stem input channels are zeroed and scale_mlp "
             "starts at exp(0)=1, so step 0 reproduces the source exactly.",
    )
    p.add_argument(
        "--delta-weight",
        type=float,
        default=None,
        help="Override yaml delta_weight for this run",
    )
    p.add_argument(
        "--approach-oversample",
        type=int,
        default=None,
        help="Override yaml approach_oversample. OS>1 ranks batch candidates by "
             "GT |Δ band-mean| (approach bias) for the Δ term, but the SAME biased "
             "batch also feeds the AbsRel/SILog loss — set OS=1 to train AbsRel on "
             "the natural (un-oversampled) distribution.",
    )
    p.add_argument(
        "--overwrite",
        action="store_true",
        help="Permit overwriting an existing ckpt / clobbering depth_train.jsonl "
             "in the target dir. Off by default so a finetune run cannot silently "
             "replace the canonical AbsRel-PASS checkpoint.",
    )
    p.add_argument(
        "--freeze-encoder",
        action="store_true",
        default=None,
        help="Freeze encoder; AdamW only on decoder (depth head). Preserves "
             "AbsRel-good features while Δ-finetuning scale. Overrides yaml.",
    )
    p.add_argument(
        "--no-freeze-encoder",
        action="store_true",
        help="Force full-model finetune even if yaml freeze_encoder=true.",
    )
    p.add_argument(
        "--base",
        type=int,
        default=None,
        help="Override yaml depth_head.base (channel width). Capacity lift "
             "uses 64; canonical AbsRel-PASS ckpt is base=32 — arch mismatch "
             "refuses --init-ckpt (strict load). Default keeps yaml (32).",
    )
    p.add_argument(
        "--backbone",
        choices=("scratch", "da3"),
        default="scratch",
        help="Depth-head backbone. 'scratch' = from-scratch _DepthHead (canonical, "
             "default, unchanged). 'da3' = DA3DepthHead (frozen DINOv2-ViT-L + "
             "trainable DPT), warm-started from DA3METRIC-LARGE — targets ①d margin.",
    )
    p.add_argument(
        "--da3-weights",
        default="depth-anything/DA3METRIC-LARGE",
        help="DA3 warm-start source for --backbone da3: HF repo id (downloaded once "
             "and cached) or a local .safetensors/.pt path. Ignored unless "
             "--backbone da3 and --init-ckpt is not set (finetune resumes from ckpt).",
    )
    args = p.parse_args(argv)
    if args.eval_every < 0:
        p.error("--eval-every must be >= 0")
    if args.approach_oversample is not None and args.approach_oversample < 1:
        p.error("--approach-oversample must be >= 1")

    root = args.dataset
    _refuse_bad_corpus(root, args.allow_v0_desync)
    dh_cfg = _load_depth_cfg(args.config)
    if args.new_param_lr is not None:
        dh_cfg["new_param_lr"] = float(args.new_param_lr)
    if args.motion_channels:
        dh_cfg["motion_channels"] = True
    if args.scale_factorized:
        dh_cfg["scale_factorized"] = True
    if args.delta_weight is not None:
        print(f"[depth-train] NOTE: --delta-weight {args.delta_weight} overrides "
              f"yaml delta_weight={dh_cfg.get('delta_weight')}", file=sys.stderr)
        dh_cfg["delta_weight"] = float(args.delta_weight)
    if args.approach_oversample is not None:
        print(f"[depth-train] NOTE: --approach-oversample {args.approach_oversample} "
              f"overrides yaml approach_oversample={dh_cfg.get('approach_oversample')}",
              file=sys.stderr)
        dh_cfg["approach_oversample"] = int(args.approach_oversample)
    if args.lr is not None:
        print(f"[depth-train] NOTE: --lr {args.lr} overrides yaml lr={dh_cfg.get('lr')}",
              file=sys.stderr)
        dh_cfg["lr"] = float(args.lr)
    if args.near_weight is not None:
        dh_cfg["near_weight"] = float(args.near_weight)
    if args.near_overread_hinge_weight is not None:
        dh_cfg["near_overread_hinge_weight"] = float(args.near_overread_hinge_weight)
    if args.near_absrel_pinball_weight is not None:
        dh_cfg["near_absrel_pinball_weight"] = float(args.near_absrel_pinball_weight)
    if args.near_absrel_pinball_tau is not None:
        dh_cfg["near_absrel_pinball_tau"] = float(args.near_absrel_pinball_tau)
    if args.fwd_overread_hinge_weight is not None:
        dh_cfg["fwd_overread_hinge_weight"] = float(args.fwd_overread_hinge_weight)
    if args.near_absrel_p90_weight is not None:
        dh_cfg["near_absrel_p90_weight"] = float(args.near_absrel_p90_weight)
    if args.near_absrel_p90_tau is not None:
        dh_cfg["near_absrel_p90_tau"] = float(args.near_absrel_p90_tau)
    if args.absrel_weight is not None:
        dh_cfg["absrel_weight"] = float(args.absrel_weight)
    if args.silog_weight is not None:
        dh_cfg["silog_weight"] = float(args.silog_weight)
    if args.nll_weight is not None:
        dh_cfg["nll_weight"] = float(args.nll_weight)
    if args.fwd_softmin_temp is not None:
        dh_cfg["softmin_temperature_m"] = float(args.fwd_softmin_temp)
    if args.near_fwd_absrel_pinball_weight is not None:
        dh_cfg["near_fwd_absrel_pinball_weight"] = float(
            args.near_fwd_absrel_pinball_weight
        )
    if args.near_fwd_absrel_pinball_tau is not None:
        dh_cfg["near_fwd_absrel_pinball_tau"] = float(
            args.near_fwd_absrel_pinball_tau
        )
    if args.min_n_fwd_trigger is not None:
        dh_cfg["min_n_fwd_trigger"] = int(args.min_n_fwd_trigger)
    if args.min_steps_before_saturate is not None:
        dh_cfg["min_steps_before_saturate"] = int(args.min_steps_before_saturate)
    if args.base is not None:
        if int(args.base) < 8:
            p.error("--base must be >= 8")
        print(f"[depth-train] NOTE: --base {args.base} overrides yaml "
              f"base={dh_cfg.get('base')}", file=sys.stderr)
        dh_cfg["base"] = int(args.base)
    backbone = str(args.backbone).lower()
    if backbone == "da3":
        # ③ is solved (reprojection estimator); DA3 trains pure metric depth for
        # ①d. Force the Δ term and heteroscedastic NLL off (DPT emits depth only
        # → zero log_sigma), and freeze the DINOv2 backbone by default (train DPT
        # head only) unless the user explicitly opts out.
        if float(dh_cfg.get("delta_weight", 0.0)) != 0.0:
            print("[depth-train] NOTE: --backbone da3 forces delta_weight=0 "
                  "(③ solved via reprojection; DA3 trains metric depth only)",
                  file=sys.stderr)
        dh_cfg["delta_weight"] = 0.0
        dh_cfg["nll_weight"] = 0.0
        if not args.no_freeze_encoder and not args.freeze_encoder:
            dh_cfg["freeze_encoder"] = True
    if args.no_freeze_encoder:
        dh_cfg["freeze_encoder"] = False
    elif args.freeze_encoder:
        dh_cfg["freeze_encoder"] = True
    # The Δ term needs window STRICTLY > n_frames to have a non-degenerate Δ
    # interval. A finetune whose whole purpose is ③/Δ must not silently run for
    # hours with the term disabled — fail fast at setup instead.
    if float(dh_cfg.get("delta_weight", 0.0)) > 0.0 and int(args.window) <= int(dh_cfg["n_frames"]):
        print(f"[depth-train] FAIL: delta_weight>0 needs --window > n_frames "
              f"(got window={args.window}, n_frames={dh_cfg['n_frames']}); at "
              "window==n_frames the Δ interval collapses to a single frame (Δ≡0)",
              file=sys.stderr)
        return 1
    if bool(dh_cfg.get("enable")):
        print(
            "[depth-train] NOTE: world_model.depth_head.enable is true in yaml; "
            "frozen §4 says flip only AFTER _v0_gate PASS — training still runs, "
            "but do not treat this as gate success.",
            file=sys.stderr,
        )

    device = torch.device(args.device if torch.cuda.is_available() or args.device == "cpu" else "cpu")
    if str(device) != args.device:
        print(f"[depth-train] falling back to {device} (requested {args.device})")

    all_eps = _usable_episodes(root, args.window)
    train_eps, holdout_eps, split_meta = _split_train_holdout(
        all_eps, holdout_frac=float(args.holdout_frac), seed=int(args.split_seed)
    )
    if args.declare_id:
        print(f"[depth-train] declare_id={args.declare_id}")
    print(
        f"[depth-train] split regime={split_meta.get('regime')} "
        f"n_train={split_meta.get('n_train')} n_holdout={split_meta.get('n_holdout')} "
        f"seed={split_meta.get('split_seed')} "
        f"holdout_indices={split_meta.get('holdout_indices')}"
    )
    if not holdout_eps:
        print(
            "[depth-train] WARN: <2 usable episodes — no held-out split; ①d AbsRel "
            "will be IN-SAMPLE and is NOT a valid gate signal. Collect more episodes.",
            file=sys.stderr,
        )
        holdout_eps = train_eps  # in-sample fallback, explicitly flagged above
    buf = _buffer_from(train_eps, tag="train", window=args.window)
    print(f"[depth-train] holdout: {len(holdout_eps)} eps reserved for ①d AbsRel")
    if backbone == "da3":
        # Frozen DINOv2-ViT-L + trainable DPT. Warm-start the whole net from
        # DA3METRIC-LARGE (backbone+head), then finetune the DPT head on our GT
        # to learn metric scale. `base` is inert for DA3 (arch is fixed by the
        # DINOv2/DPT config), so it does not enter the DA3 construction.
        model = DA3DepthHead(
            image_size=int(dh_cfg["image_size"]),
            n_frames=int(dh_cfg["n_frames"]),
            motion_channels=bool(dh_cfg.get("motion_channels", False)),
            scale_factorized=bool(dh_cfg.get("scale_factorized", False)),
        ).to(device)
        if args.init_ckpt is not None:
            # Resume a previously-finetuned, self-contained DA3 ①d ckpt.
            ckpt_path = Path(args.init_ckpt)
            blob = torch.load(ckpt_path, map_location=device, weights_only=False)
            state = blob["model"] if isinstance(blob, dict) and "model" in blob else blob
            model.load_state_dict(state, strict=True)
            prior = blob.get("holdout_absrel") if isinstance(blob, dict) else None
            print(f"[depth-train] DA3 resume from {ckpt_path} (prior_holdout={prior})")
        else:
            # Fresh warm-start from the pretrained DA3METRIC weights (strict=False:
            # our head has no cam/gs/sky branches, and the load maps only
            # backbone→encoder + head→decoder).
            state = _fetch_da3_metric_state(args.da3_weights, device)
            model.load_da3_pretrained(state)
    else:
        model = _DepthHead(
            image_size=int(dh_cfg["image_size"]),
            n_frames=int(dh_cfg["n_frames"]),
            base=int(dh_cfg["base"]),
            motion_channels=bool(dh_cfg.get("motion_channels", False)),
            scale_factorized=bool(dh_cfg.get("scale_factorized", False)),
        ).to(device)
        if args.init_ckpt is not None:
            ckpt_path = Path(args.init_ckpt)
            blob = torch.load(ckpt_path, map_location=device, weights_only=False)
            state = blob["model"] if isinstance(blob, dict) and "model" in blob else blob
            # strict=True is deliberate: refuse to finetune from a checkpoint whose
            # architecture doesn't match the configured DepthHead (n_frames / base /
            # image_size). On mismatch load_state_dict raises — there is no
            # (missing, unexpected) tuple to report (that only comes back non-empty
            # with strict=False), so surface a clean, actionable FAIL instead.
            if args.adapt_init:
                state, notes = _adapt_state_dict(state, model)
                for note in notes:
                    print(f"[depth-train] adapt-init {note}")
                if not notes:
                    print("[depth-train] adapt-init: nothing to adapt (arch already matches)")
            try:
                model.load_state_dict(state, strict=True)
            except RuntimeError as e:
                print(f"[depth-train] FAIL: --init-ckpt {ckpt_path} arch mismatch vs "
                      f"configured DepthHead (n_frames={dh_cfg['n_frames']} "
                      f"base={dh_cfg['base']} image_size={dh_cfg['image_size']} "
                      f"motion_channels={dh_cfg.get('motion_channels', False)} "
                      f"scale_factorized={dh_cfg.get('scale_factorized', False)}): {e}",
                      file=sys.stderr)
                return 1
            prior = blob.get("holdout_absrel") if isinstance(blob, dict) else None
            print(f"[depth-train] init from {ckpt_path} (prior_holdout={prior})")
    freeze_enc = bool(dh_cfg.get("freeze_encoder", False))
    trainable = _apply_freeze_encoder(model, freeze_enc)
    if not trainable:
        print("[depth-train] FAIL: no trainable params after freeze_encoder",
              file=sys.stderr)
        return 1
    n_enc = sum(p.numel() for p in model.encoder.parameters())
    n_train = sum(p.numel() for p in trainable)
    n_all = sum(p.numel() for p in model.parameters())
    print(
        f"[depth-train] freeze_encoder={freeze_enc}: "
        f"trainable={n_train}/{n_all} params "
        f"(encoder={n_enc} frozen={freeze_enc})"
    )
    base_lr = float(dh_cfg["lr"])
    new_lr = float(dh_cfg.get("new_param_lr") or base_lr)
    new_params = [p for p in model.new_pathway_parameters() if p.requires_grad]
    new_ids = {id(p) for p in new_params}
    if new_params and new_lr != base_lr:
        groups = [
            {"params": [p for p in trainable if id(p) not in new_ids], "lr": base_lr},
            {"params": new_params, "lr": new_lr},
        ]
        print(
            f"[depth-train] param groups: trunk lr={base_lr} "
            f"({sum(p.numel() for p in trainable if id(p) not in new_ids)} params), "
            f"Δ-scale pathway lr={new_lr} "
            f"({sum(p.numel() for p in new_params)} params)"
        )
    else:
        groups = [{"params": trainable, "lr": base_lr}]
    opt = torch.optim.AdamW(groups, lr=base_lr, betas=(0.9, 0.95))
    grad_clip = float(dh_cfg["grad_clip"])

    ckpt_dir = Path(str(args.checkpoint_dir or dh_cfg["checkpoint_dir"]))
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    split_path = ckpt_dir / "holdout_split.json"
    split_path.write_text(json.dumps(split_meta, indent=2) + "\n")
    print(f"[depth-train] wrote {split_path} (v4_zero_eval --expect-holdout-split)")
    log_path = ckpt_dir / "depth_train.jsonl"
    # Finetune runs default their save dir to the canonical checkpoint_dir. A
    # naive save + blind log-unlink would silently replace the AbsRel-PASS
    # canonical ckpt (and destroy its training record) with an unvalidated run.
    # Give finetune runs a distinct '_ft' stem and refuse to clobber anything
    # pre-existing unless --overwrite is explicit; point re-runs at a fresh
    # --checkpoint-dir instead.
    stem = f"depth_step_{args.steps}"
    # DA3 checkpoints are a distinct architecture family — never collide with the
    # from-scratch canonical stem (depth_step_N.pt) so canonical stays untouched.
    if backbone == "da3":
        stem += "_da3"
    # Capacity-lift / non-canonical width: keep base-32 canonical stem untouched
    # (depth_step_N.pt) and park wider ckpts under an explicit _base{N} suffix.
    base_w = int(dh_cfg["base"])
    if base_w != 32:
        stem += f"_base{base_w}"
    if args.init_ckpt:
        stem += "_ft"
    if freeze_enc:
        stem += "_head"  # decoder-only / freeze-encoder run
    save_path = ckpt_dir / f"{stem}.pt"
    if args.save_ckpt:
        if args.init_ckpt is not None and save_path.resolve() == Path(args.init_ckpt).resolve():
            print(f"[depth-train] FAIL: save path {save_path} == --init-ckpt source; "
                  "refusing to overwrite the checkpoint being finetuned from",
                  file=sys.stderr)
            return 1
        if save_path.exists() and not args.overwrite:
            print(f"[depth-train] FAIL: {save_path} already exists; pass --overwrite "
                  "or a fresh --checkpoint-dir (won't clobber a canonical ckpt)",
                  file=sys.stderr)
            return 1
    if log_path.exists():
        if not args.overwrite:
            print(f"[depth-train] FAIL: {log_path} already exists; pass --overwrite "
                  "or a fresh --checkpoint-dir (won't destroy an existing train log)",
                  file=sys.stderr)
            return 1
        log_path.unlink()
    print(
        f"[depth-train] recipe: base={dh_cfg['base']} n_frames={dh_cfg['n_frames']} "
        f"lr={dh_cfg['lr']} delta_weight={dh_cfg['delta_weight']} "
        f"grad_clip={grad_clip} "
        f"delta_min_gt_m={dh_cfg.get('delta_min_gt_m')} "
        f"approach_oversample={dh_cfg.get('approach_oversample')} "
        f"freeze_encoder={freeze_enc} "
        f"motion_channels={dh_cfg.get('motion_channels', False)} "
        f"scale_factorized={dh_cfg.get('scale_factorized', False)} "
        f"new_param_lr={dh_cfg.get('new_param_lr')} "
        f"near_weight={dh_cfg.get('near_weight', 0)} "
        f"overread_hinge={dh_cfg.get('near_overread_hinge_weight', 0)} "
        f"pinball={dh_cfg.get('near_absrel_pinball_weight', 0)}"
        f"@τ={dh_cfg.get('near_absrel_pinball_tau', 0.9)} "
        f"fwd_hinge={dh_cfg.get('fwd_overread_hinge_weight', 0)} "
        f"absrel_p90={dh_cfg.get('near_absrel_p90_weight', 0)} "
        f"near_fwd_pinball={dh_cfg.get('near_fwd_absrel_pinball_weight', 0)} "
        f"silog_w={dh_cfg.get('silog_weight', 0.5)} "
        f"absrel_w={dh_cfg.get('absrel_weight', 1.0)} "
        f"softmin_T={dh_cfg.get('softmin_temperature_m', 0)} "
        f"min_n_fwd={dh_cfg.get('min_n_fwd_trigger', 0)} "
        f"ckpt_dir={ckpt_dir}"
    )

    absrels: List[float] = []
    losses: List[float] = []
    last_holdout: Optional[float] = None
    fwd_sat_streak = 0
    absrel_lr_dropped = False
    sat_eps = float(dh_cfg.get("fwd_hinge_saturate_eps", 1.0e-4))
    sat_patience = int(dh_cfg.get("fwd_hinge_saturate_patience", 50))
    lr_drop = float(dh_cfg.get("absrel_lr_drop_on_saturate", 10.0))
    min_steps_sat = int(dh_cfg.get("min_steps_before_saturate", 0))
    min_n_fwd = int(dh_cfg.get("min_n_fwd_trigger", 0))
    use_fwd_cache = bool(args.fwd_hard_cache) or min_n_fwd > 0
    fwd_cache: List[Any] = []
    cache_rng = np.random.default_rng(int(args.split_seed) + 17)
    if use_fwd_cache:
        fwd_cache = build_fwd_hard_window_cache(
            train_eps,
            window=int(args.window),
            center_frac=float(dh_cfg.get("center_frac", 0.5)),
            trigger_m=float(dh_cfg.get("trigger_m", 3.0)),
        )
        k_req = max(1, min_n_fwd) if min_n_fwd > 0 else 1
        print(
            f"[depth-train] fwd hard cache size={len(fwd_cache)} "
            f"min_n_fwd={k_req} (declare v3 S′)"
        )
        if len(fwd_cache) < k_req:
            print(
                f"[depth-train] FAIL: fwd hard cache size={len(fwd_cache)} < K={k_req}",
                file=sys.stderr,
            )
            with log_path.open("a") as f:
                f.write(
                    json.dumps(
                        {
                            "early_refuse": True,
                            "reason": "fwd_hard_cache_too_small",
                            "fwd_cache_size": len(fwd_cache),
                            "min_n_fwd": k_req,
                        }
                    )
                    + "\n"
                )
            return 1
    model.train()
    stopped_early = False
    stop_reason = None
    for step in range(1, int(args.steps) + 1):
        if use_fwd_cache:
            windows = sample_fwd_hard_windows(
                fwd_cache,
                batch=int(args.wm_batch),
                min_n_fwd=max(1, min_n_fwd) if min_n_fwd > 0 else 1,
                rng=cache_rng,
            )
        else:
            windows = _sample_approach_biased_windows(
                buf,
                int(args.wm_batch),
                int(args.window),
                oversample=int(dh_cfg.get("approach_oversample", 1)),
                min_depth_m=float(dh_cfg["scale_depth_min_m"]),
                max_depth_m=float(dh_cfg["scale_depth_max_m"]),
                min_gt_delta_m=float(dh_cfg.get("delta_min_gt_m", 0.5)),
                support_ratio=float(dh_cfg.get("delta_support_ratio", 0.0)),
                n_frames=int(dh_cfg["n_frames"]),
            )
        arrays = windows_to_perception_arrays(windows)
        if "depth" not in arrays:
            print("[depth-train] FAIL: batch missing depth", file=sys.stderr)
            return 1
        rgb = torch.from_numpy(np.ascontiguousarray(arrays["rgb"])).to(device)
        gt = torch.from_numpy(np.ascontiguousarray(arrays["depth"])).to(device)
        pred, log_sigma = model.predict_from_window(rgb)
        loss, stats = depth_head_loss(
            pred, log_sigma, gt[:, -1],
            absrel_weight=float(dh_cfg["absrel_weight"]),
            silog_weight=float(dh_cfg.get("silog_weight", 0.5)),
            nll_weight=float(dh_cfg["nll_weight"]),
            max_depth_m=float(dh_cfg["max_depth_m"]),
            near_weight=float(dh_cfg.get("near_weight", 0.0)),
            near_focus_m=float(dh_cfg.get("near_focus_m", 5.0)),
            near_overread_hinge_weight=float(
                dh_cfg.get("near_overread_hinge_weight", 0.0)
            ),
            near_absrel_pinball_weight=float(
                dh_cfg.get("near_absrel_pinball_weight", 0.0)
            ),
            near_absrel_pinball_tau=float(
                dh_cfg.get("near_absrel_pinball_tau", 0.9)
            ),
            fwd_overread_hinge_weight=float(
                dh_cfg.get("fwd_overread_hinge_weight", 0.0)
            ),
            near_absrel_p90_weight=float(dh_cfg.get("near_absrel_p90_weight", 0.0)),
            near_absrel_p90_tau=float(dh_cfg.get("near_absrel_p90_tau", 0.9)),
            near_fwd_absrel_pinball_weight=float(
                dh_cfg.get("near_fwd_absrel_pinball_weight", 0.0)
            ),
            near_fwd_absrel_pinball_tau=float(
                dh_cfg.get("near_fwd_absrel_pinball_tau", 0.9)
            ),
            softmin_temperature_m=float(dh_cfg.get("softmin_temperature_m", 0.0)),
            center_frac=float(dh_cfg.get("center_frac", 0.5)),
            trigger_m=float(dh_cfg.get("trigger_m", 3.0)),
        )
        stats = {
            **stats,
            "phase": "p1",
            "absrel_weight": float(dh_cfg["absrel_weight"]),
            "silog_weight": float(dh_cfg.get("silog_weight", 0.5)),
            "fwd_cache_size": int(len(fwd_cache)),
            "softmin_T": float(dh_cfg.get("softmin_temperature_m", 0.0)),
        }
        # Temporal / Δ-depth: predict the first frame of the window with full
        # n_frames context and match |Δ band-mean| to GT on approach-alive rows
        # — teaches ③ without drowning AbsRel. Requires window STRICTLY > n_frames:
        # at window == n_frames, gt[:, n_f-1] and gt[:, -1] are the same frame, so
        # Δ is identically 0 and the loss is a degenerate no-op. Also needs
        # position (motion gate); skip the term for a batch that lacks it.
        delta_w = float(dh_cfg.get("delta_weight", 0.0))
        if (delta_w > 0.0 and int(args.window) > int(dh_cfg["n_frames"])
                and "position" in arrays):
            n_f = int(dh_cfg["n_frames"])
            pred_first, _ = model.predict_from_window(rgb[:, :n_f])
            pos = torch.from_numpy(np.ascontiguousarray(arrays["position"])).to(device)
            # Motion must span the SAME interval as the depth Δ: pred_first/gt
            # are at frame n_f-1, pred_last/gt at frame -1. Using full-window
            # motion pos[-1]-pos[0] overstates ‖Δp‖ and makes the support gate
            # (s_gt ≥ support_ratio·‖Δp‖) reject valid approach windows.
            motion_m = torch.linalg.norm(pos[:, -1] - pos[:, n_f - 1], dim=-1)
            d_loss, d_stats = depth_delta_scale_loss(
                pred_first,
                pred,
                gt[:, n_f - 1],
                gt[:, -1],
                min_depth_m=float(dh_cfg["scale_depth_min_m"]),
                max_depth_m=float(dh_cfg["scale_depth_max_m"]),
                min_gt_delta_m=float(dh_cfg.get("delta_min_gt_m", 0.5)),
                motion_m=motion_m,
                support_ratio=float(dh_cfg.get("delta_support_ratio", 0.0)),
            )
            loss = loss + delta_w * d_loss
            stats = {**stats, **d_stats, "loss": float(loss.detach().item())}
        else:
            stats = {**stats, "delta_rel": float("nan"), "n_delta": 0}
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(trainable, grad_clip)
        opt.step()

        losses.append(float(stats["loss"]))
        train_batch_absrel = float(stats.pop("absrel"))
        absrels.append(train_batch_absrel)
        row = {"step": step, **stats, "train_batch_absrel": train_batch_absrel}
        if int(args.eval_every) > 0 and step % int(args.eval_every) == 0:
            last_holdout = _holdout_absrel(
                model,
                holdout_eps,
                wm_batch=int(args.wm_batch),
                window=int(args.window),
                device=device,
                max_depth_m=float(dh_cfg["max_depth_m"]),
            )
            row["holdout_absrel"] = last_holdout
            print(
                f"[depth-train] step {step}/{args.steps} "
                f"holdout_absrel={last_holdout:.4f} (gate ①d ≤ "
                f"{DEFAULT_THRESHOLDS.depth_absrel_max})"
            )
            model.train()
        with log_path.open("a") as f:
            f.write(json.dumps(row) + "\n")
        if step % int(args.log_every) == 0 or step == 1:
            print(
                f"[depth-train] step {step}/{args.steps} "
                f"loss={stats['loss']:.4f} "
                f"train_batch_absrel={train_batch_absrel:.4f} "
                f"near_absrel={stats.get('near_absrel', float('nan'))} "
                f"fwd_hinge={stats.get('fwd_overread_hinge', float('nan'))} "
                f"absrel_p90={stats.get('near_absrel_p90', float('nan'))} "
                f"n_fwd={stats.get('n_fwd_trigger', 0)} "
                f"n_near={stats.get('n_near', 0)} "
                f"n_valid={stats['n_valid']}"
            )
        # Declare v3 C″: saturation of forward hinge (ignore nan / n_fwd<K; min_steps).
        fh = stats.get("fwd_overread_hinge")
        n_fwd_step = int(stats.get("n_fwd_trigger", 0) or 0)
        k_gate = max(1, min_n_fwd) if min_n_fwd > 0 else 1
        if (
            float(dh_cfg.get("fwd_overread_hinge_weight", 0.0)) > 0.0
            and step >= min_steps_sat
            and fh is not None
            and fh == fh  # not NaN
            and n_fwd_step >= k_gate
        ):
            if float(fh) < sat_eps:
                fwd_sat_streak += 1
            else:
                fwd_sat_streak = 0
            if fwd_sat_streak >= sat_patience:
                # Default recipe: --skip-p2 + --early-stop-on-fwd-saturate → stop (no P2).
                if args.early_stop_on_fwd_saturate or args.skip_p2:
                    stopped_early = True
                    stop_reason = (
                        f"fwd_overread_hinge<{sat_eps} for {sat_patience} steps "
                        f"(last={fh})"
                    )
                    print(f"[depth-train] EARLY STOP: {stop_reason}")
                    row_stop = {
                        "step": step,
                        "early_stop": True,
                        "reason": stop_reason,
                    }
                    with log_path.open("a") as f:
                        f.write(json.dumps(row_stop) + "\n")
                    break
                if args.drop_absrel_lr_on_fwd_saturate and not absrel_lr_dropped:
                    for g in opt.param_groups:
                        g["lr"] = float(g["lr"]) / lr_drop
                    absrel_lr_dropped = True
                    fwd_sat_streak = 0
                    print(
                        f"[depth-train] fwd hinge saturated — AbsRel lr ÷{lr_drop} "
                        f"(now {opt.param_groups[0]['lr']})"
                    )
                    with log_path.open("a") as f:
                        f.write(
                            json.dumps(
                                {
                                    "step": step,
                                    "absrel_lr_dropped": True,
                                    "new_lr": opt.param_groups[0]["lr"],
                                    "fwd_hinge": fh,
                                }
                            )
                            + "\n"
                        )

    final_step_was_evaluated = (
        int(args.eval_every) > 0
        and int(args.steps) > 0
        and int(args.steps) % int(args.eval_every) == 0
    )
    holdout = last_holdout if final_step_was_evaluated else _holdout_absrel(
        model,
        holdout_eps,
        wm_batch=int(args.wm_batch),
        window=int(args.window),
        device=device,
        max_depth_m=float(dh_cfg["max_depth_m"]),
    )
    new_params_end = model.new_pathway_parameters()
    if new_params_end:
        # Zero-init means "no contribution": if these norms are still ~0 the run
        # never tested the Δ-scale pathway, whatever ③ ends up reporting.
        norms = " ".join(
            f"{name}={p.detach().norm().item():.3e}"
            for name, p in model.named_parameters()
            if any(p is q for q in new_params_end)
        )
        print(f"[depth-train] Δ-scale pathway norms (0 ⇒ never trained): {norms}")
    thr = DEFAULT_THRESHOLDS.depth_absrel_max
    print(f"[depth-train] holdout median AbsRel={holdout:.4f} (gate ①d ≤ {thr})")
    ok_1d = bool(np.isfinite(holdout) and holdout <= thr)
    if not ok_1d:
        print(
            f"[depth-train] WARN: holdout AbsRel above ①d threshold — continue "
            "training or retune; _v0_gate will FAIL ①d until this clears.",
            file=sys.stderr,
        )

    if args.save_ckpt:
        path = save_path
        torch.save(
            {
                "model": model.state_dict(),
                "step": int(args.steps),
                "n_frames": int(dh_cfg["n_frames"]),
                "image_size": int(dh_cfg["image_size"]),
                "base": int(dh_cfg["base"]),
                # Architecture flags must round-trip: _DepthHead.from_payload is
                # what the gate and DepthMinPredictor rebuild from.
                "motion_channels": bool(dh_cfg.get("motion_channels", False)),
                "scale_factorized": bool(dh_cfg.get("scale_factorized", False)),
                # backbone routes build_depth_head at load time ("scratch" default
                # → _DepthHead; "da3" → DA3DepthHead). da3_arch round-trips the
                # DINOv2/DPT config so DA3DepthHead.from_payload rebuilds exactly.
                "backbone": backbone,
                "da3_arch": model.arch if backbone == "da3" else None,
                "holdout_absrel": holdout,
                "depth_cfg": dh_cfg,
                "init_ckpt": str(args.init_ckpt) if args.init_ckpt else None,
                "freeze_encoder": freeze_enc,
            },
            path,
        )
        print(f"[depth-train] wrote {path}")

    # Soft pass for the trainer process: finite descending loss + finite AbsRel.
    if not losses or not np.isfinite(losses[-1]):
        print("[depth-train] FAIL: non-finite final loss", file=sys.stderr)
        return 1
    print(f"[depth-train] OK: log={log_path} enable_flag_still={dh_cfg.get('enable')}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
