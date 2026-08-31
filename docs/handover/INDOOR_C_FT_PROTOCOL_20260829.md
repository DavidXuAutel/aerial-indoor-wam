# 阶段 C — 室内 π 短 FT 协议（2026-08-29）

> **Workspace**：`/home/yao/aerial-indoor-wam`  
> **门禁**：人签 C ✅（2026-08-29）  
> **权威**：`RUNBOOK_indoor_0xm.md` §5–6

## 1. 目标

在 **训练期** 对齐室内合同，短 FT **π（AC）**（默认只动 π，WM 冻结）：

| 项 | 值 |
|----|-----|
| `success_dist_m` | **0.20** |
| 动作盒 @ 5 Hz | `[0.15, 0.08, 0.08, 0.10]` |
| approach 距离 | **12 m**（8–15 m 室内量级；全 20 路由分布） |
| `assist` | **none** |
| BC 主料 | **禁止** GT-PD |
| 安全罩 | 训练不刷关罩；125 回归 **同协议带罩** |

## 2. Checkpoint 链

| 角色 | 路径 |
|------|------|
| WM（冻结） | `experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt` |
| π init | `experiments/aerial/rl/artifacts/v4_ac_ckpt_step_e_20260828/v4_ac_latest.pt` |
| π out | `experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_c_20260829/v4_ac_latest.pt` |

## 3. 数据

- **z0 编码**：复用 `dataset_v0_d_full_20260828`（110 ep，全路由分布）
- **goal 重写**：`approach_bias_transition_episodes` → start + **12 m** 沿 start yaw
- **想象 `goal_rel`**：离线 replay 缺 VIO → 训练期显式 `train_pose_source=gt_proxy`（仿真 stub，**须在 meta 声明**；125 回归用 `odom_from_imu_rgb`）
- **禁止**：单失败腿 / 只过采样 R10/R14

## 4. 超参

| 参数 | 值 |
|------|-----|
| iters | **300**（可停看曲线；建议 200–500） |
| imagine_batch | 16 |
| imagine_horizon | 15 |
| episodes_per_iter | 0（`--skip-collect`） |
| dynamics | torch（WM 冻结） |
| device | cuda（H100） |
| annotation | `artifacts/seen_airsim16_m1a20.json`（20 routes，`--max-episodes 20`） |

## 5. H100 命令（经 125 SSH）

```bash
# 125 → sync code + run
cd /home/yao/aerial-indoor-wam
bash experiments/aerial/scripts/sync_indoor_ft_to_h100.sh

ssh h100-25 'cd ~/aerial-indoor-wam && source experiments/aerial/scripts/env_h100.sh && \
  export PYTHONPATH=$PWD && \
  python -m experiments.aerial.rl.train_v4_ac \
    --indoor \
    --iters 300 \
    --device cuda \
    --dynamics torch \
    --wm-ckpt experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt \
    --actor-ckpt experiments/aerial/rl/artifacts/v4_ac_ckpt_step_e_20260828/v4_ac_latest.pt \
    --annotation artifacts/seen_airsim16_m1a20.json \
    --dataset experiments/aerial/rl/artifacts/dataset_v0_d_full_20260828 \
    --skip-collect \
    --train-pose-source gt_proxy \
    --ckpt-dir experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_c_20260829 \
    2>&1 | tee logs/indoor_c_ft_h100_20260829.log'
```

## 6. 125 回归（合同 B）

```bash
cd /home/yao/aerial-indoor-wam
source experiments/aerial/scripts/env_4090.sh
$AERIAL_PY experiments/aerial/scripts/indoor_mainline_baseline_eval.py \
  --actor-ckpt experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_c_20260829/v4_ac_latest.pt \
  --pose-source odom_from_imu_rgb \
  --assist none \
  --out artifacts/indoor_mainline_baseline_20260829_postC.json
```

对照 post-fix B：`mean_d_end_hat=12.1 m`，`arrival_rate_hat=0%`。

## 7. 禁止

- 关罩刷到点；松 `success_dist` 凑数  
- 单失败补洞 / GT-PD BC 主料  
- Mac 直连 H100；在 `aerial-wam-v2` 提交室内 FT ckpt  

## 8. 产物

- ckpt + `train_meta.json` → `v4_ac_ckpt_indoor_c_20260829/`  
- 回归 JSON → `artifacts/indoor_mainline_baseline_20260829_postC.json`  
- 汇报 → `/tmp/indoor_mainline_125_report.md`
