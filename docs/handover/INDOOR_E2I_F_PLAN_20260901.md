# Indoor WAM — E2i.F（合同重钉：主门 @0.50 · 0.20 降级）· 2026-09-01

> **依据**：纯视觉下世界系 0.2 m 作主验收不合理（控制量化≈0.15 m/步、罩 L1≈0.45 m、手飞亦难）；E4b 已证 nospawn 上偶发/部分 @0.20 可达，但不应再当唯一冲刺目标。  
> **前置**：E2i.E — E4 full8 ❌ SPAWN；**E4b nospawn @0.20 ✅** arr≈44%。  
> **仍禁**：盲再 FT；shield-off 完成态；夹具冒充产品；无人令 E3；把 @0.20 写回主完成态。

## 0. 一句话

**主航道室内完成态改钉：干净、可复现的 @0.50 m（nospawn 集）**；**@0.20 仅 stretch / 旁注**；全 8 路由只作 SPAWN 污染对照。

## 1. 合同重钉（冻结）

| 项 | 旧（E2i.* 冲刺） | **新（F）** |
|----|------------------|------------|
| **主验收精度** | `success_dist=0.20` | **`success_dist=0.50`** |
| **主评测集** | 常含 R01（SPAWN）+ R06 | **nospawn：去 R01 + 去 R06**（6 路由） |
| **@0.20** | 合同主门 | **stretch only**；不得单独定义「产品完成」 |
| **全 8 路由** | 常当主报 | **对照 / SPAWN 卫生**；主报不得被其淹没 |
| **位姿** | `gt_proxy`（探针） | **仍探针**；报表强制写明；**≠** 传感合同完成 |
| **飞行核** | `assist=none` + 罩 ON | **不变** |

### 1.1 主门（F-primary）

```text
头：E 头（或 STATUS 钉死的当前主头）
集：building99 nospawn（无 R01、无 R06）· 6×3 seed
assist=none · shield_v3 ON · pose_source=gt_proxy（探针）
success_dist_m = 0.50
Scene 224×224
```

**过门（合取）**：

| # | 条件 |
|---|------|
| G1 | `arrival_rate ≥ 0.50`（≥9/18） |
| G2 | `mean_d_end ≤ 1.0 m` |
| G3 | `collision_rate ≤ 0.50`；且 **arrived 子集 collided=false** |
| G4 | fail_split 落盘；**SPAWN 与 NEAR 分列**（不得只报总撞） |

**不过门**：写失败拆分；**禁止**为过 @0.20 再开短 FT。

### 1.2 Stretch（F-stretch · 旁注）

- 同集、同头、`success_dist=0.20`（即 E4b 协议）  
- 数字可报，标签必须是 **`stretch`**  
- **禁止** stretch PASS ⇒ 主张室内主航道完成

### 1.3 污染对照（F-contam）

- 全 8 路由 @0.50（或 @0.20）仅诊断 SPAWN/坏起点  
- 不进主完成态

## 2. 顺序（死）

```text
F0  本文件 + STATUS/LIVING 入口改钉     ← 本文
F1  主头 @0.50 nospawn 基线（禁 FT）   ← 下一刀
F2  读 G1–G4：过 → 钉「0.5 m 探针水位」；不过 → 只治 SPAWN/NEAR，不冲 0.2
F3  （可选）修 R01 起点后再 F-contam
F4  仅当 F1 过且人令：再议绕障课 / 更大 FT；默认仍禁盲 FT
F5  E3（真 odom）—— 无人令不开；且须在 F1 探针水位之后
```

## 3. F1 命令（125）

```bash
cd /home/yao/aerial-indoor-wam
bash experiments/aerial/scripts/run_e2i_f_primary_050_nospawn_eval.sh
# 可选 stretch 复跑：SUCCESS_DIST=0.20 bash experiments/aerial/scripts/run_e2i_e_nospawn_eval.sh
```

工件预期：

| 路径 | 内容 |
|------|------|
| `artifacts/indoor_e2i_f_050_nospawn_seed{0,1,2}_*.json` | 逐 seed |
| `artifacts/indoor_e2i_f_050_nospawn_summary_*.json` | 汇总 + G1–G4 |
| `artifacts/indoor_e2i_f_050_nospawn_seed*_fail_split.json` | SPAWN/NEAR/ARRIVE |

## 4. 与致命缺陷的关系

| 缺陷 | F 怎么处理 |
|------|------------|
| F1 夹具主料 | 不改；主评仍 `assist=none`；夹具仍 ≤25% 辅料 |
| F2 `gt_proxy` | **明示探针**；完成态句子禁止省略 |
| F3 罩导航 | 已修；F 不重开罩刀 |
| F4 域/精度 | **承认 0.2 过紧** → 主钉 0.5 |
| SPAWN 假题 | **主集 = nospawn**（E4b 已证必要） |

## 5. 禁止误读

- 「E4b @0.20 过了 ⇒ 产品 0.2 完成」—— **否**；那是 stretch + gt_proxy + nospawn。  
- 「主门改 0.5 ⇒ 可以关罩 / 上夹具」—— **否**。  
- 「F1 不过 ⇒ 再 FT 冲 0.2」—— **否**；先拆 SPAWN/NEAR。  
- 「手飞难所以停室内」—— **否**；停的是错误精度钉，不是 Stick 纯视觉航道。

## 6. 签字意图（人令）

| 项 | 意向 |
|----|------|
| 主验收 `0.50` + nospawn | **采纳**（本文） |
| `0.20` 降 stretch | **采纳** |
| 下一执行 = F1 基线评 | **待跑**（禁 FT） |
