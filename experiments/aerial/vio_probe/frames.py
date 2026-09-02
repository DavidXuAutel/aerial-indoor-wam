"""AirSim / stack / OpenVINS frame helpers.

Stack world (``airsim_env.observe_state``): AirSim NED **x,y kept**, **z negated**
→ **NEU** (north, east, up). Not full ROS ENU (which would also swap/flip y).

AirSim IMU API: **NED body** (x forward, y right, z down).

OpenVINS model (``Propagator``): ``v_dot = Rᵀ â − g`` with ``g = [0,0,+g]``,
so a **level** IMU at rest needs ``â ≈ [0,0,+g]``.

Therefore convert NED-body IMU → NEU-body by **flipping z only**:
``[wx,wy,wz] → [wx,wy,-wz]``, ``[ax,ay,az] → [ax,ay,-az]``.
(Do **not** flip y — that was an over-conversion to ROS ENU and wrecked lateral.)
"""
from __future__ import annotations

from typing import List, Tuple

import numpy as np

# NEU body ← NED body (match stack: flip z only)
_R_NED_TO_NEU = np.diag([1.0, 1.0, -1.0])


def ned_body_to_neu_body(vec3: np.ndarray) -> np.ndarray:
    v = np.asarray(vec3, dtype=np.float64).reshape(3)
    return _R_NED_TO_NEU @ v


def convert_airsim_imu_to_openvins(
    ang_vel_ned: np.ndarray, lin_acc_ned: np.ndarray
) -> Tuple[np.ndarray, np.ndarray]:
    """AirSim NED body IMU → OpenVINS / stack NEU body."""
    return ned_body_to_neu_body(ang_vel_ned), ned_body_to_neu_body(lin_acc_ned)


# Back-compat alias (old name said ENU; behavior is now NEU = flip-z).
ned_body_to_enu_body = ned_body_to_neu_body
convert_airsim_imu_to_enu = convert_airsim_imu_to_openvins


# Cam: body x-fwd, y-right, z-up → EuRoC optical (x right, y down, z fwd)
# columns of R = cam axes in body: cam_x=body_y, cam_y=-body_z, cam_z=body_x
T_IMU_CAM_NEU_FORWARD: List[List[float]] = [
    [0.0, 0.0, 1.0, 0.0],
    [1.0, 0.0, 0.0, 0.0],
    [0.0, -1.0, 0.0, 0.0],
    [0.0, 0.0, 0.0, 1.0],
]

# Alias used by older callers
T_IMU_CAM_ENU_FORWARD = T_IMU_CAM_NEU_FORWARD


# --- thrifty sim self-consistency (NOT product / NOT real-robot calib) ---
# S1: synthetic hover EuRoC → drift ≈ 0 (OpenVINS plumbing)
# S2: fixture RGB/GT + hover IMU + gt-init + imu-only → ATE ≤ 5 m (no free-fall)
# AirSim ZOH IMU / live closed VIO quality are explicitly out of scope here.
SIM_ATE_RMSE_MAX_M = 5.0
SIM_CLOSED_D_HAT_MAX_M = 15.0
SIM_HOVER_DRIFT_MAX_M = 0.05
