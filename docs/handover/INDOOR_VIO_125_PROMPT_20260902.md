# 125 Agent：OpenVINS 孤立编译 + 探针（2026-09-02）

> **Workspace**：`/home/yao/aerial-indoor-wam`  
> **权威**：[`INDOOR_VIO_OPENSOURCE_PROBE_20260902.md`](INDOOR_VIO_OPENSOURCE_PROBE_20260902.md) · [`INDOOR_0XM_STATUS.md`](INDOOR_0XM_STATUS.md)  
> **选型**：OpenVINS v2.7 · `ENABLE_ROS=OFF`  
> **性质**：**旁路 / 非阻塞** — 估器重开脚手架，**不是** F-cap / E3-cap 主门

---

## 硬隔离（先读再动手）

| 禁止 | 允许 |
|------|------|
| 占 / 抢 AirSim `:41451` | CPU 编译 OpenVINS（另目录） |
| `kill` / 改 / 重启任何 **E2i · F · E3 · Phase-2** 在跑 job | 读 `pgrep` 确认空闲 |
| 改 `safety.py` deploy、盲 FT、关罩评测 | pull 本仓 `vio_probe` 脚手架 |
| 把结果写成「E3 传感完成 / F-cap 换位姿」 | 落盘 `artifacts/vio_probe/*` + 回写 STATUS **旁注** |
| 写入 `/home/yao/aerial-indoor-wam` 的 GPU 长训目录抢盘 | 源码放 `~/src/open_vins`（仓外） |

**开工前自检**：

```bash
pgrep -af 'AirSim|airsim|run_e2i|indoor_loop|train_v4|phase.?2' || true
ss -lptn 'sport = :41451' 2>/dev/null || netstat -lptn 2>/dev/null | grep 41451 || true
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv 2>/dev/null | head
```

- AirSim / E2i·F 在跑 → **只做 §1 编译**（纯 CPU），**不要**跑需要读仿真的 collect；npz 用磁盘上已有 episode。  
- GPU 满载长训 → **仍可编译**（限制 `make -j4`），不要另起 eval。  
- 不确定是否「在跑工作」→ **停手问人**，不要猜。

---

## 0. 同步仓（只读主航道，不改默认）

```bash
cd /home/yao/aerial-indoor-wam
git fetch github && git merge github/main   # 或 origin，以机上 remote 为准
mkdir -p artifacts/vio_probe logs
python3 -m pytest experiments/aerial/rl/tests/test_vio_probe_isolated.py \
  experiments/aerial/rl/tests/test_pose_estimate.py -q
# 期望：test_vio_probe_* 全绿；pose_estimate 全绿
python3 -m experiments.aerial.vio_probe.run_isolated_probe \
  --synthetic --out artifacts/vio_probe/syn_$(date +%Y%m%d) --skip-openvins
```

---

## 1. 编译 OpenVINS（仓外 · CPU）

```bash
sudo apt-get update
sudo apt-get install -y build-essential cmake git \
  libeigen3-dev libopencv-dev libboost-all-dev \
  libgflags-dev libgoogle-glog-dev libcxsparse3 || \
sudo apt-get install -y libsuitesparse-dev

# 仓外，避免污染 aerial-indoor-wam 工作树
mkdir -p ~/src && cd ~/src
git clone --depth 1 --branch v2.7 https://github.com/rpng/open_vins.git open_vins
cd ~/src/open_vins/ov_msckf
mkdir -p build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release \
  -DBUILD_SHARED_LIBS=ON \
  -DENABLE_ROS=OFF \
  -DENABLE_ARUCO_TAGS=OFF
# 有人在跑 GPU job 时用 -j4；空闲可用 -j$(nproc)
make -j4
```

找出 offline 可执行文件（名称因分支略有差别）：

```bash
find ~/src/open_vins -type f -executable \( -name '*offline*' -o -name 'run_*' -o -name 'ov_*' \) 2>/dev/null | head -40
# 记下绝对路径，例如：
export OPENVINS_BIN=/path/to/实际二进制
echo "OPENVINS_BIN=$OPENVINS_BIN" | tee ~/src/open_vins/OPENVINS_BIN.env
```

若官方 `ov_msckf` 无现成「EuRoC 目录 → TUM」CLI：  
- 允许用社区 ROS-free wrapper（如 Eryk-Mozdzen/open_vins_example 的 `vio_offline`），**仍装在 `~/src/`**；  
- 或写 1 页笔记：二进制路径 + 你验证过的 argv，落 `artifacts/vio_probe/openvins_cli_notes.md`。  
- **不要**为接 CLI 去改主航道 collector / safety。

**编译失败**：把 cmake/make 尾部 80 行贴进 `artifacts/vio_probe/openvins_build_fail_*.log`，停在 P0；**不要**强行改系统 ROS。

---

## 2. 真 npz 导出（P0）— 不启 AirSim

优先用盘上已有 indoor episode（E3/F collect 产物均可，**只读**）：

```bash
cd /home/yao/aerial-indoor-wam
# 自行替换为机上真实路径（示例）
NPZ=$(find data artifacts -name 'episode_*.npz' 2>/dev/null | head -1)
echo "NPZ=$NPZ"
test -n "$NPZ" && test -f "$NPZ"

STAMP=$(date +%Y%m%d_%H%M)
OUT=artifacts/vio_probe/ep_${STAMP}
python3 -m experiments.aerial.vio_probe.run_isolated_probe \
  --npz "$NPZ" \
  --out "$OUT" \
  --skip-openvins
# 期望：euroc/mav0/cam0 + imu0 + gt_tum.txt + summary.json ok=true
```

无 npz → **不要**为 VIO 新开 collect 占仿真；回写 STATUS「缺 npz，P0 仅 syn」即可停。

---

## 3. 跑 OpenVINS（P1）— 仍不启 AirSim

```bash
source ~/src/open_vins/OPENVINS_BIN.env   # 或手动 export OPENVINS_BIN=...
cd /home/yao/aerial-indoor-wam
STAMP=$(date +%Y%m%d_%H%M)
OUT=artifacts/vio_probe/ov_${STAMP}
python3 -m experiments.aerial.vio_probe.run_isolated_probe \
  --npz "$NPZ" \
  --out "$OUT" \
  --run-openvins \
  --openvins-bin "$OPENVINS_BIN"
```

| 结果 | 动作 |
|------|------|
| `openvins.ok=true` + `est_tum` 存在 | **P1 PASS**；记 ATE（`ate.ate_rmse_m`） |
| 二进制 argv 不兼容 | 记 notes；用手动跑出的 TUM 放到 `$OUT/est_tum_openvins.txt`，再：`AERIAL_VIO_TRAJ=...` 测 bridge |
| 跟踪发散 / 无输出 | P1 FAIL 落盘；**禁止**为刷 ATE 改标定进主门 |

手动桥接自检：

```bash
export AERIAL_VIO_TRAJ=$OUT/est_tum_openvins.txt   # 或你导出的 TUM
python3 - <<'PY'
from experiments.aerial.rl.pose_estimate import make_pose_estimator
e = make_pose_estimator("vio_est")
print(e.pose_source, e.tum_path)
PY
```

---

## 4. 回写（旁注 only）

更新（或请 Mac 代更）[`INDOOR_0XM_STATUS.md`](INDOOR_0XM_STATUS.md) **旁注一行**：

```text
VIO 孤立：OpenVINS build ✅/❌ · P0 export ✅/❌ · P1 ov traj ✅/❌ · ATE=… m · 工件 artifacts/vio_probe/…
```

**禁止**改写：F-cap PASS、E3 签 C、把 `pose_source` 默认改成 `vio_est`。

产物清单：

- `artifacts/vio_probe/syn_*/summary.json`
- `artifacts/vio_probe/ep_*/` 或 `ov_*/summary.json`
- `~/src/open_vins/OPENVINS_BIN.env`
- 可选 `artifacts/vio_probe/openvins_cli_notes.md`

---

## 5. 明确不做（本 prompt 范围外）

- 闭环 `assist=none` + `vio_est` 飞评  
- H100 FT / 改 actor  
- 标定冻结进产品门  
- `recover_renderer_scene` / 切 Building_99  
- 任何需要占用 `:41451` 的步骤  

P1 过后停；**下一刀另令人令**。
