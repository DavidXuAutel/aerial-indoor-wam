"""Unit tests for AirSim NED → OpenVINS NEU (flip-z) IMU mapping."""
from __future__ import annotations

import numpy as np

from experiments.aerial.vio_probe.frames import (
    convert_airsim_imu_to_openvins,
    ned_body_to_neu_body,
)


def test_ned_rest_accel_becomes_plus_g_on_z():
    wm, am = convert_airsim_imu_to_openvins(
        np.zeros(3), np.array([0.0, 0.0, -9.81])
    )
    np.testing.assert_allclose(wm, 0.0, atol=1e-12)
    np.testing.assert_allclose(am, [0.0, 0.0, 9.81], atol=1e-12)


def test_y_not_flipped():
    v = np.array([1.0, 2.0, 3.0])
    out = ned_body_to_neu_body(v)
    np.testing.assert_allclose(out, [1.0, 2.0, -3.0])


def test_flip_z_involution():
    v = np.array([1.0, 2.0, 3.0])
    np.testing.assert_allclose(ned_body_to_neu_body(ned_body_to_neu_body(v)), v)
