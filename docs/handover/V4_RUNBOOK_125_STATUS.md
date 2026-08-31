# V4 RUNBOOK 125 STATUS

- **date**: 2026-08-28
- **执行归属**：**后续任务一律 cursor-125 Agent**（经 bridge/`agent`）；Mac 只 git/handoff；H100 只经 125
- **代码同步**：125 `git fetch github && git merge github/main`（Mac push github；125 github 鉴权曾失败需修）
- **B′（DONE）**：B′-1 **weak_geometry**（window R²≈−0.55）；B′-2 window gap=**0.00177**≈single **0.0018** → encode 非主因
- **coll_rep H100（DONE · FAIL）**：`wm_ckpt_coll_rep_20260828/wm_step_1500.pt`；B gap=**−0.0020**；B′-1 仍 weak；learning gate FAIL；yaml 加压无效
- **下一步（125）**：须 **代码刀**（coll hinge / depth-aux 进 latent 监督）→ H100 再训 → 重跑 B；**勿优先 B′-3**；**禁止 E**
- **enable_policy_update**: false
- **H100 WM（coll_full）**：`wm_ckpt_coll_full_20260827/wm_step_1000.pt`
- **B 产物**：`…_h100full_…json` gap=0.0018；`…_collrep_20260828.json` gap=−0.0020
- **C2**：`dataset_wam_loop_20260827/` — 31 ep
- **目标诚实口径**：坐标目标，非视觉搜目标
- **安全栈**：深度+限速罩 = 覆盖层
- **旧 RUNBOOK_v4**：审计保留；日常以 `RUNBOOK_wam_imagination.md` 为准

## V4 主线 — 当前阻塞与下一发（125 / H100）

| 步 | 状态 | 下一发 |
|----|------|--------|
| **S5F** | ✅ 3/3 签；语料+support DONE | 见 fork 声明 |
| **S-8** | ❌ FAIL（①d/⓪c ✅；⓪i/⓪h ❌） | 归档 |
| **S-8b** | ❌ FAIL（①d/⓪c ✅；⓪i/⓪h ❌） | 归档 |
| **S-8c** | ❌ FAIL（①d/⓪c ✅；⓪i/⓪h ❌） | 归档 |
| **S-8d** | ❌ FAIL（①d 早停 **0.379>0.30**） | 归档；禁 ≥2.0 signed |
| **S-8e** | ❌ FAIL（engage **2.18 m** 回退） | 归档；停 signed |
| **S-8f** | ❌ FAIL（①d **0.310**@50） | 归档 |
| **S-8g** | ❌ FAIL（①d/⓪c ✅；⓪i/⓪h ❌） | 归档；fwd 轴枯竭；Pareto **S-8c** |
| **S-8h** | ❌ FAIL（①d/⓪c/⓪h ✅；⓪i ❌） | 归档；full engage **0.89** / consec **2**；Pareto **S-8c** |
| **S-8i** | ❌ FAIL（①d/⓪c/⓪h ✅；⓪i ❌） | 归档；full engage **0.56** / consec **2**；Pareto 曾记 S-8i → **现改 S-8j** — [`V4_DEPTH_FT_S8I_MIDRANGE_DECLARE_20260825.md`](V4_DEPTH_FT_S8I_MIDRANGE_DECLARE_20260825.md) |
| **S-8j** | ✅ **promote 部署** | G1′ ⓪i PASS — [`V4_DEPTH_PROMOTE_S8J_DECLARE_20260826.md`](V4_DEPTH_PROMOTE_S8J_DECLARE_20260826.md) |
| **S-8k** | ❌ FAIL（①d **0.3539**@50） | 归档；τ 0.95 破锚；**Pareto 曾 S-8j** — [`V4_DEPTH_FT_S8K_MIDRANGE_DECLARE_20260825.md`](V4_DEPTH_FT_S8K_MIDRANGE_DECLARE_20260825.md) |
| **S-8l** | ❌ FAIL（①d/⓪c/⓪h ✅；⓪i ❌） | 归档；full engage **0.86** / cap_l1 **0.84** / consec **1**（相对 S-8j **无改善**）；**Pareto 仍 S-8j** — [`V4_DEPTH_FT_S8L_MIDRANGE_DECLARE_20260825.md`](V4_DEPTH_FT_S8L_MIDRANGE_DECLARE_20260825.md) |
| **S-8m** | ❌ FAIL（①d/⓪c ✅；⓪h/⓪i ❌） | 归档；full engage **0.88** / cap_l1 **1.43** / consec **13**（相对 S-8j **回退**）；**Pareto 仍 S-8j** — [`V4_DEPTH_FT_S8M_MIDRANGE_DECLARE_20260825.md`](V4_DEPTH_FT_S8M_MIDRANGE_DECLARE_20260825.md) |
| **S-8n** | ❌ FAIL（①d/⓪c/⓪h ✅；⓪i ❌） | 归档；full engage **0.98** / cap_l1 **1.22** / consec **2**（相对 S-8j **回退**）；**Pareto 仍 S-8j** — [`V4_DEPTH_FT_S8N_MIDRANGE_DECLARE_20260825.md`](V4_DEPTH_FT_S8N_MIDRANGE_DECLARE_20260825.md) |
| **⓪i 改门** | ✅ G1′ + **S-8j promote** | 部署已切 — [`V4_DEPTH_PROMOTE_S8J_DECLARE_20260826.md`](V4_DEPTH_PROMOTE_S8J_DECLARE_20260826.md) |
| **P3 ⓪** | ✅ 6cr 老头 merge PASS（p45） | 部署已切 S-8j；老头仍作控制臂 |
| **P1** | ❌ `p_coll` AUROC 0.549 | P4.5 WM 上已重跑；coll 仍 FAIL |
| **P4 ⓿** | ⚠️ ⓿e `infeasible`（teleport） | 与 P4.5 **正交**；harness 侧并行 |
| **P7 / P8** | Post-P8 FAIL；**PL 5/5 ✅**；场景 **DEFER** | 125 A0/A1@6800 → 对照表 |

### H100 S-8g 结案（2026-08-25 · `declare_id=s8g-20260825`）

| 项 | 结果 |
|----|------|
| 签字 | **3/3 ✅** — [`V4_DEPTH_FT_S8G_MIDRANGE_DECLARE_20260825.md`](V4_DEPTH_FT_S8G_MIDRANGE_DECLARE_20260825.md) |
| 配方 | S-8c 底座；fwd AbsRel pinball **1.50**；signed **锁 1.5** |
| ①d holdout best | **0.1337 ✅** @ step 500（step50 **0.2356**） |
| ⓪c `(5,12.2]` | hold035 p90=**0.232** ✅ / full **0.224** ✅ |
| ⓪i engage p95 | hold035 **0.50 m** ❌ / full **1.04 m** ❌（预算 0.2 m） |
| ⓪i cap_l1 p95 | hold035 **1.05 m** ❌ / full **0.98 m** ❌ |
| ⓪h consec | hold035=**3** ✅ / full **8** ❌（须双切；`<4`） |
| ckpt | `depth_ckpt_p45mid_s8g_20260825/` — **归档不部署** |
| **部署** | 仍冻结老头；**Pareto 仍 S-8c**（full engage **0.75 m** / consec **5**） |
| **下一发** | **S-8h 已签开训** — absrel **0.55** — [`V4_DEPTH_FT_S8H_MIDRANGE_DECLARE_20260825.md`](V4_DEPTH_FT_S8H_MIDRANGE_DECLARE_20260825.md) |

- **产物**：`artifacts/v4_{zero_p3,three_zone}_s8g_{hold035,full}_20260825.json`
- **读法**：hold035 略好于 S-8c，但 full engage/consec **回退**（0.75→1.04；5→8）；fwd 1.25–1.50 轴枯竭（1.75 破 ①d）。

### H100 S-8h 结案（2026-08-25 · `declare_id=s8h-20260825`）

| 项 | 结果 |
|----|------|
| 签字 | **3/3 ✅** — [`V4_DEPTH_FT_S8H_MIDRANGE_DECLARE_20260825.md`](V4_DEPTH_FT_S8H_MIDRANGE_DECLARE_20260825.md) |
| 配方 | S-8c 底座；**唯一**变更 absrel **0.45→0.55**；fwd **1.25** / signed **1.5** 锁 |
| ①d holdout best | **0.1237 ✅** @ step 450（step50 **0.1854**） |
| ⓪c `(5,12.2]` | hold035 p90=**0.216** ✅ / full **0.206** ✅ |
| ⓪i engage p95 | hold035 **0.50 m** ❌ / full **0.89 m** ❌（预算 0.2 m） |
| ⓪i cap_l1 p95 | hold035 **1.08 m** ❌ / full **1.01 m** ❌ |
| ⓪h consec | hold035=**1** ✅ / full **2** ✅（首次双切 PASS） |
| ckpt | `depth_ckpt_p45mid_s8h_20260825/` — **归档不部署** |
| **部署** | 仍冻结老头；**Pareto 仍 S-8c**（full engage **0.75 m**；S-8h consec 更优但 engage 劣） |
| **下一发** | **S-8i 已结案 FAIL** — engage 改善但 ⓪i 未过；须换损失形 — [`V4_DEPTH_FT_S8I_MIDRANGE_DECLARE_20260825.md`](V4_DEPTH_FT_S8I_MIDRANGE_DECLARE_20260825.md) |
| 通路 | Mac → **`ssh cursor-125-public`** → H100 / 125 评 |

- **产物**：`artifacts/v4_{zero_p3,three_zone}_s8h_{hold035,full}_20260825.json`
- **读法**：absrel 0.55 保住 ①d 且 ⓪h 首次双切 PASS（consec 2）；full engage 0.75→**0.89 回退** ⇒ ⓪i FAIL；不 promote。

### H100 S-8i 结案（2026-08-25 · `declare_id=s8i-20260825`）

| 项 | 结果 |
|----|------|
| 签字 | **3/3 ✅** — [`V4_DEPTH_FT_S8I_MIDRANGE_DECLARE_20260825.md`](V4_DEPTH_FT_S8I_MIDRANGE_DECLARE_20260825.md) |
| 配方 | absrel **0.60**；fwd **1.25** / signed **1.5** 锁 |
| 训 | **DONE** 600/600；best ①d=**0.1325** @ step **500**（step50 **0.1810**） |
| PID / 日志 | PID **207816**（已退出）；`logs/v4_depth_s8i_h100_20260825.log` |
| ⓪c `(5,12.2]` | hold035 p90=**0.211** ✅ / full **0.205** ✅ |
| ⓪i engage p95 | hold035 **0.00 m** ✅ / full **0.56 m** ❌（预算 0.2 m） |
| ⓪i cap_l1 p95 | hold035 **1.24 m** ❌ / full **1.06 m** ❌ |
| ⓪h consec | hold035=**0** ✅ / full **2** ✅ |
| ckpt | `depth_ckpt_p45mid_s8i_20260825/` — **归档不部署** |
| **部署** | 仍冻结老头；**Pareto → S-8i**（full engage **0.56 m** / consec **2**；仍未过 ⓪i） |
| **下一发** | **S-8j 已结案 FAIL** — engage/cap_l1 改善但 ⓪i 未过；须新 declare（禁 silent 抬 hinge）— [`V4_DEPTH_FT_S8J_MIDRANGE_DECLARE_20260825.md`](V4_DEPTH_FT_S8J_MIDRANGE_DECLARE_20260825.md) |
| 通路 | Mac → **`ssh cursor-125-public`** → H100 / 125 评 |

- **产物**：`artifacts/v4_{zero_p3,three_zone}_s8i_{hold035,full}_20260825.json`
- **读法**：absrel 0.60 保住 ①d/⓪h；full engage 0.75→**0.56 改善**（§2#2 未触发枯竭）；但 ⓪i auth 仍 FAIL（cap_l1）；不 promote。

### H100 S-8j 结案（2026-08-25 · `declare_id=s8j-20260825`）

| 项 | 结果 |
|----|------|
| 签字 | **3/3 ✅** — [`V4_DEPTH_FT_S8J_MIDRANGE_DECLARE_20260825.md`](V4_DEPTH_FT_S8J_MIDRANGE_DECLARE_20260825.md) |
| 配方 | S-8i 底座；near overread hinge **1.0**；absrel/signed/fwd **锁** |
| 训 | **DONE** 600/600；best ①d=**0.1277** @ step **550**（step50 **0.2487**） |
| PID / 日志 | PID **209703**（已退出）；`logs/v4_depth_s8j_h100_20260825.log` |
| ⓪c `(5,12.2]` | hold035 p90=**0.223** ✅ / full **0.218** ✅ |
| ⓪i engage p95 | hold035 **0.44 m** ❌ / full **0.45 m** ❌（预算 0.2 m） |
| ⓪i cap_l1 p95 | hold035 **0.93 m** ❌ / full **0.83 m** ❌ |
| ⓪h consec | hold035=**1** ✅ / full **1** ✅ |
| ckpt | `depth_ckpt_p45mid_s8j_20260825/` — **归档不部署** |
| **部署** | 仍冻结老头；**Pareto → S-8j**（full engage **0.45 m** / consec **1** / cap_l1 **0.83 m**；仍未过 ⓪i） |
| **下一发** | **S-8k 已结案 FAIL** — τ 0.95 破 ①d；须新 declare 换形（禁 τ≥0.98 / 禁抬 hinge·权）— **未自动起草** |
| 通路 | Mac → **`ssh cursor-125-public`** → H100 / 125 评 |

- **产物**：`artifacts/v4_{zero_p3,three_zone}_s8j_{hold035,full}_20260825.json`
- **读法**：hinge 1.0 保住 ①d/⓪h；相对 S-8i full engage/cap_l1 **改善**（0.56→0.45；1.06→0.83）但 ⓪i 仍 FAIL；不 promote。

### H100 S-8k 结案（2026-08-25 · `declare_id=s8k-20260825`）

| 项 | 结果 |
|----|------|
| 签字 | **3/3 ✅** — [`V4_DEPTH_FT_S8K_MIDRANGE_DECLARE_20260825.md`](V4_DEPTH_FT_S8K_MIDRANGE_DECLARE_20260825.md) |
| 配方 | S-8j 底座；signed pinball τ **0.95**；权/hinge/absrel/fwd **锁** |
| 训 | **DONE FAIL** early-stop @ step **50**；①d=**0.3539** ❌（S-8j step50 曾 **0.2487**） |
| PID / 日志 | PID **211331**（已退出）；`logs/v4_depth_s8k_h100_20260825.log` |
| ⓪c / ⓪i / ⓪h | **SKIP**（①d 破锚不过线） |
| ckpt | `depth_ckpt_p45mid_s8k_20260825/` — **归档不部署** |
| **部署** | 仍冻结老头；**Pareto 仍 S-8j**（full engage **0.45 m** / consec **1** / cap_l1 **0.83 m**） |
| **下一发** | **S-8l 已结案 FAIL** — p90 形无改善 engage；须新 declare 换形（禁再抬 p90 / τ≥0.95 / hinge·权）— **未自动起草** |
| 通路 | Mac → **`ssh cursor-125-public`** → H100 |

- **读法**：τ 0.95 单轴换形即破 ①d；本形失败；不 promote。

### H100 S-8l 结案（2026-08-25 · `declare_id=s8l-20260825`）

| 项 | 内容 |
|----|------|
| 文书 | [`V4_DEPTH_FT_S8L_MIDRANGE_DECLARE_20260825.md`](V4_DEPTH_FT_S8L_MIDRANGE_DECLARE_20260825.md) |
| 签字 | **3/3 ✅**（用户 / 2026-08-25） |
| 配方 | S-8j 底座；`near_absrel_p90` **1.0@τ=0.9**；hinge/signed/absrel/fwd **锁** |
| 训 | **DONE** 600/600；best ①d=**0.1292** @600 ✅ |
| PID / 日志 | PID **212673**（已退出）；`logs/v4_depth_s8l_h100_20260825.log` |
| 125 评 | **DONE FAIL**；⓪c ✅（0.186/0.172）；⓪h ✅（consec **0/1**）；⓪i ❌（engage 0.43/**0.86 m**；cap_l1 0.93/0.84） |
| ckpt | `depth_ckpt_p45mid_s8l_20260825/` — **归档不部署** |
| **部署** | 仍冻结老头；**Pareto 仍 S-8j**（full engage **0.45 m** / consec **1** / cap_l1 **0.83 m**） |
| **下一发** | **S-8m 已结案 FAIL** — 域切否证；须新 declare（禁再缩域同向；禁 τ≥0.95 / 抬 hinge·p90·权）— **未自动起草** |
| 通路 | Mac → **`ssh cursor-125-public`** → H100 / 125 评 |

- **产物**：`artifacts/v4_{zero_p3,three_zone}_s8l_{hold035,full}_20260825.json`
- **读法**：p90 对称尾权保住 ①d，但 full engage **回退**（0.45→0.86）；本形失败；不 promote。

### H100 S-8m 结案（2026-08-25 · `declare_id=s8m-20260825`）

| 项 | 内容 |
|----|------|
| 文书 | [`V4_DEPTH_FT_S8M_MIDRANGE_DECLARE_20260825.md`](V4_DEPTH_FT_S8M_MIDRANGE_DECLARE_20260825.md) |
| 签字 | **3/3 ✅**（用户 / 2026-08-25） |
| 配方 | S-8j 底座（无 p90）；**唯一**变更 near-focus **(5,12.2]→(7,12.2]** |
| 训 | **DONE** 600/600；best ①d=**0.1387** @550 ✅（step50 **0.2000**） |
| PID / 日志 | PID **216603**（已退出）；`logs/v4_depth_s8m_h100_20260825.log` |
| 125 评 | **DONE FAIL**；⓪c ✅（0.228/0.214）；⓪h ❌（consec **13/13**）；⓪i ❌（engage 0.90/**0.88 m**；cap_l1 1.80/1.43） |
| ckpt | `depth_ckpt_p45mid_s8m_20260825/` — **归档不部署** |
| **部署** | 仍冻结老头；**Pareto 仍 S-8j**（full engage **0.45 m** / consec **1** / cap_l1 **0.83 m**） |
| **下一发** | **S-8n 已结案 FAIL** — fwd-hinge 否证 — [`V4_DEPTH_FT_S8N_MIDRANGE_DECLARE_20260825.md`](V4_DEPTH_FT_S8N_MIDRANGE_DECLARE_20260825.md) |
| 通路 | Mac → **`ssh cursor-125-public`** → H100 / 125 评 |

- **产物**：`artifacts/v4_{zero_p3,three_zone}_s8m_{hold035,full}_20260825.json`
- **读法**：lo=7 保住 ①d/⓪c，但 ⓪h 退化 + engage/cap_l1 相对 S-8j **回退**；本域切失败；不 promote。

### H100 S-8n 结案（2026-08-25 · `declare_id=s8n-20260825`）

| 项 | 内容 |
|----|------|
| 文书 | [`V4_DEPTH_FT_S8N_MIDRANGE_DECLARE_20260825.md`](V4_DEPTH_FT_S8N_MIDRANGE_DECLARE_20260825.md) |
| 签字 | **3/3 ✅**（用户 / 2026-08-25） |
| 配方 | S-8j 底座；**唯一**变更 fwd overread hinge **0→1.0**；focus **(5,12.2]** 锁；无 p90 |
| 训 | **DONE** 600/600；best ①d=**0.1274** @450 ✅（step50 **0.2406**） |
| PID / 日志 | PID **218106**（已退出）；`logs/v4_depth_s8n_h100_20260825.log` |
| 125 评 | **DONE FAIL**；⓪c ✅（0.205/0.198）；⓪h ✅（consec **0/2**）；⓪i ❌（engage 0.00/**0.98 m**；cap_l1 1.25/1.22） |
| ckpt | `depth_ckpt_p45mid_s8n_20260825/` — **归档不部署** |
| **部署** | 仍冻结老头；**Pareto 仍 S-8j**（full engage **0.45 m** / consec **1** / cap_l1 **0.83 m**） |
| **下一发** | **⓪i 改门待签** — G1 operational **1.0 m** — [`V4_0I_BUDGET_REFREEZE_DECLARE_20260825.md`](V4_0I_BUDGET_REFREEZE_DECLARE_20260825.md) |
| 通路 | Mac → **`ssh cursor-125-public`** → H100 / 125 评 |

- **产物**：`artifacts/v4_{zero_p3,three_zone}_s8n_{hold035,full}_20260825.json`
- **读法**：fwd-hinge=1.0 保住 ①d/⓪c/⓪h，但 full engage/cap_l1 相对 S-8j **回退**；本形失败；不 promote。

### ⓪i 改门声明（2026-08-25 · **G1 全签 ✅ · 重评 DONE**）

| 项 | 内容 |
|----|------|
| 文书 | [`V4_0I_BUDGET_REFREEZE_DECLARE_20260825.md`](V4_0I_BUDGET_REFREEZE_DECLARE_20260825.md) |
| 裁定 | **G1**：primary budget **0.2→1.0 m**；z1/z2 报告；z3/collision 探针 **HARD**；①d/⓪c/⓪h 不变 |
| **S-8j @1.0 m** | engage/cap_l1 **budget PASS**（0.45/0.83）；**stop FAIL**（z3 @ probe 0.83–0.93）⇒ ⓪i ❌ |
| **vs 0.2 m** | 旧 = budget FAIL；新 = budget PASS、改由 stop 阻塞 |
| **部署** | **仍冻**（G0i-4）；不剥 OR；**不** promote |
| 备选（本轮不签） | G2 collision-only **7.2 m**（过宽，或放过老头） |
| **supersede** | stop 硬度 → **G1′**（下节） |

### ⓪i 停线探针重签（2026-08-26 · **G1′ 全签 ✅ · 125 重评 DONE**）

| 项 | 内容 |
|----|------|
| 文书 | [`V4_0I_STOP_PROBE_REFREEZE_DECLARE_20260826.md`](V4_0I_STOP_PROBE_REFREEZE_DECLARE_20260826.md) |
| 裁定 | **G1′**：budget **1.0 m**；collision HARD；z3 报告；primary = `all_bands_ok ∧ no_collision_probe` |
| **S-8j** | hold035+full **⓪i auth PASS**（engage 0.45 / cap_l1 0.83；probe z3 报告、collision=0） |
| **老头** | hold035+full **⓪i FAIL**（budget；full 另 ⓪h consec 8） |
| **部署** | ✅ **已切 S-8j**（promote 2026-08-26） |
| 产物 | `artifacts/v4_three_zone_{s8j,oldhead}_{hold035,full}_g1prime_20260826.json` |

### 深度头 promote S-8j（2026-08-26 · **全签 ✅ · yaml DONE**）

| 项 | 内容 |
|----|------|
| 文书 | [`V4_DEPTH_PROMOTE_S8J_DECLARE_20260826.md`](V4_DEPTH_PROMOTE_S8J_DECLARE_20260826.md) |
| **to** | `depth_ckpt_p45mid_s8j_20260825/depth_best_holdout_da3_ft_head.pt` |
| yaml | `configs/aerial_rl.yaml` → `world_model.depth_head.checkpoint_path` |
| OR / safety | **未改** |
| policy | `enable_policy_update` **仍 false** |

### P7-diag（2026-08-26 · S-8j + three_zone · **DONE** → 权威 spare 趟）

| 项 | 首趟 | **权威（P0c spare）** |
|----|------|------------------------|
| 产物 | `artifacts/v4_p7_diag_s8j_20260826.json` | **`artifacts/v4_p7_diag_s8j_spare_20260826.json`** |
| spare 清单 | — | `artifacts/v4_p7_diag_spare_manifest_20260826.json` |
| 栈 | depth=**S-8j**；safety=**three_zone**；WM=`wm_ckpt_p45_merged_20260821` | **同左** |
| n_scored | 9/16（spawn 跳过） | **16**；`authoritative=true`（spare_consumed=1；invalid_spawn=1） |
| **arrival** | ≈0.22 | **0.1875**（3/16） |
| hard_coll | — | **0.4375**（7/16） |
| **C_P7** | p25=**1.50**；median=2.84 | p25=**1.83**；median=3.71 |
| **5ab** | 空带 ⇒ ①′d-b **secondary** | **仍空带** |
| θ / `[lo,hi]` | 不冻 | **依法不冻** |

**读法**：逼障带不可冻；planner 在 blocked 层到达率 **≪0.50** ⇒ 走 **5ai**（见下）。

### 5ai 下车站（2026-08-26 · **登记生效**）

| 项 | 内容 |
|----|------|
| 文书 | [`V4_5AI_P7_STATION_STOP_DECLARE_20260826.md`](V4_5AI_P7_STATION_STOP_DECLARE_20260826.md) |
| 触发 | 5ab 空带 + spare auth arrival **0.1875** ≪0.50 |
| P7-accept | **跳过**（无外生 θ；禁换 seed 再冲） |
| **P8** | **BLOCKED** |
| 禁 | 降 0.50 / 换易起点宣称过 / 只判 S_open；启用 v5；改三线凑带；剥 OR |
| 合法续跑 | 退回感知/WM **或** 场景难度 re-freeze（**另案签字**） |
| policy | `enable_policy_update` **仍 false** |

### TZ 另案（2026-08-26 · **5/5 全签 ✅** · accept′ **DONE**）

| 项 | 内容 |
|----|------|
| 文书 | [`V4_TZ_CRITERIA_REFREEZE_DECLARE_20260826.md`](V4_TZ_CRITERIA_REFREEZE_DECLARE_20260826.md) |
| harness | `tz_band.py` + collector `shield_channels`；单测 6 passed |
| **P7-diag′** | ✅ `artifacts/v4_p7_diag_tz_s8j_20260826.json` — n=16 auth；arrival=**0.25**；hard_coll=**0.375**；band_frac median=**0.293**；C_P7 p25=**1.56**；seed=1100 |
| **θ freeze** | ✅ `artifacts/v4_p7_tz_theta_freeze_20260826.json` — θ=**0.2344**（≥0.10） |
| **P7-accept′** | ❌ **FAIL** — `artifacts/v4_p7_accept_tz_s8j_20260826.json` — n=16 auth；arrival=**0.1875**；hard_coll=**0.5**；band_frac median=**0.379**；C_P7 p25=**1.75**；seeds 2100/3100 |
| **5ai′** | ✅ 登记 — [`V4_5AIP_P7_STATION_STOP_DECLARE_20260826.md`](V4_5AIP_P7_STATION_STOP_DECLARE_20260826.md) |
| **P8** | **BLOCKED** |

### ATTR 归因（2026-08-26 · **5/5 全签 ✅** · **DONE**）

| 项 | 内容 |
|----|------|
| 文书 | [`V4_5AIP_ATTR_DECLARE_20260826.md`](V4_5AIP_ATTR_DECLARE_20260826.md) |
| 产物 | `artifacts/v4_p7_attr_tz_n32_20260826.json` / `logs/v4_p7_attr_tz_n32_20260826.log` |
| 语料 | n=32 auth；seed **4100**；S_blocked；S-8j + three_zone |
| rates | arrival=**0.0938**；hard_coll=**0.5625** |
| outcomes | hard_coll=18；tau_latch=10；arrived=3；timeout=1；stuck_l3=0 |
| **fork** | **label=percept**（majority_percept）；n_percept=**9** / n_plan=**0** / n_unclear_hc=9；n_hard_coll=**18** |
| **next_action** | 原 **sign_depth_ft_declare**；已让路 L3 brake → **L3 brake re-ATTR FAIL**（速度门）；depth **仍挂起另签** |
| harness | `d_hat_fovmin` non-null **3434/3434**；`tau_hat` **3433/3434** |
| 红线 | 不解 5ai′；不开 P8；不降 0.50；不训 actor/WM/depth 至另签 |

### L3 主动刹车 re-ATTR（2026-08-26 · **4/4 全签 ✅** · **FAIL**）

| 项 | 内容 |
|----|------|
| 文书 | [`V4_TZ_L3_ACTIVE_BRAKE_DECLARE_20260826.md`](V4_TZ_L3_ACTIVE_BRAKE_DECLARE_20260826.md) |
| 产物 | `artifacts/v4_p7_attr_tz_l3brake_n32_20260826.json` / `logs/v4_p7_attr_tz_l3brake_n32_20260826.log` |
| 语料 | n=32 auth；`--diag-seed 4300` / accept 预留 5300；S-8j + three_zone + L3 active −x |
| **hard_coll** | **0.0625**（2/32）✅ ≤0.40（基线 0.5625） |
| **L3 超速** | GT `clearance_fov≤1.5` 步上 `‖Δp‖/0.2>0.25` = **0.812**（345/425）❌ ≤0.40（基线 ≈0.828） |
| arrival | 0.0625（只报；禁降 0.50） |
| brake | `three_zone_brake` 步 **344** / 26 ep；GT≤1.5 时仍常无罩通道（193/425） |
| **总判** | **FAIL**（两门须同时；速度门未过） |
| 红线 | **禁** silent 加大 `brake_gain`/`retreat_step_m`；不训 depth；不开 P8；不解 5ai′；归档本控制律须新 declare |

### P0b cones→shield re-ATTR（2026-08-26 · **4/4 全签 ✅** · **接线健康 FAIL**）

| 项 | L3 brake (4300) | **P0b (4500)** | 判读 |
|----|-----------------|----------------|------|
| 文书 | L3 brake declare | [`V4_P0B_CONES_SHIELD_DECLARE_20260826.md`](V4_P0B_CONES_SHIELD_DECLARE_20260826.md) | — |
| 产物 | `…l3brake…` | `artifacts/v4_p7_attr_tz_p0b_n32_20260826.json` | — |
| hard_coll | **0.0625** (2/32) | **0.1562** (5/32) | ❌ **恶化**（健康门「不恶化」未过） |
| L3 超速（GT≤1.5，‖Δp‖/0.2>0.25） | **0.812** (345/425) | **0.997** (710/712) | ❌ 大幅回退 |
| arrival | 0.0625 | 0.0938 | 只报 |
| `three_zone_lat` | 0 | **1 ep / 2 steps** | 介入率极低（>0 但几乎无效） |
| `three_zone_brake` | 26 ep / 344 steps | 13 ep / 53 steps | forward 几何下刹车触发↓ |
| fork | unclear | unclear（percept=1 / unclear_hc=4 / n_hard=5） | `stop_no_train` |
| **总判** | — | **接线健康 FAIL** | 禁 silent 加严；须新 declare |

读法：把 L3 刹车输入从 full-min 改成 `cones["forward"]` 后，**GT full-min≤1.5 时罩更少介入**（刹车步大降），硬撞与近场超速都变差；侧钳几乎未触。不否证「需要侧向约束」，但**本配方未证明有效**。

### P0b 接线修复 re-ATTR（2026-08-26 · seed **4600** · **仍 FAIL**）

| 项 | L3 brake (4300) | P0b broken (4500) | **P0b-fix (4600)** | 判读 |
|----|-----------------|-------------------|---------------------|------|
| 修复 | — | forward-only 语义陷阱 | `min(forward,full-min)` + 单步 depth | — |
| hard_coll | **0.0625** | 0.1562 | **0.1562** | ❌ 未改善 |
| L3 超速（GT≤1.5，‖Δp‖/0.2>0.25） | **0.812** | 0.997 | **0.906** | ⚠️ 优于 4500，仍劣 L3 |
| `three_zone_brake` | 344 steps | 53 | **299** | ✅ 召回恢复 |
| `three_zone_lat` | 0 | 1 ep / 2 steps | **0** | 侧钳仍无效 |
| arrival | 0.0625 | 0.0938 | **0.0312** | 只报 |
| fork | unclear | unclear | unclear → `stop_no_train` | — |
| **总判** | — | FAIL | **仍 FAIL** | bug 修掉≠配方过门 |

产物：`artifacts/v4_p7_attr_tz_p0bfix_n32_20260826.json` / `logs/v4_p7_attr_tz_p0bfix_n32_20260826.log`

> **勘误 / 下一刀（2026-08-27 · 待签 [`V4_P0B_HEALTH_GATE_POWER_DECLARE_20260827.md`](V4_P0B_HEALTH_GATE_POWER_DECLARE_20260827.md)）**：上表「仍 FAIL」的 **hard_coll 判读无效**（跨 seed 非配对，Fisher p=0.426，功效 9.6%）⇒ 记 **UNKNOWN**。L3 超速 **(i)/(ii) 已拆**（只读上列 JSON，无新跑数）：最好臂 345/425 中 **(i) 107 / (ii) 238** ⇒ 主因刹不住，**D1 救不了超速门**。H1 签后才许 125 补跑 L3-brake@4600 与 P0b-fix@4300（冻结 seed **{4300,4600}**，硬门支配违例=0）。**不进 P8。**

### H100 v4 FT 结案（2026-08-24 · `declare_id=v4-20260824`）

| 项 | 结果 |
|----|------|
| 训 | 早停 ~step 150：`fwd_overread_hinge≈0` 假饱和（step1 起即为 0） |
| ①d holdout AbsRel | **0.778 > 0.30 ❌ 硬锚 FAIL**（init 0.064） |
| hold035 emit | `artifacts/v4_zero_p3_v4_hold035_20260824.json` |
| **⓪h** | ✅ p=0 |
| **⓪c @(1.5,3]** | ✅ p90 **0.359**（老头同切 0.699） |
| ⓪a / ⓪b / ⓪e | ✅ |
| **merge ⓪** | ✅（primary） |
| **部署** | **禁止** — ①d 硬锚 FAIL；ckpt 归档不部署 |

- **根因候选**：`--early-stop-on-fwd-saturate` 在 hinge 本已为 0 时误停；`absrel_weight=0` 下 pinball 拖垮全图 ①d。
- **处置（v4-4）**：归档；**无 v5 声明不得再训**；阈值不降。

**125 推荐命令（H100 或 125 CUDA，不重训）**：

```bash
cd ~/aerial-wam-v2 && source experiments/aerial/scripts/env_4090.sh
DATA=experiments/aerial/rl/artifacts/dataset_v0_p45_merged_20260821
OLD=experiments/aerial/rl/artifacts/depth_ckpt_da3_r60_20260814/depth_step_2000_da3_ft_head.pt
TAU=experiments/aerial/rl/artifacts/tau_ckpt_foe_r60_20260815/tau_foe_calibrator.pt
$AERIAL_PY -m experiments.aerial.rl.v4_zero_eval \
  --dataset "$DATA" --depth-ckpt "$OLD" --tau-ckpt "$TAU" --device cuda \
  --heldout-frac 0.35 --split-seed 0 \
  --emit artifacts/v4_zero_p3_oldhead_p45_hold035_6cq_trial_20260824.json \
  2>&1 | tee logs/v4_zero_p3_oldhead_hold035_6cq_trial_20260824.log
```

- **禁止**：⓪h 权威 FAIL 前开 depth FT；仅为过 ⓪d_legacy depth FT；TZ-3Z 语料训 WM；剥 D̂ OR 腿（`5ao` 挂起）
- **Mac**：只改文档 / handoff；长跑在 **cursor-125** / **H100**

### P3 hold035 · 6cq 域试验（2026-08-24 · 老头 × p45_merged · **代码已落地**）

| 子项 | 结果 | 数值 |
|------|------|------|
| **⓪h** | **✅ PASS** | `p=0.0`, `consec=0`, `n_cond=162` |
| ⓪a | ✅ | median **0.220** on `(0,3]` |
| ⓪b | ✅ | 113 near frames |
| **⓪c** | **❌ FAIL** | p90 **0.699** on **`(1.5,3]`**（旧全域 0.743） |
| **0c_wall** | ❌（只报） | p90 **2.230** on `(0,1.5]` — **不 gate** |
| ⓪d_legacy | ❌（只报） | miss **0.114**, consec **2** |
| ⓪e | ✅ | — |
| **merge** | **❌** | ⓪c@(1.5,3] 仍 FAIL |
| **authoritative** | ✅ | `domain_lo=1.5` + `oc_refreeze` 落盘 |

- **产物**：`artifacts/v4_zero_p3_oldhead_p45_hold035_6cq_trial_20260824.json`（125 已跑）
- **代码**：`near_focus_lo_m` / pinball 域 / `check_0c` / `0c_wall` — Mac + 125 单测绿
- **下一发**：S-6 已落地复算；进入 S-5（签 ⓪i 功能门）

### H100 S-8c 结案（2026-08-25 · `declare_id=s8c-20260824`）

| 项 | 结果 |
|----|------|
| 配方 | S-8b + signed pinball **1.5** |
| ①d holdout best | **0.1277 ✅** @ step 600 |
| ⓪c `(5,12.2]` | hold035 p90=**0.211** ✅ / full **0.208** ✅ |
| ⓪i engage p95 | hold035 **0.55 m** ❌ / full **0.75 m** ❌（预算 0.2 m） |
| ⓪i cap_l1 p95 | hold035 **0.78 m** ❌ / full **0.81 m** ❌ |
| ⓪h consec | hold035=**5** ❌ / full **5** ❌（`<4`） |
| ckpt | `depth_ckpt_p45mid_s8c_20260824/` — **归档不部署** |
| **部署** | 仍冻结老头；下一发 **S-8d 待签** — [`V4_DEPTH_FT_S8D_MIDRANGE_DECLARE_20260825.md`](V4_DEPTH_FT_S8D_MIDRANGE_DECLARE_20260825.md) |

- **产物**：`artifacts/v4_{zero_p3,three_zone}_s8c_{hold035,full}_20260824.json`
- **读法**：under-read 相对 S-8b 再 ↓~半（full engage 1.58→0.75）；⓪h 贴线仍 FAIL；①d/⓪c 未破。

### H100 S-8b 结案（2026-08-24 · `declare_id=s8b-20260824`）

| 项 | 结果 |
|----|------|
| 配方 | S-8 + signed pinball **1.0** |
| ①d holdout best | **0.1305 ✅** @ step 500 |
| ⓪i engage p95 full | **1.58 m** ❌（S-8 1.77 m，↓11%） |
| ⓪h consec full | **13** ❌（S-8 17，改善仍 FAIL） |
| ckpt | `depth_ckpt_p45mid_s8b_20260824/` — **归档** |
| **下一发** | ~~S-8c~~ → **已结 FAIL** — [`V4_DEPTH_FT_S8C_MIDRANGE_DECLARE_20260824.md`](V4_DEPTH_FT_S8C_MIDRANGE_DECLARE_20260824.md) §7.1 |

### H100 S-8 结案（2026-08-24 · `declare_id=s8-20260824`）

| 项 | 结果 |
|----|------|
| 配方 | 域 `(5,12.2]` + p45_mid 185 ep + trigger=12.2；absrel=0.45 / fwd_pinball=1.25 / signed_pinball=0.5 |
| ①d holdout | **0.1205 ✅** @ step 600 |
| ⓪c `(5,12.2]` | hold035 p90=**0.211** ✅ / full **0.198** ✅ |
| ⓪i budget | hold035 engage p95 **1.45 m** ❌ / full **1.77 m** ❌（预算 0.2 m） |
| ⓪h | hold035 consec=**16** ❌ / full **17** ❌ |
| ckpt | `depth_ckpt_p45mid_s8_20260824/` — **归档不部署** |
| **下一发** | **S-8b H100 训中** → 完后 125 评 ⓪/⓪i — [`V4_DEPTH_FT_S8B_MIDRANGE_DECLARE_20260824.md`](V4_DEPTH_FT_S8B_MIDRANGE_DECLARE_20260824.md) |

- **产物**：`artifacts/v4_{zero,three_zone}_s8_{hold035,full}_20260824.json`
- **读法**：域对齐首次有效（⓪c PASS）；under-read ↓ 但仍 ~9× 预算；⓪h 退化 ⇒ 一档加重 signed pinball，禁止 warm-start S-8 ckpt

### H100 v6 FT 结案（方案 A · `declare_id=v6-20260824`）

| 项 | 结果 |
|----|------|
| 配方 | absrel=**0.4**, pinball=**1.5**, hinge=**0** |
| step 50 ①d | **0.450 > 0.30** → EARLY STOP |
| vs v5 step50 | 0.720 → **0.450**（改善，仍 FAIL） |
| ckpt | `depth_ckpt_p45_v6_20260824/` — **归档不部署** |
| 下一发 | **S-8b H100 训中** → 125 评 ⓪/⓪i |

### H100 v6b FT 结案（`declare_id=v6b-20260824`）

| 项 | 结果 |
|----|------|
| 配方 | absrel=**0.5**, pinball=**1.0** |
| step 50 ①d | **0.230 ✅** |
| step 100 ①d | **0.343 ❌** → 硬停 |
| 训长 | **100 / 600** |
| ckpt | `depth_ckpt_p45_v6b_20260824/` — 归档 |

### H100 v5 FT 结案（2026-08-24 · `declare_id=v5-20260824`）

| 项 | 结果 |
|----|------|
| E′ hinge 假停 | ✅ 未触发（无 hinge 早停 flag） |
| E″ ①d 硬停 | ✅ **step 50** holdout **0.720 > 0.30** → 停 |
| 训长 | **50 / 600**（非 v4 假停 150） |
| ckpt | `depth_ckpt_p45_v5_20260824/` — **归档不部署** |
| 读法 | 硬停**按设计工作**；pinball@3.0 仍快速伤 ①d ⇒ 需 v6 调配方 |

### P3 hold035 权威 emit（2026-08-24 · 老头 · **旧域 (0,3] ⓪c** · 对照）

| 子项 | 结果 | 数值 |
|------|------|------|
| **⓪h** | **✅ PASS** | `p=0.0`, `consec=0`, `n_cond=162` |
| ⓪a | ✅ | median AbsRel **0.220** |
| ⓪b | ✅ | 113 near frames |
| **⓪c** | **❌ FAIL** | p90 **0.743** > 0.50（全 `(0,3]`） |
| ⓪d_legacy | ❌（只报） | miss **0.114**, consec **2** |
| ⓪e | ✅ | — |
| **merge** | **❌** | ⓪c 挡 primary |

- **产物**：`artifacts/v4_zero_p3_oldhead_p45_hold035_20260824.json`
- **读法**：6ap 功能门 **⓪h 过关**；旧域 ⓪c 被墙根拖垮 —— **6cq 试验已把 primary 切到 (1.5,3]**，p90 仍 **0.699 > 0.50** ⇒ 需 v4 FT

## TZ-3Z 并行支线（**结案** · 不阻塞 V4 merge）

> 部署路线 = **三线 + D**；离线诊断 `authoritative=false`。详见下方 #27/#28/TZ-3Z 节。

## #26 τ-miss（老头 · 4090 · `authoritative=false` · **挂起**）

> **2026-08-23**：部署路线裁定为 **三线 + D** ⇒ #24 (b) 全面 τ 化 **不推进**；本节 hold035 产物保留作对照，**full77 / T-2 非当前阻塞**。

| 切片 | 状态 | T-1 `p_tau_miss` | T-1 consec | `n_tau_miss_cond` | ⓪d（对照） |
|------|------|------------------|------------|-------------------|------------|
| hold035 | ✅ DONE | **0.6441** | **5** | 59 | miss 0.114, consec 2 |
| full77 | 🟡 同批 job 续跑 | — | — | — | — |

- **产物**：`artifacts/v4_tau_miss_oc_hold035_20260822.json`（full77 → `…_full77_…`）
- **log**：`logs/v4_tau_miss_oc_20260822.log`；**PID** `3998697`（launcher）
- **sync**：2026-08-22 Mac → 125：`v4_zero_eval.py` / `tau_predictor.py` / `depth_geometry.py` + tests
- **B-a**：hold035 `dt_fallback=0`
- **红线**：D̂ OR 腿未动；不发证
- **罩子 v5（2026-08-22）**：`safety.py` 运动学站位 — `min_depth_m` = **3 m 内须稳停** 外边界；`D̂ < 3 + v·min_tau_s` 提前减速（阈值未改）；待 sync 125 后重采/重评

**初读（hold035）**：τ-miss **远高于** ⓪d miss（0.64 vs 0.11），consec 更差（5 vs 2）⇒ 未签 `5ao` 前**不能**据 T-1 单独推 (b)；待 full77 + T-2 φ。

## #27 三线限速 × 深度精度预算（老头 · 4090 · **结案** · `authoritative=false`）

| 方案 | 切片 | 动力学 | 深度 vs 预算 | 总判 |
|------|------|--------|--------------|------|
| **8/5/1.5 @ 2/1**（推荐） | hold035 | ✅ engage≥12.2m | ✅ | **✅** |
| 8/5/1.5 @ 2/1 | full77 | ✅ | ❌ engage p95欠读 3.01m > 预算 3.0m | ❌ 边际 |
| 7/5/1.5 @ 2/1（用户原案） | hold035 | ❌ 余量 0 | — | ❌ |
| **7/5/1.5 @ 2/0.75** | hold035 | ✅ engage≥11.2m | ✅ | **✅** |

- **完整结论**：[`V4_THREE_ZONE_DECLARE_20260823.md`](V4_THREE_ZONE_DECLARE_20260823.md)
- **产物**：`artifacts/v4_three_zone_oldhead_{hold035_8m,full77_8m,hold035_7m,hold035_7m_v075}_20260822.json`
- **harness**：`v4_three_zone_eval.py` + `test_three_zone_eval.py`
- **裁定**：推荐 **8/5/1.5@2/1**；**已接线 deploy**（`safety.kind: three_zone`）；⓪d@3m 退役

## #25 B-2 滞回（老头 · 4090 · 已否定）

| 切片 | consec(δ=0..2) | rate δ0→δ2 | 3–5 m 误触 |
|------|----------------|------------|-----------|
| hold035 | **全 2** | 0.114→0.057 | 0.67→0.95 |
| 全77 | **全 2** | 0.076→0.028 | 0.55→0.87 |

**裁定**：engage/release **压不了 consec**；不升格 B。声明：[`V4_HYSTERESIS_SCAN_DECLARE_20260821.md`](V4_HYSTERESIS_SCAN_DECLARE_20260821.md)

## #28 5 Hz 速度曲线（4090 loopback · **DONE** · `authoritative=false`）

- **harness**：`experiments/aerial/rl/step_hz_velocity_profile.py`
- **产物（open-loop）**：`artifacts/step_hz_profile_5hz_{rgb,depth}_20260823.json`
- **产物（shield-on）**：`artifacts/step_hz_profile_5hz_shield_on_20260823.json`（GT `D̂` proxy + `ThreeZoneSpeedShield`）
- **open-loop**：`achieved_hz≈4.99`；巡航 **~4.85 m/s**；制动 decel p90 **≈3.23 m/s²**（> 三线假设 2.5）；depth 与 RGB **无显著差**
- **shield-on（2026-08-23）**：`achieved_hz≈4.99`；巡航 **~1.0 m/s**（GT 前向 depth 落在 **5 m 带**，`cmd_fwd≈0.2`/step）；制动 p90 **≈3.22 m/s²**；**无额外 observe 税**（复用 `reset`/`step` obs）

## TZ-3Z 支线：老头 · 125 采 + H100 评（`authoritative=false`）

- **声明**：[`V4_THREE_ZONE_BRANCH_125_H100_20260823.md`](V4_THREE_ZONE_BRANCH_125_H100_20260823.md)
- **launcher**：`experiments/aerial/scripts/v4_three_zone_branch.sh`
- **分工**：125 = shield-on collect；H100 = `v4_three_zone_eval`（125 ssh 触发）
- **老头**：`depth_ckpt_da3_r60_20260814`；**不重训**

### 语料与 eval（2026-08-23 **DONE**）

| 语料 | ep | path/ep | 评价 |
|------|-----|---------|------|
| `…_20260823`（无 annotation） | 22 | ~0.3 m | **废弃** |
| `…_20260823b` / `c` | 21+21 | ~11 m | 开阔远距；annotation OK |
| `…_20260823_merged` | 42 | mean **11.0 m** | 开阔主集；gt_fwd min **9.3 m**；L 带 **0 帧** |
| `…_near_20260823f` / `g` | 9 + 3 | ~10 m | blocked 近障；`topup_near` 补采 |
| **`…_near_20260823fg`** | **12** | — | **P1 目标达成**（f+g merge） |
| **`…_oldhead_20260823_full`** | **54** | — | **42 open + 12 near**；TZ-3Z eval 主语料 |

| eval（H100 · merged 42） | engage_outer | L1/L2/L3 | 总判 |
|--------------------------|--------------|----------|------|
| hold035 | n=30，p95 **0.95 m** | no support | ✅ engage only |
| full77 | n=59，p95 **0.99 m** | no support | ✅ engage only |

| eval（H100 · **full 54** · `20260823_full`） | engage_outer | cap_l1 | cap_l2 | cap_l3 | **⓪h** | 总判 |
|-----------------------------------------------|--------------|--------|--------|--------|--------|------|
| hold035 | n=32，p95 **0.95 m** | n=21 | n=40，p95 **0.63 m** | n=32，p95 **1.37 m** | n=473，p=**0.017**，consec=**3** | **✅** |
| full77 | n=97，p95 **0.99 m** | n=46 | n=93，p95 **1.33 m** | n=32，p95 **1.37 m** | n=1552，p=**0.010**，consec=**3** | **✅** |

- **产物**：`artifacts/v4_three_zone_branch_{hold035,full77}_20260823_{merged,full}.json`
- **log**：`logs/v4_three_zone_supp_20260823.log`（b/c）；`logs/v4_three_zone_topup_20260823g.log`（P1 f→g→fg→full）
- **P1 排障**：`v4_p45_collect` 扫层误用 `aerial_rl.yaml` 默认 `backend:mock` → 已修强制 `airsim`；launcher 增 `MODE=topup_near`

### 部署路线：三线 + D（2026-08-23）

| 层 | 量 | 角色 |
|----|-----|------|
| 主控 | `D̂` → `planned_speed(d)` | 8/5/1.5 m 分级限速 |
| 应急 | `τ`、`p_coll` | latch + 后退（不改） |
| 离线 primary | **⓪h** engage-miss | **已冻结**（DECLARE §4c；`20260823_full` H100 **PASS**） |
| **不做** | #24 (b) 摘 D OR 腿 | `5ao` 挂起 |

### P1 近障补采（**DONE** · `MODE=topup_near`）

```bash
# 首轮（9 ep）+ 补采（3 ep）示例
STAMP=20260823_full NEAR_STAMP=20260823g PRIOR_NEAR_STAMP=20260823f \
  NEAR_COMBINED_STAMP=20260823fg PER_LAYER=4 BLOCKED_SEED=101 MODE=topup_near \
  bash experiments/aerial/scripts/v4_three_zone_branch.sh
```

- `collect_near`：`v4_p45_collect` + `three_zone` yaml；`goal-dist-m 30` / `probe-near-m 1.5` / `p45_balanced` pool
- `merge_near`：f(9) + g(3) → **fg(12)**；`merge_full`：merged(42) + fg(12) → **full(54)**

## Checklist

- [x] 深度头冻结老头
- [x] K-min B-1 否定
- [x] B-2 Phase C 否定（不升格）
- [x] `#27` 三线结案（declare 20260823）
- [x] harness sync + `#26` 开跑（hold035 DONE）
- [x] `#28` 5 Hz 速度曲线（rgb + depth）→ `a_max` 实测 ~3.23，设计保留 2.5
- [x] TZ-3Z：merged 42 ep + H100 eval **DONE**（engage ✅）
- [x] TZ-3Z P1：近障 **12 ep** → `20260823_full` **54 ep** + hold035/full77 **双 PASS**
- [x] ⓪h engage-miss re-freeze + harness（`v4_three_zone_eval` §0h）
- [x] ⓪h 入账 H100 eval（`20260823_full` hold035+full77 **双 PASS**）
- [x] shield-on 5 Hz 速度曲线（#28 后续 · P3）
- [x] Mac 合入 + sync 125（`44d7c78`）
- [ ] **V4 主线**：控制臂 hold035 重评（`v4_zero_eval` on `p45_merged`）
- [ ] **V4 主线**：⓪ 权威 FAIL 归因 → 是否开 depth loss 声明（**须 FAIL 后**）
- [ ] **V4 主线**：P1 `p_coll` 复测 / P4 ⓿e harness

## Running jobs

- **none**（L3 brake re-ATTR 已结案 FAIL；进程已退出）
