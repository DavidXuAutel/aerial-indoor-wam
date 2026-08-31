# Aerial WAM v2 —— V0 项目总 RUNBOOK（活文档）

> **这是 aerial v2 pure-vision V0 的顶层入口 + 活文档。**
> - 想知道"项目在哪一步 / 每块去查哪份文档 / 怎么端到端跑" → 看这份。
> - **此后任何修改和调整,都在本文档底部 [§8 变更记录](#8-变更记录) 记一笔**(日期 + 改了什么 + 为什么)。
> - 阈值以冻结 spec §4.1 为**唯一权威**;本文只摘录并标注,**不在此新建第二处真相源**(那会触发 re-freeze)。

---

## 1. 一句话 & 当前阶段

**V0 ✅ 已完成（2026-08-14）**：四信号 merge PASS → `v0_gate_r60_20260814.json`；flags 已翻 `depth_head.enable` + `safety.kind: threshold`。

**V1 ✅ merge PASS（2026-08-15 严谨口径）** — 见 [V1_GATE_STATUS.md](docs/handover/V1_GATE_STATUS.md)。

**当前阶段：V4-MVP（2026-08-17）** — reward-head 轨后仍 merge FAIL（①）；下一轨 **goal+z0** 见 [V4_GATE_STATUS.md](docs/handover/V4_GATE_STATUS.md) / [V4_GOAL_Z0_125_STATUS.md](docs/handover/V4_GOAL_Z0_125_STATUS.md)。**活文档阅读顺序**：[LIVING_DOCS.md](docs/handover/LIVING_DOCS.md)。

> **防误读**：§8 晚¹⁹「从未在同 head+n=16 合拢 / merge 从未 exit 0」是 **2026-08-12 快照**。V0 已于 08-14 merge exit 0；**2026-08-17** 已将 frozen `n_eval_episodes` re-freeze 为 **8**（与实跑对齐）。

**为什么**：旧 `wm_step_5000.pt` 被判定为单柱 RGB-only RSSM shortcut(已失效);必须从随机初始化干净重训,
结构性反 shortcut。

## 2. 四信号现状（V0 — 已闭合，2026-08-14）

| 信号 | 内容 | 评估位置 | r60 结果 |
|---|---|---|---|
| **①a–c** | WM 训练健康 | H100 离线 | ✅ loss/recon/entropy PASS；`wm_train_meta authoritative=true` |
| **①d** | 深度 AbsRel ≤0.30 | H100 离线 | ✅ **0.0641** |
| **②** | 接近量↑ vs random | 4090 sim rollout | ✅ progress 13.49 vs −4.30；**n=8** |
| **③** | D̂ 尺度（重投影） | H100 离线 | ✅ median **0.212** |
| **④** | 近障 shield 开/关 | 4090 sim rollout | ✅ ④c ratio **0.113**；④b N/A（`n_contact=0` 空过）；**n=8** |

> 完整路径与 partial JSON 见 [V0_GATE_STATUS.md](docs/handover/V0_GATE_STATUS.md)。②④ rollout-dataset 仍用 `dataset_v0_headon_20260811` 做 obstacle scan。

## 3. 文档地图

**先读**：[活文档阅读清单](docs/handover/LIVING_DOCS.md)。

**权威规格 / 设计**(定义"做什么"):
- **[frozen spec](docs/superpowers/specs/2026-08-04-aerial-wam-v2-frozen-spec.md) —— §4.1 四信号阈值,最权威,改阈值需 re-freeze。**
- [pure-vision design v2](docs/superpowers/specs/2026-08-03-aerial-wam-pure-vision-design-v2.md) —— 架构。
- [sim capability spec](docs/superpowers/specs/2026-08-03-aerial-sim-capability-verification-spec-v1.md) —— Fork A 判定。
- [signal3 OLS/axis proxy design](docs/superpowers/specs/2026-08-05-signal3-ols-axis-proxy-design.md)。

**分主题 handover**(定义"怎么跑某一块"):
- **[V0 GATE 状态活文档](docs/handover/V0_GATE_STATUS.md) —— V0 合拢记录（已 PASS）。**
- **[V1 GATE 状态活文档](docs/handover/V1_GATE_STATUS.md) —— V1 三信号进度。**
- **[V1/V4 设计](docs/design/2026-08-15-v1-v4-design.md) —— post-V0 阶段设计与 gate 草案。**
- [4090 本地采集 runbook](docs/handover/2026-08-04-v0-4090-local-collect-runbook.md)
- [V1 WM H100 验证 runbook](docs/handover/2026-08-04-v1-wm-h100-validation-runbook.md)
- [signal3 reprojection estimator](docs/handover/2026-08-10-signal3-reprojection-estimator.md)
- [DA3 深度骨干](docs/handover/2026-08-10-da3-depth-backbone.md)

**基础设施**:[同步代码 & 建环境手册](experiments/aerial/scripts/RUNBOOK_sync_and_env.md)(三机 / 四脚本 / 六坑)。

**计划**:`~/.claude/plans/humble-imagining-forest.md`(V0 §6 Step 6 阶梯)。

## 4. 端到端跑法(§6 阶梯)

> 基础设施(推/拉代码、建 H100 环境、起 4090 渲染器)一律照
> [RUNBOOK_sync_and_env.md](experiments/aerial/scripts/RUNBOOK_sync_and_env.md),这里只列各阶段命令。

- **Step V-1（前置 gate）**:4090 loopback 跑 `experiments/aerial/sim_verify/run_all.sh` → 取 Fork A 判定
  (含 `depth_rate`:DepthPlanar fps ≥ 采集 step_hz)。Fork A 通过才进 Step 4。 → ✅ 已过
- **Step 4（4090 采集）**:`collect_v1.sh --airsim --host 127.0.0.1 grab_depth=true` → rsync npz 到 H100
  `experiments/aerial/rl/artifacts/`。实测闭环 Hz 设 `env.step_hz`。 → ✅ 产出 `dataset_v1_rgb`
- **Step 5（感知支柱）**:深度头 DA3(①d,已过——新语料上重验)。VIO 学习头是并行交付,不阻塞 gate。
- **Step 6（权威重训 + 四信号）**:
  - 干净重训(随机初始化,`--checkpoint-dir` 带日期):`_wm_train_validate --dataset <Step4语料> --steps N --save-ckpt --checkpoint-dir artifacts/wm_ckpt_v2clean_<date>`
  - ① 出:`_v0_gate --signals 1 --learning-log <新日志> --depth-ckpt <DA3>`
  - ③ 重跑:reprojection ≤0.25
  - **②④ rollout(4090 渲染器需先起)**——当前命令(artifact 走旧 checkout 绝对路径,见 [§5](#5-基础设施要点)):
    ```bash
    "$AERIAL_PY" -m experiments.aerial.rl._v0_gate --signals 2,4 --rollout-eval \
      --config configs/aerial_rl_rollout.yaml \
      --depth-ckpt /home/a25689/aerial-rl-skeleton/experiments/aerial/rl/artifacts/depth_ckpt_da3_near_20260811/depth_step_2000_da3_head.pt \
      --rollout-dataset /home/a25689/aerial-rl-skeleton/experiments/aerial/rl/artifacts/dataset_v0_headon_20260811 \
      --device cuda --emit experiments/aerial/rl/artifacts/v0_partial_24.json
    ```
    先盯 `[v0-gate] obstacle-facing scan: {...}` 看 `accepted`/16;跑完 `cat .../v0_partial_24.json`。
    (晚⁸:scan 现对每个位置先试采集记录航向再走 8 网格,头对头语料 `dataset_v0_headon_20260811` 才能被 probe 命中。)
  - **合并**:`_v0_gate --merge <各信号 json>` → exit 0 才算 V0 过关 → 才翻 flags。

## 5. 基础设施要点

- **三机**:Mac(写代码)/ 8×H100 `a25689@10.239.121.22 -p 31126`(训练+gate+rollout 客户端)/ 4090 `10.229.20.125`(渲染器)。
- **H100 是临时容器**:重建后 torch/venv/artifacts 全丢。环境用 `INSTALL=1 source experiments/aerial/scripts/env_h100.sh` 一键重建。
- **两个 checkout**:`~/robomaster-tt-control`(新 clone,代码新、artifacts 空)vs `~/aerial-rl-skeleton`(旧的,数据/权重全在)。
  artifacts 不在 git → 从新 clone 跑、`--depth-ckpt`/`--rollout-dataset` 用 `~/aerial-rl-skeleton/...` 绝对路径,别拷贝。
- **共享盘** `/home/a25689/aerial_cache_shared/` 存 runs/orchestration,重建通常不清 → 找丢失产物先搜这里。
- 详见 [RUNBOOK_sync_and_env.md](experiments/aerial/scripts/RUNBOOK_sync_and_env.md)。

## 6. 治理红线（永不放宽）

- V0 flags **已翻**（2026-08-14）；**V1/V4 flags 仍 OFF**，各阶段独立 gate
- `enable_policy_update`(V4) **仅在 V1b PASS 后**讨论
- 阈值 = §4.1 冻结,改阈值 / 越出 §4 gate / §6 order → 先改并 re-freeze 冻结 spec(§8)。
- 干净重训禁 warm-start 失效 ckpt;canonical `depth_step_5000.pt` 不动;失效 ckpt 归档保留。
- 代码走 git,禁 scp 热补丁;`step_hz` 实测不猜。
- goal-input 属 V3,本周期不给 RSSM 加 goal 张量输入。

## 7. §4.1 阈值摘录（**以冻结 spec 为准**,此处仅速查）

| 信号 | 键 | 阈值 |
|---|---|---|
| ①d | `depth_absrel_max` | holdout median AbsRel ≤ **0.30**(缺深度语料则 ①d=SKIP → 整门 FAIL) |
| ①a–c | `_check_learning` / `post_entropy_frac` / `loss_recon` | loss↓≥2%;recon 不劣;min entropy-frac ≥ **0.10** |
| ② | `n_eval_episodes` / `progress_margin` / `dist_margin_m` | N=**8**（re-freeze 2026-08-17）；progress policy ≥ random + **5.0** ∨ final_dist policy ≤ random − **3.0**(任一即过) |
| ③ | `scale_rel_err_max` / `min_scale_windows` | reprojection median 相对误差 ≤ **0.25**;有效接近窗 ≥ **8** |
| ④ | `intervention_before_contact_min` / `near_coll_rate_ratio_max` | 接触前干预比例 ≥ **0.50**;shield-on/off near_coll 比 ≤ **0.80** |

---

## 8. 变更记录

> 格式:`YYYY-MM-DD —— 改了什么(为什么 / 依据)`。最新在上。

- **2026-08-17** —— **洞 2/3**：④b 空过终态（实证=④c）；V1-② coll 改为独立诊断（headon coll=0 弃用；r60 n-starts=4 pos=5 / AUROC 0.972）。不改 08-15 merge。
- **2026-08-17** —— **n re-freeze**：frozen §4.1 `n_eval_episodes` **16→8**（用户拍板）；V4 `n<8` → non-authoritative。洞 1 关闭。详见 [V0_GATE_STATUS §4](docs/handover/V0_GATE_STATUS.md)。
- **2026-08-17** —— 活文档防误读：§1 标明晚¹⁹「merge 从未 exit 0」为 8/12 快照；当前阶段改为 **V4**；文档地图链到 [LIVING_DOCS.md](docs/handover/LIVING_DOCS.md)。
- **2026-08-15(午) —— V1a 执行完成（H100 `.25`）。**
  `_wm_train_validate` 500 steps on r60 PASS → `wm_ckpt_v1a_20260815/`；flip `dynamics.kind=torch` + `enable_wm_update=true`；`v1a_corrector_smoke.py` 3 iter mock **`wm=updated`×3**。详见 [V1_GATE_STATUS.md](docs/handover/V1_GATE_STATUS.md)。
- **2026-08-15 —— V0 合拢后文档同步 + V1/V4 设计。**
  V0 merge PASS（`v0_gate_r60_20260814.json`）后更新 §1/§2/§6；新增 [V1/V4 设计](docs/design/2026-08-15-v1-v4-design.md)、[V1_GATE_STATUS.md](docs/handover/V1_GATE_STATUS.md)；`PROJECT_STATUS.md` 切至 V1a 阶段。V1 分 V1a（WM corrector 环）与 V1b（τ+想象规划+双通道罩，frozen spec 完整 V1）。
- **2026-08-14(晚⁴) —— V0 GATE 合拢 + flags 翻转。**
  ②④ `v0_partial_24_r60_20260814.json` PASS（n=8）；merge exit 0；`depth_head.enable` + `safety.kind: threshold`；commit `cad5a08`/`5b301ea`。详见 [V0_GATE_STATUS.md](docs/handover/V0_GATE_STATUS.md) §6。

- **2026-08-12(晚²²) —— ①a–c 结案:v2clean 日志判据全过但**语料实质失格**(dt-desync 靠逃生舱放行)→ 用户拍板重采语料;根因(训练产物不自证语料)已修:新增 `wm_train_meta.json` 旁挂。**
  **查清过程**:H100 实测找到 `wm_ckpt_v2clean_20260810/wm_train.jsonl`(500 行,`recon_err`/`post_entropy_frac` 齐全 → 不触发 `_v0_gate.py:186-195` 缺字段 FAIL)。晚²¹ 首轮 `find -name "*train*log*"` 匹配不到 `.jsonl`,故漏搜。`check_learning_curves`(`v0_metrics.py:51`,k=50)三条**全过且余量量级**:a loss 16.7991→**1.4948**(−91%,只需 −2%);b recon 0.3245→**0.0282**(降 11.5×);c min_ent **0.4368**(需 ≥0.10,argmin 在 step 2 ⇒ **全程无后验塌缩**)。
  **但不可用 —— 失格在语料不在数字**:`_wm_train_validate.py:45-77` `_refuse_v0()` 明文拒 `step_hz>8.5`,报错原文 *"is the dt-desynced V0 corpus — **do not train a real WM on it**. Pass `--allow-v0-desync` **only to exercise the code path**"*;而 `collect_v1.sh:4` 记 7 月 `dataset_v0` **标称 12 Hz / 实测 7.1–8.3** → 标称 12 > 8.5 → 必须靠逃生舱才能训。**拿逃生舱放行的训练充当 ①a–c 证据,性质等同调阈值凑过。** → 故"非权威"是**实质失格,非记账疏漏**(修正晚²¹ 我"缺日志即可解除"的判断)。
  **用户拍板**:**重采一份语料**,不做语料考古(证明 7 月语料来历比重采更贵、结论更弱)。**可选省事路径**:`dataset_v1_rgb`(16 集 @8.0 Hz,已在 H100,过 `_refuse_v0`,正是 Step 6 `--dataset <Step4语料>` 所指)—— 集数偏薄但今天就能出一份**合格**日志走通 ①a–c;与重采不互斥。
  **根因修复(Mac 侧已落)**:`wm_train.jsonl` 只写 loss/recon/ent、**`--dataset` 完全不落盘** → 曲线无法自证语料,这正是"忘"在代码层的对应物;不修则重采后新日志同样不自证。新增 `_write_train_meta()` → 训练**开始前**在 `--checkpoint-dir` 写 `wm_train_meta.json`:dataset 绝对路径、`dataset_manifest_meta`(`step_hz`/`grab_depth`)、`allow_v0_desync`、**`authoritative`(=not allow_v0_desync)**、eps/transitions、steps/window/wm_batch、config、image_size、`git_sha`;用逃生舱则 stdout 打 `⚠ ... NOT authoritative ①a–c evidence`。**治理:纯增量旁挂,`_signal1abc_from_log` 只 parse `.jsonl` 从不读它 → 冻结 §4.1 verdict 逐字节不变**;未动阈值/shield 律/env/模型/flags。新测 `tests/test_wm_train_meta.py` 4 例(模块级 `importorskip("torch")`,Mac 跳过 H100 真跑);**Mac 全套 177 passed / 3 skipped,无回归**。
  **另记**:H100 有两份 `wm_train.jsonl` —— `wm_ckpt/`(无日期,`:216` 默认目录 fallback,疑 v1 时代)与 `wm_ckpt_v2clean_20260810/`;**喂 gate 必须用带日期全路径**。flags 全关。
- **2026-08-12(晚²¹) —— 订正晚²⁰/本文 §2 对 ①a–c 的定性(不是"要重训"而是"缺日志");①d 从待办移除;补回晚¹⁹ 的盘挂载前置。**
  起因:用户质疑"head B 的 ①③ 是硬通过的,为什么又要做 ①a–c 重训"。查证 `V0_GATE_STATUS.md` 后三处订正:
  (1) **①d 已在 head B 通过**(晚⁷ local 0.0483),我先前列的"approach 语料 ①d 未跑"是**重复列项,撤回** —— head B 侧待办**只剩 ③**。③ 之所以仍要跑一次:`near_weight=3.0` 把近带压约 10×(6.415→0.645m),而 ③ 测的是**尺度**、在**接近窗**上重投影 → 改动正落在被测量上,且 head A 余量 0.05–0.12 对阈值 0.25 不宽;而 ①d 是全图聚合(远景/地面稀释近带)故 DA3 硬扛得住 —— 两者不同类。
  (2) **①a–c 的"非权威"卡在 (a) 非 Step-6 语料 (b) 未留 `--learning-log`**(依本文 §2 line 23 + 晚¹⁹ "①a–c 需 `--learning-log`")。而 ①a–c 判 `_check_learning`(loss↓/recon/entropy-frac)**吃训练日志、不吃 ckpt** → **dry-run 日志若还在 H100,一条 `_v0_gate --signals 1 --learning-log <日志>` 即可出 verdict,零训练成本**;仅当日志没留或确认语料不对才需权威重训。我先前"①a–c 权威重训是 V0 唯一未完成的训练工作"**定性过重,撤回**。
  (3) **③ 的真实前置是共享盘挂载**(晚¹⁹ 已记但晚²⁰ 漏承):`dataset_v0_local_depth`/`approach_scale_d18` 在可拆卸共享盘、.22 当时未挂载;这也解释了晚²⁰ 那个"`~/aerial_ft_cache/` vs `~/aerial-rl-skeleton/`"路径冲突 —— **两条路径分属不同盘**,非记错。
  **①a–c 不可砍的论证不变**:①d/③=DA3 硬扛、②=不看图的 HeuristicPolicy、④=DA3 闭环 → ①a–c 是 V0 **唯一测 RSSM 本身**的信号,而 RSSM 正是 v1 崩掉的东西;砍掉则 V0 只认证了"DA3 是个好深度模型",而 V1 想象规划要建在这个未验证 WM 上。
  **另:两处悬空文档引用** —— `docs/handover/2026-08-12-v2-plan-risk-assessment.md`(晚²⁰ 引用)与 `2026-08-12-v0-gate-status-and-roadmap.md`(晚¹⁹ 称"权威文档")在 Mac worktree 全盘 `find` **均不存在**;前者是我写了 §8 记录却未确认落盘。待 H100 `ls` 确认,确不存在则删除悬空引用。查证清单见 `V0_GATE_STATUS.md` §3.1/§3.2。flags 全关。

- **2026-08-12(晚²⁰) —— 应用户要求写方案评估报告;并订正晚¹⁹的数据位置误判。**
  报告 `docs/handover/2026-08-12-v2-plan-risk-assessment.md`:接受既定 DreamerV3 模块化混合架构(不再质疑),客观评估。**总评**:方向可信、基座扎实、纪律好,但最高风险环节(想象 RL 训 actor)至今未实现,V0 只验"地基材料"不验"整楼"。**三条命门**:A 世界模型被想象 RL 利用(V0 验不到,`corrector` actor-critic 是 V4 no-op stub,v1 已崩过);B 安全共因失效**当前真实存在**(flow-TTC/占据体未建,shield 只读 D̂,近距离深度弱且样本量未查实);C 尺度锚定押 VIO 但 VIO 缺失,③ 用 GT-proprio 验证=验证-部署错位。**一致性发现**:"信号 3"定义漂移(spec 正文=WM 多步 rollout MSE,代码=深度尺度重投影;WM 预测有用性未在 V0 硬门禁,exit 0 只认证训练收敛);设计-V0 含 VIO 而执行-V0 用 GT-proprio。**数据位置(待 H100 `ls` 核实,勿硬信)**:晚¹⁹ 说"共享盘未挂载"存疑;我一度断言语料在 `~/aerial_ft_cache/datasets/`,但本文 §5/§6 权威 gate 命令指向 `~/aerial-rl-skeleton/.../artifacts/dataset_v0_headon_20260811`。两处冲突,Mac 无法 SSH → 以 H100 实测 `ls` 为准,gate `--dataset`/`--rollout-dataset` 照 §6 命令里的 `~/aerial-rl-skeleton/.../artifacts/` 绝对路径走。flags 全关。
- **2026-08-12(晚¹⁹) —— 现状/卡点/路线图收敛成单一权威文档;当前卡点=①③ 深度语料所在可拆卸共享盘未挂载于 H100 .22。**
  项目状态散在 §8 晚¹~晚¹⁸ + 多个 memory,收敛到 `docs/handover/2026-08-12-v0-gate-status-and-roadmap.md`(四信号状态表 + 3 卡点 + 5 步合拢路线 + 治理红线 + 资产清单)。**一句话诊断**:四信号各自的 blocker 已在不同时间/机器/ckpt 分别解决(③ reproj estimator 重写、④ shield 4 版+3 guard、①d 换 DA3),但**从未在「同一 head + n=16 + 一次 merge」合拢过**;剩下全是收尾合拢,非新研究。**当前卡点**:head 一致性 gap(①③ verdict 在 head A=da3_20260810,④ 用 head B=da3_near_20260811,merge 必须同 ckpt)→ 需 head B 上补跑 `--signals 1,3`;但 `dataset_v0_local_depth`/`approach_scale_d18` 在**可拆卸共享盘**,H100 .22 当前未挂载(near_head ckpt 可达是因 artifacts 在当前挂着的盘),用户挂载中。挂上→第 1 步(head B 上 ③+approach①d)→ 卡点 B(①a–c 需 `--learning-log`)→ 卡点 C(scan 喂满 n=16)→ `--merge` exit 0 翻 flags。flags 全关。
- **2026-08-12(晚¹⁸) —— jitter 守卫(8a063be)H100 权威复跑验证:seed=0 ×3 ④ 全 PASS 且稳健(ratio 0.13/0.23/0.12),不再靠 reset 抽签。**
  三次 `ok=True, n_contact=0, before=1.0, ratio=0.1328/0.2281/0.1164 (≤0.80), spawn_collision_drops=3, contact_dumps=0`。稳健化生效:退化集被 spawn/jitter 守卫剔净,`ratio` 稳定不再靠 idx8 抵消 idx0 险过 0.5(对比晚¹⁷ run2 before≈0.5)。**诚实标注**:`before=1.0` 为**空过**(无接触集,按冻结方法学合法),④ 实质由 `ratio`(on 近带占用 0.12~0.23× off)+ off 臂进近带信号兜底(同晚¹⁴ 方法学);现为稳健空过而非 reset 运气。**待**:(1) 精简输出未带 `proprio_jitter_drops`,jitter 守卫本轮是否触发未知(spawn_drops=3 证 spawn 守卫在跑);(2) n<16(须 scan 喂满冻结 n_eval_episodes=16);(3) ①③ ready(③ 待 merged+B 重训 depth re-gate);(4) `--merge` 全四 at n=16 → exit 0 才翻 flags。flags 全关。
- **2026-08-11(晚¹⁷) —— seed=0 ×3 稳健复跑 + dump 定性:idx0「lateral=19.5」集实锤 proprio-jitter 退化集(z 单步跳 19.47m vs vel −2.7);④ 过关脆弱(reset 运气)→ 拟加 proprio-jitter 无效试次守卫。**
  seed=0 固定、reset 非确定复跑 3 次(dump 开):**run1 n_contact=0 PASS、run2 n_contact=2 PASS(险)、run3 n_contact=0 PASS**;spawn_collision_drops 3/2/2。run2 dump 抓到两集:
  **idx0(铁证 proprio-jitter 退化集)**:`pos.z 19.096→next.z −0.375`(单步 Δz=−19.47m),`vel.z=−2.697`(0.2s 按速度只该动 0.54m,实测 19.47m,**差 36×,物理不可能**),`along=−0.003`(x,y 没动),`min_depth_px={row:0.345,col:1.0}`(最近障碍在**图像最右缘**,非前向),`intervention=true/action=[-1,0,0,0]`(shield 已 latch 后退),`len_on=1/coll_first_on=0`。→ reset 后 proprio z 坐标跳变的无效试次(非真实飞行、非前向、无接触前窗),与 spawn_collision 同类。
  **idx8(真前向接近集,shield 成功)**:9 步 along +6.64、前向净空 7.27→1.45 单调降;i=7 在 2.885m `intervention=true` 后退,i=8 撞(`min_depth_px row=1.0`=正下方地面);`interv_first=7 < coll_first=8` → ④b 记为**成功正例**。证明 shield 在真场景有效(撞的是底部地面,前向 depth 对正下覆盖弱,属另一回事)。
  **诚实结论**:④ 会过但**脆弱** —— run2 靠 idx8 把 idx0 抵消到 before_frac≈0.5 险过;晚¹⁴ 只出 idx0 没出 idx8 → before_frac=0 挂。过与不过取决于 reset 抽到哪些集。**拟修(治理安全,episode 有效性守卫,同 spawn/health drop)**:加 proprio-jitter 检测 —— 单步 ‖Δpos‖ 远超机体物理上限(真集单步 max 3.5m、jitter 19.5m,可干净分离)的 transition → 该集标记 `proprio_jitter` 无效试次 → resample,持续则 drop(计入 drop_stats,可审计)。判据只剔物理不可能的位移跳变,不误伤真集(≤3.5m),**非 §4.1、非 shield 律、非凑过**。**待**:实现 + 复跑确认 ④ 稳健(不靠 reset 运气)→ 再确认 ①③ → `--merge` 全四 at n=16 → exit 0 翻 flags。flags 全关。
- **2026-08-11(晚¹⁶) —— H100 权威重跑:②④ 首次「干净」partial PASS(非排除),7/7 shield 臂零碰撞存活满程;但两个稳健性缺口 → 仍不翻 flags。**
  同命令(408c47e)在 H100 重跑:**② PASS**(progress 11.18 vs random −3.75、final_dist 18.74 vs 32.89,n=9);**④ PASS** `intervention_before_contact_frac=1.0`(before_ok)、`near_coll_rate_ratio=0.0`(on 0.0 / off 0.0263,ratio_ok)、`n_contact_episodes=0`。**7 个接触起点 shield-on 全部 `len_on=200`/`coll_first_on=-1`(零碰撞存活满程),而 off 臂 6/7 在 6–11 步就撞**(`coll_first_off` 7/6/6/−1/11/8/9)→ 每个起点都是真前向碰撞风险场景,shield 确实避掉。`spawn_collision_drops=3`、`health_drops=0`、`coll_after_latch=0`、`near_before_latch=0`。晚¹²(有界后退 shield)+ 晚¹⁴(出生碰撞守卫)实锤有效。
  **为何上次(晚¹⁴)挂这次过 —— 纯 reset 非确定,非 gaming**:上次 `n_contact=1`(那个 `lateral=19.5` 的退化/盲区接触集把 ④b 打成 0),这次 `spawn_collision_drops` 2→3、该退化集被守卫剔除/未复现 → `n_contact=0`。按冻结方法学,`n_contact=0` 时 ④b=1.0 是**合法空过**(shield 好到无接触),且有 ④c(ratio 0.0)+ off 臂 6/7 全撞兜底证明场景为真风险 —— 这正是晚¹⁴ 记忆里写下的预期。**未动** §4.1(1.5/0.50/0.80)、shield 控制律、scan 判据、env/模型/flags;dump 未开(`n_contact=0` 无 dump)、且 opt-in 不影响判决。
  **仍不翻 flags,两个硬缺口(统计严谨,非 gaming)**:(1) **样本量** ②n=9 / ④n=7 均 < 冻结 `n_eval_episodes=16` → 这是 partial 非权威;要 n=16 须让 scan 喂满 16 个合格 near-obstacle 起点(扩 head-on 起点语料 / scan 覆盖,harness+数据,非 §4.1;降 n=弱化 gate=须 re-freeze,不做)。(2) **未 merge 全四** —— ①③ 需一同过(③ 待在 merged+B 语料重训 depth 头后 re-gate)。(3) **④b 空过脆弱性**:依赖每次 reset 都不冒出退化接触集;建议 `--dump-contact-frames` 复跑 1–2 次确证那个偶发集性质,若确为退化/盲区则把判据**固化进 spawn/health drop**(让 ④ 稳健不靠 reset 运气),否则另定。
  **通往权威**:①③ re-gate ready → scan 喂满 16 → `_v0_gate --merge` 全四 at n=16 → **exit 0 才翻 flags**。flags 现全关。
- **2026-08-11(晚¹⁵) —— 晚¹⁴ H100 权威 rollout 验证生效(② PASS、④c 漂亮过 ratio 0.042、spawn_collision_drops=2、start_collided_on 全 False),但 ④b 仍 =0;加 opt-in 只读接触集取证 dump 定性唯一接触集。**
  晚¹⁴ 在 H100 跨网权威重跑(commit b7823b9,4090 渲染器 PID 79217):**② PASS**(progress 11.81 vs random −3.99、final_dist 18.26 vs 33.34,双余量过,n=12);**晚¹⁴ 修复实锤生效** —— `spawn_collision_drops=2`/`health_drops=0`、所有存活集 `start_collided_on=false`、`coll_after_latch=0`、9/10 集 shield-on 存活满 200 步;**④c 漂亮过** `near_coll_rate_ratio=0.042 ≤0.80`(on 0.00185 / off 0.0439)。
  **但 ④ 仍 FAIL 于 ④b** `intervention_before_contact_frac=0.0`,`n_contact_episodes=1`。唯一接触集(scored idx 0):`len_on=1, coll_first_on=0, interv_first=-1, start_fwd_min=6.18, start_full_min=3.029, along_heading_on=0.025, lateral_on=19.554, start_collided_on=false`。画像:**前向 GT 净空 6.2m(shield 前向 D̂ 未到 3.0 → 全程未干预)→ 第一步(len=1)即撞**,全场最近 3.03m 在**非前向**;且 `lateral_on=19.554m` —— 单步(5Hz,dt=0.2s)位移 19.5m 物理上不可能(≈100 m/s),其他集 lateral 都是多步累积 3~10m。**高度疑似 (a) teleport-jitter 退化集 或 (b) 前向盲区侧向碰撞**,两者都非 shield 控制律失败,但处置不同。
  **不能凭疑似排除(=gaming gate)**。加 **opt-in 只读取证 dump**(`--dump-contact-frames DIR`,默认关 ⇒ 权威 gate 逐字节不变):对每个接触集导出逐步表(pos/next_pos/`dpos_norm` 单步|Δpos|/vel/collided/GT full+fwd min/`min_depth_px` 最近像素归一化 row,col/预测 D̂/intervention/action)+ 实际渲染 RGB&depth 帧栈(npz)+ 出生帧/碰撞帧 PNG。`min_depth_px` 直接区分正前(中心)/侧向(左右缘)/地面(底部);`dpos_norm` 直接判 teleport-jitter。`run_shield_eval` 返回 `contact_dumps`,`_v0_gate` 挂到 `shield_diag["contact_dumps"]`。纯只读、绝不影响判决(dump 异常也只 warning)。
  **治理**:未动 §4.1(1.5/0.50/0.80)、shield 控制律、env/模型/flags;dump 是 opt-in 诊断。Mac 合成接触集 smoke 验证:`dpos_norm=19.5`、`min_depth_px={row:0,col:0}`、npz+4 PNG 均生成。**待**:H100 同命令加 `--dump-contact-frames` 重跑 → 据 dump 定性接触集 → 若确证退化/盲区则治理安全排除(无效试次 or boxed-in 起点筛选,仿晚⁸/spawn-drop),否则另定。flags 仍全关。commit 本次待 push。
- **2026-08-11(晚¹⁴) —— 晚¹³ 遥测实锤:盲退假设 REFUTED;真因是 ④ eval 关掉了 collector 的出生碰撞守卫,把"出生嵌入"误计为 shield 碰撞 → 恢复 `skip_reset_collision=True` + 重采样。**
  晚¹³ 4090 rollout 带回按集几何:**盲目后退撞后墙 REFUTED** —— 5 个接触集(#2/4/6/7/9)`along_heading_on` = −0.004/−0.145/−0.311/−0.009/−0.301(全≈0)、`lateral_on` ≤0.39,**几乎没动就撞了**,不是退进后墙。真相:5 集全 `len_on=1`、`start_full_min` 低到 0.663/0.879/0.907m(3 个在 1.5m 带内),而**同起点 off 臂飞了 8–13 步**(`len_off` 8/13/11/13/11)才撞 → on/off 臂**出生净空显著不同**。位移≈0 却撞,物理上只可能是**出生就贴/嵌在几何体里**(撞前向 FOV 之外的侧/后/地面几何)。
  **代码钉死根因**:`_run_one`(v0_rollout_eval.py)给 collector 传 `skip_reset_collision=False`,**单独关掉了** collector 默认(`True`)的"出生即碰撞→跳过"守卫;`_run_one_resilient` 只在抛 `RuntimeError` 时重试,出生嵌入只返回 length-1 集不抛异常 → 不重试不跳过 → 被当成一次 shield 碰撞 → `first_i<first_c`=`0<0`=False → **④b 结构性归零**。这与 scan 自己会 reject `spawn_collision`、以及 collector 到处用的默认**自相矛盾**。
  **修复(治理安全,episode 有效性,同 晚⁸/⁹/¹³ 类)**:(1) `_run_one` 恢复 `skip_reset_collision=True`;(2) `_run_one_resilient` 把"出生碰撞→空 episode"当**可重采样 transient**(4090 reset 非确定,on/off 同起点净空都不同已证)→ 重试(=collector 文档说的 "start pose may need resampling"),持续嵌入才 drop(成对丢保持配对);(3) 新增 `drop_stats`,`run_shield_eval`/`_v0_gate` 输出 `spawn_collision_drops`/`health_drops`(**可审计,非静默截断**);(4) `_episode_geom_diag` 加只读 `start_collided_on/off`(存活集须为 False)。
  **诚实警示**:好 shield 会让"净空充足起点"零碰撞 → ④b 依冻结 metric(v0_metrics.py:286,无接触→before_frac=1.0)**空过**;此时 ④ 靠 ④c(ratio 0.172,近带占用 5.7× 更低)+ off 臂每集都撞(证明每个场景都是真碰撞风险)成立。**未动** §4.1(1.5/0.50/0.80)、shield 控制律、env/模型/flags。冻结 spec ④ 方法学追加注记(晚¹⁴)。新单测 3 个(persistent-drop / resample-recover / drops-surfaced);rollout+followups+collector 44 全过。
  **待**:4090 同命令重跑 ④ → 看 `spawn_collision_drops`>0 且接触集消失/变真接近 → 期望 ④ PASS → `_v0_gate --merge` 全四 → exit 0 才翻 flags。commit 本次待 push。
- **2026-08-11(晚¹³) —— 晚¹² 修好 ④c(ratio 12.96→0.192 ✓),但 ④b 仍 FAIL(before_frac=0);加只读按集几何遥测定位 step-1 碰撞方向。**
  晚¹² 有界后退在 4090 权威 rollout 上**大幅改善 ④c**:`near_coll_rate_ratio` 12.96→**0.192 ≤0.80** ✓、`near_coll_rate_on` 0.385→0.0066、`coll_after_latch` 4→3、6 集里 3 集存活满 200 步(shield 成功)。但 **④ 仍 FAIL 于 ④b**:`intervention_before_contact_frac=0.0`。
  **只读定位**:`collided` 是 post-step、只在 done 的终止步(v0_rollout_eval.py:571)→ `first_coll_step=0` ⟹ 该集**长度=1**(第一个动作后即撞)。3 个接触集全长度≈1 → `first_i<first_c` 恒 `0<0`=False → ④b 恒 0。**根因收窄(非 shield 控制律、非出生嵌入)**:起点 `start_clearance_m=3.0` + `spawn_collision` 拒 → 起点前向 FOV 净空 ≥3.0m(不在带内);off 臂 ~9 步才撞 → 每步 ~0.5–2.8m → **一步跨不过 5–25m 前障** → step-1 碰撞对象**不是前障**。shield 退 body −x + **前视相机看不到后方** → 强指向**盲目后退撞未感知的后/侧墙**(3 个 boxed-in 起点);design-4 有界后退在后墙就在第一退步内时仍无能为力。
  **但碰撞方向尚未实证,不据此定 fix**。加只读 `_episode_geom_diag`(v0_rollout_eval.py:600;proprio 位置 + GT 起点净空,均不入策略图)→ 按集出 `along_heading_on`(沿起点朝向净位移,**<0=后退**)、`start_full/fwd_min`(起点净空)、`len_on/off`、`coll_first_on/off`、`interv_first`,经 `run_shield_eval` 返回 `episode_diag`、`_v0_gate` 挂到 `shield_diag["episodes"]` 打印。新单测 `test_episode_geom_diag_flags_backward_retreat`;51 全过。
  **治理**:纯只读诊断,§4.1(1.5/0.50/0.80)、shield 控制律、env/模型/flags **全未动**。**待**:4090 同命令重跑 ④ → 看 `episodes[*].along_heading_on` 符号:若接触集 <0 → 实锤盲退撞后墙 → fix = 起点选择排除 boxed-in(仿晚⁸ 记录航向,治理安全的 episode 过滤);若 ≥0 或起点净空<standoff → 另定。flags 仍全关。commit 本次待 push。
- **2026-08-11(晚¹²) —— ④ shield:保持(悬停)→有界状态反馈后退;修惯性滑进带停留(near_count_on 200/200、ratio 12.96)。re-freeze。**
  晚¹¹ 4090 权威 rollout 推翻晚¹⁰"保持"假设:零 body-delta **不刹前向动量** → latch 关掉策略后机体**惯性滑进 1.5m 带并停在里面** —— `near_count_on` 达 200/200、`near_coll_rate_on=0.385`、`ratio=12.96`(比后退设计 1.24 更差)、`coll_after_latch=4`、`first_coll_step max=8`、`first_near_on max=15`。**分析错误定位**:晚¹⁰ 误以为零 delta 能定住位置;实际设计 (2) 的后退**身兼两职** —— 抵消乐观预测器 + 刹前向动量;晚⁷ 消除了乐观偏差,但**动量刹车仍需要**,悬停把它一起丢了。
  **修法**:`override_action` 恢复 `retreat_step_m=3.0`,`D̂ < min_depth_m`(反应 standoff)时后退 body −x(刹动量+退出带),`D̂ ≥ standoff` 时保持零 delta(**不再后退**→不盲目倒进后墙)。晚⁷ 使 D̂ 近带准确/欠读(前向 6.4→0.65m)故 `D̂≥standoff ⟺ 真 ≈3m 净空`(先前"退到 D̂ 安全再悬停"停带里正因乐观 D̂ 在 GT 仍<1.5 时就过 standoff,该前提已消失);latch 使 standoff 稳定后策略不再逼近。综合了后退(晚¹⁰前)刹动量 + 保持(晚¹¹)不撞后墙两者的正确部分。collector.py:158-163 在 `depth_min_pred` 填入后、`override_action` 前调用 → 状态反馈拿得到当前步 D̂(已核 wiring)。
  **治理**:改的只是 shield **保持→有界状态反馈后退**控制律(shield 是被测系统);**④a 1.5 / ④b 0.50 / ④c 0.80 钉死值不动**;env/模型/flags 未动。冻结 spec §④a 追加"保持→有界状态反馈后退 更正(re-freeze 晚¹²)"。单测 `test_threshold_shield_holds_not_retreats_after_latch`→`test_threshold_shield_bounded_state_feedback_retreat_after_latch`;shield 4 + collector/rollout/metric 34 = 38 全通过。
  **待**:4090 同命令重跑 ④,预期 `coll_after_latch→0`、`ratio≤0.80`、④ PASS → `--merge` 四信号权威判决。flags 仍全关。commit 本次待 push。
- **2026-08-11(晚¹¹) —— ④ shield:连续后退→闩锁保持(悬停);修盲目倒退撞后墙(coll_after_latch=9/9)。re-freeze。**
  晚¹⁰ 机制遥测决定性:`near_before_latch=0`(闩锁不晚)、`coll_after_latch=9/9`(闩锁后全撞)、`first_interv` p50≈0 vs `first_coll` p50≈33、`steps_on` 34 vs `steps_off` 10.5。
  根因:`override_action` 每步 body −x **无后向感知**,策略被 latch 关掉后盲目倒退,封闭场景退进后墙 —— 活久 3 倍但仍 9/10 撞 = 把碰撞**转移**到后方,非避障。
  **前提已消失**:逼出"连续后退"的是**乐观预测器**(approach AbsRel 0.167),而 **晚⁷** 已消除(前向 D̂ 6.4→0.65m、近带 P(trigger)=1.0、近带准/欠读)。
  **修法**:`override_action` latch 后**保持(返回 `np.zeros(4)` 悬停)**、删 `retreat_step_m`。触发 `min_depth_m=3.0`+欠读 → 真 ≈3m(带外)闩锁 → latch 使策略不顶入、零 delta 无前冲无盲退 → 前向稳 ≥standoff(near_rate_on≈0)、无后墙撞(coll_after_latch→0)、~3m 先于接触介入(④b)。
  保持优于纯悬停(有 latch,不再逼近)、优于后退(晚⁷ 移除了后退所补偿的乐观偏差)。冻结 spec §④a 追加"后退→保持 修订(re-freeze 晚¹⁰)"。新单测 `test_threshold_shield_holds_not_retreats_after_latch`;顺修 2 个 latch 前的顺序依赖老测(负例用新实例)。全 shield/rollout/metric 测通过。
  **待**:4090 同命令重跑 ④,预期 `coll_after_latch→0`、`ratio≤0.80`、④ PASS → `--merge` 四信号权威判决。flags 仍全关。commit 本次待 push。

- **2026-08-11(晚¹⁰) —— scan 修复生效(accepted=11);② PASS;④ 仍 FAIL(near_coll ratio=1.24>0.80),加只读机制遥测定位。**
  晚⁹ 全画面/碰撞判据把 `accepted` 0→**11**、`probe hits`=11、`obstacle_ok`=11 —— scan 阻塞彻底解除。权威 rollout:
  **② PASS**(progress 10.5 vs random −0.65;final_dist 19.5 vs 26.5,双余量过)。**④ FAIL**:④b `intervention_before_contact=0.636≥0.5` ✓,
  但 ④c `near_coll_rate_ratio = on/off = 0.0389/0.0312 = **1.24** > 0.80` ✗,且 `n_contact_episodes=**11**`(shield 开启臂 11 集**全部仍碰撞**)。
  与"闩锁+单调后退首次 breach 后 GT 间距严格单调增、on 臂不该碰撞"的设计**直接矛盾** → 要么闩锁太晚(predictor 在实测帧偏乐观),
  要么后退量压不住前向位移/动量。**不靠改 shield/阈值凑过**(那是 gaming gate)。加纯后处理只读遥测 `_shield_diag`(从已返回 `masks` 算,
  不改 rollout/不动阈值/模型/flags):每臂逐集 `steps`/`near_count`、on 臂 `first_interv`/`first_coll`/`first_near` 步、
  以及 `near_before_latch`(near 早于闩锁数)、`coll_after_latch`(闩锁后仍碰撞数)。一次重跑即可判"闩锁太晚"还是"后退失效"。
  **待**:4090 重跑 ④(同命令,遥测自动带出 `shield mechanism diag`)→ 据实定位后再动。flags 仍全关。commit 本次待 push。

- **2026-08-11(晚⁹) —— ④ probe 判据对齐评测臂(中心裁剪→全画面 + 碰撞即接受);修 probe/eval 不匹配。**
  晚⁸ 上记录航向优先只把 proxy_ok 19→22,`accepted` 仍 0。加只读遥测(每个 proxy-OK probe 记
  `reached_fwd_m`/`reached_full_m`/`travel_m`/`collided`)后一轮定论:`travel_m` p50=**24.8m**(飞得动、到位),
  `collided`=**10/22**(真撞墙),但 `reached_fwd_m`(中心裁剪 0.3)最低只 **1.63m** 从没 <1.5。**根因**:probe 接受用
  `_forward_min_depth(中心裁剪)<1.5`,而 ④ 评测臂 `_episode_masks` 的 `near_coll_off` 用 `_full_min_depth(**全画面**)<1.5`
  —— probe 严过评测,头对头碰撞几何落在中心裁剪外(中心停 1.63m 但全画面必 <1.5),22 个真起点(含 10 碰撞)全被误杀。
  **修法(对齐 harness、不碰 §4.1 的 1.5m)**:probe 接受改为 **全画面 `_full_min_depth<near_m` 或 `collided`**
  (二者都被评测臂 `near_coll_off`/`collided_on` 同款读取 → near_coll_off>0 可复现;碰撞是最抗 RPC 抖动的铁证)。
  补 `reached_full_m` 遥测;新增 probe 单测(中心裁剪触底 1.6m 但角落 <1.5 → 全画面接受、旧中心判据会拒),19 测全过。
  **待**:4090 重跑 ④,预期 `accepted>0`(全画面/碰撞判据)→ `--merge` 四信号权威判决。flags 仍全关。commits 4eab52f/cf6de28/本次待 push。
- **2026-08-11(晚⁸) —— ④ scan 用采集记录航向(修 probe_no_hit=19/accepted=0);待 4090 用新头对头语料重跑。**
  晚⁷ 深度头修好后,4090 ④ rollout 仍找不到近障起点。专采头对头语料 `dataset_v0_headon_20260811`(34/34 可用)
  后扫 656 对:`candidates=82 / proxy_ok=19 / probe_no_hit=19 / accepted=0` —— **19 个朝障候选全被 probe 判否**。
  根因:`make_obstacle_facing_episodes` 丢弃采集记录的接近航向,改用 8 网格(0/45/…/315°,最多差 22.5°);
  中距正前障碍只擦到 0.3 中心裁剪边缘 → proxy 过但直线 probe 从旁擦过。**修法(harness,非 §4.1)**:
  `_obstacle_candidate_positions` 现返回 `(positions, 记录yaw)`;`make_obstacle_facing_episodes` 新增可选
  `candidate_yaws`,每个位置**先试记录航向**再走 8 网格兜底(头对头语料里记录 yaw 正对障碍 → probe 正撞)。
  向后兼容(不传则纯网格,单测不变);新增 off-grid 单测(0.3rad≈17° 网格打不中、给记录航向即命中),3 测全过。
  **治理**:选点=episode 过滤器非 gate 阈值(docstring 明载"②/④ harness 几何修正,非 §4.1");env/阈值/模型/flags 不动。
  **待**:4090 起渲染器 → `_v0_gate --signals 2,4 --rollout-eval --rollout-dataset dataset_v0_headon_20260811
  --depth-ckpt <晚⁷ 新头>` 重跑 ④ → `--merge` 四信号权威判决。flags 仍全关。
- **2026-08-11(晚⁷) —— near-band 重训验证双绿(①d 不退 + 近带感知实锤修复);待 4090 重跑 ④。**
  合并 `dataset_v0_local_depth + dataset_v0_approach_merged`(`_merge_datasets`)→ DA3 头 fresh 重训
  (near_weight=3.0,本地 HF cache 权重,`pip install safetensors` 解依赖)→ `depth_ckpt_da3_near_20260811`。
  **① 权威复验**(`--signals 1 --dataset dataset_v0_local_depth`):①d AbsRel=**0.0483 ≤0.30**,不退反降(旧代表 0.132)。
  **⑤ 诊断复跑**(`_diag_depth_vs_gt` on approach_merged):FORWARD 正前 `GT[0,1.5)` D̂p50 **6.415→0.645m**、
  `P(trig)` **0.000→1.000**、`P(over)` 1.000→0.377、AbsRel 6.757→0.198;full-field HEADLINE 近带 `GT<1.5` 与
  反应窗 `[1.5,3)` **P(trig) 双双=1.0**(旧 0.697/0.802)。1.5m 正前墙从被读 ~6.4m 修到 ~0.65m,shield 每帧必刹 →
  ④ 感知层根因消除。§4 ②④ 命令 `--depth-ckpt` 已切至新头。**待**:4090 起渲染器 → `_v0_gate --signals 2,4
  --rollout-eval` 重跑 ④(用新头)→ `--merge` 四信号权威判决。flags 仍全关。
- **2026-08-11(晚⁶) —— 定位 ④ 真根因=深度头近障乐观 → 深度头 near-band 重训(离线诊断先证,再修 loss)。**
  晚⁵ 修完 flaky 后 ④ 仍未过。用只读离线诊断 `_diag_depth_vs_gt`(不碰 gate/spec/config/flags,仅读 ckpt+语料,
  按 shield 同款 `DepthMinPredictor` 逐帧配 D̂ vs GT、按 GT 深度分箱)在 `dataset_v0_approach_merged`(115 集/14487 帧)
  上**决定性证实**:FORWARD 正前裁剪 `GT[0,1.5)` → D̂ p50=**6.415m**、`P(over)=1.000`、`P(trig)=0.000`
  —— 1.5m 正前墙被预测成 ~6.4m,shield 永不刹。这是**安全攸关的近前向深度质量问题**,被聚合 ①d(远/地板像素主导)
  掩盖;调 shield 余量/阈值都救不了(各 GT 箱的 D̂ 分布重叠)。修:`dynamics_torch.depth_head_loss` 加
  **near-band 强调项** `near_weight*mean(AbsRel | GT≤near_focus_m)`(默认 `near_weight=0.0` 保持旧行为/单测惰性;
  `train_depth_head._load_depth_cfg` setdefault `near_weight=3.0/near_focus_m=5.0`)。加可复用 `_merge_datasets.py`
  (npz 顺序重编号复制+provenance manifest)。**治理**:改训练 loss 属 §6 Step 5/6 范围内;①d gate 度量
  (`v0_metrics.depth_absrel`,全掩码,阈值 0.30)与所有 §4.1 阈值不动;`near_focus_m` 是训练超参非 gate 阈值。
  commits `df08bfa`(诊断)/`dc4a8b5`(near-band loss)/`39db5ea`(merge)。**待**:合并
  `dataset_v0_local_depth + dataset_v0_approach_merged` → 重训 DA3 头(fresh,`--eval-every 200`)→ 权威 ①d≤0.30 复验
  + 诊断复跑(FORWARD 近带 D̂p50 下压、`P(over)`↓)→ 双绿才上 4090 重跑 ④。env/模型/flags 未动。
- **2026-08-11(晚⁵) —— rollout 对 reset/健康失败重试+跳过(修 flaky 深度帧崩全局 gate)。**
  晚⁴ 重跑时崩在 shield-off 臂的 `env.reset`:`depth sanity failed: depth nearly constant (span=0.239, std=0.048)`
  —— 一个抖动/近似恒定的深度帧让 `_assert_healthy` 抛 `RuntimeError` 冒到顶,**整个 40min gate 挂掉**。
  且 ④ 专挑"正对障碍"起点,墙面填满 FOV 本就近似恒定深度 → 最易触发该守卫。修:`v0_rollout_eval`
  加 `_run_one_resilient`,对**瞬态 reset/健康失败**(白名单 marker:sanity/‌no depth/no imu/renderer)**重试 2 次
  (间隔 0.5s,reset 顶部 `_connect` 会重连),仍失败则**跳过该起点**(②/④ 都按起点整体跳,保持两臂配对、同 N)。
  **守卫不削弱**:坏帧永不被**评分**,只重试/跳过;每次跳过打 WARNING(不静默丢)。非瞬态错误(真 bug)照常抛。
  全跳空 → 现有 `depth_steps==0`/空数组守卫仍 fail-closed。env/§4.1/模型/flags 未动。
- **2026-08-11(晚⁴) —— ④ 连续后退 + 触发余量(re-freeze ④a 注;修 ratio 反转 6.10 + before_frac 0.333)。**
  晚³ 修好后 ④ 首次可测,但仍 FAIL:`near_on=0.205 ≫ off=0.034`(ratio 6.10)、`before_frac=0.333`、
  `n_contact=3`。诊断:**深度预测器在 1.5m 边界偏乐观**(approach AbsRel≈0.167),"恰好 1.5m 反应"必然太晚:
  1. **连续后退(`safety.override_action`)**:晚³ 的"退到 `safe_depth`(2.5)再悬停"仍把机体停在 GT<1.5 带内
     (d̂ 到 2.5 就停、GT 还 ~1.2)→ latch 整集刷分子。改:latch 后**每步都后退,永不悬停**,机体单调退带 →
     `near_on≈0`、总帧变大 → ratio 稳过。删 `safe_depth_m` 字段。
  2. **触发余量(`min_depth_m` 1.5→3.0)**:`before_frac≥0.5` 在噪声预测器下对"边界反应"数学不可满足
     (在碰撞边界才反应=已在边界)。shield 触发提到 3.0m(> 度量 1.5),提前于进带反应 → 不进带、零碰撞 →
     `before_frac` 空过(`check_shield_effectiveness` 无碰撞集→1.0)。落点:`run_shield_eval(shield_trigger_depth_m=3.0)`
     与 metric 掩码**解耦**、`_v0_gate` 显式传、`train_rl._build_safety` live 默认 3.0。
  **治理**:改的是 §4.1 ④a 协议注「与 1.5 对齐」→ 用户批准 **re-freeze**(冻结 spec 已加"④ 反应余量注")。
  **度量端 `near_collision_depth_m=1.5`、④b 0.50、④c 0.80 钉死值不动**;env/模型/flags 未动。起点前向最小 5.578m>3.0m
  不误触发。**待 H100 pull + 重跑 ②④。**
- **2026-08-11(晚³) —— ④ 后退罩 + 修 step 双夹 bug + 正前 probe + 近障优先候选(修 `near_coll_off=0`/ratio NaN)。**
  用户批准方向"后退罩+细step"。诊断链:上一版 `near_coll_off=0` 的真根因有三层,全修:
  1. **`HeuristicPolicy` 双重夹取 bug**(`train_rl.py`):`act` 里 `clip_body_delta` 用默认 30Hz
     上限 `[0.167,…]`,把 `step_m` 彻底废掉 → 5Hz rollout 实际每步只走 ~0.167m(而非物理上限
     1.0m=5m/s÷5Hz),probe/eval 永远够不到障碍。改:`act` 返回 `step_m`-缩放的**原始** delta,
     由 collector `act_delta` 用 `body_delta_limits(1/step_hz)` 正确按速率夹取(删孤儿 import)。
  2. **probe 命中判据 全图最小 → 正前中心裁剪**(`v0_rollout_eval.make_obstacle_facing_episodes`):
     旧判据 `_full_min_depth` 会把侧向擦碰/下沉见地当命中(docstring 自陈"巡航全图最小往往是
     地面")→ 跨网 RPC 抖动下 eval 复跑不复现(`fwd=13.4m` 接受、probe"命中"1.08m 侧向、
     `near_coll_off=0`)。改用 `_forward_min_depth(center_frac)`:要求直线策略**正面撞**墙 →
     eval 全图 near mask(<1.5,仍是冻结 §4.1)必然复现,ratio 可测。
  3. **shield 后退罩 latch(`safety.ThresholdSafetyShield`)**:旧 `override_action` 返回 zeros=悬停,
     会把机体**停在** 1.5m 近障带里(goal-seeker 一直命令前进、罩一直抵消)→ `near_on>near_off`
     ratio 反转/NaN。改:首次触发即**整集 latch**,后退(body −x)到预测间距恢复 >`safe_depth_m`(2.5m)
     再悬停 → `near_on≈0` 构造保证。加 `reset()`,`run_shield_eval` per-episode 清 latch(shield 实例跨集复用)。
  4. **近障优先候选 + 扫描参数**(`_v0_gate`):`_obstacle_candidate_positions` 按采集帧深度全图最小
     **近障优先排序**(RGB-only 无存深度则安全回退原序);`make_obstacle_facing_episodes` 加
     `preserve_order` 按此序扫(不打乱);scan 参数 `obstacle_max_m` 15→25、`probe_steps` 12→40
     (配 ~1m/步够到 25m 正前障)、`max_scans` 400→1000。诊断依据:上一版 `open_ahead=392/400`
     (98% 候选点前向 >15m 空)+ 只扫了 8.7%(400/4584 对)→ 巡航走廊本就多为开阔,把少数近障点排前是关键。
  harness 几何/罩行为修 + 一个真 step bug,**env / §4.1 阈值 / 模型 / flags 均未动**。①③② 的判读不受影响
  (② 决定性通过的 banked 结果仍成立;重跑会在障碍起点上重测 ②,仍应过)。**待 H100 pull + 重跑 ②④。**
- **2026-08-11(晚²) —— ④ probe 验证起点(修 near_coll_off=0)。**
  - `make_obstacle_facing_episodes` 加 `probe_policy/probe_steps/probe_near_m`:代理判据通过后,用同一
    `HeuristicPolicy` 空跑 24 步(shield 关),只保留 GT 深度真进 `<near_collision_depth_m` 的起点 →
    ④ shield-off 臂 `near_coll_off>0` 构造保证。`_v0_gate` 传入该策略,并收紧代理(`obstacle_max_m=15`、
    `center_frac=0.3`)。scan diag 新增 `probe.{hits,hit_depth_m}` + `rej.{proxy_ok,probe_no_hit}`。
    harness 几何修,env/阈值/模型/flags 均未动。**待 H100 pull + 重跑 ②④ 验证。**
- **2026-08-11(晚) —— ②④ rollout 判读 + 修 DA3 依赖漏装。**
  - ②④ rollout 出结果:**② 决定性过**(progress 24.13 vs −5.11;final_dist 5.01 vs 34.99m);
    **④ 不可测**(④b 干预 1.0 ✅,但 `near_coll_rate_off=0`/`n_contact=0`→ratio NaN)。判定:过 ② 的
    好策略天然不进 <1.5m 近障区,shield 无分母。**下一阶段 = 收紧 ④ 几何**(障碍上 start→goal 连线、
    `obstacle_max_m`↓、goal 置障碍远端),非改 §4.1。
  - **修 `env_h100.sh`**:DA3 深度头 hard-import `einops`+`addict`(vendored depth_anything_3 的
    DinoV2+DPT),之前最小依赖漏装 → 新 clone 跑 ②④/①③ 报 `ModuleNotFoundError: einops`。已加进安装
    列表 + 自检。`xformers` 有 try/except 回退,**不需要**。(纠正"DA3 是纯 torch"的错误判断。)
- **2026-08-11 —— 建本活文档 + 基础设施脚本化 + ④ 障碍生成器上线。**
  - 新增本 RUNBOOK(总入口 + 活文档约定)。
  - 新增 `experiments/aerial/scripts/{sync_push,sync_pull,start_renderer_4090,env_h100}.sh`
    + `RUNBOOK_sync_and_env.md`:把三机同步 / H100 临时容器建环境(torch cu128 + airsim,
    含 ensurepip / headless-cv2 / 两 checkout 坑)一键化。动因:每次代码提交/环境重建都极易出错。
  - `v0_rollout_eval.make_obstacle_facing_episodes` + `_v0_gate --rollout-dataset`:扫真实轨迹点找前向障碍,
    修 ④ 在开阔空域 `near_coll_rate_off=0` 的假失败(commit 540eb98/1c4178c)。属 ②④ **harness 几何修**,非 §4.1 改动。
  - 2026-08-11 首次带障碍生成器的 ②④ scan:`accepted 16/16`(前向障碍 ~21m);rollout 进行中,结果待记。
