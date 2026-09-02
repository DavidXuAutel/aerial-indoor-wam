# Indoor WAM — STATUS（主航道）

> **更新**：2026-09-02 · **Stick 主航道 CLOSED**  
> **关闭声明**：[`INDOOR_STICK_CLOSE_20260902.md`](INDOOR_STICK_CLOSE_20260902.md)  
> **下一项目**：[`aerial-vgoal-wam`](../../../aerial-vgoal-wam/) 室内语义导航 · [`2026-09-02-indoor-semantic-nav-design.md`](../../../aerial-vgoal-wam/docs/superpowers/specs/2026-09-02-indoor-semantic-nav-design.md)  
> **E3（签 C）**：z18 双报 gt 3/3 · hat 1/3 · G1 未过 · **停追** sim odom  
> **主门（已过）**：F-cap east @0.50 · gt_proxy · [`INDOOR_E2I_F_PLAN_20260901.md`](INDOOR_E2I_F_PLAN_20260901.md) §1.1  
> **缺口表**：[`INDOOR_GAP_CONTINUATION_20260902.md`](INDOOR_GAP_CONTINUATION_20260902.md)（产品仍 0/12 · **不再作为本仓默认下一刀**）

## 一句话

**Stick 室内主航道 close**：F-cap ✅ · spawn/SE 探针 ✅ · E3 签 C 归档。**不**写产品结案。后续语义搜+飞 → **`aerial-vgoal-wam`**（另立项目）。

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
| **缺口续作序 6 F6** | ✅ south 单路由 + **SE 联合** F-cap **PASS**（z18）— 6/6 arr · spawn=0 · gt_proxy |
| **缺口续作序 7 F1** | ⚠️ 审计：E mix **fixture_frac=0.25**；F-collect 39ep **assist=none** |
| **缺口续作序 9 F7** | ✅ stretch @0.20 nospawn — **arr 44%** · mean_d≈1.24 · **stretch 旁注** |
| **spawn fix 验证** | ✅ east/south PASS；**west z18** policy step0–4 不撞（fix 前 step0 撞） |

## 收口（2026-09-02）

- **可 close**：F-cap 主完成态；spawn 工程修复（不过产品 3 日稳定门）。  
- **E3 签 C**：停止仿真 odom 积分/标定/E3.2′ 盲追；权威双报工件 `artifacts/indoor_e2i_e3_odom_east_velfix_050_summary_20260902_z18.json`。  
- **禁止**：gt_proxy / `arrived_gt` 冒充 E3 传感完成；无人令盲 FT；再开 sim CE 兔洞。  
- **估器重开（人令）**：真机采集+真标定 → `vio_est`（sim thrifty 已归档）。  
- **VIO thrifty（2026-09-02）**：📦 **签过归档** — S1/S2 ✅（ATE **3.13 m** ≤5）· 停追 AirSim ZOH/占位标定 · 非产品 VIO。见 [`INDOOR_VIO_THRIFTY_ARCHIVE_20260902.md`](INDOOR_VIO_THRIFTY_ARCHIVE_20260902.md)。

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
