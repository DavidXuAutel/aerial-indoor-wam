# 125 Agent：E3 velfix 同步 + east spawn watch（2026-09-02）

> **Workspace**：`/home/yao/aerial-indoor-wam`  
> **权威**：[`INDOOR_E3_PLAN_20260902.md`](INDOOR_E3_PLAN_20260902.md) · [`INDOOR_0XM_STATUS.md`](INDOOR_0XM_STATUS.md)  
> **主门不变**：F2-cap east @0.50 · gt_proxy ✅（[`INDOOR_E2I_F_PLAN_20260901.md`](INDOOR_E2I_F_PLAN_20260901.md) §1.1）

## 背景

Mac 已推 **velfix**（`pose_estimate.py` 用 `obs.velocity×dt` 积分）+ E3 全管线脚本。E3.3 post-FT G1 仍 ❌（odom hat 全灭）；E3.5 审计 velfix 后 east **2/3 arr_hat**。East formal odom re-eval 被 **sim SPAWN** 挡住 → **spawn watch 后台静默、非 blocker**。

## 同步

```bash
cd /home/yao/aerial-indoor-wam
git fetch github && git merge github/main   # 或 origin/main
mkdir -p artifacts logs
cp -n building99_indoor_short_routes_clean_*.json artifacts/ 2>/dev/null || true
python3 -m pytest experiments/aerial/rl/tests/test_pose_estimate.py -q   # 期望 7 passed
```

## Spawn watch（若已在跑旧 commit → 重启）

旧 watch 不含 velfix / 新 eval 链时 **kill 后重开**：

```bash
# 可选：查旧进程
pgrep -af run_e2i_e3_east_spawn_watch || true

STAMP=20260902_velfix nohup bash experiments/aerial/scripts/run_e2i_e3_east_spawn_watch.sh \
  >> logs/e2i_e3_east_spawn_watch_20260902_velfix.nohup.log 2>&1 &
echo "watch pid=$!"
tail -f logs/e2i_e3_east_spawn_watch_20260902_velfix.nohup.log
```

| 项 | 值 |
|----|-----|
| 探针 | gt_proxy · clean_sg **route 2**（east） |
| 间隔 | 300 s · 最多 48 轮 |
| 日志 | `logs/e2i_e3_east_spawn_watch_20260902_velfix.nohup.log` |
| GREEN 后 | 自动 odom east 3-seed + F-cap summary |

**GREEN 产物**：

`artifacts/indoor_e2i_e3_odom_east_sg_velfix_050_summary_20260902_velfix.json`

读 summary → 回写 STATUS「E3 formal east odom」行（**禁止** gt_proxy 冒充 E3 完成）。

## 若 summary G1 仍差

1. 读 gap diag / step audit 工件（E3 plan §8–§10）  
2. **仅在人令下** 议 E3.2′ **小 FT**（非盲 400 iters）  
3. south/west → **F-hygiene**（`indoor_west_collision_probe.py`），不过门

## 禁止

- spawn 死磕当主门 blocker  
- 盲加 H100 iters  
- gt_proxy 写 E3 传感完成态  
- Mac 上长 eval（归属 125）
