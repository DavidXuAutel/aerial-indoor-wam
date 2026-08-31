"""``_wm_train_validate`` provenance sidecar (①a–c auditability).

A bare ``wm_train.jsonl`` carries only loss/recon/entropy, so a curve on disk
cannot evidence WHICH corpus produced it. That gap is what disqualified
``wm_ckpt_v2clean_20260810`` as ①a–c evidence: its numbers clear the frozen §4.1
thresholds decisively (loss 16.80→1.49, recon 0.3245→0.0282, min_ent 0.4368) yet
nothing on disk rules out the dt-desynced July V0 corpus waved through with
``--allow-v0-desync``. These tests pin the sidecar that closes it.

Module skipped off-H100 — ``_wm_train_validate`` imports torch at module top.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

pytest.importorskip("torch")  # noqa: E402  (skip whole module off-H100)

from experiments.aerial.rl import _wm_train_validate as wmv  # noqa: E402


class _FakeBuf:
    num_episodes = 7
    num_transitions = 913


def _args(**over) -> argparse.Namespace:
    base = dict(
        allow_v0_desync=False, steps=500, window=8, wm_batch=16,
        config="configs/aerial_rl.yaml", heldout_frac=0.0,
    )
    base.update(over)
    return argparse.Namespace(**base)


def _write_manifest(root: Path, **meta) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "manifest.json").write_text(json.dumps({"meta": meta}))


def test_meta_records_dataset_and_marks_authoritative(tmp_path: Path) -> None:
    root = tmp_path / "dataset_v1_rgb"
    _write_manifest(root, step_hz=8.0, grab_depth=False)
    ckpt = tmp_path / "wm_ckpt_test"
    ckpt.mkdir()

    path = wmv._write_train_meta(
        ckpt, root=root, args=_args(), buf=_FakeBuf(), image_size=224
    )

    meta = json.loads(path.read_text())
    assert path.name == "wm_train_meta.json"
    assert meta["dataset"] == str(root.resolve())
    assert meta["dataset_manifest_meta"]["step_hz"] == 8.0
    assert meta["allow_v0_desync"] is False
    assert meta["authoritative"] is True
    assert meta["episodes"] == 7 and meta["transitions"] == 913
    assert meta["steps"] == 500 and meta["window"] == 8
    assert meta["heldout_frac"] == 0.0


def test_meta_records_heldout_frac(tmp_path: Path) -> None:
    root = tmp_path / "dataset_v1_rgb"
    _write_manifest(root, step_hz=5.0, grab_depth=True)
    ckpt = tmp_path / "wm_ckpt_heldout"
    ckpt.mkdir()

    path = wmv._write_train_meta(
        ckpt, root=root, args=_args(heldout_frac=0.25), buf=_FakeBuf(), image_size=224
    )
    meta = json.loads(path.read_text())
    assert meta["heldout_frac"] == 0.25
    assert meta["authoritative"] is True


def test_allow_v0_desync_disqualifies_as_authoritative(tmp_path: Path) -> None:
    """The escape hatch is documented "only to exercise the code path" — a run that
    used it must never read as authoritative ①a–c evidence."""
    root = tmp_path / "dataset_v0"
    _write_manifest(root, step_hz=12.0, grab_depth=False)
    ckpt = tmp_path / "ckpt"
    ckpt.mkdir()

    path = wmv._write_train_meta(
        ckpt, root=root, args=_args(allow_v0_desync=True), buf=_FakeBuf(), image_size=224
    )

    meta = json.loads(path.read_text())
    assert meta["allow_v0_desync"] is True
    assert meta["authoritative"] is False
    # The desynced label is preserved verbatim so the disqualification is evidenced.
    assert meta["dataset_manifest_meta"]["step_hz"] == 12.0


def test_missing_manifest_does_not_raise(tmp_path: Path) -> None:
    """Provenance is best-effort: a corpus without manifest.json must still train."""
    root = tmp_path / "no_manifest"
    root.mkdir()
    ckpt = tmp_path / "ckpt"
    ckpt.mkdir()

    meta = json.loads(
        wmv._write_train_meta(
            ckpt, root=root, args=_args(), buf=_FakeBuf(), image_size=224
        ).read_text()
    )
    assert meta["dataset_manifest_meta"] == {}
    assert meta["authoritative"] is True


def test_sidecar_does_not_shadow_the_gate_log(tmp_path: Path) -> None:
    """①a–c parses wm_train.jsonl only — the sidecar must not collide with it."""
    root = tmp_path / "ds"
    _write_manifest(root, step_hz=8.0)
    ckpt = tmp_path / "ckpt"
    ckpt.mkdir()
    (ckpt / "wm_train.jsonl").write_text(
        json.dumps({"step": 0, "loss": 1.0, "recon_err": 0.1, "post_entropy_frac": 0.4})
        + "\n"
    )

    wmv._write_train_meta(ckpt, root=root, args=_args(), buf=_FakeBuf(), image_size=224)

    rows = [
        json.loads(l)
        for l in (ckpt / "wm_train.jsonl").read_text().splitlines()
        if l.strip()
    ]
    assert len(rows) == 1 and rows[0]["loss"] == 1.0
