# Indoor WAM — E2i.A（WM encode 短窗 + π 再 C1）· 2026-08-31

> **Workspace（125）**：`/home/yao/aerial-indoor-wam`  
> **人令**：选 **A**（相对 B/C）  
> **权威链**：本文件 → [`INDOOR_0XM_STATUS.md`](INDOOR_0XM_STATUS.md) → [`INDOOR_FULL_STACK_20260831.md`](INDOOR_FULL_STACK_20260831.md) §13  
> **禁**：E3；shield-off 当完成；夹具刷分；`5ao` 未签不剥 D̂/OR

---

## 0. 一句话

C1 @0.50 不过门的主因之一是 **室外 WM encode 域差（F4）**：π FT 时 `enable_wm_update=False`，视觉表征未进室内。  
**E2i.A** = 用室内 B1 主料对 WM **短窗 warm-start FT** → 换新 WM 再跑 **π C1** → 同协议 @0.50 罩 ON 评测。

---

## 1. 动机（相对「再 500 iter π」）

| 证据 | 含义 |
|------|------|
| C1 只训 π，WM 冻结在 `wm_step_3500`（室外） | encode 仍按开阔域 |
| 视频：R04/R05 能到，R01 spawn 撞、R06 近场撞 | 有策略但不稳；域+spawn 噪声 |
| shield-off best 0.63 m collided | π 本体也缺近场，但 A 先修表示 |

---

## 2. 顺序（死）

```text
A0  Cloudflare Access 可用 → 125 SSH
A1  成功加权 / spawn 过滤 mix（encode 语料 + π 语料可同目录或分目录）
A2  WM encode 短窗 FT（warm-start wm_step_3500）→ 新 ckpt 目录
A3  π C1 短 FT（--skip-collect，新 WM，仍 enable_wm_update=False）
A4  @0.50 罩 ON · assist=none · 同 C1 合同评测
A5  过门？→ 再议 C2/@0.20；不过 → 停，不自动 H100
```

**禁止**：跳过 A2 直接再训 π；用 shield-off 冒充过门；B2 夹具占比 >30% 进 π mix。

---

## 3. 语料

### 3.1 Encode 语料（WM）

优先 **B1** `dataset_indoor_b99_none_near_20260831`（assist=none · d_end≤1.0 · 无碰撞偏好）：

- 目标：室内 RGB 短窗（`window≈8–16`）适配 encoder/RSSM
- 可选：少量 B2 仅作视觉多样性，**≤20%**
- 入口：`_wm_train_validate.py --init-ckpt … --save-ckpt --skip-gate`（室内短窗诊断；gate 失败仍可存 ckpt 供 A3，但日志如实记）

### 3.2 π mix（再 C1）

相对原 C1（B1 62 / B2 34 / old 24）：

| 桶 | 规则 |
|----|------|
| B1 | **≥60%**；优先 `d_end` 更小、无碰撞；spawn 早撞剔除 |
| B2 | **≤25%** |
| old e2h | **≤15%** 或 0（A 默认可砍到 0） |

脚本：`experiments/aerial/scripts/indoor_build_e2i_a_mix.py`  
输出：`dataset_indoor_e2i_a_20260831/`（symlink + `mix_meta.json`）

---

## 4. WM encode FT 命令（125）

```bash
cd /home/yao/aerial-indoor-wam
source experiments/aerial/scripts/env_4090.sh

$AERIAL_PY experiments/aerial/rl/_wm_train_validate.py \
  --config configs/aerial_rl_indoor_c1_050.yaml \
  --dataset experiments/aerial/rl/artifacts/dataset_indoor_b99_none_near_20260831 \
  --init-ckpt experiments/aerial/rl/artifacts/wm_ckpt_d_full_20260828/wm_step_3500.pt \
  --checkpoint-dir experiments/aerial/rl/artifacts/wm_ckpt_indoor_encode_e2i_a_20260831 \
  --steps 400 --window 12 --wm-batch 8 \
  --device cuda --save-ckpt --skip-gate \
  2>&1 | tee logs/e2i_a_wm_encode_400_20260831.log
```

产物：`wm_ckpt_indoor_encode_e2i_a_20260831/wm_step_400.pt` + `wm_train.jsonl` + `wm_train_meta.json`（含 `init_ckpt`）。

---

## 5. π 再 C1

```bash
$AERIAL_PY experiments/aerial/rl/train_v4_ac.py \
  --indoor --dynamics torch --device cuda \
  --wm-ckpt experiments/aerial/rl/artifacts/wm_ckpt_indoor_encode_e2i_a_20260831/wm_step_400.pt \
  --actor-ckpt experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2i_c1_20260831/v4_ac_latest.pt \
  --dataset experiments/aerial/rl/artifacts/dataset_indoor_e2i_a_20260831 \
  --skip-collect --no-approach-bias \
  --train-pose-source gt_proxy \
  --success-dist-m 0.50 \
  --iters 500 \
  --ckpt-dir experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2i_a_20260831 \
  2>&1 | tee logs/e2i_a_pi_c1_500_20260831.log
```

评测：与 C1 同协议（Building_99 · 罩 v3 ON · `assist=none` · `@0.50` · 8×3）。

过门（同 C1）：**≥2/3 seed 有到点** **或** mean d_end **≤1.0 m**。

---

## 6. 记账

| 项 | 路径 |
|----|------|
| 计划 | 本文件 |
| STATUS | `INDOOR_0XM_STATUS.md` E2i.A 行 |
| WM log | `logs/e2i_a_wm_encode_400_20260831.log` |
| π log | `logs/e2i_a_pi_c1_500_20260831.log` |
| eval | `artifacts/indoor_e2i_a_eval_050_summary_*.json` |
| launch | `experiments/aerial/scripts/run_e2i_a_pipeline.sh` |

---

## 7. 不做

- 不把 LEARNING gate 当室内产品验收（`--skip-gate` 仅允许存 ckpt）
- 不自动开 H100 / C2
- 不改 `safety.py` deploy 语义（罩仍用 v3 yaml）
