# Indoor WAM — E2i.D（夹具绕障 + none 近场自采）· 2026-09-01

> **人令**：确定，按夹具示范 + none 自采方式采数据  
> **前置**：E2i.C S2 ❌ — 自采 ≤1.5 m 不能教绕障；@0.20 仍 FAIL  
> **仍禁**：夹具成绩当产品完成；shield-off；E3；B2 mix >25%

## 目标

采 **对题、同构、可进 mix** 的料，供后续短 FT（D4 待人令，本刀只采）。

| 桶 | assist | 路由 | 保留条件 | 目标量 |
|----|--------|------|----------|--------|
| **D1 夹具绕障** | `gt_pd` | R06 加权 + R02/R08 NEAR；**跳过 R01** | `arrived_gt` @ **0.25 m**；无 chronic SPAWN | **≥15 usable** |
| **D2 none 近场** | `none` | R03–R07 ARRIVE 区；**跳过 R01/R02** | `d_end≤0.30 m`、无撞 | **≥50 usable** |

## 顺序

```text
D0  本文件 + 脚本
D1  run_e2i_d_fixture_avoid_collect.sh
D2  run_e2i_d_none_near_collect.sh
D3  mix：D2 none ≥75% + D1 fixture ≤25% → `dataset_indoor_e2i_d_*`
D4  FT + @0.20 评 — `run_e2i_d_ft_eval.sh`（人令：继续）
```

## 过门（采完 D1+D2）

- D1：`n_usable ≥ 15`（本轮 **58**；R06 detour 仍 0，记缺口）
- D2：`n_usable ≥ 50`（本轮 **56** @0.50；原 @0.30 产量≈0）
- 评测合同不变：**assist=none** @0.20

## 工件

| 路径 | 内容 |
|------|------|
| `dataset_indoor_b99_fixture_avoid_20260901` | D1 · 58 |
| `dataset_indoor_b99_none_near_d_20260901` | D2 · 56 |
| `dataset_indoor_e2i_d_20260901` | D3 mix |
| `v4_ac_ckpt_indoor_e2i_d_20260901` | D4 π |
| `artifacts/indoor_e2i_d_020_summary_20260901.json` | @0.20 汇总 |
