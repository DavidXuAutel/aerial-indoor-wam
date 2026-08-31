# 125 Agent：E2i — 罩重标定 + 近成功语料 + 分阶 FT

> **Workspace**：`/home/yao/aerial-indoor-wam`  
> **权威**：[`INDOOR_E2I_PLAN_20260831.md`](INDOOR_E2I_PLAN_20260831.md) · `RUNBOOK_indoor_0xm.md` §8.9  
> **前置**：E2h FAIL（101 NPZ + re-FT 仍 0/3 @0.20）；shield-off best 0.63 m  

## 铁律

- 完成态：**罩 ON**、`assist=none`、forbid GT、pose 声明  
- 夹具/GT-PD **仅 BC 辅轨**；禁当默认飞行核  
- 禁 E3；禁关罩刷分；禁再堆 0.50 BC 冒充进展  
- 室内占用 `:41451` 后须 `recover_renderer_scene.sh outdoor` 归还 Phase-2  

## 必做顺序

### E2i.1 — 室内罩重标定

1. 分析 Building_99 intervention 逐步曲线 + depth 分布  
2. 出一版 indoor `ThreeZoneSpec`（yaml/config 分支，须落盘参数）  
3. 同 `e2h4` ckpt、同路由 A/B：旧罩 vs 新罩（**不重训**）  
4. 过门：intervention_mean <0.5 且 mean d_end vs E2h.4 改善 >30%  

### E2i.2 — 语料双轨

- **B1**：`assist=none`，3 m，保留 d_end<1.0 m 近成功，≥50 usable  
- **B2**：夹具 `gt_pd_body`，`success=0.20`，`max-intervention=0`，≥20 arrived  
- 见计划文档 §5 E2i.2 命令模板  

### E2i.3 — C1 @4090

- init=e2h4 或 outdoor；B1 主 + B2≤30%；`success_dist=0.50`；500 iter  
- 评：Building_99 × 3 seed @0.50  
- 过门：≥2/3 seed 到点或 mean≤1.0 m  

### E2i.4 — H100 长 FT（C1/C2）

- C1：2000+ iter；C2：1000+ iter，主料 B2@0.20  
- 合同：≥2/3 seed @0.20 或 mean≤0.8 m  

## 汇报

更新 `INDOOR_0XM_STATUS.md` + `LIVING_DOCS.md` A0；`/tmp/indoor_mainline_125_report.md`。
