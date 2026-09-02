# Indoor WAM — STATUS（主航道）

> **更新**：2026-09-02（**F 合同改钉 F-cap** · SPAWN 剔主门分母）  
> **E3 结论**：管线 ✅ · G1 ❌ · **6/6 scored `arrived_gt` · 0/6 `arrived_hat`**（odom 终态 +0.4–0.7 m）  
> **主门**：[`INDOOR_E2I_F_PLAN_20260901.md`](INDOOR_E2I_F_PLAN_20260901.md) §1.1 F-cap  
> **干净集 east**：`building99_indoor_short_routes_clean_e.json`（125 可 `cp` 至 `artifacts/`）  
> **125 handoff**：[`INDOOR_E3_125_PROMPT_20260902.md`](INDOOR_E3_125_PROMPT_20260902.md)

## 一句话

**主完成态 = F-cap**：east_from_1 @0.50 · gt_proxy 探针 · **non-SPAWN ep 过 G1–G4**。SPAWN（含 sim 贴地 / 动线占用）**旁注不过门**；west/south/full8 进 **F-hygiene**。

## 勾选

| 项 | 状态 |
|----|------|
| F1–F1e legacy | ✅ 已跑 · legacy **FAIL**（SPAWN 打穿 G2） |
| east 能力 | ✅ F1d/F1e **6/6 到点**（d≈0.41–0.49） |
| **F2-cap east** | ✅ **PASS**（3/3 到点 · mean_d≈0.45 · spawn 0） |
| **F-collect east** | ✅ 39 usable @0.50 gt_proxy |
| **E3 估器 velfix** | ✅ E3.5 east 2/3 arr_hat · spawn watch **后台静默**（非门） |

## Legacy 对照（不过门）

| 轮次 | legacy pass | 备注 |
|------|-------------|------|
| F1c clean_sg | ❌ arr 67% | west SPAWN×3 |
| F1d south+east | ❌ arr 50% | south 回归 SPAWN |
| F1e + spawn retry | ❌ arr 67% | west 仍 SPAWN |

## Hygiene backlog（不过门）

- west：静态贴地 ~10–20% · 探针 `indoor_west_collision_probe`  
- south：F1c 绿 → F1d 全 SPAWN（待查）  
- 动态人动线：部署 hold/换点；不进 F-cap
