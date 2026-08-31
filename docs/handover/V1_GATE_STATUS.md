# V1 Gate 状态活文档

> **用途**：V1 三信号 merge 进度与待办（镜像 `V0_GATE_STATUS.md` 治理模型）。  
> **前置**：V0 merge PASS — `v0_gate_r60_20260814.json`（2026-08-14）。  
> **设计（re-freeze 草案）**：[V1/V4 设计 §1.2](../design/2026-08-15-v1-v4-design.md#12-v1-三个同权过关信号re-freeze-草案2026-08-15)。

---

## 1. 一句话结论（2026-08-15 晚¹⁵ · rigor）

**✅ V1 merge PASS（严谨口径）** — ① **δ 实证** + ② honest held-out + ③ Phase 2 auth（含 V0 ③ reproj 证据绑定）。

| 主机 | HEAD |
|---|---|
| Mac / 125 bare / H100 | `86dd457`+（① 拒 tied-zero；晚¹⁵ 实测后文档提交） |

**yaml 已 flip**（`tau_predictor.kind=foe_calibrated`；`planner.enable`/`enable_policy_update` 仍 false）。  
**下一步**：[V4-MVP](../superpowers/specs/2026-08-16-v4-mvp-design.md) — V4 scaffold M1–M4 完成，见 [V4_GATE_STATUS](V4_GATE_STATUS.md)。②-coll 为独立诊断（§4.1），**不是** merge 重写。

产物（H100）：

- merge：`experiments/aerial/rl/logs/v1_gate_r60_20260815/v1_gate_r60_20260815.json`（`ok=true`）
- ①：`artifacts/v1_gate_r60_20260815/v1_partial_1_r60_20260815.json`
- ②：`logs/.../v1_partial_2_r60_20260815.json`
- ③：`logs/.../v1_partial_3_auth_r60_20260815.json`

---

## 2. 三信号（严谨复核后）

| 信号 | 判据 | 结果 |
|---|---|---|
| **V1-①** | `v0>0` 且 `v1 ≤ 0.8×v0`；V1=`foe_calibrated`；trigger=1.5 | ✅ **auth PASS**（当时判据）— `delta_reduction`；hard **v0=0.75 → v1=0.50**（target≤0.60）；off_hard=1.0。**功效脆弱（已记、未修）**：对 target 裕度 **0.8 局**；配对 McNemar **2:0**，**p≈0.5**。n=8 re-freeze **不**治此；条款②③ 见 [待签字草案](V1_SIGNAL1_POWER_REFREEZE_PROPOSAL.md) |
| **V1-②** | honest held-out；beat≥0.80；coll N/A if pos&lt;3 | ✅ **progress PASS** — goalvel beat=**0.93**；merge `coll_ok=null`（pos=1）；②-coll **诊断**另账（§4.1 r60：pos=5 / AUROC 0.972；§4.2 新 held-out：pos=20 / AUROC 0.977，unique usable coll ep=8） |
| **V1-③** | FOE+D̂；both_fail≤0.20；τ MAE≤2；**V0 ③ reproj≤0.25 同 ckpt** | ✅ auth PASS — both_fail=0.0013；MAE=0.935；`v0_reproj_evidence.median=0.212`（`v0_partial_3_r60_20260814.json`） |

### 软过 → 严谨（晚¹⁵）

| 信号 | 曾软过 | 问题 | 晚¹⁵ 处置 |
|---|---|---|---|
| **①** | `tied_zero_collision_bearing`（hard 双 0，trigger=3.0，τ=`gt_proxy`） | δ 未测；V1 非产品 τ | 代码默认拒 tied-zero；trigger=**1.5** + **foe_calibrated** 重跑 → **δ PASS** |
| **②** | merge JSON `coll_ok=true` | fidelity 仅 **+1/−11** 碰撞轨，AUROC 不应 authoritative | 按 §1.2.2 重记 **`coll_ok=null`**；overall 仍由 reward 等 PASS |
| **③** | `v0_reproj_note` 口头引用 | 未绑定数字/路径 | 写入 **`v0_reproj_evidence`**（median 0.212，n=90，同 r60 ft-head） |

---

## 3. 待办

- [x] V1a / 严谨 ① δ / ② honest / ③ Phase 2 auth + **merge**
- [x] **人工**：yaml `tau_predictor.kind=foe_calibrated` + `ckpt=.../tau_foe_calibrator.pt` (**flipped 2026-08-15 on 125**)
- [x] **洞 3 定义 + 诊断测量**：②-coll 为**独立诊断**（不改 08-15 merge）。headon coll=**0** 不能当 OOD。r60 `--n-starts 4` → `coll_traj_pos=5`、AUROC=0.972（unique held-out coll ep=2）。**2026-08-17** 新 WM-unseen held-out `dataset_v1_coll_heldout_20260817` → pos=**20** / AUROC=**0.977** / unique usable coll ep=**8** → `coll_claimed=true`（见 §4.2）。P0b / V4 仍开。
- [ ] **V1-① 功效条款②③（待签字）**：配对强制 + 裕度带 — [提案](V1_SIGNAL1_POWER_REFREEZE_PROPOSAL.md)。脆弱性已记入 §2；**未**改 merge / frozen。

---

## 4. 资产与数字

### ① authoritative（H100→4090，晚¹⁵）

| 项 | 值 |
|---|---|
| τ | `foe_calibrated` + `tau_ckpt_foe_r60_20260815/tau_foe_calibrator.pt` |
| trigger | **1.5 m**（metric band；非 3.0 standoff） |
| hard v0 / v1 / off | **0.75 / 0.50 / 1.0** |
| target_max | 0.60（δ=0.20） |
| **功效（记录）** | 裕度 **0.8 局**；McNemar **2:0**，p≈0.5 — **fragile**；见 [提案](V1_SIGNAL1_POWER_REFREEZE_PROPOSAL.md) |
| near_ep v0 / v1 | 0.625 / 0.875（hard 为主判据；near 未单独 gate） |
| scan | 8/8；probe collided=8 |
| log | `artifacts/v1_partial1_auth_rerun.log` |

### ② goalvel

| 项 | 值 |
|---|---|
| ckpt | `wm_ckpt_v1_heldout_goalvel_20260815/wm_step_5000.pt` |
| meta | `heldout_frac=0.25`，train eps=**36**/48，`authoritative=true` |
| fidelity | held-out 12 ep；beat=**0.933**；latent_norm_max=21.3 |
| coll（08-15 merge） | pos=**1** → N/A；`coll_claimed=false`；log AUROC=0.909 仅诊断；**不改写** |
| **②-coll 诊断（洞 3）** | §4.1 r60；§4.2 新 held-out（cleaner）；**不并入** 08-15 merge JSON |

### 4.1 ②-coll 诊断 — r60 held-out tail（2026-08-17；不改 08-15 merge）

**定义**：②-progress merge 仍只主张 reward/done/recon/latent；碰撞预测保真是**另开账本**的诊断。`v1_metrics.check_wm_fidelity` 增加 `coll_claimed`（`coll_ok is not None`）。

**语料计数**（`count_dataset_collisions.py`，npz `collided` 含 quarantine）：

| dataset | coll_eps | 能否当 ②-coll |
|---|---|---|
| `dataset_v0_headon_20260811` | **0** | **否** — headon-as-OOD 计划失败 |
| `dataset_v0_local_depth_r60_20260814` | **9**/51（quarantine 3 全是碰撞；usable 6） | 用 **held-out 窗**（下） |
| `dataset_v0_approach_merged` | 12 | 无 manifest，`_refuse_v0` 风险，未用 |
| `dataset_v0_depth_near_merged` | 14 | 同上，未用 |

**H100 作业** PID 33709 **已结束**（log `~/aerial-wam-v2/artifacts/v1_coll_fidelity_nstarts4.log`）。`_wm_fidelity_eval` 不 emit JSON；数字从 log 抄录：

| 项 | 值 |
|---|---|
| dataset / ckpt | r60；`wm_ckpt_v1_heldout_goalvel_20260815/wm_step_5000.pt` |
| split | `--heldout-frac 0.25`（12/48 tail；与 train meta `heldout_frac=0.25`、train eps=36 **同切**） |
| `--horizon` / `--n-starts` | 15 / **4** → 48 windows |
| `coll_traj_pos` / neg | **5** / 43 |
| `coll_auroc` | **0.972**（≥0.65） |
| reward beat / recon / latent | 1.00 / growth_ok / 21.60 |
| `v1_metrics` wrap | `coll_ok=true`，`coll_claimed=true`，`coll_insufficient=false` |

**泄漏/口径**：usable 碰撞 ep 6 条，train 切到 4 条（idx 14/15/30/31），held-out **2** 条（idx 46/47 = `episode_00049/00050.npz`）。eval 窗只来自 held-out，**无训练集约窗重叠**。`coll_traj_pos=5` 是这 2 条 ep 被 n-starts=4 加密出的**窗**数（规格门槛是窗，不是 unique ep）。unique collision ep≥3 的更严主张 → **已用** 4090 增采 held-out（§4.2）；**仍不把 08-15 merge 改成 coll PASS**。

```json
{
  "kind": "v1_2_coll_diagnostic",
  "not_a_merge_rewrite": true,
  "source_log": "artifacts/v1_coll_fidelity_nstarts4.log",
  "dataset": "dataset_v0_local_depth_r60_20260814",
  "heldout_frac": 0.25,
  "n_starts": 4,
  "coll_traj_pos": 5,
  "coll_traj_neg": 43,
  "coll_auroc": 0.972,
  "unique_heldout_collision_episodes": 2,
  "coll_claimed": true,
  "coll_ok": true
}
```

### 4.2 ②-coll 诊断 — WM-unseen held-out（2026-08-17；不改 08-15 merge）

活文档：[`V1_COLL_HELDOUT_COLLECT_125_STATUS.md`](V1_COLL_HELDOUT_COLLECT_125_STATUS.md)（collect DONE）· [`V1_COLL_HELDOUT_DIAGNOSTIC_STATUS.md`](V1_COLL_HELDOUT_DIAGNOSTIC_STATUS.md)。

| 项 | 值 |
|---|---|
| dataset | `dataset_v1_coll_heldout_20260817`（125→H100；usable 65；usable coll ep **8**） |
| ckpt | same goalvel `wm_step_5000.pt` |
| split | **`--heldout-frac 1.0`** — 全集为 WM-未见 OOD；勿用 0.25 误切 |
| `--horizon` / `--n-starts` | 15 / **4** → 260 windows |
| `coll_traj_pos` / neg | **20** / 240 |
| `coll_auroc` | **0.977** |
| `coll_claimed` / `coll_ok` | **true** / **true** |
| log / JSON | `artifacts/v1_coll_heldout_fidelity_20260817.log` · `artifacts/v1_coll_heldout_diagnostic_20260817.json` |

```json
{
  "kind": "v1_2_coll_heldout_diagnostic",
  "not_a_merge_rewrite": true,
  "dataset": "dataset_v1_coll_heldout_20260817",
  "heldout_frac": 1.0,
  "n_starts": 4,
  "coll_traj_pos": 20,
  "coll_traj_neg": 240,
  "coll_auroc": 0.977,
  "unique_usable_collision_episodes": 8,
  "coll_claimed": true,
  "coll_ok": true
}
```

### ③ auth FOE

| 指标 | 值 | 阈 |
|---|---|---|
| both_fail_frac | 0.0013 | ≤0.20 |
| tau_only_frac | 0.010 | ≥0.005 |
| tau_mae_s | 0.935 | ≤2.0 |
| depth_pred_vs_gt_both_fail | 0.0045 | ≤0.35（设计） |
| V0 ③ reproj median | **0.212**（n=90） | ≤0.25 |

---

## 5. 复现 merge

```bash
cd ~/aerial-wam-v2 && source experiments/aerial/scripts/env_h100.sh && export PYTHONPATH=$PWD
LOG=experiments/aerial/rl/logs/v1_gate_r60_20260815
ART=experiments/aerial/rl/artifacts/v1_gate_r60_20260815
python -m experiments.aerial.rl._v1_gate --merge \
  $ART/v1_partial_1_r60_20260815.json \
  $LOG/v1_partial_2_r60_20260815.json \
  $LOG/v1_partial_3_auth_r60_20260815.json \
  --emit $LOG/v1_gate_r60_20260815.json
```

严谨 ① 重跑：

```bash
python experiments/aerial/scripts/v1_gate_run_partials.py rollout4090 \
  --rollout-dataset ~/aerial-rl-skeleton/.../dataset_v0_headon_20260811 \
  --depth-ckpt ~/aerial-rl-skeleton/.../depth_ckpt_da3_r60_20260814/depth_step_2000_da3_ft_head.pt \
  --tau-kind foe_calibrated \
  --tau-ckpt ~/aerial-rl-skeleton/.../tau_ckpt_foe_r60_20260815/tau_foe_calibrator.pt \
  --shield-trigger-m 1.5 \
  --n-episodes 8 --device cuda
# 禁止 --allow-tied-zero
```

---

## 6. 变更记录

- **2026-08-17(晚²)** — **V1-① 功效缺口入账**：§2/§4 记 0.8 局裕度 + McNemar 2:0 p≈0.5；与 n re-freeze **正交**。条款②③ → [待签字提案](V1_SIGNAL1_POWER_REFREEZE_PROPOSAL.md)；**不改** 08-15 merge。
- **2026-08-17(晚)** — **②-coll 清洁 held-out**：125 采 `dataset_v1_coll_heldout_20260817`（usable 65 / usable coll ep 8）→ H100 `--heldout-frac 1.0` n-starts=4 → pos=**20** / AUROC=**0.977** → `coll_claimed=true`。**不改** 08-15 merge。
- **2026-08-17** — **洞 3 收口（定义+诊断）**：②-coll 独立诊断，不改 08-15 merge。headon coll=0 弃用；r60 n-starts=4 → pos=5 / AUROC=0.972 → `coll_claimed=true`（unique held-out collision ep=2）。`v1_metrics.coll_claimed`。
- **2026-08-15(晚¹⁵)** — **严谨复核**：① 拒 tied-zero 并 δ 重跑 PASS（0.75→0.50）；② `coll_ok` 改 N/A；③ 绑定 V0 reproj 证据；**merge 重出 ok=true**。代码 `86dd457`。
- **2026-08-15(晚¹⁴)** — Phase 2 FOE；auth ③；曾 merge（① 为 soft tied-zero，后撤销权威性）。
- **2026-08-15(晚¹³)** — ② goalvel beat=0.93。
- **2026-08-15(晚¹²…午)** — scaffold / 首跑 partial / harness 修复等（见 git log）。

---

## Deploy flip (follow-up 2026-08-15)

**Done on 125:** `tau_predictor.kind=foe_calibrated`, `use_gt_depth=false`, ckpt=`/home/a25689/aerial-rl-skeleton/experiments/aerial/rl/checkpoints/tau_ckpt_foe_r60_20260815/tau_foe_calibrator.pt`.

- `planner.enable` remains **false**
- `enable_policy_update` remains **false** (needs V4 gate re-freeze — do not flip)
- Next focus: **V4** entry (re-freeze checklist below)
- Ops: commit on 125 → push local bare `origin` → sync H100; Mac may sleep

### V4 entry checklist (do not start training update yet)

- [ ] Re-freeze V4 gate criteria in design doc
- [ ] Confirm imagination / actor-critic eval harness
- [ ] Only then consider flipping `enable_policy_update: true`
- [ ] Keep planner.enable policy separate from V4 AC update

