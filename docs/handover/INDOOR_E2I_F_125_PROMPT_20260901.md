# 125 Agent：E2i.F F1 — @0.50 nospawn 主门基线（禁 FT）

> **Workspace**：`/home/yao/aerial-indoor-wam`  
> **权威**：[`INDOOR_E2I_F_PLAN_20260901.md`](INDOOR_E2I_F_PLAN_20260901.md)  
> **STATUS**：[`INDOOR_0XM_STATUS.md`](INDOOR_0XM_STATUS.md)

## 任务

只跑 **F1**：当前 E 头在 **nospawn** 集上、`success_dist=0.50`、`assist=none`、罩 ON、`gt_proxy`（探针）。**禁止 FT / 改权重 / 关罩。**

## 命令

```bash
cd /home/yao/aerial-indoor-wam
git pull --ff-only   # 或与 Mac 同步 F 计划 + 脚本
bash experiments/aerial/scripts/run_e2i_f_primary_050_nospawn_eval.sh
```

## 过门（写回 STATUS）

读 `artifacts/indoor_e2i_f_050_nospawn_summary_*.json`：

- `primary_gate_pass` true/false  
- G1–G4 逐项  
- SPAWN / NEAR 分列  

**过** → STATUS 勾 F1 ✅；标注「0.5 m 探针水位」；**仍禁止**写成传感合同完成。  
**不过** → 只写 fail_split 归因；**禁止**为冲 0.20 再 FT。

## 禁止

盲 FT；shield-off；夹具当完成；无人令 E3；把 stretch @0.20 写主完成态。
