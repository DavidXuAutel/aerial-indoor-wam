# Indoor WAM — 完整方案 / 模型 / 接线详解（2026-08-31）

> **Workspace（125）**：`/home/yao/aerial-indoor-wam`（与 phase2 `/home/yao/aerial-wam-v2` **物理分开**，禁止混 PYTHONPATH）  
> **权威链**：本文件（详解快照）→ [`INDOOR_0XM_STATUS.md`](INDOOR_0XM_STATUS.md) → [`RUNBOOK_indoor_0xm.md`](../../experiments/aerial/RUNBOOK_indoor_0xm.md) §8.9  
> **配套**：[`INDOOR_E2I_PLAN_20260831.md`](INDOOR_E2I_PLAN_20260831.md) · [`INDOOR_E2I_DTFIX_PLAN_20260831.md`](INDOOR_E2I_DTFIX_PLAN_20260831.md) · [`INDOOR_FATAL_DEFECTS_20260831.md`](INDOOR_FATAL_DEFECTS_20260831.md) · [`INDOOR_C1_ROUTE_VID_AUDIT_20260831.md`](INDOOR_C1_ROUTE_VID_AUDIT_20260831.md) · [`ACCESS.md`](ACCESS.md)  
> **分工**：闭环/评测/采集/4090 FT → **cursor-125**；深 FT → **H100 `.26`**（经 125）；Mac → 文档/接线/GitHub（推送常需 125 SOCKS）  
> **禁**：Franka / Desk / `10.229.66.70`；`5ao` 未签不剥 D̂/OR、不乱改 `safety.py` deploy  

---

## 0. 一句话

室内主航道已执行完 **E2i**：修 dt 尺度 → 罩 v3 A/B → 双轨语料（B1/B2）→ C1 混合 500 iter → Building_99 @0.50 罩 ON eval。  

- **安全层可用**：v3 平均 intervention **≈0.05**（修前 ≈0.95–1.0）。  
- **策略探针未过门**：C1 @0.50 仅 **1/3 seed** 有到点，mean d_end **3.55 m**（要 ≤1.0 或 ≥2/3 到点）。  
- **视频抽检**把失败拆成三类：**spawn 贴障**、**近场撞障**、**偶发真到点**——不能只用全表均值叙事。  
- **停自动升档**：不自动开 H100 C2 / E3；下一步是 **F4 室内 WM+π 适配规模评估**。

---

## 1. 产品合同 vs 当前探针合同

### 1.1 产品合同（尚未主张完成）

| 维度 | 合同 |
|------|------|
| 传感 | RGB + IMU + 高度 → 估计位姿 \(\hat p\) |
| 控制 | **WAM π 唯一飞行核**；安全罩只做硬限速/急停，不当导航 |
| 精度 | 室内 **0.x m** 到点（主合同常写 **0.20 m**） |
| 场景 | 真室内图（Building_99），非 `env_airsim_16` 冒充 |

### 1.2 当前 E2\* 实际探针（允许，但禁止写成产品完成）

| 维度 | 实际 |
|------|------|
| 位姿 | **`gt_proxy`**（上帝位姿 stub 算 `goal_rel`） |
| 控制 | `assist=none` 评测；夹具语料可含 `gt_pd`（B2）但 **≤30%** |
| 精度探针 | C1 用 **0.50 m**；合同仍是 0.20 |
| 罩 | **必须 ON** 写完成态；关罩只做诊断 |

### 1.3 致命残留（仍未消解）

见 [`INDOOR_FATAL_DEFECTS_20260831.md`](INDOOR_FATAL_DEFECTS_20260831.md)：

| ID | 内容 | 现状 |
|----|------|------|
| **F1** | 夹具训 / `assist=none` 验 | B1=62 已有主料形态；C1 仍不够证明可学 |
| **F2** | 全程 `gt_proxy` | 未解；E3 禁 |
| **F3** | 罩曾全接管导航 | **dt 已修 + v3 过门**，残留是复发风险 |
| **F4** | 室外表示/尺度当缩盒适配 | **C1 不过 → 已触发**，须评估 WM+π |
| **F5** | 撞近/夹具刷分 | 纪律已写；视频证明 R01 类会污染均值 |

---

## 2. 路线图与过门账本

### 2.1 已执行链

```text
E2h 场景切换 Building_99 ✅ / 合同@0.20 ❌ / shield-off best 0.63m collided
        │
        ▼
E2i.0  计划 v2 + 致命缺陷文档 ✅
E2i.0w yaml→eval/collect 罩接线；B1 keep-near-success / append ✅
E2i.1  罩 A/B + _dt_from_limits 修复 ✅（v3 interv 0.048，d_end↓47.8%）
E2i.2a B2 夹具@0.20 ✅（34 arrived）
E2i.2b B1 assist=none 近成功 ✅（usable 62≥50）
E2i.3  C1 mix FT 500iter ✅ / @0.50 8×3 eval ❌
E2i.4  H100 长 FT ⛔
E3     odom/VIO ⛔
```

### 2.2 过门表（数字）

| 门 | 判据 | 结果 | 工件 |
|----|------|------|------|
| 罩 A/B | new interv&lt;0.5；d_end↓&gt;30%；collision 不恶化 | ✅ interv **0.048**；↓**47.8%** | `artifacts/indoor_shield_ab_summary_post_dtfix_20260831.json` |
| 通道诊断 | 开阔段不再永久 three_zone | ✅ interv **0.00×4** | `artifacts/indoor_shield_channel_diag_v3_post_dtfix_20260831.json` |
| B1 | usable≥50，`assist=none` | ✅ **62** | `dataset_indoor_b99_none_near_20260831` |
| C1 @0.50 | ≥2/3 seed 有到点 **或** mean_d≤1.0 | ❌ 1/3；mean **3.5514** | `artifacts/indoor_c1_eval_050_summary_c1_050_20260831.json` |
| 合同 @0.20 | ≥2/3 或 mean≤0.8 | ❌ 未主张 | E2h.4 / 未跑 C2 |

### 2.3 C1 @0.50 分 seed

| seed | arrived_n/8 | mean_d_end | collision_n | mean_interv |
|------|-------------|------------|-------------|-------------|
| 0 | **1** | 1.74 | 5 | 0.061 |
| 1 | 0 | 3.85 | 8 | 0.019 |
| 2 | 0 | 5.06 | 8 | 0.464 |

### 2.4 视频抽检修正（seed0，C1 ckpt）

目录：`artifacts/videos/indoor_c1_route_vid_20260831/`  
文档：[`INDOOR_C1_ROUTE_VID_AUDIT_20260831.md`](INDOOR_C1_ROUTE_VID_AUDIT_20260831.md)

| 路由 | 视频结论 | 含义 |
|------|----------|------|
| R01 | **1 步即 COLLIDED**，贴柱/屏柜 | spawn/贴障污染，不是长航失败 |
| R04 | **ARRIVED** d=0.45 | 真到点（食堂区） |
| R05 | **ARRIVED** d=0.43，135 步 | 长航真到点 |
| R06 | **COLLIDED** 货架，d≈2.0 | 真近障失败 |

→ 全表 mean 被 R01 类与高碰撞路由拉高；评估适配时必须 **分失败模式记账**。

---

## 3. 系统架构（闭环数据流）

```text
┌─────────────────────────────────────────────────────────────────┐
│ Building_99 (Unreal) :41451                                      │
│ recover_renderer_scene.sh building99                             │
│ settings: configs/airsim_settings_indoor.json → persistent AirSim│
└───────────────────────────────┬─────────────────────────────────┘
                                │ RGB 224² @5Hz + depth(grab)
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│ DepthMinPredictor (p45mid head)                                  │
│   → obs.info["depth_min_pred"]                                   │
└───────────────────────────────┬─────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
 PoseEstimator            WM.encode(obs)          (optional τ/p_coll)
 gt_proxy → p_hat         z latent                emergency latch
 stamp goal_rel
        │                       │
        └───────────┬───────────┘
                    ▼
        LatentActorDeployPolicy (π)  deterministic
                    │
                    ▼
        ImaginationPlanner.plan (horizon=5, 可关逻辑上仍构造)
                    │
                    ▼
        MainlineIndoorPolicyWrapper.arbitrate
          assist=none  → 保持 WAM（完成态）
          assist=gt_pd → GT-PD/IBVS（仅夹具 BC）
                    │
                    ▼
        ThreeZoneSpeedShield.apply_action(limits)
          dt = limits[0] / v_cruise     ★ E2i 关键修复
          v_cap = planned_speed(D̂)
          max_dx = v_cap * dt
          + τ / p_coll emergency retreat
                    │
                    ▼
        env.step(action)  body delta clipped to micro box
```

### 3.1 关键代码入口

| 层 | 文件 |
|----|------|
| Env | `experiments/aerial/rl/env/airsim_env.py` · `obs.py` · `action.py` |
| 罩 | `experiments/aerial/rl/safety.py`（`_dt_from_limits`） |
| 三区运动学 | `experiments/aerial/rl/three_zone.py`（室内保持 cruise=5 默认；**室内数值来自 yaml**） |
| 罩工厂 | `experiments/aerial/scripts/indoor_shield_config.py` |
| 控制器 | `experiments/aerial/rl/indoor_controller.py` |
| 策略封装 | `indoor_mainline_baseline_eval.py` → `MainlineIndoorPolicyWrapper` |
| 采集 | `indoor_loop_collect.py`（`--keep-near-success` · `--append`） |
| 训练 | `experiments/aerial/rl/train_v4_ac.py` |
| 视频 | `indoor_c1_route_vid.py` |
| 场景 | `recover_renderer_scene.sh` · `check_airsim_indoor_ready.sh` |

### 3.2 控制频率与动作盒

| 量 | 值 | 说明 |
|----|-----|------|
| `step_hz` | **5.0** | 室内统一 |
| `max_dx,dy,dz,dyaw` | **0.15, 0.08, 0.08, 0.10** | 每步位移/转角 |
| 等效巡航 | ≈ **0.75 m/s** 前向 | 必须 ≈ `v_cruise_m_s` |
| 观测 | RGB 224×224 | `grab_depth=true`；`health_check=false`（B99 平墙误杀） |

---

## 4. 安全罩详解

### 4.1 部署规格 = **shield_v3**（= C1 yaml safety）

```yaml
l1_m: 0.45
l2_m: 0.28
l3_m: 0.14
v1_m_s: 0.55
v2_m_s: 0.30
v_stop_m_s: 0.05
v_cruise_m_s: 0.75
a_max_m_s2: 2.0
min_tau_s: 0.35
max_p_coll: 0.65
retreat_step_m: 0.12
```

对照：

| 配置 | L1 | v_cruise | 用途 |
|------|-----|----------|------|
| `shield_e2h_baseline` | 1.5 | 1.0 | A/B 旧臂（lobby 易误触发） |
| `shield_v2` | 0.90 | … | 中间档 |
| **`shield_v3` / `c1_050`** | **0.45** | **0.75** | **当前部署** |

### 4.2 dt 尺度 bug（已修）

```text
旧：dt = limits[0] / MAX_BODY_VELOCITY[0] = 0.15 / 5.0 = 0.03 s
    → 开阔 v_cap=v_cruise 时 max_dx ≈ 0.75*0.03 = 0.0225 ≪ 策略 0.15
    → 几乎每步 three_zone → intervention≈1 → sustained_escape

新：dt = limits[0] / zone.v_cruise_m_s = 0.15 / 0.75 = 0.20 s
    → 开阔 max_dx = 0.75*0.20 = 0.15 ≡ 策略盒
    → 近障 v_cap < v_cruise 仍按比例限速
```

单测：`test_indoor_micro_limits_open_space_no_false_cap`（`test_three_zone_shield.py`）。

### 4.3 栈纪律

- 室内 workspace **禁止**整文件覆盖 `aerial-wam-v2` 的 `safety.py`+`three_zone.py`（v2 默认 cruise **25**，会再次弄坏 dt/测试）。  
- 只允许改 yaml 数值；结构性改动需人审 / 5ao。

---

## 5. 模型清单（ckpt）

所有路径相对 `/home/yao/aerial-indoor-wam/`。

### 5.1 Actor-Critic π

| 标签 | 路径 | 角色 |
|------|------|------|
| **e2i_c1（当前头）** | `experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2i_c1_20260831/v4_ac_latest.pt` | C1 500iter；@0.50 **未过门** |
| e2h4 | `.../v4_ac_ckpt_indoor_e2h4_20260831/v4_ac_latest.pt` | C1 热启父本；lobby realign |
| e2h | `.../v4_ac_ckpt_indoor_e2h_20260831/` | Building_99 早期 |
| e2f | `.../v4_ac_ckpt_indoor_e2f_20260830/` | 夹具 BC 链 |
| e2e…e2 | 更早 | 归档 |

共同属性：

- `policy_class=tanh_bounded_v1`  
- 室内 FT 时用 CLI 覆盖 `action_limits=(0.15,0.08,0.08,0.10)`  
- 日志曾有 `imagined actions left the deployed box` 警告（想象空间 vs 微盒）——已知现象，不单独当过门

### 5.2 World Model

| 项 | 值 |
|----|-----|
| ckpt | `experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt` |
| dims | recurrent 512 · stoch 32×32（yaml） |
| C1 FT | **`enable_wm_update=False`** —— 只训 π |
| 含义 | 室内失败更可能卡在 **encode 域差（F4）**，下一刀候选是 WM encode 短窗 |

### 5.3 Depth

| 项 | 值 |
|----|-----|
| ckpt | `experiments/aerial/rl/artifacts/depth_ckpt_p45mid_s8j_20260825/depth_best_holdout_da3_ft_head.pt` |
| 输出 | `depth_min_pred` 喂罩 |

---

## 6. 语料详解

### 6.1 三集资产

| 集 | 目录 | n | 采集条件 | FT 角色 |
|----|------|---|----------|---------|
| **B1** | `dataset_indoor_b99_none_near_20260831` | **62** | `assist=none` · keep d_end≤1.0 · drop-collided · max_interv≤0.55 · v3 · annotation=`building99_indoor_short_routes.json` | **主料 ≥50%** |
| **B2** | `dataset_indoor_b99_fixture_020_20260831` | **34** | 夹具 @0.20 arrived | **≤30%** |
| 旧 E2h | `dataset_indoor_building99_e2h_20260830` | **101** | 多为夹具 @0.50 | **≤20%** |

### 6.2 C1 混合集

目录：`dataset_indoor_e2i_c1_20260831`（symlink，非拷贝）

| 来源 | 条数 | 占比 |
|------|------|------|
| B1 | 62 | **51.7%** ≥50% |
| B2 | 34 | **28.3%** ≤30% |
| old（随机 24） | 24 | **20.0%** ≤20% |
| **合计** | **120** | 100% |

元数据：`MIX_SUMMARY.json` / `manifest.json`。

### 6.3 路由 annotation

- 室内：`artifacts/building99_indoor_short_routes.json`（Mainline_Route_01…）  
- **禁止**室内 B1/B2 使用 `artifacts/seen_airsim16_m1a20.json`（室外 OpenFly）

---

## 7. 训练协议（C1 已跑）

```bash
$AERIAL_PY -u -m experiments.aerial.rl.train_v4_ac \
  --indoor --iters 500 --device cuda --dynamics torch --backend mock \
  --success-dist-m 0.50 \
  --action-limits 0.15,0.08,0.08,0.10 \
  --no-approach-bias \          # 保留近场真实 goal，禁止 12m approach 改写
  --wm-ckpt .../wm_step_3500.pt \
  --actor-ckpt .../e2h4/.../v4_ac_latest.pt \
  --dataset .../dataset_indoor_e2i_c1_20260831 \
  --skip-collect --train-pose-source gt_proxy \
  --ckpt-dir .../v4_ac_ckpt_indoor_e2i_c1_20260831
```

| 开关 | 选择 | 理由 |
|------|------|------|
| `--skip-collect` | 开 | 不占 AirSim |
| `--backend mock` | 开 | 离线 z0 |
| `--no-approach-bias` | 开 | B1 近成功目标不能被改成 12 m |
| `--success-dist-m 0.50` | 显式 | `--indoor` 默认 0.20，C1 探针要用 0.50 |
| WM update | 关 | 只 FT π |

说明：`train_v4_ac` **没有** `--config`；eval/collect 读 yaml，FT 靠 CLI。

---

## 8. 评测协议

### 8.1 标准探针（C1）

- 场景 Building_99 · 8 短路由 · 3 seed · segment 3 m · success **0.50** · max_steps 160  
- `pose_source=gt_proxy` · `assist=none` · **罩 ON（v3）**  
- 脚本：`indoor_mainline_baseline_eval.py` + `configs/aerial_rl_indoor_c1_050.yaml`

### 8.2 罩 A/B

- 同 ckpt（e2h4）· baseline yaml vs v3 · tag `post_dtfix_20260831`  
- 脚本：`run_e2i_shield_ab.sh`

### 8.3 视频抽检

- 脚本：`indoor_c1_route_vid.py`  
- 输出 ego mp4 + start/mid/end png + `summary.json`

---

## 9. 配置文件地图

| 文件 | 职责 |
|------|------|
| `configs/aerial_rl_indoor_shield_v3.yaml` | **部署罩 + 微盒**（主） |
| `configs/aerial_rl_indoor_c1_050.yaml` | C1：success_dist **0.50** + 同 v3 safety |
| `configs/aerial_rl_indoor_shield_e2h_baseline.yaml` | A/B 旧臂 |
| `configs/aerial_rl_indoor_shield_v2.yaml` | 中间档 |
| `configs/aerial_rl_indoor_lossless.yaml` | 早期 lossless 模板 |
| `configs/airsim_settings_indoor.json` | 拷到 persistent AirSim |
| `configs/aerial_rl.yaml` | `train_v4_ac` 基座（被 CLI 覆盖） |

---

## 10. 运维接线

### 10.1 机器

| 端 | 用法 |
|----|------|
| Mac | 文档、脚本接线、GitHub；**不**跑长 GPU/eval |
| **125** | Building_99 闭环、采集、4090 FT、评测 |
| **H100 `.26`** | `ssh h100-26` ← 125；`a25689@10.239.121.26 -p 31126` |

### 10.2 AirSim 互斥

```bash
bash experiments/aerial/scripts/check_airsim_indoor_ready.sh
bash experiments/aerial/scripts/recover_renderer_scene.sh {building99|outdoor|blocks|stop}
```

- 室内占用 `:41451` 时 **禁止** Phase-2 outdoor 并行  
- 环境：`source experiments/aerial/scripts/env_4090.sh`  
- `export AIRSIM_CAMERA=0 AIRSIM_VEHICLE=drone_1`

### 10.3 GitHub

- 远程：`https://github.com/DavidXuAutel/aerial-indoor-wam`  
- Mac 直连 443 常失败 → 经 125 SOCKS 推送（已多次验证）  
- **约定**：内容更新后 commit + push

---

## 11. 常用命令速查

### 场景就绪

```bash
source experiments/aerial/scripts/env_4090.sh
export AIRSIM_CAMERA=0 AIRSIM_VEHICLE=drone_1
bash experiments/aerial/scripts/check_airsim_indoor_ready.sh
# 若 port free：
bash experiments/aerial/scripts/recover_renderer_scene.sh building99
```

### Eval @0.50（当前头）

```bash
$AERIAL_PY experiments/aerial/scripts/indoor_mainline_baseline_eval.py \
  --config configs/aerial_rl_indoor_c1_050.yaml \
  --actor-ckpt experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2i_c1_20260831/v4_ac_latest.pt \
  --pose-source gt_proxy --assist none \
  --annotation artifacts/building99_indoor_short_routes.json \
  --routes 0,1,2,3,4,5,6,7 \
  --segment-len-m 3.0 --success-dist 0.50 --max-steps 160 \
  --out artifacts/indoor_c1_eval_050_manual.json
```

### B1 append 续采

```bash
$AERIAL_PY experiments/aerial/scripts/indoor_loop_collect.py \
  --config configs/aerial_rl_indoor_shield_v3.yaml \
  --annotation artifacts/building99_indoor_short_routes.json \
  --routes 0,1,2,3,4,5,6,7 \
  --pose-source gt_proxy --assist none \
  --segment-len-m 3.0 --success-dist 0.50 --max-steps 120 \
  --max-intervention-rate 0.55 \
  --keep-near-success --near-success-max-m 1.0 --drop-collided \
  --append --episodes 100 --min-usable 50 \
  --actor-ckpt experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2i_c1_20260831/v4_ac_latest.pt \
  --out experiments/aerial/rl/artifacts/dataset_indoor_b99_none_near_20260831
```

### 视频抽检

```bash
$AERIAL_PY experiments/aerial/scripts/indoor_c1_route_vid.py \
  --routes 0,3,4,5 --seed 0 \
  --out-dir artifacts/videos/indoor_c1_route_vid_20260831
```

### 罩单测（无 AirSim）

```bash
$AERIAL_PY -m pytest experiments/aerial/rl/tests/test_three_zone_shield.py -q
```

---

## 12. 工件总表

| 路径 | 说明 |
|------|------|
| `artifacts/indoor_shield_ab_summary_post_dtfix_20260831.json` | 罩过门 |
| `artifacts/indoor_shield_channel_diag_v3_post_dtfix_20260831.json` | dt 修后通道 |
| `artifacts/indoor_c1_eval_050_summary_c1_050_20260831.json` | C1 FAIL |
| `artifacts/indoor_c1_eval_050_seed{0,1,2}_c1_050_20260831.json` | 分 seed |
| `artifacts/videos/indoor_c1_route_vid_20260831/` | 视频+stills |
| `logs/e2i_c1_ft_500_20260831.log` | FT |
| `logs/e2i_c1_eval_050_20260831.log` | Eval |
| `logs/e2i_b1_continue_until_gate_20260831.log` | B1 续采 |
| `experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2i_c1_20260831/` | 当前 π |
| `experiments/aerial/rl/artifacts/dataset_indoor_*` | 语料 |

---

## 13. 下一步决策框架（必须人拍）

C1 不过门 ⇒ **禁止**「再来 500 iter 碰运气」或直接 H100。按 F4 三选一：

| 选项 | 做什么 | 过门仍用 |
|------|--------|----------|
| **A（优先写可行性）** | WM encode 室内短窗微调 + π 再 C1；记账分离 spawn vs 近障 | @0.50 罩 ON 同协议 |
| **B** | spawn 健康过滤 + 加码 B1 后再短 FT | 同上 |
| **C** | 全量室内 WM+π 适配日程（非补洞） | 另立里程碑 |

**无论选哪条**：完成态仍须罩 ON、`assist=none`、禁夹具刷分；`gt_proxy` 成绩不得写产品完成。

---

## 14. 文档索引

| 文档 | 用途 |
|------|------|
| **本文件** | 方案+模型+接线详解快照 |
| `INDOOR_0XM_STATUS.md` | 勾选状态 |
| `INDOOR_E2I_PLAN_20260831.md` | E2i 计划 v2 |
| `INDOOR_E2I_DTFIX_PLAN_20260831.md` | dt 修复与 F0–F2 |
| `INDOOR_FATAL_DEFECTS_20260831.md` | 致命缺陷 F1–F5 |
| `INDOOR_C1_ROUTE_VID_AUDIT_20260831.md` | 视频抽检 |
| `INDOOR_MAINLINE_125_PROMPT_20260831.md` | 125 Agent 提示 |
| `RUNBOOK_indoor_0xm.md` §8.9 | 运行手册 |
| `ACCESS.md` | 机器访问 |

---

*详解版 · 2026-08-31 · 人令：更详细整理方案/模型/接线*
