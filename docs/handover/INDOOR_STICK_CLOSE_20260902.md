# Indoor Stick mainline — CLOSED (2026-09-02)

> **裁定**：`aerial-indoor-wam` Stick 主航道 **先算 close**。  
> **下一项目**：室内语义导航（指令 → 开放词表 → 搜+飞）另立于 [`aerial-vgoal-wam`](../../../aerial-vgoal-wam/) · 设计 [`2026-09-02-indoor-semantic-nav-design.md`](../../../aerial-vgoal-wam/docs/superpowers/specs/2026-09-02-indoor-semantic-nav-design.md)

## 已 close（主航道）

| 项 | 状态 |
|----|------|
| F-cap east @0.50 · gt_proxy | ✅ PASS |
| Spawn z=1.8 工程 | ✅ east/south/west 探针绿 |
| SE 联合 F-cap | ✅ 6/6 · spawn=0 |
| E3 sim hat | 📦 **签 C**（双报 · 停追 · 非传感完成） |

## 明确不宣称

- 产品室内 12/12 结案（仍 **0/12**）
- E3 `arrived_hat` G1
- 无罩 π 避障、F4 域训、部署、V4 室内语义 AC

## 渲染器

室内刀结束如需归还 outdoor Phase-2：

```bash
bash experiments/aerial/scripts/recover_renderer_scene.sh outdoor
```

## 接手

语义导航实现与评测 → **打开 / 切到 `aerial-vgoal-wam`**，按设计 P0→P1→P2。本仓仅作 env / E-head / shield 捐赠方。
