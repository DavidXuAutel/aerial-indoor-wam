"""Optional OpenVINS offline subprocess wrapper (ov_euroc_offline)."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional


def resolve_openvins_bin(explicit: Optional[str | Path] = None) -> Optional[Path]:
    cand = explicit or os.environ.get("OPENVINS_BIN")
    if cand:
        p = Path(cand).expanduser()
        return p if p.is_file() else None
    # Prefer our ROS-free runner next to the probe package build
    here = Path(__file__).resolve().parent
    local = here / "cpp" / "build" / "ov_euroc_offline"
    if local.is_file():
        return local
    home_local = Path.home() / "src" / "ov_euroc_offline" / "build" / "ov_euroc_offline"
    if home_local.is_file():
        return home_local
    for name in ("ov_euroc_offline", "ov_msckf_offline", "vio_offline"):
        hit = shutil.which(name)
        if hit:
            return Path(hit)
    return None


from experiments.aerial.vio_probe.frames import T_IMU_CAM_NEU_FORWARD


def write_config_cam_yaml(
    out_path: Path,
    *,
    width: int,
    height: int,
    fx: float,
    fy: float,
    cx: float,
    cy: float,
) -> Path:
    """Write OpenVINS cam chain: NEU-body IMU + forward cam (EuRoC optical)."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for r in T_IMU_CAM_NEU_FORWARD:
        rows.append(
            "    - [{0:.1f}, {1:.1f}, {2:.1f}, {3:.1f}]".format(r[0], r[1], r[2], r[3])
        )
    text = "\n".join(
        [
            "%YAML:1.0",
            "",
            "cam0:",
            "  T_imu_cam:",
            *rows,
            "  camera_model: pinhole",
            "  distortion_coeffs: [0.0, 0.0, 0.0, 0.0]",
            "  distortion_model: radtan",
            f"  intrinsics: [{fx:.6f}, {fy:.6f}, {cx:.6f}, {cy:.6f}]",
            f"  resolution: [{int(width)}, {int(height)}]",
            "",
        ]
    )
    out_path.write_text(text, encoding="utf-8")
    return out_path


def stage_openvins_config(
    template_dir: Path,
    stage_dir: Path,
    camera: Dict[str, Any],
) -> Path:
    """Copy estimator+imu yaml and rewrite cam yaml from export meta camera dict."""
    template_dir = Path(template_dir)
    stage_dir = Path(stage_dir)
    stage_dir.mkdir(parents=True, exist_ok=True)
    for name in ("config.yaml", "config_imu.yaml"):
        src = template_dir / name
        if not src.is_file():
            raise FileNotFoundError(src)
        shutil.copy2(src, stage_dir / name)
    write_config_cam_yaml(
        stage_dir / "config_cam.yaml",
        width=int(camera["width"]),
        height=int(camera["height"]),
        fx=float(camera["fx"]),
        fy=float(camera["fy"]),
        cx=float(camera["cx"]),
        cy=float(camera["cy"]),
    )
    return stage_dir / "config.yaml"


def run_openvins_offline(
    euroc_dir: Path,
    out_tum: Path,
    *,
    bin_path: Optional[Path] = None,
    config_yaml: Optional[Path] = None,
    extra_args: Optional[List[str]] = None,
    timeout_s: float = 600.0,
) -> Dict[str, Any]:
    """Invoke ``ov_euroc_offline <config> <euroc_root> <out_tum>``."""
    binary = resolve_openvins_bin(bin_path)
    if binary is None:
        return {
            "ran": False,
            "reason": "OPENVINS_BIN not set / ov_euroc_offline not found",
            "out_tum": None,
        }
    if config_yaml is None or not Path(config_yaml).is_file():
        return {
            "ran": False,
            "reason": "config_yaml missing",
            "out_tum": None,
        }
    out_tum = Path(out_tum)
    out_tum.parent.mkdir(parents=True, exist_ok=True)
    argv = [str(binary), str(config_yaml), str(euroc_dir), str(out_tum)]
    if extra_args:
        argv.extend(extra_args)
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=float(timeout_s),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "ran": True,
            "ok": False,
            "reason": "timeout",
            "argv": argv,
            "stdout": (exc.stdout or "")[-4000:],
            "stderr": (exc.stderr or "")[-4000:],
            "out_tum": str(out_tum) if out_tum.is_file() else None,
        }
    ok = proc.returncode == 0 and out_tum.is_file() and out_tum.stat().st_size > 32
    return {
        "ran": True,
        "ok": ok,
        "returncode": int(proc.returncode),
        "argv": argv,
        "stdout": (proc.stdout or "")[-4000:],
        "stderr": (proc.stderr or "")[-4000:],
        "out_tum": str(out_tum) if out_tum.is_file() else None,
        "reason": None if ok else "nonzero_or_missing_traj",
    }
