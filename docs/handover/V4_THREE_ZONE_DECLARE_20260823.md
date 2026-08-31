# V4 诊断声明：三线限速方案结论（2026-08-23）

> **性质**：跑后结案 + **部署接线**（2026-08-23）。`safety.kind: three_zone` 已写入 `configs/aerial_rl.yaml`；`enable_policy_update` 仍 false。  
> **深度头冻结**：部署/基线继续 **老头** `depth_ckpt_da3_r60_20260814`；v1–v3 FT **不部署**。  
> **部署路线（2026-08-23 裁定）**：**三线 + D** — `D̂` 驱动分级限速（主控）；`τ` 仅应急 latch；**不推进** #24 (b) 全面 D→τ 主触发（`5ao` 挂起）。  
> **与现行 gate 关系**：⓪d@3.0 m **退役**为 deploy primary；离线 primary 待 **⓪h engage-miss** re-freeze。

## 0. 问什么

在 **5 m/s 巡航、5 Hz、反应延迟 0.2 s** 下，能否用 **分级速度线**（远→近减速→刹停）替代「单点 3 m 硬触发」，并在 **老头 D̂** 的实测误差带内 **动力学可行**？

## 1. 方案定义（本诊断冻结）

| 符号 | 含义 | 默认 |
|------|------|------|
| `L1` | 外圈速度线上界距离 | **8 m**（备选 7 m） |
| `L2` | 中圈速度线上界距离 | **5 m** |
| `L3` | 内圈刹停线 | **1.5 m**（对齐 frozen ④ 近碰带） |
| `v1` | `L1` 内限速 | **2 m/s** |
| `v2` | `L2` 内限速 | **1 m/s**（备选 0.75 m/s） |
| `v_stop` | `L3` 内目标 | **0.2 m/s** |
| `v_cruise` | 巡航 | **5 m/s** |
| `a_max` | 最大减速度（bang-bang 上界） | **2.5 m/s²**（设计保守值）；**#28 实测主动制动 p90 ≈ 3.23 m/s²** |
| `dt` | 控制周期 | **0.2 s**（5 Hz） |
| `delay_s` | 感知+执行延迟 | **0.2 s**（1 步） |

**engage 外边界**（开始减速的真实距离）：

```text
engage_outer = L1 + (v_cruise² − v1²) / (2·a_max)
```

默认 **8/5/1.5 @ 2/1** ⇒ **engage_outer = 12.2 m**。

控制律（诊断用 bang-bang，未写入 `safety.py`）：

```text
d > L1  → 规划减速至 v1
L2 < d ≤ L1 → 规划减速至 v2
L3 < d ≤ L2 → 规划减速至 v_stop
d ≤ L3  → v_stop
```

## 2. 动力学可行性（Mac 仿真 · 已单元测试）

制动距离 `need(v0, v1, a) = (v0² − v1²) / (2a)`：

| 段 | 需要距离 | 可用距离 | 余量 |
|----|----------|----------|------|
| 5→2 m/s | **4.2 m** | L1−L2 = **2 m**（7 m 外圈） | **❌ 不够** |
| 5→2 m/s | **4.2 m** | L1−L2 = **3 m**（8 m 外圈） | ⚠️ 段内不够，须 **提前在 engage≥12.2 m 开始** |
| 2→1 m/s | **0.6 m** | L2−L3 = **3.5 m** | ✅ |
| 1→0.2 m/s | **0.19 m** | — | ✅ |

| 方案 | engage_outer | 动力学（含 delay=0.2s） | 结论 |
|------|--------------|-------------------------|------|
| **7/5/1.5 @ 2/1**（用户原案） | 11.2 m | ❌ L1 段余量 0 | **不可行** |
| **7/5/1.5 @ 2/0.75** | 11.2 m | ✅ | **可行**（牺牲中圈速度） |
| **8/5/1.5 @ 2/1**（推荐） | **12.2 m** | ✅ | **可行** |

**关键结论**：7 m 外圈 @ 2 m/s **不是深度问题，是运动学不够** — 5 m/s 降到 2 m/s 需要 4.2 m，而 7→5 m 只有 2 m。

## 3. 反推深度精度预算（a=2.5, delay=0.2s）

欠读（D̂ > GT）⇒ 晚 engage ⇒ 以 **max_engage_delay_m** 为各边界允许欠读上界：

| 边界 | GT 参考 | p95 欠读预算 | 相对误差（σ_rel） |
|------|---------|--------------|-------------------|
| engage @ **12.2 m** | 外圈开始 | **≤ 3.0 m** | ≈ **25%** |
| **L1 = 8 m** | 2 m/s 线 | ≤ 3.0 m | ≈ 38% |
| **L2 = 5 m** | 1 m/s 线 | **≤ 2.4 m** | ≈ **48%** |
| **L3 = 1.5 m** | 刹停线 | ≤ 3.3 m | ≈ 220%（段短，主要靠速度已低） |

对比 frozen **⓪d@3.0 m**（≈2% σ_rel）：三线预算 **松 1–2 个数量级** — 这是设计意图（用距离换速度梯度），不是漏检。

## 4. 4090 / H100 离线实测（老头 · `v4_three_zone_eval.py`）

### 4a. 对照语料 `p45_merged`（2026-08-22）

语料：`dataset_v0_p45_merged_20260821`；D̂ = 老头前向锥 `D̂_fwd`。

| 方案 | 切片 | 动力学 | 深度 vs 预算 | 总判 |
|------|------|--------|--------------|------|
| **8/5/1.5 @ 2/1** | hold035 | ✅ | ✅ | **✅** |
| 8/5/1.5 @ 2/1 | full77 | ✅ | ❌ engage p95欠读 **3.01 m** > 3.0 m（n=24） | ❌ 边际 |

- **产物**：`artifacts/v4_three_zone_oldhead_{hold035_8m,full77_8m,…}_20260822.json`

### 4b. TZ-3Z 语料 `20260823_full`（2026-08-23 · **54 ep** = 42 open + 12 near）

语料：`dataset_v0_three_zone_oldhead_20260823_full`；125 shield-on 采集 + H100 评。

| 切片 | engage_outer | cap_l1 | cap_l2 | cap_l3 | 总判 |
|------|--------------|--------|--------|--------|------|
| hold035 | n=32，p95 **0.95 m** | n=21 | n=40，p95 **0.63 m** | n=32，p95 **1.37 m** | **✅** |
| full77 | n=97，p95 **0.99 m** | n=46 | n=93，p95 **1.33 m** | n=32，p95 **1.37 m** | **✅** |

- **产物**：`artifacts/v4_three_zone_branch_{hold035,full77}_20260823_full.json`
- **读法**：近障 12 ep 补入后 hold035 **首次有 L 带 support**；仍为 `authoritative=false`（诊断级）。

### 4c. ⓪h engage-miss（三线 deploy primary · 2026-08-23 冻结）

替代退役的 **⓪d@3.0 m** 作三线 + D 路线的离线 functional primary（`v4_three_zone_eval` 内嵌）。

| 项 | 冻结值 |
|----|--------|
| **条件帧** | `GT_fwd ≤ engage_outer_m`（默认 **12.2 m**，8/5/1.5 @ 2/1） |
| **miss** | `D̂_fwd > engage_outer_m`（欠读 ⇒ 晚 engage） |
| **p_engage_miss** | ≤ **0.10**（provisional；⓪d 为 0.05） |
| **max_consecutive_miss** | < **4**（允许最多 3 连 miss；⓪d 为 <2） |
| **对照** | `0d_legacy` 仍在同 JSON 输出（L3=1.5 m），**不作 deploy primary** |

**总判（TZ-3Z）**：`kinematic_feasible ∧ depth_vs_budget.all_bands_ok ∧ 0h.ok`。

## 5. 与 V4 冻结 gate 的关系

| 项 | 现行 frozen | 三线方案 |
|----|-------------|----------|
| 触发哲学 | 单点 **3 m** latch | **12.2 m** 开始渐变减速 |
| ⓪d primary | D̂@3 m miss rate | 不适用（改用 engage / 带内预算） |
| ⓪f(3) | 3–8 m 误触 | 不同几何（按 L1/L2/L3 分带） |
| gen-4 latch | 3 m 一触整局废 | 需重新定义 latch 语义 |

**不杀 V4**：阻塞的是 **P8 / enable_policy_update** 在 **现行 primary** 下过 gate；三线可作为 **并行安全合同** 另签。

**与 GATE #24 (AN) 一致**：⓪d@3 m 在 D̂ 通道 **理论上不可达**；三线用 **更远的 engage + 更松的深度预算** 换可部署性。

## 6. 与 Dream to Fly (arXiv:2501.14377) 的对照（摘要）

- DTF：**竞速穿门、CTBR、最高 8–9 m/s、碰撞 −4 终止** — **无** 深度硬罩 / 3 m 线。
- 本项目：**导航绕障、body Δ @ 5 Hz、硬 shield** — 三线是 **部署安全层**，DTF **不能** 为 3 m 触发或 ⓪d 精度背书。
- **可借鉴**：DreamerV3 配方、progress 奖励、机动惩罚量级（0.01）。
- **不可照搬**：64×64、CTBR、无 standoff、高速开阔赛道假设。

## 7. 推荐基线（诊断级，未升格 deploy）

1. **首选**：**8 / 5 / 1.5 m @ 2 / 1 / 0.2 m/s**，engage ≥ **12.2 m**。
2. **备选**（坚持 7 m 外圈）：**7 / 5 / 1.5 @ 2 / 0.75 / 0.2**，engage ≥ **11.2 m**。
3. **禁止**：**7 / 5 / 1.5 @ 2 / 1**（动力学不可行）。
4. **`a_max=2.5`**：相对 #28 实测 **偏保守**（主动制动 p90≈3.23）；保留 2.5 作设计余量，或改用 **3.0** 收紧 engage 距离（8 m 方案 engage 可从 12.2→约 11.3 m）。

## 8. 未决 / 下一步

| # | 项 | 状态 |
|---|-----|------|
| **#28** | 5 Hz 速度曲线 + 实测 `a_max`（rgb / depth） | ✅ **2026-08-23 DONE**（见下） |
| — | 三线写入 `safety.py` | ✅ `ThreeZoneSpeedShield` + yaml `kind: three_zone` |
| — | ⓪h engage-miss primary | ✅ **冻结**（§4c）；harness 在 `v4_three_zone_eval` |
| — | **TZ-3Z** 125 采 + H100 评 | ✅ **DONE** — `20260823_full` **54 ep**；hold035/full77 **双 PASS** |
| — | TZ-3Z P1 穿 L 带 | ✅ **DONE** — near **12 ep**（f9+g3→fg）；L 带有 support |
| — | shield-on 5 Hz 速度曲线 | 🟡 **P3 进行中** — `step_hz_velocity_profile --shield three_zone` |
| — | **部署路线：三线 + D** | ✅ **2026-08-23 裁定**（见 DECLARE 头注）；⓪h **已冻**（§4c） |
| — | `#26` τ-miss / `5ao` (b) 全面 τ 化 | ⏸️ **挂起**（非三线 deploy 阻塞项） |
| — | `5ao` 未签前 | 不得剥 D̂ OR 腿 |

## 9. #28 5 Hz 速度曲线实测（4090 loopback · 2026-08-23）

harness：`step_hz_velocity_profile.py`；`step_hz=5`；phases = accel→cruise→coast→brake。

| 模式 | achieved_hz | v_cruise | tracking | brake decel p90 | coast decel p90 |
|------|-------------|----------|----------|-----------------|-----------------|
| RGB-only | **4.993** | **4.85 m/s** | 0.907 | **3.23 m/s²** | 2.73 m/s² |
| grab_depth | **4.990** | **4.84 m/s** | 0.893 | **3.23 m/s²** | 2.72 m/s² |

- **产物**：`artifacts/step_hz_profile_5hz_{rgb,depth}_20260823.json`
- **读法**：yaml `step_hz=5` **可冻结**（wall_dt≈0.200 s）；巡航实测 **~4.85 m/s**（<5 因逐步跟踪 ~90%）；**深度抓取不拖慢 5 Hz**（与 RGB 几乎同）。
- **三线含义**：`a_max=2.5` 比实测主动制动 **低 ~22%** ⇒ engage 距离 **偏长**（更保守）；shield-on 路径 **未测**（待另跑）。

## 10. 产物与 harness

- **运动学 + 深度预算**：`experiments/aerial/rl/v4_three_zone_eval.py`
- **单元测试**：`experiments/aerial/rl/tests/test_three_zone_eval.py`（4 tests）
- **速度曲线**：`experiments/aerial/rl/step_hz_velocity_profile.py`
- **状态登记**：[`V4_RUNBOOK_125_STATUS.md`](V4_RUNBOOK_125_STATUS.md) §#27 / §#28
