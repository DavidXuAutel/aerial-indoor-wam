# C2 ①-eval first-act cos + goal_rel0 (125)

- **status**: **DONE** (2026-08-18)
- **prompt**: `docs/handover/V4_C2_COS_DIAG_125_PROMPT.md`
- **ckpt**: `v4_ac_ckpt_20260818_c2_fromscratch/v4_ac_latest.pt` + RH WM `wm_step_1000.pt`
- **script**: `experiments/aerial/scripts/v4_progress_diag.py` (`--imagine-horizon 15`)
- **renderer**: `127.0.0.1:41451` TCP OK
- **HEAD**: `b35d245f2d6fa32a4d4f35927c68fcfd94162ebf`

Pre-committed: mean cos(first_act, goal_body) **< 0** → 签 §4 In 表；**≥ 0** → 不签（想象-真实倒挂）。实现代码本 job **不写**。

> **洞 4（harness 事实，与实测并存）**：评测 `goal_body0` 由构造 **≈ `[+30,0,z]`** 恒定 ⇒ 首动作 cos 退化为 `sign(a0_x)`；`signals.1.scan` 键是 **`rejections`**（不是 `rej`）；`rejections["spawn_collision"]` = 扫描期被拒 ≠ 评测期 `_run_one_resilient→None` 丢局。`cos ≥ 0` 路径**不依赖**这条收紧：事前表已规定不签。

## Verdict

**`do_not_sign_imagine_real_inversion`** — 两跑 mean cos **同号且 ≥ 0**（+0.806 / +0.762），按事前表 **不签** §4 In 表。活假设 = 想象-真实回报倒挂（imagined ΣG ≈ **+85** vs real progress ≈ **−5**；Pearson +0.59 / +0.22 但 mean(real−imag) ≈ **−91**）。

**方向分布退化（事实）**：harness t=0 body `goal_rel0` 全 ep ≈ **`[+30, 0, z]`**，azimuth **|θ| ≤ 0.8°**（7/8 ep ≤ 0.2°）。评测 goal 方向几乎恒定前向（构造，非宽方位抽样）⇒ 正 cos **不能**读成「随 goal 转向」；仍按事前表用 mean cos 签字。

**固定偏置指纹弱**：`first_act_xyz_std_actor` x 维 **0.12 / 0.21**（非 ≈0），且 `n_cos_first_act_lt0=0`（无 ep 负 cos）。`cos_path_goal` 有负 ep（seed=0 3/7），但 first-act cos 全正。

> **复核（2026-08-18 同日；verdict 与下面所有数字一字不改）** —— 四处记述要改、一处别的结论被推翻：
> 1. **`clip_insufficient` 本轮应记 `unclassified`**：该行是合取「① FAIL **且** cos<0」，cos ≥0 ⇒ 不成立；「不签」依据是**本 job 的事前表**（PROMPT），不是那行。
> 2. **本跑最强的数是 `cos_path_goal` +0.075/+0.098（≈85°）**，不是 first-act cos；形态 = 跟踪丢失。仍不签，但理由须写成**洞 4**（训练侧单 `_mock_goal_episode()` + 评测侧 |az|≤0.8° ⇒ goal 是常量输入、可被 bias 吸收，In 表表达力增量 **0**），否则将来会有人拿 `cos_path` 负 ep 重开 In 表。
> 3. **Pearson 无功效**：+0.588（n=7，p≈**0.17**）/ +0.217（n=8，p≈**0.61**），两跑差 2.7× ⇒ 不得作为下一案依据。**`mean_real_minus_imagined ≈ −91` 混了 horizon**（想象 15 步 vs 真实整局 ≤200 步），不是校准误差；要量化须取**同窗口**（真实前 15 步）。
> 4. **n=5 归因翻转**：本 job step 0 实测 `accepted` = **9 / 8**（扫描期被拒会补扫到数），掉到 scored=5 发生在**评测期**；同 seed 同构造的本 diag 拿到 **n=7 / n=8**（seed=1 零丢局）⇒ 「n=5 = spawn 扫描 / 存活局偏开阔空间」**无依据、已撤回**，病灶在 gate 的**评测循环**（`_run_one_resilient→None`，或 ④ on/off 配对那条路径）。全权 ① 很可能**不必碰 spawn**，仍**不**降 `n`。
> 5. **倒挂已定位到 RH 幅度校准，且不需要真机**：`v4_imagine_return_decomp` C2 训后表里，(b) 最大前飞 yaw **恒 0** ⇒ 15 步 × 上限 1.0 m = **恰好 15.0 m** 闭合（`‖goal‖ 30→15.0` 印证），RH `Σprogress` = **+62.60** ⇒ **4.2×**；π 闭合 12.2 m 得 **+81.64** ⇒ **6.7×**；**几何排序**（15.0 > 12.2）与 **RH 排序**（81.64 > 62.60）**相反** ⇒ **RH 案重开**（推翻 `V4_SIGNAL1_SA_DIAG_STATUS` 那句「多出来的 λG0 来自侧向/垂向自由度、不要读成再开 RH 案」）。**RH 校准曲线已跑**（[`V4_RH_CALIB_125_STATUS.md`](V4_RH_CALIB_125_STATUS.md)）：非 1:1，π **6.66×** / 前飞 **4.18×** / 后退 **反号** ⇒ **`sign_reopen_rh_progress_head`**。
> 6. **code lead（未修，须签字）**：`advance_goal_rel_body`（`goal_features.py:60-73`）只做 `g[:3] -= a[:3]`、**不按 `a[3]` 旋转** body goal，而 `imagine()` 逐步用它传播 RH conditioning（`imagination.py:164-165`）⇒ yaw≠0 的臂失真（π 的 12.2 m 亦不可靠；(b) yaw≡0 不受影响 ⇒ 4.2× 干净）。
> 7. **未报字段**：PROMPT 里要求的 `cos_mean10_act_xy_goal_body_xy` / `mean10_action` 本 STATUS **没写**（JSON 里有，零成本可补）。另 `goal_rel0` up 分量 **0.07–1.04**（非 0，疑为起飞悬停高度与 spawn z 之差，**待一句确认**，非 harness 异源）。

## Step 0 — gate partials on disk

Partial-1 JSON **confirmed missing** `first_act`, `cos_*`, `goal_rel0` (only progress sums + embedded `scan`).

### signals.1.scan (seed=0, dir `v4_gate_r60_20260818_c2`)

- requested **10** → accepted **9** → **n_starts_scored 5** (eval drop 9→5)
- rejections: `open_ahead` **708**, `spawn_collision` 10, `probe_no_hit` 11, `obstacle_ok` 9, `proxy_ok` 20
- probe: hits 9/20, collided 9

### signals.1.scan (seed=1, dir `v4_gate_r60_20260818_c2_n8`)

- requested **8** → accepted **8** → **n_starts_scored 5** (eval drop 8→5)
- rejections: `open_ahead` 15, `spawn_collision` 8, `probe_no_hit` 4, `obstacle_ok` 8, `proxy_ok` 12
- probe: hits 8/12, collided 8

## Summary table

| run | n scored | mean cos actor | n cos<0 | mean ‖a0[:3]‖ | Pearson imagΣG vs real progress | verdict |
|---|---|---|---|---|---|---|
| seed=0 | 7 | **+0.806** | 0 | 0.848 | **+0.588** | do_not_sign |
| seed=1 | 8 | **+0.762** | 0 | 0.829 | **+0.217** | do_not_sign |

Also: mean `cos_path_goal` actor **+0.075 / +0.098**；heur first-act cos **+0.999 / +0.993**。`mean_imagined_sum_progress` **84.9 / 86.5** vs `mean_actor` **−5.94 / −4.48**。

Artifacts: `artifacts/v4_progress_diag_c2_seed0_20260818.json`, `artifacts/v4_progress_diag_c2_seed1_20260818.json`；logs `logs/v4_progress_diag_c2_seed{0,1}_20260818.log`。

## Per-ep (actor)

### seed=0 (n=7; idx 2,5,9 dropped spawn)

| ep | cos_act | cos_heur | cos_path | ‖a0‖ | az° | progress | imagΣG | goal_rel0 (xyz) |
|---|---|---|---|---|---|---|---|---|
| 0 | +0.774 | +0.998 | +0.198 | 0.803 | −0.00 | −3.42 | +84.0 | [30.00, −0.002, 1.04] |
| 1 | +0.845 | +1.000 | +0.287 | 0.897 | +0.01 | −4.15 | +87.8 | [29.99, +0.003, 0.81] |
| 3 | +0.820 | +0.999 | +0.568 | 0.959 | +0.00 | +2.47 | +89.4 | [30.01, +0.002, 0.68] |
| 4 | +0.731 | +1.000 | −0.188 | 0.613 | +0.03 | −10.60 | +81.5 | [30.02, +0.018, 0.18] |
| 6 | +0.850 | +1.000 | +0.081 | 0.956 | +0.01 | −6.36 | +93.8 | [30.00, +0.003, 1.03] |
| 7 | +0.844 | +1.000 | −0.238 | 0.898 | −0.03 | −10.08 | +81.5 | [30.00, −0.016, 0.07] |
| 8 | +0.778 | +0.997 | −0.180 | 0.810 | +0.16 | −9.44 | +76.3 | [30.01, +0.086, 0.11] |

### seed=1 (n=8)

| ep | cos_act | cos_heur | cos_path | ‖a0‖ | az° | progress | imagΣG | goal_rel0 (xyz) |
|---|---|---|---|---|---|---|---|---|
| 0 | +0.750 | +1.000 | +0.593 | 0.775 | −0.00 | +4.41 | +90.3 | [30.00, −0.002, 0.83] |
| 1 | +0.810 | +1.000 | −0.205 | 0.788 | −0.01 | −5.67 | +85.4 | [30.00, −0.004, 0.82] |
| 2 | +0.830 | +0.990 | +0.178 | 0.985 | +0.00 | −3.17 | +91.4 | [30.00, +0.003, 0.85] |
| 3 | +0.720 | +1.000 | +0.140 | 0.718 | +0.05 | −4.79 | +91.0 | [30.01, +0.024, 0.91] |
| 4 | +0.850 | +0.980 | +0.010 | 1.002 | −0.00 | −8.03 | +90.1 | [30.00, −0.001, 0.82] |
| 5 | +0.860 | +1.000 | +0.170 | 0.885 | +0.79 | −3.93 | +89.7 | [30.10, +0.412, −0.04] |
| 6 | +0.410 | +0.990 | −0.210 | 0.480 | +0.02 | −9.87 | +84.3 | [29.98, +0.012, 0.83] |
| 7 | +0.870 | +1.000 | +0.110 | 0.999 | +0.23 | −4.76 | +70.0 | [29.92, +0.122, 0.16] |

## Disposition

- **§4 In 表**：**不签**（签会白训一轮 In-table 实现）。
- ~~**下一件**：活假设 = WM 转移保真 / z0 域差 / 想象-真实倒挂；须另案（非 In 表 goal concat）。全权 ① 仍须解 spawn-in-collision~~；`enable_policy_update` 仍 false。
- ~~**下一件（2026-08-18 复核后收窄）**：**先做 RH 校准曲线**~~ ← **已跑完**（同日，125 离线，零渲染零训练零改码）：[`V4_RH_CALIB_125_STATUS.md`](V4_RH_CALIB_125_STATUS.md)，判定 **`sign_reopen_rh_progress_head`** —— 非 1:1，π **6.66×**（81.64 / 12.26）、前飞 **4.18×**（62.60 / 14.99，yaw≡0）、后退 **反号**（RH +9.28 对几何 −15.00）；形状 t0–t4 近校准、**t≈6 起 RH 爆到 6–9 m/步**而几何仍 ~1。⇒ 曲线未近 1:1 ⇒ **不**走 **WM 转移保真 / z0 域差** 那条贵路（真实 ① ≈ −5 的世界差是 RH 诚实之后才轮到的活）。
- **下一件**：**签「重开 RH progress 头」**（校准曲线即签字材料），签完才改码。全权 ① 改查 **gate 评测循环**（不是 spawn 扫描，见复核第 4 条），**不**降 `n`；`enable_policy_update` 仍 **false**。
