# 125 Agent：跑 B′ 诊断（git 同步后）

> **执行归属**：后续 WAM 主线任务 **一律在本机（125）Agent 完成**；Mac 只 push 代码。  
> Mac 已 push **github/main**（`f69860b` 或更新）。125：`git fetch github && git merge github/main`。

## 拉代码

```bash
cd ~/aerial-wam-v2
git fetch github && git merge github/main
# 或：git fetch origin && git merge origin/main（若 bare 已同步）
git log -1 --oneline   # 应含 WAM B′ latent probe
```

## 跑 B′-1 + B′-2

```bash
source experiments/aerial/scripts/env_4090.sh
DS=experiments/aerial/rl/artifacts/dataset_v0_p45_merged_20260821
CKPT=experiments/aerial/rl/artifacts/wm_ckpt_coll_full_20260827/wm_step_1000.pt

$AERIAL_PY experiments/aerial/scripts/wam_latent_depth_probe.py \
  --dataset "$DS" --wm-ckpt "$CKPT" --stride 2 --max-samples 32 \
  --out artifacts/wam_latent_depth_probe_20260827.json

$AERIAL_PY experiments/aerial/scripts/wam_imagine_coll_rank.py \
  --dataset "$DS" --wm-ckpt "$CKPT" --stride 2 --max-samples 32 \
  --encode-mode window --window 8 \
  --out artifacts/wam_imagine_coll_rank_hwindow_20260827.json
```

## 汇报

- B′-1：`readout`、`center_depth.encode_single/window` 的 R² / MAE
- B′-2：window `median_p_coll_gap` vs h100full single **0.0018**
- 更新 `RUNBOOK_wam_imagination.md` §7 B 备注 + `V4_RUNBOOK_125_STATUS.md`
- **禁止开 E**；不改 deploy yaml

权威：`experiments/aerial/RUNBOOK_wam_imagination.md` §B′
