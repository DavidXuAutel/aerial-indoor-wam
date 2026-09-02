"""Indoor RGB: **one camera grab**, then fan-out to consumers.

Not dual cameras. Not flipping CaptureSettings between sizes.

::

    AirSim Scene (single cam, capture WH e.g. 640×480)
            │
            ├─→ VIO / OpenVINS     ``rgb_vio``   (native capture)
            ├─→ WAM / FastWAM      ``rgb``       (resize → 224)
            └─→ YOLO (side branch) ``rgb_yolo``  (native or detector size)

Capture resolution lives in AirSim ``CaptureSettings`` / ``INDOOR_CAPTURE_*``.
WAM encode size is always ``WAM_ENCODE_SIZE`` (224) derived **after** the grab.
"""
from __future__ import annotations

import os
from typing import Optional, Tuple

import numpy as np

# Single-camera sensing resolution (AirSim CaptureSettings).
INDOOR_CAPTURE_W = int(os.environ.get("INDOOR_CAPTURE_W", "640"))
INDOOR_CAPTURE_H = int(os.environ.get("INDOOR_CAPTURE_H", "480"))

# Policy / WM branch size (FastWAM image_size).
WAM_ENCODE_SIZE = int(os.environ.get("WAM_ENCODE_SIZE", "224"))

# Optional YOLO branch size; None = keep native capture pixels.
_YOLO_W = os.environ.get("INDOOR_YOLO_W", "").strip()
_YOLO_H = os.environ.get("INDOOR_YOLO_H", "").strip()
YOLO_WH: Optional[Tuple[int, int]] = (
    (int(_YOLO_W), int(_YOLO_H)) if _YOLO_W and _YOLO_H else None
)


def indoor_capture_wh() -> Tuple[int, int]:
    return (INDOOR_CAPTURE_W, INDOOR_CAPTURE_H)


def wam_encode_wh() -> Tuple[int, int]:
    return (WAM_ENCODE_SIZE, WAM_ENCODE_SIZE)


def fanout_rgb(
    capture_rgb: np.ndarray,
    *,
    wam_size: int = WAM_ENCODE_SIZE,
    yolo_wh: Optional[Tuple[int, int]] = YOLO_WH,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Split one capture into (rgb_wam, rgb_vio, rgb_yolo).

    ``rgb_vio`` is the capture (contiguous copy). ``rgb_wam`` is resized to
    ``wam_size²``. ``rgb_yolo`` is native or resized to ``yolo_wh`` if set.
    """
    import cv2  # lazy: AirSim hosts have it; unit tests may mock

    cap = np.ascontiguousarray(np.asarray(capture_rgb, dtype=np.uint8))
    rgb_vio = cap
    h, w = int(cap.shape[0]), int(cap.shape[1])
    if (h, w) != (wam_size, wam_size):
        rgb_wam = np.ascontiguousarray(
            cv2.resize(cap, (wam_size, wam_size), interpolation=cv2.INTER_AREA),
            dtype=np.uint8,
        )
    else:
        rgb_wam = cap.copy()
    if yolo_wh is None:
        rgb_yolo = cap.copy()
    else:
        yw, yh = int(yolo_wh[0]), int(yolo_wh[1])
        if (w, h) != (yw, yh):
            rgb_yolo = np.ascontiguousarray(
                cv2.resize(cap, (yw, yh), interpolation=cv2.INTER_AREA),
                dtype=np.uint8,
            )
        else:
            rgb_yolo = cap.copy()
    return rgb_wam, rgb_vio, rgb_yolo
