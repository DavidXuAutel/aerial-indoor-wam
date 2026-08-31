# Aerial WAM 执行 Runbook（想象到点 · 诚实版）

> **日期**：2026-08-27  
> **本文件是什么**：按「结构 → 训练 → 数据 → 接大脑 → 验收」执行的**唯一日常入口**。  
> **方案全文**：[`docs/superpowers/plans/2026-08-27-imagination-to-goal-wam.md`](../../docs/superpowers/plans/2026-08-27-imagination-to-goal-wam.md)  
> **本质说明**：[`docs/handover/V4_MAINLINE_WAM_REANCHOR_DECLARE_20260827.md`](../../docs/handover/V4_MAINLINE_WAM_REANCHOR_DECLARE_20260827.md)  
> **125 交接（Mac 下线）**：[`docs/handover/V4_WAM_125_HANDOFF_20260827.md`](../../docs/handover/V4_WAM_125_HANDOFF_20260827.md)  
> **不是什么**：不是旧 V4 代号门流水账；与旧 [`RUNBOOK_v4.md`](RUNBOOK_v4.md) 冲突时，**以本文件 + 上列方案为准**（旧稿保留审计）。  
> **室内小空间（同主航道 · 尺度特化）**：[`RUNBOOK_indoor_0xm.md`](RUNBOOK_indoor_0xm.md) — 单目+里程计+高度计→WAM→到点；禁止 GT-PD/夹具冒充完成。

---

## 主线纪律（常驻 · 违反即改）

**主线唯一**：单目 RGB（+IMU 尺度/监督）→ 世界模型**想象**选动作 → 到点；深度/限速罩只做安全；学得策略才是大脑（不是直线启发式、不是路点跟踪器）。

1. **一切工作围绕主线**（结构接线、训练目标、数据、验收）。开新实验前先问：是否直接服务「想象到点」或为其必要前提（如碰撞头可信、5 Hz 闭环语料）。  
2. **若偏离主线 → 立刻停下并修正**：把资源拉回主线；旁支最多记一笔「已搁置」，不得占默认评测/默认策略/生产开关。  
3. **典型偏离（禁止当主战役）**：只刷安全罩过门；用启发式/路点跟踪冒充 WAM；关罩或事后降到点标准凑数；无目标旧策略热启当新大脑；把坐标目标结果写成「视觉找到目标」。  
4. 文档与 STATUS 的「当前下一步」必须能映射到本 runbook 步骤 A–G；映射不上 = 已偏，先改叙述再干活。

---

## 0. 一页诚实结论

| 项 | 事实 |
|----|------|
| **要做的事** | 单目 RGB（+IMU 尺度/监督），靠**世界模型想象**选动作，飞到目标；深度限速罩只防撞 |
| **现在接没接大脑** | **没有。** 默认仍是直线启发式采集；`enable_policy_update=false`；学得策略未当日常飞行核 |
| **目标从哪来** | 当前是仿真/标注里的**世界坐标**，再算机体系相对量——**不是**从画面认出目标。目标被墙挡住，对「坐标目标」几乎无影响；真·视觉搜目标仍未做 |
| **已改接线** | 策略/价值默认吃 `(z, goal_rel)`；想象环传目标；部署包装可算 goal_rel。旧无目标权重须**重训**，不能热加载当新大脑 |
| **机器** | **执行：cursor-125 Agent**（评测/B/C/文档/H100 跳板）；训 WM/π：**H100**（只经 125 SSH）；**Mac**：git + handoff，不开长 GPU、不直连 H100 |

**成功定义（产品）**：同协议评测上 **到点 ∧ 少严重碰撞**。  
**不是成功**：只把安全罩调过；只证明「不比直线启发式差」；接上路点跟踪器冒充 WAM。

---

## 1. 当前真实结构（对照用）

```text
RGB + 位姿 ──encode──► z
已知目标坐标 ──► goal_rel
                 │
        π(a | z, goal_rel)     ← 结构已有；日常默认未启用
                 │
              Δa ──► 深度/τ/p_coll 罩子（可改写）──► 环境

训练旁路：回放 → 想象 H 步 → 更新 π/V   ← enable_policy_update 默认关
世界模型更新：回放窗口 → RSSM           ← enable_wm_update 默认开
```

| 模块 | 角色 | 诚实状态 |
|------|------|----------|
| 世界模型 | 想象里预见下一步 | 在用；碰撞头是否「够区分撞/绕」待测 |
| 策略 π | 决定飞哪 | 结构已接目标；**默认不飞** |
| 深度 + 限速罩 | 安全 | 在用；不是导航 |
| 直线启发式 | 探针/采感知 | **默认在飞**；不是产品大脑 |
| 旧短程候选搜索 | — | 默认关；勿当大脑 |
| 路点跟踪 densify | 可选教师 | 可选；勿当部署大脑 |

---

## 2. 能留 / 别用错

| 留 | 用法 |
|----|------|
| AirSim/Mock、collector、5 Hz、NPZ（rgb/imu/vel/actions/goal） | 采集与评测 |
| 深度头 + 三线/限速罩 | 仅安全 |
| Torch WM + imagine + 有界 AC | 想象学习 |
| r60 / 近障合并包 | **预热**世界模型与深度，**不是**绕障到点老师 |

| 别当主方案 |
|------------|
| 关罩子刷到点 |
| 直线启发式当「部署导航」 |
| 无目标的旧搜索器当上界神话 |
| 路点跟踪器替换想象策略 |
| 把「目标看不见」当成已解决——坐标特权 ≠ 视觉目标 |

---

## 3. 执行顺序（必须按序）

> **「按序」指验收闸门，不是「同一时刻只能干一件」。** 可并行项见 [§3.1](#31-可并行--可同步准备)。

### 步骤 A — 锁结构（已大部分完成）

- [x] 策略/价值 `condition_on_goal=True`（默认）
- [x] 想象环传 `goal_rel` 并写入 rollout
- [x] 部署包装从观察目标算 `goal_rel`
- [x] 单测保持绿：`test_actor_goal_cond.py`（125：2 passed，2026-08-27）

**完成标准**：无目标旧 ckpt 加载会告警且为 goal-blind；新训必须带 `condition_on_goal`。

### 步骤 B — 想象里碰撞是否有用

在打开策略长训之前做一次诊断（mock 或短闭环均可）：

1. 固定 z，构造「朝墙」vs「侧向绕」的想象回报差。  
2. 若差值≈0 → **先修碰撞头/损失**，不要猛训 π。  
3. 记录产物路径与数字；不写「感觉可以」。

**完成标准**：书面记下「撞明显更差」或「不够，已开修」。  
**入口**：`experiments/aerial/scripts/wam_imagine_coll_rank.py`（可用现有 WM ckpt，**不依赖**新采语料）。

**2026-08-27 实测 → 不够，已开修：**

| 产物 | n | median p_coll 差（前−侧） | 判定 |
|------|---|---------------------------|------|
| `artifacts/wam_imagine_coll_rank_p45_n32_20260827.json` | 32 | ≈ −0.00015 | insufficient |
| `artifacts/wam_imagine_coll_rank_r60_n32_20260827.json` | 9 | ≈ 0 | insufficient |
| `artifacts/wam_imagine_coll_rank_collft_act_n32_20260827.json` | 32 | ≈ −0.0008 | insufficient |
| `artifacts/wam_imagine_coll_rank_h100full_20260827.json` | 32 | **0.0018**（前 mean_p≈0.23，侧≈0.24） | insufficient |

- 基线：前/侧 `mean_p_coll` ≈ **2e-5**（头塌成常数近零）。H100 全量 WM 后升至 ≈0.23，但前/侧仍几乎无差。回报差来自进展几何，**不算**碰撞可用。  
- **已开修（仅训练损失，未改部署罩）**：`coll_near_depth_m=5.0` + auto pos_weight；动作条件 `p(coll|z,a)`。  
- **H100 全量 WM**（2026-08-27）：`wm_ckpt_coll_full_20260827/wm_step_1000.pt`；复测 `…_h100full_…json` → **仍 insufficient，禁止 E**。  
- **下一闸**：加强 coll 监督/损失 → H100 再训 → 125 重跑 B；C2 语料已齐（31 ep）可作 D 预热。

#### 步骤 B′ — latent 探针 + coll 读出头诊断（**不替代 B 主闸**）

> **为什么有 B′**：B 失败时不知道是「latent 没编码几何」还是「coll_head 读不出」。B′ 只做**只读分叉诊断**，帮助选下一刀；**E 仍只认 B 的 `median_p_coll_gap ≥ 0.05`**。

**分工（与深度头）**

| 轨 | 测什么 | 过不过 E |
|----|--------|----------|
| **B（主闸）** | 想象里 `p_coll(z,a)` 前/侧能否分开 | **硬条件** |
| **B′（诊断）** | latent 里有没有几何；读出头是否太弱；D̂ 上界 | **不替代 B** |
| **深度头 D̂** | 部署罩子 ⓪c/⓪i | 与 B 正交，不算白训 |

**B′-1 · latent 线性探针（只读，125）**

在同一批 B 采样点 `(episode, t)` 上：

1. `z_feat = concat(h, z)`（与 `coll_head` 同宽，1536-D）。  
2. 标签：`y = center_depth_m`（NPZ GT depth 中心 patch 中位数，与 `wam_imagine_coll_rank.py` 一致）。  
3. 拟合 **ridge 回归** `y ~ z_feat`（或 1 层小 MLP，hold-out 25%）。

| 指标 | 解读 |
|------|------|
| hold-out **R² ≥ 0.3** 且 **MAE < 2 m** | latent **含**可用近场几何 → 优先修 **coll 读出头/损失**（B′-3） |
| R² ≈ 0 或 MAE 很差 | latent **未编码**几何 → 优先改 **表示目标**（coll 损失权重、对比监督、窗口 encode） |
| 仅「前向扇区 depth」可预测、全图 depth 不行 | 几何偏局部；coll 应用 **前向 min-depth aux**（对齐 `forward_min_depth_torch`） |

产物：`artifacts/wam_latent_depth_probe_<日期>.json`（`r2`, `mae_m`, `n`, `wm_ckpt`）。

**B′-2 · encode 对照（只读，125）**

当前 B 用单帧 `encode(obs)` 且 **`h=0`**；训练是窗口 teacher-forcing。对同一 `z0` 样本做两路：

| 路 | 做法 |
|----|------|
| **A（现状）** | `encode(obs)` → `h=0` posterior |
| **B（对照）** | 回放窗口 `[t−W+1 … t]` teacher-forcing 取 **末帧 `h‖z`**（`W=8`，与训练一致） |

两路各跑一遍 `wam_imagine_coll_rank.py` 逻辑，比 `median_p_coll_gap`。

| 结果 | 解读 |
|------|------|
| B 显著好于 A（gap 升 ≥3× 且 >0.02） | **encode 偏瘦**是主因之一 → B 脚本应切到窗口 `h` |
| A≈B | 不是 encode 问题 → 看 B′-1 / B′-3 |

产物：`artifacts/wam_imagine_coll_rank_hwindow_<日期>.json`（与 B 同 schema）。

**B′-3 · coll 读出头 v2（需短训，H100；仍须 B 复测）**

对齐已过关的 **reward 头**设计，给 coll 同等待遇（**仅训练 coll 支路 + `coll_feat_proj`**，不动 deploy 罩子）：

```text
coll_in = coll_feat_proj(h‖z) ‖ action ‖ coll_aux
```

`coll_aux`（训练可用 GT，推理只用可在线量）建议 4 维起：

| 维 | 含义 | 训练 | 想象/部署 |
|----|------|------|-----------|
| 1 | `log1p(center_depth_m)` | GT depth | 暂无 → 先探针验证后再接 D̂ |
| 2 | `forward_min_depth_m`（前向扇区） | GT depth | 可接 `depth_min_pred`（**仅作对照轨 B′-4**，不进主闸） |
| 3 | `action[0]`（前向分量） | ✓ | ✓ |
| 4 | `‖action[1:2]‖`（侧向幅度） | ✓ | ✓ |

训练：冻结 encoder/RSSM/decoder/reward；只训 `coll_feat_proj` + `coll_head`（或 2 层 MLP）；损失同现 coll BCE + near-depth soft；可加 **同 z0 前/侧 hinge**：要求 `p_coll(fwd) − p_coll(lat) ≥ margin`。

短训后 **125 重跑 B**（主闸）。B′-3 自身无独立 pass 阈——**以 B 为准**。

产物 ckpt：`wm_ckpt_coll_v2_<日期>/`；B 产物：`artifacts/wam_imagine_coll_rank_collv2_<日期>.json`。

**B′-4 · D̂ oracle 上界（只读，125，可选）**

用 **GT depth**（诊断 only）构造 oracle 分数，在同一 `z0` 上想象 H 步：

```text
oracle_risk(a) = mean_t  1[ forward_min_depth(GT) < d_thresh ]
```

比 `oracle_gap = oracle_risk(fwd) − oracle_risk(best_lat)` 的中位数。

| 结果 | 解读 |
|------|------|
| oracle_gap 大（≥0.3）而 B gap≈0 | **几何在数据里可分**，WM coll 路径没学到 → 支持 B′-3 / 加强监督 |
| oracle_gap 也小 | 采样帧/动作盒本身分不开 → 调 B 采样（更近障、`stride`、动作幅度） |

产物：`artifacts/wam_coll_oracle_gtdepth_<日期>.json`。**不得**用 oracle 过 E。

**推荐执行顺序（125 空档即可）**

```text
B′-1 探针  →  B′-2 encode 对照  →  （并行可选 B′-4 oracle）
       ↓
  若 latent 有几何 → H100 做 B′-3 短训 → 重跑 B
  若 latent 无几何 → 先改 coll 损失/对比目标/窗口监督，再 B′-3
```

**实现（2026-08-27）**

| 脚本 | 作用 |
|------|------|
| `experiments/aerial/scripts/wam_latent_depth_probe.py` | B′-1 |
| `experiments/aerial/scripts/wam_imagine_coll_rank.py --encode-mode window` | B′-2 |
| `experiments/aerial/scripts/wam_coll_head_v2_ft.py` | B′-3（待接） |
| `experiments/aerial/scripts/wam_coll_oracle_rank.py` | B′-4（待接） |

**125 一键（与 h100full 同 ckpt / 语料 / stride=2）：**

```bash
source experiments/aerial/scripts/env_4090.sh
DS=experiments/aerial/rl/artifacts/dataset_v0_p45_merged_20260821
CKPT=experiments/aerial/rl/artifacts/wm_ckpt_coll_full_20260827/wm_step_1000.pt
$AERIAL_PY experiments/aerial/scripts/wam_latent_depth_probe.py \
  --dataset "$DS" --wm-ckpt "$CKPT" --stride 2 --max-samples 32 \
  --out artifacts/wam_latent_depth_probe_20260827.json
$AERIAL_PY experiments/aerial/scripts/wam_imagine_coll_rank.py \
  --dataset "$DS" --wm-ckpt "$CKPT" --stride 2 --max-samples 32 \
  --encode-mode window --window 8 \
  --out artifacts/wam_imagine_coll_rank_hwindow_20260827.json
```

**纪律**：B′ 结论写进 STATUS + 本表备注；**禁止**用 B′-4 oracle 或 D̂ 对照轨替代 B 开 E。

### 步骤 C — 数据

1. **日常预热**：继续可用现有带深度的闭环包训 WM/深度（标明用途=感知/动力学）。  
2. **导航相关**：按 **5 Hz** 采 RGB+IMU（+深度）+ 动作 + **goal** + 碰撞；尽量筛 **到点且少撞** 的局（可选模仿热身）。  
3. **禁止**：用「直线启发式撞墙高 progress」的包当绕障老师。  
4. **路点 densify**：仅当可选教师；失败可停，不阻塞主路径。

采集入口（现有）：

```bash
# 125：感知/WM 向闭环（启发式可采，但勿当导航老师）
source experiments/aerial/scripts/env_4090.sh
$AERIAL_PY -m experiments.aerial.rl.collect_dataset \
  --backend airsim --host 127.0.0.1 --step-hz 5.0 --grab-depth \
  --episodes 32 --annotation artifacts/seen_airsim16_m1a20.json \
  --out experiments/aerial/rl/artifacts/dataset_wam_loop_<日期>
```

导航向（可选教师，筛到点）另有：`collect_path_expert_dataset.py`（densify / path expert；失败不阻塞）。

### 步骤 D — 训世界模型（H100）

- 用步骤 C 的闭环包（或合格旧包）更新 RSSM。  
- 过关看：损失有界 + **步骤 B 的碰撞区分**不回退。  
- 配置：`dynamics.kind=torch`，`corrector.enable_wm_update=true`。

### 步骤 E — 训策略（大脑）（H100，作业内开开关）

1. **必须**新结构：`condition_on_goal=True`，从零训（禁无目标旧权重热启当新大脑）。  
2. 作业内临时 `enable_policy_update=true`（或等价训练入口）；**不要**先改生产 yaml 默认。  
3. 想象 H≤15；动作盒与 `step_hz=5` 一致。  
4. mock 先冒烟：loss 有界、朝目标进展非零。  
5. 再上 125 短评。

### 步骤 F — 接大脑（改默认飞行核）

**仅当**步骤 G 的验收通过后：

1. 采集/评测默认策略改为 `LatentActorDeployPolicy`（加载新 ckpt）。  
2. 生产配置才允许讨论长期 `enable_policy_update` / 部署 flip。  
3. 直线启发式退回「仅探针」。

**未验收前禁止**：把启发式换成「未过门的 π」并对外宣称 WAM 已通。

### 步骤 G — 验收（产品）

事先写死（可改数字，但须**跑前**写在本文件或当次日志）：

| 项 | 建议首版 | 说明 |
|----|----------|------|
| 评测条数 | n≥16，权威 | 不足则结论非权威 |
| 到点 | 率 ≥ **0.25** | 半径与训练 `success_dist_m`（默认 3 m）一致；**不要**偷换成 20 m 充数 |
| 严重碰撞 | 事先写上限或不差于对照臂 | 对照臂须说明是谁 |
| 决策路径 | RGB→z→(z,goal_rel)→Δa→罩子 | 日志/配置可核对 |

未过：停在步骤 E/B，**不**接大脑，**不**降阈值凑过。

### 3.1 可并行 / 可同步准备

闸门依赖（**不可**跳过）：

```text
A(结构绿) ──► B 结论书面化 ──► E 长训 π
                │
C 语料就绪 ──► D 训 WM ──►（B 不回退）──► E
E + 跑前冻结的 G 表 ──► 短评 ──► G PASS ──► F
```

**现在就可以同步开的（推荐立刻标工）：**

| 并行项 | 谁跑 | 与谁并行 | 说明 |
|--------|------|----------|------|
| **✅ C1 预热语料盘点** | Mac/125 只读 | A / B | 登记现有 `dataset_v0_*` / p45 路径与用途标签（WM预热 ≠ 导航老师）；**零采集成本** |
| **✅ C2 导航向新采（5 Hz + goal）** | **125** | **与 B 同步** | **不依赖** B 出数；启发式可采但 meta 必须标 `role=wm_loop` 或 `role=nav_candidate`；**禁止**事后当绕障老师除非筛到点 |
| **✅ B 碰撞区分** | 125 或 H100 短跑 | **与 C2 同步** | 吃**现有** WM ckpt + 旧包即可；入口 `wam_imagine_coll_rank.py` |
| **✅ A 单测保绿** | 125 | 与 B/C | `pytest …/test_actor_goal_cond.py` |
| **✅ G 跑前冻结表** | Mac 文档 | 全程 | 把 §G 数字抄进当次 `artifacts/wam_accept_protocol_<日期>.md`（可改数字但须**训前**落盘） |
| **✅ C4 densify / path expert** | 125 | 与 B/C2 | **可选**；0 usable 可停；**不阻塞** E |
| **⚠️ D 用旧包预热 WM** | H100 | 可与 C2 **部分重叠** | 仅当包已标「预热」且 **B 已有基线数字**（或接受「训完必须重跑 B」）；**若 B=不够，先修碰撞头再长训 D** |
| **❌ E 长训 π** | — | — | **必须** A 绿 + B 书面结论（够用或已修）+ 有可用语料 |
| **❌ F 接大脑** | — | — | **必须** G PASS |

**机器并行建议（少抢卡）：**

| 机 | 现在同步跑 |
|----|------------|
| **125** | **默认 Agent 执行**：B/B′、C、STATUS；**经 125 SSH 开 H100** |
| **H100** | coll 损失再训 WM；**勿**无 B 猛训 π |
| **Mac** | `git push` + handoff；**禁止**代跑 125/H100 任务 |

**明确不同步（会再次偏航）：** 新开罩子/深度 FT 战役；无 B 结论开 E；把 C2 启发式包直接当 E 的模仿主集。

---

## 4. 「目标被遮挡」怎么写进执行（避免自欺）

| 阶段 | 诚实做法 |
|------|----------|
| **现在（坐标目标）** | 目标来自标注/环境坐标；遮挡不测「看不见」。文档与对外说明必须写：**特权目标，非视觉目标** |
| **下一步（仍属本 runbook 范围外的增强）** | 要做真单目：最后可见方位记忆、搜索动作、检测置信；想象在「目标信念」上选路。单独立项，不与「坐标到点」混报完成 |

本 runbook **验收只覆盖坐标目标下的想象到点**。视觉搜目标未做完，不得写「单目找到目标」。

---

## 5. 常用命令（125 / H100）

```bash
# 125 环境
source experiments/aerial/scripts/env_4090.sh

# 结构单测（须有 torch）
$AERIAL_PY -m pytest experiments/aerial/rl/tests/test_actor_goal_cond.py -q

# 策略训练入口（示例；具体超参见 train 脚本 / yaml 作业覆盖）
# 务必确认 condition_on_goal 写入 ckpt config
```

H100：由 **125** SSH 拉齐代码与语料后训 WM / AC；**禁止从 Mac 直连或开长训**。

---

## 6. 明确停止条件

出现任一情况 → **停并写原因**，不要平行开罩子大战：

1. 想象里撞墙与绕开回报几乎无差别，仍强行长训 π  
2. 用关罩 / 放大到点半径 / 换简单场景 **事后**充到点  
3. 未验收就把启发式默认改成未过门 π  
4. 把路点跟踪到点率写成「WAM 到点」  
5. 把坐标目标结果写成「图像目标可见性已解决」

---

## 7. 进度勾选（活页）

| 步骤 | 状态 | 产物 / 备注 |
|------|------|-------------|
| A 结构 | **完成** | goal 条件 π；125 `test_actor_goal_cond` 2 passed（2026-08-27） |
| B 碰撞区分 | **不够** | B′：**weak_geometry**；window gap≈single 0.0018；coll_rep H100 后 gap=**−0.0020** 仍 insufficient；下一刀 **代码级 coll 监督**（非 B′-3）；**禁止 E** |
| C 数据 | **125 C2 完成（2026-08-27）** | `dataset_wam_loop_20260827/` · **34 npz / 33 OK** · meta `role=wm_loop`；topup `episode_00031–00033`；`logs/wam_c2_collect_20260827.log` |
| D WM | **DONE（H100 2026-08-27）** | `wm_ckpt_coll_full_20260827/wm_step_1000.pt`；log `logs/wm_coll_full_h100_20260827.log`；B 仍 insufficient |
| E 策略重训 | 未做 | **不可**在 B 未过阈时长训 |
| F 接大脑 | **未做** | 须 G PASS |
| G 验收 | 未做 | **协议表可立刻冻结** |

更新本表时只写路径与数字，不写代号战役名。
