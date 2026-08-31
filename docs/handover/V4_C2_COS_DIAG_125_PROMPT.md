# C2 ①-eval first-act cos + goal_rel0 — run on 125

Living status (update as you go): `docs/handover/V4_C2_COS_DIAG_125_STATUS.md`.  
Context: `docs/handover/V4_GATE_STATUS.md` §1, `V4_SIGNAL1_SA_DIAG_STATUS.md` C2 节, `V4_PROGRESS_DIAG_125_STATUS.md` (M5d unbounded 对照).  
Access: `docs/handover/ACCESS.md` — on-campus **`cursor-125`**. You are ON **125** (`/home/yao/aerial-wam-v2`). Renderer: `127.0.0.1:41451`. Python: `source experiments/aerial/scripts/env_4090.sh` → `$PYTHON_BIN`.

## Hard rules
- **Do NOT** flip `enable_policy_update` (must stay `false`). Do **not** change `δ_p` / yaml.
- **Do NOT** push GitHub; only `git push origin main` (bare on 125).
- Never modify Franka / robot network; never use `10.229.66.70`.
- **Do NOT** implement §4 In-table (goal concat into actor/critic). This job is **read-only diag + docs sign/no-sign**.
- **Do NOT** open an RH case. **Do NOT** retrain. Honest FAIL is OK.

## Why this job exists

C2 从零重训后再 gate：① **仍 FAIL**（seed=0 **−7.43** / seed=1 **−3.53** vs heur ~9，两跑 **n=5 < 8** 非全权），④ PASS。判定 **`clip_insufficient`**。

但训后 §A 的想象 a0 x = **+0.567（前向）**，而 **①-eval 逐 ep 首动作 cos 从未报**。π 仍 goal-blind ⇒ probe goal `[+30,0,0.85]` 上的正 cos **不能**外推到评测 goal 分布。A.3 事前处置写过「再 gate 强制报 ‖a‖ 分布 + 想象-真实回报相关性」，一直没报。

对照（无界 M5d，**不是**本跑）：`v4_progress_diag.py` 首动作 cos(goal_body) **≈−0.88** vs heur **≈+0.99**。本跑要对 **C2 ckpt** 取同一个量。

## Pre-committed decision (do not renegotiate)

主数 = ①-eval **scored eps** 上 actor `mean cos(first_act[:3], goal_body0)`。

| 结果 | 归因 | 处置 |
|---|---|---|
| **mean cos < 0** | goal-blind 固定偏置（a0 不随评测 goal 转） | **签** §4 In 表（goal 进 actor/critic）是对的修。提案 §5 签字。**不写实现**。 |
| **mean cos ≥ 0** | 活假设换成想象-真实回报倒挂（WM 保真 / z0 域差） | **不签** In 表。签了会白训一轮。记入 STATUS / GATE §1。 |

混合号（有的 ep <0 有的 ≥0）：仍以 **mean** 套上表；同时把逐 ep 表和 `first_act_xyz_std` 写进 STATUS，并加一句「混合 ⇒ 固定偏置指纹弱」。**不要**自己发明第三行。

也报（不改判据）：`cos_path_goal`、`cos_mean10_act_xy_goal_body_xy`、逐 ep `goal_rel0`。harness 可能把 t=0 body goal 收成 ~`[+30,0,0]`（构造，不是抽样）——若如此，把「方向分布退化」写成事实，**仍然**用上表的 first-act mean cos 签字。

n=5 非全权 merge，但 **够读 cos 的符号**。

> **⚠️ 事后注记（2026-08-18 读码，洞 4；只收紧不放松，上表数字/判据一字不改）**
>
> 评测 goal **不是分布，是构造性常量**：`make_obstacle_facing_episodes` 用 `goal_dist_m=30.0`、`goal = start + heading*30` 且 spawn `yaw = heading`（`v0_rollout_eval.py:251` / `:386-389`）⇒ **每个 ep 的 `goal_body0` ≡ `[+30, 0, 0]`**。由此：
>
> 1. **`cos < 0` 在本 harness 上退化为 `sign(a0_x) < 0`**（= 首动作**后退**）。它**不能**证明上表第一行的归因「a0 不随评测 goal 转」—— goal 根本没转过，这个命题在本 harness 上**不可检验**。
> 2. **`first_act_xyz_std ≈ 0` 不是 goal-blind 指纹**：常量 goal 下，一个 goal-aware 策略喂同一个 goal 也会输出近常量 a0（差异只来自图像 z0）。该指纹在本跑**作废**，仍照记但**不得**作为签字理由。
> 3. **§4 In 表在 t=0 加不进任何信息**：`goal_rel0` 对所有 ep 是同一个常量，喂给 actor 的信息量为 0。In 表的价值只可能在 **t>0 的跟踪**上 ⇒ 需要**轨迹级**证据，首动作只是其中一格。
>
> **因此处置收紧**（判据不改，门槛只升不降）：
>
> - `mean cos ≥ 0` → **仍是「不签」**，不变。
> - `mean cos < 0` → 改为 **「待签」**（不是直接签）。签字还需同一 JSON 里**已有**的轨迹级数（零额外成本，`v4_progress_diag.py` 本来就 emit）：
>   - `cos_path_goal`、`cos_mean10_act_xy_goal_body_xy`（actor + heur 都记）
>   - 判别：**t=0 正、沿 t 翻负** ⇒ goal-blind 跟踪丢失 ⇒ §4 有基础，可签；**全程正而 progress 仍负** ⇒ 想象-真实回报倒挂（WM 保真 / z0 域差）⇒ §4 **不修这个**，不签。
>
> 依据：`docs/handover/V4_GATE_STATUS.md` §1 洞 4、`V4_SIGNAL1_STRUCTURAL_REFREEZE_PROPOSAL.md` §3 收紧块。

## Artifacts to start from (C2 re-gate)

```
experiments/aerial/rl/artifacts/v4_gate_r60_20260818_c2/          # seed=0, ask 10
experiments/aerial/rl/artifacts/v4_gate_r60_20260818_c2_n8/       # seed=1, ask 8
experiments/aerial/rl/artifacts/v4_ac_ckpt_20260818_c2_fromscratch/v4_ac_latest.pt
experiments/aerial/rl/artifacts/wm_ckpt_r60_rh_20260816/wm_step_1000.pt
dataset: ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/dataset_v0_headon_20260811
yaml: configs/aerial_rl_rollout.yaml   # do not edit
```

Partial JSON 里通常只有 `actor_progress_sums` / `heuristic_progress_sums`，**没有** first_act / `goal_rel0`。先打开确认；缺则必须重跑 diag（同源 harness，同一 ckpt / dataset / seed）。**不要**翻 yaml、不要重训。

## Work

0. From the two C2 gate dirs, dump `signals.1.scan` and confirm partial-1 has **no** first_act / cos / `goal_rel0`. Record which bucket ate n (scan-time reject vs eval drop are different). This is the only part that is truly "already on disk".
   - **键名更正（08-18 读码）**：落盘键是 **`scan.rejections`**（不是 `scan.rej`）—— `v0_rollout_eval.py` 的 `diag = {"requested", "accepted", "scanned", "candidates", "rejections", "accepted_fwd_depth_m", "probe"}`。桶名：`no_depth / spawn_collision / too_close / open_ahead / proxy_ok / probe_no_hit / obstacle_ok / reset_error`。
   - **口径分清**：`rejections["spawn_collision"]`（`:398`）是**扫描期候选被拒**，`accepted` 会补扫直到够数；真正的「评测中丢局」是 `_run_one_resilient` 返回 `None`。两者修法不同，**必须**在 STATUS 里分开写。若 `accepted == 10 / 8` 而 scored 只有 5 ⇒ 丢在评测期，不在扫描期。
1. `git pull origin main` so you have the updated `v4_progress_diag.py` (`--imagine-horizon`, ‖a‖, `goal_rel0`, imagined-vs-real).
2. Renderer up: `127.0.0.1:41451`. If down, `experiments/aerial/scripts/recover_renderer.sh` (or the living-doc recover path) then continue. Do not wait forever — record and stop if AirSim is dead.
3. Run **both** seeds (match the two C2 gates):

```bash
cd ~/aerial-wam-v2
source experiments/aerial/scripts/env_4090.sh
mkdir -p artifacts logs

# seed=0  (gate ask 10 → scored 5)
$PYTHON_BIN experiments/aerial/scripts/v4_progress_diag.py \
  --repo ~/aerial-wam-v2 \
  --rollout-dataset ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/dataset_v0_headon_20260811 \
  --actor-ckpt experiments/aerial/rl/artifacts/v4_ac_ckpt_20260818_c2_fromscratch/v4_ac_latest.pt \
  --wm-ckpt experiments/aerial/rl/artifacts/wm_ckpt_r60_rh_20260816/wm_step_1000.pt \
  --env-host 127.0.0.1 \
  --seed 0 --n-episodes 10 --imagine-horizon 15 \
  --out artifacts/v4_progress_diag_c2_seed0_20260818.json \
  2>&1 | tee logs/v4_progress_diag_c2_seed0_20260818.log

# seed=1  (gate ask 8 → scored 5)
$PYTHON_BIN experiments/aerial/scripts/v4_progress_diag.py \
  --repo ~/aerial-wam-v2 \
  --rollout-dataset ~/aerial-rl-skeleton/experiments/aerial/rl/artifacts/dataset_v0_headon_20260811 \
  --actor-ckpt experiments/aerial/rl/artifacts/v4_ac_ckpt_20260818_c2_fromscratch/v4_ac_latest.pt \
  --wm-ckpt experiments/aerial/rl/artifacts/wm_ckpt_r60_rh_20260816/wm_step_1000.pt \
  --env-host 127.0.0.1 \
  --seed 1 --n-episodes 8 --imagine-horizon 15 \
  --out artifacts/v4_progress_diag_c2_seed1_20260818.json \
  2>&1 | tee logs/v4_progress_diag_c2_seed1_20260818.log
```

4. From each JSON `summary` **and** per-ep table, record:
   - 逐 ep: `cos_first_act_goal_body` (actor + heur), `first_action`, `goal_rel0`, `goal_azimuth_deg`, `first_act_norm3`, `mean_act_norm3`, `progress`, `imagined_sum_progress`, `imagined_return`
   - 逐 ep **轨迹级**（洞 4 追加，脚本已 emit，零额外成本）：`cos_path_goal`、`cos_mean10_act_xy_goal_body_xy`、`mean10_action`、`collided`（actor + heur 都记）
   - `goal_rel0` 预期对所有 ep **恒为 `[30, 0, 0]`**；若不是，说明 harness 与 gate partial-1 不同源，**停下先查**
   - `mean_cos_first_act_actor`, `n_cos_first_act_lt0_actor`, `first_act_xyz_std_actor`（近 0 ⇒ a0 恒定 = goal-blind 指纹）
   - `pearson_imagined_vs_real`（A.3 欠账）
   - `in_table_verdict_precommitted` — **照表执行，不要改判据**

两跑 mean cos **同号**才签/不签；若两跑符号相反，**不签**，STATUS 写「符号冲突，停」。

> 按上文事后注记：两跑同为 `cos < 0` ⇒ 结论写 **「待签，需轨迹级复核」**并把 `cos_path_goal` / `cos_mean10_...` 一并落表；**不要**在本 job 里直接签 §5。两跑同为 `cos ≥ 0` ⇒ 照原表 **不签**（此路径不变）。

5. Docs (changelog 风格 `YYYY-MM-DD —— 改了什么(为什么/依据)`；**不改写**旧表数字):
   - 填 `V4_C2_COS_DIAG_125_STATUS.md`
   - `V4_SIGNAL1_SA_DIAG_STATUS.md` 文末 **新小节**（C2 ①-eval cos）
   - `V4_GATE_STATUS.md` §1 + §3 一行
   - `LIVING_DOCS.md` / `PROJECT_STATUS.md` 下一件
   - 若 **签**：提案 `V4_SIGNAL1_STRUCTURAL_REFREEZE_PROPOSAL.md` §5 签字行（日期 + HEAD + mean cos）。若 **不签**：§5 写「08-18 C2 cos≥0，In 表修订搁置」。
6. Commit + `git push origin main`. Do **not** implement In-table code.

If renderer/scan fails: document and stop honestly.
