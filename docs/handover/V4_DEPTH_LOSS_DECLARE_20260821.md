# V4 深度 loss 改法 — 跑前声明（2026-08-21）

> **状态**：v1 **已跑、未过线**（归档）。→ 继任声明见 [`V4_DEPTH_LOSS_DECLARE_v2_20260821.md`](V4_DEPTH_LOSS_DECLARE_v2_20260821.md)。  
> **本文件不改写**；仅作审计链与失败依据。

---

## 1. 为什么现在才改

同一次 FT 跑：全 mask holdout AbsRel **0.1127**（①d 好看）与近场 ⓪c/d 坏同时出现；控制臂同域 **⓪a median PASS + ⓪c p90 FAIL**。  
⇒ 「逐像素对称均值管不住近场功能量」已是实测，不是假设。

⓪d 判 `D̂_forward` ⇒ **无 L0 argmin / shield 消费路径退路**，只能修感知。

---

## 2. 改什么（对齐判据；对 ①d 全 mask 中性）

| # | 对准 | 改法 | 默认 | 本轮 FT 拟用 |
|---|------|------|------|----------------|
| A | ⓪d 过读漏触发 | 近带 **单侧 hinge**：只罚 `(D̂−GT)/GT` 的正部（`D̂>GT`） | weight=0（关） | `near_overread_hinge_weight=3.0` |
| B | ⓪c p90 尾巴 | 近带 **pinball**（τ=0.9）作用于 signed relative `(D̂−GT)/GT`：过读权重 τ、欠读权重 1−τ | weight=0（关） | `near_absrel_pinball_weight=2.0`, `tau=0.9` |
| C | consec≥2 | **不**改 shield 滞回（eval 不跑罩，滞回过不了 ⓪d）。本轮指望 A/B 降低漏帧后 consec 自然掉；若 rate 已过而 consec 仍挂 → **另案**声明 D̂ 时序平滑（须 eval 同口径） | — | 本轮不做 |

保留既有：全 mask AbsRel + SILog + NLL；对称 `near_weight` AbsRel **本轮 FT 降为 0**（避免与 A/B 叠成对称均值主导）。`near_focus_m=5.0` 不变。

---

## 3. 怎么训 / 怎么验

- **机**：深度 FT **只在 H100**（不要 4090 / cursor-125）。4090 留给渲染 / rollout / 采集。
- **init**：`depth_ckpt_da3_r60_20260814/depth_step_2000_da3_ft_head.pt`（部署老头；新 p45 头不用）
- **语料**：`dataset_v0_p45_merged_20260821`
- **holdout 训**：`--holdout-frac 0.2`（①d）
- **验收 ⓪**：`v4_zero_eval --heldout-frac 0.2`（与 depth 训同一尾部纪律）
- **过线**：held-out 上 ⓪b 仍过；⓪c p90≤0.50；⓪d miss≤0.05 **且** `max_consecutive_miss<2`；①d holdout AbsRel 仍 ≤0.30（中性检查）
- **失败**：归档 ckpt，**禁止**无新声明再训；不降阈值

控制臂重 emit（`n_near_forward_frames`）可与训并行；不阻塞本声明。

> **注（2026-08-21）**：本轮 hinge+pinball 首发误开在 4090（PID 3410491）；**下次及以后深度训一律 H100**。

---

## 4. 明确不做什么

- 不用对称 `near_weight` 再盲 FT  
- 不用 shield 滞回冒充修 ⓪d consec  
- 不把 in-sample / `heldout-frac=0` 的 PASS 当权威  
- 不改 trigger / p90 / miss 阈值凑过  
- 新头未过 ⓪c/d 前不进部署、不重跑 ④ 冒充安全

---

## 5. 代码落点

- `dynamics_torch.depth_head_loss`：新增 A/B 项（weight=0 时行为与改前逐字节兼容）
- `train_depth_head` / yaml：透传超参
- 本文件 + `V4_RUNBOOK_125_STATUS.md` / `V4_GATE_STATUS.md` 变更记录
