# 支线 TZ-3Z：三线罩 × 老头 · 125 采 + H100 评（2026-08-23）

> **性质**：**并行支线**（不阻塞主线 `#26` τ-miss / `5ao`）。  
> **深度头**：**仅老头** `depth_ckpt_da3_r60_20260814`；v1–v3 **不部署、不开训**。  
> **罩子**：`safety.kind: three_zone`（8/5/1.5 @ 2/1/0.2，见 [`V4_THREE_ZONE_DECLARE_20260823.md`](V4_THREE_ZONE_DECLARE_20260823.md)）。  
> **机器分工**：**125/4090** = 渲染 + **闭环采集** + shield-on rollout；**H100** = **离线评**（`v4_three_zone_eval` / 后续 ⓪h）。  
> **红线**：`enable_policy_update=false`；不剥 D̂ OR 腿；Mac 只 sync/文书。

---

## 0. 问什么

在 **三线 deploy 已接线** 后，用 **老头** 走通：

1. **125** 上 shield-on、grab_depth、5 Hz **新语料**（或补采近带）  
2. **语料 tar → H100**  
3. **H100** 上离线 **三线深度预算** +（后续）shield-on ④ / ⓪h engage-miss  

**替代** 已废弃的 **⓪d@3.0 m** 作为主读数（3 m 单点指标不再作 deploy 依据）。

---

## 1. 冻结参数（本支线）

| 项 | 值 |
|----|-----|
| 三线 | L1/L2/L3 = **8 / 5 / 1.5 m**；v1/v2/v_stop = **2 / 1 / 0.2 m/s** |
| 巡航 | 5 m/s；`a_max` = **2.5 m/s²**（#28 实测制动 ~3.23，设计保守） |
| engage | **≥ 12.2 m** |
| step_hz | **5.0**；`grab_depth=true` |
| 老头 ckpt | `depth_ckpt_da3_r60_20260814/depth_step_2000_da3_ft_head.pt` |
| τ ckpt | `tau_ckpt_foe_r60_20260815/tau_foe_calibrator.pt` |
| 基线语料（可先评） | `dataset_v0_p45_merged_20260821`（77 ep，三线代码落地前采的，**对照 only**） |
| 新语料（本支线目标） | `dataset_v0_three_zone_oldhead_<STAMP>` |

---

## 2. 机器与路径

| 机器 | SSH | Repo | Python |
|------|-----|------|--------|
| **125** | `cursor-125-public` / `ssh cursor-125` | `~/aerial-wam-v2` | `source experiments/aerial/scripts/env_4090.sh` → `$AERIAL_PY` |
| **H100** | `ssh -p ${H100_PORT} ${H100_USER}@${H100_HOST}` | `${H100_REPO}`（默认 `~/aerial-wam-v2`） | `source experiments/aerial/scripts/env_h100.sh` → `$AERIAL_PY` |

**H100 默认**（与 `post_collect_r60_pipeline.sh` 对齐，可用 env 覆盖）：

```bash
export H100_USER=a25689
export H100_HOST=10.239.121.25
export H100_PORT=31126
export H100_REPO=~/aerial-wam-v2
```

125 → H100：**一次性配钥**（密码勿进 git）：

```bash
# ON 125
export H100_PASS='…'
bash experiments/aerial/scripts/setup_h100_ssh_from_125.sh
```

写入 gitignored `experiments/aerial/scripts/env_h100_from_125.sh`；`v4_three_zone_branch.sh` 自动 source。

---

## 3. 阶段（launcher：`experiments/aerial/scripts/v4_three_zone_branch.sh`）

### Phase A — 125 采集（shield-on + 三线）

```bash
# ON 125
cd ~/aerial-wam-v2
git pull   # 或 Mac sync 后 125 pull
source experiments/aerial/scripts/env_4090.sh

MODE=collect STAMP=20260823 EPISODES=24 \
  bash experiments/aerial/scripts/v4_three_zone_branch.sh
```

- 读 `configs/aerial_rl.yaml`（`safety.kind: three_zone`）  
- `collect_dataset`：`--backend airsim --grab-depth --step-hz 5 --host 127.0.0.1`  
- 产物：`experiments/aerial/rl/artifacts/dataset_v0_three_zone_oldhead_<STAMP>/`  
- log：`logs/v4_three_zone_collect_<STAMP>.log`

**粗检**：`grab_depth=true`、`step_hz=5`、quarantine ≤0.20、median `achieved_hz` ≥4.9。

### Phase B — 125 → H100 语料同步

```bash
MODE=sync STAMP=20260823 bash experiments/aerial/scripts/v4_three_zone_branch.sh
```

- `tar cf - dataset_* | ssh H100 'tar xf - -C .../artifacts'`  
- H100 校验：`manifest.json` + npz 计数

### Phase C — H100 离线评（从 125 触发 ssh）

```bash
MODE=eval STAMP=20260823 bash experiments/aerial/scripts/v4_three_zone_branch.sh
```

在 H100 上跑（老头，**不重训**）：

| job | 命令要点 | 产物 |
|-----|----------|------|
| 三线预算 hold035 | `v4_three_zone_eval --heldout-frac 0.35` | `artifacts/v4_three_zone_branch_hold035_<STAMP>.json` |
| 三线预算 full77 | `--heldout-frac 0` | `artifacts/v4_three_zone_branch_full77_<STAMP>.json` |
| 对照（可选） | 语料 = `p45_merged` | 与 #27 横比 |

H100 需先 `git pull` + `source env_h100.sh`（脚本内自动）。

### Phase D — 后续（未开跑，登记）

| # | 内容 | 机 |
|---|------|-----|
| D1 | shield-on **④** 配对 eval（`v4_episode_pool` 已切 `ThreeZoneSpeedShield`） | 125 rollout，H100 可只聚 JSON |
| D2 | **⓪h engage-miss** harness（替代 ⓪d@3m） | H100 离线 |
| D3 | shield-on 闭环 `step_hz` + `three_zone_speed_cap` 逐步落盘 | 125 |

---

## 4. 一键（125 上）

```bash
STAMP=20260823 EPISODES=24 MODE=all \
  bash experiments/aerial/scripts/v4_three_zone_branch.sh
```

顺序：**collect → sync → eval**。`MODE=eval` 可单独重跑（语料已在 H100）。

---

## 5. 读数 / 过关（本支线 provisional）

| 判据 | 过线（provisional） | 依据 |
|------|---------------------|------|
| 动力学 | `kinematic.feasible_nominal=true` | 8/5/1.5 方案 |
| 深度 vs 预算 hold035 | `depth_vs_budget.all_bands_ok=true` | #27 已 PASS |
| full77 engage 带 | p95 欠读 ≤3.0 m 或 **登记功效不足** | n=24 边际 |
| ⓪d@3m | **不作为本支线 primary** | 用户裁定 + declare |

**不发证**：`authoritative=false` 直至 ⓪h re-freeze + ④′ 三线口径签字。

---

## 6. 与主线关系

| 主线 | 本支线 |
|------|--------|
| `#26` τ-miss / `5ao` | **正交**；不并行改 D̂ OR 腿 |
| P8 / `enable_policy_update` | **仍 blocked** |
| V0 ④ @3m | **legacy**；本支线不回头修 ⓪d |

---

## 7. 产物清单（模板）

```
# 125
experiments/aerial/rl/artifacts/dataset_v0_three_zone_oldhead_<STAMP>/
logs/v4_three_zone_collect_<STAMP>.log
logs/v4_three_zone_branch_<STAMP>.log

# H100
artifacts/v4_three_zone_branch_hold035_<STAMP>.json
artifacts/v4_three_zone_branch_full77_<STAMP>.json
logs/v4_three_zone_eval_<STAMP>.log
```

---

## 8. Mac 侧（仅 handoff）

1. 合入三线代码 → `sync_push`  
2. 125 pull + 跑 `MODE=all`  
3. 回写 [`V4_RUNBOOK_125_STATUS.md`](V4_RUNBOOK_125_STATUS.md) §TZ-3Z
