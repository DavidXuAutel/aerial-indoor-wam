# Indoor WAM — E2i.C（S3→S1→S2）· 2026-09-01

> **人令**：按这个来  
> **前置**：B @0.20 FAIL；视频确认 SPAWN（R01）+ NEAR_COLL（R06）+ B 欠收口（R04/R07）  
> **事后**：[`INDOOR_E2I_B_POSTMORTEM_20260901.md`](INDOOR_E2I_B_POSTMORTEM_20260901.md)  
> **禁**：同款近场 BC 碰运气；夹具/shield-off 完成态；无人令 E3

## 代号

| 代号 | 人话 |
|------|------|
| **A** | 室内 encode 后再训 π、已过 @0.50 的基准头 |
| **B** | 冲 @0.20 失败的头（近场 B1+再 encode） |
| **S3** | A vs B 同协议 @0.50 回测，定主头 |
| **S1** | SPAWN（开场撞）治理：过滤/改起点 + 分列记账 |
| **S2** | 近场绕障专课（对 R06 怼柜），主料仍 `assist=none` |

## 顺序（死）

```text
C0  本文件落盘
C1  S3：A vs B @0.50（8×3，罩 ON，assist=none）
C2  根据 S3：主头钉 A（若 B 明显差）或并列说明
C3  S1：评测拆 SPAWN/NEAR/ARRIVE；改/滤 R01；训练过滤早撞
C4  S2：在主头上近场绕障数据/短 FT → @0.20 质量门
```

## S3 过门读数

- 主：对比 mean d、到点率、碰撞；**不以「2/3 seed 有一次到点」单独定案**
- 若 B 的 mean/到点率明显差于 A → **主头 = A**，B 归档废分支
- 工件：`artifacts/indoor_e2i_c_s3_A050_summary_*.json` / `…_B050_summary_*.json` / `…_compare_*.json`

### S3 实结（2026-09-01）

| 头 | seeds 有到点 | mean d | 到点率 | 撞 / SPAWN / NEAR |
|----|-------------|--------|--------|-------------------|
| A050 | 3/3 | **1.91** | 37.5% (9/24) | 15 / 7 / 8 |
| B050 | 3/3 | **1.54** | **45.8% (11/24)** | 13 / 4 / 9 |

- 规则：`prefer A if B mean worse >0.3 OR A arrival higher >0.10` → **未触发** → `recommend_primary_head=tie_or_B`
- **主头钉 B（@0.50）**；A 仍作对照。**B@0.20 仍 FAIL**，不回滚该结论。
- 工件：`artifacts/indoor_e2i_c_s3_compare_050_20260901.json`

## S1 / S2（S3 后）

| 步 | 状态 | 命令 / 工件 |
|----|------|-------------|
| S1 分列 | ✅ | `indoor_fail_split_report.py`；seed0 A/B 均为 SPAWN1+NEAR3+ARRIVE4 |
| S1 滤 R01 | ✅ | nospawn B@0.50：mean **1.28** / arr **57%**；SPAWN 仍 5/21 → **不止 R01** |
| S2 | 🔄 | 主头 B；`run_e2i_c_s2_collect.sh` → FT/eval |
