# VIO isolated probe results（2026-09-02 · 本机 SSH→125 · **无** 125 Cursor Agent）

## 结论

| 门 | 结果 |
|----|------|
| **P0** EuRoC 导出 + ATE + `vio_est` bridge | ✅ |
| **P1a** OpenVINS 库 + `ov_euroc_offline` 可执行 | ✅ |
| **P1b** 自动 init 出 traj（真 VIO） | ❌ AirSim indoor npz |
| **P1c** `--gt-init` 种子后写出 traj（跟踪探针） | ✅ 172 poses · ATE 仍炸（占位标定） |

**未宣称** E3 / F-cap 传感完成；**未**占 AirSim 做 collect。

---

## 已落盘

| 路径 | 说明 |
|------|------|
| `~/src/open_vins` | OpenVINS v2.7 · `ENABLE_ROS=OFF` |
| `~/src/open_vins/OPENVINS_BIN.env` | `OPENVINS_BIN=.../vio_probe/cpp/build/ov_euroc_offline` |
| `experiments/aerial/vio_probe/` | 导出 / ATE / bridge / runner / 占位标定 |
| `artifacts/vio_probe/syn_20260902/` | dry-run |
| `artifacts/vio_probe/ov_gtinit3_*/` | GT-seed 成功样例（`ok:true` · tum 172） |

## P1b 失败现象

自动 init：`not enough feats to compute disp: N,0 < 15`（新半窗特征恒 0）。  
已试：动态 init、低 disparity、`track_frequency=5`、480×640 上采样、accel Z 翻转 — 均未过。

## P1c 说明

`--gt-init` 只种子一次（勿每帧重 seed，否则 clone 攒不起来）。  
ATE RMSE ~km 级 ⇒ **标定/坐标系未冻**，仅证明「二进制+EuRoC+接口」通，**不能**当位姿质量门。

### 排查：`ov_gtinit_20260902_163425` 写 0 poses（2026-09-02）

| 现象 | 解释 |
|------|------|
| 日志 `gt-init at t=… ok=no`（每帧） | **旧** `ov_euroc_offline`：每帧 `initialize_with_gt` + 用 `initialized()` 当 ok |
| `initialized()` 一直 false | OpenVINS 要攒够 clone / `timelastupdate`；**每帧重 seed 会冲掉 clone** |
| cam/GT 时间 | 已对齐 `[0, 55.6]s`，**不是**时间戳对不上 |
| 对照 | 改「只 seed 一次」后 `ov_gtinit3_20260902_163840` → **172 poses · ok** |

结论：那次失败是 **runner 种子逻辑 bug**，不是 OpenVINS 库坏了，也不是 fan-out/分辨率问题。当前仓内 cpp 已是 once-seed。

## 复跑

```bash
source ~/src/open_vins/OPENVINS_BIN.env
cd /home/yao/aerial-indoor-wam
python3 -m experiments.aerial.vio_probe.run_isolated_probe \
  --npz experiments/aerial/rl/artifacts/dataset_indoor_fixture_bc_e2f_20260830/episode_00000.npz \
  --out artifacts/vio_probe/ov_repro --run-openvins --openvins-bin "$OPENVINS_BIN" \
  --gt-init --resize 480 640
```

### 坐标对齐（2026-09-02 · **离线** · 未占 AirSim/OV 跑数）

| 项 | 结论 |
|----|------|
| 栈 world / GT seed | ENU +up |
| AirSim `getImuData` | **NED body**（静止 `a≈[0,0,-g]`） |
| 旧探针 | 原样喂 OpenVINS → 当 ENU 用 → **Z 自由落体**（est z→−30 km；闭环 `d_hat≈723`） |
| ATE 旧报 | `gt_tum` 用绝对 `timestamps`，OV 用相对 t0 → 几乎对不齐时间（假 ATE） |
| 修复 | `frames.ned_body_to_enu_body`；`euroc_export` / `live_bridge` 转换 IMU；`T_imu_cam` 改为 EuRoC 光轴；`gt_tum` 改相对 t0 |

### 划算过门（2026-09-02 · thrifty sim self-consistency）→ 📦 [签过归档](INDOOR_VIO_THRIFTY_ARCHIVE_20260902.md)

**目标**：仿真修到「坐标/重力不再逻辑性炸」；**不**精修占位标定；真机另标。

| 门 | 条件 | 结果 |
|----|------|------|
| **S1** 合成悬停 imu-only | drift ≈ 0 | ✅ |
| **S2** fixture + `imu_mode=hover` + gt-init + imu-only | ATE ≤ 5 m | ✅ **3.13 m**（`ov_thrifty_hover_20260902_174512` · gate JSON `thrifty_gate_20260902_hover.json`） |
| AirSim ZOH 真 IMU 积分 | — | ❌ 故意不做（假 IMU 不可积） |
| 真机标定 | — | 另做 |

脚本：`run_indoor_vio_align_when_idle.sh`（默认 `SKIP_CLOSED=1`，`--imu-mode hover`）。

## 闭环接线（2026-09-02 · 继续）

| 项 | 状态 |
|----|------|
| `ov_stream_online` 行协议 | ✅ 编过 · GTINIT/IMU/CAM/POSE |
| `AERIAL_VIO_LIVE=1` → `LiveVioEstPoseEstimator` | ✅ |
| 单相机 fan-out → `rgb_vio` 喂流 | ✅（capture 640×480） |
| `run_indoor_vio_closed_smoke.sh` east | ✅ 跑通接口 · **`d_end_hat≈723 m`**（位姿炸） |
| 产品 VIO / F-cap 换源 | ❌ |

**说明**：闭环 smoke 默认 `AERIAL_VIO_GT_SEED=1`（仿真探针）；auto-init 仍不过。位姿炸 = 占位标定/坐标系（与 P1c ATE 同源），**不是**「没接到闭环」。

```bash
export OPENVINS_STREAM_BIN=.../ov_stream_online
bash experiments/aerial/scripts/run_indoor_vio_closed_smoke.sh
```

## 分辨率（2026-09-02 更正 · 再更正）

**单相机一次采集**，采集后分发（不是双相机，也不是 CaptureSettings 在 224/640 间切换）：

```
CaptureSettings（如 640×480）
        ├─ rgb_vio  → OpenVINS
        ├─ rgb      → WAM（resize 224）
        └─ rgb_yolo → YOLO 旁路
```

仓内：`indoor_capture.fanout_rgb` + `Observation.rgb_vio` / `rgb_yolo`。  
生效需 `settings_indoor.json` 为采集分辨率并 **重启 AirSim**（勿抢在跑 eval）。

1. 更高帧率 / 真 IMU 录一段或 EuRoC 原生数据过 **P1b**  
2. 标定 camera–IMU 后再看 ATE  
3. 再谈闭环 `pose_source=vio_est`
