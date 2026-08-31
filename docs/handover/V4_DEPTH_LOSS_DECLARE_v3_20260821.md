# V4 深度 loss 改法 — 跑前声明 v3（2026-08-21）

> **状态**：**H100 已跑**；主表 ⓪c **PASS**、⓪d **FAIL**（miss 0.086 / consec 3）；附表 miss 点估计过、consec FAIL。ckpt 归档不部署。  
> **取代**：[`V4_DEPTH_LOSS_DECLARE_v2_20260821.md`](V4_DEPTH_LOSS_DECLARE_v2_20260821.md)（下称 **v2**）—— v2 已在 H100 跑完、**主表/附表均未过线**，本文件为**新声明**，不改写 v2 原文。  
> **红线**：不改 §4.6 / §4.1 任一阈值；`enable_policy_update` 仍 false；深度 FT **只上 H100**（不上 4090）；**不用** v1/v2 FT ckpt 作 init。

---

## 0. v2 失败结案（依据）

产物（H100）：

- 主表：`artifacts/v4_zero_p3_v2_holdout_h100_20260821.json`（seeded 15/77，indices MATCH ✓）
- 附表：`artifacts/v4_zero_p3_v2_full77_h100_20260821.json`
- 对照老头全 77（既有权威 FAIL）

| | v2@holdout15 | v2@全77 | 老头@全77 |
|--|--------------|---------|-----------|
| ①d holdout AbsRel | 0.139 | — | — |
| ⓪a median | 0.265 PASS | 0.138 PASS | ~0.20 |
| ⓪b 近带帧 | **72 FAIL** | 315 PASS | 315 |
| ⓪c p90 | **1.23 FAIL** | **0.78 FAIL** | **0.72 FAIL** |
| ⓪d miss / consec | **0.58 / 4 FAIL** | **0.123 / 4 FAIL** | **0.076 / 2 FAIL** |

切法/源配比已按 v2 §7 修好（MATCH、by_src 5/5/5）——**失败不是 #19/#20**。

**原因（有训练 jsonl 直接证据）**：

1. **A′ 空转**：`n_fwd_trigger` 均值 **~1.7**（142/800 步为 0；最大 6）。有条件时 `fwd_overread_hinge` **~88% 已为 0** ⇒ `3×fwd` 对 loss 可忽略，⓪d **几乎未进梯度**。
2. **C′ 早停失效 → 满跑有害 AbsRel FT**：`n_fwd=0` 时 hinge=`nan` **不推进**饱和 streak；偶发 `fwd>ε` 清零 ⇒ **未 EARLY STOP**，800 步主导仍是全图 AbsRel/SILog + B′ —— 与 v1「饱和后空转 AbsRel」同病；全 77 上 ⓪c/d **劣于老头**。
3. **B′ 代理仍不对**：`near_absrel_p90` = 近带 AbsRel 的**软尾权均值**，≠ AbsRel 的 τ-pinball；管不住 `(0,1.5]` p90。
4. **hard min 梯度极稀**：即便命中前向条件，回传只到 crop 内 1 个像素 × 每步少数帧。

v2 ckpt（`depth_ckpt_p45_v2_fwd_hinge_20260821`）**归档、不部署**。

---

## 1. v3 改什么（对准 v2 四条根因；含 §8 闭合）

| # | 对准 | 改法 | **冻结数** |
|---|------|------|------------|
| **S′** | 原因 1 / §8 C-3 | **前向难例缓存 + 有放回填满 K**（**禁止**静默 fallback 均匀采样） | 开训前扫 train 集，建 `GT_fwd_hard≤trigger` 的窗索引缓存。每步从缓存**有放回**抽到 `n_fwd_trigger≥K`；**缓存大小 &lt; K ⇒ 禁止开训**。冻结 **`K=4`**，`batch=32`，`fwd_oversample` 仅作诊断（主路径=缓存）。采样条件用 **hard** `forward_min`（与 eval 同）。不得用 `approach_oversample` 冒充 |
| **A″** | 原因 1+4 / §8 D-1 D-2 | 前向过读；**训练**用 softmin 聚合 `D̂_fwd`；**条件/验收**用 hard min | `center_frac=0.5`，`trigger_m=3.0`，`softmin_temperature_m=0.05`（冻结）。**主 hinge（贴 miss）**：在 `GT_fwd_hard≤trigger` 上 `mean(relu(D̂_fwd_soft − trigger))`；`fwd_overread_hinge_weight=3.0`。jsonl **兼报** no-grad `fwd_hinge_hard`（hard min 上同式）。相对 hinge `((D̂−GT)/GT)` 权重 **0**（仅诊断可选） |
| **B″** | 原因 3 / §8 D-3 | **真 AbsRel pinball τ=0.9**，域 = 前向 crop ∩ GT≤`near_focus_m` | `near_fwd_absrel_pinball_weight=2.0`，`tau=0.9`，`near_focus_m=5.0`。`near_weight=0`；v1 signed / v2 soft-p90 **=0**。全图近带 AbsRel-p90 **只报不训**（`report_near_absrel_p90`） |
| **C″** | 原因 2 / §8 C-2 C-4 | **P1-only + 关全图回归 + 防假饱和** | **P1**：`absrel_weight=0`，**`silog_weight=0`**，`nll_weight=0.05`；只训 A″+B″。默认 **`skip_p2=true`**（不进 P2）。`max_steps_p1=600`。早停：仅当 `step≥min_steps_before_saturate=100` 后，连续 `patience=50` 个**有支撑**步（`n_fwd≥K`）且 `fwd_hinge_soft<ε=1e-4` → stop；`nan`/`n_fwd<K`：**跳过、不冻不清零** streak |

保留 v2 切法：`holdout_split.py` + `holdout_split.json` + `--expect-holdout-split`。

**D / consec（§8 D-4）**：不做滞回。过线仍要求 consec&lt;2。若 **rate≤0.05 且 consec≥2** → 本发记 FAIL，结案须**拆腿**写「rate 已过 / consec 另案」，**不得**把整案打成「方案无效」。时序平滑另声明。

**P0b**：本发不做；A″ = 训练/eval 几何，≠ 部署 `predict_min`。

---

## 2. 怎么训 / 怎么验

- **机**：**H100 only**
- **init**：`depth_ckpt_da3_r60_20260814/depth_step_2000_da3_ft_head.pt`（**禁用** v1/v2/对称 p45 FT）
- **语料**：`dataset_v0_p45_merged_20260821`
- **holdout（§8 C-1 闭合）**：`--holdout-frac **0.35** --split-seed **0`**（`n_holdout=27`；v2 的 0.2/seed0 已证 ⓪b=72，**作废**）。期望近带帧 ≈315×27/77≈**110**；**仍以实测为准**
- **`declare_id=v3-20260821`**
- **开训硬前置（全部通过才准训）**：
  1. **⓪b**：老头 × 同切 `v4_zero_eval --heldout-frac 0.35 --split-seed 0` ⇒ `n_frames_with_near_px≥100`。不过 ⇒ **禁止开训**（只许改切法并**写回本节冻结**，不得训后改）
  2. **S′ 缓存**：train 侧 hard 前向条件窗数 **≥K=4**；否则禁止开训
  3. 打印 holdout indices + MATCH 契约字段
- **主表**（FT 权威）：训互斥 holdout + MATCH；过线见下
- **附表**：全 77；**禁止仅凭附表宣称过关**；附表 ⓪c/d **劣于**老头同表 ⇒ **回归 FAIL**（即使主表过）
- **过线（主表，阈值不改）**：⓪b；⓪a≤0.30；⓪e；⓪c p90≤0.50；⓪d miss≤0.05 **且** consec&lt;2；①d holdout AbsRel≤0.30
- **⓪d 口径**：miss/consec **点估计**（本发写死）
- **失败**：归档；无 v4 声明不得再训；不降阈值

### H100 recipe（实现落地后）

```bash
# 0) 老头同切 ⓪b 预检（frac=0.35 seed=0；须 ≥100）
# 1) train
python -m experiments.aerial.rl.train_depth_head \
  --backbone da3 --init-ckpt <r60 old head> \
  --dataset dataset_v0_p45_merged_20260821 \
  --steps 600 --holdout-frac 0.35 --split-seed 0 \
  --near-weight 0 --absrel-weight 0 --silog-weight 0 --nll-weight 0.05 \
  --fwd-overread-hinge-weight 3.0 --fwd-softmin-temp 0.05 \
  --min-n-fwd-trigger 4 --fwd-hard-cache \
  --near-fwd-absrel-pinball-weight 2.0 --near-fwd-absrel-pinball-tau 0.9 \
  --early-stop-on-fwd-saturate --min-steps-before-saturate 100 --skip-p2 \
  --declare-id v3-20260821 \
  --checkpoint-dir depth_ckpt_p45_v3_fwd_20260821 --save-ckpt --overwrite --device cuda

# 2) eval 主表（0.35/0）+ 附表全 77（expect-holdout-split）
```

---

## 3. 落盘契约（缺字段 ⇒ `authoritative=false`）

训练 jsonl / stdout 逐步：

- `fwd_overread_hinge`（soft / 主损失）、`fwd_hinge_hard`（no-grad）
- `near_fwd_absrel_pinball`、`report_near_absrel_p90`
- `n_fwd_trigger`、`fwd_cache_size`、`phase=p1`
- `absrel_weight`、`silog_weight`、`softmin_T`
- early-stop 的 step / reason；若因缓存&lt;K 拒训须落盘

eval：沿用 v2（`n_near_forward_frames`、split+by_src/layer、⓪c `gt_bins`、MATCH）。

---

## 4. 明确不做什么

- 不重复 v2「无前向过采样 + soft-p90 + 满步 AbsRel/SILog」
- 不用 4090 FT；不用 v1/v2 ckpt init；不用滞回冒充 consec
- 本发不绑 P0b；不降 §4 阈值
- 禁止静默采样 fallback；禁止仅附表洗过关
- **禁止**再用 `--holdout-frac 0.2 --split-seed 0` 当本发主表（已证 ⓪b 不足）

---

## 5. 代码落点（**已实现**；开训仍须 ⓪b 预检）

1. ~~hard 缓存~~ → `build_fwd_hard_window_cache` / `sample_fwd_hard_windows`；`--fwd-hard-cache`；&lt;K 拒训
2. ~~softmin + miss hinge~~ → `forward_min_depth_torch`；`relu(D̂−trigger)`；`fwd_hinge_hard`
3. ~~near_fwd pinball + silog_weight~~ → DONE
4. ~~早停~~ → nan 跳过；`min_steps_before_saturate`；`--skip-p2`
5. ~~CLI + 单测~~ → DONE（H100 depth_head 套件）
6. ~~STATUS 预检命令~~ → DONE

---

## 6. 一句话

v2 证伪「几何对了但采不到难例、又停不掉 AbsRel/SILog」；v3 用 **hard 缓存保 K、softmin+贴 miss 的 A″、真 pinball B″、P1 双关 AbsRel/SILog、防 init 假早停**，并换用 **⓪b 可过的 holdout(0.35,0)**。

---

## 7. 与 v2 审查条款的继承

| v2 §7 | v3 |
|-------|-----|
| C-1 切法统一 | **已继承**（MATCH assert） |
| C-2 主表=诚实最大切片 | **已继承** |
| C-3 ⓪b / 禁尾切 | **已继承**；切法改为 **frac=0.35 seed=0** + 实测硬门 |
| V 部署≠eval | **仍成立**；本发不修 P0b |
| W / #17 | **点估计** |
| D-2 softmin 温度 | **T=0.05 m**；采样/验收 hard |

---

## 8. 审查附注（2026-08-21；**历史**；不改写当时正文）

> 原审查指出 C-1～C-4 阻塞。**闭合结果见 §1–§2 与 §9**；本节保留审计，不删。

### A. §0 原因核验 — 四条均属实（略，见前次）。

### B. 对症性 — 方向正确。

### C. 当时阻塞（现已闭合）

- **C-1** recipe 0.2/seed0 ⓪b=72 → **已改 0.35/seed0**
- **C-2** `absrel_weight=0` 仍有 `0.5×silog` → **已冻 `silog_weight=0`**
- **C-3** K=8 可能不可达 + 禁静默 fallback → **K=4 + hard 缓存有放回，缓存不足拒训**
- **C-4** init 假饱和 → **`min_steps_before_saturate=100`**

### D. 重要缺口（已部分并入 §1）

- D-1 soft/hard 错配 → 采样/验收 hard，训 soft，兼报 `fwd_hinge_hard`
- D-2 hinge≠miss → 主损失改为 `relu(D̂−trigger)`
- D-3 B″≠全图 ⓪c → 全近带 p90 只报不训
- D-4 consec → 拆腿结案口径写入 §1 D

### E. 一句话（当时）

方向对，当时稿不能开训 → **现稿以 §9 为准可进入实现；开训仍须硬前置实测通过**。

---

## 9. 审查闭合清单（2026-08-21）

| 项 | 处置 |
|----|------|
| C-1 切法 | **冻结 `holdout-frac=0.35`, `split-seed=0`**；开训前老头实测 ⓪b≥100 |
| C-2 silog | **P1 `silog_weight=0`**（与 `absrel_weight=0` 并列） |
| C-3 K | **`K=4` + hard 缓存有放回**；不足拒训；禁止均匀 fallback |
| C-4 假早停 | **`min_steps_before_saturate=100`** |
| D-1/D-2 | soft 训 / hard 验；主 hinge=`relu(D̂−trigger)` |
| D-3/D-4 | 全近带 p90 只报；consec 拆腿结案 |

**下一步**：实现 §5 → 硬前置 → H100。实现前仍不得开训。
