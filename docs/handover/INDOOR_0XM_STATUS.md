# Indoor WAM — STATUS（主航道）

> **更新**：2026-09-02（**主航道收口** · F-cap ✅ · E3 formal odom **deferred**）  
> **E3 结论**：管线 ✅ · post-FT G1 ❌ · velfix 审计 east **2/3 arr_hat** · formal east odom summary **deferred**（sim SPAWN hygiene，**非门**）  
> **主门**：[`INDOOR_E2I_F_PLAN_20260901.md`](INDOOR_E2I_F_PLAN_20260901.md) §1.1 F-cap  
> **干净集 east**：`building99_indoor_short_routes_clean_e.json`（125 可 `cp` 至 `artifacts/`）  
> **125 handoff（归档）**：[`INDOOR_E3_125_PROMPT_20260902.md`](INDOOR_E3_125_PROMPT_20260902.md)  
> **缺口续作**：[`INDOOR_GAP_CONTINUATION_20260902.md`](INDOOR_GAP_CONTINUATION_20260902.md)（12 项 · 产品 0/12）

## 一句话

**主完成态 = F-cap**：east_from_1 @0.50 · gt_proxy 探针 · **non-SPAWN ep 过 G1–G4**。SPAWN（含 sim 贴地 / 动线占用）**旁注不过门**；west/south/full8 进 **F-hygiene**。**E3 传感轨已 landing velfix，formal 评 deferred，不阻塞 close。**

## 勾选

| 项 | 状态 |
|----|------|
| F1–F1e legacy | ✅ 已跑 · legacy **FAIL**（SPAWN 打穿 G2） |
| east 能力 | ✅ F1d/F1e **6/6 到点**（d≈0.41–0.49） |
| **F2-cap east** | ✅ **PASS**（3/3 到点 · mean_d≈0.45 · spawn 0） |
| **F-collect east** | ✅ 39 usable @0.50 gt_proxy |
| **E3 管线 E3.0–E3.3** | ✅ 已跑 · post-FT G1 ❌（odom hat 全灭，根因已定位） |
| **E3 velfix + E3.5 审计** | ✅ east drift 0.93→0.11 m · **2/3 arr_hat** |
| **E3 formal odom east** | ⏸ **deferred** — sim east SPAWN（gt_proxy 探针亦首步撞）；**非门** |
| spawn watch | ⏸ 可选后台（125）；**不阻塞 close**；绿了可补 summary |
| **缺口续作序 2 F10** | ⏳ west/south hygiene 探针（125 · 不过门） |

## 收口（2026-09-02）

- **可 close**：F-cap 主完成态已满足；E3 估器修复已合入 `main`（`pose_estimate` velfix + 脚本/handoff）。  
- **刻意不收口**：`artifacts/indoor_e2i_e3_odom_east_sg_velfix_050_summary_*` — 等 sim 可飞时手动或 watch 补跑。  
- **禁止**：spawn 死磕当 blocker；gt_proxy 冒充 E3 传感完成；无人令盲 FT。

## Legacy 对照（不过门）

| 轮次 | legacy pass | 备注 |
|------|-------------|------|
| F1c clean_sg | ❌ arr 67% | west SPAWN×3 |
| F1d south+east | ❌ arr 50% | south 回归 SPAWN |
| F1e + spawn retry | ❌ arr 67% | west 仍 SPAWN |

## Hygiene backlog（不过门）

- east：~11:05 起 intermittent SPAWN（gt/odom 同现）· watch 可选  
- west：静态贴地 ~10–20% · 探针 `indoor_west_collision_probe`  
- south：F1c 绿 → F1d 全 SPAWN（待查）  
- 动态人动线：部署 hold/换点；不进 F-cap
