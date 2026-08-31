# Indoor WAM — STATUS（主航道）

> **Workspace**：`/home/yao/aerial-indoor-wam`  
> **权威**：`RUNBOOK_indoor_0xm.md` §8.9 **E2i**  
> **分析+计划**：[`INDOOR_E2I_PLAN_20260831.md`](INDOOR_E2I_PLAN_20260831.md) **v2**  
> **致命缺陷**：[`INDOOR_FATAL_DEFECTS_20260831.md`](INDOOR_FATAL_DEFECTS_20260831.md)  
> **更新**：2026-08-31

## 一句话

E2h ❌ 结案。**dt 已修；F1/F2 ✅**（v3 interv **0.048**≪0.5，d_end↓47.8%）。**E2i.1 正式过 → 解禁 B1**。致命残留见缺陷文档 F1/F2/F4。禁 E3。

## 勾选

| 项 | 状态 |
|----|------|
| E2h | ❌ 场景合格；合同/shield-off 见计划 §8 |
| **E2i.0** 计划 v2 落盘 | ✅ |
| **E2i.0w** yaml 罩 + 近成功接线 | ✅ |
| **E2i.1** 室内罩 A/B | ✅ **post-dtfix**：v3 vs baseline — interv **0.048 vs 0.706**；d_end↓**47.8%**；gate 全过。summary `artifacts/indoor_shield_ab_summary_post_dtfix_20260831.json` |
| **E2i.1b** shield_v3 | ✅ 并入 F2（new=v3） |
| **E2i.diag** 介入通道 | ✅ 根因 dt；修后 F1 interv=**0.00×4** |
| **E2i.dtfix** | ✅ F0/F1/F2 全过；方案 [`INDOOR_E2I_DTFIX_PLAN_20260831.md`](INDOOR_E2I_DTFIX_PLAN_20260831.md) |
| **F1** 通道诊断 post-dtfix | ✅ interv=0.00×4；`indoor_shield_channel_diag_v3_post_dtfix_20260831.json` |
| **F2** 罩 A/B post-dtfix | ✅ gate_intervention_lt_0_5 + gate_d_end_improve_gt_30pct |
| **E2i.2a** B2 夹具 @0.20 | ✅ **34 arrived** |
| **E2i.2b** B1 | 🔄 **采集中** — assist=none + v3 + keep-near-success≤1.0 + drop-collided；目标 usable≥50 / 120 ep → `dataset_indoor_b99_none_near_20260831`；log `logs/e2i_b1_none_near_20260831.log` |
| **E2i.3** C1 短 FT @0.50 @4090 | ⬜ |
| **E2i.4** C1/C2 H100 长 FT | ⬜ |
| E3 | ⛔ 禁止 |

## E2h 结案数字（引用）

| 评测 | 结果 |
|------|------|
| E2h.4 合同 @0.20 罩 ON | 0/3；best min≈1.78 m |
| shield-off diag @0.20 | 0/3；best **0.63 m collided** |
| 语料 | `dataset_indoor_building99_e2h_20260830` — **101 NPZ**（夹具 @0.50 为主） |

## E2i v2 要点

- **顺序**：E2i.1 过门前 **禁止 B1**；B2 可与 E2i.1 并行  
- **B1 必须** `--annotation building99_indoor_short_routes.json`  
- **B2 无** `max-intervention-rate`（夹具无罩）  
- **FT** `--skip-collect` 不占 AirSim；eval/采集占  

## 运维

- 切换：`experiments/aerial/scripts/recover_renderer_scene.sh {blocks|building99|outdoor|stop}`
- 室内 settings：`configs/airsim_settings_indoor.json` → `~/aerial_airsim_persistent/AirSim/settings_indoor.json`
- 125 prompt：[`INDOOR_MAINLINE_125_PROMPT_20260831.md`](INDOOR_MAINLINE_125_PROMPT_20260831.md)
