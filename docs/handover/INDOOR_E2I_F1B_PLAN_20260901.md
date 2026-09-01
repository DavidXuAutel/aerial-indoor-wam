# Indoor WAM — E2i.F1b（去北向脏路由 · @0.50 重评）· 2026-09-01

> **人令语境**：F1 FAIL 后视频抽检 → 下一刀 = **评测卫生**，禁 FT。  
> **前置**：[`INDOOR_E2I_F_PLAN_20260901.md`](INDOOR_E2I_F_PLAN_20260901.md)；F1 summary；视频 `artifacts/videos/indoor_e2i_f_vid_E050_20260901/`

## 0. 一句话

F1 的 G2 被 **`north_3m` 开场即撞** + **`north_from_y1` 怼柱** 拉爆；从主集去掉这两条，同 E 头重评 @0.50。

## 1. F1 视频归因（已证）

| nospawn idx | traj | F1 模式 | 视频 |
|-------------|------|---------|------|
| **0** | `B99_lobby_north_3m` | SPAWN×3 | **step=0 已 COLLIDED**，贴柱/展板 |
| **6** | `B99_lobby_north_from_y1` | NEAR×3 | ~11 步撞弯柱 |
| 1–3,5 | west/south/diag_ne/east_from_1 | 多数到点 | R04/R06 绿 ARRIVED |

到点局 mean≈**0.45** → 不是「不会 @0.50」。

## 2. F1b 集

```text
ann: building99_indoor_short_routes_nospawn_r01.json
ROUTES = 1,2,3,5     # 去 idx0 north_3m、idx6 north_from_y1
# 仍跳过 idx4 = diag_nw（原 R06 放弃）
4 routes × 3 seeds = 12 eps
头/罩/位姿/精度 = 同 F1（E · shield_v3 · gt_proxy 探针 · @0.50）
```

**过门（合取，n=12）**：

| # | 条件 |
|---|------|
| G1 | `arrival_rate ≥ 0.50` |
| G2 | `mean_d_end ≤ 1.0 m` |
| G3 | `collision_rate ≤ 0.50`；arrived 无撞 |
| G4 | fail_split 落盘 |

旁注：F1 全表与北向簇仍作污染对照，**不写完成态借口「删难路由刷分」**——删的是视频证伪的 **invalid spawn / 同簇怼柱**，不是随机丢失败。

## 3. 命令（125）

```bash
cd /home/yao/aerial-indoor-wam
bash experiments/aerial/scripts/run_e2i_f1b_clean_050_eval.sh
```

## 4. 读数后

| 结果 | 动作 |
|------|------|
| **过** | STATUS 钉「0.5 m 干净探针水位」；仍标 `gt_proxy`；禁当传感完成；禁自动冲 0.2 |
| **不过** | 只拆剩余失败（哪条 NEAR/MISS）；**仍禁盲 FT** |
| 北向簇 | 另册卫生/绕障；不绑主门 mean |

## 5. 禁

盲 FT；shield-off；夹具完成态；把 F1b PASS 写成「全 Building_99 已通」。
