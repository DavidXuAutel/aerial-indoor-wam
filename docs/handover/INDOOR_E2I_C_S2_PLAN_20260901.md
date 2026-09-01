# Indoor WAM — E2i.C S2 近场绕障（草案）· 2026-09-01

> **依赖**：S3 ✅ 主头 = **B**；S1 滤 SPAWN 记账后开刀  
> **禁**：夹具当完成；shield-off；无人令 E3；再堆直线近场 BC

## 目标

对 **R06 类怼柜**（有侧向通道仍前撞）做短课，使主头 B 在 **@0.20** 质量门可议（mean≤0.8 或 arrival≥25%，assist=none，罩 ON）。

## 料（死）

| 项 | 要求 |
|----|------|
| assist | **none**（合同同构） |
| 场景 | Building_99；优先 R06 邻域 + 其它 NEAR_COLL 路由 |
| 标签 | 侧移/绕停成功；**拒** 纯直线贴脸到点 |
| SPAWN | 训练 **丢弃** steps≤8 碰撞轨；评测可另账 |

## 步骤（待 S1 数字齐）

```text
S2.1  采：主头 B + shield ON + assist=none，近障成功绕行（目标 ~40–80 条干净）
S2.2  可选短 encode（仅当视觉域再漂）
S2.3  π 短 FT（init = e2i_b）
S2.4  评 @0.20（全 8 路由 + 分列 SPAWN/NEAR/ARRIVE）+ 质量门
```

## 过门

- 质量门优先；legacy「2/3 seed 一次到点」仅旁注  
- R06 至少 1/3 seed 不撞柜或 d_end 明显改善  
- 不过门 → 停，写事后，**不**自动开更深 FT
