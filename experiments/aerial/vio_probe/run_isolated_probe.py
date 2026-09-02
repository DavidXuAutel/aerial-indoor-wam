#!/usr/bin/env python3
"""Isolated OpenVINS probe CLI — no AirSim, no E2i defaults.

Examples::

  python -m experiments.aerial.vio_probe.run_isolated_probe --synthetic --out /tmp/vio_syn
  python -m experiments.aerial.vio_probe.run_isolated_probe --npz ep.npz --out artifacts/vio_probe/x --skip-openvins
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from experiments.aerial.vio_probe.ate import ate_rmse_posyaw
from experiments.aerial.vio_probe.euroc_export import (
    export_episode_npz_to_euroc,
    make_synthetic_episode_npz,
)
from experiments.aerial.vio_probe.openvins_runner import (
    resolve_openvins_bin,
    run_openvins_offline,
    stage_openvins_config,
)
from experiments.aerial.vio_probe.pose_bridge import VioEstPoseEstimator
from experiments.aerial.vio_probe.traj_io import load_tum_trajectory, write_tum_trajectory

_DEFAULT_CFG = Path(__file__).resolve().parent / "config" / "indoor_placeholder"


def _gt_as_est_tum(euroc_dir: Path, noise_m: float = 0.0, seed: int = 0) -> Path:
    """Copy GT TUM to est path (optional noise) for dry-run without OpenVINS."""
    gt = euroc_dir / "gt_tum.txt"
    t, pos, quat = load_tum_trajectory(gt)
    if noise_m > 0:
        rng = np.random.default_rng(seed)
        pos = pos + rng.normal(0.0, noise_m, size=pos.shape)
    out = euroc_dir / "est_tum_from_gt.txt"
    write_tum_trajectory(out, t, pos, quat)
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Isolated OpenVINS / vio_est probe")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--npz", type=Path, help="episode_*.npz with rgb+imu")
    src.add_argument("--synthetic", action="store_true", help="write + use synthetic npz")
    p.add_argument("--out", type=Path, required=True, help="probe output directory")
    p.add_argument("--skip-openvins", action="store_true", help="do not invoke OpenVINS")
    p.add_argument("--run-openvins", action="store_true", help="require OpenVINS binary")
    p.add_argument("--openvins-bin", type=Path, default=None)
    p.add_argument(
        "--openvins-config-dir",
        type=Path,
        default=_DEFAULT_CFG,
        help="dir with config.yaml + config_imu.yaml (cam rewritten from meta)",
    )
    p.add_argument(
        "--gt-init",
        action="store_true",
        help="pass --gt-init to ov_euroc_offline (seed from EuRoC GT; probe tracking only)",
    )
    p.add_argument(
        "--imu-only",
        action="store_true",
        help="thrifty S2: blank cams (IMU propagate only) — frame/gravity check without vision",
    )
    p.add_argument(
        "--imu-mode",
        default="airsim",
        choices=["airsim", "gt_consistent", "hover"],
        help="airsim=ZOH AirSim; gt_consistent=synth from GT; hover=a=[0,0,g] thrifty plumbing",
    )
    p.add_argument("--hfov-deg", type=float, default=90.0)
    p.add_argument(
        "--resize",
        type=int,
        nargs=2,
        metavar=("H", "W"),
        default=None,
        help="optional RGB upsample before EuRoC export (e.g. 480 640)",
    )
    p.add_argument("--gt-noise-m", type=float, default=0.0, help="dry-run est = GT+noise")
    args = p.parse_args(argv)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if args.synthetic:
        npz_path = make_synthetic_episode_npz(out / "synthetic_episode.npz")
    else:
        npz_path = Path(args.npz)

    euroc_dir = out / "euroc"
    # Default: keep native npz resolution (indoor capture ≥640×480). Upsample only
    # for legacy 224² corpora via --resize H W; --resize 0 0 keeps native.
    if args.resize is None:
        resize_hw = None
    elif args.resize[0] <= 0:
        resize_hw = None
    else:
        resize_hw = tuple(args.resize)
    meta = export_episode_npz_to_euroc(
        npz_path,
        euroc_dir,
        hfov_deg=args.hfov_deg,
        resize_hw=resize_hw,
        imu_mode=args.imu_mode,
    )

    ov_report: dict = {"ran": False, "reason": "skipped"}
    est_tum: Path | None = None
    if args.run_openvins and not args.skip_openvins:
        cfg_yaml = stage_openvins_config(
            Path(args.openvins_config_dir),
            out / "openvins_config",
            meta["camera"],
        )
        bin_path = args.openvins_bin or resolve_openvins_bin()
        extra = []
        if args.gt_init:
            extra.append("--gt-init")
        if args.imu_only:
            extra.append("--imu-only")
        ov_report = run_openvins_offline(
            euroc_dir,
            out / "est_tum_openvins.txt",
            bin_path=bin_path,
            config_yaml=cfg_yaml,
            extra_args=extra or None,
        )
        ov_report["config_yaml"] = str(cfg_yaml)
        ov_report["gt_init"] = bool(args.gt_init)
        ov_report["imu_only"] = bool(args.imu_only)
        if ov_report.get("ok") and ov_report.get("out_tum"):
            est_tum = Path(ov_report["out_tum"])
        elif args.run_openvins:
            summary = {
                "ok": False,
                "gate": "P1_openvins",
                "export_meta": meta,
                "openvins": ov_report,
            }
            (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
            print(json.dumps(summary, indent=2))
            return 2
    if est_tum is None:
        est_tum = _gt_as_est_tum(euroc_dir, noise_m=args.gt_noise_m)
        ov_report = {
            "ran": False,
            "reason": "dry_run_est_equals_gt",
            "out_tum": str(est_tum),
            "gt_noise_m": float(args.gt_noise_m),
        }

    t_e, p_e, _ = load_tum_trajectory(est_tum)
    t_g, p_g, _ = load_tum_trajectory(euroc_dir / "gt_tum.txt")
    # Align time bases: export GT uses absolute npz t; OpenVINS may use 0-based —
    # for dry-run both absolute; if est starts near 0 and gt does not, shift est.
    if float(t_e[0]) < 1.0 and float(t_g[0]) > 1.0:
        t_e = t_e + float(t_g[0])
    ate = ate_rmse_posyaw(t_e, p_e, t_g, p_g, max_dt_s=0.25)

    from experiments.aerial.vio_probe.frames import SIM_ATE_RMSE_MAX_M

    thrifty_pass = bool(ate.get("n_pairs", 0) >= 2) and float(ate["ate_rmse_m"]) <= SIM_ATE_RMSE_MAX_M

    # Bridge smoke: step estimator at GT timestamps
    from experiments.aerial.rl.env.obs import Observation

    est = VioEstPoseEstimator(est_tum)
    pe0 = None
    for i, ti in enumerate(t_g[: min(5, len(t_g))]):
        state = np.array(
            [p_g[i, 0], p_g[i, 1], p_g[i, 2], 0, 0, 0, 0], dtype=np.float32
        )
        obs = Observation(
            rgb=np.zeros((8, 8, 3), dtype=np.uint8),
            state=state,
            t=float(ti),
        )
        pe0 = est.reset(obs) if i == 0 else est.update(obs)
    assert pe0 is not None and pe0.pose_source == "vio_est"

    summary = {
        "ok": True,
        "gate": "P0_export+P3_bridge" + ("+P2_ate" if ate["n_pairs"] >= 2 else ""),
        "thrifty_sim_S2_pass": thrifty_pass,
        "thrifty_sim_S2_max_m": SIM_ATE_RMSE_MAX_M,
        "backend": "openvins" if ov_report.get("ran") else "dry_run_gt",
        "pose_source": "vio_est",
        "export_meta": meta,
        "openvins": ov_report,
        "ate": ate,
        "est_tum": str(est_tum),
        "note": (
            "Isolated probe / thrifty sim self-consistency — not E3-cap / F-cap / robot calib."
        ),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
