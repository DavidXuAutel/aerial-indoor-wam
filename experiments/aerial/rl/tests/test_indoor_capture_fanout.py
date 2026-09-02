"""Unit tests for single-grab RGB fan-out (VIO / WAM / YOLO)."""
from __future__ import annotations

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")

from experiments.aerial.rl.indoor_capture import fanout_rgb


def test_fanout_rgb_shapes():
    cap = np.zeros((480, 640, 3), dtype=np.uint8)
    cap[10, 20] = (1, 2, 3)
    wam, vio, yolo = fanout_rgb(cap, wam_size=224, yolo_wh=None)
    assert wam.shape == (224, 224, 3)
    assert vio.shape == (480, 640, 3)
    assert yolo.shape == (480, 640, 3)
    assert vio is not wam
    np.testing.assert_array_equal(vio[10, 20], (1, 2, 3))


def test_fanout_yolo_resize():
    cap = np.zeros((480, 640, 3), dtype=np.uint8)
    _, _, yolo = fanout_rgb(cap, wam_size=224, yolo_wh=(320, 320))
    assert yolo.shape == (320, 320, 3)
