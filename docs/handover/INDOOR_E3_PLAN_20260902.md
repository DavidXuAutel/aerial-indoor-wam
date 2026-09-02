# Indoor WAM — E3 全量（odom 同构）· 2026-09-02

> **前置**：F2-cap ✅（gt_proxy 探针）；F-collect east 39 usable ✅  
> **人令**：推全量 E3  
> **仍禁**：盲 FT；关罩完成态；gt_proxy 冒充 E3 完成

## 0. 一句话

**E3 = clean_sg 三路由 · `odom_from_imu_rgb` 闭环采 → H100 同构 FT → 125 odom @0.50 回归（F-cap 口径：SPAWN 剔分母）**

## 1. 路由集

| 标注 | 路由 |
|------|------|
| `building99_indoor_short_routes_clean_sg.json` | west / south / east_from_1 |

采集：`--drop-collided` · `--keep-arrived-only` · `@0.50` · spawn retry=3

## 2. 顺序

```text
E3.0  odom 基线评（E 头未 odom-FT）     run_e2i_e3_odom_eval.sh BASELINE=1
E3.1  odom 闭环采集 min_usable≥30       run_e2i_e3_odom_collect.sh
E3.2  H100 π FT train=eval=odom         run_e2i_e3_h100_ft.sh
E3.3  odom 回归 @0.50 F-cap             run_e2i_e3_odom_eval.sh ACTOR=<E3 ckpt>
```

## 3. E3 过门（F-cap · scored 子集）

| # | 条件 |
|---|------|
| G1 | `arrival_rate_scored ≥ 0.50` |
| G2 | `mean_d_end_scored ≤ 1.0 m` |
| G3 | scored 子集无 arrived+collided |
| 旁注 | `spawn_rate` · legacy 全 ep 对照 |

**不过门**：写拆分；**禁止**回 gt_proxy 主完成态。

## 4. 命令（125 / H100）

```bash
# 125 — 一键管线（采集中不含 H100）
bash experiments/aerial/scripts/run_e2i_e3_pipeline_125.sh

# H100 — E3.2（dataset rsync 后）
bash experiments/aerial/scripts/run_e2i_e3_h100_ft.sh

# 125 — 采完后自动 FT+eval
bash experiments/aerial/scripts/run_e2i_e3_auto_after_collect.sh
```

## 5. 工件

| 阶段 | 路径 |
|------|------|
| 采集 | `dataset_indoor_e3_odom_050_<STAMP>/` |
| 基线 | `artifacts/indoor_e2i_e3_odom_baseline_summary_*.json` |
| E3 评 | `artifacts/indoor_e2i_e3_odom_cap_summary_*.json` |
| ckpt | `v4_ac_ckpt_indoor_e3_odom_<STAMP>/` |

## 6. E3 结论（2026-09-02）

| 项 | 结果 |
|----|------|
| 管线 | E3.0–E3.3 ✅ |
| F-cap | **FAIL G1** · G2/G3 ✅ |
| 根因 | **`arrived_hat` 全灭**；scored 6 ep 全 **`arrived_gt=True`**（d_gt≈0.38–0.50）但 d_hat≈0.83–1.14 |
| 含义 | π 在 GT 下能到点；**odom 终态误差** 打穿 @0.50 _hat 门，非「不会飞」 |
| 主门 | **不变**：F-cap east · gt_proxy 探针（F2-cap ✅） |

## 7. 下一步（E3 后）

1. **E3.5 逐步审计**（125）：`run_e2i_e3_pose_step_audit.sh` · routes 1,2 · seeds 0–2  
2. **估器轨**（优先）：修/标定 `odom_from_imu_rgb` 终态 CE，再决定是否二轮 FT  
3. **合同轨**（备选）：E3-cap-east-only + 双报 gt/hat；**禁止**用 gt 冒充 E3 主完成  
4. **仍禁**：spawn 死磕；盲加 iters；gt_proxy 写 E3 完成态

## 8. E3.4 诊断（2026-09-02）

```bash
bash experiments/aerial/scripts/run_e2i_e3_odom_gap_diag.sh
```

| 指标 | 值 |
|------|-----|
| scored eval ep | **12/12 `ARRIVE_GT_ONLY`**（真到了 · hat 判未到） |
| mean **d_hat − d_gt** | **+0.68 m**（hat 以为更远） |
| Route_02 / Route_03 gap | +0.44 / +0.92 m |
| 采集 NPZ 离线重放 pos_err | mean **0.94 m** · p90 **1.31 m** |

工件：`artifacts/indoor_e2i_e3_odom_gap_diag_20260902.json`

## 9. E3.5 逐步审计（2026-09-02）

```bash
bash experiments/aerial/scripts/run_e2i_e3_pose_step_audit.sh
```

| 路由 | mean Δerr/步(warmup) | mean 累积 drift | arr_gt / arr_hat |
|------|----------------------|-----------------|------------------|
| route_1 south | **0.51 m** ❌ | 1.20 m | 2/3 · 0/3 |
| route_2 east | 0.13 m | 0.93 m | 3/3 · 0/3 |

**结论**：route_1 **逐步积分坏**（首步 spawn 亦贡献）；route_2 逐步误差尚可但 **累积 drift ~0.9 m** 仍打穿 @0.50 hat 门 → **修 `pose_estimate` 再 FT**。

工件：`artifacts/indoor_e2i_e3_pose_step_audit_20260902.json`

## 10. 估器修复 velfix（2026-09-02）

**根因**：积分 **command action** 而非 **实际 velocity**（单步实现 ~1/3）。

**改法**：`pose_estimate.py` — 有 `obs.velocity` 时用 **`velocity × dt`** 更新 XY。

| 指标 | 修前 | 修后（E3.5 复跑） |
|------|------|-------------------|
| east drift | 0.93 m | **0.11 m** |
| east mean Δerr/步 | 0.13 m | **0.019 m** |
| east arr_hat | 0/3 | **2/3** |
| south drift | 1.20 m | 0.56 m |
| south arr_hat | 0/3 | **2/3** |

**待办**：`run_e2i_e3_east_spawn_watch.sh` **后台静默**（非 blocker）— east 能飞时补 formal summary；**不过门**。
