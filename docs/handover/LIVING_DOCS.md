# 活文档阅读清单（2026-08-18）

> **用途**：回答「现在该读哪些活文档」。只列**仍在维护 / 决定现状**的入口；历史备忘与已闭合细节按需下钻。  
> **防误读**：`RUNBOOK_v0.md` §8 晚¹⁹–²² / 任何「merge 从未 exit 0」叙述 = **2026-08-12 快照**，不是现状（V0 已于 08-14 merge PASS）。  
> **2026-08-28**：本仓若在跑 **室内 0.xm** 轨，优先读下方 **A0**，勿把 GT-PD demo 成绩写进 V4/WAM 主线完成态。  
> **2026-09-01**：室内 **E2i.C = S3→S1→S2**（人令已锁）见 [`INDOOR_E2I_C_PLAN_20260901.md`](INDOOR_E2I_C_PLAN_20260901.md)；**E3 须人令**。

---

## A0. 室内 WAM（主航道尺度特化 · Stick）

| 顺序 | 文档 | 读什么 |
|---|---|---|
| **1** | [`INDOOR_E2I_C_PLAN_20260901.md`](INDOOR_E2I_C_PLAN_20260901.md) | **当前刀 = C**：S3→S1→S2 |
| **2** | [`INDOOR_0XM_STATUS.md`](INDOOR_0XM_STATUS.md) | 勾选 / S3 跑中 |
| **3** | [`INDOOR_E2I_B_POSTMORTEM_20260901.md`](INDOOR_E2I_B_POSTMORTEM_20260901.md) | B 失败拆因 |
| **4** | [`INDOOR_FULL_STACK_20260831.md`](INDOOR_FULL_STACK_20260831.md) | 方案/模型/接线快照 |
| **5** | [`../../experiments/aerial/RUNBOOK_indoor_0xm.md`](../../experiments/aerial/RUNBOOK_indoor_0xm.md) | §8.9 E2i |

**现状一句话（09-01）**：**E2i.C S3 在 125 跑**（A vs B @0.50 定主头）。B@0.20 已废。E3 仍禁。  

**禁止**：关罩当完成态；夹具成绩当完成态；GT-PD 作默认飞行核；无人令开 E3；同款近场 BC 碰运气。

---

## A. 必读（当前主线）

| 顺序 | 文档 | 读什么 |
|---|---|---|
| 1 | [`V4_GATE_STATUS.md`](V4_GATE_STATUS.md) | **当前阶段**一句话：V4 merge 状态、下一轨 |
| **1b** | [`RUNBOOK_v4.md`](../../experiments/aerial/RUNBOOK_v4.md) | **执行入口**：**下一步 = P4.5**。P3 = **`insufficient_support`（非 ⓪ FAIL）**；P1 FAIL；P4 已跑须重跑。R-16 运营 **(B)**。判据看提案 §4.6。机上 [`V4_RUNBOOK_125_STATUS.md`](V4_RUNBOOK_125_STATUS.md) |
| 2 | [`V4_PROGRESS_DIAG_125_STATUS.md`](V4_PROGRESS_DIAG_125_STATUS.md) | **① 诊断 DONE**：反目标飞；规格 goal-blind + 单 mock goal |
| 2b | [`V4_SIGNAL1_STRUCTURAL_REFREEZE_PROPOSAL.md`](V4_SIGNAL1_STRUCTURAL_REFREEZE_PROPOSAL.md) | **部分签字**：C2 已落地并重训；① 本轮 = **`unclassified`**（`clip_insufficient` 是合取，cos≥0 ⇒ 不成立）。**§4 In 表搁置**（C2 cos≥0）。V3 / unique-goals / **重开 RH progress 头** 仍待签 |
| 2c | [`V4_SIGNAL1_SA_DIAG_STATUS.md`](V4_SIGNAL1_SA_DIAG_STATUS.md) | 先读「A.3 判定作废」；文末 **C2 重跑** + **cos diag** |
| 2d | [`V4_C2_COS_DIAG_125_STATUS.md`](V4_C2_COS_DIAG_125_STATUS.md) | **DONE**：C2 ①-eval cos **+0.806 / +0.762** ⇒ **不签** §4 In 表（想象-真实倒挂；洞 4：`goal_rel0` 构造性前向）。**先读顶部「复核」块**：本轮记 `unclassified`；**RH 案重开**（RH 高估 4.2×，排序反转）；n=5 归因已翻转为**评测期** |
| 2e | [`V4_RH_CALIB_125_STATUS.md`](V4_RH_CALIB_125_STATUS.md) | **DONE**：RH vs Δ‖g‖ **非 1:1**（π 6.66× / 前飞 4.18× / 后退反号）⇒ 重开 RH 签字材料 |
| 2f | [`V4_RH_REOPEN_125_STATUS.md`](V4_RH_REOPEN_125_STATUS.md) | **DONE（125）**：R1 + calib 1:1 + analytic AC 重训；① 仍 FAIL n=5；④ PASS — [`V4_RH_REOPEN_125_PROMPT.md`](V4_RH_REOPEN_125_PROMPT.md) |
| **2g** | [`V4_CRITERIA_REFREEZE_PROPOSAL_20260818.md`](V4_CRITERIA_REFREEZE_PROPOSAL_20260818.md) | **待签字（新，08-18）**：**V4-① / ④ 判据本身不成立** —— 旧 ① 奖励撞墙、旧 ④ 可被横漂空过、①④ 互为对抗 ⇒ 全 PASS 也证明不了想象 AC 有用。新口径 = **分层到达**（S_open 不退化 + S_blocked 逼障绕行）+ 两条新前置门（⓪ 近带深度 / ⓿ 想象排序）。**先读 §0**（立案），**然后直接读 §4.6「判据 v2 整合稿」= 实施唯一权威口径，并**必读 §4.6.8 + §4.6.9**（第五轮 G1–G7：头号裁定从「改 shield」改成「改判据的带定义」⇒ §4.6.0 降 fallback；第六轮 H1–H7：**5x 的方向留、数字撤** —— 罩触发面是 **D̂ ∪ τ ∪ p_coll**，τ 前向裁剪 ÷ 速度且在 gate 里是活的 ⇒ 巡航触发到 ≈5 m ⇒ `[3.5,5.0]` 撤回、新增 **⓪f**、in-band 改「并集非介入」、`θ=0.10` 失锚、**跑前分叉**决定 ①′d-b 是否 primary）** —— §1 / §2 是事前记录，其中 §1.0 / §1.3 / §1.5 已被 §4.5 D1–D4 证明与冻结实现冲突，**不得照 §1 实施**（§1 原表按审计链保留不改写）。**⚠️ 签字前必读 §4.6.10（第七轮 U1–U9，复核方 = 用户）+ §5.0 削减签字表 v3** —— **§5 旧签字表整表作废为审计留档、禁止整表签**（整表签会把第六轮撤回的 `[3.5,5.0]` / `θ=0.10` / 「shield-on 原稿口径」冻回去）；唯一可签 = **13 / 5z(修) / 5aa / 5ab(修) / 5ac(修) / 5y / 5ad / 5ae / 5af / 5ag / 5ah / 5ai / 5aj / 5ak**。标题已改 **「分层到达；逼障仅当 ⓪f 证出可行带」**。头号阻塞签字项 = **5z（按第七轮修订文本）**。**第八轮（§4.6.11 V0–V5）**：U1–U9 **已闭合、不再自毁**；削减表裁定栏**仍空** ⇒ 下一动作是人填表（**5af / 5ag 必须勾**），不是再改判据。轻洞已入库：P7-diag 先冻 `[lo,hi]` 再同 log 算 θ；P2 须含 collector/`gate` 传 `wm_out`（`collector.py:185` 现状未传）；§2 P0 IN PROGRESS = stale。**⚠️ 第九轮（§4.6.12 W1–W7，08-20，复核对象 = 第七/八轮自己的处置）：第八轮「可以按 14 行签」失效，表扩为 16 行**（+**5al** 起点集互斥口径更正 ⇒ 原「三者互斥」会让 ①′c-b/①′d-b **无样本**、且与 5ag(A) 配对矛盾 ⇒ 改 `S_diag` ⟂ {`S_accept` ∪ actor gate} 且 `S_accept ≡ S_gate`；5ag(A) 改**配对检验 + 跑前冻结 `Δ`**；+**5am** shield **v5 条件化** ⇒ 评测构型 = 现行第 (4) 代 latch、**P3.5 本周期 N/A**、并如实登记「无 v5 ⇒ 一次触发即整局报废 ⇒ **①′a-b ≥ 0.50 的可解性完全押在 P7-accept**」），**两行是阻塞项**；另 W3 补 C1/C2 落盘字段（归 5aj），W4–W7 为改名/清单遗漏的就地更正。**本轮无一处放松阈值**。**✅ 08-20 已签字（16/16 行）**：14 行采纳 + **5af=(a)**（goal 限前向扇区、侧/后向不测）+ **5ag=(B)**（**MVP 不主张想象 AC 增益**，只主张不退化+安全）+ 包内 **5p** 裁定（到达 = `min_t dist ≤ 3.0`、主动终止 out of scope）⇒ **判据冻结，改动须 re-freeze**；`enable_policy_update` 未翻；代码/yaml 未动 |
| 3 | [`V4_GOAL_Z0_125_STATUS.md`](V4_GOAL_Z0_125_STATUS.md) | 已完成的 goal+z0 轨（① 仍 FAIL） |
| 4 | [`ACCESS.md`](ACCESS.md) | 校园直连：`cursor-125` / H100 hop；异地备用 `cursor-125-public` |
| 5 | [`../superpowers/specs/2026-08-16-v4-mvp-design.md`](../superpowers/specs/2026-08-16-v4-mvp-design.md) | V4-MVP In/Out、①/④ 判据（规格，非日志） |

可选同轨细节（按需，非每天）：

- [`V4_REWARD_HEAD_125_STATUS.md`](V4_REWARD_HEAD_125_STATUS.md) — RH 修好后 ①−3.17 / ④ PASS  
- [`V4_ENCODE_TRAIN_125_STATUS.md`](V4_ENCODE_TRAIN_125_STATUS.md) — 坏 RH → ①−68 的那轮  
- [`V4_H100_TRAIN_STATUS.md`](V4_H100_TRAIN_STATUS.md) — H100 ckpt 路径  
- [`V4_GOAL_Z0_125_PROMPT.md`](V4_GOAL_Z0_125_PROMPT.md) — 远端 agent 指令（调试用）

---

## B. 已闭合但仍常查（V0 / V1）

| 文档 | 读什么 |
|---|---|
| [`V0_GATE_STATUS.md`](V0_GATE_STATUS.md) | **§1+§2** = V0 权威现状；§3.3 = 旧 ①a–c 失格史；§4 = **n=8 已 re-freeze**；§4.1 = **④b 空过终态已收口** |
| [`V1_GATE_STATUS.md`](V1_GATE_STATUS.md) | V1 三信号严谨 PASS + 部署 flags；**§4.1/§4.2 = ②-coll 独立诊断**（不改 08-15 merge）；§2 ① **功效脆弱已记** |
| [`V1_SIGNAL1_POWER_REFREEZE_PROPOSAL.md`](V1_SIGNAL1_POWER_REFREEZE_PROPOSAL.md) | **待签字**：V1-① 条款②配对强制 + ③裕度带（与 n re-freeze 正交） |
| [`V1_COLL_HELDOUT_COLLECT_125_STATUS.md`](V1_COLL_HELDOUT_COLLECT_125_STATUS.md) | 125 碰撞富集 held-out 采集 **DONE**（usable 65 / coll usable 8） |
| [`V1_COLL_HELDOUT_DIAGNOSTIC_STATUS.md`](V1_COLL_HELDOUT_DIAGNOSTIC_STATUS.md) | H100 ②-coll 新 held-out 诊断 **CLAIMED**（pos=20 / AUROC 0.977） |
| [`../../experiments/aerial/RUNBOOK_v0.md`](../../experiments/aerial/RUNBOOK_v0.md) | V0 顶层入口；**§1–§2 现状**；§8 = 变更考古（勿把晚¹⁹ 当今天） |
| [`../PROJECT_STATUS.md`](../PROJECT_STATUS.md) | 项目鸟瞰（若与 V4 活文档冲突，**以 V4_GATE_STATUS 为准**） |
| [`../design/2026-08-15-v1-v4-design.md`](../design/2026-08-15-v1-v4-design.md) | V1/V4 母本设计 |

阈值唯一真相源（改阈值才读、才改）：

- [`../superpowers/specs/2026-08-04-aerial-wam-v2-frozen-spec.md`](../superpowers/specs/2026-08-04-aerial-wam-v2-frozen-spec.md) §4.1

---

## C. 运维 / 采集（按任务）

| 文档 | 何时读 |
|---|---|
| [`ACCESS.md`](ACCESS.md) | SSH / origin / 异地 |
| [`../../experiments/aerial/scripts/RUNBOOK_sync_and_env.md`](../../experiments/aerial/scripts/RUNBOOK_sync_and_env.md) | 三机同步与环境 |
| [`2026-08-04-v0-4090-local-collect-runbook.md`](2026-08-04-v0-4090-local-collect-runbook.md) | **4090 本地采集**（与 sync RUNBOOK 有冲突，见 `V0_GATE_STATUS` §3.5；实操以本文件 + r60 为准） |
| [`2026-08-10-signal3-reprojection-estimator.md`](2026-08-10-signal3-reprojection-estimator.md) | V0 ③ 估计器细节 |
| [`2026-08-10-da3-depth-backbone.md`](2026-08-10-da3-depth-backbone.md) | DA3 深度头 |

---

## D. 不要当作「当前权威」的东西

- 任何指向下列**空文件**的链接（已确认不存在）：  
  `2026-08-12-v2-plan-risk-assessment.md`、`2026-08-12-v0-gate-status-and-roadmap.md`  
  → 内容只活在 `RUNBOOK_v0.md` §8 晚¹⁹/晚²⁰ 正文。
- 「`_v0_gate --merge` 从未 exit 0」「仍在 Step 6 合拢」类 8/12 备忘。
- 「n=8 相对冻结 16 越界」—— **2026-08-17 已 re-freeze，n=8 即冻结值**（洞 1 = **事后合法化**，见 `V0_GATE_STATUS` §4；非事前干净通过）。
- 「n=8 re-freeze 治了 V1-① 擦边」—— **否**；合法性 ≠ 统计功效。① 裕度 0.8 局 / McNemar p≈0.5 见 `V1_GATE_STATUS` §2 + [待签字条款②③](V1_SIGNAL1_POWER_REFREEZE_PROPOSAL.md)。
- 「V4-① 再训一轮 / 对齐 z0 就能过」—— **否（再训现 π）**；C2 已从零重训仍 FAIL。**对齐 z0 / WM 保真**是 08-18 后的**活假设**（cos≥0 后的倒挂），尚未验证、不得当「就能过」。见 [cos STATUS](V4_C2_COS_DIAG_125_STATUS.md)。
- 「§A `b>c` 已证明改 In 表就够」—— **否**，§4 仍不充分（A.2 只排除碰撞项通道）。
- 「A.3 = `b3_le_a` ⇒ 先修 RH」—— **否，2026-08-18 已作废**：那条臂无效（① 幅度只匹配第 0 步、欠 ~4.6×，π 轨迹均值 ‖a[:3]‖≈16.5；② 五臂全超部署上限 `body_delta_limits(1/5Hz)`=[1.0,0.4,0.4,0.314]，`imagine()` 不夹；③ (b3) 冲过目标 23.9 m）。**可实现集合内 RH 方向偏好是对的**。A.4 seed=0 已实测：夹后最大前飞 λG0 **47.64 ≥** π_clipped **18.25**（`fwdmax_ge_pi`）⇒ 倒挂来自无界动作通道，~~**确诊不是 RH 案**~~。裁定已签 = **C2**（08-18，代码已落地），见 `V4_GATE_STATUS` §1/§3。**← 「确诊不是 RH 案」已于 08-18 晚复核推翻**：A.3 作废只证那条臂**不可实现**，A.4 只证**方向**偏好在夹后是对的，**两者都没检验幅度校准** ⇒ **RH 案重开**（见下条新记）。
- **「RH 案已排除」—— 否，2026-08-18 已重开（幅度校准轴）**。C2 训后 §A：(b) 最大前飞 yaw **恒 0** ⇒ 15 步 × 上限 1.0 m = **恰好 15.0 m** 闭合（`‖goal‖ 30→15.0` 印证），RH `Σprogress` **+62.60** ⇒ **高估 4.2×**；π 闭合 12.2 m 得 **+81.64** ⇒ **6.7×**。**几何排序**（15.0 > 12.2）与 **RH 排序**（81.64 > 62.60）**相反** ⇒ 倒挂在**可实现集合内、想象内部**已存在，**不需要真机**。校准曲线**已跑**（[`V4_RH_CALIB_125_STATUS.md`](V4_RH_CALIB_125_STATUS.md)）：**非 1:1**，π **6.66×** / 前飞 **4.18×**（yaw≡0 ⇒ 与漏转 yaw 无关）/ 后退 **反号** −0.62 ⇒ 判定 **`sign_reopen_rh_progress_head`**。下一件 = **签「重开 RH progress 头」**，改码未动。
- **「`advance_goal_rel_body` 已静态验过没问题」—— 只验了符号，没验旋转**（08-18）。它只做 `g[:3] -= a[:3]`（`goal_features.py:60-73`），**不按 `a[3]`（yaw delta）旋转** body-frame goal，而 `imagine()` 逐步用它传播 RH conditioning（`imagination.py:164-165`）⇒ **yaw≠0 的臂** conditioning 失真（π 有 yaw ⇒ 它的 12.2 m 不可靠；(b) yaw≡0 **不受影响**）。**未修，改动会动 §A 全部数字 ⇒ 须签字。**
- 「`action_scale=3.0` 是动作上界 / π 已饱和」—— **否**；`_MLP` 末层裸 `nn.Linear`，它是**增益**，‖a‖ 无上界（`actor_critic.py:200`）。**← 描述 pre-C2**；C2 起 `action_scale` 默认 **1.0** 且是 **pre-tanh 增益**，动作由 `limits ⊙ tanh(u)` **构造性有界**（旧 ckpt 仍按 legacy 类以 3.0 回放）。
- 「一致性修 = 在 `imagine()` 加一行 clip」—— **不够**（提案 §4.1）。actor 更新是 **REINFORCE**（`actor_critic.py:257`/`:271`，无梯度穿 `dynamics.step`），字面 clip ⇒ 用未夹高斯给夹后动作算 logp（似然错配）+ 探索塌缩（σ=0.607 四维同值 > 后三维上限；盒内采样概率 8.6%，现 ckpt 3.4e-6）。推荐 **C2 有界策略分布**（`a = limits ⊙ tanh(u)` + 雅可比修正），须**从零重训**。**← 已按 C2 落地**（08-18）；`imagine()` 里的 clip 保留为**计数器** `n_action_clipped`（C2 下实测 0），不是修本身。
- **「C2 已落地 ⇒ V4-① 已修好 / 可以翻 flags」—— 否**（08-18）。C2 已从零重训并再 gate：`n_action_clipped=0`，① **仍 FAIL**（−7.43 / −3.53 vs heur ~9），`enable_policy_update` 仍 **false**。~~判定 `clip_insufficient`。~~ **← 08-18 复核：本轮应记 `unclassified`** —— `clip_insufficient` 是合取「① FAIL **且** 首动作 cos<0」，cos 实测 **+0.806/+0.762** ⇒ 第二项假、该行**不成立**，观测落在事前三行**之外**（事前表不改写，见提案 §4.1 注记）。
- **「`clip_insufficient` 已判实 ⇒ 直接签 §4 In 表」—— 否**（08-18 cos diag DONE）。mean cos actor **+0.806 / +0.762**（≥0）⇒ 事前表 **不签** In 表；活假设 = 想象-真实倒挂（imagΣG ~85 vs real ~−5）。见 [`V4_C2_COS_DIAG_125_STATUS.md`](V4_C2_COS_DIAG_125_STATUS.md)。（该行本身亦**不成立**，本轮记 `unclassified`，见上。）
- **「`cos_path_goal` 有负 ep ⇒ 还是要签 In 表」—— 否**（08-18 复核）。`cos_path_goal` mean **+0.075 / +0.098**（≈85°，负 ep 3/7 与 2/8）是本跑最强的数，形态 = 「t=0 朝前、整条路径几乎垂直于目标」= **跟踪丢失**；但**洞 4** 使 In 表在本 harness 上无效：训练侧只有一个 `_mock_goal_episode()`、评测侧 |az| ≤ 0.8° ⇒ goal 对 actor 是**常量输入、可被 bias 完全吸收**，表达力增量 **0**。要让 In 表有意义，须先有**多样 goal**（提案 unique-goals 下限，仍待签）。
- **「想象-真实倒挂只能靠查 WM 转移 / z0 域差」—— 否，有更便宜的一步**（08-18）。倒挂在**想象内部、可实现集合内**就能看到（(b) 臂几何 15.0 m vs RH +62.60）⇒ 先做 **RH 校准曲线**（零渲染零训练零改码），只有它接近 1:1 时才走 WM/z0 那条贵路。**已跑，非 1:1**（π 6.66× / 前飞 4.18× / 后退反号）⇒ WM/z0 那条路**本周期不走**，先修 RH。见 [`V4_RH_CALIB_125_STATUS.md`](V4_RH_CALIB_125_STATUS.md)。
- **「Pearson +0.59 说明想象与真实相关」—— 无功效**（08-18）。+0.588（n=7，p≈**0.17**）/ +0.217（n=8，p≈**0.61**），两跑差 2.7×。且 **`mean_real_minus_imagined ≈ −91` 混了 horizon**（想象 15 步 vs 真实整局 ≤200 步），不是校准误差；要量化须取**同窗口**。
- **「那个 cos 已在 C2 re-gate 产物里」—— 否**（08-18）。gate partial-1 只落 progress / final_dist / scan，**无 cos 无动作**。出 cos 的是 `v4_progress_diag.py`（M5d ≈−0.88；C2 **+0.76~+0.81**）。
- **「评测 `goal_rel0` 是一个分布」—— 否，是构造性常量**（08-18 洞 4 + 实测）。`goal_dist_m=30.0` + `goal=start+heading*30` + spawn yaw=heading ⇒ t=0 body goal ≈ `[+30,0,z]`（diag |az|≤0.8°）。正 cos **不能**读成「随 goal 转向」。
- **「n=5 = 扫描期 spawn_collision」—— 否**（08-18 读盘）。seed=0：accepted 9 → scored 5（评测期丢）；`rejections.open_ahead=708` 是扫描期拒收。键名 **`rejections`**（不是 `rej`）。修扫描拒收 ≠ 修 `_run_one_resilient→None`。
- **「训后 λG0 59.09 > 最大前飞 47.78 ⇒ 又在薅想象」—— 否**（08-18）。事前 `clip_helped` 行写的「λG0(π)≤最大前飞」隐含「纯前飞是盒内最优」，**四自由度盒里不成立**。`goal_rel` 30→17.8 = 闭合 **12.2 m**，H=15 × 上限 1.0 m/步 ⇒ 盒内理论上限 15 m 的 **81%** ⇒ 是真接近目标。~~**不**重开 RH 案。~~ **← 「不重开 RH 案」已推翻**（08-18 复核）：goal 在正前方 ⇒ 前飞即闭合最优，侧向/垂向不可能多闭合一米，59.09−47.78 的盈余只能来自 **RH 幅度校准**（见上面「RH 案已排除 —— 否」条）。「12.2 m 是真接近目标」这半句仍成立，但它本身也依赖失真的 yaw 记账 ⇒ 只有 (b) 臂的 15.0 m 是干净的。
- **「① n=5 是 spawn 扫描丢的 / 存活局偏开阔空间」—— 否，2026-08-18 已撤回**。gate 两跑 `accepted` = **9 / 8**（扫描期被拒会**补扫**到数），掉到 scored=5 发生在**评测期**；同 seed 同构造的 cos diag 拿到 **n=7 / n=8**（seed=1 零丢局）⇒ 病灶在 **gate 的评测循环**（`_run_one_resilient→None`，或 ④ on/off 配对那条路径），**不是** spawn 的性质，「选择偏差」论据**不得再引**。仍然成立的部分：FAIL 方向对 n 稳健（补 3 局须各 ≈37.9 / 33.7，heuristic 每局仅 ~8.7），**两跑均非全权**、不得入账干净 gate，**④ PASS 同为非全权**（off-rate 2/5；on-rate=0 ⇒ ④b 大概率 `before_vacuous`）。全权 ① 查评测循环即可，**不**降 `n`。附：`rejections["open_ahead"]` 两跑 **708 vs 15**（47×），扫描行为本身不稳，另记。
- 「V1 部署侧动作空间已一致」—— **未核**；`planner.default_candidates`（`planner.py:31-42`）在未夹空间打分，到 `collector.py:167` 才夹。**不**重开 08-15 merge，仅记为同源不一致。**← C2 未改这条**：`planner.action_limits` 默认 `None`，V1 部署路径逐位不变（打开须 V1 re-gate）。
- 「④b before=1.0 是测得的干预先于接触」—— **否**；`n_contact=0` 时空过终态，④ 实证=④c。
- 「headon 可作 V1-② coll OOD」—— **否**；headon `coll_eps=0`。
- **「④ PASS ⇒ V4 的安全性已经证明了」—— 否**（08-18 立案）。横漂策略**永不接近障碍** ⇒ on-rate 0、`n_contact=0` ⇒ ④b `before_vacuous` + ④c **0.000** ⇒ **自动 PASS**。**④ 的 PASS 与 ① 的 FAIL 是同一个病的两面**，不是两个独立结论。反空过项见[判据 re-freeze 提案](V4_CRITERIA_REFREEZE_PROPOSAL_20260818.md) §1.4 ④′c。
- **「旧 V4-① 只是裕度不够 / 再训一轮就过」—— 否，判据本身奖励撞墙**（08-18 立案）。`progress_sum = ‖g−p₀‖ − ‖g−p_final‖` 且 collector 遇 `done` **break** ⇒ 撞墙即停在**离目标最近点**，progress 拿满；而正确的绕行行为横向位移**不计分**。⇒ **①④ 互为对抗**，唯一双赢行为是**逼障（贴障绕行）**。见提案 §0.1。
- **「所以起点集应该只留「直线到不了」的」—— 否，这是另一个极端**（08-18）。开阔路径上**直线就是正确解**；只在遮挡层判会训出「永远绕圈」的策略。正解 = **分层评测**：探针打标签成 **S_open**（直线可达，判不退化：到达率 ≥0.875 / 效率 ≥0.90 / 硬碰 0）与 **S_blocked**（直线撞，判逼障到达），**merge 取合取**。见提案 §0.1.1 / §1.3。
- **「spawn 即碰撞的局算 actor 撞了」—— 否，那是无效局**（08-18 补）。`steps_to_collision==0` ⇒ 丢弃 + 补扫 + `n_invalid_spawn` 独立落盘；若记成 `hard_coll`，则「硬碰率=0」**永远不可能达成**，判据自毁。与已知「① n=5 丢局在评测期」同源 ⇒ 修丢局时 `n_invalid_spawn` / `n_none_returned` / `n_pair_broken` **必须分开**计数。
- **「撞墙那局效率算出来很高 ⇒ 策略走得直」—— 否**（08-18 补）。`path_efficiency = ‖g−p₀‖/Σ‖Δp‖` 在撞墙短路径上**虚高（可 >1）**⇒ 效率与带占用**只在到达 ep 上算**，否则早撞反而抬分（旧 ① 奖励撞墙的同型错误）。
- **「探针 2 m 就撞的起点也算 S_blocked 正常样本」—— 需拆层**（08-18 补）。`start_clearance_m=3.0` 只保证起点 3 m 净空，**不保证存在绕行解** ⇒ 按 `d_first_contact < 5 m` 拆 **S_blocked_tight** 单独报告；可解性经验上界 = **P7 planner 到达率**（planner 也过不去 ⇒ 可解性未知，不得据此判 actor FAIL）。**禁止**事后按「太难」剔除已评分 start（选择偏差，洞 3 同类）。
- **「shield 触发深度 3.0→2.0 已定」—— 否，暂缓且方向可能相反**（08-18 补）。若撞点落盘显示「shield 已触发仍撞」，病是**反应余量不足**，应保持 3.0 或加大。**须在 ⓪ 近带深度 + 首轮撞点落盘之后裁定。** 先验余量是够的（5 Hz × 1.0 m/步 ⇒ 3.0 m 有 3 步）⇒ 第一嫌疑是深度，但实测优先。
- **「④′c 反空过已经把空过堵死了」—— 否，它会把理想目标行为判成 `vacuous`**（08-18 第三轮复核，提案 §4.4 A1）。逼障的定义就是停在 [1.5,3.0] m、**不进 1.5 m**，而 ④′c 要求 `near_coll_rate_off > 0` ⇒ **完美达成目标的策略 off 臂 near-coll = 0 ⇒ 不得记 PASS**，且 merge **未定义 N/A 怎么并** —— 旧 ④ 把「从不接近」当安全，④′c 把「从不危险」当空过，**同型对称陷阱**。修 = 反空过改**遭遇机会**口径（`n_steps_forward_depth<3.0m (off) ≥ K`）。
- **「逐步 GT 深度当然可以在评测里落盘」—— 否，会改闭环速率 ⇒ 撞红线**（08-18）。跨网闭环 RGB ~14 Hz / **+depth ~3 Hz**，部署 `step_hz=5` ⇒ 在线取 GT 深度就把 **dt** 改了（rate-lock 已治好的 dt-desync 复发路径）。⇒ **GT 深度只由位姿回放离线取**，在线只落 pose / D̂ / action / intervention。
- **「新判据全过就证明想象 AC 有用」—— 否，反事实臂在改判据时被删掉了**（08-18，提案 §4.4 B1）。旧 ① 至少有 heuristic 比较臂（虽然它奖励撞墙），新口径全是**绝对阈值** ⇒ 全过只证「有一个策略能干活」。⇒ 须把 `actor ≥ P7 planner 到达率` 预注册为增益判据，**或明确宣告 MVP 不主张该增益 —— 不得沉默**。
- **「n 提到每层 16 就够稳了」—— 功效从未计算**（08-18，提案 §4.4 B3）。n=16 手算：①′a-o ≥0.875 对真值 **0.80 仍有 35.2%** 放过；①′a-b ≥0.50 在真值 0.50 处 **59.8%**（边界抛硬币）。**合取方向更要紧**：15 条子判据全 AND、每条 5% 误杀 ⇒ **merge 误 FAIL ≈ 54%**，而红线禁事后放松 ⇒ **跑出来就卡死**。⇒ 跑前必须落盘 OC + 预注册 seed 数与「两 seed 不一致」裁决 + 声明 **primary vs secondary**。
- **「带占用 ①′d-b 能证明策略在贴障」—— 只测结果，不测机制**（08-18）。它用 **GT** 深度，瞎子也可能因场景几何落在带里；且 `yaw` 可解耦 —— 策略**转开机头、侧向平移**就能同时让带占用与 shield 前向锥**都瞎**（heuristic `yaw`≡0 ⇒ 探针对 yaw 无参照）。⇒ 机制主张全压在 **⓿ 与 P7** 上；带占用与撞点归因须按**速度方向**算。
- **「P0–P8 顺序已经理清了」—— 否，缺「语料重采 + WM 重训」这一环**（08-18，提案 §4.4 A3）。§3.1 完整重采 + §3 goal ≥32 ⇒ **WM 必须重训** ⇒ P1/P3/P4 都得在新 WM 上重做；现链条是 P1 先给旧 WM 发证、随后 WM 被换掉、**证书作废**。⇒ 插入 **P4.5**。
- **「in-band 只要 `engaged=false` 就代表『罩没介入』」—— 否，`engaged` 是 latch 状态，「本步刚破、尚未 latch」时它仍是 false**（08-19 第七轮 U3，`safety.py:96-107`）。in-band 必须写成 **`NOT _breached(step)`（= `D̂_fovmin ≥ 3.0` ∧ `τ̂ ≥ 1.0` ∧ `p_coll ≤ 0.5`）∧ `engaged == false`** —— 两条是**合取**，后者不能替代前者。第六轮的写法还**漏了 `p_coll` 整条通道**，桌面副本比仓内更松（连 D̂ 都没写）⇒ 两份已改到逐字一致。**连带（U3-b）**：`p_coll` 现在是死值（P2 未做）⇒ 现测的「非介入域」是**乐观上界** ⇒ **band 正式冻结必须排在 P2 之后**，或标 `band_frozen_before_p2=true` 并在 P2 后重跑 ⓪f + 重裁分叉（**只许缩窄**）。落盘要求：`_breached` **三通道各自的布尔位**（否则带为空时无法归因）。
- **「本周期会有滞回解锁的 shield v5（或 P3.5 v5 回归是必做步）」—— 否，v5 早在第五轮就被降为 fallback，本周期评测构型 = 现行第 (4) 代（latch + 有界状态反馈后退）**（08-20 第九轮 W2）。第五轮把头号裁定从「改 shield」改成「改判据的带定义」、5r′ 降 fallback 之后，**§4.6 内部的 v5 依赖没清扫**：评测构型行写「shield-on（v5）」、冻结清单含 v5 的 `release_depth_m/M/上限`、**§4.6.6 的 P3.5「shield v5 回归」还标着「必须在 P3 之后」**⇒ 与红线「本周期不动 shield」直接冲突。⇒ v5 相关全部改 **conditional**、**P3.5 本周期 N/A**、v5 三参数不进冻结清单（`release_step[]` / `n_release` 仍落盘，无 v5 时恒 0）。**连带须如实登记的代价**：无解锁 ⇒ **一次触发即整局 latch ⇒ 本局报废**，而 τ 通道在 `v=5 m/s` 巡航下触发到 **≈5 m** ⇒ **①′a-b ≥ 0.50 的经验可解性完全押在 P7-accept 上**（第五轮 G1 只论证了带定义，从未论证过到达率）；若 P7-accept 在 S_blocked FAIL ⇒ 走 **P7-FAIL 下车站**，不得改判据。签字项 **5am** ⇒ **✅ 08-20 已采纳**（v5 全部 conditional / P3.5 本周期 N/A / 代价已如实登记进 `V4_GATE_STATUS.md` §1.1）。
- **「V4 会证明『世界模型想象 / AC 有增益』」—— 否，签字时明确放弃了这个主张**（08-20 `5ag` 裁定 **(B)**）。V4-MVP 只主张「**不退化 + 安全**」。原因不是做不到，而是 (A) 的门槛 `arrival_actor ≥ arrival_planner − Δ` 里 planner 到达率按 **5c** 就是**经验可解性上界**，`Δ=0` 时等于要求 actor 打到上界，且该门槛是跑后才知的随机量 ⇒ 违反 5n/B3「OC 曲线跑前冻结」。**「想象有增益」的出证留 V5 另案**（届时按配对检验 + 跑前冻结 `Δ` 预注册，`Δ=0` 已在案）。⇒ **不要**在读到 V4 PASS 时把它讲成「想象 AC 被验证了」。
- **「V4 的 ①′ 结论 = 全向导航能力」—— 否，只覆盖机体前向扇区**（08-20 `5af` 裁定 **(a)**）。评测 goal 限 body-forward 扇区，**侧向 / 后向 goal 本周期不测**，In-表（goal 表示）改动属 **V3 另案**。另：「**主动终止**」（policy 自主决定停止）本周期 **out of scope**，一条判据都没有。两条都已登记进 `V4_GATE_STATUS.md` §1.1 结论栏 ⇒ **不得外推**。
- **「判据签完了就可以边跑边调阈值」—— 否，08-20 签字即 re-freeze 生效**。此后改任何阈值 / band `[lo,hi]` / `n` / primary-secondary 划分都须**重开表签字**。仍留的空（`[lo,hi]`、`δ`、`θ`、`Q_0.25(C_P7)`、C1 的 `k`）是**等实测才能填的填空，不是待裁的裁定**，且只许按已签的公式机械填、只许缩窄。**`enable_policy_update` 未因签字翻开**（红线：四信号全过前不翻）。
- **「`n` 从 8 提到每层 16 = 判据更严了」—— 否，丢局不修的话 16 永远填不满 ⇒ 全部信号永久 `authoritative=false`**（08-19 第七轮 U9）。现况曾 `n=5 < 8` 出在 `v4_gate_run_partials.py` 的 `_run_one_resilient`（`if ep_on is None: continue` 直接吞掉），且 ④ 仍 **on/off 配对**。叠上红线「不降 n」⇒ **「四信号全过」在结构上成为不可能事件**。⇒ 前提步 **P0c**（三计数器 + spare 补扫 + 禁降 n）。**✅ P0c 已 DONE（2026-08-20）**：正式跑 `v4_gate_p0c_formal_20260820/` 在 `--spare-count 16` 下各臂 **n_scored=16 / authoritative=true**（例：① spare_consumed=8、invalid=3、pair_broken=5）。不得再把「评测期丢局导致永久非全权」当现状。
- **「θ 可以从 P7 的跑里定出来」—— 否，那趟 P7 同时又是 ①′d-b 的验收 ⇒ 自指**（08-19 第七轮 U4）。必须**两趟**：**P7-diag**（θ 未定义，只落盘 `band_frac` 与 clearance 分布 `C_P7`）⇒ **冻结 θ / 裕度式 / k / `[lo,hi]`（加时间戳）** ⇒ **P7-accept**（在与 `S_diag` **起点 + seed 双不相交**的 `S_accept` 上验收）。~~三个起点集（`S_diag` / `S_accept` / actor gate）互斥~~ ⇒ **08-20 第九轮 W1 就地更正**：三者互斥会让 E3 的固定公共子集 `P`（= P7-planner 到达的起点，`P ⊆ S_accept`）与 actor 的 gate 起点集不交 ⇒ **①′c-b / ①′d-b 的中位数无样本可算**，且与 5ag(A)「同 `S_accept`、按 start 配对」自相矛盾 ⇒ 正确口径 = **`S_diag` 与 {`S_accept` ∪ actor gate} 互斥**，且 **`S_accept` ≡ actor 的 gate 起点集**（`S_accept ≡ S_gate`）；训练集仍与三者都不交。`S_diag` 与后两者重叠 ⇒ θ 记 `authoritative=false`（θ 仍**只在 `S_diag` 上拟合** ⇒ 防事后调阈值的效力不减，**未放松任何阈值**）。签字项 **5al**。一趟做完 = 在同一批数据上又定阈值又验收 = **事后调阈值（撞红线）**，且 P7 会构造性通过。同理 band 上沿 `hi` 也只能取 **`Q_0.25(C_P7)`**（来自 diag 趟）+ 绝对护栏 8 m（**如实登记为拍的**）；第六轮拍的 `hi ≤ 6 m` 已撤。**✅ 08-20 签字**：5ac(修) 与 **5al** 同时采纳 ⇒ 起点集口径 = `S_diag` ⟂ {`S_accept` ∪ actor gate}、**`S_accept` ≡ `S_gate`**（θ 仍只在 `S_diag` 上拟合 ⇒ 防 p-hacking 不减）；5al(b) 的配对检验因 `5ag`=(B) **暂无适用对象**，`Δ=0` 已冻结在案、日后启用 (A) 时不得另议。
- **「R1 落地后横漂已经解释清楚了 / 5f 护栏在起作用」—— 否，两条都不成立**（08-19 第七轮 U6，`30b9ff8` + `d96da1d`）。R1 **已 DONE**：Phase-2 校准比值打到 **1.00 PASS**、analytic 进展已接进 imagine aux 路径 ⇒ **谎报通道确实关了，但 ① 仍 FAIL**（−7.43 / −3.53，`n=5` 非全权）⇒ **§3.2「横漂只能用 RH 谎报解释」的排除式论证作废**，至少还有一个未识别成因（候选：goal-blind 结构 / H=15 只覆盖 30 m 的一半 / 语料无逼障正例）。且 analytic 一进 aux 路径，**5f 的「imagined ΣG vs analytic ΣΔ‖g‖」比值恒 ≈1 ⇒ 护栏空转** ⇒ 须改成「对**真实 rollout 的 Δ‖g‖**（离线回放）比」或撤案。P1 的「forward ratio ∈ [0.8,1.2]」同样**过时**（actor 已不吃该读出）⇒ 降诊断。
- **「提案的签字栏可以整表『采纳』」—— 否，整表签会把第六轮刚撤回的数字冻回去**（08-19 第七轮 U1）。旧 §5 表里项 **5**（shield-on 原稿口径，D1 已否）、**5k**（速度方向带占用，5u/G2 已撤）、**5x**（`[3.5,5.0]`，H1b/H3 已撤）、项 **10**（`θ=0.10`，H5 已失锚）都还写着「采纳」，且 **5r′** 写「必须最先裁」而头号其实是 5z，§6 的 **P1–P4** 还和前提链 **P0–P8** 撞名（已改 **Q1–Q5**）。⇒ **唯一可签 = §5.0 削减签字表 v3**（13 / 5z(修) / 5aa / 5ab(修) / 5ac(修) / 5y / 5ad / 5ae / 5af / 5ag / 5ah / 5ai / 5aj / 5ak **+ 08-20 第九轮新增 5al / 5am ⇒ 共 16 行**），旧表降审计留档。另**只签项 13 会静默丢字段**：**5d（撞点 7 项）与 5e（`action_commanded` 落盘）根本不在 §4.6.1 的落盘清单里** ⇒ 由 **5aj** 打包补回；**第九轮 W3 同类**：5q 的 **C1（进带前 k 步的 `D̂_fovmin` / `v_fwd` / 侧向位移）** 与 **C2（`S_open` 的 `intervention_rate`）** 也不在契约里 ⇒ 一并归 **5aj**。**✅ 08-20 签字即按此执行**：只签 §5.0 的 **16 行**，旧 §5 表**整表未签**（仅审计留档，其「采纳」字样无签字效力）；5aj 已采纳 ⇒ 5c/5d/5e/5g/5o/5p/C1/C2 字段全部进 §4.6.1 落盘契约（缺失 ⇒ `authoritative=false`）。
- **「罩的触发面就是 D̂ 一条，把带定在 FOV-min ≥ 3.0 就安全了」—— 否，触发面是两条几何不同通道的并集，τ 通道随速度缩放 ⇒ 巡航时任何 ≤5 m 的带都在触发区内**（08-19 第六轮读码，`safety.py:96-107` + `tau_predictor.py:143-192` + `v4_gate_run_partials.py:250-291` + `action.py:43-45`，提案 §4.6.9 H1/H1b）。`_breached` = **`D̂<3.0` ∪ `τ<1.0` ∪ `p_coll>0.5`**；τ 通道在 V4 gate 里**是活的**（`foe_calibrated`、`min_tau_s=1.0`），几何是**前向中心裁剪 `center_frac=0.5` ÷ 闭合速度**，与 D̂ 的**整幅 FOV min** 不同。`MAX_BODY_VELOCITY[0]=5.0 m/s` ⇒ 巡航时 τ 触发到 **≈5 m** ⇒ 第五轮提的 `[3.5, 5.0]` **整段在触发区内、已撤回**。⇒ ① in-band 必须按「**并集非介入**」判（band ∧ `τ̂ ≥ min_tau_s` ∧ `engaged=false`）；② band 是**速度条件**的 —— 在 clearance `d` 不被接管要求 **`v_fwd ≤ d / min_tau_s`** ⇒ **可证明的「逼障」= 减速贴障通过，不是高速贴障**；③ 带边界无法由 ⓪a 校准（support 只到 3.0 m）⇒ 新增 **⓪f**（`D_gt ∈ (3.0, 8.0]` + D̂/τ 双通道误触发率）；④ **「存在可行带」是未证事实** ⇒ 跑前分叉：无可行带（`hi ≤ 6 m`）⇒ **①′d-b 降 secondary**，机制主张落到 ⓿ + P7。头号阻塞 **5x → 5z**（另 5aa/5ab/5ac）。**← 第七轮 supersede 本条两处**：(a) in-band 公式**漏 `p_coll`**、且 `engaged=false` 不等于「本步未破」⇒ 正式写法见上面第一条（`NOT _breached ∧ engaged==false`）；(b) 分叉里的 `hi ≤ 6 m` 是**拍的** ⇒ 换成 `hi ≤ Q_0.25(C_P7)` + 绝对护栏 8 m。
- **「`frac_steps_in_band ≥ 0.10` 就是『紧绕行』」—— 否，那是时间占比 ⇒ 慢速盘旋即可空过，且 `0.10` 已失锚**（08-19 第六轮，提案 §4.6.9 H4/H5）。H1b 迫使带内减速 ⇒ 在 4 m 处**慢速磨蹭**是最省力的刷分法，median 又只在到达局上算 ⇒ 「磨蹭完再到达」反而得高分。⇒ 改 **primary 取更严者**：进展加权（k 步窗口内 `dist(p,g)` 严格下降）/ 路径长加权（`band_path_len/total_path_len`，对速度不变），纯时间占比降诊断。`0.10` 是为「带在 standoff 之内」选的 ⇒ 带一挪即**无定义**（既不是收紧也不是放松）⇒ 须由 **P7 planner 同定义下的基线占比 + 裕度跑前重导冻结**；重导值低于 0.10 ⇒ **属放松、须单独签字**。另：`band_frac` / `frac_steps_in_band` 在 `v0_metrics.py` / `v4_metrics.py` 里**还不存在** ⇒ 这是**待实现**，不是改已有代码。**← 第七轮 supersede 本条的推导路径**：「由 P7 基线重导 θ」是**自指**的（那趟 P7 同时在验收含 θ 的 ①′d-b）⇒ 必须拆 **P7-diag ⇒ 冻结 ⇒ P7-accept（起点集不相交）**，见上面第三条。
- **「①′d-b 的逼障带可以定在 1.5–3.0 m」—— 否，那个区间被部署安全罩结构性禁止，判据在要求策略违规**（08-18 第五轮读码，`depth_predictor.py:81-90` + `safety.py`，提案 §4.6.8 G1）。`predict_min` = **整幅深度图（全 FOV）** finite&positive 的 **min**，`min_depth_m=3.0` 就是拿这个数触发 ⇒ 任何要求 `clearance < 3.0` 的判据，都是要求策略进入罩的**禁区**；**这与 latch 无关** —— 换成第 (1) 代瞬时罩也一样会被接管。⇒ **头号裁定不是「改 shield」而是「改判据的带定义」**：band 整体上移到 standoff **之上**（`clearance_fov ∈ [3.5, 5.0]` provisional，下边界 = `min_depth_m + δ`，δ = ⓪ 实测 D̂ 近带欠读偏差，P3 出数后冻结）⇒ 签字项 **5x**；shield v5（5r′）**降为 fallback**。连带：**D1 severity 大幅下降**（剩下的是 E2 可解释性问题，不是不可满足）、**R-2 大部分消解**（`[3.5,5.0]` 在罩非介入区 ⇒ 语料本来就有）、**P5 很可能不必要**、**①′d-b 与 ④ 的对抗性消失**。**代价（诚实登记）**：可证明的「逼障」收窄为「贴 standoff 边缘紧绕行」，`[1.5,3.0]` 内的行为**在当前部署构型下不可测** ⇒ 原 §1.3.2 与部署构型**本就不自洽**。**← 第六轮 supersede 本条的数字**：`[3.5, 5.0]` 与「δ 由 ⓪ 校准」均已撤回（τ 通道 + ⓪ support 只到 3.0 m），见上面第六轮那条与 §4.6.9；本条的**方向**（改判据不改罩）成立且被晚⁷ 实测加强（`[1.5,3.0)` 上 `P(trig)=1.0`）。
- **「band 用『全向最小净空』就能修 D4 的侧掠不可测」—— 否，那会引入 FOV 外方位 ⇒ 判据可被「盲区贴障」空过**（08-18 第五轮，`depth_predictor.predict_cones` docstring：「Not wired into the collector/shield until P0b」）。判据几何必须与**触发几何一致** = FOV-min；五向 cone 分解只作诊断。侧掠可测性靠**带上移**解决，不靠**加方位**。（原 5u 因此撤案。）
- **「latch 有问题，那就把 latch 去掉改瞬时罩」—— 否，那是 `safety.py` 历史设计 (1)，实测会让 ④ ratio 反转**（08-18，`safety.py:48-79` docstring 四代设计史）。(1) 非 latch + hover ⇒ 目标寻径持续前推、罩持续抵消 ⇒ **带内外振荡 ⇒ `near_coll_rate_on ≫ off`**；(2) latch + 无界后退 ⇒ 盲退**倒撞后墙**（晚¹⁰ `coll_after_latch=9/9`）；(3) latch + 纯 hold ⇒ 零 delta **不消前向动量** ⇒ 滑入带驻留（晚¹¹ `rate_on` 0.385、**ratio 12.96**）；(4) latch + 有界状态反馈后退 = 现行。⇒ **解 D1 的正确方向是第 (5) 代「有界后退 + 滞回解锁」**（`release_depth 4.0 > 触发 3.0`、连续 M=5 步、每局 ≤3 次），因为 (1) 的病根是**触发面与解锁面重合、没有滞回**。改罩前必须过 **P3.5 回归**（不振荡/不倒撞/不驻带/解锁真发生，负载用 shield-on heuristic 而非被测 actor）。**读 `safety.py` 只读函数体会得出错误裁定 —— 设计史在 docstring 里。**
- **「shield 只是在危险那一步接管」—— 否，它 latch 整局**（08-18 第四轮读码，`safety.py:115-116`，提案 §4.5 D1）。`if self._engaged: return True`，`reset()` 只在**局间**清（`v0_rollout_eval.py:912`）⇒ 一旦 D̂ < 3.0 触发，**策略在本局剩余全部步都失效**，被钉在 standoff 上直到 `max_steps`（`override_action:137-140` = D̂<3.0 后退 / D̂≥3.0 hold）。⇒ **①′ 若在 shield-on 下测，S_blocked 里任何贴到 3.0 m 的策略本局当场结束 ⇒ arrival 不可能 ⇒ ①′a-b 与 ①′d-b 互斥、合取不可满足**；并**推翻**「①′ vs ④′ 交集只有逼障」的结论 —— latch 罩下**交集是空集**。**这是当前提案的头号阻塞项（签字项 5r）。**
- **「shield 能替策略把障碍绕开，所以 shield-on 下到达率没意义」—— 否，罩不转向**（08-18 读码，`safety.py:139-140`）。`override_action` 只有 body −x 后退与 hold ⇒ 罩**不能**替策略完成绕行。反面是：**④′a 硬碰 0 与 ④′b ratio 的高分主要由 latch 产生、不由策略产生** ⇒ **④′ 现口径测的是罩不是策略**。
- **「④c 的 off 臂 near-coll = 0 会被判 vacuous」—— 否，冻结码里是直接 FAIL**（08-18 读码，`v0_metrics.py:305-307/313`）。`rate_off <= 0 ⇒ ratio_ok=False ⇒ overall_ok=False` ⇒ **理想逼障策略（从不进 1.5 m）会被判 ④ FAIL**，比第三轮记的「vacuous」**更严重**；且 ④′c 提的 `near_coll_rate_off > 0` **在冻结码里已等价存在** ⇒ 修法必须是**方法学 re-freeze 注记**（满足遭遇机会 K 时 `rate_off==0` ⇒ **N/A**），不能只写在 ④′c 里。`0.80` / `1.5 m` 仍不动。
- **「④c 的 ratio 是两臂公平比较」—— 否，是 pooled per-step，被局长搬动**（08-18 读码，`v0_metrics.py:296-301`）。`hits / 全部局的总步数` ⇒ latch 后 on 臂被拖到 `max_steps` 的安全步**稀释** `rate_on`、off 臂早撞局短 ⇒ **ratio→0 结构性通过**，且 `max_steps` 越长越宽。⇒ 必须落盘两臂总步数/命中数（0.80 阈值不动，只加诊断）。
- **「`make_start_episodes` 能生成多样起点」—— 否，所有局共用同一个起点**（08-18 读码，`v0_rollout_eval.py:233`）。`start = [0,0,cruise_alt]` 固定，只随机 heading；而 `env_airsim_16` 在巡航高度**基本开阔**（`:269-271` 原注释）⇒ (a) 从原点**扫不出 16 个 S_blocked**、gate 不可跑；(b) 32 局是**同一点出发的 32 条射线**、几何高度相关 ⇒ **n=16 的二项功效计算前提被破**。⇒ 起点池必须保留 `candidate_positions`（真实轨迹位置 + teleport 询问），只去掉深度窗准入、改由探针**打标签**（签字项 5t）。
- **「带占用用前向中心裁剪就能测到贴障」—— 否，理想行为是侧掠、前向开阔**（08-18，提案 §4.5 D4）。真正的贴障绕行里障碍在**侧**、前向深度开阔 ⇒ `frac_steps_in_band ≈ 0`；唯一能刷到带占用的姿态是**机头对准 3 m 内的障碍**，而那恰好触发 shield = 整局失效。⇒ 带占用必须用**全向最小净空**（离线位姿回放），不是前向裁剪、**也不只是**速度方向。
- **「效率/带占用只在到达 ep 上算」是必要的，但它让判据对策略质量非单调**（08-18，提案 §4.5 E3）。到达集合由**被测策略自己**决定 ⇒ 只在最容易 8 局到达的差策略在**容易子集**上算效率，能到 14 局的好策略在**更难的局**上算 ⇒ **把策略改好可能把 ①′c-b 从 PASS 翻成 FAIL**，等于奖励「保守放弃难局」。⇒ 效率/带占用改在**固定公共子集**（建议 = P7 planner 到达的 start）上报或按 start 配对。
- **「⓪ 的 AbsRel ≤0.30 能保证罩会触发」—— 否**（08-18 手算，提案 §4.5 E4）。AbsRel 0.30 在 `D_gt=3.0 m` 允许 `D̂` 高读到 **3.9 m** ⇒ **罩不触发**而 ⓪ 仍 PASS；median 还允许**一半像素任意坏**。⇒ ⓪ 须增功能项 `P(D̂ > trigger | D_gt ≤ trigger) ≤ ε`、用 **p90** 而非 median、support 改**逐帧**。
- **「S_open 全过说明策略学到了视觉导航」—— 否，S_open 由特权盲策略构造性通过**（08-18，提案 §4.5 F7）。heuristic（proprio 直线 oracle）本身就在 S_open 上满分 ⇒ S_open 三项**不构成任何视觉能力证据**，只是退化护栏。⇒ 应加**盲对照臂**（图像置零/打乱、其余不变）**必须在 S_blocked FAIL**；若它也过，则 gate 与视觉无关。这条同时补上「反事实臂被删」的缺口。
- **「`path_efficiency ≥0.90` 只允许 10% 冗余」—— 否，上界是 1.11 ⇒ 实际允许 23%**（08-18 手算，提案 §4.5 F1）。到达半径 3.0 m ⇒ 最短行程 27 m，而分子是 `‖g−p₀‖=30` ⇒ 到达局系统性 >1。⇒ 分子改 `‖g−p₀‖ − arrival_radius` 或按 1.11 归一后重述（**口径对齐不是放松**，必须跑前定）。另：效率**只算平移** ⇒ 原地转 yaw 不增路径长，「磨蹭旋转」只被未冻结的 `max_steps` 罚。
- **「语料里存的是策略指令动作」—— 否，存的是 shield 执行后动作**（08-18 读码，`collector.py:186/196`）。`action` 被 `override_action` **覆盖**后同时喂 `env.step` 和 `Transition`，指令动作**被丢弃**（只剩 `intervention` 布尔）。好处：WM 学的是**真实动力学**，没把罩学进转移函数。坏处：语料里**不存在**「距障 <3 m 且指令前飞」的 `(z,a)` 对 ⇒ `dynamics.step` 在 **[1.5,3.0] m 带上是纯外推** ⇒ **想象里「贴障前飞」的后果是虚构的**。⇒ §3.1 重采从「语料偏斜」升级为「**逼障不可学**」；并应加 `action_commanded` 落盘（提案 §5 项 5e）。
- **「新判据能防住学出横漂/绕飞/不动」—— 只防住「混过 gate」，不等于「学得会」**（08-18 提案 §1.4b）。判据是 gate，actor 优化的是**想象里的 RH 回报**。真实几何下（`w_progress=1.0`/`w_maneuver=0.01`/H=15/5 Hz 盒/‖g‖₀=30）手算：前飞 **+14.85** > 斜绕 **+13.68** > 不动 **0.00** > 横漂 **−0.65** ⇒ 不动与横漂**已被罚**，实测 85° 横漂**不由奖励结构解释** ⇒ **抑制退化的主力是 P0（R1），不是判据**。两个真弱点：(i) 前飞 vs 斜绕只差 **8%**，RH 的 4–6× 误差足以翻转（已实测翻转），且 H=15×1 m 只覆盖 30 m 的一半 ⇒ **绕大圈的代价落在窗口外**，本周期**无干净训练侧抑制**（时间成本与逼障冲突；最短绕行 oracle 属 V2）⇒ 登记为已知残余风险；(ii) `p_coll` 死 ⇒ 想象里撞墙零成本 ⇒ 短视目标实际偏好**直冲穿墙** ⇒ **P2 也是「不学成直冲」的前提**。另：`a=0` 正是 C2 `tanh` 的**初始化点** ⇒「不动」须靠**训练期**监控 imagined ΣG / analytic ΣΔ‖g‖ 比值（R1 臂 b），不能只靠事后 gate。
- **「旧判据至少排序是对的」—— 否，完全反的**（08-18）。旧口径：撞墙 progress **~+9** > 不动 **0** > 横漂 **−7.43**，而 ④ 给不动/横漂**最高安全分** ⇒ 撞墙排第一、绕飞排最后。
- **「heuristic 是要打赢的能力基线」—— 语义已变**（08-18 提案）。它是**特权 proprio 直线 oracle**（`train_rl.py:33-74`，`yaw` delta ≡ 0、从不避障），新口径下它是①**分层器**、②S_open 的**效率上界**、③S_blocked 的**≈0 地板** —— 不是被打赢的对象。
- **「①d AbsRel 0.0641 ⇒ 近处深度可信」—— 否**。①d 是 `D_gt ∈ (0,200] m` 的**全域 median**；全域 0.064 与「1.5 m 的墙读成 ~6 m」**可以共存**（V0 ④ 根因就是这个）。近带从未单独 gate ⇒ 提案新增 **V4-⓪**（`D_gt ∈ (0,3.0] m` 上 median AbsRel ≤ 0.30，**阈值不降**）。
- **「V1-② 已经证明想象可信 ⇒ V4 想象没问题」—— 否，三处不覆盖**（08-18）。V1-② 确实是多步保真（`reward_beat_frac` 0.93）但：① bar 是「**打赢常数基线**」不是校准（高估 4–6× 也能打赢，且校准曲线 t0–t4 才准、t≈6 起爆）；② 当时 `coll_ok=null`（`coll_claimed=false`）⇒ **p_coll 保真从未主张**；③ **V4 实际用的是 RH 线 `wm_ckpt_r60_rh_20260816/wm_step_1000.pt`，从未重过 ②**。换 WM 应重跑 ②，没重跑。
- `PROJECT_STATUS.md` / `RUNBOOK_v0.md` §1 若仍写「V1 进行中 / V4 未开始」而与 `V4_GATE_STATUS` 冲突时 → **以 V4 活文档为准**（并应回写那两处）。

---

## E. 最短路径（5 分钟对齐）

1. `V4_GATE_STATUS.md` §1  
2. [`V4_RH_CALIB_125_STATUS.md`](V4_RH_CALIB_125_STATUS.md) — RH 校准曲线 **DONE**：非 1:1（π 6.66× / 前飞 4.18× / 后退反号）⇒ 签字材料已出；**不签** §4 In 表  
2f. [`V4_RH_REOPEN_125_STATUS.md`](V4_RH_REOPEN_125_STATUS.md) — **DONE**：R1 calib 1:1 → analytic AC 重训 → ① FAIL / ④ PASS  
2g. [`V4_CRITERIA_REFREEZE_PROPOSAL_20260818.md`](V4_CRITERIA_REFREEZE_PROPOSAL_20260818.md) **§0 + §4.6 + §5.0** — **判据本身不成立**（旧 ① 奖励撞墙 / 旧 ④ 可空过 / 两者对抗）⇒ 新口径 = 分层到达 + ⓪⓿ 前置门。**实施口径 = §4.6 v2 整合稿 + §4.6.8（第五轮）+ §4.6.9（第六轮）+ §4.6.10（第七轮）+ §4.6.11（第八轮 V0–V5）+ §4.6.12（第九轮 W1–W7）**（§1/§2 是事前记录、与 D1–D4 冲突，不得照实施）；**签字口径 = §5.0 削减签字表 v3，§5 旧表禁止整表签**。**头号阻塞 = 5z（第七轮修订文本）「in-band = `NOT _breached`（D̂ ∪ τ ∪ p_coll 三通道）∧ `engaged=false`；band 是速度条件的」**，**并列阻塞 = 第九轮的 5al（起点集互斥口径 + 5ag 配对检验）/ 5am（v5 条件化 + P3.5 本周期 N/A）**。第八轮：U1–U9 已闭合；**第九轮：第八轮「14 行可签」失效 ⇒ 扩为 16 行表**。**✅ 2026-08-20 签字完成（16/16）**：14 行采纳 + `5af`=(a) + `5ag`=(B) + 包内 `5p` 裁定（到达 = `min_t dist ≤ 3.0`、主动终止 out of scope）⇒ **判据 re-freeze 生效，实施中改阈值须重签**；三条主张范围声明已登记进 `V4_GATE_STATUS.md` §1.1（不主张 AC 增益 / 仅前向扇区 / 主动终止不测）。**R1 已 DONE（P0 满足）；实施进度（08-20）**：**P3 = `insufficient_support`（非 FAIL）**；**下一步 = P4.5** → 重跑 P3/P1/P4；R-16=(B)；supervisor 已停（见 [`RUNBOOK_v4.md`](../../experiments/aerial/RUNBOOK_v4.md) / [`V4_GATE_STATUS.md`](V4_GATE_STATUS.md)）  
3. `ACCESS.md`  
4. 需要 V0/V1 数字时再打开 `V0_GATE_STATUS` / `V1_GATE_STATUS` 的 §1
