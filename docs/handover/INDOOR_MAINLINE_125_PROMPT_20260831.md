# Indoor E2i.A — 125 Agent 执行提示（2026-08-31）

> **Workspace**：`/home/yao/aerial-indoor-wam`  
> **计划**：[`INDOOR_E2I_A_PLAN_20260831.md`](INDOOR_E2I_A_PLAN_20260831.md)  
> **禁**：E3；shield-off 完成态；夹具刷分；碰运气再 500（须先 WM encode）

## 目标

跑通 **A**：成功加权 mix → WM encode 短窗 FT（warm-start `wm_step_3500`）→ π 再 C1 → @0.50 罩 ON eval。

## 同步（若 Mac 已推代码）

确保以下文件在 125 上是最新：

- `experiments/aerial/rl/_wm_train_validate.py`（`--init-ckpt` / `--skip-gate`）
- `experiments/aerial/scripts/indoor_build_e2i_a_mix.py`
- `experiments/aerial/scripts/run_e2i_a_pipeline.sh`
- `docs/handover/INDOOR_E2I_A_PLAN_20260831.md`

## 一键（GPU 空闲时）

```bash
cd /home/yao/aerial-indoor-wam
source experiments/aerial/scripts/env_4090.sh
# FT 不占 AirSim；eval 才需要 Building_99
nohup bash experiments/aerial/scripts/run_e2i_a_pipeline.sh mix 2>&1 | tee logs/e2i_a_mix_20260831.log &
# 然后：
nohup bash experiments/aerial/scripts/run_e2i_a_pipeline.sh wm 2>&1 | tee -a logs/e2i_a_pipeline_20260831.log &
# WM 完：
nohup bash experiments/aerial/scripts/run_e2i_a_pipeline.sh pi 2>&1 | tee -a logs/e2i_a_pipeline_20260831.log &
# π 完且 Building_99 就绪：
bash experiments/aerial/scripts/check_airsim_indoor_ready.sh
bash experiments/aerial/scripts/run_e2i_a_pipeline.sh eval
```

或：`bash experiments/aerial/scripts/run_e2i_a_pipeline.sh all`（eval 会占 AirSim）。

## 过门

同 C1：`seeds_with_arrival ≥ 2/3` **或** `mean_d_end ≤ 1.0`。  
Summary：`artifacts/indoor_e2i_a_eval_050_summary_a_20260831.json`  
不过门 → **停**，不自动 H100。
