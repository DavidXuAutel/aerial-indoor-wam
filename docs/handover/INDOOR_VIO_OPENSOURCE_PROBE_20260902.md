# Indoor — 开源 VIO 孤立验证（OpenVINS → `vio_est`）· 2026-09-02

> **人令**：找开源 VIO 接当前栈，**先孤立验证**，**不碰在跑工作**。  
> **选型**：**OpenVINS**（[rpng/open_vins](https://github.com/rpng/open_vins)）— 可 `ENABLE_ROS=OFF` 离线跑 EuRoC。  
> **状态**：脚手架已落仓；**未**宣称 E3 传感完成；**未**改 E2i/F-cap 默认 `pose_source`。

---

## 1. 为什么是 OpenVINS

| 候选 | 取舍 |
|------|------|
| **OpenVINS** | MAV 主流；EuRoC 原生；可无 ROS 离线；ATE/RPE 工具链成熟 |
| VINS-Fusion | 强依赖 ROS，接 Stick 仿真成本高 |
| ORB-SLAM3 | 更偏 SLAM；标定/初始化重 |
| 自研积分 `odom_from_imu_rgb` | 签 C 已停追；**不是**真 VIO |

现有 `experiments/aerial/rl/vio.py` 只是 **窗口尺度 metric**，不是前端 VIO。

---

## 2. 隔离边界（硬）

| 做 | 不做 |
|----|------|
| 离线：`episode_*.npz` → EuRoC →（可选）OpenVINS → ATE vs GT | 占 AirSim `:41451` / 打断 E2i·F 在跑 job |
| `pose_source=vio_est` 仅显式开；默认仍 `gt_proxy` / `odom_from_imu_rgb` | 改 `safety.py` deploy、盲 FT、关罩完成态 |
| Mac / 空闲机编译 OpenVINS | 把仿真 odom hat 冒充 VIO 完成 |
| 报表写 `backend=openvins` + ATE | 无人令把 VIO 当 F-cap / E3-cap 主门 |

---

## 3. 接线（合同接口）

```text
episode npz (rgb + imu_ang_vel + imu_lin_acc + timestamps + proprio)
        │
        ▼  vio_probe.euroc_export
EuRoC ASL dir (cam0/data + imu0/data.csv + body.csv GT)
        │
        ▼  OpenVINS offline（本机二进制；未装则 --dry-run 只验导出）
est_traj.txt (TUM: t px py pz qx qy qz qw)
        │
        ▼  vio_probe.ate  +  VioEstPoseEstimator(traj)
PoseEstimate(pose_source="vio_est") → goal_rel 同构接口
```

`make_pose_estimator("vio_est")`：**不再**静默 alias 到 `odom_from_imu_rgb`。  
需 `AERIAL_VIO_TRAJ=<tum.txt>`（或构造时传入 traj）；否则 **显式报错**。

---

## 4. 怎么跑（孤立）

```bash
# A. 仅脚手架自检（无需 OpenVINS / AirSim）
python -m experiments.aerial.vio_probe.run_isolated_probe --synthetic --out /tmp/vio_probe_syn

# B. 已有 episode npz → EuRoC +（若有 GT）对「伪 traj=GT」ATE 自洽
python -m experiments.aerial.vio_probe.run_isolated_probe \
  --npz path/to/episode_00000.npz \
  --out artifacts/vio_probe/<stamp> \
  --skip-openvins

# C. 本机已装 OpenVINS offline 后
export OPENVINS_BIN=/path/to/ov_msckf_offline   # 或你们编出的 vio_offline
python -m experiments.aerial.vio_probe.run_isolated_probe \
  --npz path/to/episode_00000.npz \
  --out artifacts/vio_probe/<stamp> \
  --run-openvins
```

编译提示（**另开目录，勿写入本仓在跑产物**）：

```bash
git clone --depth 1 --branch v2.7 https://github.com/rpng/open_vins.git /tmp/open_vins
cd /tmp/open_vins/ov_msckf && mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release -DENABLE_ROS=OFF -DENABLE_ARUCO_TAGS=OFF
make -j$(nproc)
```

标定：**单相机** CaptureSettings（默认 **640×480**）一次抓图，再 `fanout_rgb` → VIO 原生 / WAM 224 / YOLO；**不是**双相机，也不是把同一路 CaptureSettings 切来切去。  
EuRoC 导出按 npz 原生分辨率写 cam；仅 legacy 224 语料才 `--resize`。
---

## 5. 过门（孤立探针，非 E3-cap）

| 门 | 条件 |
|----|------|
| P0 | EuRoC 导出可复现；目录含 `cam0` + `imu0` + GT |
| P1 | OpenVINS 在至少 1 段 indoor npz 上跑完且输出 traj |
| P2 | posyaw ATE RMSE **有限**且落盘 JSON（阈值待标定后再冻） |
| P3 | `VioEstPoseEstimator` 用该 traj 步进，`pose_source=="vio_est"` |

**之后**才谈：闭环 `assist=none` + `vio_est` 评测 / 是否小 FT（另令人令）。

### 闭环入口（已落 · 2026-09-02）

```bash
export AERIAL_VIO_LIVE=1 AERIAL_VIO_GT_SEED=1   # sim 探针种子；非产品
export OPENVINS_STREAM_BIN=.../ov_stream_online
bash experiments/aerial/scripts/run_indoor_vio_closed_smoke.sh
```

`make_pose_estimator("vio_est")`：`AERIAL_VIO_LIVE=1` → 流式；否则 `AERIAL_VIO_TRAJ` 离线回放。  
**未**改 F-cap 默认 `pose_source`。闭环 smoke 已通接口；位姿质量仍受占位标定限制。

---

## 6. 代码入口

| 路径 | 角色 |
|------|------|
| `experiments/aerial/vio_probe/` | 孤立包 |
| `experiments/aerial/vio_probe/live_bridge.py` | 闭环流式 `vio_est` |
| `experiments/aerial/vio_probe/cpp/ov_stream_online.cpp` | 行协议 OpenVINS |
| `experiments/aerial/scripts/run_indoor_vio_closed_smoke.sh` | indoor 闭环 smoke |
| `experiments/aerial/rl/pose_estimate.py` | `vio_est` → live/offline |
| `experiments/aerial/rl/tests/test_vio_probe_isolated.py` | 无二进制单测 |
