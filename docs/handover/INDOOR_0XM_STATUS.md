# Indoor WAM — STATUS（主航道）

> **更新**：2026-09-02（F-cap ✅ · **E3 仿真 hat 签 C 归档** · spawn z=1.8 · **开源 VIO 孤立探针脚手架**）  
> **E3（签 C）**：formal z18 **双报** spawn=0 · **3/3 gt** · **1/3 hat** · G1 **未过**；**停追** sim odom CE / 盲 FT；估器重开 = **开源 VIO 或真机**（人令）  
> **VIO 孤立轨**：[`INDOOR_VIO_OPENSOURCE_PROBE_20260902.md`](INDOOR_VIO_OPENSOURCE_PROBE_20260902.md)（OpenVINS · **不**占 AirSim / **不**改 F-cap 默认）  
> **主门**：[`INDOOR_E2I_F_PLAN_20260901.md`](INDOOR_E2I_F_PLAN_20260901.md) §1.1 F-cap  
> **干净集 east**：`building99_indoor_short_routes_clean_e.json`（z=1.8 · `spawn_z_floor_cmd_m=1.8`）  
> **125 handoff（归档）**：[`INDOOR_E3_125_PROMPT_20260902.md`](INDOOR_E3_125_PROMPT_20260902.md)  
> **E3 计划**：[`INDOOR_E3_PLAN_20260902.md`](INDOOR_E3_PLAN_20260902.md) §11 签 C  
> **缺口续作**：[`INDOOR_GAP_CONTINUATION_20260902.md`](INDOOR_GAP_CONTINUATION_20260902.md)（12 项 · 产品 0/12）

## 一句话

**主完成态 = F-cap**：east_from_1 @0.50 · gt_proxy 探针 · **non-SPAWN ep 过 G1–G4**。SPAWN **旁注不过门**。**E3 传感完成态 = 未宣称**：仿真 `arrived_hat` G1 未过且 **签 C 停追**；报表 **强制双报 gt/hat**，禁止用 gt 冒充 E3。

## 勾选

| 项 | 状态 |
|----|------|
| F1–F1e legacy | ✅ 已跑 · legacy **FAIL**（SPAWN 打穿 G2） |
| east 能力 | ✅ F1d/F1e **6/6 到点**（d≈0.41–0.49） |
| **F2-cap east** | ✅ **PASS**（3/3 到点 · mean_d≈0.45 · spawn 0） |
| **F-collect east** | ✅ 39 usable @0.50 gt_proxy |
| **E3 管线 E3.0–E3.3** | ✅ 已跑 · post-FT G1 ❌（odom hat） |
| **E3 velfix + E3.5 审计** | ✅ east drift 0.93→0.11 m · 审计 **2/3 arr_hat** |
| **E3 formal odom east** | 📦 **签 C 归档** — z18 双报：gt **3/3** · hat **1/3** · G1 未过 · **非传感完成** |
| spawn watch | ⏸ 可选；**不阻塞**；不作为 E3 重开条件 |
| **缺口续作序 6 F6** | ✅ F3 south cap **PASS**（z18）— 3/3 arr · spawn_rate=0 · mean_d≈0.47 · gt_proxy |
| **缺口续作序 7 F1** | ⚠️ 审计：E mix **fixture_frac=0.25**；F-collect 39ep **assist=none** |
| **缺口续作序 9 F7** | ✅ stretch @0.20 nospawn — **arr 44%** · mean_d≈1.24 · **stretch 旁注** |
| **spawn fix 验证** | ✅ east/south PASS；**west z18** policy step0–4 不撞（fix 前 step0 撞） |

## 收口（2026-09-02）

- **可 close**：F-cap 主完成态；spawn 工程修复（不过产品 3 日稳定门）。  
- **E3 签 C**：停止仿真 odom 积分/标定/E3.2′ 盲追；权威双报工件 `artifacts/indoor_e2i_e3_odom_east_velfix_050_summary_20260902_z18.json`。  
- **禁止**：gt_proxy / `arrived_gt` 冒充 E3 传感完成；无人令盲 FT；再开 sim CE 兔洞。  
- **估器重开（人令）**：开源 VIO → `vio_est`，或真机实测轨。  
- **VIO 孤立探针（2026-09-02）**：选型 **OpenVINS**；仓内 `experiments/aerial/vio_probe/` + `pose_source=vio_est` 需 `AERIAL_VIO_TRAJ`（**不再**静默 alias odom）。下一步 = 空闲机编 OpenVINS + 真 npz 跑 P1（**勿**打断在跑 E2i/F）。

## Legacy 对照（不过门）

| 轮次 | legacy pass | 备注 |
|------|-------------|------|
| F1c clean_sg | ❌ arr 67% | west SPAWN×3 |
| F1d south+east | ❌ arr 50% | south 回归 SPAWN |
| F1e + spawn retry | ❌ arr 67% | west 仍 SPAWN |

## Hygiene backlog（不过门）

- **spawn fix 20260902** ✅：hold + XY nudge；**显式出生高度** `spawn_z_floor_cmd_m=1.8` + 注解 z=1.8  
- west：旧 floor 下沉归因已对上；可选再跑 west probe  
- 动态人动线：部署 hold/换点；不进 F-cap
