# Indoor WAM — STATUS（主航道）

> **更新**：2026-09-01（**起终点净空审计** → `clean_sg`；**F1c** @0.50）  
> **审计**：`artifacts/building99_route_clearance_audit_20260901.json`  
> **干净集**：`artifacts/building99_indoor_short_routes_clean_sg.json`

## 一句话

按规则删掉：**起飞净空&lt;1 m / 前探即撞**，以及 **终点净空&lt;1 m / 终点碰障**。保留 west / south / east_from_1。下一刀 **F1c** 在该集上 @0.50 评（禁 FT）。

## 勾选

| 项 | 状态 |
|----|------|
| F1 @0.50 | ❌ G2（北向脏） |
| F1 视频 | ✅ |
| F1b 手工去北向 | ❌ 仍被 **west** SPAWN×3 拖死 |
| **起终点 clearance 审计** | ✅ start≥1.0 · goal≥1.0 + nudge |
| **clean_sg 标注** | ✅ 3 条 |
| **F1c @0.50** | 🔄 跑中 |
| E3 / 盲 FT | ⛔ |

## 审计丢掉（full8）

| 路由 | 原因 |
|------|------|
| east_3m | start_collide_nudge / 净空 0.7 |
| north_3m | **goal_collide**（终点贴障 0.12） |
| north_from_y1 | **goal_collide** |
| diag_ne | goal_clearance 0.83&lt;1.0 |
| diag_nw | goal_clearance 0.17&lt;1.0 |
