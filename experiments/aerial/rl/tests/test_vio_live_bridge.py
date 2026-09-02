"""Tests for live vio_est helpers (no OpenVINS binary required)."""
from __future__ import annotations

import numpy as np

from experiments.aerial.rl.env.obs import Observation
from experiments.aerial.vio_probe.live_bridge import sim_gt_imustate17
from experiments.aerial.rl.pose_estimate import make_pose_estimator


def test_sim_gt_imustate17_layout():
    obs = Observation(
        rgb=np.zeros((224, 224, 3), np.uint8),
        state=np.array([1.0, 2.0, 3.0, 0.1, 0.0, 0.0, 0.5], np.float32),
        t=1.25,
        imu={"ang_vel": [0, 0, 0], "lin_acc": [0, 0, 9.8]},
    )
    s = sim_gt_imustate17(obs)
    assert s.shape == (17,)
    assert abs(s[0] - 1.25) < 1e-9
    np.testing.assert_allclose(s[5:8], [1.0, 2.0, 3.0])


def test_make_pose_estimator_live_flag(monkeypatch):
    monkeypatch.setenv("AERIAL_VIO_LIVE", "1")
    monkeypatch.delenv("AERIAL_VIO_TRAJ", raising=False)
    # Construction needs binary — expect RuntimeError without ov_stream_online
    try:
        make_pose_estimator("vio_est")
    except RuntimeError as e:
        assert "ov_stream_online" in str(e) or "OPENVINS_STREAM" in str(e)
    else:
        # If binary exists locally, ok
        pass
