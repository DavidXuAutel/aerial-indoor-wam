# V4-MVP Design（方案 1：Corrector 内嵌 AC）

> **日期**：2026-08-16  
> **状态**：APPROVED for scaffold on 125（用户选方案 1 + 分期 C）  
> **前置**：V1 merge PASS（严谨）+ `tau_predictor.kind=foe_calibrated`  
> **母本**：[V1/V4 设计 §2](../../design/2026-08-15-v1-v4-design.md)、[DreamerV3 对齐](../../design/2026-08-04-dreamerv3-alignment-optim.md) §2.5  
> **冻结规格**：本文件为 V4-MVP 第二真相源；与母本冲突时以本文件为准直至 re-freeze。

---

## 0. 一句话

在 **已过关的 torch WM + V1 安全双通道** 上，于 `corrector._update_policy` 插入点实现 **DreamerV3 式 λ-return actor-critic（纯想象，H≤15）**；用 V0 ② progress + 安全不回归过 **V4-MVP gate**；**真环境 TD 混合留给 V4.1**。未过 gate **禁止** flip `enable_policy_update`。

---

## 1. 范围

### In（V4-MVP）

| 项 | 内容 |
|---|---|
| 训练 | 纯想象 AC：λ-return + REINFORCE（或等价 policy gradient）+ 熵正则 + value stop-grad |
| 接入 | `corrector.py` 现有插入点；`imagine()` + torch RSSM `step` |
| Actor | `act_latent(z)`（或 `h‖z`）；输出 4-D 运动学动作。**2026-08-18 记载**：看不见 goal（非实现 bug）；① **不可稳健达成**。§A 已排除碰撞项；**「§4 充分」待 A.3** — [`V4_SIGNAL1_STRUCTURAL_REFREEZE_PROPOSAL.md`](../../handover/V4_SIGNAL1_STRUCTURAL_REFREEZE_PROPOSAL.md)；禁止现 π 加长训 |
| Critic | `V(z)` on latent（同上，goal 不进 value） |
| 评测 | V0 ② 同 harness progress；安全：V0 ④ ratio≤0.80 且 hard coll 不差于 V1-① 权威对照 |
| 门控 | yaml `enable_policy_update` 默认 **false**；仅 merge PASS 后 flip |

### Out（明确不做）

- V4-② SEARCH 发现步数、V4-③ vs BC（后置）
- PPO / model-free 主路径
- 打开 V2 语义模块；改 V0 §4.1 阈值
- V4-MVP 内真环境 TD 混合（→ **V4.1**）
- 默认打开 `planner.enable`（与 AC 更新解耦）

### 分期 C

1. **V4-MVP**：纯想象 AC → `_v4_gate` merge  
2. **V4.1**：想象 loss + 真 env TD 小比例混合（另开设计修订）

---

## 2. 架构

```
collect (4090) → buffer
       ↓
[V1] WM update (enable_wm_update=true，已开)
       ↓
[V4] if enable_policy_update:
         sample z0 → imagine(H≤15) → actor_critic.update(rollout)
       ↓
deploy / eval smoke（shield 仍 ON：DepthTauShield + FOE τ）
```

| 组件 | 文件（拟） | 职责 |
|---|---|---|
| ActorCritic | `experiments/aerial/rl/actor_critic.py` | λ-return、policy/value loss、熵 |
| 接线 | `corrector._update_policy` | 调用 `actor_critic.update(rollout)` |
| Policy 适配 | `ImaginationActorPolicy` | 实现 `imagine()` 所需 `act(z)` |
| Gate | `_v4_gate.py` + `v4_metrics.py` | 两信号 MVP merge |
| Smoke | `scripts/v4_ac_smoke.py` | mock/dynamics 短跑，**不**翻生产 yaml |

**红线**：训练时 shield / τ / depth 路径与 V1 部署一致；禁止为过 gate 关掉安全罩。

---

## 3. 算法（MVP 钉死值）

| 超参 | MVP 值 | 说明 |
|---|---|---|
| Horizon H | **15**（≤ `MAX_IMAGINATION_HORIZON`） | 与 V1-② 对齐 |
| λ | 0.95 | DreamerV3 常用起點 |
| γ | 0.997 | 可随 reward 尺度微调，须记入 train meta |
| 熵系数 | 3e-4 起 | 防塌缩；写入 yaml `v4.entropy_scale` |
| imagine_batch | 沿用 corrector config | |
| 优化器 | Adam，lr 与 WM 分离 | actor/critic 独立 param group |
| 算法 | **λ-AC，不用 PPO** | 对齐 dreamerv3-alignment §2.5 |

Reward：想象轨迹使用与 collector 相同的 `RewardConfig`（progress / collision / maneuver 权重）；`w_maneuver` curriculum 仍按「总回报过阈再拉起」机制，**阈值不抄论文 50.0**。

---

## 4. V4-MVP 过关信号（re-freeze 草案）

| 信号 | 内容 | PASS |
|---|---|---|
| **V4-①** | Progress vs Heuristic | 同 V0 ② harness（n=8，obstacle-facing）；actor progress_sum **≥** heuristic × **(1+δ_p)**，**δ_p=0.10** |
| **V4-④** | 安全不回归 | （a）V0 ④ 协议 `ratio≤0.80`；（b）hard coll_rate **≤** V1-① 权威对照臂（同 starts 或同协议复测） |

**Authoritative 规则**：

- 须 `enable_policy_update=true` **仅在评测/训练作业内临时打开**或加载已训 actor ckpt；**生产 yaml flip 仅 merge 后**
- 禁止 tied-zero 式「双零安全」冒充 ④——须有 shield-off 或 V1 对照证明评测集非空域
- Split：H100 可训；①④ rollout 走 H100→4090（与 V0/V1 同）

Merge：`_v4_gate --merge v4_partial_1.json v4_partial_4.json` → `v4_gate_r60_YYYYMMDD.json`。

---

## 5. 里程碑（125 / H100）

| 步 | 交付 | 完成判据 |
|---|---|---|
| M0 | 本设计进仓库 + 活文档 | commit 可见 |
| M1 | `actor_critic.py` + 单测（mock dynamics） | pytest 绿 |
| M2 | 接入 `_update_policy`；smoke（临时 flag） | `v4_ac_smoke` OK |
| M3 | H100 纯想象短训（不翻生产 yaml） | loss 有界 + ckpt |
| M4 | `_v4_gate` + partial runner | self-check 绿 |
| M5 | 4090 评测 ①④ | merge PASS 或诚实 FAIL 数字 |
| M6 | 人工验收后 flip `enable_policy_update` | 活文档 + commit |

**本轮 125 agent 目标**：完成 **M0–M4**（能训、能自检）；M5–M6 留给用户验收后决定是否继续。

---

## 6. 配置（草案）

```yaml
corrector:
  enable_policy_update: false   # GATE V4 — merge 前禁止 true
  imagine_horizon: 15
  imagine_batch: 16             # 若已有字段则沿用
v4:
  lambda_gae: 0.95
  gamma: 0.997
  entropy_scale: 3.0e-4
  actor_lr: 1.0e-4
  critic_lr: 1.0e-4
```

---

## 7. 治理

- 不降低 V0/V1 阈值凑过  
- 不 push GitHub（除非用户明确要求）  
- 同步：125 bare `origin` + H100 bundle/pull  
- 活文档：新建 `docs/handover/V4_GATE_STATUS.md`；更新 `V1_GATE_STATUS` 一句话「V4 scaffold 进行中」

---

## 8. 验收清单（用户回流时）

- [ ] 设计文件在 `docs/superpowers/specs/2026-08-16-v4-mvp-design.md`
- [ ] M1–M4 代码 + 测试在 125 HEAD
- [ ] `artifacts/V4_125_AGENT_STATUS.md` 写明 HEAD、pytest、smoke、未翻 yaml
- [ ] `enable_policy_update` 仍为 **false**
- [ ] 若 M5 已跑：partial JSON 路径与数字诚实落盘

---

## 9. 变更记录

- **2026-08-18** — 记载：In 表 goal-blind + 单 mock goal 使 ① **不可稳健达成**。§A `b>c` 只排除碰撞项；排序倒挂 → 「§4 充分」待 A.3。**本文件 In 表尚未改**。
- **2026-08-16** — 用户确认：MVP=A、训练分期=C、实现=方案1 Corrector 内嵌；本规格首版；125 离线 agent 执行 M0–M4。
