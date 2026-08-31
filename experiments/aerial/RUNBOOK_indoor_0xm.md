# Indoor WAM Runbook（主航道 · 尺度特化）

> **日期**：2026-08-29（全方案 Stick 主航道 + 传感合同冻结）  
> **工程**：`aerial-indoor-wam`  
> **本文件是什么**：室内小空间的**唯一执行入口**。室内 **不是** 旁支、不是夹具工程、不是第二条产品线。  
> **主航道唯一**：与 [`RUNBOOK_wam_imagination.md`](RUNBOOK_wam_imagination.md)（阶段 1）及仓库外/同族 [`RUNBOOK_wam_phase2_long_horizon.md`](../../../aerial-wam-v2/experiments/aerial/RUNBOOK_wam_phase2_long_horizon.md)（阶段 2）**同一条航道**；室内只改**空间尺度与到达精度**，不另开方案。  
> **冲突裁决**：任何「室内专用捷径」（GT-PD、假里程计、夹具刷分、单失败补洞）与本文冲突 → **以本文为准并视为偏离，立刻拉回**。  
> **机器**：长闭环 → **125**，workspace **必须** 为独立目录 `/home/yao/aerial-indoor-wam`（与 phase2 `/home/yao/aerial-wam-v2` **分开**）；深 FT → **H100（经 125）**；Mac → 文档 / 接线 / handoff。  
> **旁证（非验收）**：`artifacts/indoor_*_20260828*` 夹具账 → **禁止**写入完成态。  
> **Workspace 身份**：见 125 上 `WORKSPACE_IDENTITY.md`。禁止在 `aerial-wam-v2` 里跑本室内 A0/B/C。

---

## 铁律：所有方案 Stick 主航道

```text
主航道（全仓唯一）
  单目 RGB + IMU + 高度计
        → 状态估计 \(\hat p,\hat\psi,\hat v\)
        → WAM（encode / 想象 / π）
        → 到目标
  深度 / 三区罩 = 仅安全

室内 = 同一主航道 × 更小空间 × 0.x m 到达
室外长航程 = 同一主航道 × 合法折线 + 局部胡萝卜
```

| 允许 | 禁止（偏离主航道） |
|------|-------------------|
| 改动作尺度、`success_dist`、室内语料分布 | 另立「室内夹具主线」 |
| 同一 \(\hat p\) 接口接 VIO / 滤波 /（显式声明的）gt_proxy | GT 世界位姿 PD / 「IBVS」当默认飞行核 |
| 高度计：室内优先下视测距，baro 辅助 | 把 baro≈GT 写成 Z 已解决 |
| 路点/A* 只作**任务生成** | densify / 跟踪器冒充 WAM 能力 |
| 全分布 FT（H100） | 单失败腿补洞、松门控凑数 |
| 深度 FT 服务罩 | 刷罩过门当导航成功 |

**开任何实验前必问**：是否直接服务「RGB+IMU+高度 → \(\hat p\) → WAM → 到点」？若否 → **停下或标已搁置**，不得占默认评测 / 默认策略 / 完成叙述。

---

## 0. 传感合同（与阶段 2 冻结对齐 · 室内不另立）

| 通道 | 角色 | 不做的事 |
|------|------|----------|
| **单目 RGB** | WAM 主视觉；VIO 前端 | 不是深度真值；默认验收不是画面认目标 |
| **IMU** | 姿态 / 角速度 / 加速度；VIO 核心 | alone 不能给无漂水平位姿 |
| **高度计** | \(z\) 锚定；**室内默认优先 rangefinder/ToF**，气压辅助 | 不替代水平定位 |

**状态估计**：`RGB + IMU + 高度计 → \(\hat p,\hat\psi,\hat v\)` → 与主航道相同的 `goal_rel` / π / 想象接口。  
**没有**独立于视觉惯性的「第三路神话里程计」；所谓里程计 = 上述估计器输出的相对运动。

### 0.1 位姿与 `goal_rel`（室内补钉 · 防假基线）

| 字段 | 冻结规则 |
|------|----------|
| `pose_source` | 必填：`vio_est` \| `odom_from_imu_rgb` \| `gt_proxy` |
| **主航道默认完成态** | **禁止**未声明的 `gt_proxy` |
| `goal_rel` | **必须**由 \(\hat p,\hat\psi\) 与目标算出；**禁止**默许 `obs.position`（AirSim GT）却报表写「未用 GT」 |
| 控机动作 | 只许 π（+ 合法安全罩改写）；`assist=gt_pd` 默认 **off**，仅对照 |
| **0.x m 验收坐标系** | 在 \(\hat p\) 下量相对目标距离；若主张世界系 0.x m，须先过估计器噪声/漂移消融。**禁止**「纯积分假 odom + 世界坐标门控」混用 |

仿真可用 `gt_proxy` 作估计器 stub，但报表必须写明；**不得**写成「无定位传感已飞通」。

### 0.2 产品一句话

室内小空间：与室外**同一主航道传感与大脑**，把到点精度做到 **0.x m**；学得策略是唯一飞行核。

---

## 1. 主线纪律（常驻）

1. **偏离 → 立刻拉回**。  
2. 报表强制：`controller_attribution`、`sensors_used`、`pose_source`、`used_gt_world_pose_for_control`、`goal_rel_pose_source`。  
3. 禁止单失败修模型。  
4. 禁止 GT-PD 轨迹当 BC 主料。  
5. STATUS「下一步」必须映射本文件阶段字母。  
6. **与阶段 1/2 runbook 冲突时**：传感合同以阶段 2 冻结表为准；室内尺度与 0.x m 以本文件 §0.1 为准；大脑=WAM 三方共同。

---

## 2. 一页诚实结论（现状）

| 项 | 事实 |
|----|------|
| **要什么** | Stick 主航道的室内 0.x m |
| **现在实际** | 室外 ckpt + 缩盒/微罩 + **GT-PD 近场** + GT 算 `goal_rel`；baro/「odom」未按合同 |
| **差距** | 换脑、GT 特权 `goal_rel`、尺度未进训练、合同未冻 |
| **夹具多路由账** | 非主航道验收 |
| **要不要重训** | Stick 主航道则 **要 FT**；禁单点补洞；禁零重训宣称达标 |
| **125 未冻合同的 A/B** | **不算**主航道基线；须按 §0.1 重跑 |

---

## 3. 目标结构（主航道）

```text
RGB ──encode──► z
IMU + 高度计 ─┐
RGB (VIO)    ┴► \(\hat p,\hat\psi,\hat v\)  ──► goal_rel
已知目标（标注/局部子目标）─────────────────────┘
                 │
        π(a | z, goal_rel) + 想象
                 │
              Δa ──► 深度/τ 罩（仅安全）──► 环境
```

| 模块 | 主航道角色 | 现状 |
|------|------------|------|
| WM + π | 唯一大脑 | 近场曾被 GT-PD 替换 |
| \(\hat p\) | `goal_rel` 与验收 | 仍默许 GT `obs.position` |
| 高度计 | \(z\) | 偏 GT/baro；室内应优先测距 |
| 深度罩 | 仅安全 | 近场分布未按室内训 |
| GT-PD / densify | 非主航道 | 对照 only |

---

## 4. 致命偏离清单（相对主航道）

1. 换脑（GT-PD / 跟踪器）  
2. GT 算 `goal_rel` 却称契约传感已满足  
3. 世界系 0.x m + 无回环积分位姿混用  
4. 只部署缩盒、训练仍室外尺度  
5. 安全罩冒充导航  
6. 单点补洞 FT  
7. 另写「室内专用方案」与主航道并行  

**展开分析（F1–F5 + 现状缓解）**：[`docs/handover/INDOOR_FATAL_DEFECTS_20260831.md`](../../docs/handover/INDOOR_FATAL_DEFECTS_20260831.md)。

---

## 5. 重训（仅服务主航道）

| 问 | 答 |
|----|----|
| Stick 主航道室内 0.x m？ | **必须**按合同 FT（H100） |
| 全网从零？ | 通常不必 |
| 失败腿专用？ | **禁止** |
| 合同未冻就 FT？ | **禁止** |

优先级：\(\hat p\) 接口同构 → π 全航段 → 训练期微盒与 0.x m → 深度近带（仅罩）。

---

## 6. 阶段（全部 Stick 主航道）

### 阶段 A0 — 合同落地（阻塞 · 先于原 A/B 验收）

- [ ] 本文件 + 阶段 2 传感表为唯一合同；删「独立里程计」表述。  
- [ ] 代码：`goal_rel` 走 \(\hat p\) 接口；`pose_source` / `goal_rel_pose_source` 落盘。  
- [ ] 默认 `assist=none`；禁未声明 GT 控机与 GT `goal_rel`。  
- [ ] 室内高度默认 rangefinder 字段（仿真可 stub，须声明）。  
- [ ] **作废**未声明 `pose_source` 的「主航道基线」数字。

### 阶段 A — 拆偏接线

- [ ] 默认飞行核仅 WAM；归因字段齐全。  
- [ ] 夹具 / GT-PD 仅 `assist` 对照。

### 阶段 B — 诚实基线（125）

- [ ] 主航道协议重跑；预期差于夹具账。  
- [ ] JSON：`pose_source`、attribution、到点、碰撞、罩介入。

### 阶段 C — FT（签字后 · H100）

- [ ] 室内全分布；同构观测；禁单失败过采样。  
- [ ] 每轮用阶段 B 协议回归。

### 阶段 D — 验收（125）

- [ ] held-out；attribution=`wam`；`pose_source`≠未声明 gt。  
- [ ] 世界系 0.x m 主张前须估计器消融。

---

## 7. 禁止的假进度

| 假进度 | 为何假 |
|--------|--------|
| GT-PD / 夹具刷 0.2 m | 换脑 |
| GT `goal_rel` + 报表「未用 GT」 | 静默违约 |
| 未冻合同的 A/B 当基线 | 假数 |
| 单失败补洞 / 松门控 | 训偏 / 指标游戏 |
| 另立室内方案 | 违反 Stick |
| 深度罩过门 | 安全 ≠ 大脑 |

---

## 8. 当前下一步

1. ~~E2d~~ ✅；~~E2e/E2f~~ ❌；~~E2g~~ ⏸；~~E2h~~ ❌（场景合格，合同 0/3 @0.20）。  
2. **进行中 = E2i v2**：**接线（E2i.0w）→ 罩 A/B（E2i.1）→ B2∥ / B1 序（E2i.2）→ 分阶 FT（E2i.3–4）**。  
3. **分析文档**：[`docs/handover/INDOOR_E2I_PLAN_20260831.md`](../../docs/handover/INDOOR_E2I_PLAN_20260831.md) **v2**  
4. **禁 E3**；禁关罩刷完成态；禁再堆 0.50 BC。

默认：**125 @ `/home/yao/aerial-indoor-wam`**；FT 快验 **4090 OK**；长 FT **H100**。  
**共享渲染器**：室内刀占用 `:41451` 时须停 Phase-2；结束后用 `recover_renderer_scene.sh outdoor` 归还 `env_airsim_16`。

### 8.5 E2e — @0.20 + 加长（已停）

| 步 | 结果 |
|----|------|
| E2e.1 | ❌ e2d 直评爆炸 / postFT 仍 0% @0.20 |
| E2e.2 | ✅ 又叠 HER+FT（未救 @0.20） |
| E2e.3/4 | ⏸ 一级不过停 |

### 8.6 阶段 E2f — 夹具 BC 冷启动（已完成 · FAIL）

| 步 | 结果 |
|----|------|
| E2f.1 | ✅ 20 arrived @`success=0.50` |
| E2f.2 | ✅ FT `v4_ac_ckpt_indoor_e2f_20260830` |
| E2f.3 | ❌ 0/3 seed @0.20；最佳 seed1 mean≈0.90 m（R07 0.56 / R13 1.23） |
| 停 | ✅ 按协议停；**不开 E3** |

**归因（诚实）**：不是「没数据」；BC 标签（0.50）与评测（0.20）不对齐 + 高介入示范难迁移。下一刀 = E2g 新规格。

### 8.7 阶段 E2g — 新规格夹具 BC（人令：加新规格数据）

**目标**：与合同同尺的进圈正例（`success=0.20`），过滤高罩介入后，训同一 π，再 `assist=none` 验收。

| 步 | 内容 | 过门 |
|----|------|------|
| **E2g.0** | `wait_airsim_idle`；必要时 `recover_renderer`（Phase-2 后 gt_pd yield≈0） | AirSim 空闲 |
| **E2g.1** | 采 `dataset_indoor_fixture_bc_e2g_020_*`：R07/R13，段长 5–6 m，`success=0.20`，`--keep-arrived-only`，`--max-intervention-rate 0.55`，罩 ON，`bc_tag=fixture_gt_pd_020`；可续采 | **n_arrived≥15** 且均值 `intervention_rate≤0.55` |
| **E2g.2** | 同构 gt_proxy FT @4090，init=`e2f`（或 e2d）；**主料=E2g.1**；可选混 ≤30% 旧 E2f 0.50 BC（须写比例） | — |
| **E2g.3** | 合同回归：`assist=none`、短段 6 m @**0.20**，**≥3 seed** | ≥2/3 seed 有到点 **或** mean≤0.8 m |
| **停** | 不过 → 停；禁 E3；禁关罩；禁再堆同规格 0.50 BC 冒充进展 | — |

**纪律**：夹具轨 = bootstrap；完成叙述只认 E2g.3。  
**状态**：⏸ **已停**（场景不合格；改 E2h）。

### 8.8 阶段 E2h — AirSim 室内场景（人令：首选推进）

**目标**：在 **真室内图**（非 `env_airsim_16`）上建立近障语料与合同评测。首选 **Building_99**；**Blocks** 仅冒烟/接线。

| 步 | 内容 | 过门 |
|----|------|------|
| **E2h.0** | 停 E2g；下载 Linux `Blocks` + `Building_99`（v1.8.0-linux）；`recover_renderer_scene.sh` | 二进制就位 |
| **E2h.1** | 启动室内图 + `indoor_scene_smoke.py`（yaw 扫） | `depth_min` 中位 **&lt;5 m** 且 skyish **&lt;0.5** |
| **E2h.2** | 室内短段生成（非室外 annotation 切段）+ 夹具/闭环采集 | 样本近障占比达标 |
| **E2h.3** | FT @4090 + `assist=none` 合同多 seed @0.20（室内段） | 另表 |

```bash
# 冒烟（先 Blocks）
bash experiments/aerial/scripts/recover_renderer_scene.sh blocks
export AIRSIM_CAMERA=0 AIRSIM_VEHICLE=drone_1
$AERIAL_PY experiments/aerial/scripts/indoor_scene_smoke.py \
  --out artifacts/indoor_scene_smoke_blocks.json

# 主场景
bash experiments/aerial/scripts/recover_renderer_scene.sh building99
$AERIAL_PY experiments/aerial/scripts/indoor_scene_smoke.py \
  --out artifacts/indoor_scene_smoke_building99.json

# 归还 Phase-2 室外图
bash experiments/aerial/scripts/recover_renderer_scene.sh outdoor
```

**状态**：❌ **E2h.3/E2h.4 FAIL**；shield-off diag best 0.63 m（仍 0/3 @0.20）。详见 [`INDOOR_E2I_PLAN_20260831.md`](../../docs/handover/INDOOR_E2I_PLAN_20260831.md)。

### 8.9 阶段 E2i — 罩重标定 + 近成功语料 + 分阶 FT（v2 · 人令：下一步）

**目标**：Building_99 场景合格前提下，解决 **π+罩 近场联合不可达**；分阶过门后再议 E3。完整分析见 [`INDOOR_E2I_PLAN_20260831.md`](../../docs/handover/INDOOR_E2I_PLAN_20260831.md) **v2**。

| 步 | 内容 | 过门 |
|----|------|------|
| **E2i.0** | E2h 结案；计划 v2 落盘 | 文档就位 |
| **E2i.0w** | yaml→eval/collect 罩；B1 近成功过滤接线 | 可复现 A/B |
| **E2i.1** | 室内 `ThreeZoneSpec` A/B（**需 AirSim**） | intervention<0.5；d_end↓>30%；collision 不恶化 |
| **E2i.2a** | B2 夹具 @0.20≥20（可与 E2i.1 并行） | arrived≥20 |
| **E2i.2b** | B1 `assist=none` 近成功≥50（**E2i.1 过门后**） | usable≥50；禁室外 annotation |
| **E2i.3** | C1 短 FT @4090（FT **不占** AirSim） | ≥2/3 seed @0.50 或 mean≤1.0 m |
| **E2i.4** | C1/C2 H100 长 FT（≥2000/≥1000 iter） | 合同 @0.20：≥2/3 seed 或 mean≤0.8 m |
| **停** | E2i.1 不过 → 禁 B1；C1 不过 → 停；C2 不过 → WM encode 评估；禁 E3 | — |

**完整分析+命令**：[`docs/handover/INDOOR_E2I_PLAN_20260831.md`](../../docs/handover/INDOOR_E2I_PLAN_20260831.md)  
**125 prompt**：[`docs/handover/INDOOR_MAINLINE_125_PROMPT_20260831.md`](../../docs/handover/INDOOR_MAINLINE_125_PROMPT_20260831.md)

---

## 9. 变更记录

| 日期 | 内容 |
|------|------|
| 2026-08-28 | 初版诚实账；主航道重锚定（仍写「里程计」并列） |
| 2026-08-29 | **全方案 Stick 主航道**：与阶段 2 传感合同对齐；钉死 \(\hat p\)/`goal_rel`/0.x m 坐标系；A0 阻塞未合同基线；删除独立里程计神话 |
| 2026-08-29 | C FT + D FAIL；开 **阶段 E**（同构位姿 + 室内闭环；禁错配 FT） |
| 2026-08-29 | E2 可学习过门；开 **E2b**（示范质量→收口）；未过门禁 E3 |
| 2026-08-29 | E2b FAIL；开 **E2c** 短程近成功；FT 允许 4090 fallback |
| 2026-08-29 | E2c 无近成功；开 **E2d HER** 子目标重标 |
| 2026-08-29 | E2d 短段 @0.50 过门；开 **E2e**（@0.20 + 加长课表；禁自动 E3） |
| 2026-08-30 | E2e @0.20 FAIL；开 **E2f** 夹具 BC 冷启动（同脑；合同评测） |
| 2026-08-30 | E2f 合同 FAIL；人令 **E2g** 新规格 BC（`success=0.20` + 低介入过滤） |
| 2026-08-30 | **场景审计 FAIL**：E2 系数据全是室外 `env_airsim_16` 短段（多垂直爬升）；人令首选推进 → **E2h 室内场景**；**E2g 停** |
| 2026-08-31 | **E2h.3 FAIL**：Building_99 FT + `assist=none` @0.20 → 0/3 seed；罩介入≈1.0；场景合格但 π 未进圈；禁 E3 |
| 2026-08-31 | **E2h.4 FAIL** + shield-off diag；开 **E2i**（罩重标定+近成功语料+分阶 FT）；见 `INDOOR_E2I_PLAN_20260831.md` |
| 2026-08-31 | **E2i plan v2**：修正 B1/B2 命令、A→B1 顺序、collision 过门、yaml 接线、AirSim 表 |
| 2026-08-31 | **致命缺陷文档**：`INDOOR_FATAL_DEFECTS_20260831.md`（F1–F5）；挂 LIVING/STATUS/§4 |
