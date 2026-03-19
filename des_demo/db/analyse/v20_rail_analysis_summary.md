# Innovus v20 Dynamic IR Drop 分析实验报告

## 1. 实验目的

对 DES3 加密核进行基于 VCD 波形的动态 IR Drop 分析，将完整仿真时间 (0~11850ns) 划分为 5 个等长窗口分别分析，并与全时段分析结果对比，验证分窗口方法的有效性和覆盖能力。

## 2. 实验环境

| 项目 | 配置 |
|------|------|
| EDA 工具 | Cadence Innovus v20.10-p004_1 (含 Voltus 引擎) |
| 服务器 | Intel Xeon Platinum 8475B, 48 cores, CentOS 7.9 |
| 设计 | DES3 加密核 (ASAP7 7nm 工艺库) |
| 电源电压 | VDD = 0.7V |
| IR Drop 阈值 | 0.651V (7% margin) |
| VCD 来源 | RTL 仿真 `test.vcd`, timescale 10ps, 总时长 11850ns |
| 功耗分析方式 | Dynamic vector-based, resolution 1ns, avg current |
| Rail 分析精度 | XD (eXtended Dynamic) |

## 3. 时间窗口划分

VCD 总时长 11850ns，等分为 5 个窗口 (每窗口 2370ns):

| 窗口 | 起始时间 | 结束时间 | 对应 VCD 时间戳 |
|------|---------|---------|----------------|
| win1 | 0ns | 2370ns | #0 ~ #237000 |
| win2 | 2370ns | 4740ns | #237000 ~ #474000 |
| win3 | 4740ns | 7110ns | #474000 ~ #711000 |
| win4 | 7110ns | 9480ns | #711000 ~ #948000 |
| win5 | 9480ns | 11850ns | #948000 ~ #1185000 |
| full | 0ns | 11850ns | #0 ~ #1185000 |

## 4. 分析流程

```
加载设计 (LEF/DEF/Verilog/MMMC)
    ↓
生成 PG Library (techonly, QRC tech file)
    ↓
┌─ 循环每个时间窗口 ──────────────────────┐
│  功耗分析:                              │
│    read_activity_file -start -end       │
│    set_dynamic_power_simulation         │
│    report_power → ptiavg 文件           │
│  Rail 分析:                             │
│    set_power_data (加载 ptiavg)         │
│    set_rail_analysis_mode -accuracy xd  │
│    analyze_rail → 报告 + 热力图         │
└─────────────────────────────────────────┘
```

关键脚本:
- `full_irdrop_v20.tcl` — 5 窗口完整流程 (功耗 + Rail)
- `rerun_rail_v20_fix.tcl` — 仅 Rail 分析 (复用已有 power 数据)
- `full_irdrop_v20_full.tcl` — 全时段完整流程

## 5. VDD IR Drop 结果

### 5.1 各窗口 IR Drop 总览

| 数据集 | Min Voltage | Avg Voltage | Max IR Drop | Worst Case Interval | Violations |
|--------|------------|------------|-------------|-------------------|------------|
| **full** | **0.674V** | **0.681V** | **26mV** | **4.050us** | **0** |
| win1 | 0.676V | 0.685V | 24mV | 2.350us | 0 |
| **win2** | **0.674V** | **0.683V** | **26mV** | **1.680us** | **0** |
| win3 | 0.678V | 0.684V | 22mV | 10ns | 0 |
| win4 | 0.675V | 0.683V | 25mV | 2.140us | 0 |
| win5 | 0.675V | 0.684V | 25mV | 0.370us | 0 |

### 5.2 VSS Ground Bounce 总览

| 数据集 | Min IR Drop | Avg IR Drop | Max IR Drop |
|--------|------------|------------|-------------|
| **full** | **0.000V** | **18.127mV** | **23.822mV** |
| win1 | 0.000V | 15.234mV | 22.164mV |
| **win2** | **0.000V** | **16.633mV** | **23.823mV** |
| win3 | 0.000V | 15.920mV | 19.961mV |
| win4 | 0.000V | 16.903mV | 22.681mV |
| win5 | 0.000V | 15.196mV | 22.503mV |

### 5.3 Layer-based IR Drop (VDD, 各窗口 Max IR Drop)

| Layer | win1 | win2 | win3 | win4 | win5 | full |
|-------|------|------|------|------|------|------|
| M6 | 13.3mV | 23.2mV | 18.6mV | 17.7mV | 22.2mV | 23.2mV |
| M5 | 13.3mV | 23.2mV | 18.8mV | 17.7mV | 22.3mV | 23.2mV |
| M4 | 12.4mV | 22.3mV | 17.5mV | 16.7mV | 21.5mV | 21.9mV |
| M3 | 20.7mV | 23.2mV | 18.5mV | 21.9mV | 22.2mV | 22.7mV |
| M2 | 19.7mV | 23.0mV | 17.8mV | 21.0mV | 22.0mV | 22.1mV |
| M1 | 19.3mV | 22.8mV | 17.4mV | 20.7mV | 21.9mV | 21.6mV |
| LISD | 20.9mV | 24.4mV | 19.1mV | 22.1mV | 23.5mV | 23.2mV |

## 6. 关键发现

### 6.1 Worst-case 窗口识别
- **win2 (2370~4740ns) 是最差窗口**，其 VDD Max IR Drop = 26mV，与 full 完全一致
- full 的 Worst Case Interval = 4.050us，对应绝对时间恰好落在 win2 范围内
- VSS 的 Max Ground Bounce 同样在 win2 达到最大 (23.823mV ≈ full 的 23.822mV)

### 6.2 窗口间差异分析
- IR Drop 范围: 22mV (win3) ~ 26mV (win2)，差异 18%
- **win3 是最优窗口** (22mV)，可能对应加密核切换活动较低的阶段
- win4、win5 的 IR Drop 接近 (25mV)，处于中等水平

### 6.3 分窗口 vs 全时段一致性
- 分窗口方法能准确捕获全时段的 worst-case IR Drop (win2 = full = 26mV)
- 分窗口的平均电压略高于 full (0.683~0.685V vs 0.681V)，因为单窗口时间更短，peak 效应被平均稀释程度不同
- 所有场景均为 0 violations (阈值 0.651V)，电网设计具有充足裕量

### 6.4 Layer 分布特征
- 上层金属 (M5/M6) IR Drop 主要受电源入口分布影响
- 下层金属 (M1/LISD) IR Drop 受局部单元电流密度影响
- **LISD 层 IR Drop 最大** (win2 达 24.4mV)，为直接连接标准单元的本地互连层

## 7. 输出文件清单

```
db/
├── power/
│   ├── avg_v20_win1/         # win1 功耗数据
│   ├── avg_v20_win2/         # win2 功耗数据
│   ├── avg_v20_win3/         # win3 功耗数据
│   ├── avg_v20_win4/         # win4 功耗数据
│   ├── avg_v20_win5/         # win5 功耗数据
│   └── avg_v20_full/         # 全时段功耗数据
├── rail_power_v20_win1/      # win1 Rail 报告
│   └── PD_25C_dynamic_1/Reports/{VDD,VSS}/
├── rail_power_v20_win2/      # win2 Rail 报告 (worst case)
├── rail_power_v20_win3/      # win3 Rail 报告
├── rail_power_v20_win4/      # win4 Rail 报告
├── rail_power_v20_win5/      # win5 Rail 报告
└── rail_power_v20_full/      # 全时段 Rail 报告
    └── PD_25C_dynamic_1/Reports/{VDD,VSS}/
        ├── VDD.main.rpt              # 主报告
        ├── VDD.layerbased_ir.rpt     # 逐层 IR Drop
        ├── VDD.iv                    # Instance 电压文件
        └── VDD_VSS.iv               # 有效 Instance 电压
```

## 8. 下一步

1. **覆盖率分析**: 使用 `coverage_tier1.py` 对 v20 数据计算 C₁(IR drop)、C_peak、C_layer、C_violation 覆盖率指标
2. **窗口筛选验证**: 基于 toggle 密度选出的 worst-case 窗口是否与 IR Drop 分析结论一致
3. **VCD 压缩效果评估**: 对比只保留 worst-case 窗口 vs 全时段分析的结果差异，量化压缩方法的有效性
