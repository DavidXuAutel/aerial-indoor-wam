# Aerial WAM v2 — 项目现状整理

> **日期**: 2026-08-18（对齐 V4 活文档；V0 merge 08-14 / V1 merge 08-15）  
> **阅读顺序**: [handover/LIVING_DOCS.md](handover/LIVING_DOCS.md)  
> **代码来源**: `aerial-wam-v2` @ `main`（历史分支名 `aerial-rl-skeleton`）  
> **阈值权威**: [frozen spec §4.1](superpowers/specs/2026-08-04-aerial-wam-v2-frozen-spec.md) — 本文只摘录，不新建第二真相源

---

## 1. 项目目标

重建 **goal-first 纯视觉世界模型**（DreamerV3 RSSM），从随机初始化干净重训。

**V0（已完成 2026-08-14）**：四信号 merge PASS → 已翻：

- `world_model.depth_head.enable: true`
- `safety.kind: threshold`

**V1（已完成 2026-08-15 严谨 merge PASS）**：`dynamics.kind=torch` + `enable_wm_update` + τ/`foe_calibrated` + 双通道罩 — 见 [V1_GATE_STATUS](handover/V1_GATE_STATUS.md)。

**V4（进行中）**：想象 AC；`enable_policy_update` **仍 false** 直至 V4 merge PASS — 见 [V4_GATE_STATUS](handover/V4_GATE_STATUS.md)。

旧 `wm_step_5000.pt` 已判定为单柱 RGB shortcut，**不可 warm-start**。权威 V0 WM：`wm_ckpt_r60_20260814`；V4 RH 线另有 `wm_ckpt_r60_rh_20260816`。

---

## 2. 一句话结论（2026-08-18）

**✅ V0 / V1 均已 merge PASS。**  
**当前：V4-MVP** — **下一步 = P4.5**。P3 = **`authoritative=false` / near-band `insufficient_support`**（不是 ⓪ FAIL）；P1 FAIL；P4 须重跑。R-16 运营 **(B)**。Supervisor **已停**。入口 [`RUNBOOK_v4.md`](experiments/aerial/RUNBOOK_v4.md)。`enable_policy_update` **仍 false**。

**⚠️ 2026-08-18 新立案：V4-① / ④ 判据本身不成立** —— 旧 ① **奖励撞墙**（撞墙 `done` ⇒ 停在离目标最近点 ⇒ progress 拿满）、旧 ④ **可被横漂空过**（on-rate 0 + `n_contact=0` ⇒ 自动 PASS）、两者**互为对抗** ⇒ **即使双 PASS 也证明不了想象 AC 有用**。新口径 = **分层到达**（S_open 不退化 + S_blocked 逼障绕行，合取）+ 两条新前置门 **V4-⓪**（近带深度）/ **V4-⓿**（想象排序）。**§4.1 阈值一字不动**，`n` 8→每层 16（收紧）。稿：[V4 判据 re-freeze 提案](handover/V4_CRITERIA_REFREEZE_PROPOSAL_20260818.md)（**待签字**，与 R1 正交）。`enable_policy_update` 仍 **false**。
> **同日补（§1.4b/§1.4c）**：判据只挡「混过 gate」，**不等于学得会**。真实几何下手算 前飞 **+14.85** > 斜绕 **+13.68** > 不动 **0.00** > 横漂 **−0.65** ⇒ 退化行为**已被目标函数罚** ⇒ 抑制退化的主力是 **P0（R1）**，不是判据。两个真弱点如实登记：前飞 vs 斜绕仅差 8%、H=15 覆盖不到绕大圈的代价 ⇒ **绕飞本周期无干净训练侧抑制**；`p_coll` 死 ⇒ 想象里撞墙零成本 ⇒ **P2 也是「不学成直冲」的前提**。另查明 `collector.py:186/196` 存的是 **shield 执行后**动作 ⇒ 语料里没有「逼障带 + 指令前飞」的 `(z,a)` 对 ⇒ **逼障在当前语料下不可学**（§3.1 重采从「偏斜」升级为「不可学」）。
> **第三轮复核补漏（§4.4，18 项）**：4 项致命 —— **④′c 会把理想目标行为判成 `vacuous`**（与旧 ④ 对称的陷阱，改「遭遇机会」口径）、**逐步 GT 深度在线落盘会改 dt**（须位姿回放离线取）、**P0–P8 缺「语料重采+WM 重训」⇒ P1 给注定作废的 WM 发证**（插 P4.5）、**yaw 解耦攻击**（带占用与 shield 前向锥可同时被转开机头绕过 ⇒ 改按速度方向算）。5 项重要 —— **反事实臂被删**（新口径全绝对阈值 ⇒ 不证「想象 AC 必要」）、训练/gate 起点集未互斥、**功效从未算**（真值 0.80 仍 35% 放过；15 条 AND ⇒ 误 FAIL ≈54%）、`max_steps` 未冻结、arrival 用末态可能漏判 + 「主动终止」一条没测。9 项应补见提案 §4.4 C。签字项加 **5h–5q**。
> **第四轮复核补漏（§4.5，18 项，读码确证）**：新判据与**既有实现互斥**，4 项致命 —— **① shield 会 latch 整局**（`safety.py:115-116`，触发后策略本局全失效、被钉在 standoff）⇒ 在 shield-on 下 **①′a-b（到达）与 ①′d-b（带占用）不可同时满足**、且「①′④′ 不对抗」的结论作废 ⇒ **头号阻塞项（5r）**；**冻结码里 `near_coll_rate_off == 0` 是 FAIL 不是 vacuous**（`v0_metrics.py:305-307`）⇒ 理想逼障策略直接 ④ FAIL，须出方法学 re-freeze 注记判 N/A（阈值仍不动，5s）；**`make_start_episodes` 所有局共用一个起点**（`:233`）+ 巡航高度基本开阔 ⇒ **S_blocked 填不满、gate 不可跑**，且 32 局是同点 32 射线 ⇒ 二项功效前提被破（5t）；**带占用用前向裁剪对「侧掠」不可满足**（5u）。7 项重要 —— ④c ratio 是 **pooled per-step** 被局长搬动；罩**不转向** ⇒ ④′ 测的是罩不是策略；效率只在到达 ep 上算 ⇒ **判据对策略质量非单调**（改好可能翻 FAIL）；⓪ 的 AbsRel 0.30 允许 3 m 墙读 3.9 m ⇒ **罩仍不触发也能 PASS**；⓿ 未定真实侧 reward；P5 与「与 V1 部署一致」红线冲突未裁；探针 off / actor on 构型不一致。7 项应补见提案 §4.5 F（含 `path_efficiency` 上界实为 **1.11** ⇒ 0.90 实际允许 23% 冗余；**盲对照臂**必须在 S_blocked FAIL）。签字项加 **5r–5w**。
> **整合 → §4.6「判据 v2 整合稿」= 实施唯一权威口径**（签字项 13–16；§1/§2 原表按审计链保留不改写，但**不得照 §1 实施** —— §1.0/§1.3/§1.5 已被 D1–D4 证伪）。同时**更正第四轮自己对 D1 的推荐**：候选 (i)「非 latch 瞬时罩」= `safety.py:48-79` 记录的历史设计 (1)，实测**振荡 ⇒ `rate_on ≫ off` ⇒ ratio 反转** ⇒ 退出候选。新裁定 = **shield 第 (5) 代：有界状态反馈后退 + 滞回解锁**（`release_depth 4.0 >` 触发 `3.0`、连续 `M=5` 步、每局 ≤3 次解锁、逐局落 `latch_step[]/release_step[]/n_release`）—— 第 (1) 代的病根是触发面与解锁面重合、**没有滞回**；策略退到 4 m 稳定 1 s 后**重获控制权可以转向**（罩永不转向）⇒ D1 解。强制前置 = **新增 P3.5「v5 回归验证」**（不振荡 ratio ≤0.80 / 不倒撞 `coll_after_latch=0` / 不驻带 / 解锁真发生；负载 = shield-on **heuristic**，非被测 actor ⇒ 不构成「为过 gate 调罩」），且**必须在 P3(⓪) 之后**（v5 解锁信任 `D̂ ≥ release_depth` = ⓪d 要保证的东西）。连带：v5 改部署构型 ⇒ **须同时 re-freeze V1 部署构型 + 声明 V4 ④ 与 V1 历史 ④ 不可比**（V1 对照臂正式移除）。其余 v2：**收紧** = 效率分子 −`arrival_radius`（0.90 从「允许 23%」变真 10%）、⓪ 加 p90 ≤0.50 + **功能项 `P(D̂>trigger|D_gt≤trigger) ≤0.05`** + support 逐帧、加**盲对照臂**、加 primary/secondary + OC 曲线跑前冻结、加起点几何独立性（≥10 m）；**口径修正** = 起点池改 `candidate_positions` 只打标签、band 改**全向最小净空**、效率/带占用改**固定公共子集**（= P7 planner 到达的 start，恢复单调性）、①′b-b 改**分层器确定性自检**、④′c 改遭遇机会 + **`rate_off==0 ⇒ N/A`**、⓿ 真实侧 G = analytic、GT 深度只离线取、`step_hz` 重测、冻结清单 +`cruise_alt_m`/`goal_dist_m`/起点池来源。前提链 v2 = P0→P1→P2→P3→**P3.5**→P4→**P4.5**→P5（**可能因 v5 而不再必要**）→P6→P7→P8。**代码 / yaml / 阈值仍一行未动**；`enable_policy_update` 仍 false；R1 on 125 不受影响。

> **第六轮（复核 5x 自身，读码 + 实测记录）→ §4.6.9「H1–H7」+ 签字项 5z / 5aa / 5ab / 5ac；5x 的方向被实测加强、数字与依赖链撤回，头号阻塞 5x → 5z。** **H1**：`safety.py:96-107` 的 `_breached` 是 **`D̂<3.0` ∪ `τ<1.0` ∪ `p_coll>0.5`** 三通道**并集**，且 `v4_gate_run_partials.py:250-291` 确证 **τ 通道在 V4 gate 里是活的**（`foe_calibrated`、`min_tau_s=1.0`、`use_gt_depth=False`）；两通道**几何不同** —— D̂ = 整幅 FOV min，τ = **前向中心裁剪 `center_frac=0.5` ÷ 闭合速度**（`tau_predictor.py:143-192`）⇒ 只按 `clearance_fov` 定的带**不是罩的非介入区** ⇒ in-band 改「**并集非介入**」（band ∧ `τ̂ ≥ min_tau_s` ∧ `engaged=false`）。**H1b（数字撤回）**：`action.py:43-45` `MAX_BODY_VELOCITY[0]=5.0 m/s` + `min_tau_s=1.0` ⇒ 巡航时 τ 触发到 **≈5 m** ⇒ `[3.5, 5.0]` **整段在触发区内** ⇒ 撤回，并写明「clearance `d` 处不被接管要求 **`v_fwd ≤ d/min_tau_s`**」⇒ **可证明的「逼障」再收窄为「减速贴障通过」**。**H2**：⓪a 的 support 是 `(0, 3.0]`、晚⁷ diag 分箱只有 `<1.5`/`[1.5,3.0)` ⇒ **GT>3 m 无任何实测**，而带下边界 δ 与 `release_depth_m` 都定义在那里 ⇒ 依赖链**悬空** ⇒ **新增 ⓪f**（`D_gt ∈ (3.0, 8.0]` 的 median/p90 AbsRel + **D̂ 与 τ 双通道误触发率 ≤ 0.05**），**P3 范围扩大**。**H3**：晚⁷ 近带 `P(over-read)=0.377`（**非一致欠读**）⇒ 把 gain≈0.43 外推到 3.5–5 m **无依据**；若 gain 真在 0.4，`D̂≥3.0` 需 GT≈**7 m**（已不叫逼障）⇒ **跑前预声明分叉**：⓪f 出数后若存在「并集非介入 ∧ `hi ≤ 6 m`」的带 ⇒ ①′d-b 保持 primary；**若不存在 ⇒ 降 secondary**，机制主张落到 **⓿ + P7**（事后做这个分叉 = p-hacking）。**H4/H5**：`frac_steps_in_band` 是**时间占比** ⇒ 与带内减速合起来可被「4 m 处慢速磨蹭」空过 ⇒ 改**进展加权 / 路径长加权**（primary 取更严者），纯时间占比降诊断；`θ=0.10` 为旧带所选 ⇒ **已失锚**，须由 P7 基线重导并跑前冻结，**低于 0.10 ⇒ 属放松、须单独签字**。**H6**：`tau_predictor.py:289` 默认 `dt_s=0.1` vs `step_hz=5.0`（dt=0.2）且 `:330-333` 仅条件覆盖 ⇒ 回退会让 τ 触发面**翻倍** ⇒ 加 dt 直方图 + 回退标志（`authoritative=false`）。**H7（反向）**：τ 是 `use_gt_depth=false` 纯视觉 ⇒ 红线 A2 与部署罩**不冲突**，登记已核对。另：`band_frac`/`frac_steps_in_band` 在 `v0_metrics.py`/`v4_metrics.py` 里**还不存在** ⇒ 属待实现；**G1 被实测加强**（晚⁷ full-field `<1.5` 与 `[1.5,3.0)` 的 `P(trig)` 均 = 1.0）。**代码 / yaml / 阈值 / flag 仍一行未动。**

> **第七轮（复核方 = 用户，第一次非提出人复核）→ §4.6.10「U1–U9」+ §5.0 削减签字表 v3 + 签字项 5ad–5ak；立案标题改「分层到达；逼障仅当 ⓪f 证出可行带」。** 九条全部成立，三条**实施第一天必踩**。**U1（头号）**：抬头写「以 §4.6 为准」而 §5 仍是整张「提议=采纳」表 ⇒ 整表签会把第六轮撤回的东西**冻回去**（项 5 shield-on 原稿口径 / 5k 速度方向带占用 / 5x 的 `[3.5,5.0]` / 项 10 的 `θ=0.10`），且 5r′ 仍写「必须最先裁」、§6 的 **P1–P4** 与前提链 **P0–P8 撞名** ⇒ **§5.0 削减签字表 v3 = 唯一可签表**（13 / 5z(修) / 5aa / 5ab(修) / 5ac(修) / 5y / 5ad–5ak），旧表降审计留档，§6 改 **Q1–Q5**。**U1-b（自补）**：**5d 撞点 7 项与 5e `action_commanded` 根本不在 §4.6.1 落盘清单里** ⇒ 只签 13 会静默丢字段 ⇒ **5aj** 打包补回。**U3（必踩，且是第六轮自引缺陷）**：in-band 谓词**漏 `p_coll` 通道**，且 **`engaged=false` 不等于「本步未破」**（刚破未 latch 的步会被误计入）⇒ 改 **`NOT _breached(step)`（三通道逐字展开）∧ `engaged==false`** + 落盘三通道布尔位；**U3-b**：`p_coll` 现为死值 ⇒ 非介入域是**乐观上界** ⇒ **band 冻结排在 P2 之后**（或标 conditional，P2 后重跑 ⓪f，**只许缩窄**）。**U9（必踩）**：评测期丢局（`_run_one_resilient` 吞 `None`）不修 ⇒ 每层 16 永远填不满 ⇒ 叠上「不降 n」= **gate 永久非全权、四信号全过成为不可能事件** ⇒ 新增前提步 **P0c**（三计数器分类落盘 + spare 起点补扫 + 禁降 n），排在 P1 之前。**U4（第二处自引缺陷：自指）**：θ 由 P7 推、P7 验收又含 θ ⇒ 拆 **P7-diag ⇒ 冻结 θ/k/带 ⇒ P7-accept（起点集与 seed 双不相交）**，否则等于事后调阈值（撞红线）。**U2**：分叉抽空标题 ⇒ **标题已改**；`hi ≤ 6 m` 是拍的 ⇒ 换 **`hi ≤ Q_0.25(C_P7)`** + 绝对护栏 8 m（登记为拍的）。**U5**：项 8 不得与「不改 In 表」同时签（goal-blind ⇒ 侧/后向 ①′a-o 预先注定 FAIL）⇒ 改条件项 **5af**。**U7**：5l 至今沉默、F7 盲臂**不能**替代「actor ≥ P7 planner」⇒ **5ag 强制表态，空白 = 非法签字**。**U8**：C7 算了「采纳」而前提链**没有任何 FAIL⇒停 的节点** ⇒ 新增 **P7-FAIL 下车站**（禁降阈值/换易起点/只判 S_open），**R-16 改部分闭合**。**U6**：R1 已 DONE（`30b9ff8`/`d96da1d`）⇒ P0 改 DONE、**5f 护栏恒 ≈1 须改口径或撤案**、§3.2 排除式论证作废、P1 forward-ratio 降诊断、本节第 30 行的 stale 已更正。**元结论 → Q5**：提出人自查连续四轮都能找出致命项但**收敛慢且有盲区**（U3/U4 是第六轮自引）⇒ 凡 re-freeze 提案**签字前必须有一轮非提出人复核**。**代码 / yaml / 阈值 / flag 仍一行未动**；头号阻塞签字项仍 **5z（按第七轮修订文本）**。

> **第九轮（2026-08-20，复核对象 = 第七/八轮**自己的处置**）→ §4.6.12「W1–W7」+ 签字项 **5al / 5am**；签字表 **14 行 → 16 行**；**第八轮「可以按 14 行签」的结论失效**。** W1–W7 **全部成立**，两条阻塞。**W1（阻塞）**：第七轮 U4 为解自指而加的硬约束「actor gate 起点集与 `S_diag` / `S_accept` **三者互斥**」与 E3 的固定公共子集 `P`（= P7-planner 到达的起点）**冲突** —— planner 验收趟跑在 `S_accept` ⇒ **`P ⊆ S_accept`** ⇒ actor **永不飞 `P`** ⇒ **①′c-b（效率）/ ①′d-b（带占用）的中位数无样本可算**；且与 **5ag(A)**「同 `S_accept`、按 start 配对」直接矛盾 ⇒ 就地改为 **`S_diag` ⟂ {`S_accept` ∪ actor gate}** 且 **`S_accept` ≡ `S_gate`**（训练集仍与三者不交，5m/B2 不动；θ 仍**只在 `S_diag` 上拟合** ⇒ 防事后调阈值的效力不减，**未放松任何阈值**）。**W1-b**：5ag(A) 的阈值 `arrival_rate_P7planner` 是 P7-accept 跑完才知的**随机量** ⇒ 与 5n/B3「OC 曲线跑前冻结」不相容 ⇒ 改 **`arrival_actor ≥ arrival_planner − Δ`**，`Δ` 跑前冻结（提议 **0**，`Δ=0` 与原式等价 ⇒ 不放松）+ **McNemar / paired bootstrap** 判读。**W2（阻塞）**：第五轮把 shield **v5 降为 fallback** 后**没清扫下游** —— §4.6.1 评测构型仍写「shield-on（**v5**）」、冻结清单仍含 v5 的 `release_depth_m/M/上限`、**§4.6.6 的 P3.5「v5 回归」仍标「必须在 P3 之后」**、§5 项 5 的 U1 注记同样引 v5，与 5r′(改)「本周期不动 shield」**直接冲突** ⇒ v5 全部改 **conditional**：评测构型 = **现行第 (4) 代（latch + 有界状态反馈后退）**、v5 三参数**本周期不冻结**（`release_step[]`/`n_release` 仍落盘，无 v5 时恒 0）、**P3.5 = 本周期 N/A**；并**如实登记代价**：无解锁 ⇒ **一次触发即整局 latch ⇒ 本局报废**，而 τ 通道在 `v=5 m/s` 巡航下触发到 **≈5 m** ⇒ **①′a-b ≥ 0.50 的经验可解性完全押在 P7-accept 上**（G1 只论证过带定义，从未论证到达率）；P7-accept 若在 S_blocked FAIL ⇒ 走 **P7-FAIL 下车站**，不得改判据。**W3**：5q 被记「已被 §4.6 吸收」，但 **C1（进带前 k 步的 `D̂_fovmin` / `v_fwd` / 侧向位移）** 与 **C2（`S_open` 的 `intervention_rate`）** 从未进 §4.6.1 落盘契约 ⇒ 契约自检会判 `authoritative=false`（与 U1-b 抓到的 5d/5e 同类）⇒ 已补入契约并归 **5aj**。**W4–W7（轻，就地更正）**：抬头警示行与 §1.3.5 的「§6 P1」改 **Q1**；§6 表头/正文改 **Q1–Q5 / 五条**（Q5 是新增、非改名）；§5 归属清单补漏列的**项 7 / 项 8**；重复的 `5r′` 原行补「不签、无需裁定」注记。**元结论**：第八轮宣布「可以签」时**没有复核第七轮自己新引入的约束**，也没查 §4.6 内部的 v5 残留 —— Q5 的「非提出人复核」还需加一条：**每轮处置必须清扫其下游引用**。**本轮无一处放松阈值；代码 / yaml / 阈值 / flag 仍一行未动。** ⇒ **下一动作：人填 §5.0 的 16 行**（5af / 5ag 必须勾 A 或 B；选 5ag(A) ⇒ 5al 必须同时采纳）。**本轮新增残余（只登记不解）**：无 v5 时「一次触发即报废」对 ①′a-b 的实际难度**未量化**；`Δ=0` 无独立依据；C1 的「进带前 k 步」与 5ac(a) 进展窗口 `k` **是否同一个数未定**。

> **✅ 判据签字完成（2026-08-20，§5.0 16/16 行裁定填毕 ⇒ V4 判据 re-freeze 生效）**：14 行「采纳」+ 用户手选 **`5af` = (a)**（评测 goal 限机体前向扇区、**侧/后向不测**、In-表改动仍属 V3 另案）+ **`5ag` = (B)**（**V4-MVP 不主张「想象 AC 有增益」**，只主张「不退化 + 安全」；依据 5c「planner 到达率 = 可解性上界」⇒ `Δ=0` 下 (A) 等于要求 actor 打到上界，且门槛是跑后随机量、违反 5n/B3 ⇒ 该出证留 **V5 另案**）；**`5aj` 包内 `5p` 同日裁定**：到达定义写死 **`min_t dist(p_t,g) ≤ 3.0 m`**（**不改 harness 控制流**）、「**主动终止**」**明确宣告 out of scope**；两个阻塞项 **`5al` / `5am` 均采纳**（起点集 = `S_diag` ⟂ {`S_accept` ∪ actor gate} 且 `S_accept` ≡ `S_gate`；v5 全部 conditional、**P3.5 本周期 N/A**、评测构型 = 现行第 (4) 代 latch 罩）。**签字未下调任何阈值**（三处「缩小主张 + 如实登记」不是放松）；**`enable_policy_update` 未翻**（红线）；**代码 / yaml 一行未动**。**自此起改任何阈值 / band / `n` / primary 划分都须 re-freeze 重签；实施入口 = [`RUNBOOK_v4.md`](../experiments/aerial/RUNBOOK_v4.md)。** 08-20：**P3 = insufficient_support**；**下一步 = P4.5**；R-16=(B)。三条主张范围声明已登记进 [`V4_GATE_STATUS.md`](handover/V4_GATE_STATUS.md) §1.1。
>
> **第八轮（2026-08-19，将第七轮后独立检查入库）→ §4.6.11「V0–V5」。** U1–U9 **已闭合、不再构成自毁**。削减表 14 行裁定栏**仍全空** ⇒ **下一动作是人填 §5.0（尤其 5af / 5ag），不是再开一轮改判据。** 入库三条更轻过程洞：**(V1)** P7-diag 须先冻 `[lo,hi]`、再在同一份逐步 log 上算 θ（不必再飞）；**(V2)** P2 完成判据含 collector / gate 传入 `wm_out`（`collector.py:185` 现状未传）；**(V3)** §2 表 P0 IN PROGRESS = stale，实施只认 §4.6.6。已知残余（R-1 / R-3 / R-16 剩余 / 主动终止 / tight 的 n / ④′b vs ④′c 几何 / spare 池未定量）不解。**代码 / yaml / 阈值 / flag 仍一行未动。**
>
> **第五轮（复核 §4.6 自身，读码确证）→ §4.6.8「G1–G7」+ 签字项 5x / 5y；头号裁定从「改 shield」改为「改判据的带定义」。** **G1**：`depth_predictor.py:81-90` 的 `predict_min` = **整幅深度图（全 FOV）的 min**，`min_depth_m=3.0` 就是拿它触发 ⇒ 我第四轮写的「①′d-b band = `[1.5, 3.0] m`」**是在要求策略违反部署安全罩**，且**与 latch 无关**（换瞬时罩也一样被接管）⇒ **第四轮把矛头指向 shield 是指错对象**（D1 上的第二次反转，两次都以读码为据）。最小正确修法 = band 整体**上移到 standoff 之上**：`clearance_fov ∈ [3.5, 5.0]`（provisional，下边界 = `min_depth_m + δ`，δ = ⓪ 实测 D̂ 近带欠读偏差，P3 出数后冻结、冻结后不动）⇒ 新签字项 **5x**（**本周期不动 shield**，5r′ 降 fallback）。**G2**：原提的「全向最小净空」引入 **FOV 外方位** ⇒ 「盲区贴障」可空过、且与触发几何不一致（`predict_cones` docstring 明写 P0b 前未接线）⇒ band 改 **FOV-min GT 深度**，五向 cone 只作诊断，**5u 撤案**。**G1 连带**：D1 severity **大幅下降**（剩 E2 可解释性问题）、R-2「逼障不可学」**大部分消解**（新带在罩非介入区 ⇒ 语料本来就有）、**P5 很可能撤案**（两个理由全失效）、**①′d-b 与 ④ 的对抗性消失**；**代价（诚实登记）**：可证明的「逼障」收窄为「贴 standoff 边缘紧绕行」，`[1.5,3.0]` 内行为在当前部署构型下**不可测** ⇒ 原 §1.3.2 与部署构型**本就不自洽**。另五条就地更正（= **5y**，全部收紧或补未定义分支）：**G3** 路径长须在**首次到达步截断**（否则直飞 = 27/30 = **0.90 刀口值**）、**G4** 盲臂改**打乱帧**（置零图是 OOD ⇒ 两层齐挂不构成证据）+ 加「两层都 FAIL ⇒ **inconclusive**」分支、**G5** 公共子集 `P` 上 actor 未到达的局**填 0** 且要求 `|P| ≥ 8`、**G6** ④′c 的 `K_off<5` 重跑改**有条件**（仅当 ①′a-b PASS）、**G7** `release_depth_m` **不可写死 4.0**（D̂ 近带欠读 ⇒ 解锁可能永不触发 ⇒ v5 静默退化成 v4）须由 ⓪ 校准 = P3.5 排在 P3 之后的**第二条**理由。**代码 / yaml / 阈值 / flag 仍一行未动**（本轮只改我自己未签字的 §4.6）；头号阻塞签字项 **5r′ → 5x**。

---

## 3. 四信号现状（V0 — 已闭合）

| 信号 | 判据摘要 | r60 结果（2026-08-14） |
|---|---|---|
| **①a–c** | loss↓≥2%、recon 不劣、min entropy-frac ≥0.10 | ✅ loss 3.87→1.96；recon↓；min_ent 0.47；`authoritative=true` |
| **①d** | holdout AbsRel ≤ 0.30 | ✅ **0.0641**（r60 ft-head） |
| **②** | progress ≥ random+5.0 ∨ final_dist ≤ random−3.0 | ✅ progress **13.49** vs **−4.30**；**n=8** |
| **③** | reprojection median rel ≤ 0.25；n≥8 | ✅ median **0.212**；n=90 |
| **④** | ④c ratio ≤0.80（④b 有接触才测） | ✅ ④c ratio **0.113**；④b N/A（`n_contact=0`）；**n=8** |

### 3.1 r60 部署线（head 已统一）

| 资产 | 路径（H100 `~/aerial-rl-skeleton/.../artifacts/`） |
|---|---|
| 语料 | `dataset_v0_local_depth_r60_20260814`（51 npz / 48 usable） |
| 深度 | `depth_ckpt_da3_r60_20260814/depth_step_2000_da3_ft_head.pt` |
| WM | `wm_ckpt_r60_20260814/wm_step_5000.pt` |
| Merge | `v0_gate_r60_20260814.json` |

**洞 2 ④b**：✅ 关闭（2026-08-17）— 空过为终态，实证=④c。  
**洞 3 V1-② coll**：✅ 定义关闭 + 诊断已测（r60 n-starts=4，`coll_traj_pos=5` / AUROC 0.972；**2026-08-17** WM-unseen held-out `dataset_v1_coll_heldout_20260817` → pos=**20** / AUROC=**0.977** / unique usable coll ep=**8**，`coll_claimed=true`）；**不改** 08-15 merge（仍 `coll_ok=null`）。headon coll=0 不可用。~~§4.1 n=16 vs 8~~ → **已 re-freeze 为 8**（2026-08-17）。

---

## 4. 公式与协议（§4.1 摘录）

### 4.1 信号 ①d — 深度 AbsRel

\[
\mathrm{AbsRel} = \mathrm{median}\left(\frac{|\hat{D} - D_{\mathrm{gt}}|}{D_{\mathrm{gt}}}\right)
\]

在 holdout 像素上，\(D_{\mathrm{gt}} \in (0, 200]\) m。过门：**AbsRel ≤ 0.30**。

### 4.2 信号 ①a–c — WM 训练曲线

在训练日志首尾各 \(k=\max(1, \lfloor N/10\rfloor)\) 步取均值：

| 子信号 | 条件 |
|---|---|
| a | \(\overline{\mathrm{loss}}_{\mathrm{tail}} \le 0.98 \cdot \overline{\mathrm{loss}}_{\mathrm{head}}\)（降 ≥2%） |
| b | \(\overline{\mathrm{recon}}_{\mathrm{tail}} \le \overline{\mathrm{recon}}_{\mathrm{head}}\) |
| c | \(\min_t \mathrm{post\_entropy\_frac}(t) \ge 0.10\) |

语料守卫：`_refuse_v0()` 拒绝标称 `step_hz > 8.5` 的 dt-desync 语料（除非 `--allow-v0-desync`，此时日志标 `authoritative=false`）。

### 4.3 信号 ② — 接近量 vs 随机

在 \(N=8\) 个 rollout episode 上（re-freeze 2026-08-17；原 16）：

\[
\text{PASS} \iff
\underbrace{\bar{P}_{\mathrm{policy}} \ge \bar{P}_{\mathrm{random}} + 5.0}_{\text{progress margin}}
\;\;\lor\;\;
\underbrace{\bar{d}_{\mathrm{policy}} \le \bar{d}_{\mathrm{random}} - 3.0\ \mathrm{m}}_{\text{distance margin}}
\]

### 4.4 信号 ③ — 深度尺度（当前：重投影估计器）

> **注意**：2026-08-10 起 ③ 已从「band-median Δ vs VIO」改为 **GT-proprio 位移 + 深度重投影** 估计器。详见 [signal3 reprojection handover](handover/2026-08-10-signal3-reprojection-estimator.md)。

对每个有效**接近窗**（前向余弦 ≥0.7、位移 ≥0.5 m、support 等，见 frozen spec §4.1 ③c–③e）：

\[
e_w = \frac{|\hat{s}_D - s_{\mathrm{VIO}}|}{\max(s_{\mathrm{VIO}}, \varepsilon)}, \quad \varepsilon = 10^{-3}
\]

其中 \(\hat{s}_D\) 来自重投影管线，\(s_{\mathrm{VIO}} = \|\Delta p\|\)（GT proprio 位移）。

过门：

\[
\mathrm{median}(e_w) \le 0.25, \quad n_{\mathrm{valid}} \ge 8
\]

**GT oracle**：把 \(\hat{D}\) 换为 GT depth 后的同一条 median — 当前语料上 ≈ **0.002**（head A 测 0.05–0.12 有余量）。

### 4.5 信号 ④ — Shield 有效性

在 near-obstacle 起点、shield on/off 配对 rollout 上：

| 子信号 | 条件 |
|---|---|
| ④b | 接触前干预比例 \(\ge 0.50\)；`n_contact=0` 时 **N/A**（`before_vacuous`；JSON 仍 emit 1.0 仅兼容，非测得） |
| ④c | \(\mathrm{near\_coll\_rate\_on} / \mathrm{near\_coll\_rate\_off} \le 0.80\)（④ 实证） |

Shield 触发深度：**3.0 m**（反应余量，re-freeze 注；度量带仍为 1.5 m）。

---

## 5. 基础设施

| 机器 | 地址 | 角色 |
|---|---|---|
| Mac | 本仓库 | 写代码 |
| H100 | `a25689@10.239.121.25:31126` | 训练、①③ 离线 gate、②④ rollout 客户端 |
| 4090 | `10.229.20.125:41451` | AirSim 渲染器 |

**两个 checkout（H100）**：

- `~/aerial-rl-skeleton` — 旧 checkout，**artifacts / 权重 / 语料** 在这里
- `~/robomaster-tt-control` — 新 clone，代码新、artifacts 空

Gate 命令里的 `--depth-ckpt` / `--dataset` 用 **`~/aerial-rl-skeleton/.../artifacts/` 绝对路径**，不要拷贝。

共享盘 `/home/a25689/aerial_cache_shared/` 存 runs；可拆卸盘上的语料跑 gate 前须 `ls` 确认已挂载。

---

## 6. 待办（V1 → V4）

详见 [V1_GATE_STATUS.md](handover/V1_GATE_STATUS.md) 与 [V1/V4 设计](design/2026-08-15-v1-v4-design.md)。

| 优先级 | 任务 |
|---|---|
| ~~**V1a-1**~~ | ✅ `_wm_train_validate` → `wm_ckpt_v1a_20260815` |
| ~~**V1a-2**~~ | ✅ `kind=torch` + `enable_wm_update=true` + corrector smoke |
| **V1b** | τ + 想象规划 + `DepthTauShield` + `_v1_gate` — **merge PASS（严谨）**；部署 flip FOE yaml 待人工 |
| **P0b** | shield 消费 `predict_cones()`（可选，会改 ④ 行为） |
| **n re-freeze** | ✅ **关闭**（2026-08-17）：frozen `n_eval_episodes=8`（**事后合法化**，非事前干净；合法性轴） |
| **洞 2 ④b 空过** | ✅ **关闭**（2026-08-17）：空过为终态；实证=④c |
| **洞 3 V1-② coll N/A** | ✅ 定义关闭；r60 诊断 + **held-out 20260817** `pos=20` / AUROC 0.977 / usable coll ep=8（`coll_claimed`）；**不改** 08-15 merge |
| **V1-① 功效②③** | ⏳ **待签字**：[提案](handover/V1_SIGNAL1_POWER_REFREEZE_PROPOSAL.md)；脆弱（0.8 局 / McNemar p≈0.5）已记；与 n re-freeze **正交** |
| **V4 判据** | ✅ **已签字冻结（08-20；08-18 立案，历九轮复核）**：[判据 re-freeze 提案](handover/V4_CRITERIA_REFREEZE_PROPOSAL_20260818.md) —— 旧 ① 奖励撞墙 / 旧 ④ 可空过 / ①④ 对抗 ⇒ 改**分层到达**（S_open 不退化 + S_blocked 逼障）+ 新增 ⓪ 近带深度 / ⓿ 想象排序两条前置门；`n` 8→每层 16；**§4.1 阈值不动**。含前提链 P0–P8（P0=R1，**已 DONE**；新增 **P0c** 丢局修复 / **P7-FAIL 下车站**）与流程补丁 **Q1–Q5**（原 P1–P4，改名消歧）。**实施看 §4.6 v2 整合稿 + §4.6.8（第五轮）+ §4.6.9（第六轮）+ §4.6.10（第七轮）+ §4.6.11（第八轮 V0–V5）+ §4.6.12（第九轮 W1–W7）**（前提链 v2 插入 ~~**P3.5** shield v5 回归~~（**第九轮 W2：本周期 N/A**，评测构型 = 现行第 (4) 代 latch）/ **P4.5** 语料重采+WM 重训；P3 扩范围含 **⓪f**；P7 拆 **diag/accept** 两趟，起点集口径 = **`S_diag` ⟂ {`S_accept` ∪ actor gate}** 且 **`S_accept` ≡ `S_gate`**（第九轮 W1 更正原「三者互斥」））。**签字看 §5.0 削减签字表 v3 —— §5 旧表禁止整表签**（会把 `[3.5,5.0]` / `θ=0.10` / shield-on 原稿口径冻回去）；头号阻塞 = **5z（第七轮修订）「in-band = `NOT _breached`（D̂∪τ∪p_coll）∧ `engaged=false`」**，**并列阻塞 = 5al / 5am（第九轮）**。第八轮：U1–U9 已闭合；**第九轮：表扩为 16 行、第八轮「14 行可签」失效**。**✅ 08-20 签字完成（16/16）**：14 行采纳 + `5af`=(a) + `5ag`=(B) + 包内 `5p` 裁定（到达 = `min_t dist ≤ 3.0`、主动终止 out of scope）⇒ **判据 re-freeze 生效**（改阈值须重签）；`enable_policy_update` 未翻；P2 须含 `wm_out` 接线。**标题已改「分层到达；逼障仅当 ⓪f 证出可行带」** |
| **V4** | 判据冻结。**下一步 P4.5**；P3=`insufficient_support`；R-16=(B)。`enable_policy_update` false |

---

## 7. 治理红线

- V0 flags **已翻**；V1/V4 flags **仍 OFF**，各阶段独立 gate
- **不为凑过调 §4.1 阈值**；shield 控制律可改，阈值改需 re-freeze
- 代码走 git，**禁 scp 热补丁**
- 干净重训禁 warm-start 失效 ckpt

---

## 8. 关键资产（H100，不在 git）

| 资产 | 路径 |
|---|---|
| **r60 语料（权威）** | `.../dataset_v0_local_depth_r60_20260814` |
| **r60 深度 ckpt** | `.../depth_ckpt_da3_r60_20260814/` |
| **r60 WM ckpt** | `.../wm_ckpt_r60_20260814/` |
| V0 merge verdict | `.../v0_gate_r60_20260814.json` |
| 头对头 rollout 语料 | `.../dataset_v0_headon_20260811` |
| 历史 head A/B | `depth_ckpt_da3_20260810` / `depth_ckpt_da3_near_20260811`（归档） |

---

## 9. 历史备注：Aug-5 band-median ③ 战役（已 superseded）

2026-08-05~06 曾用旧协议（band-median \(\hat{s}_D = |d_{L-1}-d_0|\) vs \(\|\Delta p\|\)）攻关 ③，结论已归档于原 worktree 的 `signal3_campaign_20260806`（若 H100 已落盘）。要点：

- GT oracle ≈ **0.229**，门槛 0.25 余量仅 0.021
- δ 扫描最好 D̂=0.268（δ=1.6）；增采 d18 **抬高** oracle 至 0.245
- Δ 监督密度（`wm-batch` 32）提升 Spearman，但 ③ 协议已切换至重投影

**当前权威 ③ 以 §4.4 重投影为准**；旧战役仅作踩坑记录，勿与 head B 补跑混淆。

---

## 10. 文档索引

| 文档 | 内容 |
|---|---|
| [RUNBOOK_v0.md](../experiments/aerial/RUNBOOK_v0.md) | 顶层入口 + §8 变更记录 |
| [V0_GATE_STATUS.md](handover/V0_GATE_STATUS.md) | V0 合拢记录（已 PASS） |
| [V1_GATE_STATUS.md](handover/V1_GATE_STATUS.md) | V1 三信号进度 |
| [V1/V4 设计](design/2026-08-15-v1-v4-design.md) | post-V0 阶段设计 |
| [frozen spec](superpowers/specs/2026-08-04-aerial-wam-v2-frozen-spec.md) | 阈值 §4.1 |
| [pure-vision design v2](superpowers/specs/2026-08-03-aerial-wam-pure-vision-design-v2.md) | 架构 |
| [DA3 backbone](handover/2026-08-10-da3-depth-backbone.md) | 深度骨干 |
| [signal3 reprojection](handover/2026-08-10-signal3-reprojection-estimator.md) | ③ 估计器 |
| [sync & env](../experiments/aerial/scripts/RUNBOOK_sync_and_env.md) | 三机同步 |

---

## 11. 本仓库迁移说明

本目录 `/Users/xudazhong/Projects/aerial-wam-v2` 从 `robomaster-tt-control/.claude/worktrees/aerial-rl-skeleton` @ `8a063be` 提取。

**已迁移（整棵 `experiments/aerial/`）**：

- `rl/` — V0 gate、WM 训练、collector、DA3 vendored
- `sim_verify/` — Fork A 前置验证
- `orchestration/` / `eval/` / `collapse_fix/` — B0/B1 编排与评测（v1 线，历史资产）
- `scripts/` — sync/env/renderer + B0/B1/collapse 脚本
- OpenFly 辅助：`convert_openfly_to_lerobot.py`、`path_expert.py`、`takeover.py` 等
- `configs/aerial_rl*.yaml` + V0/B0 相关 docs

**未迁移（刻意留在旧 monorepo）**：FastWAM `src/`、`configs/train.yaml` / libero / robotwin、Tello 真机控制。

H100 上 artifacts 仍指向旧 checkout 路径；后续可将 `sync_pull.sh` 的 remote/branch 指向本仓库新 remote。
