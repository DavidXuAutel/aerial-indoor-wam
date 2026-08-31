"""Imagination aux pass-through for torch reward head (V4 reward-head fix)."""
import numpy as np
import pytest

torch = pytest.importorskip("torch")

from experiments.aerial.rl.dynamics_torch import TorchRSSMDynamics  # noqa: E402
from experiments.aerial.rl.env.obs import Observation  # noqa: E402
from experiments.aerial.rl.imagination import imagine  # noqa: E402


class _FixedActionPolicy:
    def __init__(self, action):
        self._action = np.asarray(action, dtype=np.float64)

    def act_latent(self, z):
        return self._action.copy()


class _ZeroPolicy:
    def act_latent(self, z):
        return np.zeros(4, dtype=np.float64)


def _obs(pos=(0.0, 0.0, 0.0), goal=(10.0, 0.0, 0.0)):
    state = np.array([pos[0], pos[1], pos[2], 0.0, 0.0, 0.0, 0.0], dtype=np.float32)
    return Observation(
        rgb=np.zeros((16, 16, 3), np.uint8),
        state=state,
        info={"goal": np.asarray(goal, dtype=np.float32)},
    )


def _tiny_torch_wm():
    return TorchRSSMDynamics(
        image_size=16, recurrent_dim=16, stoch_dim=4, stoch_classes=4,
        hidden_dim=16, num_bins=41, device="cpu", torch_dtype=torch.float32,
    )


def test_imagine_aux_progress_is_analytic_delta_goal_norm():
    """R1: aux path progress = analytic_progress(g, a[:3]), not RH readout."""
    m = _tiny_torch_wm()
    z = m.encode(_obs())
    z0 = z[None, :]
    g1 = np.array([[10.0, 0.0, 0.0, 10.0]], dtype=np.float32)
    v = np.array([[0.0, 0.0, 0.0]], dtype=np.float32)

    roll_fwd = imagine(
        m, _FixedActionPolicy([1.0, 0.0, 0.0, 0.0]), z0, horizon=1,
        goal_rel0=g1, body_vel0=v,
    )
    assert roll_fwd.progress[0, 0] == pytest.approx(1.0, abs=1e-5)

    roll_ret = imagine(
        m, _FixedActionPolicy([-1.0, 0.0, 0.0, 0.0]), z0, horizon=1,
        goal_rel0=g1, body_vel0=v,
    )
    assert roll_ret.progress[0, 0] == pytest.approx(-1.0, abs=1e-5)

    g2 = np.array([[0.0, 8.0, 0.0, 8.0]], dtype=np.float32)
    roll_zero = imagine(m, _ZeroPolicy(), z0, horizon=1, goal_rel0=g2, body_vel0=v)
    assert roll_zero.progress[0, 0] == pytest.approx(0.0, abs=1e-5)

    roll_zero_g1 = imagine(m, _ZeroPolicy(), z0, horizon=1, goal_rel0=g1, body_vel0=v)
    assert roll_zero_g1.progress[0, 0] == pytest.approx(0.0, abs=1e-5)


def test_imagine_aux_p_coll_still_from_dynamics_step():
    """RH p_coll must still come from dynamics.step on the aux path."""
    m = _tiny_torch_wm()
    z = m.encode(_obs())
    z0 = z[None, :]
    g0 = np.array([[10.0, 0.0, 0.0, 10.0]], dtype=np.float32)
    v = np.array([[0.0, 0.0, 0.0]], dtype=np.float32)
    a = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64)

    expected_pc = m.step(z0[0], a, goal_rel=g0[0], body_vel=v[0]).p_coll
    roll_aux = imagine(
        m, _FixedActionPolicy(a), z0, horizon=1,
        goal_rel0=g0, body_vel0=v,
    )
    assert roll_aux.p_coll[0, 0] == pytest.approx(expected_pc, rel=0, abs=1e-6)
