# Indoor WAM — 致命缺口逐项续作（2026-09-02）

> **前置**：F-cap ✅ · E3 velfix ✅ · formal odom **deferred**  
> **权威**：[`INDOOR_FATAL_DEFECTS_20260831.md`](INDOOR_FATAL_DEFECTS_20260831.md) · [`INDOOR_0XM_STATUS.md`](INDOOR_0XM_STATUS.md)  
> **用法**：按 **序#** 逐项推进；**不过门**项标 hygiene；产品结案须 **12/12 产品列** 全绿（当前 **0/12**）。

## 总览

| 序# | ID | 缺口 | 09-02 | 产品结案 | 下一刀归属 |
|-----|-----|------|-------|----------|------------|
| 1 | F5 | 指标污染 | 纪律+F-cap | ⚠️ 流程 | Mac 文档 |
| 2 | F10 | SPAWN/可复现 | ✅ 探针 | ❌ | hygiene 结论已落盘 |
| 3 | F2 | gt_proxy | E3 签 C | ❌ | 估器重开=VIO/真机 |
| 4 | F8 | E3 formal | 📦 签 C · G1 未过 | ❌ | **停追** sim hat |
| 5 | F9 | E3 ckpt×velfix | 📦 随签 C 搁置 | ❌ | 人令 VIO 后再议 |
| 6 | F6 | 单路由 | **south PASS z18** | ❌ | west hygiene / 产品扩 |
| 7 | F1 | 夹具训/none验 | ⚠️ 审计 | ❌ | fixture_frac=0.25 |
| 8 | F3 | π 无罩近场 | 罩已修 | ❌ | 归档 shield-off |
| 9 | F7 | @0.20 产品精度 | ✅ stretch 44% | ❌ | 旁注已报 |
| 10 | F4 | 域适配 | 未结案 | ❌ | **人令** H100 F4 |
| 11 | F11 | 动态/部署 | 未测 | ❌ | 部署轨（另立） |
| 12 | F12 | WAM AC 室内 | 未证 | ❌ | V4 轨（另立） |

---

## 序 1 · F5 — 指标污染（撞近/夹具/SPAWN）

**缺口**：`d_end`  alone 可误读；SPAWN/夹具/shield-off 可刷假进度。

**09-02**：F-cap 剔 SPAWN 分母；G3 强制 arrived `collided=false`；F PLAN §1.1 冻结。

**继续**：

| 步 | 动作 | 归属 |
|----|------|------|
| 1.1 | 所有新报表强制 `gate_mode=cap` + fail_split | Mac 脚本已 wired |
| 1.2 | stretch @0.20 标签 **`stretch`**，禁止进主完成态句子 | 汇报纪律 |

**过门（产品）**：任何对外「完成态」文档含 gt_proxy/夹具/shield-off 数字 ⇒ **FAIL**。

**状态**：⚠️ **流程缓解** — 不阻塞 F-cap close；产品仍依赖人工审表。

---

## 序 2 · F10 — SPAWN / 可复现卫生

**缺口**：west/south/east intermittent 首步撞；sim 贴地、spawn 点、动线。

**证据**：F1c–F1e west SPAWN×3；south F1d 全 SPAWN；east ~11:05 起 gt/odom 同 SPAWN。

**继续**：

```bash
# 125 · west 逐步撞障归因
bash experiments/aerial/scripts/run_e2i_f_hygiene_west_probe.sh

# 125 · south 对照（clean_sg route 1 · gt_proxy 探针）
bash experiments/aerial/scripts/run_e2i_f_hygiene_south_spawn_probe.sh
```

**2026-09-02 结果（fix 前）**：探针 JSON 落盘；west policy step0 → floor；south SPAWN。

**2026-09-02 spawn fix 后**：east `east_spawn_probe_postfix` — **spawn_rate=0 · 3/3 arr · cap PASS**；south probe — **spawn=false · arrived d≈0.44**。

**过门（产品）**：full8 或 clean_sg **non-SPAWN spawn_rate < 10%** 稳定 3 天 — **单日复探已绿，未做 3 日稳定性**。

**禁止**：为压 spawn 无限改 sim / 擦路由当主门 blocker。

---

## 序 3 · F2 — gt_proxy（产品位姿 never tested）

**缺口**：合同 `RGB+IMU+高度→p̂`；主评仍 stub。

**继续**：见序 4–5（E3 链）；F-cap 成绩 **只标 probe**。

**过门（产品）**：独立 **E3-cap** 门须 **真 VIO/`vio_est` 或真机** 后再开；仿真 odom **签 C 不凑 G1**。报表始终 **双报 gt/hat**。

---

## 序 4 · F8 — E3 formal odom east

**缺口**：E3.3 / formal z18 **`arrived_hat` 未过 G1**（估器开环 CE，非 π 不会飞）。

**2026-09-02_z18 双报（权威归档）**：

| 指标 | 值 |
|------|-----|
| spawn_rate | **0** |
| arrived_gt | **3/3** |
| arrived_hat (G1) | **1/3** · **未过** |
| G2/G3 | ✅ |
| 工件 | `artifacts/indoor_e2i_e3_odom_east_velfix_050_summary_20260902_z18.json` |

**签 C（人令 2026-09-02）**：**停追** sim odom CE（scale / dt / 梯形 / E3.2′）。**不**写 E3 传感完成。重开 = 开源 VIO→`vio_est` 或真机（另令人令）。

---

## 序 5 · F9 — E3 ckpt × velfix 未对齐

**缺口**：FT 与 velfix 后 p̂ 分布未对齐。

**签 C**：随序 4 **搁置**；禁盲 400 iters。VIO/真机重开估器后再议是否小 FT。

---

## 序 6 · F6 — 单路由 east / south

**缺口**：F-cap 原仅 east_from_1；需扩 south（west 仅 hygiene）。

```bash
STAMP=20260902_z18 TAG=f3_cap_050_south ROUTES=0 GATE_MODE=cap PROTOCOL=e2i_f3_cap_south \
  ANN=building99_indoor_short_routes_clean_se.json \
  bash experiments/aerial/scripts/run_e2i_f_eval_050.sh
```

**2026-09-02（fix 前）**：`..._summary_20260902.json` — **FAIL** · 3/3 SPAWN · n_scored=0。

**2026-09-02_z18（spawn fix 后重跑）**：`artifacts/indoor_e2i_f3_cap_050_south_summary_20260902_z18.json`

| 指标 | 值 |
|------|-----|
| primary_gate_pass_cap | **true** |
| G1–G4 | ✅ |
| arrived_scored | **3/3** · rate **1.0** |
| mean_d_scored | ≈ **0.47 m** |
| spawn_rate | **0** |
| pose_source | gt_proxy（探针 · 非 E3） |

**过门（F3 south 探针）**：✅ **PASS**（gt_proxy）。产品扩路由仍待 west hygiene / 多路由合同。

**禁止**：west 进主门分母（仅 hygiene 序 2）；gt_proxy south 冒充 E3。

---

## 序 7 · F1 — 夹具训 / assist=none 验

**缺口**：训练分布含夹具；验收 none。

**继续**：

| 步 | 动作 |
|----|------|
| 7.1 | ✅ E 头 `dataset_indoor_e2i_e_20260901`：`e2i_e_mix` · **fixture_frac=0.25** |
| 7.2 | ✅ F-collect east 39 NPZ：manifest **`assist=none`** · gt_proxy · drop_collided |
| 7.3 | E3 集 60 NPZ：**assist=none** · train/eval=odom |
| 7.4 | ✅ south F3 z18 **PASS** → 可议 south collect（人令） |

**过门（产品）**：下轮 FT **B1/none ≥70%** 主料；B2 夹具 **≤25%** — E 头 **0.25 边界合规**，但 **F1 结构性残留未消**（mix 仍含夹具）。

---

## 序 8 · F3 — π 无罩近场避障

**缺口**：shield-off 0.63 m collided；不能主张 π 自主避障。

**继续**（125 · **归档 diag only**）：

```bash
# 已有工件复阅，不写入完成态
# artifacts/indoor_shield_off_diag_summary_20260831.json
bash experiments/aerial/scripts/run_e2i_f2_cap_050_eval.sh  # 对照：罩 ON 水位
```

**过门（产品）**：**不设** shield-off 产品门；仅当 shield-off arrived @0.50 **且 collided=false** 才可议（当前 **否**）。

**状态**：罩 v3 **工程结案**；π 无罩 **仍 FAIL**。

---

## 序 9 · F7 — @0.20 产品精度

**缺口**：产品常写 0.2 m；主门已 0.50 m 探针。

**继续**（125 · stretch 旁注）：

```bash
STAMP=20260902 SUCCESS_DIST=0.20 \
  ACT=experiments/aerial/rl/artifacts/v4_ac_ckpt_indoor_e2i_e_20260901/v4_ac_latest.pt \
  bash experiments/aerial/scripts/run_e2i_f_primary_050_nospawn_eval.sh
```

**2026-09-02 结果**：`artifacts/indoor_e2i_f_020_nospawn_summary_20260902.json` — **arr 44% (8/18)** · mean_d≈**1.24** · spawn=2 · **primary_gate_pass=false**（标签 **`stretch`**，非产品门）。

**过门**：**无产品门**；数字标签 **`stretch`**；禁止 stretch PASS ⇒ 产品完成。

---

## 序 10 · F4 — 室外→室内域适配

**缺口**：WM encode / 尺度 / 视觉域未室内结案。

**继续**（**须人令**）：

```bash
# 见 INDOOR_FULL_STACK §13 · INDOOR_E2I_A_PLAN
bash experiments/aerial/scripts/run_e2i_a_pipeline.sh   # 或 F4 新日程
```

**过门**：clean_sg 或 nospawn **≥2 路由** @0.50 cap PASS + mean_d≤1.0 — **非单路由补洞**。

**禁止**：4090×500 碰运气；单 east 补洞冒充 F4。

---

## 序 11 · F11 — 动态障碍 / 真部署

**缺口**：静态 sim 路由；动态人、实机、渲染共享未合同化。

**继续**：另立 **部署轨**（hold 动线 / 换 spawn / 实机 VIO）— **不在 Stick sim 主门内**。

**过门**：部署 checklist 单独签字 — **未开**。

---

## 序 12 · F12 — WAM 想象 AC 室内语义

**缺口**：室内只证 π+罩 到点；D̂/τ/imagined AC 未过室内门。

**继续**：回 **V4 主线**（P4.5 / 分层到达）— 与 indoor F-cap **正交**。

**过门**：V4 签字表 + 室内子集 eval — **未开**。

---

## 125 执行顺序（默认）

```text
序1 F5   Mac 已文档化
序2 F10  ✅ west/south 探针
序6 F6   ✅ south cap FAIL（全 SPAWN）
序7 F1   ✅ 语料审计（fixture 25% · collect none）
序9 F7   ✅ stretch @0.20 arr 44%
序4 F8   sim 可飞 → run_e2i_e3_east_velfix_eval.sh
序5 F9   读 summary → 人令 E3.2′
序8 F3   归档 shield-off（不新跑）
序10 F4  等人令
序11–12 另立轨
```

## 产品结案判据（12/12）

全部满足才可写「产品室内导航避障结案」：

1. F5 流程审计通过  
2. F10 spawn_rate 稳定低位（或部署轨替代 sim）  
3–5. F2/F8/F9：E3-cap east odom PASS + ckpt 对齐  
6. F6：≥2 路由 cap PASS  
7. F1：none 主料 FT 纪律  
8. F3：接受「罩 ON 产品态」或 shield-off 实证  
9. F7：@0.20 stretch 报出（非必须 PASS）  
10. F4：WM+π 室内适配签字  
11. F11：部署 checklist  
12. F12：V4 室内子集（若产品含 AC）

**当前：0/12 — F-cap 里程碑可 close，产品不可 close。**

---

*Mac Agent · 2026-09-02 · 人令：致命缺口逐一继续*
