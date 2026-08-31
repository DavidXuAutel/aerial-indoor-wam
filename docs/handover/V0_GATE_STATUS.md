# V0 Gate 状态活文档

> **用途**:`_v0_gate --merge` 到底还差什么,一处说清。**每次 gate 相关动作后必须更新本文件**(这是 Claude 会话间遗忘的补丁 —— Mac 侧 artifacts/ 无任何 emit JSON,历史结果全在 H100,不写这里就丢)。
> **权威性**:阈值以 frozen spec §4.1 为唯一真相源;信号现状以总 RUNBOOK §2 + 本文件为准。本文件**不新建阈值**。
> **关联**:总 RUNBOOK [`experiments/aerial/RUNBOOK_v0.md`](../../experiments/aerial/RUNBOOK_v0.md)（顶层入口 + 文档地图）；活文档阅读顺序见 [`LIVING_DOCS.md`](LIVING_DOCS.md)。
>
> **防误读（2026-08-17）**：若你看到「`_v0_gate --merge` 从未 exit 0 / 四信号 0/4 可 merge / 仍卡在 Step 6 合拢」类备忘 —— 那是 **2026-08-12（晚¹⁹–晚²²）前后** 的诊断快照，**不是现状**。当时论证（✅≠权威 merge、①a–c dt-desync 实质失格、证明力缩水、n&lt;16）多数属实；**2026-08-14 已在同一 r60 ft-head 下 merge PASS**（见 §1）。读现状以 **§1 + §2** 为准；§3.3 / RUNBOOK §8 晚¹⁹–²² 仅作历史。当前主线已过 V0/V1，见 [`V4_GATE_STATUS.md`](V4_GATE_STATUS.md)。

---

## 1. 一句话结论(2026-08-14)

**✅ 四信号已在「同一 r60 ft-head + 一次 merge」下合拢 PASS。** `_v0_gate --merge` exit 0 → `v0_gate_r60_20260814.json`(H100 `.25`); flags 已翻(`depth_head.enable` + `safety.kind: threshold`)。②④ **n=8**（现已与 frozen §4.1 对齐，re-freeze 2026-08-17）。④ **实证=④c** ratio=0.113；④b `n_contact=0` 为终态空过（`before_ok=null` / `before_vacuous=true`；JSON 仍 emit `before=1.0` 仅兼容，**不是**测得的干预先于接触）。

> **⚠️ supersede（2026-08-21，审计链：原文不改写）** —— 上段「④ PASS」在**有功效近带语料**下不再可作为 shield 安全性证据：同一 r60 部署头在 V4-⓪ **控制臂**（诚实 held-out）上 **⓪d 权威 FAIL**（`consec=2` 稳固；速率腿待 `n_near_forward_frames`）。性质同「V1 WM gate INVALIDATED」。**④ 标低功效、重新入列重跑**；④c `0.113` 本身不推翻。详见 §4.1 注记 + [`V4_GATE_STATUS.md`](V4_GATE_STATUS.md) §3 (J)–(R)。
>
> **⚠️ supersede 续（2026-08-21，只登记、暂不跑）** —— ④ 重跑 **绑定 depth head 定稿**（v3 不可用：①d FAIL + ⓪d/consec FAIL；部署线仍 r60 老头）。**在 head 定稿前不 launch** ④ rollout / partial emit。清单项 = E′ deferred；见 §3 E′ + [`V4_RUNBOOK_125_STATUS.md`](V4_RUNBOOK_125_STATUS.md)。

---

## 2. 四信号:还差什么

| 信号 | 判据(§4.1) | 最后已知结果 | **还差什么** |
|---|---|---|---|
| **①a–c** | loss↓≥2% / recon 不劣 / min entropy-frac ≥0.10 | ✅ **r60 clean WM 训练 PASS**(H100 2026-08-14): loss 3.87→1.96 / recon 0.065→0.021 / min_ent 0.47; `wm_train_meta.json` **authoritative=true**; ✅ **partial emit PASS** → `v0_partial_1_r60_20260814.json` | **无 —— partial 已落盘**(H100 2026-08-14) |
| **①d** | AbsRel ≤0.30 | ✅ head A 0.132(代表)/0.167(approach OOD);✅ **head B local 0.0483**(晚⁷);✅ **r60 ft-head holdout 0.0641**(同上 partial 1) | **无 —— r60 ckpt 已在 partial 1 通过** |
| **②** | N=**8**;progress ≥random+5.0 ∨ final_dist ≤random−3.0 | ✅ **r60 merge PASS**(H100 2026-08-14): progress **13.49** vs random **−4.30**; final_dist **16.54** vs **34.12**; **n=8** | **无 —— partial 24 + merge 已 PASS**（n 已 re-freeze） |
| **③** | reproj median 相对误差 ≤0.25;有效窗 ≥8 | ✅ head A 0.05–0.12(余量对 0.25 不宽);✅ **r60 ft-head median 0.212 / n=90**(H100 2026-08-14) | **无 —— partial 3 已落盘** |
| **④** | ④c ratio ≤0.80；④b ≥0.50 仅当有接触 | ✅ **r60 merge PASS**: ④c ratio **0.113**；④b **N/A**（`n_contact=0`，`before_vacuous`）；JSON `before=1.0` 仅兼容；**n=8** | **⚠️ 2026-08-21 更正：标低功效、重新入列；续：deferred（等 depth head 定稿，暂不跑）** —— 控制臂 `⓪d miss=0.076 / consec=2`；`n=8` 功效上界 ≈0.375。**④c `0.113` 不推翻**。详见 §4.1 + §3 E′ |

### 2.1 核心 gap:head 一致性

- **r60 部署线(2026-08-14)**: depth = `depth_ckpt_da3_r60_20260814`; WM = `wm_ckpt_r60_20260814`; 语料 = `dataset_v0_local_depth_r60_20260814`
- **Merge 权威 verdict**: `v0_gate_r60_20260814.json` — 四信号全 `ok=true`, exit 0
- **Flags 已翻**(2026-08-14): `depth_head.enable=true`, `safety.kind=threshold`; **`enable_wm_update` / `enable_policy_update` 仍 OFF**

---

## 3. 待办清单(按依赖排序)

- [x] **A. r60 depth ckpt 上跑 ③(仅 signal 3)** — ✅ `v0_partial_3_r60_20260814.json` PASS(median_rel 0.212, n=90)
- [x] ~~**B. ①a–c:先找 dry-run 的训练日志**~~ → **已查清,结论:重采语料**(2026-08-12 第三轮,详见 §3.3)
      日志找到了(`wm_ckpt_v2clean_20260810/wm_train.jsonl`,500 行,字段齐全),**三条判据全过且余量是量级的**:a loss 16.80→1.49(降 91%,只需 2%)、b recon 0.3245→0.0282(降 11.5×)、c min_ent 0.4368(需 ≥0.10,最小值在 step 2 ⇒ 全程无后验塌缩)。
      **但不能用** —— 见 §3.3 的失格理由(dt-desync 语料)。用户拍板:**重采一份语料**,不做语料考古。
- [x] **B'. 用合格语料重跑 ①a–c** ← 取代旧 B
      ~~`dataset_v1_rgb` 省事路径~~ → **撤回(2026-08-14)**:跨网语料不算 V0 训练集(runbook §目标)。
      **✅ 完成(2026-08-14)**:
      - **采集(4090)**: `dataset_v0_local_depth_r60_20260814` — 48/51 usable, `quarantine_fraction=0.059`, `grab_depth=true`, `step_hz=5.0`, tar+ssh → H100 `.25`
      - **DepthHead [1b](H100)**: `depth_ckpt_da3_r60_20260814/depth_step_2000_da3_ft_head.pt` — init from head B, holdout AbsRel **0.0641**(gate ①d ≤0.3), exit=0
      - **Clean WM(H100)**: `wm_ckpt_r60_20260814/wm_step_5000.pt` + `wm_train.jsonl` — **无 `--allow-v0-desync`**, `wm_train_meta.json` **authoritative=true**, learning+non-divergence PASS, exit=0
      - **H100 env**: `~/aerial-wam-v2/.venv`, `[env] READY`, torch 2.7.1+cu128, cuda H100 80GB
      - **Gate partial 1(H100)**: `v0_partial_1_r60_20260814.json` — `--signals 1` 含 ①a–c+①d(需 `--dataset`+`--depth-ckpt`), **PASS**
- [x] **C0. P0a: `predict_cones()` 落地** — Mac @ `27f11a3+`; `depth_geometry.py` + `DepthMinPredictor.predict_cones` 五向净空; **`predict_min()`/collector/safety 未动** → ④ 逐字节不变。单测 7/7 pass。
- [ ] **C1. P0b: shield 消费侧切到锥** — 在 ④ 重跑前做;会改 ④ 行为 → 需重跑 emit partial
- [x] **D. n 的 re-freeze** — ✅ 2026-08-17 用户拍板 **n=8**；见 §4
- [x] **E. ②④ 重跑** — ✅ `v0_partial_24_r60_20260814.json` PASS(n=8; ② progress 13.49/−4.30; ④c ratio 0.113; ④b N/A 空过)
- [ ] **E′. ④ 低功效重跑（2026-08-21 入列；2026-08-21 续：deferred）** — V4-⓪ 控制臂权威 FAIL 后 supersede；须在功效近带语料 / **定稿后的**感知头上重 emit ④（不降阈值）。**前置硬闸**：depth head 定稿（同时过 ⓪c/d 且 ①d 锚不丢；v3 不满足）。**现阶段只登记、不 launch rollout**。
- [x] **F. `--merge` 全四 partial JSON** — ✅ **`v0_gate_r60_20260814.json` MERGED PASS exit 0**; flags 已翻

### 3.1 H100 查证进展(2026-08-12 第一轮已回)

**已解除:③ 的盘挂载前置** —— `~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/dataset_v0_local_depth` **存在**(正是 §6 权威 gate 路径)。
⚠️ **存在两份同名语料**:`aerial-rl-skeleton/.../artifacts/` 与 `rl_collect_run/.../artifacts/` 各一份 → **一律用 `aerial-rl-skeleton/` 那份**(RUNBOOK §6 权威路径),勿混。
⚠️ `approach_scale_d18` 尚未确认存在,跑 ③ 前一并 `ls`。

**仍待查:①a–c 的 `wm_train.jsonl`** —— 用户首轮 `find` 用 `*log*` 匹配,**匹配不到 `.jsonl` 结尾的文件名,故漏搜**。
代码钉死:`_wm_train_validate.py:218` `log_path = ckpt_dir / "wm_train.jsonl"` —— 训练时**无条件写在 `--checkpoint-dir` 内部** → 大概率就在 `wm_ckpt_v2clean_20260810/` 里。

```bash
# 1. 找 dry-run 的 wm_train.jsonl
ls -la ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/wm_ckpt_v2clean_20260810/
find ~ -name "wm_train.jsonl" 2>/dev/null

# 2. 硬判据:是否带 recon/entropy 字段
head -1 ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/wm_ckpt_v2clean_20260810/wm_train.jsonl
wc -l ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/wm_ckpt_v2clean_20260810/wm_train.jsonl

# 3. ③ 的另一份语料
ls -d ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/approach_scale_d18 2>&1
```

**第 2 条是硬判据**(`_v0_gate.py:186-195`):日志缺 `recon_err`/`recon` 或 `post_entropy_frac`/`ent` **任一** → 直接判 FAIL,代码注释原话:"与其让 pass-safe 默认值(recon 0, ent 1)靠 loss drop 单独放行,不如判挂"。→ `head -1` 那行 JSON 的 key 直接决定 ①a–c 是**零成本出 verdict** 还是**必须重训**。

**已排除:7 月那批日志全部不可用** —— 用户列出的 `logs/ft/collapse_fix/train_20260731*.log`、`FastWAM/logs/train_*_2026072*.log` 等均为 **0720–0731**,属老 v1 时代;v2clean dry-run 是 **8/10**,时间对不上。且格式为 `.log` 非 `.jsonl`。**即便格式可转,语料也不是 Step-6 的 —— 拿 v1 崩掉的那次训练充当 V0 证据 = gaming,不做。**

### 3.3 ①a–c 已查清:v2clean 为何**实质失格**(不是记账疏漏)

**日志本身没问题**:`wm_ckpt_v2clean_20260810/wm_train.jsonl`(500 行)字段齐全,`check_learning_curves`(`v0_metrics.py:51`,k=500//10=50,首尾各 50 行取均值)三条全过、余量量级级:

| 判据 | 实测 | 阈值 | 余量 |
|---|---|---|---|
| a loss↓ | 16.7991 → **1.4948**(−91%) | 需 <16.4631(−2%) | ~11× |
| b recon 不劣 | 0.3245 → **0.0282** | 需 ≤0.3245 | 11.5× |
| c min entropy-frac | **0.4368**(argmin 在 step 2) | 需 ≥0.10 | 4.4×,**全程无后验塌缩** |

**但这份日志不能当 ①a–c 权威证据**,理由是语料而非数字:

`_wm_train_validate.py:45-77` `_refuse_v0()` 明文拒绝 `step_hz > 8.5` 的语料,报错原文 *"is the dt-desynced V0 corpus — **do not train a real WM on it**. Pass `--allow-v0-desync` **only to exercise the code path**"*。而 `collect_v1.sh:4` 记载 7 月 `dataset_v0` **标称 12 Hz、实测仅 7.1–8.3** → 标称 12 > 8.5 → **该语料必须靠 `--allow-v0-desync` 逃生舱才能训**。

→ 所以"非权威"是**实质失格**:漂亮的三条数字建立在一份代码明文写着"不要用它训真 WM"的 dt-desync 语料上。**用它充当 ①a–c 证据 = 拿逃生舱放行的训练冒充 gate 证据,性质等同调阈值凑过。**

**根因(已修,见 §3.4)**:`wm_train.jsonl` 只写 loss/recon/ent,**`--dataset` 完全不落盘** → 曲线无法自证语料 → 三周后无人能判权威性。**这就是"你经常忘"在代码层的对应物;不修,重采一份新语料后新日志同样不自证。**

### 3.4 根因修复(2026-08-12,Mac 侧已落):训练产物自证语料

`_wm_train_validate.py` 新增 `_write_train_meta()` → 训练**开始前**在 `--checkpoint-dir` 内写 `wm_train_meta.json`,记录:`dataset` 绝对路径、`dataset_manifest_meta`(含 `step_hz`/`grab_depth`)、`allow_v0_desync`、**`authoritative`(= not allow_v0_desync)**、episodes/transitions、steps/window/wm_batch、config、image_size、`git_sha`。用了逃生舱则 stdout 直接打 `⚠ allow_v0_desync=TRUE → NOT authoritative ①a–c evidence`。

**治理**:纯增量旁挂文件。`_v0_gate._signal1abc_from_log` **只 parse `.jsonl`、从不读该文件** → 冻结 §4.1 verdict **逐字节不变**;未动阈值/shield/env/模型/flags。训练前写以便崩溃/中断也留痕。
**测试**:`tests/test_wm_train_meta.py` 4 例(记录语料并标 authoritative / `--allow-v0-desync` 标 authoritative=False / 缺 manifest 不抛 / 不污染 gate 读的 `.jsonl`);模块级 `importorskip("torch")` 照 `test_dynamics_torch.py:12` 惯例 → Mac 跳过、H100 真跑。**Mac 全套 177 passed / 3 skipped,无回归。**

### 3.2 悬空引用（已确认不存在 — 2026-08-17）

下列路径在 Mac / 本仓库全盘 `find` **均不存在**（从未落盘或只写在别的 worktree 未合并）。**禁止再当作权威文档链接**：

| 悬空路径 | 原引用 | 唯一残留载体 |
|---|---|---|
| `docs/handover/2026-08-12-v2-plan-risk-assessment.md` | RUNBOOK §8 晚²⁰ | **RUNBOOK §8 晚²⁰ 正文**（证明力缩水 / 信号3 定义漂移等） |
| `docs/handover/2026-08-12-v0-gate-status-and-roadmap.md` | 晚¹⁹「单一权威文档」 | **本文件 + RUNBOOK §8 晚¹⁹** |

本文件 header **不再**关联上述空路径。RUNBOOK §8 历史条目可保留日期叙事，但其中文件名视为死链。

### 3.5 4090 文档冲突（仍开放）

两处 handover **对立**，卡在「①a–c / 采集是否在 4090 checkout 代码」：

| 文档 | 说法 |
|---|---|
| [`RUNBOOK_sync_and_env.md`](../../experiments/aerial/scripts/RUNBOOK_sync_and_env.md) L13 | 4090「只跑渲染，不 pull 代码」 |
| [`2026-08-04-v0-4090-local-collect-runbook.md`](2026-08-04-v0-4090-local-collect-runbook.md) | 采集必须在 4090；「禁止 scp 热补丁 → 4090 上 git checkout/pull」 |

**实操（r60）偏向后者**：`~/aerial-wam-v2` + `env_4090.sh` + loopback `:41451`。待办：统一改 sync RUNBOOK 措辞，避免再靠口头推断。

---

## 4. n re-freeze（用户拍板 2026-08-17：`n=8`）

**已收口。** frozen spec §4.1 ②a `n_eval_episodes`：**16 → 8**。

| 项 | 值 |
|---|---|
| 冻结值 | **8**（V0 ②④ / V1-① / V4-① 下限） |
| 理由 | r60 scan 喂满 16 不可达；强做必重引晚⁸–晚¹⁴ harness 几何 bug |
| 代码 | `v0_metrics.n_eval_episodes=8`；V4 `n<8` → `authoritative=false`，merge 拒收 |
| 历史 | 2026-08-12 曾「待用户定 n」；2026-08-14 在 n=8 上 merge/翻 flags（当时相对旧冻结值 16 为越界）→ 本次文书 re-freeze 把第一真相源对齐到已发生的权威跑 |

**诚实边界（洞 1）**：这是**事后合法化**——08-14 先在 n=8 上 merge 并翻 flags，08-17 才把冻结值从 16 对齐到 8。理由实质性（scan 喂满 16 不可达 / 会重引 harness bug），**不是为凑过**，且上表自陈顺序。严格说：V0 从「相对旧冻结值的越界通过」变成「事后合法化的通过」，**不是**「事前干净通过」。合法性轴已关；**不**与 V1-① 统计功效脆弱（另案）混淆。

**不再追 scan 喂满 16。**

### 4.1 洞 2：④b 空过终态（2026-08-17）

**已收口（文书 + 指标诚实字段）。** r60 ④ `n_contact=0` → ④b 无测量。frozen §4.1 现写明：此为 **3.0 m 反应余量下的接受终态**；④ 实证在 **④c**；`before_ok=null` / `before_vacuous=true`。不另造接触对照（除非将来要主张 ④b 数字）。

> **⚠️ supersede 注记（2026-08-21，V4-⓪ 控制臂出数后加；上文原文不改写）** —— **本节的收口理由被 V4-⓪d 削弱，④ 须重新入列重跑。**
> - 收口理由是「**3.0 m 反应余量下的接受终态**」，其**前提** = 罩在 3.0 m 处会触发。但 V4-P3 控制臂（`artifacts/v4_zero_p3_oldhead_merged_20260821.json`）在**同一个头** `depth_ckpt_da3_r60_20260814/depth_step_2000_da3_ft_head.pt`（= ②④ rollout / r60 部署线）上、**诚实 held-out** + **support 充足**（315 近带帧）测得 **`P(D̂_forward > 3.0 | GT_forward ≤ 3.0) = 0.076 > 0.05`，且 `max_consec_miss = 2` 直接违反「不得 ≥2 连续漏触发帧」** ⇒ **该头在 7.6% 的近障机会上罩根本没触发** ⇒ `n_contact=0` 更可能来自 **n=8 太小**，而非余量足够。
> - **功效算术**：④ 的 `n=8` + `0 接触` ⇒ 接触率 95% 上界 ≈ **3/8 = 0.375** ⇒ **「零接触」与「接触率高达 37%」在该样本量下不可区分**。
> - **不受影响的部分**：**④c `ratio=0.113` 的 PASS 不推翻** —— 它测的是罩对行为的改变量，不是漏触发。受影响的是 ①「④ 整体可作为 shield 安全性证据」这一读法、②「④b 空过 = 余量足够」这一解释。
> - **动作**：④ **标低功效、重新入列重跑**（无论最终采用哪个 depth head）；换头则本就必须重跑（红线「训练 / 部署的 shield-τ-depth 路径一致」）。**不降 §4.1 任何阈值。**

---

## 5. 治理红线（V0 已过关；V1/V4 仍适用）

- V0 flags **已翻**（2026-08-14）；**V1/V4 flags 仍 OFF**
- **不为凑过调 §4.1 阈值**；shield 控制律可改，阈值改需 re-freeze
- 代码走 git,禁 scp 热补丁

---

## 6. 变更记录

- **2026-08-21** — **④ 重跑登记为 deferred（只登记、暂不跑）**。改了什么：**仅文书**；§1 banner 加续 supersede；§3 E′ 标 deferred + 硬闸「depth head 定稿」；**未 launch** rollout、**未改** §4.1 阈值/flags。为什么：④ 绑定感知头；v3 头不可用（①d/⓪d）；须等头定稿后再重 emit。见 [`V4_GATE_STATUS.md`](V4_GATE_STATUS.md) §3 (AI)、[`V4_RUNBOOK_125_STATUS.md`](V4_RUNBOOK_125_STATUS.md)。
- **2026-08-21** — **④ 判为低功效、重新入列重跑（依据 = V4-⓪ 控制臂；原文不改写，注记加在 §1 banner + §4.1）**。改了什么：给 §1 一句话结论加 supersede banner；§4.1（洞 2）与 §2 的 ④ 行加 supersede 注记；**未改任何 §4.1 阈值、未改 flags**。为什么：V4-P3 控制臂在**同一个 r60 部署头**上、诚实 held-out + 315 近带帧 support 下测得 **⓪d 权威 FAIL**（稳固支点 = `max_consec_miss=2`；速率腿待 `n_near_forward_frames`）。功效：`n=8` + `0 接触` ⇒ 接触率 95% 上界 ≈ 3/8 = **0.375**。**④c `ratio=0.113` 不推翻**。产物：`artifacts/v4_zero_p3_oldhead_merged_20260821.json`；详见 [`V4_GATE_STATUS.md`](V4_GATE_STATUS.md) §3 (J)–(R)。
- **2026-08-17** — §4 **诚实边界**显式化：洞 1 = 事后合法化（08-14 merge@n=8 → 08-17 冻结对齐），非事前干净通过；与 V1-① 功效正交。
- **2026-08-17** — **洞 2 收口**：④b `n_contact=0` 接受为终态（`before_ok=null` / `before_vacuous`）；④ 实证=④c；JSON `frac=1.0` 仅兼容。§3 待办 D 标为已完成（洞 1）。
- **2026-08-17** — **n re-freeze 收口**：frozen §4.1 `n_eval_episodes` 16→**8**（用户拍板）；V4 `n<8` 非权威。洞 1 关闭。防误读注 / 悬空引用 / §3.5 4090 冲突见同日更早条目；阅读顺序见 [`LIVING_DOCS.md`](LIVING_DOCS.md)。
- **2026-08-17** — 防误读：header 标明「8/12 Step-6 / merge 从未 exit 0」类备忘≠现状；§3.2 悬空引用结案为不存在；新增 §3.5 4090 双 runbook 冲突；阅读顺序见 [`LIVING_DOCS.md`](LIVING_DOCS.md)。
- **2026-08-15** — V0 合拢后文档同步 + V1/V4 设计：新增 [V1/V4 设计](../design/2026-08-15-v1-v4-design.md)、[V1_GATE_STATUS.md](V1_GATE_STATUS.md)；更新 `PROJECT_STATUS.md` / `RUNBOOK_v0.md` / `README.md`。
- **2026-08-14(晚⁴)** —— **V0 GATE 合拢 + flags 翻转**:
  1. **②④ rollout PASS**(H100→4090): `v0_partial_24_r60_20260814.json`; scan 10/16 accepted → eval **n=8**; ② progress 13.49 vs −4.30; ④ ratio **0.113**, before=1.0(空过)
  2. **Merge PASS exit 0**: `v0_gate_r60_20260814.json` = partial 1 + 3 + 24; 四信号全 `ok=true`
  3. **Flags 翻转**(`configs/aerial_rl.yaml`): `depth_head.enable=true`, `safety.kind=threshold`; V1/V4 flags **仍 OFF**
  4. **Git**: commit **`cad5a08`** pushed origin+github; 4090 pulled; H100 bundle sync
- **2026-08-14(晚³)** —— **git + 语料 + ②④ rollout 启动**:
  1. **Git**: Mac commit **`caa28e6`**(`P0a predict_cones` + r60 scripts + gate doc) → pushed **origin(4090 bare)** + **github**; 4090 pulled; H100 synced via **git bundle** → `caa28e6`
  2. **r60 语料核实**: `dataset_v0_local_depth_r60_20260814` — **51 npz** / **48 usable** / 3 quarantined(`quarantine_fraction=0.059`) on **4090 + H100**; manifest OK; `grab_depth=true`, `step_hz=5.0`
  3. **Gate partials 已有(H100)**: `v0_partial_1_r60_20260814.json`(① PASS), `v0_partial_3_r60_20260814.json`(③ median 0.212)
  4. **②④ rollout 启动(H100→4090)**: `_v0_gate --signals 2,4 --rollout-eval`, depth=`depth_ckpt_da3_r60_20260814`, rollout-dataset=`dataset_v0_headon_20260811`, emit=`v0_partial_24_r60_20260814.json`, log=`~/aerial-wam-v2/artifacts/v0_gate_24_r60.log`, PID≈6143; scan 进行中(10/16 accepted @440/1000 时)
  5. **Next**: partial 24 PASS → `--merge` 1+3+24 → exit 0 → flip `depth_head.enable` + `safety.kind: threshold`
- **2026-08-14(晚²)** —— **B' 管线完成(H100 `.25`)**:
  1. **PASS coarse verify**: manifest `grab_depth=true`, `step_hz=5.0`, `quarantine_fraction=0.059≤0.20`, npz keys depth/imu_*/timestamps/vel OK
  2. **Step 3 DepthHead**: `depth_ckpt_da3_r60_20260814/` — finetune from `depth_ckpt_da3_near_20260811`, holdout AbsRel 0.0641, DEPTH_EXIT=0
  3. **Step 4 Clean WM**: `wm_ckpt_r60_20260814/` — 5000 steps, `authoritative=true`, `allow_v0_desync=false`, WM_EXIT=0; loss 3.87→1.96, recon↓, min_ent 0.47
  4. **Next**: `_v0_gate --signals 1 --learning-log .../wm_train.jsonl` emit partial; then A(③ on head B r60 ckpt)
- **2026-08-14(晚)** —— **P0a 完成**: `predict_cones()` 五向(forward/left/right/up/down);共享 `depth_geometry.py`;④ 未接。P0b 待做。
- **2026-08-14** —— B' 4090 重采启动;澄清单局提前结束≠整轮 abort;撤回 dataset_v1_rgb;同步改 tar+ssh(H100 `.25`)。详见 robomaster worktree 同名文件 §6。
- **2026-08-12(第三轮)** —— ①a–c 查清并**结案为"重采语料"**;根因(训练产物不自证语料)已在 Mac 侧修掉。
  1. **日志找到了**(用户 H100 实测):`wm_ckpt_v2clean_20260810/wm_train.jsonl` 500 行,`recon_err`/`post_entropy_frac` 齐全 → `_v0_gate.py:186-195` 的"缺字段直接 FAIL"分支不触发。首轮 `find` 用 `*log*` 匹配不到 `.jsonl`,故此前漏搜。
  2. **判据三条全过、余量量级**(见 §3.3 表)。
  3. **但语料实质失格** —— `_refuse_v0()` 明文拒 `step_hz>8.5`("do not train a real WM on it");7 月 `dataset_v0` 标称 12 Hz → 必须靠 `--allow-v0-desync`("only to exercise the code path")。→ **"非权威"不是记账疏漏。** 用户拍板重采,不做语料考古。
  4. **根因修复**(§3.4):新增 `wm_train_meta.json` 旁挂,记 dataset 绝对路径 + `step_hz` + `allow_v0_desync` + `authoritative` + git_sha,训练前写。**gate verdict 逐字节不变**;4 新单测;Mac 177 passed/3 skipped。
  5. 另记:H100 上有**两份** `wm_train.jsonl` —— `wm_ckpt/`(无日期,默认目录 fallback,疑 v1 时代)与 `wm_ckpt_v2clean_20260810/`。**喂 gate 必须用带日期的全路径**,勿混。
- **2026-08-12(第二轮修订)** —— 用户质疑"head B 的 ①③ 是硬通过的,为什么又要做 ①a–c 重训"。查证后三处订正:
  1. **①d 从待办移除** —— head B 上晚⁷ 已 PASS(0.0483),我上一版列成"approach 语料未跑"属重复列项。**待办只剩 ③。**
  2. **①a–c 不是"重训"而是"缺日志"** —— RUNBOOK line 23 + 晚¹⁹ line 117("①a–c 需 `--learning-log`")显示"非权威"卡在 (a) 非 Step-6 语料 (b) 未留日志;而 ①a–c 判 `_check_learning` **吃日志不吃 ckpt** → 日志若在则零训练成本出 verdict。上一版"V0 唯一未完成的训练工作"**定性过重,撤回**。
  3. **补上晚¹⁹ 的盘挂载卡点** —— `dataset_v0_local_depth`/`approach_scale_d18` 在可拆卸共享盘,.22 当时未挂载;这同时解释了 `~/aerial_ft_cache/` vs `~/aerial-rl-skeleton/` 的路径冲突(**分属不同盘**)。③ 的真实前置是盘,不只是命令。
  另发现 §3.2 两个悬空文档引用(含我自己在 RUNBOOK §8 晚²⁰ 引用却未落盘的评估报告)。**①a–c 不可砍的论证不变**(见 §3B)。
- **2026-08-12** —— 建本文件。动因:Mac 侧 `artifacts/` 无任何 emit verdict JSON,gate 历史结果全在 H100,跨会话必丢。核实内容:`_v0_gate.py:1260` merge 判据、`_ALL_SIGNALS=("1","2","3","4")`、artifacts 目录实际内容。确认 head 一致性为主 gap。head B 定性由"妥协"更正为"修复真实缺陷"(依晚⁶ 证据 + 用户确认)。
