# 阶段 E — 诚实最可行协议（2026-08-29）

> **Workspace**：`/home/yao/aerial-indoor-wam`  
> **权威**：`RUNBOOK_indoor_0xm.md` §8.1  
> **诊断**：C/D 错配 FT（gt_proxy 训 / odom 考）→ 0% 到点；须同构 + 闭环采集

## E 铁律

| # | 规则 |
|---|------|
| 1 | `train_pose_source === eval_pose_source` |
| 2 | **室内闭环**采集后再 FT（125 AirSim） |
| 3 | 先 **E2 gt_proxy 同构**证可学习，再 **E3 odom 同构** |
| 4 | 禁关罩 / 单失败补洞 / GT-PD 换脑 |
| 5 | 验收双看 `d_end_hat` 与 `d_end_gt`；碰撞或 `d_end_gt` 爆炸 → ep 作废 |

## E0 — 接线

| 项 | 值 |
|----|-----|
| 采集 | `experiments/aerial/scripts/indoor_loop_collect.py` |
| FT | `python -m experiments.aerial.rl.train_v4_ac --indoor --skip-collect` |
| 回归 | `indoor_mainline_baseline_eval.py --pose-source <同构>` |
| `success_dist_m` | **0.20**（E2 全零到点可声明过渡 0.50 探针，须写 STATUS） |
| 动作盒 @ 5 Hz | `[0.15, 0.08, 0.08, 0.10]` |
| 段长 | **8–15 m**（默认 12 m） |
| 罩 | ThreeZone L1/L2/L3 = 1.5/0.8/0.4 m，**ON** |
| `assist` | **none** |

**过门**：`pytest experiments/aerial/rl/tests/test_pose_estimate.py` + mock dry-run collect。

## E1 — 闭环采集（gt_proxy）

| 项 | 值 |
|----|-----|
| 输出 | `experiments/aerial/rl/artifacts/dataset_indoor_loop_e1_gtproxy_20260829/` |
| `pose_source` | **gt_proxy**（显式） |
| 路由 | 全 20 路由分布 |
| π init | `v4_ac_ckpt_indoor_c_20260829`（或 step_e） |
| **过门** | `n_usable ≥ 30` |

```bash
cd /home/yao/aerial-indoor-wam
source experiments/aerial/scripts/env_4090.sh
$AERIAL_PY experiments/aerial/scripts/indoor_loop_collect.py \
  --pose-source gt_proxy --episodes 35 \
  --segment-len-m 12 --success-dist 0.20 \
  --out experiments/aerial/rl/artifacts/dataset_indoor_loop_e1_gtproxy_20260829
```

## E2 — 同构 gt_proxy FT（H100 via 125）

| 项 | 值 |
|----|-----|
| 数据 | E1 闭环集 |
| `train_pose_source` | **gt_proxy** |
| eval | **gt_proxy**（同构） |
| π init | `v4_ac_ckpt_indoor_c_20260829` |
| iters | 300–500 |
| ckpt out | `v4_ac_ckpt_indoor_e2_20260829` |
| 回归 JSON | `artifacts/indoor_mainline_baseline_e2_gtproxy_20260829.json` |

**过门**（诚实二选一）：

- `arrival_rate_gt > 0` @ 0.20 m，**或**
- `mean_d_end_gt` 相对 postC（10.7 m）↓ **≥ 30%**（≤ 7.5 m）

**不过门**：停，写失败分析；**禁止**自动开 E3。

### H100 命令

```bash
cd /home/yao/aerial-indoor-wam
bash experiments/aerial/scripts/sync_indoor_ft_to_h100.sh
# 额外 rsync E1 dataset（sync 脚本排除 dataset_*）

rsync -av experiments/aerial/rl/artifacts/dataset_indoor_loop_e1_gtproxy_20260829/ \
  h100-25:~/aerial-indoor-wam/experiments/aerial/rl/artifacts/dataset_indoor_loop_e1_gtproxy_20260829/

ssh h100-25 'cd ~/aerial-indoor-wam && source experiments/aerial/scripts/env_h100.sh && \
  export PYTHONPATH=$PWD && \
  python -m experiments.aerial.rl.train_v4_ac \
    --indoor --iters 400 --device cuda --dynamics torch \
    --wm-ckpt experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt \
    --actor-ckpt experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_c_20260829/v4_ac_latest.pt \
    --dataset experiments/aerial/rl/artifacts/dataset_indoor_loop_e1_gtproxy_20260829 \
    --skip-collect --train-pose-source gt_proxy \
    --ckpt-dir experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2_20260829 \
    2>&1 | tee logs/indoor_e2_ft_h100_20260829.log'
```

### 125 回归

```bash
source experiments/aerial/scripts/env_4090.sh
$AERIAL_PY experiments/aerial/scripts/indoor_mainline_baseline_eval.py \
  --actor-ckpt experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2_20260829/v4_ac_latest.pt \
  --pose-source gt_proxy --assist none \
  --out artifacts/indoor_mainline_baseline_e2_gtproxy_20260829.json
```

## E3 — 仅 E2 过门后

- 采 `dataset_indoor_loop_e3_odom_*`（`pose=odom_from_imu_rgb`）
- FT train=eval=odom
- 回归 postE odom + 可选 held-out

## 作废规则

- 碰撞 ep / spawn collision / quarantine → 不计 usable
- C 式 offline replay + 错配 pose → **禁止**再作 E2 主料
- postC/postD 数字仅作对照，非完成态
