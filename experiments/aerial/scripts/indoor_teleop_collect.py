#!/usr/bin/env python3
"""Indoor teleop collector — GUI-first on 125 local seat.

Records RGB + proprio + body-delta actions → NPZ (same schema as fixture collect).
Declared assist=teleop — NOT mainline completion.

Primary control is the OpenCV window ``teleop_ego`` (keyboard + mouse).
TTY keys still work as a fallback when stdin is a real terminal.

Keys (focus the teleop_ego window):
  w/s  forward / back          a/d  left / right (body)
  r/f  up / down               q/e  yaw left / right
  space  hover (zero cmd)
  n / x  reset / discard episode
  enter  SAVE if arrived & not collided
  esc    quit

Mouse:
  Click START to begin an episode (spawn + record).
  Click END to finish (save if arrived, else discard).
  Click on-screen WASD/RF/QE caps to move (same as keys).

Example (on 125 console / GNOME terminal):
  source experiments/aerial/scripts/env_4090.sh
  export DISPLAY=:1
  export AIRSIM_CAMERA=0 AIRSIM_VEHICLE=drone_1
  $AERIAL_PY experiments/aerial/scripts/indoor_teleop_collect.py \\
    --route-idx 5 --success-dist 0.25 \\
    --out experiments/aerial/rl/artifacts/dataset_indoor_b99_teleop_r06_e_20260901
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import os
import select
import sys
import termios
import time
import tty
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("indoor_teleop")

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

WIN = "opencv_control"  # sole control surface — ignore UE window

def _downscale_transitions_rgb(transitions: List[Any], size: Tuple[int, int] = (224, 224)) -> None:
    """Resize RGB to policy size before NPZ write (display may be hi-res)."""
    import cv2

    tw, th = size
    for t in transitions:
        for attr in ("obs", "next_obs"):
            o = getattr(t, attr, None)
            if o is None or getattr(o, "rgb", None) is None:
                continue
            rgb = np.asarray(o.rgb)
            if rgb.ndim == 3 and (rgb.shape[1], rgb.shape[0]) != (tw, th):
                o.rgb = np.ascontiguousarray(
                    cv2.resize(rgb, (tw, th), interpolation=cv2.INTER_AREA),
                    dtype=np.uint8,
                )


HELP = """
========== OpenCV CONTROL (window: opencv_control) ==========
  Ignore the UE/Building_99 window — fly ONLY in OpenCV.
  Mouse: START begin  |  END finish (save if arrived)
  Click WASD / R F / Q E on-screen, or type with this window focused
  Goal: cyan TARGET reticle when goal is ahead (no path trail)
=============================================================
"""

# OpenCV waitKey codes (Qt/GTK vary slightly; cover common)
_CV_KEYMAP = {
    ord("w"): "w",
    ord("W"): "w",
    ord("s"): "s",
    ord("S"): "s",
    ord("a"): "a",
    ord("A"): "a",
    ord("d"): "d",
    ord("D"): "d",
    ord("r"): "r",
    ord("R"): "r",
    ord("f"): "f",
    ord("F"): "f",
    ord("q"): "q",
    ord("Q"): "q",
    ord("e"): "e",
    ord("E"): "e",
    ord("n"): "n",
    ord("N"): "n",
    ord("x"): "x",
    ord("X"): "x",
    ord("h"): "h",
    ord("H"): "h",
    ord(" "): "space",
    13: "enter",  # Enter
    10: "enter",
    27: "esc",  # Esc
}


class TtyKeys:
    """Optional non-blocking TTY reader (fallback if window unfocused)."""

    def __init__(self) -> None:
        self.enabled = False
        self.fd = -1
        self.old = None
        if not sys.stdin.isatty():
            logger.warning("stdin is not a TTY — use opencv_control window keys/mouse only")
            return
        try:
            self.fd = sys.stdin.fileno()
            self.old = termios.tcgetattr(self.fd)
            tty.setcbreak(self.fd)
            self.enabled = True
        except Exception as exc:
            logger.warning("TTY keys unavailable (%s) — use GUI", exc)

    def close(self) -> None:
        if self.enabled and self.old is not None:
            try:
                termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old)
            except Exception:
                pass
            self.enabled = False

    def drain(self) -> Set[str]:
        keys: Set[str] = set()
        if not self.enabled:
            return keys
        while True:
            r, _, _ = select.select([self.fd], [], [], 0.0)
            if not r:
                break
            ch = os.read(self.fd, 1)
            if not ch:
                break
            if ch == b"\x1b":
                r2, _, _ = select.select([self.fd], [], [], 0.02)
                if r2:
                    os.read(self.fd, 8)
                else:
                    keys.add("esc")
                continue
            if ch in (b"\n", b"\r"):
                keys.add("enter")
                continue
            if ch == b" ":
                keys.add("space")
                continue
            try:
                keys.add(ch.decode("utf-8", errors="ignore").lower())
            except Exception:
                pass
        return keys


def keys_to_action(keys: Set[str], limits: np.ndarray, held: Dict[str, float]) -> np.ndarray:
    """Latch keys for a short hold so taps still produce motion."""
    now = time.time()
    for k in ("w", "s", "a", "d", "r", "f", "q", "e"):
        if k in keys:
            held[k] = now + 0.25
    if "space" in keys:
        held.clear()
    a = np.zeros(4, dtype=np.float64)
    lim = np.asarray(limits, dtype=np.float64)
    if held.get("w", 0) > now:
        a[0] += lim[0]
    if held.get("s", 0) > now:
        a[0] -= lim[0]
    if held.get("a", 0) > now:
        a[1] -= lim[1]
    if held.get("d", 0) > now:
        a[1] += lim[1]
    if held.get("r", 0) > now:
        a[2] += lim[2]
    if held.get("f", 0) > now:
        a[2] -= lim[2]
    if held.get("q", 0) > now:
        a[3] -= lim[3]
    if held.get("e", 0) > now:
        a[3] += lim[3]
    a[:3] = np.clip(a[:3], -lim[:3], lim[:3])
    a[3] = float(np.clip(a[3], -lim[3], lim[3]))
    return a


def _user_vertical_active(held: Dict[str, float], keys: Set[str]) -> bool:
    now = time.time()
    return ("r" in keys) or ("f" in keys) or (held.get("r", 0) > now) or (held.get("f", 0) > now)


def _pullback_goal(start: np.ndarray, goal: np.ndarray, pullback_m: float) -> np.ndarray:
    """Move goal toward start so the success ball sits farther from far-side furniture."""
    if pullback_m <= 0:
        return np.asarray(goal, dtype=np.float64).copy()
    s = np.asarray(start, dtype=np.float64).reshape(3)
    g = np.asarray(goal, dtype=np.float64).reshape(3)
    vec = g - s
    dist = float(np.linalg.norm(vec))
    if dist <= pullback_m + 0.4:
        return g
    g2 = g - (vec / dist) * float(pullback_m)
    g2[2] = s[2]  # keep cruise altitude
    return g2


def _load_route(ann: Path, route_idx: int) -> Dict[str, Any]:
    routes = json.loads(ann.read_text(encoding="utf-8"))
    if route_idx < 0 or route_idx >= len(routes):
        raise SystemExit(f"route_idx {route_idx} out of range (n={len(routes)})")
    r = routes[route_idx]
    pos = np.asarray(r["pos"], dtype=np.float64)
    yaw = np.asarray(r["yaw"], dtype=np.float64).reshape(-1)
    start, goal = pos[0], pos[-1]
    return {
        "source_route_idx": route_idx,
        "route_name": r.get("trajectory_id", f"Route_{route_idx + 1:02d}"),
        "segment_name": f"Teleop_{r.get('trajectory_id', f'R{route_idx+1:02d}')}",
        "pos": [start.tolist(), goal.tolist()],
        "yaw": [float(yaw[0]), float(yaw[min(len(yaw) - 1, len(pos) - 1)])],
        "d0_m": round(float(np.linalg.norm(goal - start)), 3),
        "gpt_instruction": r.get("gpt_instruction", "teleop indoor"),
        "goal": goal,
        "goal_raw": goal.copy(),
    }


class TeleopGui:
    """OpenCV HUD: key legend, clickable caps, START/END buttons, key+mouse input."""

    def __init__(self) -> None:
        import cv2

        self.cv2 = cv2
        self.clicks: List[str] = []
        self._btn_rects: Dict[str, Tuple[int, int, int, int]] = {}
        self._cap_rects: Dict[str, Tuple[int, int, int, int]] = {}
        self._ready = False
        self._last_size = (960, 720)
        if not os.environ.get("DISPLAY"):
            raise RuntimeError("DISPLAY unset — export DISPLAY=:1 on 125 GNOME seat")
        cv2.namedWindow(WIN, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(WIN, 1280, 720)
        try:
            cv2.setWindowProperty(WIN, cv2.WND_PROP_TOPMOST, 1)
        except Exception:
            pass
        cv2.setMouseCallback(WIN, self._on_mouse)
        blank = np.zeros((720, 1280, 3), dtype=np.uint8)
        blank[:] = (28, 28, 28)
        cv2.putText(
            blank,
            "OpenCV CONTROL — click START (ignore UE window)",
            (160, 360),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (0, 220, 255),
            2,
            cv2.LINE_AA,
        )
        cv2.imshow(WIN, blank)
        cv2.waitKey(1)
        self._ready = True
        logger.info("GUI ready window=%s DISPLAY=%s (control ONLY here)", WIN, os.environ.get("DISPLAY"))

    def _on_mouse(self, event: int, x: int, y: int, flags: int, param: Any) -> None:
        if event != self.cv2.EVENT_LBUTTONDOWN:
            return
        for name, (x0, y0, x1, y1) in self._btn_rects.items():
            if x0 <= x <= x1 and y0 <= y <= y1:
                self.clicks.append(name)
                return
        for name, (x0, y0, x1, y1) in self._cap_rects.items():
            if x0 <= x <= x1 and y0 <= y <= y1:
                self.clicks.append(name)
                return

    def poll_keys(self, wait_ms: int = 30) -> Set[str]:
        """Drain OpenCV key queue + pending mouse clicks."""
        keys: Set[str] = set()
        # Multiple waitKey peeks: mouse events need the event loop
        deadline = time.time() + max(wait_ms, 1) / 1000.0
        while True:
            remaining = max(1, int((deadline - time.time()) * 1000))
            code = self.cv2.waitKey(remaining if remaining < wait_ms else wait_ms) & 0xFF
            if code != 255 and code != 0:
                mapped = _CV_KEYMAP.get(code)
                if mapped:
                    keys.add(mapped)
                elif 32 <= code < 127:
                    keys.add(chr(code).lower())
            if time.time() >= deadline:
                break
            wait_ms = 1
        for c in self.clicks:
            keys.add(c)
        self.clicks.clear()
        return keys

    def _draw_keycap(
        self,
        frame: np.ndarray,
        xy: Tuple[int, int],
        label: str,
        key_id: str,
        active: bool,
    ) -> None:
        cv2 = self.cv2
        x, y = xy
        tw = max(48, 14 + 14 * len(label))
        th = 36
        bg = (40, 180, 40) if active else (45, 45, 45)
        edge = (240, 240, 240) if active else (160, 160, 160)
        cv2.rectangle(frame, (x, y), (x + tw, y + th), bg, -1)
        cv2.rectangle(frame, (x, y), (x + tw, y + th), edge, 2)
        cv2.putText(
            frame,
            label,
            (x + 10, y + 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        self._cap_rects[key_id] = (x, y, x + tw, y + th)

    def _draw_button(
        self,
        frame: np.ndarray,
        rect: Tuple[int, int, int, int],
        label: str,
        btn_id: str,
        *,
        fill: Tuple[int, int, int],
        enabled: bool = True,
    ) -> None:
        cv2 = self.cv2
        x0, y0, x1, y1 = rect
        bg = fill if enabled else (70, 70, 70)
        cv2.rectangle(frame, (x0, y0), (x1, y1), bg, -1)
        cv2.rectangle(frame, (x0, y0), (x1, y1), (240, 240, 240), 2)
        tw = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.85, 2)[0][0]
        tx = x0 + (x1 - x0 - tw) // 2
        ty = y0 + (y1 - y0) // 2 + 10
        cv2.putText(frame, label, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (255, 255, 255), 2, cv2.LINE_AA)
        if enabled:
            self._btn_rects[btn_id] = rect

    def _goal_body(
        self, pos: np.ndarray, yaw: float, goal: np.ndarray
    ) -> Tuple[float, float, float, float, float]:
        """Return (fwd, right, up, bearing_rad, horiz_m) in body frame."""
        dx = float(goal[0] - pos[0])
        dy = float(goal[1] - pos[1])
        up = float(goal[2] - pos[2])
        c, s = math.cos(yaw), math.sin(yaw)
        fwd = c * dx + s * dy
        right = -s * dx + c * dy
        bearing = math.atan2(right, fwd)
        horiz = math.hypot(dx, dy)
        return fwd, right, up, bearing, horiz

    def _draw_goal_hud(
        self,
        frame: np.ndarray,
        *,
        pos: np.ndarray,
        yaw: float,
        goal: np.ndarray,
        d_end: float,
        success: float,
        arrived: bool,
        start: Optional[np.ndarray] = None,
    ) -> None:
        """Goal bearing arrow + on-image TARGET reticle (no path / mini-map)."""
        cv2 = self.cv2
        h, w = frame.shape[:2]
        fwd, right, up, bearing, _horiz = self._goal_body(pos, yaw, goal)
        gcol = (80, 255, 80) if arrived else (0, 200, 255)  # BGR cyan/green

        # Compact bearing chip (top-center) — does not cover ego view center
        chip_w, chip_h = 420, 70
        cx0 = (w - chip_w) // 2
        cy0 = 58
        chip = frame.copy()
        cv2.rectangle(chip, (cx0, cy0), (cx0 + chip_w, cy0 + chip_h), (0, 0, 0), -1)
        cv2.addWeighted(chip, 0.55, frame, 0.45, 0, frame)
        cv2.putText(
            frame,
            f"GOAL {d_end:.2f}m   brg {math.degrees(bearing):+.0f}deg",
            (cx0 + 16, cy0 + 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.75,
            gcol,
            2,
            cv2.LINE_AA,
        )
        cv2.putText(
            frame,
            f"fwd {fwd:+.2f}  R {right:+.2f}  dZ {up:+.2f}",
            (cx0 + 16, cy0 + 55),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (230, 230, 230),
            1,
            cv2.LINE_AA,
        )
        # Small bearing tick on chip
        mid = cx0 + chip_w // 2
        ex = int(mid + 50 * math.sin(bearing))
        ey = int(cy0 + 38 - 22 * math.cos(bearing))
        cv2.arrowedLine(frame, (mid, cy0 + 38), (ex, ey), gcol, 2, tipLength=0.4)

        # Project goal into image if in front (~90deg HFOV pinhole)
        if fwd > 0.15:
            hfov = math.radians(90.0)
            fx = (w / 2.0) / math.tan(hfov / 2.0)
            fy = fx
            u = int(w / 2.0 + fx * (right / fwd))
            v = int(h / 2.0 - fy * (up / fwd))
            if 40 < u < w - 40 and 90 < v < h - 80:
                r_outer = max(24, int(140 / max(d_end, 0.4)))
                cv2.circle(frame, (u, v), r_outer, gcol, 3, cv2.LINE_AA)
                cv2.circle(frame, (u, v), max(5, r_outer // 4), gcol, -1, cv2.LINE_AA)
                cv2.drawMarker(frame, (u, v), gcol, cv2.MARKER_CROSS, r_outer + 14, 2)
                cv2.putText(
                    frame,
                    "TARGET",
                    (u - 42, v - r_outer - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.65,
                    gcol,
                    2,
                    cv2.LINE_AA,
                )
                if d_end <= success * 2:
                    cv2.circle(frame, (u, v), r_outer + 16, (80, 255, 80), 2, cv2.LINE_AA)

    def render(
        self,
        obs: Optional[Any],
        *,
        d_end: float,
        success: float,
        coll: bool,
        step_i: int,
        flying: bool,
        goal: Optional[np.ndarray] = None,
        start: Optional[np.ndarray] = None,
        pressed: Optional[Set[str]] = None,
        held: Optional[Dict[str, float]] = None,
        usable_n: int = 0,
        min_usable: int = 8,
        hint: str = "",
    ) -> None:
        cv2 = self.cv2
        self._btn_rects.clear()
        self._cap_rects.clear()

        if obs is not None and getattr(obs, "rgb", None) is not None:
            # Prefer native capture branch for the pilot UI (WAM rgb is 224).
            rgb = getattr(obs, "rgb_vio", None)
            if rgb is None:
                rgb = np.asarray(obs.rgb)
            else:
                rgb = np.asarray(rgb)
            if rgb.ndim == 3:
                frame = np.ascontiguousarray(rgb[:, :, ::-1])
            else:
                frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        else:
            frame = np.zeros((720, 1280, 3), dtype=np.uint8)
            frame[:] = (36, 36, 36)

        h0, w0 = frame.shape[:2]
        # Native hi-res preferred; only upscale if still small (legacy 224)
        if h0 < 640:
            scale = max(2, int(np.ceil(720 / max(h0, 1))))
            frame = cv2.resize(frame, (w0 * scale, h0 * scale), interpolation=cv2.INTER_LINEAR)
        elif h0 > 1080:
            scale = 1080 / h0
            frame = cv2.resize(
                frame,
                (int(w0 * scale), int(h0 * scale)),
                interpolation=cv2.INTER_AREA,
            )
        h, w = frame.shape[:2]
        self._last_size = (w, h)
        try:
            cv2.resizeWindow(WIN, w, h)
        except Exception:
            pass

        # Top status
        bar_h = 52
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, bar_h), (0, 0, 0), -1)
        arrived = flying and d_end <= success and not coll
        if not flying:
            mode = "IDLE — click START"
            color = (0, 220, 255)
        elif coll:
            mode = "COLLIDED — click END or RESET"
            color = (0, 80, 255)
        elif arrived:
            mode = "ARRIVED — click END / Enter to SAVE"
            color = (80, 255, 80)
        else:
            mode = "FLYING"
            color = (230, 230, 230)
        status = (
            f"step={step_i}  d={d_end:.2f}m  need<={success:.2f}m  "
            f"usable={usable_n}/{min_usable}  {mode}"
        )
        if obs is not None:
            try:
                z = float(np.asarray(obs.position)[2])
                status += f"  z={z:.2f}m"
            except Exception:
                pass
        cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)
        cv2.putText(frame, status, (14, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2, cv2.LINE_AA)

        # Goal target overlay (reticle / arrow / map)
        if goal is not None and obs is not None:
            try:
                pos = np.asarray(obs.position, dtype=np.float64).reshape(3)
                yaw = float(obs.yaw)
                self._draw_goal_hud(
                    frame,
                    pos=pos,
                    yaw=yaw,
                    goal=np.asarray(goal, dtype=np.float64).reshape(3),
                    d_end=d_end,
                    success=success,
                    arrived=arrived,
                    start=start,
                )
            except Exception as exc:
                logger.debug("goal hud skip: %s", exc)

        # START / END buttons (top-right)
        bw, bh, gap = 150, 48, 12
        end_rect = (w - bw - 16, 60, w - 16, 60 + bh)
        start_rect = (w - 2 * bw - gap - 16, 60, w - bw - gap - 16, 60 + bh)
        self._draw_button(
            frame,
            start_rect,
            "START",
            "start",
            fill=(40, 160, 60),
            enabled=not flying,
        )
        self._draw_button(
            frame,
            end_rect,
            "END",
            "end",
            fill=(40, 40, 200) if arrived else (50, 90, 200),
            enabled=flying,
        )

        # Key panel bottom-left
        panel_w, panel_h = 360, 280
        x0, y0 = 12, h - panel_h - 12
        panel = frame.copy()
        cv2.rectangle(panel, (x0, y0), (x0 + panel_w, y0 + panel_h), (12, 12, 12), -1)
        cv2.rectangle(panel, (x0, y0), (x0 + panel_w, y0 + panel_h), (100, 100, 100), 2)
        cv2.addWeighted(panel, 0.82, frame, 0.18, 0, frame)
        cv2.putText(
            frame,
            "OpenCV keys (this window only)",
            (x0 + 12, y0 + 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (0, 220, 255),
            2,
            cv2.LINE_AA,
        )

        now = time.time()
        pressed = pressed or set()
        held = held or {}
        active = set(pressed)
        for k in ("w", "s", "a", "d", "r", "f", "q", "e"):
            if held.get(k, 0) > now:
                active.add(k)

        base_x, base_y = x0 + 20, y0 + 48
        self._draw_keycap(frame, (base_x + 56, base_y), "W", "w", "w" in active)
        self._draw_keycap(frame, (base_x, base_y + 42), "A", "a", "a" in active)
        self._draw_keycap(frame, (base_x + 56, base_y + 42), "S", "s", "s" in active)
        self._draw_keycap(frame, (base_x + 112, base_y + 42), "D", "d", "d" in active)
        cv2.putText(frame, "move", (base_x + 180, base_y + 66), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1, cv2.LINE_AA)

        self._draw_keycap(frame, (base_x, base_y + 96), "R", "r", "r" in active)
        self._draw_keycap(frame, (base_x + 56, base_y + 96), "F", "f", "f" in active)
        cv2.putText(frame, "up/dn", (base_x + 130, base_y + 120), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1, cv2.LINE_AA)
        self._draw_keycap(frame, (base_x, base_y + 142), "Q", "q", "q" in active)
        self._draw_keycap(frame, (base_x + 56, base_y + 142), "E", "e", "e" in active)
        cv2.putText(frame, "yaw", (base_x + 130, base_y + 166), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1, cv2.LINE_AA)

        y = y0 + 210
        for label, desc, kid in (
            ("Space", "hover", "space"),
            ("Enter", "SAVE", "enter"),
            ("N / X", "reset", "n"),
            ("Esc", "quit", "esc"),
        ):
            on = kid in active or (kid == "n" and "x" in active)
            col = (80, 255, 80) if on else (220, 220, 220)
            cv2.putText(frame, f"{label}: {desc}", (x0 + 16, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, col, 1, cv2.LINE_AA)
            y += 18

        if hint:
            cv2.putText(frame, hint, (14, h - panel_h - 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2, cv2.LINE_AA)

        cv2.imshow(WIN, frame)
        cv2.waitKey(1)

    def close(self) -> None:
        try:
            self.cv2.destroyAllWindows()
        except Exception:
            pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--annotation", default="artifacts/building99_indoor_teleop_reachable.json")
    ap.add_argument("--route-idx", type=int, default=0, help="0=east open from R06 spawn")
    ap.add_argument("--out", required=True)
    ap.add_argument("--success-dist", type=float, default=0.25)
    ap.add_argument("--max-steps", type=int, default=400)
    ap.add_argument("--min-usable", type=int, default=8)
    ap.add_argument("--bc-tag", default="teleop_reachable_e2i_e")
    ap.add_argument(
        "--goal-pullback-m",
        type=float,
        default=0.0,
        help="Pull goal toward start (m); keep 0 for reachable open goals",
    )
    ap.add_argument("--hold-alt", action="store_true", default=True, help="PD altitude hold (default on)")
    ap.add_argument("--no-hold-alt", action="store_false", dest="hold_alt")
    args = ap.parse_args()

    from experiments.aerial.rl import dataset as ds
    from experiments.aerial.rl.buffer import Transition
    from experiments.aerial.rl.env.airsim_env import AirSimDroneEnv, AirSimEnvConfig
    from experiments.aerial.rl.indoor_controller import AltitudeLockController
    from experiments.aerial.rl.reward import NavigationReward, RewardConfig

    root = _ROOT
    ann = Path(args.annotation) if Path(args.annotation).is_absolute() else root / args.annotation
    seg = _load_route(ann, args.route_idx)
    start_pos = np.asarray(seg["pos"][0], dtype=np.float64)
    goal_raw = np.asarray(seg["goal"], dtype=np.float64)
    goal = _pullback_goal(start_pos, goal_raw, float(args.goal_pullback_m))
    seg["goal"] = goal
    seg["pos"] = [start_pos.tolist(), goal.tolist()]
    seg["d0_m"] = round(float(np.linalg.norm(goal - start_pos)), 3)
    if float(args.goal_pullback_m) > 0:
        logger.info(
            "goal pullback %.2fm: raw=%s -> hold=%s (d0=%.2fm)",
            args.goal_pullback_m,
            goal_raw.round(3).tolist(),
            goal.round(3).tolist(),
            seg["d0_m"],
        )

    cfg = AirSimEnvConfig(
        host="127.0.0.1",
        port=41451,
        vehicle=os.environ.get("AIRSIM_VEHICLE", "drone_1"),
        camera=os.environ.get("AIRSIM_CAMERA", "0"),
        width=int(os.environ.get("TELEOP_W", os.environ.get("INDOOR_CAPTURE_W", "640"))),
        height=int(os.environ.get("TELEOP_H", os.environ.get("INDOOR_CAPTURE_H", "480"))),
        fanout_rgb=os.environ.get("AIRSIM_FANOUT_RGB", "1") not in ("0", "false", "False"),
        grab_depth=True,
        step_hz=5.0,
        health_check=False,
    )
    env = AirSimDroneEnv(cfg)
    limits = np.array([0.15, 0.08, 0.08, 0.10], dtype=np.float64)
    reward_cfg = RewardConfig(success_dist_m=float(args.success_dist))

    out_dir = Path(args.out) if Path(args.out).is_absolute() else root / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    existing = sorted(out_dir.glob("episode_*.npz"))
    ep_idx = len(existing)

    gui = TeleopGui()
    keys_reader = TtyKeys()
    held: Dict[str, float] = {}
    reports: List[Dict[str, Any]] = []
    manifest: List[Dict[str, Any]] = []
    quality: List[Dict[str, Any]] = []

    print(HELP, flush=True)
    logger.info(
        "teleop route=%s idx=%d goal=%s (raw=%s) success<=%.2fm hold_alt=%s out=%s (prior_npz=%d)",
        seg["route_name"],
        args.route_idx,
        goal.tolist(),
        goal_raw.tolist(),
        args.success_dist,
        args.hold_alt,
        out_dir,
        ep_idx,
    )

    obs: Optional[Any] = None
    transitions: List[Any] = []
    reward_fn: Optional[NavigationReward] = None
    flying = False
    step_i = 0
    hint = "Click START — alt HOLD on; goal pulled back from wall"
    dt = 1.0 / float(cfg.step_hz)
    alt_lock = AltitudeLockController(kp=1.6, kd=0.55, max_dz=float(limits[2]))
    alt_lock.reset(float(start_pos[2]))

    def show(
        o: Optional[Any],
        *,
        d_end: float,
        coll: bool,
        step_i: int,
        flying: bool,
        pressed: Optional[Set[str]] = None,
        held: Optional[Dict[str, float]] = None,
        usable_n: int = 0,
        hint: str = "",
    ) -> None:
        gui.render(
            o,
            d_end=d_end,
            success=args.success_dist,
            coll=coll,
            step_i=step_i,
            flying=flying,
            goal=goal,
            start=start_pos,
            pressed=pressed,
            held=held,
            usable_n=usable_n,
            min_usable=args.min_usable,
            hint=hint,
        )

    def reset_ep() -> Tuple[Any, List[Any], NavigationReward]:
        o = env.reset(
            {
                "pos": seg["pos"],
                "yaw": seg["yaw"],
                "gpt_instruction": seg["gpt_instruction"],
            }
        )
        if o is None or getattr(o, "rgb", None) is None:
            raise RuntimeError("reset_failed")
        o.info["goal"] = goal.tolist()
        rf = NavigationReward(goal, reward_cfg)
        rf.reset(goal, o.position)
        held.clear()
        alt_lock.reset(float(start_pos[2]))
        return o, [], rf

    def apply_alt(action: np.ndarray, o: Any, pressed: Set[str]) -> np.ndarray:
        if not args.hold_alt or o is None:
            return action
        a = np.asarray(action, dtype=np.float64).copy()
        if _user_vertical_active(held, pressed):
            alt_lock._prev_alt = float(o.position[2])
            return a
        a[2] = alt_lock.step(float(o.position[2]), dt=dt)
        return a

    def d_and_coll(o: Any) -> Tuple[float, bool]:
        d = float(np.linalg.norm(np.asarray(o.position) - goal)) if o is not None else 99.0
        c = bool(getattr(o, "collided", False)) if o is not None else False
        return d, c

    try:
        # Idle preview: spawn once so ego view is visible before START
        obs, transitions, reward_fn = reset_ep()
        d_end, coll = d_and_coll(obs)
        show(obs, d_end=d_end, coll=coll, step_i=0, flying=False, usable_n=0, hint=hint)

        while True:
            pressed = keys_reader.drain() | gui.poll_keys(40)
            usable_n = sum(1 for m in manifest if m.get("usable"))

            if "esc" in pressed:
                logger.info("quit")
                break
            if "h" in pressed:
                print(HELP, flush=True)

            # START (button or Enter while idle)
            if not flying and ("start" in pressed or "enter" in pressed):
                obs, transitions, reward_fn = reset_ep()
                step_i = 0
                flying = True
                hint = "Flying — alt HOLD; follow TARGET; END when arrived"
                logger.info("START episode (will save as ep %d if arrived)", ep_idx)
                d_end, coll = d_and_coll(obs)
                show(
                    obs,
                    d_end=d_end,
                    coll=coll,
                    step_i=step_i,
                    flying=flying,
                    pressed=pressed,
                    held=held,
                    usable_n=usable_n,
                    hint=hint,
                )
                continue

            # Reset / discard
            if "n" in pressed or "x" in pressed:
                logger.info("discard / reset (steps=%d flying=%s)", step_i, flying)
                obs, transitions, reward_fn = reset_ep()
                step_i = 0
                flying = False
                held.clear()
                hint = "Reset — click START"
                d_end, coll = d_and_coll(obs)
                show(obs, d_end=d_end, coll=coll, step_i=0, flying=False, usable_n=usable_n, hint=hint)
                continue

            if not flying:
                # Idle: keep refreshing ego + altitude hold
                try:
                    hover = apply_alt(np.zeros(4, dtype=np.float64), obs, pressed)
                    obs, _ = env.step(hover)
                    obs.info["goal"] = goal.tolist()
                except Exception:
                    pass
                d_end, coll = d_and_coll(obs)
                show(
                    obs,
                    d_end=d_end,
                    coll=coll,
                    step_i=0,
                    flying=False,
                    pressed=pressed,
                    held=held,
                    usable_n=usable_n,
                    hint=hint,
                )
                continue

            # END button / Enter while flying → try save
            want_end = "end" in pressed or "enter" in pressed

            action = apply_alt(keys_to_action(pressed, limits, held), obs, pressed)
            next_obs, info = env.step(action)
            next_obs.info["goal"] = goal.tolist()
            assert reward_fn is not None
            r, done, terms = reward_fn.step(next_obs, action)
            ep_info = {
                **info,
                **terms,
                "intervention": False,
                "goal": goal.tolist(),
                "assist": "teleop",
            }
            transitions.append(
                Transition(
                    obs=obs,
                    action=action,
                    reward=r,
                    done=done,
                    next_obs=next_obs,
                    info=ep_info,
                )
            )
            obs = next_obs
            step_i += 1
            d_end, coll = d_and_coll(obs)
            show(
                obs,
                d_end=d_end,
                coll=coll,
                step_i=step_i,
                flying=True,
                pressed=pressed,
                held=held,
                usable_n=usable_n,
                hint=hint,
            )
            if step_i % 5 == 0 or want_end:
                print(
                    f"\r step={step_i:3d} d_end={d_end:.2f}m "
                    f"{'ARRIVE?' if d_end <= args.success_dist else '      '} "
                    f"{'COLL' if coll else '    '}",
                    end="",
                    flush=True,
                )

            force_end = coll or step_i >= args.max_steps
            if want_end or force_end:
                print(flush=True)
                arrived = d_end <= args.success_dist and not coll
                if want_end and not arrived:
                    logger.warning(
                        "END ignored for save: not arrived (d=%.2f coll=%s) — discarded",
                        d_end,
                        coll,
                    )
                    obs, transitions, reward_fn = reset_ep()
                    step_i = 0
                    flying = False
                    hint = "Not arrived — discarded. Click START"
                    continue
                if not arrived:
                    logger.info("auto-end without save (coll=%s steps=%d d=%.2f)", coll, step_i, d_end)
                    obs, transitions, reward_fn = reset_ep()
                    step_i = 0
                    flying = False
                    hint = "Ended without save. Click START"
                    continue

                # ``rgb`` already fan-out to WAM 224; ``rgb_vio`` stays capture WH.
                # Optional TELEOP_SAVE_* only crushes the WAM ``rgb`` field.
                save_wh = (
                    int(os.environ["TELEOP_SAVE_W"]),
                    int(os.environ["TELEOP_SAVE_H"]),
                ) if os.environ.get("TELEOP_SAVE_W") and os.environ.get("TELEOP_SAVE_H") else (224, 224)
                _downscale_transitions_rgb(transitions, save_wh)
                path = ds.write_episode(out_dir, ep_idx, transitions)
                qrep = ds.quality_report(transitions)
                bad = ds.assert_nontrivial(qrep)
                quar = ds.quarantine_reasons(qrep)
                usable = not bad and not quar
                rep = {
                    "ok": True,
                    "segment_name": seg["segment_name"],
                    "route_name": seg["route_name"],
                    "source_route_idx": seg["source_route_idx"],
                    "steps": step_i,
                    "d0_m": seg["d0_m"],
                    "d_end_m_gt": round(d_end, 4),
                    "arrived_gt": True,
                    "collided": False,
                    "assist": "teleop",
                    "bc_tag": args.bc_tag,
                    "scene": "Building_99",
                    "pose_source": "gt_proxy",
                }
                logger.info(
                    "SAVED ep %d steps=%d d_end=%.2f usable=%s -> %s",
                    ep_idx,
                    step_i,
                    d_end,
                    usable,
                    path.name,
                )
                manifest.append(
                    {
                        "file": path.name,
                        "steps": qrep["steps"],
                        "segment_name": rep["segment_name"],
                        "route_name": rep["route_name"],
                        "source_route_idx": rep["source_route_idx"],
                        "d_end_m_gt": rep["d_end_m_gt"],
                        "arrived_gt": True,
                        "usable": usable,
                    }
                )
                quality.append(qrep)
                reports.append({**qrep, **rep})
                ep_idx += 1
                usable_n = sum(1 for m in manifest if m.get("usable"))
                logger.info("progress usable=%d / min=%d", usable_n, args.min_usable)
                obs, transitions, reward_fn = reset_ep()
                step_i = 0
                flying = False
                hint = f"Saved. usable={usable_n}/{args.min_usable} — click START"
    finally:
        keys_reader.close()
        try:
            env.close()
        except Exception:
            pass
        gui.close()

    usable_n = sum(1 for m in manifest if m.get("usable"))
    meta = {
        "protocol": "indoor_teleop_E2i_e_r06",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "scene": "Building_99",
        "annotation": str(ann),
        "assist": "teleop",
        "bc_tag": args.bc_tag,
        "pose_source": "gt_proxy",
        "success_dist_m": args.success_dist,
        "n_collected": len(manifest),
        "n_usable": usable_n,
        "note": "Human teleop GUI on 125; NOT assist=none product completion.",
    }
    if manifest:
        ds.write_manifest(out_dir, manifest, meta=meta)
        ds.write_quality_summary(out_dir, quality)
        summary = {
            **meta,
            "arrival_rate_gt": 1.0,
            "mean_d_end_gt": round(float(np.mean([r["d_end_m_gt"] for r in reports])), 4),
            "episodes": reports,
        }
        (out_dir / "collection_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    logger.info("done usable=%d -> %s", usable_n, out_dir)
    if usable_n < args.min_usable:
        logger.error("usable %d < min gate %d", usable_n, args.min_usable)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
