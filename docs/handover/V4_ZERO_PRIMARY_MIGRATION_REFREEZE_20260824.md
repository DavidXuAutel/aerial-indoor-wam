# V4-⓪ primary 迁移 re-freeze —— ⓪d@3m → ⓪h@12.2m（A 方案 · 待签字）

> **性质**：对 **2026-08-20 已冻结** 的 [`V4_CRITERIA_REFREEZE_PROPOSAL_20260818.md`](V4_CRITERIA_REFREEZE_PROPOSAL_20260818.md) §4.6.2 **局部 supersede** —— 只改 **V4-⓪ 的 primary/secondary 划分** 与 **P3/P4.5 过关定义**；**不改** ⓪a/b/c 阈值、不改 ①′/④′/⓿、不翻 `enable_policy_update`、不剥 D̂ OR 腿（`5ao` 仍挂起）。
>
> **状态**：**✅ 2026-08-24 签字完成（12/12 采纳）**。Harness 已接 ⓪h primary（`v4_zero_eval.py`）；下一发 = 125 权威 emit on `p45_merged` hold035。
>
> **依据链**：RUNBOOK §3 **#24 (AN)**（单目单帧尺度不可观测 ⇒ ⓪d@3m 在 D̂ 通道差 12–14×）+ [`V4_THREE_ZONE_DECLARE_20260823.md`](V4_THREE_ZONE_DECLARE_20260823.md)（部署 **三线 + D**；⓪d 退役 deploy primary；⓪h 诊断冻结 §4c）+ 用户 **2026-08-24** 裁定「不信 3 m 门 ⇒ 采用 A 方案」。
>
> **审计链纪律**：§4.6.2 原 **⓪d primary** 行**原文保留、不改写**；本稿以 **supersede 注记 + 新表** 方式提出，**§7 签字表全填** 后才生效。

---

## 0. 问什么

在 **部署已裁定为 `safety.kind: three_zone`（engage_outer ≈ 12.2 m）** 的前提下，V4 merge 的 **P3 权威门** 是否仍应使用 **gen-4 时代的 ⓪d@3.0 m**（`min_depth_m` 硬触发漏检率）？

**本稿答案（A 方案）**：**否**。⓪d@3m 与当前传感器栈及部署合同**不自洽** ⇒ **降为 secondary（只报、不入 merge）**；**⓪h engage-miss @12.2 m** 升为 **V4-⓪ primary 功能项**。

---

## 1. 物理依据（签字前须认同的事实，非阈值）

| # | 事实 | 证据 |
|---|------|------|
| **F1** | 部署深度头 = **RGB 四帧窗口 → DA3/DepthHead → D̂**；**不读 IMU** | `depth_predictor.py` 仅 `obs.rgb`；collector 在 shield 前写 `depth_min_pred` |
| **F2** | IMU 存在于 `Observation`，用于 **τ 去旋转** 等旁路，**不进深度训练/推理图** | `train_depth_head.py` 注释；`collector.py` 不传 IMU 给 depth |
| **F3** | ⓪d@3m 隐含 **σ_rel ≈ 2%** @3 m；实测老头 **σ_rel ≈ 28%**（p90 AbsRel 0.47–0.53）⇒ **差 12–14×** | `V4_GATE_STATUS.md` **(AN)** |
| **F4** | 三线方案用 **更远 engage + 更松深度预算**（engage 带允许 **~25%** 欠读）换可部署性 | `V4_THREE_ZONE_DECLARE_20260823.md` §3 |
| **F5** | TZ-3Z 诊断：老头在 `20260823_full` 上 **⓪h hold035/full77 双 PASS**；仍为 `authoritative=false` **仅因** V4 frozen primary 仍是 ⓪d | `artifacts/v4_three_zone_branch_*_20260823_full.json` |

**推论（不签 F1–F5 则不得签后续行）**：在 **不更换传感器栈** 的前提下，继续把 **⓪d FAIL** 当作 **P4.5 / P8 阻塞** = 用 **不可达** 的尺子卡 **已裁定的 deploy 路线**。

---

## 2. A 方案改动一览（相对 2026-08-20 冻结）

| 对象 | 2026-08-20 frozen | A 方案（签字后） |
|------|-------------------|----------------|
| **V4-⓪ primary 功能项** | **⓪d** @ `trigger = min_depth_m = 3.0 m` | **⓪h** @ `engage_outer_m = 12.2 m` |
| **⓪d** | primary（`aggregate_verdict` keys 含 `0d`） | **secondary / report-only**；JSON 仍输出，标签可加 `0d_legacy` |
| **⓪h** | 仅 `v4_three_zone_eval` 诊断 | **并入 `v4_zero_eval` primary**；与 deploy 三线参数对齐 |
| **P3 权威 PASS** | ⓪a∧⓪b∧⓪c∧**⓪d**∧⓪e | ⓪a∧⓪b∧⓪c∧**⓪h**∧⓪e |
| **P4.5 深度阻塞** | 控制臂 ⓪d `consec=2` ⇒ 考虑 depth FT | **⓪h FAIL** 才阻塞 depth FT；⓪d FAIL **不阻塞** |
| **depth FT 动机** | 为过 ⓪d@3m | **禁止**仅为过 ⓪d 开训；⓪h 亦 FAIL 时另案（传感器 / 语料 / 非单目方案） |
| **deploy yaml** | 已 `three_zone` | **不变**（本 re-freeze 与 deploy 对齐，不要求回退 gen-4 latch） |
| **⓪a / ⓪b / ⓪c / ⓪e** | primary | **不变** |
| **⓪f** | ①′d-b 带校准 + 误触发诊断 | **不变**；⓪f(3)「D̂@min_depth_m 误触发」**降为 report**（deploy 不再以 3 m latch 为主触发） |
| **①′ / ④′ / ⓿ / P1 / P7 / P8** | 不变 | **不变**（本表不碰） |
| **`enable_policy_update`** | false | **不变** |

---

## 3. ⓪h primary 定义（签字后冻结 —— 与 DECLARE §4c 对齐）

| 符号 | 含义 | 冻结值 |
|------|------|--------|
| `engage_outer_m` | 三线外圈开始减速距离（8/5/1.5 @ 2/1，a=2.5，delay=0.2s） | **12.2 m** |
| `L1` / `L2` / `L3` | 速度线 / 刹停线（deploy 默认） | **8 / 5 / 1.5 m** |
| **条件帧** | `GT_fwd ≤ engage_outer_m` | 与 DECLARE 一致 |
| **miss** | `D̂_fwd > engage_outer_m`（欠读 ⇒ 晚 engage） | 与 `check_0h` 一致 |
| `p_engage_miss` | `P(miss \| 条件)` 上界 | **≤ 0.10** |
| `max_consecutive_miss` | 连续 miss 上界（fail 若 **≥ 4**） | **< 4**（允许最多 3 连 miss） |
| **几何** | `D̂_fwd` / `GT_fwd` = 前向锥 `forward_min`（非全 FOV min） | `depth_geometry.forward_min_depth` |
| **权威语料** | P3 / P4.5 控制臂 | `dataset_v0_p45_merged_20260821` + **hold035**（与 TZ 诊断切片一致） |
| **深度头** | 控制臂 | 老头 `depth_ckpt_da3_r60_20260814` |

**总判（P3 primary）**：

```text
⓪_ok_primary ⟺ ⓪a ∧ ⓪b ∧ ⓪c ∧ ⓪h ∧ ⓪e
```

⓪f、⓪d_legacy **不进入** 上式。

---

## 4. ⓪d legacy（secondary —— 仍落盘、不 gate）

| 项 | 保留内容 |
|----|----------|
| 定义 | `P(D̂_fwd > 3.0 \| GT_fwd ≤ 3.0) ≤ 0.05` 且 `max_consecutive_miss < 2` |
| 地位 | **report-only**；FAIL **不阻塞** P4.5 / P8 |
| 用途 | 与 gen-4 / #24 对照；与 TZ τ-miss 表并列 |
| 禁止 | 不得因 ⓪d FAIL 单独触发 depth loss FT 或改 deploy 回 3 m latch |

---

## 5. P4.5 / P3 过关定义（签字后）

| 步 | 旧阻塞叙事 | A 方案 |
|----|------------|--------|
| **P4.5 语料** | 77 ep、近带 315 帧 | **保留**（仍服务 ⓪b / WM / P1） |
| **P4.5 深度** | 控制臂 ⓪d `consec=2` ⇒ 须 depth FT | **改为**：控制臂 **⓪h** on `p45_merged` hold035；**PASS ⇒ P4.5 深度项结案** |
| **P3 权威** | `v4_zero_eval` → ⓪d FAIL | 同 harness 改 primary 后重 emit；**以 ⓪h 为准** |
| **TZ-3Z** | 并行诊断 | **不替代** p45 权威跑；TZ 双 PASS 仅作 **先验信心**，不作 merge 证书 |

**P4.5 深度项结案条件（提议）**：

```text
oldhead × p45_merged × hold035  ⇒  v4_zero_eval (或等价)  ⇒  ⓪_ok_primary == true
```

---

## 6. 签字后实施清单（**2026-08-24 已落地 Mac 侧**）

| # | 动作 | 文件 / 产物 | 状态 |
|---|------|-------------|------|
| I1 | `aggregate_verdict` primary keys：`0d` → `0h`；`check_0h` 接入主路径 | `v4_zero_eval.py` | ✅ |
| I2 | JSON 输出 `0d_legacy` + `0h` | 同上 | ✅ |
| I3 | 单测：primary 含 ⓪h、⓪d_legacy 不 gate | `test_v4_zero_eval.py` | ✅ |
| I4 | `V4_GATE_STATUS.md` / `V4_RUNBOOK_125_STATUS.md` / `RUNBOOK_v4.md` §2.1 | handoff | ✅ |
| I5 | `RUNBOOK_v4.md` §0 + 变更记录 | runbook | ✅ |
| I6 | 125 重跑：`p45_merged` hold035 老头 | `artifacts/v4_zero_p3_oldhead_p45_hold035_20260824.json` | ⬜ **125 下一发** |

---

## 7. 签字表（**唯一可签表** · A 方案）

> **签法**：在「裁定」栏填 **✅ 采纳** 或 **❌ 驳回**（驳回须写替代方案，否则视为未签字）。**任一行留空 ⇒ 整表未签字，不得按 A 方案改 harness / 改 P4.5 阻塞叙事。**
>
> **建议顺序**：先签 **6ap-1（物理依据）** → **6ap-2～4（primary 迁移）** → **6ap-5～9（不动项与 P4.5）** → **6ap-10～12（边界）**。

| # | 项 | 提议 | 裁定 |
|---|-----|------|------|
| **6ap-1** | **物理依据**：确认 F1–F5（§1）—— 深度头 **RGB-only、无 IMU 融合**；⓪d@3m 在 D̂ 通道 **量级不可达**（#24 AN）；三线是用距离换精度预算的 **有意设计** | 采纳 | **✅ 采纳（2026-08-24）** |
| **6ap-2** | **⓪d@3.0 m 降为 secondary / report-only**：仍落盘对照，**FAIL 不阻塞** P4.5 / P3 权威 / P8 | 采纳 | **✅ 采纳（2026-08-24）** |
| **6ap-3** | **⓪h engage-miss 升为 V4-⓪ primary 功能项**；并入 `v4_zero_eval` 的 `aggregate_verdict` primary 合取 | 采纳 | **✅ 采纳（2026-08-24）** |
| **6ap-4** | **⓪h 参数冻结**（§3）：`engage_outer_m=12.2`，`p_engage_miss≤0.10`，`max_consecutive_miss<4`，条件/ miss 定义与 DECLARE §4c、`check_0h` 一致 | 采纳 | **✅ 采纳（2026-08-24）** |
| **6ap-5** | **⓪a / ⓪b / ⓪c / ⓪e 阈值与 primary 地位不变**（median/p90/support/部署分布） | 采纳 | **✅ 采纳（2026-08-24）** |
| **6ap-6** | **⓪f 地位不变**（仍服务 ①′d-b 带校准）；⓪f(3)「D̂@3m 误触发」**降为 report-only**（deploy 主触发已非 3 m latch） | 采纳 | **✅ 采纳（2026-08-24）** |
| **6ap-7** | **P3 / P4.5 权威过关**改为 §5：`⓪_ok_primary = ⓪a∧⓪b∧⓪c∧⓪h∧⓪e`；控制臂 = 老头 × `p45_merged` × **hold035** | 采纳 | **✅ 采纳（2026-08-24）** |
| **6ap-8** | **禁止**仅为过 ⓪d@3m 开 depth loss FT 或换头部署；⓪d FAIL ** alone ** 不得作为 WM/P8 阻塞理由 | 采纳 | **✅ 采纳（2026-08-24）** |
| **6ap-9** | **⓪h FAIL** 时：按 R-16 **(B)** 预注册处置（不静默降阈值、不换易语料凑 PASS）；**传感器栈变更**（IMU 融合深度 / 立体）须 **另案 re-freeze**，不得在本表隐式引入 | 采纳 | **✅ 采纳（2026-08-24）** |
| **6ap-10** | **deploy 对齐**：权威评测与 `configs/aerial_rl.yaml` 的 `three_zone` 默认 **8/5/1.5 @ 2/1** 一致；**不要求** yaml 回退 gen-4 `min_depth_m` latch | 采纳 | **✅ 采纳（2026-08-24）** |
| **6ap-11** | **签字后下一发**（125/H100）：`v4_zero_eval`（或签字后已接 ⓪h 的等价路径）on `p45_merged` hold035 → `artifacts/v4_zero_p3_oldhead_p45_hold035_20260824.json`；**不以 ⓪d 为 merge 门** | 采纳 | **✅ 采纳（2026-08-24）** |
| **6ap-12** | **边界**：`enable_policy_update` **仍 false**；不签 `5ao`、不剥 D̂ OR 腿；①′/④′/⓿/P1/P7 阈值 **本表不碰**；与 2026-08-20 §5.0 十六行 **并存**，冲突处以 **本表 ⓪ primary 行为准** | 采纳 | **✅ 采纳（2026-08-24）** |

### 签字块

```text
签字人：用户
日期：2026-08-24
6ap 行数：12 / 12 采纳
备注：全部同意；增补 runbook。
```

---

## 8. 签字后下一发命令（125 · 不重训）

```bash
cd ~/aerial-wam-v2 && source experiments/aerial/scripts/env_4090.sh
DATA=experiments/aerial/rl/artifacts/dataset_v0_p45_merged_20260821
OLD=experiments/aerial/rl/artifacts/depth_ckpt_da3_r60_20260814/depth_step_2000_da3_ft_head.pt
TAU=experiments/aerial/rl/artifacts/tau_ckpt_foe_r60_20260815/tau_foe_calibrator.pt
# 须在 Mac sync 后跑（harness 已接 ⓪h primary）
$AERIAL_PY -m experiments.aerial.rl.v4_zero_eval \
  --dataset "$DATA" --depth-ckpt "$OLD" --tau-ckpt "$TAU" --device cuda \
  --heldout-frac 0.35 --split-seed 0 \
  --emit artifacts/v4_zero_p3_oldhead_p45_hold035_20260824.json \
  2>&1 | tee logs/v4_zero_p3_oldhead_hold035_20260824.log
```

**先验（TZ 诊断，非权威）**：同老头在 `20260823_full` 上 ⓪h 已 PASS ⇒ **p45 hold035 有较大概率 PASS**，但 **必须以 p45 权威 emit 为准**。

---

## 9. supersede 注记（写入 §4.6.2 审计链 —— 签字后由实施方追加）

> **2026-08-24 re-freeze 6ap**：§4.6.2 **⓪d（功能项）** 的 **primary** 地位被 **⓪h** 取代；⓪d 定义保留为 **legacy report**。P3 `aggregate_verdict` 与 P4.5 深度阻塞叙事以本文件 §5、§7 为准。部署 primary 与 [`V4_THREE_ZONE_DECLARE_20260823.md`](V4_THREE_ZONE_DECLARE_20260823.md) 一致。
