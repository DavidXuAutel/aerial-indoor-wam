"""Isolated OpenVINS probe unit tests (no AirSim / no OpenVINS binary)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from experiments.aerial.rl.pose_estimate import make_pose_estimator
from experiments.aerial.vio_probe.ate import ate_rmse_posyaw
from experiments.aerial.vio_probe.euroc_export import (
    export_episode_npz_to_euroc,
    make_synthetic_episode_npz,
)
from experiments.aerial.vio_probe.pose_bridge import VioEstPoseEstimator
from experiments.aerial.vio_probe.traj_io import load_tum_trajectory


def test_euroc_export_and_ate_dry_run(tmp_path: Path):
    npz = make_synthetic_episode_npz(tmp_path / "ep.npz", n=20)
    euroc = tmp_path / "euroc"
    meta = export_episode_npz_to_euroc(npz, euroc)
    assert meta["n_frames"] == 20
    assert (euroc / "mav0" / "cam0" / "data.csv").is_file()
    assert (euroc / "mav0" / "imu0" / "data.csv").is_file()
    assert (euroc / "gt_tum.txt").is_file()
    t, pos, _ = load_tum_trajectory(euroc / "gt_tum.txt")
    ate = ate_rmse_posyaw(t, pos, t, pos)
    assert ate["n_pairs"] >= 2
    assert ate["ate_rmse_m"] < 1e-9


def test_vio_est_requires_traj_env(monkeypatch):
    monkeypatch.delenv("AERIAL_VIO_TRAJ", raising=False)
    with pytest.raises(RuntimeError, match="AERIAL_VIO_TRAJ"):
        make_pose_estimator("vio_est")


def test_vio_est_bridge_from_tum(tmp_path: Path, monkeypatch):
    npz = make_synthetic_episode_npz(tmp_path / "ep.npz", n=12)
    euroc = tmp_path / "euroc"
    export_episode_npz_to_euroc(npz, euroc)
    tum = euroc / "gt_tum.txt"
    monkeypatch.setenv("AERIAL_VIO_TRAJ", str(tum))
    est = make_pose_estimator("vio_est")
    assert est.pose_source == "vio_est"

    from experiments.aerial.rl.env.obs import Observation

    t, pos, _ = load_tum_trajectory(tum)
    state = np.array([0, 0, 1.8, 0, 0, 0, 0], dtype=np.float32)
    obs = Observation(rgb=np.zeros((8, 8, 3), dtype=np.uint8), state=state, t=float(t[0]))
    pe = est.reset(obs)
    assert pe.pose_source == "vio_est"
    assert float(np.linalg.norm(pe.p_hat - pos[0])) < 1e-6

    # Direct class path
    est2 = VioEstPoseEstimator(tum)
    pe2 = est2.reset(obs)
    assert pe2.pose_source == "vio_est"
