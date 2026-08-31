# Indoor WAM — 完整方案 / 模型 / 接线快照（2026-08-31）

> **Workspace（125）**：`/home/yao/aerial-indoor-wam`（与 phase2 `aerial-wam-v2` 分开）  
> **权威链**：本文件（快照）← [`INDOOR_0XM_STATUS.md`](INDOOR_0XM_STATUS.md) ← [`RUNBOOK_indoor_0xm.md`](../../experiments/aerial/RUNBOOK_indoor_0xm.md) §8.9  
> **分析**：[`INDOOR_E2I_PLAN_20260831.md`](INDOOR_E2I_PLAN_20260831.md) · [`INDOOR_E2I_DTFIX_PLAN_20260831.md`](INDOOR_E2I_DTFIX_PLAN_20260831.md) · [`INDOOR_FATAL_DEFECTS_20260831.md`](INDOOR_FATAL_DEFECTS_20260831.md) · [`INDOOR_C1_ROUTE_VID_AUDIT_20260831.md`](INDOOR_C1_ROUTE_VID_AUDIT_20260831.md)  
> **机器**：闭环/评测/采集 → **cursor-125**；深 FT → **H100 `.26`**（经 125）；Mac → 文档/接线/GitHub  

---

## 0. 一句话

室内主航道已走完 **E2i：dt 修罩 → B1/B2 语料 → C1 500 iter → @0.50 eval**。  
**罩层已可用（interv≈0.05）**；**C1 合同探针未过门**（1/3 seed 有到点，mean d_end≈3.55 m）。  
视频抽检表明失败要拆：**spawn 贴障** vs **近场撞障** vs **偶发真到点**。  
**禁止**自动开 H100 C2 / E3；下一步是 **室内 WM+π 适配规模评估（F4）**。

---

## 1. 方案状态（E2i 结案到哪）

```text
E2h FAIL（场景合格，合同@0.20 不过）
  → E2i.0/0w 接线 ✅
  → E2i.1 罩 A/B + dt fix ✅（v3 interv 0.048）
  → E2i.2a B2 夹具@0.20 ✅（34）
  → E2i.2b B1 assist=none 近成功 ✅（62）
  → E2i.3 C1 FT 500iter ✅ / @0.50 eval ❌
  → E2i.4 H100 ⛔（C1 不过不自动开）
  → E3 ⛔
```

| 过门 | 结果 |
|------|------|
| 罩 intervention &lt;0.5 | ✅ v3 **0.048**（baseline 仍 ~0.70，因 L1 过宽） |
| B1 usable ≥50 | ✅ **62** |
| C1 @0.50：≥2/3 seed 到点 **或** mean≤1.0 m | ❌ 1/3；mean **3.55** |
| 合同 @0.20 | ❌（E2h.4 / C1 均未主张） |

**纪律（Stick）**：禁换脑；禁关罩刷分；禁夹具写完成态；`gt_proxy` 只当探针；5ao 未签不剥 D̂/OR、不乱改 deploy safety。

---

## 2. 模型栈（当前部署/评测）

### 2.1 飞行核 π（Actor-Critic）

| 角色 | 路径（相对 repo） | 说明 |
|------|-------------------|------|
| **当前 C1 头** | `experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2i_c1_20260831/v4_ac_latest.pt` | e2h4 热启 + C1 mix 500 iter；**@0.50 未过门** |
| 热启父本 | `.../v4_ac_ckpt_indoor_e2h4_20260831/v4_ac_latest.pt` | Building_99 lobby realign 后头 |
| 更早室内链 | e2f / e2h / e2e … | 归档；默认勿混用 |

- 策略类：`tanh_bounded_v1` · `LatentActorDeployPolicy`（deterministic）  
- 动作盒（室内）：`[0.15, 0.08, 0.08, 0.10]` m|rad / step @ **5 Hz**（≈ 0.75 / 0.4 / 0.4 m/s）  
- 训练位姿戳：`gt_proxy`（**非产品合同**）

### 2.2 世界模型 WM

| 项 | 值 |
|----|-----|
| ckpt | `experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt` |
| 用途 | encode → imagination planner；C1 FT **未**更新 WM（`enable_wm_update=False`） |
| 缺口 | 室外 encode → 室内域；C1 不过后门是 **WM encode 室内适配**（F4） |

### 2.3 深度 / 罩感知

| 项 | 值 |
|----|-----|
| Depth head | `experiments/aerial/rl/artifacts/depth_ckpt_p45mid_s8j_20260825/depth_best_holdout_da3_ft_head.pt` |
| 罩输入 | `depth_min_pred` → `ThreeZoneSpeedShield` |
| 紧急通道 | τ / p_coll（室内 yaml：`min_tau_s=0.35`，`max_p_coll=0.65`） |

### 2.4 安全罩（部署规格 = **v3**）

配置权威：`configs/aerial_rl_indoor_shield_v3.yaml` / `configs/aerial_rl_indoor_c1_050.yaml`（同 safety 块）

| 参数 | v3 |
|------|-----|
| L1 / L2 / L3 | 0.45 / 0.28 / 0.14 m |
| v1 / v2 / v_stop | 0.55 / 0.30 / 0.05 m/s |
| **v_cruise** | **0.75** m/s（与 max_dx 对齐） |
| retreat | 0.12 m |

**关键修**：`ThreeZoneSpeedShield._dt_from_limits`  
`dt = limits[0] / zone.v_cruise_m_s`（禁 `limits[0]/MAX_BODY_VELOCITY`）  
→ 开阔巡航不再永久 three_zone。

接线：`experiments/aerial/scripts/indoor_shield_config.py` → eval/collect 统一 `build_indoor_shield(cfg)`。

---

## 3. 控制器接线（闭环）

```text
RGB + (depth head) + gt_proxy pose stub
        │
        ▼
 LatentActorDeployPolicy (π) ──► ImaginationPlanner (可选)
        │
        ▼
 MainlineIndoorPolicyWrapper.arbitrate
   assist=none → 不走 GT-PD/IBVS 主控（完成态）
   assist=gt_pd → 仅夹具 BC（须 --allow-gt-assist）
        │
        ▼
 ThreeZoneSpeedShield.apply_action  (罩 ON)
        │
        ▼
 AirSim step @ 5 Hz · Building_99 :41451
```

| 层 | 模块 | 备注 |
|----|------|------|
| Env | `airsim_env` · settings 室内 JSON | `recover_renderer_scene.sh building99` |
| Pose | `gt_proxy`（探针） | 真 odom/VIO = E3，禁 |
| Policy wrap | `indoor_controller` TwoPhase | 主航道 assist=none |
| Shield | `safety.ThreeZoneSpeedShield` | yaml 数值；dt 已修 |
| Collect | `indoor_loop_collect.py` | `--keep-near-success` · `--append` |
| Eval | `indoor_mainline_baseline_eval.py` | 合同/探针 |
| Vid | `indoor_c1_route_vid.py` | 抽检 ego+stills |

---

## 4. 语料

| 集 | 路径 | n | 用途 |
|----|------|---|------|
| **B1** | `dataset_indoor_b99_none_near_20260831` | **62** | `assist=none` · near≤1.0 · drop-collided · **FT 主料** |
| **B2** | `dataset_indoor_b99_fixture_020_20260831` | **34** | 夹具 @0.20 · **≤30%** |
| 旧 E2h | `dataset_indoor_building99_e2h_20260830` | 101 | 夹具 @0.50 为主 · **≤20%** |
| **C1 mix** | `dataset_indoor_e2i_c1_20260831` | 120 | 62+34+24 symlink；比例 51.7/28.3/20 |

Annotation（室内）：`artifacts/building99_indoor_short_routes.json`  
**禁**把 `seen_airsim16_m1a20.json` 当室内 B1/B2 路由。

---

## 5. 配置文件

| 文件 | 用途 |
|------|------|
| `configs/aerial_rl_indoor_shield_v3.yaml` | **部署罩** + 微盒 |
| `configs/aerial_rl_indoor_c1_050.yaml` | C1 FT/eval（success_dist **0.50** + v3 safety） |
| `configs/aerial_rl_indoor_shield_e2h_baseline.yaml` | A/B 旧臂对照 |
| `configs/aerial_rl_indoor_shield_v2.yaml` | 中间档（归档） |
| `configs/airsim_settings_indoor.json` | → `~/aerial_airsim_persistent/AirSim/settings_indoor.json` |

`train_v4_ac` **无** `--config`：室内 FT 靠 CLI（`--indoor --success-dist-m 0.50 --action-limits ...`）；yaml 主要服务 eval/collect/罩。

---

## 6. 关键命令（125）

### 6.1 场景

```bash
source experiments/aerial/scripts/env_4090.sh
export AIRSIM_CAMERA=0 AIRSIM_VEHICLE=drone_1
bash experiments/aerial/scripts/check_airsim_indoor_ready.sh
bash experiments/aerial/scripts/recover_renderer_scene.sh building99   # 若未起
```

### 6.2 合同/探针 eval（罩 ON）

```bash
$AERIAL_PY experiments/aerial/scripts/indoor_mainline_baseline_eval.py \
  --config configs/aerial_rl_indoor_c1_050.yaml \
  --actor-ckpt experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2i_c1_20260831/v4_ac_latest.pt \
  --pose-source gt_proxy --assist none \
  --annotation artifacts/building99_indoor_short_routes.json \
  --routes 0,1,2,3,4,5,6,7 \
  --segment-len-m 3.0 --success-dist 0.50 --max-steps 160 \
  --out artifacts/indoor_c1_eval_050_rerun.json
```

### 6.3 离线 FT（不占 AirSim）

```bash
$AERIAL_PY -u -m experiments.aerial.rl.train_v4_ac \
  --indoor --iters 500 --device cuda --dynamics torch --backend mock \
  --success-dist-m 0.50 --action-limits 0.15,0.08,0.08,0.10 \
  --no-approach-bias \
  --wm-ckpt experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt \
  --actor-ckpt experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2h4_20260831/v4_ac_latest.pt \
  --dataset experiments/aerial/rl/artifacts/dataset_indoor_e2i_c1_20260831 \
  --skip-collect --train-pose-source gt_proxy \
  --ckpt-dir experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2i_c1_20260831
```

### 6.4 B1 续采

```bash
$AERIAL_PY experiments/aerial/scripts/indoor_loop_collect.py \
  --config configs/aerial_rl_indoor_shield_v3.yaml \
  --annotation artifacts/building99_indoor_short_routes.json \
  --routes 0,1,2,3,4,5,6,7 \
  --pose-source gt_proxy --assist none \
  --segment-len-m 3.0 --success-dist 0.50 \
  --keep-near-success --near-success-max-m 1.0 --drop-collided \
  --max-intervention-rate 0.55 --append \
  --episodes 100 --min-usable 50 \
  --actor-ckpt experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2i_c1_20260831/v4_ac_latest.pt \
  --out experiments/aerial/rl/artifacts/dataset_indoor_b99_none_near_20260831
```

### 6.5 视频抽检

```bash
$AERIAL_PY experiments/aerial/scripts/indoor_c1_route_vid.py \
  --routes 0,3,4,5 --seed 0 \
  --out-dir artifacts/videos/indoor_c1_route_vid_20260831
```

### 6.6 H100（仅过门后）

```bash
# 经 125
ssh h100-26   # a25689@10.239.121.26 -p 31126
# 深 FT ≥2000 iter；Mac 不直连长训
```

---

## 7. 关键工件索引

| 工件 | 内容 |
|------|------|
| `artifacts/indoor_shield_ab_summary_post_dtfix_20260831.json` | 罩 A/B 过门 |
| `artifacts/indoor_shield_channel_diag_v3_post_dtfix_20260831.json` | dt 修后 interv=0 |
| `artifacts/indoor_c1_eval_050_summary_c1_050_20260831.json` | C1 @0.50 **FAIL** |
| `artifacts/videos/indoor_c1_route_vid_20260831/` | R01/04/05/06 ego+stills |
| `logs/e2i_c1_ft_500_20260831.log` | C1 FT |
| `logs/e2i_c1_eval_050_20260831.log` | C1 eval |

---

## 8. 决策点（现在该答的题）

按 [`INDOOR_FATAL_DEFECTS`](INDOOR_FATAL_DEFECTS_20260831.md) **F4**，C1 不过 → **停自动升档**，三选一：

| 选项 | 内容 |
|------|------|
| **A** | WM encode 室内短窗 + π 再 C1（优先倾向） |
| **B** | 加码 B1 + spawn 健康过滤后再短 FT |
| **C** | 全量室内 WM+π 适配日程（非补洞） |

视频修正：记账时分离 **spawn 碰撞（R01）** 与 **近场撞障（R06）**，避免均值被重置污染。

---

## 9. 访问

| 端 | 入口 |
|----|------|
| 125 | `ssh cursor-125-public` / `ssh cursor-125` |
| H100 | 125 上 `ssh h100-26` |
| GitHub | `https://github.com/DavidXuAutel/aerial-indoor-wam`（Mac 推送常需经 125 SOCKS） |
| 禁 | Franka / Desk / `10.229.66.70` |

---

*Mac/125 Agent · 2026-08-31 · 人令：整理完整方案+模型+接线*
