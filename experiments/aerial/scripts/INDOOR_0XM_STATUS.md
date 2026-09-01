# Indoor WAM — STATUS（主航道）

> **更新**：2026-09-01（**E2i.C · S3✅ S1✅ · S2 采集中**）  
> **C 计划**：[`INDOOR_E2I_C_PLAN_20260901.md`](INDOOR_E2I_C_PLAN_20260901.md) · S2：[`INDOOR_E2I_C_S2_PLAN_20260901.md`](INDOOR_E2I_C_S2_PLAN_20260901.md)

## 一句话

**S3 ✅ 主头 B**（@0.50 mean 1.54）。**S1 ✅** 滤 R01 → mean 1.28 / 57%，SPAWN 仍在。**S2** 近场自采（assist=none，d≤1.5，偏 ARRIVE 路由）进行中 → 随后 FT/@0.20。**E3 仍禁**。

## 勾选

| 项 | 状态 |
|----|------|
| **E2i.C S3** A vs B @0.50 | ✅ 主头 **B** · `indoor_e2i_c_s3_compare_050_20260901.json` |
| E2i.C S1 分列 + 滤 R01 | ✅ nospawn mean 1.28 / arr 57% · SPAWN 仍在 |
| E2i.C S2 近场绕障 | 🔄 `run_e2i_c_s2_collect.sh` |
| E2i.B @0.20 | ❌ 仍 FAIL（对照） |
| E3 | ⛔ |

## 对比

| 评测 | seeds 有到点 | mean | 到点率 | 碰撞 / SPAWN |
|------|-------------|------|--------|--------------|
| **S3 B050**（8 路由） | 3/3 | 1.54 | 45.8% | 13/24 · SPAWN 4 |
| **S1 B nospawn**（去 R01） | 3/3 | **1.28** | **57%** | 9/21 · SPAWN **5** |
| S3 A050 | 3/3 | 1.91 | 37.5% | 15/24 · SPAWN 7 |
| B @0.20 | 1/3 | 2.41 | 4% | 19/24 |
