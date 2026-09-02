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

### 1.1 主门（F-cap · **2026-09-02 冻结**）

**能力门**：评 WAM 会不会飞、能不能 @0.50；**不把 SPAWN 算进主门分母**。

```text
头：E 头（v4_ac_ckpt_indoor_e2i_e_20260901）
集：F2-cap = east_from_1 单路由 · 1×3 seed = 3 scored eps（无 SPAWN 时）
assist=none · shield_v3 ON · pose_source=gt_proxy（探针）
success_dist_m = 0.50 · Scene 224×224
```

**SPAWN 定义**（与 fail_split 一致）：`collided && steps ≤ 8`。

**过门（合取 · 仅 non-SPAWN 子集）**：

| # | 条件 |
|---|------|
| G1 | `arrival_rate_scored ≥ 0.50` |
| G2 | `mean_d_end_scored ≤ 1.0 m` |
| G3 | `collision_rate_scored ≤ 0.50`；且 **arrived 子集 collided=false** |
| G4 | fail_split 落盘；**spawn_rate 旁注**（不过门） |

**旁注（必报、不过门）**：`spawn_rate`、`spawn_collision_n`、`gates_legacy_all_eps`（全 ep 旧口径，供对照）。

**不过门**：写失败拆分；**禁止**为过 @0.20 再开短 FT；**禁止**为压 spawn 无限改路由/擦 sim。

### 1.1b 旧主门（F-legacy · 归档对照）

全 ep 进分母（F1–F1e 已跑）。**west/south SPAWN 会打穿 G2** → 不再作为完成态门槛。

### 1.2 Stretch（F-stretch · 旁注）

- 同集、同头、`success_dist=0.20`（即 E4b 协议）  
- 数字可报，标签必须是 **`stretch`**  
- **禁止** stretch PASS ⇒ 主张室内主航道完成

### 1.3 卫生对照（F-hygiene · 不过门）

- clean_sg（west/south/east）、full8、spawn 率、静态审计  
- **动态人 / sim 贴地** 导致的概率 SPAWN → 只进 hygiene，**不进 F-cap 分母**

## 2. 顺序（死）

```text
F0  本文件 + STATUS/LIVING 入口改钉
F1–F1e  legacy 全 ep 基线（已跑 · 对照）
F2  F-cap east @0.50 + spawn 剔分母          ← 现行主门
F3  （可选）扩路由 south；west 仅 hygiene
F4  仅当 F2 过且人令：再议课 / FT；默认仍禁盲 FT
F5  E3（真 odom）—— 无人令不开；且须在 F2 探针水位之后
```

## 3. F2-cap 命令（125）

```bash
cd /home/yao/aerial-indoor-wam
bash experiments/aerial/scripts/run_e2i_f2_cap_050_eval.sh
# 重算已有 seed（不跑 sim）：GATE_MODE=cap TAG=... STAMP=... \
#   $AERIAL_PY experiments/aerial/scripts/indoor_e2i_f_summary.py ...
```

工件预期：

| 路径 | 内容 |
|------|------|
| `artifacts/indoor_e2i_f2_cap_050_east_seed{0,1,2}_*.json` | 逐 seed |
| `artifacts/indoor_e2i_f2_cap_050_east_summary_*.json` | F-cap 汇总 + legacy 对照 |

## 4. 与致命缺陷的关系

| 缺陷 | F 怎么处理 |
|------|------------|
| F1 夹具主料 | 不改；主评仍 `assist=none`；夹具仍 ≤25% 辅料 |
| F2 `gt_proxy` | **明示探针**；完成态句子禁止省略 |
| F3 罩导航 | 已修；F 不重开罩刀 |
| F4 域/精度 | **承认 0.2 过紧** → 主钉 0.5 |
| SPAWN 假题 | **F-cap：SPAWN 剔分母 + 旁注**；hygiene 集继续诊断 |

## 5. 禁止误读

- 「E4b @0.20 过了 ⇒ 产品 0.2 完成」—— **否**；那是 stretch + gt_proxy + nospawn。  
- 「主门改 0.5 ⇒ 可以关罩 / 上夹具」—— **否**。  
- 「F1 不过 ⇒ 再 FT 冲 0.2」—— **否**；先拆 SPAWN/NEAR。  
- 「手飞难所以停室内」—— **否**；停的是错误精度钉，不是 Stick 纯视觉航道。

## 6. 签字意图（人令）

| 项 | 意向 |
|----|------|
| 主验收 `0.50` + F-cap east | **采纳**（2026-09-02） |
| `0.20` 降 stretch | **采纳** |
| F1 基线评 | ✅ **FAIL legacy G2**（arr 61%；北向脏） |
| F1c / F1d / F1e | ✅ legacy **FAIL**；east **6/6 到点**；SPAWN 单列 |
| **F2-cap** east @0.50 spawn 剔分母 | **现行主门** → `run_e2i_f2_cap_050_eval.sh` |
| F1b 去北向 | 已废 → 审计 clean_sg |
