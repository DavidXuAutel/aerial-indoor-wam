"""Tests for ``wm_data.windows_to_arrays`` — the replay-window → tensor adapter.

Feeds it the same ``List[List[Transition]]`` shape ``ReplayBuffer.sample_windows``
produces and checks the stacked arrays' keys/shapes/dtypes, obs-alignment, the
all-or-nothing depth channel, and rejection of empty/ragged input.
"""
import numpy as np
import pytest

from experiments.aerial.rl import wm_data
from experiments.aerial.rl.buffer import ReplayBuffer, Transition
from experiments.aerial.rl.env.obs import Observation


def _obs(x, frame_val, depth=None):
    state = np.array([float(x), 0.0, 2.0, 0.0, 0.0, 0.0, 0.1], dtype=np.float32)
    rgb = np.full((6, 8, 3), int(frame_val) % 256, dtype=np.uint8)
    return Observation(rgb=rgb, state=state, depth=depth, collided=(x == 2))


def _window(length, with_depth=False, base=0):
    w = []
    for i in range(length):
        depth = np.full((6, 8), 5.0 + i, np.float32) if with_depth else None
        obs = _obs(base + i, frame_val=10 + i * 20, depth=depth)
        w.append(Transition(obs=obs, action=np.ones(4) * (0.1 * (i + 1)),
                            reward=float(i), done=(i == length - 1)))
    return w


def test_shapes_dtypes_and_keys():
    windows = [_window(5), _window(5, base=10)]
    arr = wm_data.windows_to_arrays(windows)
    assert arr["rgb"].shape == (2, 5, 6, 8, 3) and arr["rgb"].dtype == np.uint8
    assert arr["proprio"].shape == (2, 5, 4) and arr["proprio"].dtype == np.float32
    assert arr["action"].shape == (2, 5, 4) and arr["action"].dtype == np.float32
    assert arr["reward"].shape == (2, 5) and arr["reward"].dtype == np.float32
    assert arr["done"].shape == (2, 5) and arr["done"].dtype == np.bool_
    assert arr["collided"].shape == (2, 5) and arr["collided"].dtype == np.bool_
    assert arr["goal_rel"].shape == (2, 5, 4) and arr["goal_rel"].dtype == np.float32
    assert arr["body_vel"].shape == (2, 5, 3) and arr["body_vel"].dtype == np.float32
    # fixtures without goal → zeros; velocity from state is present
    assert np.allclose(arr["goal_rel"], 0.0)
    assert "depth" not in arr


def test_goal_rel_from_obs_info():
    windows = [_window(3)]
    goal = np.array([10.0, 0.0, 2.0], dtype=np.float32)
    for tr in windows[0]:
        tr.obs.info["goal"] = goal.copy()
    arr = wm_data.windows_to_arrays(windows)
    # at x=0, yaw~0.1: remaining dist to (10,0,2) ≈ 10
    assert arr["goal_rel"][0, 0, 3] > 9.0
    assert arr["goal_rel"][0, 2, 3] < arr["goal_rel"][0, 0, 3]

def test_obs_alignment():
    windows = [_window(4)]
    arr = wm_data.windows_to_arrays(windows)
    # proprio x-coordinate follows the per-step position 0,1,2,3
    np.testing.assert_allclose(arr["proprio"][0, :, 0], [0, 1, 2, 3])
    # reward = step index; done only on the last frame
    np.testing.assert_allclose(arr["reward"][0], [0, 1, 2, 3])
    assert arr["done"][0].tolist() == [False, False, False, True]
    # collided flagged at x==2 (third frame)
    assert arr["collided"][0].tolist() == [False, False, True, False]
    # action grows with step (0.1, 0.2, ...)
    np.testing.assert_allclose(arr["action"][0, :, 0], [0.1, 0.2, 0.3, 0.4], rtol=1e-6)


def test_depth_present_only_when_every_frame_has_it():
    both = [_window(3, with_depth=True), _window(3, with_depth=True, base=10)]
    assert "depth" in wm_data.windows_to_arrays(both)
    assert wm_data.windows_to_arrays(both)["depth"].shape == (2, 3, 6, 8)
    # one window without depth -> whole channel dropped
    mixed = [_window(3, with_depth=True), _window(3, with_depth=False, base=10)]
    assert "depth" not in wm_data.windows_to_arrays(mixed)


def test_empty_raises():
    with pytest.raises(ValueError):
        wm_data.windows_to_arrays([])


def test_ragged_windows_raise():
    with pytest.raises(ValueError):
        wm_data.windows_to_arrays([_window(5), _window(4, base=10)])


def test_integrates_with_buffer_sample_windows():
    # end-to-end: a real ReplayBuffer window batch stacks cleanly
    buf = ReplayBuffer(capacity_episodes=8, seed=1)
    for e in range(4):
        buf.add_episode(_window(6, base=e * 10))
    windows = buf.sample_windows(batch=3, length=4)
    arr = wm_data.windows_to_arrays(windows)
    assert arr["rgb"].shape == (3, 4, 6, 8, 3)
    assert arr["action"].shape == (3, 4, 4)
