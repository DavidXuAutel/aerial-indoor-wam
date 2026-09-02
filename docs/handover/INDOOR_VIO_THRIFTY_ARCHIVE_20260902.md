# Indoor VIO thrifty — ARCHIVED (2026-09-02)

> **裁定**：仿真 thrifty 自洽探针 **签过归档** · **停追** AirSim 占位标定 / ZOH IMU。  
> **权威结果**：[`INDOOR_VIO_PROBE_RESULT_20260902.md`](INDOOR_VIO_PROBE_RESULT_20260902.md)  
> **选型/脚手架**：[`INDOOR_VIO_OPENSOURCE_PROBE_20260902.md`](INDOOR_VIO_OPENSOURCE_PROBE_20260902.md)

## 已 archive（sim thrifty）

| 项 | 状态 |
|----|------|
| S1 合成悬停 imu-only drift≈0 | ✅ |
| S2 fixture + `imu_mode=hover` + gt-init + imu-only · ATE ≤ 5 m | ✅ **3.13 m** |
| Gate 工件（125） | `artifacts/vio_probe/thrifty_gate_20260902_hover.json` · `ov_thrifty_hover_20260902_174512` |
| 仓内脚手架 | `experiments/aerial/vio_probe/` · `pose_source=vio_est` · live bridge · fan-out 640×480 |

## 明确不宣称

- 产品 VIO / F-cap 换源 / E3-cap 传感完成
- AirSim ZOH 当真 IMU 可积（故意不做）
- 闭环米级 `d_hat`、占位 K 精修、auto-init 过门

## 重开条件（须人令）

真机采集 + 真相机/IMU 标定 + 真 IMU 流 → 再接 `vio_est` / 部署轨。

## 停做

- 再开 sim CE / 假 IMU 积分兔洞  
- 无人令把 `arrived_hat` / live smoke 炸数当产品完成
