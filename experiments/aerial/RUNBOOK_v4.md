# V4-MVP RUNBOOK（判据 v2，2026-08-20 签字后的干净执行稿）

> **本文件是什么**：V4 的**执行**入口 —— 按序做什么、每步产物是什么、跑前必须先定死什么、必须先实测什么、什么情况下停。
> **本文件不是什么**：不是判据的权威定义源。**判据的唯一权威口径 = [`V4_CRITERIA_REFREEZE_PROPOSAL_20260818.md`](../../docs/handover/V4_CRITERIA_REFREEZE_PROPOSAL_20260818.md) §4.6（含 §4.6.8–§4.6.12）**；签字记录 = 同文件 **§5.0**（16/16 行，2026-08-20）。本文件与 §4.6 有任何不一致 ⇒ **以 §4.6 为准**，并回来改本文件。
> **不得照 §1 / §2 实施**（那是事前预注册记录，已被 §4.5 D1–D4 证明与冻结实现冲突，按审计链保留不改写）。
> **判据已 re-freeze（2026-08-20）**：实施过程中改任何阈值 / band `[lo,hi]` / `n` / primary-secondary 划分 ⇒ 必须回 §5.0 **重开表重签**，不得就地改。
> **⓪ primary 局部 re-freeze（2026-08-24，6ap 12/12）**：[`V4_ZERO_PRIMARY_MIGRATION_REFREEZE_20260824.md`](../../docs/handover/V4_ZERO_PRIMARY_MIGRATION_REFREEZE_20260824.md) —— **⓪h@12.2m 升 primary**、**⓪d@3m 降 report-only**；P3/P4.5 权威合取改为 `⓪a∧⓪b∧⓪c∧⓪h∧⓪e`。与 §4.6.2 ⓪d primary 行冲突时 **以 6ap 为准**。

---

## 0. 一页速览

| | |
|---|---|
| **目标** | 分层到达：`S_open` 不退化 + `S_blocked` 逼障绕行（**「逼障」仅当 ⓪f 证出可行带才入 merge**） |
| **信号** | **V4-⓪**（近带深度）、**V4-⓿**（想象排序一致性）、**V4-①′**（分层到达）、**V4-④′**（安全不回归 + 反空过） |
| **merge** | `⓪ ∧ ⓿ ∧ ①′ ∧ ④′`，其中 `①′ = S_open primary 全过 ∧ S_blocked primary 全过` |
| **n** | 每层 **16**（合计 32）；不足 ⇒ `authoritative=false`，**禁止降 n** |
| **评测构型** | **deploy = `safety.kind: three_zone`**（8/5/1.5 @ 2/1，engage_outer **12.2 m**）。离线 P3 权威 = 同参数 **⓪h** + 老头 RGB-only 深度头（**无 IMU 融合**） |
| **当前状态** | **6ap 已签（2026-08-24）**；**主线 = P4.5 控制臂 hold035 权威 emit**（⓪h primary，⓪d_legacy 只报）。TZ-3Z 并行结案。**P1** coll FAIL；**P4** ⓿e `infeasible`。**`enable_policy_update` = false**。R-16 **(B)**。Supervisor **已停** |
| **主张范围** | 只主张「**不退化 + 安全**」，**不主张「想象 AC 有增益」**；到达能力**仅覆盖机体前向扇区**；「主动终止」**不测** |

**机器分工**（不再逐次确认）：**8×H100** `a25689@10.239.121.25:31126` = 训练 / 数据 / 离线诊断；**4090** `10.229.20.125:41451` = **纯渲染**（gate、探针、planner、闭环 rollout 都在这跑）。

---

## 1. 前提链（**必须按序，不是并行**）

| 步 | 内容 | 跑在哪 | 产物 / 通过条件 | 状态 |
|---|---|---|---|---|
| **P0** | R1 落地（`imagine` aux progress = analytic Δ‖g‖） | H100 + 125 | 校准比值 **1.00 PASS**；① 仍 FAIL（`n=5` 非全权） | ✅ **DONE**（`30b9ff8` / `d96da1d`） |
| **P0c** | **修评测期丢局**（`v4_gate_run_partials.py` 的 `_run_one_resilient` 里 `if ep_on is None: continue` 吞局） | 125 | ①三互斥计数器落盘 `n_invalid_spawn` / `n_none_returned` / `n_pair_broken`；②用**预留 spare 起点**补扫到每层 16（spare 清单与消耗顺序**跑前落盘**，禁临时新采）；③仍不足 ⇒ `authoritative=false` **且必须报三计数器**；④**禁止用降 n 解决** | ✅ **DONE（2026-08-20）** — harness `e28baa9`；正式跑 `v4_gate_p0c_formal_20260820/`（`--target-n 16 --spare-count 16`）。**①**：`n_scored=16` `authoritative=true` spare_consumed=**8** / invalid=**3** / none=**0** / pair_broken=**5**。**④ on**：n=16 auth spare=**7** / inv=**3** / none=**0** / pair=**4**；**④ off**：spare=**9** / inv=**2** / none=**0** / pair=**7**；**④ v1**：spare=**11** / inv=**10** / none=**0** / pair=**1**。旧 actor 上 ①/④ 信号 `ok=False` **不否定** P0c（机制 PASS） |
| **P1** | 在 V4 实际用的 RH 线 WM 上重跑 **V1-②** + 校准子项 | H100 | V1-② 判据。注：「RH 头 forward ratio ∈ [0.8,1.2]」**已降为诊断**（R1 后 actor/aux 不再消费该读出） | ❌ **FAIL（2026-08-20）** — `wm_ckpt_r60_rh_20260816` step=1000，held-out 12/48 尾部，log `artifacts/v4_p1_fidelity_rh_20260820.log`。**按 §1.2.2（`v1_metrics.check_wm_fidelity`）重记**：reward ❌ `beat_frac=0.67 < 0.80`（`growth_ok=True`；**`one_step_ok=True`** — log h=0 行 `wm_mae=0.5817 \| mean-base=0.6508` ⇒ **0.5817 < 0.6508**）／p_coll **`null` N/A**（`coll_traj_pos=1 < 3`，raw AUROC 0.091 **不是**权威 FAIL）／done **PASS 但 vacuous**（`acc=0.994 == majority`）／recon+latent ✅（19.89 ≤ 25.0）。⇒ **FAIL 完全且仅由 reward 支撑**。修复走 **P4.5**（重训后重跑 P1），不跳过<br>**⟶ re-P1（2026-08-21，P4.5 merge 后）：仍 ❌ FAIL，但支撑项已从 reward 换成 coll。** `wm_ckpt_p45_merged_20260821/wm_step_500.pt`，log `logs/v4_p1_p45_merged_20260821.log`。**reward ✅ PASS 且为诚实 held-out** —— `beat_frac=0.93`、`growth_ok=True`、h=0 `0.330 < 0.907` ⇒ `one_step_ok=True`；切分已核：[`_wm_train_validate.py:157`](rl/_wm_train_validate.py) 与 [`_wm_fidelity_eval.py:51-61`](rl/_wm_fidelity_eval.py) 均确定性尾部、注释互锁（"MUST match"）、两处同 `0.25` ✅。**⚠️ 但 `0.67 → 0.93` 不得全记为 WM 变好**：`mean-base` 同时 `0.6508 → 0.907`（**基线变松本身更易打**）⇒ 须落盘逐 horizon `wm_mae` vs base 曲线才能分离（现无）。**`p_coll` 首次可判 ⇒ ❌ FAIL 成立**：`coll_traj_pos=3` 正好达已签 `coll_traj_min_for_auroc=3`，`AUROC=0.549 < 0.65`（**≈随机**）。**功效登记（不对称，须遵守）**：`pos=3` 功效极低 ⇒ **只反对将来宣 PASS、不反对现在这个 FAIL**；**明文登记：将来若在 `pos=3` 上得到 PASS，该 PASS 不可采。** `done` 仍 **vacuous**；`latent_norm_max=21.85 ≤ 25` ✅ |
| **P2** | **`p_coll` 复活** | H100 + 125 | 头 AUROC 达标 **不足以**收工：**collector 与 V4 gate 都必须以 `should_override(obs, wm_out=…)` 调用**。未接线 ⇒ ⓪f 重跑仍只测 D̂/τ 两通道 | ✅ **接线 DONE（`4e76865`）** — collector/gate 已传 `wm_out`。头侧：P1 上 coll **N/A**（pos<3）；AUROC claimed 仍待合适 held-out / **P4.5** 重训后重证 |
| **P3** | **V4-⓪ v2**（⓪a–⓪f，见 §2.1） | H100 离线 | **⓪f 是 `[lo,hi]` 的唯一合法依据**；P3 不出 ⓪f ⇒ 5ab 分叉无法裁 | ⛔ **`authoritative=false` / `insufficient_support`（2026-08-20）** — 主产物 `artifacts/v4_zero_p3_20260820.json`；补数产物 `artifacts/v4_zero_p3_20260820_bins.json`（48 ep / **6005** frames；近带帧 **95 = 1.6%**）。**⓪b**：`near_px_total=support_px=790055 ≥ 1e4` ✅／`n_frames_with_near_px=95 < 100` ❌／**单帧贡献占比** `max_frame_frac=0.0416 ≤ 0.2` ✅ ⇒ 门未过。**同像素域 ⓪a/⓪c 不可入账**（raw median 0.123、p90 1.38 **不作 PASS/FAIL**）。**⓪c GT 分箱（归因，非判据）**：`(0,1.5]` n=256750 median **0.409** p90 **1.978**；`(1.5,3]` n=533305 median **0.079** p90 **0.380**（坏尾集中在 <1.5 m）。⓪d/⓪e：miss=0；deployment corpus。**⓪f**：`(1)(2)` `(3,8]` median **0.074** / p90 **0.259**；`(3)` D̂ 误触曲线见下表（`[lo,hi]=null`，**非单点 PASS**；diag `lo≈4.5` **非冻结**）；`(4)` 同表 `p_tau_false_trigger` **凡有 `n_tau_cond` 的 bin 均为 0.0**（非汇总 PASS）。δ/`[lo,hi]`/`release_depth_m` **继续锁死**。修 = **P4.5 → 重跑 P3**<br>**⟶ re-P3（2026-08-21，`artifacts/v4_zero_p3_p45_merged_20260821.json`，语料 `dataset_v0_p45_merged_20260821` 77ep / open35:blocked42 ≈ **1:1.2 达标** ✅，深度头 `depth_ckpt_p45_merged_20260821`）：仍 ⛔ 不可发证。逐项按判据重记（≠125 status 表）：**<br>• **⓪b ✅ PASS 成立** —— 近带帧 **315 ≥ 100**、`max_frame_frac=0.024 ≤ 0.2`、px `1.54e6 ≥ 1e4`（support 门与模型精度无关，不受下述 in-sample 影响）。<br>• **⓪a `median=0.144` —— PASS 不可采（in-sample）**；**⓪c `p90=0.792 > 0.50` ❌ FAIL 成立且偏保守**；**⓪d `miss=0.142 > 0.05` ❌ FAIL 成立且偏保守，且 `max_consec_miss=4` 独立违反「不得 ≥2 连续漏触发帧」**（= 2026-08-11 ④ 出 4/7 接触的**同一病根**）；**⓪e ✅**。<br>• **⓪f：125 记「outer p90 `0.504 > 0.50` ⇒ FAIL」= 判错，须改回。** §4.6.2 的 **⓪f(1)(2) 是 report-only，无 0.50 阈值**（`0.50` 属 **⓪c**、像素域 `(0,3.0]` 而非 `(3.0,8.0]`）；**⓪f(3)(4) 因 `[lo,hi]` 未冻仍未判** ⇒ 应记「**(1)(2) 已报；(3)(4) 未判**」。此为**自行加严**（不撞红线）但属**判据外加项 ⇒ 污染审计链**。真正要紧：**outer p90 `0.259 → 0.504`（外带精度变差）**，且**新 `clearance_sweep` 与 ⓪f(3)(4)/`n_tau_cond` 一个未落盘** ⇒ band 可采性无法重算（缺字段 ⇒ 该项 `authoritative=false`）。<br>• **⚠️ 阻塞①：⓪ 是 in-sample 评的。** [`v4_p45_merge_retrain_eval.sh:35`](scripts/v4_p45_merge_retrain_eval.sh) 深度头 `--holdout-frac 0.2` 训在 `$DATA`，`:62` 的 `v4_zero_eval` 吃**整个** `$DATA`，而 [`v4_zero_eval.py:552-559`](rl/v4_zero_eval.py) **无 holdout 参数** ⇒ ~80% 帧是训练帧。读法**不对称：PASS 不可采、FAIL 更硬**。<br>• **⚠️ 阻塞②：一次改了两件事**（语料 **且** 深度头）⇒ **⓪c/⓪d 变化不可归因**；⓪d `0 → 0.142` 两种相反解释分不开：(i) 新头近场过读退化；(ii) **老 `miss=0` 本是低 support 假象**（当时仅 95 近带帧）⇒ 老头也从不安全、V0 ④ 的 PASS 本身低功效。<br>• **⟶ 下一发只跑控制臂**：**老头** `depth_ckpt_da3_r60_20260814/depth_step_2000_da3_ft_head.pt`（本轮 `$INIT_DEPTH`）× **新语料** × 同一 `v4_zero_eval` ⇒ 老头**未见过**新语料 ⇒ **完全 held-out ⇒ 诚实**，且同语料 ⇒ **可归因**。产物 `artifacts/v4_zero_p3_oldhead_merged_20260821.json`。同轮补：**新 `clearance_sweep` 全表 + ⓪f(3)(4) `n_tau_cond`**；并给 `v4_zero_eval` **加 holdout 参数**（改 harness、不改判据 ⇒ 不需签字，但**须在出数前落盘声明**）。<br>• **⚠️ 新深度 ckpt 不得进部署路径**：`⓪d max_consec_miss=4` 即 ④ 病根；换头 ⇒ **V0 ④ 的 08-14 PASS 立即失效**（红线「shield/τ/depth 路径与 V1 部署一致」）⇒ 须重跑 ④。⇒ `depth_ckpt_p45_merged_20260821` 按红线**归档保留、暂不采用**，等能**同时过 ⓪a–⓪d** 的头（双侧夹逼，偏置换不来）。<br>• **⬜ 待 125/人给出处**：`$INIT_DEPTH` = `depth_ckpt_da3_r60_20260814` **是否即 V0 ④ 实际过 gate 的头**？红线禁 warm-start 失效 ckpt；「深度头一致性缺口」（`da3_20260810` / `da3_near_20260811` / canonical `depth_step_5000.pt`）仍未结。**若属失效 ckpt，本轮 depth FT 整轮作废。**<br>• **⬜ τ 未动**：`tau_ckpt_foe_r60_20260815` 仍在**旧语料**上校准、评测语料已换 ⇒ τ 现**分布外**，且本轮 ⓪f(4) 一个数未报 ⇒ 控制臂同轮补报<br>**⟶ 控制臂已跑（2026-08-21，`artifacts/v4_zero_p3_oldhead_merged_20260821.json`，老头 × 新语料）：二义性拆开，且拿到 ⓪ 的第一个权威 FAIL。**<br>• **三点分解**：老头×**旧**语料 `⓪d miss=0 / consec=0`（近带帧仅 95 ⇒ 低 support）→ 老头×**新**语料 `miss=**0.076** / consec=**2**`（**完全 held-out ⇒ 权威**；老头训于 08-14 r60 语料、新语料全采于 08-20/21 ⇒ 无重叠）→ 新 FT 头×新语料 `miss=**0.142** / consec=**4**`（in-sample）。⇒ **语料效应 `0→0.076`：老 `miss=0` 确系低 support 假象**；**FT 效应 `0.076→0.142`：FT 确系退化（约翻倍）**。⓪c 同向：老头 `p90=0.72` < 新头 `0.79`，**两臂均 FAIL**（>0.50）。<br>• **⇒ ⓪ 的第一个权威 FAIL**（非 `insufficient_support`、非 in-sample）：**部署线上的头** ⓪d 不过。按 **R-16 (B)**：不停跑，但 **P8 在 ⓪ 权威重过为 PASS 前 blocked**。<br>• **⇒ 连带：V0 ④ 的 PASS 判为低功效假象，须重新入列**（审计链：加 supersede 注记、不改写原文）。④ 于 08-14 过 gate 用的正是这个头、`n=16`；今在有功效的近带语料上该头 `miss=0.076 / consec=2` ⇒ **④ 的 PASS 无法在有功效条件下存活 ⇒ 须重跑**（无论最终采用哪个头）。<br>• **FAIL 的稳固支点 = `consec` 条款**（不依赖分母；老头 `2`、新头 `4` 均直接违反「不得 ≥2 连续」）。速率腿 `0.076` 的**分母 `n_near_forward_frames` 两臂都未落盘** ⇒ 若分母仅数十，95% CI 下界会掉破 0.05 ⇒ 单独不够硬。**须补该分母**；且「`≤0.05` 按点估计还是 95% 上界」与 **§3 #17 是同一欠规范 ⇒ ⓪d 一并定**。<br>• **⚠️ `809cde6` 的 ⓪f 修法有一处风险**：「**primary = ⓪a–e**」**不得读成「⓪f(3)(4) 降为只报」** —— ⓪f(1)(2) report-only 已改对，但 **⓪f(3)(4) 带 `≤0.05` 阈值、且本行写死「⓪f 是 `[lo,hi]` 的唯一合法依据」**；整项降 secondary 会 ① 抽掉 band 唯一依据、② 属**看到数后**降级 = 放松 ⇒ 须签字、③ §3 #7 本登记为**跑前**写死。⇒ 应记「**⓪f(1)(2)=report-only；⓪f(3)(4) 仍为判据，现状「未判（band 未冻）」**」。<br>• **⇒ 改训练目标的依据由预测转实测**（前述「收回」的触发条件已满足）：同跑内 **全 mask holdout AbsRel `0.113`（好）** 与 **⓪c `0.79` / ⓪d `0.142`（坏）** 并存。且 **⓪d 判 `D̂_forward`（按定义即前向）⇒ L0 argmin 归因对 ⓪d 不适用、无 shield 管线退路 ⇒ 只能修感知**。对症（对齐判据、对 ①d 中性）：**⓪d ⇒ 近前向单侧 hinge，只罚 `D̂ > GT`**（现 `near_weight=3.0/near_focus_m=5.0` 是**对称均值**，管不住单侧）；**⓪c ⇒ 分位/pinball/尾部加权**；**`consec` ⇒ 时序性质，单帧 loss 管不了**，需时序平滑或触发侧滞回（后者属 shield 控制律、允许改）。三条须**跑前落盘声明**且**在 held-out 上验** ⇒ **`v4_zero_eval` 的 holdout 参数仍缺 = 硬前置**。<br>• **⬜ 控制臂须补全（唯一诚实的一臂）**：缺 **⓪a / ⓪e / ⓪f(1)(2)(3)(4) / `clearance_sweep` 全表 / `n_tau_cond` / `n_near_forward_frames`**。**全套 ⓪ 权威数字应出自此臂**，新 FT 头臂只作对照。不用重飞、只重跑 eval。<br>• **⬜ ⓪e 须加注**：语料含**刻意近带富集** + approach-bias ⇒ 严格已非部署分布，两臂记 PASS 属默认成立。**判定：不影响 ⓪c/⓪d 的 FAIL**（皆为条件统计量，富集改 support 不改条件率；且 V4 部署场景本就是逼障头向）⇒ **此处取不到宽免** |
| **P3.5** | ~~shield v5 回归验证~~ | — | **本周期 N/A**（5am / W2：v5 降 fallback，「不动 shield」）。`release_step[]` / `n_release` 仍落盘、无 v5 时恒 0 | 🚫 **N/A** |
| **P4** | **V4-⓿ v2**（想象排序一致性） | H100 + 125 | 含 ⓿d（真实侧 G 写死 = analytic）、⓿e（**teleport 能否复现同一 `z0` 须先实测**） | ⚠️ **已跑但须重跑（2026-08-20）** — `v4_rho_p4_20260820.json`：⓿a–d PASS（ρ median **0.963**）；**⓿e FAIL**（teleport `median_rel_l2=1.37`）。在 P3/`P1` 未过且 P4.5 将换 WM 时跑的 ⓿ **不得当证书** ⇒ **P4.5 后重跑 P4**。<br>**⚠️ 更正（同日，待 5an 一并裁）**：**⓿e 与 ⓪b 同型 = 可行性前置，不是精度判据** —— §4.6.5 `:613` 驱动 C4 原文「**不支持则 ⓿ 现写法不可实现**」；⓿ 的构造要求「同一 `z0` 出发、K 条动作序列比想象 vs 真实排序」⇒ 真实侧必须从同一 `z0` **重新执行 K 次** ⇒ 必须精确状态重置。`median_rel_l2=1.37` ⇒ 真实侧并非从想象的 `z0` 出发 ⇒ **⓿a–d 的 ρ=0.963 不可入账**，记 **`infeasible`**（非「⓿ FAIL」）。**且 teleport 属 harness / AirSim 能力，P4.5 换 WM 修不好** ⇒ **P4 的真前置是 ⓿e 修复，与 P4.5 正交、可并行**；不得用「P4.5 后重跑 P4」代替（否则重跑撞同一个 ⓿e） |
| **P4.5** | 语料重采（`S_open : S_blocked ≈ 1:1`，**须抬高近带帧占比**）+ WM 重训 ⇒ **重跑 P3 / P1 / P4** | H100 + 125 | 否则 P1/P3/P4 给注定被替换的 WM 发证 | 🟡 **已跑一轮（2026-08-21）：语料达标 ✅、reward 修好 ✅、⓪ 仍不可发证** —— 语料 `dataset_v0_p45_merged_20260821`（77ep，open35:blocked42 **≈1:1.2 达标**、近带帧 95→**315**）；depth FT + WM(500 步) + re-P3 + re-P1 见 P1 / P3 行。**未完**：⓪c/⓪d FAIL、⓪a 不可采（in-sample）、⓪f 落盘缺项、`p_coll` FAIL。**下一发 = 控制臂（老头 × 新语料），不是再治深度头** |
| **P5** | shield 触发深度 3.0 → 2.0 裁定 | — | **暂缓**；G1 之后其两个理由都失效 ⇒ **很可能完全不必要**；方向也可能相反（由撞点落盘裁定） | ⏸ |
| **P6** | `planner.action_limits` 夹到 `body_delta_limits(1/step_hz)` | 代码 | 现默认 `None` | ✅ **DONE（`4e76865`）** — `_build_planner` 设 `action_limits = body_delta_limits(1/step_hz)` |
| **P7-diag** | planner 纯前向跑 **诊断起点集 `S_diag`** | 125 | **只落盘不判**：逐步 `clearance_fov` ⇒ 得 `C_P7` 分布；判据里 `θ := undefined` | ⬜ |
| **⟶ 冻结** | 先冻 **`[lo,hi]`**（⓪f ∧ `hi ≤ Q_0.25(C_P7)` ∧ `hi ≤ 8 m`）**加时间戳** ⇒ 再在**同一份逐步 log** 上算 `band_frac` ⇒ 冻 **`θ = 0.8 × median_P7`**、冻 **`k`** | 离线 | **不必再飞**。**禁止**「看到 `band_frac` 分布后再改 `hi`」 | ⬜ |
| **P7-accept** | planner 在 **`S_accept`** 上跑 **§4.6.3 全判据**（此时 θ 已是外生常数） | 125 | `S_diag` ⟂ `{S_accept ∪ actor gate}`；**`S_accept` ≡ `S_gate`**（actor 必须飞同一批起点） | ⬜ |
| **⟶ 下车站** | **P7-accept 在 S_blocked FAIL ⇒ 停** | — | 见 §6 | — |
| **P8** | 才训 actor（**从零，禁 warm-start**）⇒ gate ①′ / ④′ | H100 训 + 125 gate | `enable_policy_update` 仍**由四信号全过前不翻** | ⬜ |

---

## 2. 判据（执行口径，权威定义见 §4.6）

### 2.1 V4-⓪ 近带深度（P3）

> **6ap（2026-08-24）**：merge primary 功能项 = **⓪h**（三线 engage_outer）；**⓪d@3m = `0d_legacy` report-only**。传感器栈 = **RGB 四帧单目**（IMU **不进**深度头）。完整签字 = [`V4_ZERO_PRIMARY_MIGRATION_REFREEZE_20260824.md`](../../docs/handover/V4_ZERO_PRIMARY_MIGRATION_REFREEZE_20260824.md)。

**P3 primary 合取**：

```text
⓪_ok ⟺ ⓪a ∧ ⓪b ∧ ⓪c ∧ ⓪h ∧ ⓪e
```

| 子项 | PASS | 备注 |
|---|---|---|
| ⓪a | `median AbsRel ≤ 0.30` on `D_gt ∈ (0, 3.0]` | 不动 |
| ⓪b | support ≥ 1e4 px **且** `n_frames_with_near_px ≥ 100`、单帧贡献占比 ≤ 0.2 | **support 门**（非精度判据）：未过 ⇒ 近带 ⓪a/⓪c **不可入账**，记 `insufficient_support`，**不是 ⓪ FAIL** |
| ⓪c | `p90 AbsRel ≤ 0.50`（同像素域） | median 允许一半像素任意坏 |
| **⓪h（primary 功能项）** | `P(D̂_fwd > engage_outer \| D_gt_fwd ≤ engage_outer) ≤ 0.10`，**且** `max_consecutive_miss < 4` | `engage_outer` = **12.2 m**（`three_zone` 8/5/1.5 @ 2/1）；几何 = **前向锥** `D̂_fwd` |
| **⓪d_legacy（report-only）** | 同旧 ⓪d：`P(D̂_fwd > 3.0 \| D_gt_fwd ≤ 3.0) ≤ 0.05`，`max_consecutive_miss < 2` | **不入 merge**；禁止仅为过此项 depth FT |
| ⓪e | 测试分布 = **部署分布**（评测起点集实际帧），不得只用训练 holdout | |
| **⓪f** | 在 **`D_gt ∈ (3.0, 8.0]`** 上报：`median AbsRel`、`p90 AbsRel`；**(3)(4) 误触发**在 `[lo,hi]` 冻结前 **report-only** | **⓪f 出数前 `[lo,hi]` 一律不填数**；⓪f(3)@3m latch **不作 deploy primary** |

**禁止**：仅为过 **⓪d_legacy** 开 depth loss FT 或换部署头。⓪h FAIL ⇒ R-16 **(B)** 下车站；传感器栈变更须 **另案 re-freeze**。

**权威控制臂（P4.5 / P3 下一发）**：老头 `depth_ckpt_da3_r60_20260814` × `dataset_v0_p45_merged_20260821` × **hold035**（`--heldout-frac 0.35 --split-seed 0`）→ `artifacts/v4_zero_p3_oldhead_p45_hold035_20260824.json`。

P5 若改 `min_depth_m` ⇒ **⓪d_legacy 与 ⓪f(3)** 须按新 trigger 重测（与 deploy `three_zone` 无耦合，仅 legacy 对照）。

**P3 补数表 · ⓪f(3)/(4) `clearance_sweep`（0.25 m bin；源 `v4_zero_p3_20260820_bins.json`）** — 仅诊断；**不得**据此冻 `[lo,hi]`：

| clearance | n | n_τ | p(D̂ 误触) | p(τ 误触) |
|---|---:|---:|---:|---:|
| [3.00, 3.25) | 11 | 3 | 0.727 | 0.000 |
| [3.25, 3.50) | 45 | 7 | 0.578 | 0.000 |
| [3.50, 3.75) | 10 | 5 | 0.600 | 0.000 |
| [3.75, 4.00) | 12 | 1 | 0.167 | 0.000 |
| [4.00, 4.25) | 12 | 6 | 0.250 | 0.000 |
| [4.25, 4.50) | 4 | — | 0.000 | — |
| [4.50, 4.75) | 8 | 1 | 0.000 | 0.000 |
| [4.75, 5.00) | 18 | 4 | 0.111 | 0.000 |
| [5.00, 5.25) | 12 | 4 | 0.083 | 0.000 |
| [5.25, 5.50) | 17 | 5 | 0.059 | 0.000 |
| [5.50, 5.75) | 16 | 3 | 0.125 | 0.000 |
| [5.75, 6.00) | 17 | 9 | 0.000 | 0.000 |
| [6.00, 6.25) | 25 | 19 | 0.000 | 0.000 |
| [6.25, 6.50) | 13 | 3 | 0.000 | 0.000 |
| [6.50, 6.75) | 11 | 4 | 0.000 | 0.000 |
| [6.75, 7.00) | 9 | 4 | 0.000 | 0.000 |
| [7.00, 7.25) | 16 | 11 | 0.000 | 0.000 |
| [7.25, 7.50) | 22 | 15 | 0.000 | 0.000 |
| [7.50, 7.75) | 17 | 11 | 0.000 | 0.000 |
| [7.75, 8.00) | 18 | 16 | 0.167 | 0.000 |

全域：`n = 313`、`n_τ = 131`（两者 ≥ 100 ⇒ 汇总 support 够；**逐带另算，见下**）。

**⓪f(3) 逐 1.5 m 候选带累加（离线推导，源同上表；仅供冻结时读，不得跳过 §1「⟶ 冻结」流程）**：

| lo | n | 误触 | p̂ | 判（`≤ 0.05`） | n_τ |
|---|---:|---:|---:|---|---:|
| 3.00 | 94 | 45 | 0.479 | ✗ | 22 |
| 4.00 | 71 | 7 | 0.099 | ✗ | 20 |
| **4.50** | 88 | 6 | **0.068** | ✗ ← diag 建议的 `lo≈4.5` **过不了** | 26 |
| 4.75 | 105 | 6 | 0.057 | ✗ | 44 |
| **5.00** | 100 | 4 | **0.040** | ✓ **最低可采（点估计）** | 43 |
| 5.25 | 99 | 3 | 0.030 | ✓ | 43 |
| 5.50 | 91 | 2 | 0.022 | ✓ | 42 |
| **5.75** | 91 | **0** | **0.000** | ✓ **最低 95% 置信可采**（rule-of-three 上界 **0.033**） | 50 |
| 6.00 | 96 | 0 | 0.000 | ✓（上界 0.031） | 56 |
| 6.50 | 93 | 3 | 0.032 | ✓（点估计；受 `[7.75,8.00)` 异常拖累） | 61 |

⇒ **`lo ≥ 5.00`（点估计）/ `lo ≥ 5.75`（95% 置信）**；**`hi ≤ 7.75`**（`[7.75,8.00)` 的 `p=0.167` 打破单调，疑域边界 / 天空混淆）。**仍不冻结**，等 §1「⟶ 冻结」流程 + `hi ≤ Q_0.25(C_P7)`。

**⚠️ 两条派生结论（`5an` 一并裁）**：

1. **`⓪f(1)(2)` PASS 不保证 `(3)` PASS，机制已定量**：shield 用**全 FOV 最小值**（`depth_predictor.py:81-90`），故 `p90 = 0.259` 的尾巴足以把 3.2 m 读成 2.4 m ⇒ **`3–5 m` 净空走廊逐步误触发率 = 47/120 = `0.392`**。配 latch 罩（`5am(d)`：一次触发即整局报废）⇒ 穿越 k 步不被触发概率：`k=2 → 0.370`、`k=3 → 0.225`、`k=5 → 0.083`、`k=10 → 0.007`。**「逼障绕行」必须穿过这条走廊** ⇒ **预测（非已测事实）P7-accept 在 `S_blocked` FAIL** ⇒ 走 `5ai` 下车站，其写死的合法反应 = **退回感知侧**。禁三种反应照旧。<br>~~**P4.5 必须含 depth head 在 3–5 m 区的重训，不能只做语料 1:1 重采**~~ ⇒ **2026-08-21 收回（顺序错）**：⓪ 现无任一子项判成 FAIL（⓪a/⓪c `insufficient_support`、**⓪f(3) 因 `[lo,hi]` 未冻而尚未判**、⓪d PASS）⇒ 以「预测会 FAIL」为依据提前重训感知侧，正是 5ai 想防的反向操作（5ai 的退回是 **FAIL 之后**的合法反应，不是 FAIL 之前的预防动作）。**正确顺序 = P4.5 补语料 → re-P3 出 authoritative ⓪ → 若 ⓪c 真 FAIL → 才动 depth head。** 现阶段只做**诊断不做修**，见下 (5)。
2. **`⓪f` 与 `C_P7` 方向相反、可能交成空集**：⓪f 把 `lo` 顶到 ≥5.0，`hi ≤ Q_0.25(C_P7)` 把 `hi` 往下压。⇒ **P7-diag 产物第一眼就看 `Q_0.25(C_P7)` 是否 ≥ 6.5**；否则 `[lo,hi]` = **空集** ⇒ ①′d-b **不可执行**（触发 5ab 分叉 / 下车站讨论）。
3. **主张收窄（不改阈值，如实登记）**：band 落在 5.0–6.5 m ⇒ 「**逼障（贴障绕行）**」实际是「**维持 5–6.5 m 净空绕行**」。按 `5af(a)` 同例登记范围收窄，**不得继续用「贴障」表述**。
4. **落盘小项**：`[4.25,4.50)` 的 `n_τ` 记为 `—`，按 §5 契约应记 `n_tau_cond=0`（缺字段 ⇒ `authoritative=false`）。
5. **L0 归因（2026-08-21 新增；诊断，不动任何被测对象 / 阈值 ⇒ 现在就能做）**：`predict_min`（[`depth_predictor.py:80-88`](rl/depth_predictor.py)）返回的是**整张图的单像素最小值**（`np.min(finite)`，**无方向筛选**）⇒ 拉响 shield 的那个像素**未必是前方障碍**，可能是**下方地面 / 侧壁**。⇒ **须先落盘那 47 次误触发步的 argmin 像素坐标及其 cone 归属**（`predict_cones` 的 forward/left/right/up/down）。**若 argmin 落在 down/side** ⇒ `0.392` 与 depth head 精度**无关**，是 **shield 消费口径问题（P0b：改读 `predict_cones()['forward']`）**，不需重训；**若落在 forward** ⇒ 才是近场精度问题。**此为假设，须实测**；在归因出来之前不得据 `0.392` 推断 depth head 需重训。
6. **⓪ 与 V0 ①d 判的不是同一个量（回答「深度头不是已经 pass 了吗」）**：V0 ①d = **全 mask** AbsRel（`max_depth_m=200`；[`dynamics_torch.py:649-650`](rl/dynamics_torch.py) docstring 自陈近带项「does NOT change the ①d gate metric ... over the full mask」）；V4 ⓪a/⓪c **限死 `(0,3.0]`**，⓪f(3)/(4) 判的是**全图 min 的误触发率**（V0 无此量）。近带帧仅占 **1.6%** ⇒ 在全 mask 均值里被稀释 ⇒ **①d PASS 与 ⓪ 存疑不冲突**（⓪f 当初就是为此而立）。但**也不等于 ⓪ 已 FAIL**，见 (3) 的收回注记。

### 2.2 V4-⓿ 想象排序一致性（P4）

`⓿a/b/c`：Spearman ρ median ≥ 0.50（`n_z0 ≥ 8`）、top-1 ≥ 0.50、**禁 Pearson、禁混 horizon**。
`⓿d`：**真实侧 G 写死 = analytic（纯位置几何）**，想象侧 = 模型自身。
`⓿e`：`z0` 来源 + **AirSim teleport 能否复现同一 `z0` 必须先实测**，不能假设。

### 2.3 V4-①′ 分层到达（P7 / P8）

**起点池**：用 `candidate_positions`（真实 rollout 位姿 + teleport 询问），**不用** `make_start_episodes`。
**准入只有两条**：`start_clearance_m ≥ 3.0` 实测通过；非 spawn-in-collision。**层标签只由探针给**（不做深度窗准入）。
**到达定义（已签死）**：`arrival ⟺ min_t dist(p_t, g) ≤ 3.0 m`（曾进入 3 m 球即算，离线由落盘位姿算）。**不改 rollout 控制流**（`max_steps` 跑满），路径长在**首次到达步 `T_arr`** 截断。

| 子项 | 层 | PASS |
|---|---|---|
| ①′a-o | S_open | `arrival_rate_actor ≥ 0.875` |
| ①′b-o | S_open | `median path_efficiency ≥ 0.90`，`path_efficiency = (‖g−p₀‖ − 3.0) / Σ_{t<T_arr}‖Δp_t‖` |
| ①′c-o | S_open | `hard_coll_rate_actor = 0` |
| ①′a-b | S_blocked | `arrival_rate_actor ≥ 0.50` |
| ①′b-b | S_blocked | **改为「分层器确定性自检」**：同起点重复探针 `R ≥ 3` 次标签一致率 **= 1.0**；不成立 ⇒ **gate 作废（harness 病）**，不是 actor FAIL。原「`arrival_rate_heuristic = 0`」降为构造性事实、只落盘 |
| ①′c-b | S_blocked | `median path_efficiency ≥ 0.70`（同上分子/截断口径） |
| ①′d-b | S_blocked | `median band_frac ≥ θ`；**primary / secondary 由 5ab 跑前分叉决定**（见 §3） |

**in-band 判定（`_breached` 逐字展开，缺一不可）** —— 一步计入 band **当且仅当**：
1. `D̂_fovmin ≥ 3.0` **∧** `τ̂ ≥ 1.0` **∧** `p_coll ≤ 0.5`（= `NOT _breached(step)`），**且**
2. `engaged == false`，**且**
3. `clearance_fov ∈ [lo, hi]`。

> 条件 1 与 2 是**合取不是替代**：`engaged=false` 只排除已 latch 的步，「本步刚破尚未 latch」仍会被误计入。

**band 是速度条件的**：在 clearance `d` 处不被接管要求 `v_fwd ≤ d / min_tau_s`（1.0 s）⇒ **「逼障」的可证明含义 = 「减速贴障通过」，不是高速贴障**；合格域定义在 `(clearance, v_fwd)` 联合平面上并跑前冻结。
**`clearance_fov` 定义**：离线位姿回放，取**整幅 GT 深度图的 min**（与 `depth_predictor.predict_min` 同几何，**不引入 FOV 外方位**）；`cone_clearances` 五向只作诊断。
**`band_frac` 两版都预注册、primary 取更严者**：(a) **进展加权**（一步入 band 还须在 `k` 步窗口内 `dist(p,g)` 严格下降）；(b) **路径长加权** `band_path_len / total_path_len`。旧的纯时间占比 `frac_steps_in_band` **降为诊断**。
**band 分母**：只计 `engaged=false` 且属到达局的步；接管步单独落盘。
**公共子集 `P`** = **P7 planner 到达的 start**（跑前确定、与被测策略无关），`P ⊆ S_accept` ⇒ **actor 的 gate 起点集必须 = `S_accept`**。`s ∈ P` 但 actor 未到达 ⇒ `path_efficiency := 0`、`frac_steps_in_band := 0` **计入 median**（不剔除、不 NaN）；要求 **`|P| ≥ 8`**，否则 ①′c-b/①′d-b 记 `authoritative=false`。
**诊断（不入 merge）**：`path_efficiency_heuristic`（shield-**off**，应 ≈1.0）+ shield-**on** 同项（= 经验效率上界兼罩过敏判别）；累计 yaw 转角（原地转 yaw 不被 `path_efficiency` 罚，只被 `max_steps` 约束）。
**盲对照臂（入报告不入 merge）**：用**时序打乱 / 错配帧**（**不用置零图** —— 那是 OOD）。三分支判读：① 盲臂 S_open 过 / S_blocked FAIL ⇒ gate 依赖视觉；② 两层都过 ⇒ **gate 与视觉无关，结论作废**；③ 两层都 FAIL ⇒ **inconclusive**，不得当作「依赖视觉」的证据。

### 2.4 V4-④′ 安全不回归 + 反空过（P8）

**只在 S_blocked 判**（S_open 的安全由 ①′c-o 承担）。

| 子项 | PASS |
|---|---|
| ④′a | `hard_coll_rate_on = 0` |
| ④′b | `near_coll_rate_on / near_coll_rate_off ≤ 0.80`（**`1.5 m` 与 `0.80` 一字不动**）；**可解释前提**：落盘两臂总步数 + 命中数 + 每局步数直方图，预注册「ratio 只在两臂步数量级可比时可解释」 |
| ④′c | 定义**遭遇机会** `K_off = #{steps: 前向 GT 深度 < 3.0 m, off 臂}`。`K_off ≥ 5` 且 `near_coll_rate_off == 0` ⇒ 记 **`N/A` 不入 merge（不是 FAIL）**；`K_off < 5` ⇒ 记 `vacuous` 不入 merge，**重跑有条件**：仅当 ①′a-b PASS 才重采起点补遭遇机会；①′a-b FAIL ⇒ gate 已 FAIL，**不重跑** |
| ④′d | 旧 ④b（接触前干预 ≥ 0.50）；`n_contact = 0` ⇒ N/A（洞 2 口径不动） |
| 诊断 | shield-**off** 臂 `hard_coll_rate` 随训练下降（④′ 现口径测的是**罩**不是策略，E2） |
| V1 对照臂 | **正式移除**，登记为已知代价 |

---

## 3. 【跑前必须先判断 / 先冻结】—— 不定完不许开跑

> 纪律：下列每一项都必须**在看到相应数据之前**定死并**加时间戳落盘**。事后定 = p-hacking = 撞红线。
> 已签字的部分不得再动；标 ⬜ 的是**填空**（只许按已签公式机械填、只许缩窄），不是重新裁定。

| # | 要定的东西 | 谁定 / 怎么定 | 依赖 | 状态 |
|---|---|---|---|---|
| 1 | **`[lo, hi]`**（逼障带） | `lo = min_depth_m + δ`，`δ` = 「D̂ 与 τ 误触发率**均 ≤ 0.05**」的最小 clearance；宽度 1.5 m；`hi ≤ Q_0.25(C_P7)` **且** `hi ≤ 8 m`（后者**如实登记为拍的**，只与 ⓪f support 上界对齐） | **⓪f**（P3）+ **P7-diag** | ⬜ 待实测填 |
| 2 | **`θ`**（band 占用阈值） | `θ = 0.8 × median(band_frac_P7-diag)`，裕度系数 **0.8 已冻结**；**在已冻的 `[lo,hi]` 上、用同一份 P7-diag 逐步 log 算**（不必再飞）。若重导值 **< 0.10 ⇒ 属放松 ⇒ 须单独签字**，不得静默采用 | P7-diag（须先冻 `[lo,hi]`） | ⬜ 待实测填 |
| 3 | **`k`**（进展窗口） | 与 C1「进带前 k 步」的 `k` **是否同一个数未定 ⇒ 跑前必须一并冻结** | 无（人定） | ⬜ **待定，两处同时冻** |
| 4 | **`Q_0.25(C_P7)`** | `C_P7` = P7-diag 中 planner 在 S_blocked **实际经过的 clearance 分布**；分位 `p = 0.25` **已冻结** | P7-diag | ⬜ 待实测填 |
| 5 | **5ab 分叉：①′d-b 是 primary 还是 secondary** | ⓪f + τ 误触发出数后：**存在**同时满足「并集非介入」与「`hi ≤ Q_0.25(C_P7)`」的带 ⇒ 冻结该带、①′d-b **保持 primary**；**不存在** ⇒ **降 secondary（只报不入 merge）**，机制主张全部落到 **⓿ + P7** | ⓪f | ✅ **分叉规则已签死**（分支由数据选，不是人事后选） |
| 6 | **band 冻结的时序 vs P2** | 正式冻结**排在 P2 之后**；若为进度先用 P2 前的数 ⇒ 必须写 `band_frozen_before_p2 = true` 并标该带 **conditional**，P2 落地后**强制重跑 ⓪f + 重裁 5ab**，且**只许缩窄** | P2 | ✅ 规则已签；**走哪条须跑前声明** |
| 7 | **primary / secondary 划分** | 15 条全 AND ⇒ 误 FAIL ≈54% ⇒ 必须显式分开，**primary 条数跑前冻结** | 无 | ⬜ **待写死清单** |
| 8 | **OC 曲线 + seed 数 + 「两 seed 不一致」的裁决规则** | 每条判据**跑前**落盘 OC 曲线；预注册 seed 数与裁决规则；声明 primary/secondary | 需起点几何独立性成立 | ⬜ **待做** |
| 9 | **起点几何独立性下限** | 落盘起点两两最小间距；预注册下限 **≥ 10 m**；不满足 ⇒ 二项功效计算无效 ⇒ **重采起点** | 无 | ✅ 数值已提；⬜ 待实测校验 |
| 10 | **三个起点集的关系** | `S_diag` ⟂ `{S_accept ∪ actor gate}`；**`S_accept` ≡ `S_gate`**；训练起点集与三者**全部互斥**（seed / 场景区域显式互斥并落盘）。任何重叠 ⇒ `θ` 记 `authoritative=false` | 无 | ✅ **已签死** |
| 11 | **spare 起点清单与消耗顺序** | 跑前从同一起点池多采并落盘；**禁止临时新采**。**spare 池大小**：对 `target_n=16`，**`--spare-count=16`**（选项 1 固定缓冲；2026-08-20 人签） | 无 | ✅ **已定**（`--spare-count=16`） |
| 12 | **冻结清单** | 到达半径 3.0、`max_steps`、时间预算、`cruise_alt_m`、`goal_dist_m = 30`、**候选起点池来源（哪个 rollout dataset）**、探针参数。**v5 三参数（`release_depth_m`/`M`/上限）本周期不进冻结清单** | 无 | ⬜ **待逐项写死数值/出处** |
| 13 | **分层器重复次数 `R`** | `R ≥ 3`（含变 env seed / 渲染随机性），一致率必须 = 1.0 | 无 | ✅ 已定 |
| 14 | **`Δ`（5ag 非劣裕度）** | `Δ = 0` **已冻结在案**；因签 **5ag(B)** 本周期**无适用对象**，日后 V5 另案启用时**不得届时另议 `Δ`** | 无 | ✅ 已冻结（暂不适用） |
| 15 | **盲对照臂的打乱方式** | 同 episode 内随机换帧，或换用另一 start 的帧流；**不得用置零图** | 无 | ✅ 口径已定；⬜ 实现待定 |
| 16 | **到达定义** | `min_t dist(p_t, g) ≤ 3.0 m`，**不改 rollout 控制流** | 无 | ✅ **已签死** |
| **17** | **⓪f(3) / ⓪d 的 `≤ 0.05` 按点估计还是 95% 置信上界判** | **人定，须签字**（挂 `5an` 附带欠规范①）。实测差别（⓪f）：最低可采 `lo` = **5.00**（点估计 0.040）vs **5.75**（0/91，rule-of-three 上界 0.033）。**⓪d 同欠规范**：控制臂 `p_miss=0.076` 的分母 `n_near_forward_frames` 须落盘；若分母仅数十，CI 下界可掉到 0.05 以下 ⇒ **速率腿单独不够硬**（稳固支点仍是 `consec≥2`）。**冻结规则原文只写阈值、未写点估计 vs CI** ⇒ 看到数后再选 = p-hacking。**⚠️ 2026-08-21 新算术：本项现在决定「下一步是重训还是补语料」** —— 若按 95% 上界判，rule-of-three 要求主表 **`n_fwd ≥ 60` 且 0 miss**（3/60 = 0.050）；**现主表 `n_fwd = 35` ⇒ 即便 0 miss 上界也是 0.086 > 0.05 ⇒ ⓪d rate 腿在当前 holdout 上「结构性不可能过」**。全库 106（0 miss 上界 0.028；1 miss ≈0.047）够，**但对 FT 头 in-sample 不可采** ⇒ 唯一出路是把语料做大到全库 `n_fwd ≳ 170`（0.35 holdout ⇒ 主表 ≈60）。现 77 ep / 106 帧 ≈ 1.4 帧/ep ⇒ 需 **再补 ~45 ep approach-bias**（若补采提高每 ep 近前向密度则更少） | 无（已有数；`n_near_forward_frames` 键已加） | ⬜ **待签 —— 现为最高优先，堵住 v4 全部下游动作**，且 **#1 的 `lo` 不定完本项不许填** |
| **18** | **⓪f(4)（τ 项）逐带 support 门** | **人定，须签字**（挂 `5an` 附带欠规范②）。实测逐候选带 `n_τ` 仅 **42–50** ⇒ 上界 3/43 = **0.070 > 0.05** ⇒ **τ 项在候选带上不可判**；仅 `(3,8]` 全域（`n_τ=131`, FT=0, 上界 0.023）够，**但判据条件是 `D_gt ∈ [lo,hi]` 不是全域**。禁止：加宽带宽凑 support（1.5 m 已冻）、换成全域、因难达而回退 | 无（已有数） | ⬜ **待签**；在此之前 ⓪f(4) 只能记「**未见误触，但逐带 support 不足**」 |
| **19** | **depth 训 holdout 与 ⓪ eval holdout 是两个不同集合** | **事实错误、须改代码**（不需签字：改 harness 不改判据）。[`train_depth_head.py:159-178`](rl/train_depth_head.py) `_split_train_holdout` = **seeded permutation**（`--split-seed` 默认 0）；[`v4_zero_eval.py:311-337`](rl/v4_zero_eval.py) `_heldout_episodes` = **确定性尾切**。⇒ 期望重叠仅 16×16/77 ≈ **3.3/16 ep**，`V4_DEPTH_LOSS_DECLARE_v2` §2「主表 = 与训同一尾部」**不成立**，该主表对 FT 头 **约 80% in-sample**。读法不对称：**v1 的 FAIL 因此更硬**；**v2 若在同协议下 PASS ⇒ 不可采**。另：**主表须与 ckpt 绑定** = 「对该 ckpt 诚实的最大切片」（老头 ⇒ 全 77 ep `0.076/consec2` FAIL；FT 头 ⇒ 与训练互斥那片）——把小分母有利尾切定为权威会洗掉 ⓪ 首个权威 FAIL 与 V0 ④ 低功效判定，**该放松不给签** | 统一两侧切法（复用同一函数/同 seed）+ 开训前打印两侧 index 集合并 `assert` 相等，写入落盘契约 | ✅ **DONE**（`holdout_split.py` + MATCH assert；编年 §6 / GATE (X)） |
| **20** | **主表（尾 16）的 ⓪b 可判性 + 尾切在本语料上是错的仪器** | ⓪b 要求 `n_frames_with_near_px ≥ 100`；尾 16 仅占语料 ~21% ⇒ 全库不足 ~480 近带帧则**主表天生不可判**（而过线第一条正是「⓪b 过」）。且 [`v4_p45_merge_usable.py:25-45`](scripts/v4_p45_merge_usable.py) **按源顺序**写 `episode_{idx:05d}`，`near_enrich` 为**第三源** ⇒ **尾部集中是近带富集集** ⇒ 要么 (a) 帧数够但分布**明显富近带**（与 ⓪e「测试分布=部署分布」冲突，且尾 16 的 `0.044` vs 全库 `0.076` **是分布差、不是抽样噪声**），要么 (b) 帧数不够（不可判）。**两种情况都判定确定性尾切不适用于本语料** | ① 开训前先在**老头**上跑 holdout 只看 ⓪b；② 改 seeded 随机切（与 #19 同 seed 同集合）；③ 落盘按源分布 | ✅ **DONE**（seeded 切 + 老头 hold035 预检 113；编年 §6 / GATE (X)；hold 0.2 曾证 72&lt;100 ⇒ 改 0.35） |
| **21** | **①d ≤0.30 是过线项，不得事后删；且不得再靠 `absrel=silog=0` 拿 ①d 换 ⓪c** | v3 关掉全图回归后 **①d `0.113 → 0.684`（6× 退化）**，编年记为「未作过线」= **事后删项**；而 ①d 是 **V0 ① 已签子项**、v2 声明 §2 过线也明写 ≤0.30。⇒ 正确记法「**v3 = ⓪c PASS ∧ ①d FAIL ⇒ 整头不可用**」；删项须回 §5.0 重签（**不应签**）。v4 须改**约束式**（①d ≤0.30 作硬约束/罚项）或**近带/远场双头分离** | 无（已有数） | ⬜ **v4 声明须写死** |
| **22** | **`holdout_frac=0.35 / seed=0` 就地冻结** | 本次 0.2→0.35 由 **⓪b 可行性**驱动、且在**老头**上预检（113 ≥ 100）⇒ **合规**。但评测总体一旦可调即可「挑分片」⇒ 须冻结；v4 若改，必须先声明并**重报老头同切基线**。另：三轮对照（v1 尾16 / v2 hold15 / v3 hold035）**跨行不可比**，只许同切片内比较 | 无 | ⬜ **待冻结**（写入下份声明即闭合） |
| **23** | **v3 结案缺 ⓪e / ⓪f ⇒ `authoritative=false`** | ⓪f 是 `[lo,hi]` **唯一合法依据**；`①d=0.684` 意味远场读数已崩 ⇒ 预期 v3 `⓪f(1)(2)` 明显变差、`⓪f(3)` 可采 `lo` 被推更远。**即便 ⓪d 修好，⓪f 也可能对 v3 致命** | 从既有 H100 emit 抄入文书（字段本已落盘；不重训） | ✅ **DONE**（§6.6 数字 + **§6.7 结案读法**：H100 字段齐不补跑；(1)(2) **未** 6× 崩 ⇒ ①d≠⓪f 远场已死；双头由 **①d 锚**驱动、**非** ⓪f(3) 单独强制；「v3 结案」仍因 ①d/⓪d/consec 不可发证） |
| **24** | **⓪c 的显式阈值与 ⓪d ∧ ⓪f(3) 的隐含精度要求不相容 —— 这是「须裁」，不是「填空」** | 3.0 m 阈值上判据是**双侧**的：⓪d 要 `P(D̂_fwd>3 \| GT_fwd≤3) ≤0.05`，而 ①′ S_blocked 要走廊可通行即 `P(D̂_fwd<3 \| GT_fwd∈[3.0,3.5))` 必须小。无 guard band 时二者同时 ≤0.05 ⇒ 须能分辨 GT=2.9 与 3.1 ⇒ 单侧余量 0.1 m @1.645σ ⇒ **σ(D̂) ≤ 0.061 m @3 m（σ_rel ≈ 2%）且偏置 ≈ 0**。而 ⓪c 显式只要 **p90 AbsRel ≤0.50**（= ±1.5 m @3 m）⇒ **显式阈值比隐含功能要求宽 5–15×**。实证：**v3 ⓪c 0.432 PASS 与 ⓪d/⓪f(3) FAIL 同时成立** ⇒ 「过 ⓪c」**不蕴含**「够 ⓪d」，不得再拿 ⓪c 当深度头充分性指标。裁定项（二选一或并用）：(a) 把 ⓪d 隐含的精度前提**显式写下**并承认单目 D̂ 通道不满足；(b) 把触发迁到**尺度无关量 τ̂**（shield 控制律，红线明许改）。**红线：两条都不是降 ⓪c/⓪d 阈值** | 已实测（`v4_dhat_kmin_scan_*` + §6.6/6.7），无待测项 | ⬜ **待用户裁** |
| **25** | **S_blocked「逼障绕行」按 §0 已签规则本轮自动出局（登记，非放松）** | §0 目标行原文：「逼障」**仅当 ⓪f 证出可行带才入 merge」**。现状：⓪f(3) diag `lo` = **5.25**（老头）/ **6.25**（v3），而带宽 1.5 且 `hi ≤ 8` ⇒ 可行带即使存在也已贴上界；近墙误触 `[3.0,3.25)` = **0.778（n=27，95% 下界 ≈0.60）**、hold035 **0.90（n=10）**，`[3.25,3.5)` = **0.571（n=35）/ 0.722（n=18）**；⓪f(4) `n_tau_cond` = **1–3 ⇒ τ 侧不可判**。⇒ **⓪f 未证出可行带** ⇒ 逼障**不入本轮 merge，不需新签名、不算放松**。本轮主张缩为「**S_open 不退化 + ④′ 安全**」。将来要重纳，须先由 ⓪f 证出可行带（**含 τ support 达标**） | 无（规则生效） | ✅ **登记完成** |
| **26** | **#24 已裁 (b)：触发迁到 τ̂ —— 迁移合法，但两项判据级后果须先签（`5ao`）** | **裁定（2026-08-21，用户）= (b)**。代码事实：**τ 早已是 live 触发通道**（`safety.py:104`/`:171` 三通道 OR）⇒ (b) 实为**摘掉 `d_hat < min_depth_m` 那条 OR 腿**，属 shield **控制律**（红线明许）。**顺带收益**：`TauPredictor.center_frac=0.5` ⇒ τ 天生前向锥 ⇒ **消掉 P0b 那处「eval 几何 ≠ 部署几何」错配**。**但两项不是控制律 ⇒ 立 `5ao` 待签**：(i) ⓪d 还算不算 primary（改划分须回 §5.0）；(ii) **新增 ⓪g「τ 漏触发」** —— 全库确认 `v4_zero_eval` 只算 `p_tau_false_trigger`、**无任何 τ-miss 统计** ⇒ 摘 D̂ 腿 = 安全腿**从有判据变无判据**。**签字前不得摘腿、不得改 rollout 构型**；不动 `min_tau_s=1.0` | 声明 [`V4_TAU_TRIGGER_MIGRATION_DECLARE_20260821.md`](../../docs/handover/V4_TAU_TRIGGER_MIGRATION_DECLARE_20260821.md)；诊断 T-1..T-5 不发证、可先跑；阻塞预检 B-a `dt` 回退（**τ 成唯一触发量后从精度问题升级为直接改部署罩**，且 `foe_calibrated` 分支里 dt 进入两次 ⇒ 非线性缩放）/ B-b `min_depth_m` 三处不一致（yaml **1.5** vs `safety.py` 默认 **3.0** vs gate `trigger_m=3.0`）**实测对账** / B-c τ 标定器仍是老 r60 语料 / B-d `τ_gt` 锥参数对齐 | ⬜ **`5ao` 待签**；诊断可跑 |

---

## 4. 【必须实测、不许假设】

> 红线：**「`step_hz` 实测不猜」**。下列每一项都有「假设错了就悄悄改变了被测系统」的实证前科。

| # | 必测项 | 为什么（前科 / 机制） | 不测的后果 |
|---|---|---|---|
| 1 | **`step_hz` 重测并冻结** | 必须在 **shield-on 且逐步跑 D̂/τ/p_coll** 的构型下测（D̂ 是网络前向，与渲染 GT 是两件事） | 全部时间口径（τ、制动余量、band 占比）失真 |
| 2 | **τ 预测器实测 `dt` 直方图 + 「是否用过 `dt_s` 默认回退」标志** | `tau_predictor.py:289` 默认 `dt_s=0.1`（10 Hz），而 `configs/aerial_rl.yaml:20` `step_hz=5.0`（dt=0.2）；`:330-333` 仅在 `obs.t` 有限且单调时才覆盖 ⇒ 回退一旦发生 **τ 秒数减半、触发面约翻倍 = 悄悄改了部署罩** | 用过回退 ⇒ **`authoritative=false`**（进 self-check） |
| 3 | **⓪f：`D_gt ∈ (3.0, 8.0]` 的 D̂ 精度 + D̂/τ 双通道误触发率** | ⓪a 的 support 只到 3.0 m ⇒ **GT > 3 m 区从未测过**；晚⁷ diag `P(over-read) = 0.377`（既非一致欠读也非一致过读）⇒ 从 `GT1.5→D̂0.645` 外推 gain **无依据** | `[lo,hi]` 无合法依据 ⇒ ①′d-b 不可裁 |
| 4 | **teleport 能否复现同一 `z0`**（⓿e） | 精确状态重置是 ⓿ 全部结论的前提 | ⓿ 的 ρ 可能测的是重置噪声 |
| 5 | **起点两两最小间距** | 「32 局 = 同点 32 射线」的老病（`make_start_episodes` 全局共用 `[0,0,cruise_alt]`） | B3 的二项功效计算无效 |
| 6 | **分层器标签一致率**（`R ≥ 3`） | 分层是 ①′ 全部结论的地基 | 不一致 ⇒ **gate 作废（harness 病）** |
| 7 | **`C_P7` clearance 分布 + `median band_frac`（P7-diag）** | 「逼障」与 `θ` 唯一合法锚 | `θ` 失锚、`hi` 变拍脑袋 |
| 8 | **`K_off`（off 臂遭遇机会）** | 旧 ④ 被横漂空过的直接病根 | ④ 记 PASS 而其实 vacuous |
| 9 | **S_open 的 `intervention_rate`**（应 ≈ 0） | S_open FAIL 时**分不清罩过敏还是策略坏** | ①′a-o 的 FAIL 无法归因 |
| 10 | **进带前 `k` 步的 `D̂_fovmin` / `v_fwd` / 侧向位移**（C1） | ①′d-b 只剩结果不剩机制 | 带为空 / 带很高时都无法解释 |
| 11 | **碰撞局撞点 7 项**（5d） | 三分失效源必须可分：`steps_to_collision`、`d_first_contact`、撞点前 5 步的 `D̂_forward` 与 `D_gt_forward`、`intervention` 标志、shield 触发步号 | 无法区分「深度不可信」/「shield 消费路径」/「反应余量不足」；**P5 的方向也无从裁定** |
| 12 | **`action_commanded`**（shield 覆盖**前**的指令动作，5e） | 否则策略行为与罩行为不可分离 | ④′ 只能测罩 |
| 13 | **GT 深度只允许离线位姿回放取** | 在线取 GT ⇒ ~3 Hz ⇒ **dt 变** ⇒ 改了被测系统（A2）。已核对：τ 通道是**纯视觉**（`use_gt_depth=False`），A2 与部署罩**不冲突**（H7） | 闭环速率与部署不一致 ⇒ 结论不可比 |

---

## 5. 落盘契约（**缺字段 ⇒ gate 直接 `authoritative=false`**，进 self-check，不靠人工核）

- §1.0 全部原有字段
- `latch_step[]`、`release_step[]`、`n_release`、`frac_steps_engaged`、latch 时 `shield_channels`（无 v5 时 `release_step[]`/`n_release` 恒 0）
- 两臂**总步数与命中数**、每局步数直方图（E1）
- **累计 yaw 转角**（F2）
- `n_invalid_spawn` / `n_none_returned` / `n_pair_broken`（P0c）
- **碰撞局撞点 7 项**（5d，见 §4-11）
- **`action_commanded`**（shield 覆盖前的指令动作，5e）
- `angle(yaw_forward, velocity)`（5k）
- **`_breached` 三通道各自的布尔位** + `v_fwd` / `τ̂` / `p_coll` / `D̂_fovmin` / `engaged`（5z）—— **哪条通道破的必须可分离**，否则带为空时无法归因
- **τ 实测 dt 直方图 + `dt_s` 回退标志**（5ac-c）
- **S_open 的 `intervention_rate`**（C2）
- **进带前 k 步的 `D̂_fovmin` / `v_fwd` / 侧向位移**（C1）
- 逐步 `clearance_fov` + `cone_clearances` 五向分解（诊断）

---

## 6. 停止规则 / 下车站（预注册，FAIL 后不许「换个条件再跑一次」）

**P7-accept 在 S_blocked FAIL**（planner 纯前向 + 真实感知都到不了 ⇒ 该层在当前 WM / 罩 / 场景下**经验不可解**）⇒
1. **不进 P8**（不训 actor，`enable_policy_update` 保持 false）；
2. 判定 **「V4-MVP 的前提被否证」**，写进 `V4_GATE_STATUS.md`；
3. 退回 **WM / 感知侧**（P1 / P3 / P4.5 的重训与语料），或裁定 S_blocked 场景难度本身需 re-freeze（**另案，须新签字**）；
4. **明令禁止的三种反应**：降 S_blocked 到达率阈值 / 换更容易的起点集后宣布 P7 过 / 把 ①′ 只在 S_open 上判。

**已如实登记的最大风险（5am(d)）**：v5 不启用 ⇒ **一次触发即整局 latch、本局报废**（`safety.py` `if self._engaged: return True`），而 τ 通道在 `v = 5 m/s` 巡航下触发到 **≈5 m** ⇒ **①′a-b ≥ 0.50 的经验可解性完全押在 P7-accept 上**（G1 只论证了「带定义不与罩互斥」，**未论证到达率**）。P7-accept FAIL ⇒ 走上面的下车站，**不得就地放宽阈值、不得顺势启用 v5**。

**仍未预注册停止规则的缺口（R-16 剩余，如实登记）**：**⓪ / ⓿ / P3.5 各自 FAIL 后**没有下车站。

---

## 7. 主张范围（签字随附，**不得外推**）

1. **不主张「想象 AC 有增益」**（5ag(B)）—— V4-MVP 只主张「**不退化 + 安全**」。⇒ **V4 不对「世界模型想象是否有用」出证**，该主张留 **V5 另案**（届时按配对检验 + 跑前冻结 `Δ=0` 预注册）。
2. **到达能力仅覆盖机体前向扇区**（5af(a)）—— **侧向 / 后向 goal 本周期不测**；In-表（goal 进 π 的表示）改动属 **V3 另案**。⇒ ①′ 结论**不得读成全向导航能力**。
3. **「主动终止」out of scope**（5p 后半）—— policy 自主停止**一条判据都没有**，登记为最终目标的未覆盖维度。
4. 「逼障」的可证明含义已收窄为「**贴着罩的 standoff 边缘、减速做紧绕行**」，**不是**「飞进 `[1.5, 3.0]` 近碰带」—— 后者被部署罩**结构性禁止**，任何要求它的判据都是在要求策略违反安全罩。

---

## 8. 红线（实施期间一条都不许碰）

- **四信号全过前不翻 flags**；`enable_policy_update` **绝不顺带打开**。
- **不为凑过调阈值 / shield 参数** —— shield **控制律**是被测系统（可改）；§4.1 **阈值**不可改（改需 re-freeze）。**不降低 V0/V1 阈值凑过**。
- **禁止 tied-zero 式「双零安全」冒充 ④**。
- 训练时 **shield / τ / depth 路径与 V1 部署一致**；**禁止为过 gate 关掉安全罩**。
- 代码走 **git**，**禁 scp 热补丁**；**`step_hz` 实测不猜**。
- 干净重训**禁 warm-start 失效 ckpt**；canonical `depth_step_5000.pt` **不动**；失效 ckpt **归档保留**。
- **goal 张量输入属 V3**，本周期不给 RSSM 加 goal 输入。
- **不 push GitHub**（除非明确要求）。
- **不降 `n`**（P0c 用补扫解决，不用降 n 解决）。

---

## 9. 已知残余风险（不解、只登记）

| 项 | 内容 |
|---|---|
| R-1 | 「绕大圈 vs 贴障」目标函数区分力弱（≈8%） |
| R-3 / P2 | `p_coll` 现为死值；**即使头活了，`collector.py:185` 仍不传 `wm_out`** ⇒ 第三条通道在采集环里可能仍是哑的 |
| R-16 剩余 | ⓪ / ⓿ / P3.5 各自 FAIL 后无预注册停止规则 |
| 5p 后半 | 「主动终止」零判据 |
| — | `S_blocked_tight` 的 `n` 未定 |
| — | ④′b 用**全场 min** vs ④′c 用**前向遭遇**，两者几何不同 |
| — | ~~P0c 的 spare 池大小未定量~~ → **已定** `--spare-count=16`（2026-08-20） |
| — | 无 v5 时「一次触发即报废」对 ①′a-b 的实际难度**未量化**（只能等 P7-accept 实测） |
| — | C1 的 `k` 与 5ac(a) 的 `k` 是否同一个数**未定** |
| P0b | shield 消费路径仍是 `predict_min`，`predict_cones()` 未接线 |
| — | 头一致性缺口：`depth_ckpt_da3_20260810` vs `depth_ckpt_da3_near_20260811` |
| — | `advance_goal_rel_body`（`goal_features.py:60-73`）**不按 `a[3]` 旋转** body-frame goal ⇒ 任何 yaw≠0 的臂喂给 RH 的 goal 失真（改它会改 §A 全部数字 ⇒ **走签字**） |
| — | ~~`planner.action_limits` 默认 `None`~~ → **P6 DONE**（`4e76865`）；yaml `imagination.horizon: 10` vs 权威 H=15；`open_ahead` 拒收数 708 vs 15（47×）扫描行为不稳 |

---

## 10. 变更记录

- **2026-08-24（6ap ⓪ primary 迁移签字 + harness）** —— [`V4_ZERO_PRIMARY_MIGRATION_REFREEZE_20260824.md`](../../docs/handover/V4_ZERO_PRIMARY_MIGRATION_REFREEZE_20260824.md) **12/12 采纳**：⓪h@12.2m **primary**、⓪d@3m **`0d_legacy` report-only**；`v4_zero_eval.aggregate_verdict` 合取改为 `⓪a∧⓪b∧⓪c∧⓪h∧⓪e`；禁止仅为过 ⓪d depth FT。P4.5 深度结案改看 ⓪h。下一发 = 老头 × `p45_merged` hold035 权威 emit。**不改** ⓪a/b/c 阈值、①′/④′/⓿、`enable_policy_update`。
- **2026-08-21（B-2 Phase C 滞回扫描 DONE：不可解）** —— 声明 [`V4_HYSTERESIS_SCAN_DECLARE_20260821.md`](../../docs/handover/V4_HYSTERESIS_SCAN_DECLARE_20260821.md)；`--scan-trigger-hysteresis-delta`。老头两片 **consec 全 δ=2**；rate 可降、误触变差 ⇒ **不升格 B**。下一路径 `#26`/`5ao`。不改判据阈值。
- **2026-08-21（D̂ K-min 扫描 DONE：B-1 否定）** —— 声明 [`V4_DHAT_TEMPORAL_MIN_SCAN_DECLARE_20260821.md`](../../docs/handover/V4_DHAT_TEMPORAL_MIN_SCAN_DECLARE_20260821.md)；`--dhat-temporal-min` / `--scan-…`。老头两片 **consec 全 K=2**；rate 可压、误触随 K 变差 ⇒ **须 B-2 滞回**（不升格 K）。不改判据阈值。
- **2026-08-21（#23 结案读法 DONE + V0 ④ deferred）** —— 编年 §6.7：H100 复核字段齐；①d=0.684 ≠ ⓪f 远场死；双头 = ①d 锚选项、非 ⓪f(3) 强制。V0 ④ 重跑只登记、等 head 定稿（不 launch）。不改判据阈值。
- **2026-08-21（#23 补录 DONE）** —— 编年 §6.6：v3 ⓪e/⓪f 从 H100 既有 emit 入文书（不重训）。主表同切 diag `lo` 老头 5.25 → v3 **6.25**。不改判据阈值。
- **2026-08-21（编年审查入库：§3 #21–#23；#19/#20 DONE）** —— 编年 [`V4_DEPTH_FT_V1_V2_V3_CHRONICLE_20260821.md`](../../docs/handover/V4_DEPTH_FT_V1_V2_V3_CHRONICLE_20260821.md) §6；GATE (X)–(AE)。**#21** 禁事后删 ①d / 禁拿 ①d 换 ⓪c；**#22** holdout 0.35/0 冻结 + 跨轮不可比；**#23** v3 缺 ⓪e/⓪f ⇒ 归档前必补。不改判据阈值。
- **2026-08-21（声明 v3 §9 闭合）** —— [`V4_DEPTH_LOSS_DECLARE_v3_20260821.md`](../../docs/handover/V4_DEPTH_LOSS_DECLARE_v3_20260821.md)：holdout **0.35/0**；K=4 hard 缓存；P1 silog=0；min_steps=100；主 hinge=`relu(D̂−trigger)`。实现前不开训。
- **2026-08-21（声明 v3）** —— 初稿；**→ 见上条闭合**。
- **2026-08-21（声明 v2）** —— [`V4_DEPTH_LOSS_DECLARE_v2_20260821.md`](../../docs/handover/V4_DEPTH_LOSS_DECLARE_v2_20260821.md)：前向几何 hinge + AbsRel-p90；v1 未过线已结案。**→ 已跑未过线，见 v3。**
- **2026-08-21（跑前声明：hinge+pinball）** —— [`V4_DEPTH_LOSS_DECLARE_20260821.md`](../../docs/handover/V4_DEPTH_LOSS_DECLARE_20260821.md)；loss 默认关、CLI 开。不改判据阈值。**→ 已跑未过线，见 v2。**
- **2026-08-21（⓪ 权威 FAIL + 改训练目标开闸 + holdout 硬前置落地）** —— 控制臂 = 首个权威 FAIL；V0 ④ supersede 低功效；§3 #17 扩到 ⓪d；`v4_zero_eval --heldout-frac` + `n_near_forward_frames`。详见 [`V4_GATE_STATUS.md`](../../docs/handover/V4_GATE_STATUS.md) §3 (J)–(R)。**不改判据阈值。**
- **2026-08-20（P3/P1 补数入库）** —— P3：`near_px_total`、`max_frame_frac`、⓪c GT p90 分箱、⓪f(3)/(4) 全表；P1：`one_step_ok` 绑 h=0 行。产物 `artifacts/v4_zero_p3_20260820_bins.json`。不改判据。
- **2026-08-20（P3 记法更正入库；运营裁定 R-16=(B)；停 supervisor / 下一步改 P4.5）** —— 见 GATE_STATUS 同日顶条。不改判据阈值。
- **2026-08-20（P3 FAIL 入库；下一步 = P4）** —— ~~原文「⓪ FAIL ⇒ 继续 P4」已由上条更正 supersede~~（审计保留）。
- **2026-08-20（实施进度入库）** —— 前提链表与 §0「当前状态」更新为：**P0c / P2 接线 / P6 DONE**；**P1 FAIL**（权威层仅 reward）；**下一步当时 = P3**。P0c 正式跑数值见 §1 行；`--spare-count=16` 已签（§3 #11）。不改判据 / 不翻 flag。
- **2026-08-20** —— 新建本文件（V4 执行 runbook 干净稿）。**为什么 / 依据**：§5.0 削减签字表 16/16 行已于 2026-08-20 签字冻结，权威判据（§4.6）已无未决二选一 ⇒ 需要一份**只讲怎么执行**的入口，把散在九轮复核里的「跑前必须冻结」（§3）与「必须实测」（§4）**收成两张可勾的清单**。本文件**不新增、不修改任何判据**；一切定义以提案 §4.6 为准。
