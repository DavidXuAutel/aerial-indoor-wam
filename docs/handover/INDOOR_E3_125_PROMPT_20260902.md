# 125 Agent：E3 velfix 同步（2026-09-02 · **归档 / 非阻塞**）

> **Workspace**：`/home/yao/aerial-indoor-wam`  
> **权威**：[`INDOOR_E3_PLAN_20260902.md`](INDOOR_E3_PLAN_20260902.md) · [`INDOOR_0XM_STATUS.md`](INDOOR_0XM_STATUS.md)  
> **主门不变**：F2-cap east @0.50 · gt_proxy ✅（[`INDOOR_E2I_F_PLAN_20260901.md`](INDOOR_E2I_F_PLAN_20260901.md) §1.1）  
> **线程状态**：Mac **已 close**；E3 formal odom east = **deferred**（sim SPAWN hygiene）

## 背景

Mac 已推 **velfix** + E3 脚本（`7589a9d`+）。E3.3 post-FT G1 ❌；E3.5 velfix 审计 east **2/3 arr_hat**。East formal odom 被 **sim SPAWN** 挡住 — **非主门 blocker**。

## 同步（若 125 未 pull）

```bash
cd /home/yao/aerial-indoor-wam
git fetch github && git merge github/main
mkdir -p artifacts logs
cp -n building99_indoor_short_routes_clean_*.json artifacts/ 2>/dev/null || true
python3 -m pytest experiments/aerial/rl/tests/test_pose_estimate.py -q   # 期望 7 passed
```

**不必为 velfix 重启 watch**：GREEN 后 odom eval 每次新起 Python，**pull 后自动读新 `pose_estimate.py`**。仅当改了 bash 脚本逻辑才需重启 watch。

## Spawn watch（可选 · 可 kill）

已在跑则 **可留可停**；不跑也不阻塞 close。

```bash
pgrep -af run_e2i_e3_east_spawn_watch || true
# 停：kill <pid>
# 启：
STAMP=20260902_velfix nohup bash experiments/aerial/scripts/run_e2i_e3_east_spawn_watch.sh \
  >> logs/e2i_e3_east_spawn_watch_20260902_velfix.nohup.log 2>&1 &
```

| 项 | 值 |
|----|-----|
| 探针 | gt_proxy · clean_sg **route 2**（east） |
| 间隔 | 300 s · 最多 48 轮 |
| 日志 | `logs/e2i_e3_east_spawn_watch_20260902_velfix.nohup.log` |
| GREEN 后 | 自动 odom east 3-seed + summary |

**GREEN 产物**：`artifacts/indoor_e2i_e3_odom_east_sg_velfix_050_summary_20260902_velfix.json`  
→ 可选回写 STATUS「E3 formal east odom」行（**禁止** gt_proxy 冒充 E3 完成）。

## 若日后补跑 formal eval

```bash
bash experiments/aerial/scripts/run_e2i_e3_east_velfix_eval.sh
```

G1 仍差 → **仅人令** 议 E3.2′ 小 FT；south/west → F-hygiene。

## 禁止

- spawn 死磕当主门 blocker  
- 盲加 H100 iters  
- gt_proxy 写 E3 传感完成态  
- Mac 上长 eval（归属 125）
