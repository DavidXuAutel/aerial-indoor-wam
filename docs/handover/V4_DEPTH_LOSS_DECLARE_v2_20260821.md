# V4 深度 loss 改法 — 跑前声明 v2（2026-08-21）

> **状态**：**H100 已跑、主表/附表 FAIL**；被 [`V4_DEPTH_LOSS_DECLARE_v3_20260821.md`](V4_DEPTH_LOSS_DECLARE_v3_20260821.md) 取代。ckpt 归档不部署。  
> **取代**：[`V4_DEPTH_LOSS_DECLARE_20260821.md`](V4_DEPTH_LOSS_DECLARE_20260821.md)（下称 **v1**）—— v1 已跑、**held-out 未过线**，本文件为**当时**新声明，不改写 v1 原文。  
> **红线**：不改 §4.6 / §4.1 任一阈值；`enable_policy_update` 仍 false；深度 FT **只上 H100**（不上 4090）。

---

## 0. v1 失败结案（依据，非重训理由空转）

产物：`artifacts/v4_zero_p3_hinge_pinball_holdout_20260821.json`  
对照（**同一** `--heldout-frac 0.2` 尾 16/77）：`artifacts/v4_zero_p3_oldhead_holdout16_20260821.json`

| | 老头@holdout16 | v1 hinge+pinball@holdout16 |
|--|----------------|----------------------------|
| ⓪c p90 | 0.76 FAIL | **1.13 FAIL**（更差） |
| ⓪d miss / consec | **0.044 / 1 PASS** | **0.156 / 4 FAIL** |
| ①d holdout AbsRel | — | 0.115（仍好看） |

**原因（已测，写入本声明前提）**：

1. **几何错配**：v1 在「近带全体像素」上罚平均过读；⓪d 考的是 **`forward_min(D̂)`**。训练日志末段 `near_overread_hinge≈0.003`（均值过读已近 0），eval 仍 miss=0.16 ⇒ 均值 hinge ≠ 前向 min。
2. **项饱和后变成有害 AbsRel FT**：hinge/pinball 在 ~500 step 内塌到可忽略，其后 ~1500 step 主导是全图 AbsRel/SILog —— 与对称 FT 同病（①d 好、⓪c/d 伤）。
3. **⓪c 代理写错**：pinball(signed relative, τ=0.9) ≠ 压 AbsRel p90；`(0,1.5]` median↓ 而 p90↑（欠读/野值尾）。
4. **关 `near_weight` 后欠读几乎无约束**（τ=0.9 对欠读只乘 0.1）。

v1 ckpt（`depth_ckpt_p45_hinge_pinball_20260821`）**归档、不部署**。

---

## 1. v2 改什么（对准判据几何）

| # | 对准 | 改法 | 拟用 |
|---|------|------|------|
| **A′** | ⓪d | **前向 crop / cone 上的过读 hinge**（与 eval `forward_min_depth` / `center_frac` **同一几何**）：在 `GT_fwd ≤ trigger`（或近带前向像素）上罚 `relu(D̂_fwd − GT_fwd)` 或 `relu(D̂_fwd − trigger)`；**禁止**再只对「全图近带像素均值」做 hinge 充数 | `fwd_overread_hinge_weight=3.0`，`center_frac` = 部署/eval 同值 |
| **B′** | ⓪c | 近带（或前向近带）上对 **AbsRel `e=\|D̂−GT\|/GT`** 做 **pinball τ=0.9** 或等价尾权（`e * stopgrad(e/median)`）；**禁止**再用 signed-relative pinball 冒充 p90 | `near_absrel_p90_weight=2.0`, `tau=0.9` |
| **C′** | 训练日程 | **早停 / 两阶段**：A′ 饱和（日志 `fwd_hinge` 连续 N step 低于 ε）后 **停或把全图 AbsRel lr 降 ≥10×**，禁止再盲跑满 2000 step AbsRel；默认 **max 800 step** 或 saturation 触发停 | `max_steps=800` 或 saturation early-stop |
| **D** | consec | 仍 **不**做 shield 滞回。若 A′ 后 rate≤0.05 而 consec 仍≥2 → **另案**声明 D̂ 时序平滑（eval 同口径） | 本轮不做 |

保留：全 mask AbsRel（①d 锚定）但 **阶段 2 降权**；对称 `near_weight` 本轮 **0**（避免再走均值近带）。  
`near_focus_m=5.0` / `trigger=3.0` 与 gate 一致。

---

## 2. 怎么训 / 怎么验

- **机**：**H100 only**
- **init**：`depth_ckpt_da3_r60_20260814/depth_step_2000_da3_ft_head.pt`（部署老头；**不用** v1 / 对称 p45 FT 头）
- **语料**：`dataset_v0_p45_merged_20260821`（须先同步到 H100）
- **holdout 训**：`--holdout-frac 0.2`
- **验收 ⓪**：`v4_zero_eval --heldout-frac 0.2`  
  - ~~**主表**：与训同一尾部~~ → **⚠️ 事实错误，见 §7 (C-1)**：`train_depth_head._split_train_holdout`（:159-178）是 **seeded permutation**（`--split-seed` 默认 0），`v4_zero_eval._heldout_episodes`（:311-337）是 **确定性尾切** ⇒ **两侧不是同一集合**，期望重叠仅 ≈3.3/16 ep ⇒ 所谓「主表」对 FT 头 **约 80% in-sample**。**开训前必须先统一切法并 assert 两侧 index 集合相等。**
  - **附表（必报）**：同 ckpt × **全 77 ep**（`heldout-frac=0`），防止再出现「尾 16 上老头 ⓪d PASS、全库 FAIL」的切片错觉；~~**权威过线以主表为准**~~ → **⚠️ 不可接受，见 §7 (C-2)**：老头对全 77 ep 全部诚实 ⇒ 其权威支撑就是 77 ep（`0.076 / consec 2` FAIL）；把权威定为更小分母的有利尾切（`0.044 / consec 1` PASS）= **看到哪片过线之后**丢掉 61 集诚实数据，违反已登记的「小分母 / in-sample PASS 不可采」。**改为：主表 = 「对该 ckpt 诚实的最大切片」**（老头 ⇒ 全 77；FT 头 ⇒ 与其训练互斥的那一片）。
- **过线（主表）**：⓪b 过；⓪c p90≤0.50；⓪d miss≤0.05 **且** consec&lt;2；①d holdout AbsRel≤0.30 —— **补：漏列 ⓪a（median ≤0.30）与 ⓪e**，二者按用户「primary = ⓪a–e」均属 primary，须在过线清单内（§7 D-1）
- **失败**：归档；**禁止**无 v3 声明再训；不降阈值

---

## 3. 落盘契约（缺字段 ⇒ 本发 `authoritative=false`）

训练 jsonl / stdout 逐步：

- `fwd_overread_hinge`（或等价前向项）  
- `near_absrel_pinball`（**基于 AbsRel e**，不是 signed）  
- `n_fwd_near` / `n_near`  
- 触发 early-stop 的 step 与原因  

eval emit：`n_near_forward_frames`、`split`、⓪c `gt_bins`。

---

## 4. 明确不做什么

- 不重复 v1「全近带像素均值 hinge + signed pinball + 满步 AbsRel」  
- 不用 4090 做深度 FT  
- 不用 v1/对称 FT ckpt 当 init  
- 不用 shield 滞回冒充修 ⓪d consec  
- 不把 in-sample / 无声明 PASS 当过关  

---

## 5. 代码落点（声明后实现，实现前不得开训）

1. ~~`forward_min` 可微~~ → **DONE**：`depth_geometry.forward_min_depth_torch` + `fwd_overread_hinge_weight`  
2. ~~AbsRel-p90~~ → **DONE**：`near_absrel_p90_weight`（signed pinball 保留默认 0）  
3. ~~early-stop / 两阶段~~ → **DONE**：`--early-stop-on-fwd-saturate` / `--drop-absrel-lr-on-fwd-saturate`  
4. ~~切法统一 #19/#20~~ → **DONE**：`holdout_split.py`；训写 `holdout_split.json`；评 `--expect-holdout-split` assert；seeded 随机切（禁尾切）  
5. 开训前打印 `declare_id=v2-20260821`；机 = **H100**

---

## 6. 一句话

v1 证伪的是「近带像素平均过读 hinge」，不是「对准 ⓪d」这条路；v2 把损失收到 **与 eval 同一前向几何**，把 ⓪c 收到 **AbsRel 尾**，并 **禁止 hinge 饱和后继续长跑 AbsRel**。

---

## 7. 审查附注（2026-08-21，审查方；不改写 §0–§6 原文，只加注）

> 审查范围 = 用户令「看一下这个方案以及分析的原因是否属实」。**未改任何阈值**；`enable_policy_update` 仍 false。

### A. §0 四条「原因」核验

| # | 结论 | 依据 |
|---|------|------|
| 1 几何错配 | **属实（有直接实测）** | 训练 `near_overread_hinge≈0.003` 与 eval `miss=0.16` 并存，即「均值近带 hinge 管不住前向 min」的直接反证；与代码一致：`depth_head_loss`（`dynamics_torch.py:624-685`）近带项是**对称均值**，判据侧取**极值** |
| 2 项饱和后变有害 AbsRel FT | **方向可信，归因未分离（不得当已证前提）** | 支持：①d `0.115` 好而 ⓪c/d 更坏，与对称 FT 同型。但 v1 ⓪c `1.13` 比**对称 p45 FT 头**的 `0.79` 还差得多 ⇒ 单靠「饱和后空转回 AbsRel」解释不了，更像 **pinball 在早期就把 p90 弄坏**（即原因 3）。⇒ 2 与 3 的权重须由逐步 loss trace 分开；**若真正肇因是 3，则 C′ 的 `max_steps=800` 并不构成修复** |
| 3 ⓪c 代理写错 | **属实（定义层面即可判）** | signed-relative pinball τ=0.9 对欠读只乘 0.1，而 AbsRel `|e|` 的 p90 由**两侧尾**共同决定 ⇒ 压 signed 分位 ≠ 压 `|e|` p90；「median↓ / p90↑」正是压中位、放尾的典型形态 |
| 4 关 `near_weight` 后欠读无约束 | **属实**，是 3 的直接推论 | 同上 |

### B. 方案对症性（成立部分）

- A′/B′/C′ 分别对准 1 / 3-4 / 2，**方向正确**；D 不做滞回符合红线「不用滞回冒充修 ⓪d」。
- `v4_zero_eval --heldout-frac` 已落地（`v4_zero_eval.py:311-390` 确认为确定性尾切 + `split` 落盘）⇒ 此前要求的**硬前置已闭合**。
- 落盘契约含 `n_near_forward_frames`，与 GATE §3 (M) 的要求一致。
- **A′ 的适用边界（必须写明）**：⓪d 判 `forward_min_depth`，但**部署 shield 消费的是 `depth_predictor.predict_min`（:80-88，全图单像素 min，无方向过滤）** ⇒ A′ 做到的是「训练几何 = **eval** 几何」，**不是**「= 部署几何」。P0b（shield 改用 `predict_cones()`）不做完，这个错配只是被搬了一站。

### C. 阻塞级（不改则本发无论结果如何 **不可采为 PASS**）

- **C-1（事实错误）§2「主表 = 与训同一尾部」不成立**：depth 训是 **seeded permutation**（seed 0），eval 是**确定性尾切** ⇒ 不同集合，期望重叠 16×16/77 ≈ 3.3 ep ⇒ 主表 16 ep 中约 13 ep 被深度头训练过。  
  推论：(i) §0 表头「**同一** `--heldout-frac 0.2` 尾 16/77」对 **FT 头不成立**（对**老头**成立——老头未训过任何一集）；(ii) v1 的 `⓪d 0.156 / ⓪c 1.13` 是在**偏乐观**条件下取得的 FAIL ⇒ **FAIL 更硬，v1 结案不受影响**；(iii) 但 v2 在同一协议下若得 PASS，该 PASS **不可采**。  
  **必做**：在 `train_depth_head` 加与 `_heldout_episodes` **同一函数/同一 seed** 的切法，开训前**打印两侧 episode index 集合并 assert 相等**，写入 §3 落盘契约。
- **C-2（红线附近）** 见 §2 注：主表须**与 ckpt 绑定**为「对该 ckpt 诚实的最大切片」。老头@尾16 只作**同切片对照**，不作过线判定。此更正是既签规则（in-sample / 小分母 PASS 不可采）的直接应用，**不需新签名**；反向用法（小切片当权威）才需签名，**而该签名不应给出**。
- **C-3 主表可判性未先核（⓪b）**：⓪b 要求 `n_frames_with_near_px ≥ 100`。尾 16 仅占语料 ~21%，全库若不足 ~480 近带帧则主表**天生不可判**，而 §2 过线第一条正是「⓪b 过」。**开训前先在老头上跑一次 `--heldout-frac 0.2`，只看 ⓪b 的 `n_frames_with_near_px`**。  
  更严重的一层：merge **按源顺序**写 `episode_{idx:05d}`（`v4_p45_merge_usable.py:25-45`），`near_enrich` 是第三个源 ⇒ **尾部集中是近带富集集**。于是尾 16 要么 (a) 近带帧够但**分布明显富近带** ⇒ 与 ⓪e「测试分布 = 部署分布」冲突，且 `0.044` vs `0.076` 的差**不是抽样噪声而是分布差**；要么 (b) 帧数不够 ⇒ 不可判。**两种情况都说明确定性尾切在本语料上是错的仪器** ⇒ 改用 seeded 随机切（两侧同 seed、同集合），并报 `merge_manifest.json` 的按源分布。

### D. 次级缺口（应补，不阻塞开训）

- **D-1** §2 过线清单漏 **⓪a**（median ≤0.30）与 **⓪e**（已在 §2 就地加注）。
- **D-2** `center_frac` 写「部署/eval 同值」= **引用式规范**，须落**冻结数值**；若用 `softmin` 代 `min`，**温度必须声明并冻结**，否则温度是未签的自由参数。
- **D-3** D 本轮不做滞回，但过线仍含 `consec<2` ⇒ 若 A′ 把 rate 压到 ≤0.05 而 consec 仍 ≥2，本发按声明即 FAIL。这是正确的，但要预知：**`consec` 很可能是本发真正的拦路项**。
- **D-4** 「⓪d 的 `≤0.05` 按点估计还是 95% 上界判」仍未声明（RUNBOOK §3 #17/#18、`5an` 待裁）。**主表 n 越小，这个选择越决定性 ⇒ 必须开训前定。**
