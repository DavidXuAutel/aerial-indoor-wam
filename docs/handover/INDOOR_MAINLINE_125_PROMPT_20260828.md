# 125 Agent：E2g — 新规格夹具 BC（success=0.20）

> **Workspace**：`/home/yao/aerial-indoor-wam`  
> **权威**：`RUNBOOK_indoor_0xm.md` §8.7  
> **人令**：加新规格数据；FT@4090；**禁 E3**；禁关罩。

## 背景

E2f FAIL：20 条 **0.50** 进圈 BC + FT 后，合同 @0.20 仍 0/3（最佳 mean≈0.90 m）。  
诚实下一刀：**合同同规格** `success=0.20` 正例 + 过滤高罩介入 → 同脑 FT → `assist=none`。

## 铁律

- 采集：可 `assist=gt_pd` + `--allow-gt-assist`（**仅 BC**）  
- 评测：**必须** `assist=none`、forbid GT、罩 ON、pose 声明  
- meta：`bc_from=fixture_gt_pd_020`、`success_dist_m=0.20`  
- 禁把夹具到点率写进完成态；禁 E3；禁再堆 0.50 BC 冒充进展

## 必做

### E2g.0 — 先等 AirSim 空闲

```bash
bash experiments/aerial/scripts/wait_airsim_idle.sh --timeout-sec 7200
# Phase-2 后若 gt_pd yield≈0：跑 recover_renderer.sh 再采
```

禁止为抢机杀 Phase-2。

### E2g.1 采新规格成功示范

```bash
source experiments/aerial/scripts/env_4090.sh
$AERIAL_PY experiments/aerial/scripts/indoor_loop_collect.py \
  --pose-source gt_proxy --assist gt_pd --allow-gt-assist --keep-arrived-only \
  --success-dist 0.20 --max-intervention-rate 0.55 \
  --bc-tag fixture_gt_pd_020 \
  --routes 6,12 --segment-len-m 6 --max-steps 200 \
  --episodes 60 --min-usable 15 \
  --actor-ckpt experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2f_20260830/v4_ac_latest.pt \
  --out experiments/aerial/rl/artifacts/dataset_indoor_fixture_bc_e2g_020_20260830
```

过门：n_arrived（usable）≥15；落盘 `collection_summary` 里 mean intervention 应 ≤0.55。  
若 yield 太低：可先去掉 `--max-intervention-rate` 采满 15 条 @0.20，再在报表写明介入分布；**不得**退回 success=0.50。

### E2g.2 FT @4090

- init=`v4_ac_ckpt_indoor_e2f_20260830`  
- dataset=E2g.1（主料）；可选混 ≤30% E2f 0.50 BC（写比例）  
- train_pose=`gt_proxy`；iters 400–600  
- out=`v4_ac_ckpt_indoor_e2g_20260830`

### E2g.3 合同回归（硬）

- assist=**none**；6 m；success=**0.20**；**≥3** seed  
- 过门：≥2/3 seed arrival@0.20>0，或稳定 mean≤0.8 m  
- 不过 → 停，禁 E3

## 汇报

更新 `INDOOR_0XM_STATUS.md` + `LIVING_DOCS.md` A0；`/tmp/indoor_mainline_125_report.md`。
