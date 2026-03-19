# 基于 IR Drop 结果的覆盖率量化——可用数据文件分析

## 1. 数据全景

本项目中 Voltus Rail Analysis 的输出分为两大类：

| 类别 | 路径 | 含义 | 角色 |
|------|------|------|------|
| **全集 (Ground Truth)** | `rail_power_v15/PD_25C_dynamic_1/` | 完整 VCD 仿真的 IR Drop 结果 | 基准 |
| **子集 win1** | `rail_power_v15_win1/.../PD_25C_dynamic_2/` | 最坏窗口 1 的 IR Drop 结果 | 被评估对象 |
| **子集 win2** | `rail_power_v15_win2/.../PD_25C_dynamic_2/` | 最坏窗口 2 的 IR Drop 结果 | 被评估对象 |
| **子集 win3** | `rail_power_v15_win3/.../PD_25C_dynamic_2/` | 最坏窗口 3 的 IR Drop 结果 | 被评估对象 |
| **子集 win4/5** | `rail_power_v15_win4,5/` | 最坏窗口 4,5（报告不完整） | 待补充 |

> **注意**: win3 的 `VDD.main.rpt` 未生成，win4/5 只有 `pgv_table.rpt`，没有 `VDD.main.rpt` 和 `layerbased_ir.rpt`。后续如需完整对比，需要重新运行 Voltus 报告生成步骤。

---

## 2. 可用于覆盖率量化的关键文件

### 2.1 ★★★ VDD.main.rpt — 全局汇总指标（最易用，文本格式）

| 字段 | 全集 (v15) | win1 | win2 |
|------|-----------|------|------|
| **M1 Min Voltage** | 0.667V | 0.673V | 0.667V |
| **M1 Avg Voltage** | 0.682V | 0.682V | 0.679V |
| **M1 Max Voltage** | 0.700V | 0.700V | 0.700V |
| **Worst IR Drop** | 0.033V | 0.027V | 0.033V |
| **Peak Dynamic Current** | 16.485mA | 16.215mA | 16.490mA |
| **Worst Case Interval** | 50ns | 2350ns | 1680ns |
| **Violations** | 0 | 0 | 0 |

**可量化的覆盖率指标**:

- **C1: 全局最坏 IR Drop 捕获率** = `max_IRdrop_sub / max_IRdrop_full`
  - win1: (0.700 - 0.673) / (0.700 - 0.667) = 0.027/0.033 = **81.8%**
  - win2: (0.700 - 0.667) / (0.700 - 0.667) = 0.033/0.033 = **100%**
- **C_peak: 峰值电流捕获率** = `peak_current_sub / peak_current_full`
  - win1: 16.215 / 16.485 = **98.4%**
  - win2: 16.490 / 16.485 = **100.0%** (甚至略高)

**文件位置**:
```
rail_power_v15/PD_25C_dynamic_1/Reports/VDD/VDD.main.rpt     ← 全集
rail_power_v15_win1/.../PD_25C_dynamic_2/Reports/VDD/VDD.main.rpt  ← win1
rail_power_v15_win2/.../PD_25C_dynamic_2/Reports/VDD/VDD.main.rpt  ← win2
```

---

### 2.2 ★★★ VDD.layerbased_ir.rpt — 分层 IR Drop（空间维度细化）

每个金属层的最坏 IR Drop 对比：

| Layer | 全集 IR Drop | 全集 Min V | win1 IR Drop | win1 Min V | win2 IR Drop | win2 Min V | win3 IR Drop | win3 Min V |
|-------|-------------|-----------|-------------|-----------|-------------|-----------|-------------|-----------|
| M7 | 0.0298V | 0.670V | 0.0140V | 0.686V | 0.0298V | 0.670V | 0.0298V | 0.670V |
| M6 | 0.0298V | 0.670V | 0.0143V | 0.686V | 0.0298V | 0.670V | 0.0298V | 0.670V |
| M5 | 0.0288V | 0.670V | 0.0132V | 0.685V | 0.0283V | 0.670V | 0.0275V | 0.670V |
| M4 | 0.0295V | 0.669V | 0.0242V | 0.674V | 0.0291V | 0.669V | 0.0279V | 0.669V |
| M3 | 0.0294V | 0.669V | 0.0230V | 0.674V | 0.0280V | 0.669V | 0.0275V | 0.669V |
| M2 | 0.0292V | 0.669V | 0.0227V | 0.674V | 0.0275V | 0.669V | 0.0270V | 0.669V |
| **M1** | **0.0312V** | **0.667V** | **0.0238V** | **0.673V** | **0.0295V** | **0.667V** | **0.0290V** | **0.667V** |

**可量化的覆盖率指标**:

- **C_layer: 逐层 IR Drop 捕获率** = `IRdrop_sub(layer) / IRdrop_full(layer)`
  - 可以看出 win1 在上层金属(M7/M6)的覆盖率仅 ~47%，但 win2/win3 几乎 100%
  - 这揭示了不同窗口对不同物理层面的覆盖差异

**文件位置**:
```
.../Reports/VDD/VDD.layerbased_ir.rpt   (每个 rail_power 目录下)
```

---

### 2.3 ★★★ VDD_dynpwr.rpt — 动态功耗峰值电流

| 来源 | Peak Dynamic Current |
|------|---------------------|
| 全集 | 1.6486e-02 A (16.486mA) |
| win1 | 1.6215e-02 A (16.215mA) |
| win2 | 1.6490e-02 A (16.490mA) |
| win3 | 1.7206e-02 A (17.206mA) |

**可量化**: 直接计算峰值电流覆盖率。win3 峰值电流甚至超过全集，说明子集在某些窗口捕获了全集未聚焦的瞬态高峰。

**文件位置**:
```
.../Reports/VDD/VDD_dynpwr.rpt
```

---

### 2.4 ★★☆ EIVDB/EIV/*.blob — 网格级有效实例电压（Hotspot 分析核心）

这是覆盖率量化中**最有价值但最难解析**的数据。

| Blob 文件 | 含义 | 用途 |
|-----------|------|------|
| **0.blob** | VDD-VSS 联合最坏有效电压（无实例标注） | **→ Hotspot 检出率 C2 的数据来源** |
| 1.blob | 最坏有效电压（含实例标注） | 可定位具体 instance |
| 2.blob | 最佳有效电压 | 参考 |
| 4.blob | 平均有效电压 | 分布分析 C3 |
| 6.blob | 最坏平均有效电压 | 统计补充 |

**如何用于覆盖率**:
- 如果能解析 blob 的二进制格式（Cadence 专有 tile 网格），可逐 tile 对比全集 vs 子集的电压值
- 定义 hotspot 阈值(如 Veff < 0.651V)，计算 Recall/Precision/F1
- 计算分布距离（Wasserstein）

**局限**: blob 是 Cadence 专有二进制格式，需要在 Innovus 中用 Tcl API 提取或寻找转换工具。

**文件位置**:
```
.../Reports/EIVDB/EIV/0.blob   (每个分析目录下约 1MB)
.../Reports/EIVDB/EIVDBInfo    (网络定义)
.../Reports/EIVDB/EIV/EIV.table (blob 索引)
```

---

### 2.5 ★★☆ ReportDB/ir.db — IR Drop 数据库

| 文件 | 大小 | 含义 |
|------|------|------|
| `VDD/ReportDB/ir.db` | ~567K | VDD IR Drop 按 tile 的数据库 |
| `VDD/ReportDB/iv.db` | ~441K | 实例电压数据库 |
| `VDD/ReportDB/dd.db` | ~567K | 电流密度数据库 |
| `VDD/ReportDB/tc.db` | ~441K | Current Tap 数据库 |
| `VDD/ReportDB/vc.db` | ~7K | 电压违例数据库 |

**可量化**: 如果能解析 `.db` 格式，可以做更精细的空间覆盖率分析。这些文件是 Innovus GUI 查看报告时读取的底层数据。

---

### 2.6 ★★☆ voltus_rail.worstcase — 最坏电压网格（二进制）

每个分析目录下 `VDD/voltus_rail.worstcase` (~567K) 存储了每个 tile 的最坏瞬态电压。

**可量化**: 逐 tile 对比，可直接用于 Hotspot 检出率计算。但同样是二进制格式。

---

### 2.7 ★★☆ VDD.instpower.gz / VDD.instcurrent.gz — 实例级功耗/电流

| 文件 | 全集大小 | 子集大小 | 含义 |
|------|---------|---------|------|
| `VDD.instpower.gz` | 247K | 247K | 每个标准单元实例的功耗 |
| `VDD.instcurrent.gz` | 47B (marker) | 47B | 实例电流（v15 版本可能未完整导出） |

**可量化**: 解压后可以对比每个 instance 的功耗分布，计算实例级覆盖率。

---

### 2.8 ★☆☆ GIF 热力图 — 可视化对比（定性）

| GIF 文件 | 含义 | 用途 |
|----------|------|------|
| `ir_linear.gif` | IR Drop 线性热力图 | 定性比较全集/子集的空间分布 |
| `ir_limit.gif` | 超阈值区域热力图 | 直观看 hotspot 分布差异 |
| `VDD_VSS.worst_eiv.gif` | 联合最坏有效电压热力图 | 最综合的单张图 |

**局限**: GIF 是渲染后的图片，无法精确提取数值，但可用于论文中的定性比较图。

---

### 2.9 ★☆☆ VDD.pgv_table.rpt — 单元库使用统计

列出了 103 种标准单元类型及实例数量（如 DFFHQx4 有 2489+4671 个实例），但**不包含 IR Drop 数值**，不能直接用于覆盖率计算。可作为补充信息说明设计复杂度。

---

### 2.10 ★☆☆ voltus_power.togglestats — 翻转统计

`power/avg/voltus_power.togglestats` 记录了每个时间步的全局 toggle count。这是功耗仿真的输入数据，虽然不直接是 IR Drop 结果，但可以辅助验证"高 toggle 窗口 → 高 IR Drop"的相关性假设。

---

## 3. 覆盖率量化可行性总结

### 第一梯队：立即可用（文本格式，无需解析二进制）

| 指标 | 数据来源 | 公式 | 可对比的维度 |
|------|---------|------|-------------|
| **C1: 最坏 IR Drop 捕获率** | `VDD.main.rpt` → Min Voltage | `(Vnom - Vmin_sub) / (Vnom - Vmin_full)` | 全局 |
| **C_peak: 峰值电流捕获率** | `VDD.main.rpt` → Peak Current | `Ipeak_sub / Ipeak_full` | 全局 |
| **C_layer: 逐层 IR Drop 捕获率** | `VDD.layerbased_ir.rpt` | 逐层 `IRdrop_sub / IRdrop_full` | 7 层金属 |
| **C_violation: 违例一致性** | `VDD.main.rpt` → Violations | 全集无违例 → 子集也无违例 = pass | 通过/失败 |

> **当前数据足够做这一梯队的完整分析，且已有全集 + win1/win2/win3(部分) 的数据。**

### 第二梯队：需要在 Innovus 中额外导出

| 指标 | 需要的数据 | 获取方法 |
|------|-----------|---------|
| **C2: Hotspot 检出率** | 逐 tile/instance 的最坏电压 | Innovus Tcl: `report_rail -output_file` 或解析 `voltus_rail.worstcase` |
| **C3: 分位数捕获率** | 所有 instance 的 Vmin 分布 | Innovus Tcl: `report_power_rail_results -instance_voltage` |
| **C4: 分布相似度** | 完整的电压/IR Drop 分布 | 同上，导出为 CSV 后用 Python 计算 |

### 第三梯队：辅助/定性分析

| 数据 | 用途 |
|------|------|
| GIF 热力图 | 论文配图，直观对比 |
| pgv_table.rpt | 设计复杂度描述 |
| togglestats | 验证 toggle 与 IR Drop 相关性 |

---

## 4. 建议的下一步行动

1. **立即可做**: 编写 Python 脚本自动解析所有 `VDD.main.rpt` 和 `VDD.layerbased_ir.rpt`，计算 C1/C_peak/C_layer 指标，输出对比表格。

2. **补全数据**: 对 win3/win4/win5 重新运行 Voltus 报告生成（`report_rail`），确保所有窗口都有完整的 `VDD.main.rpt`。

3. **深入分析（可选）**: 在 Innovus 中编写 Tcl 脚本，逐 instance 导出最坏电压，用于计算 Hotspot 检出率 C2。

4. **多窗口组合**: 评估 "win1+win2"、"win1+win2+win3" 等组合的联合覆盖率，为"最少保留几个窗口即可达到足够覆盖"提供量化依据。

---

## 5. 数据可用性速查表

| 文件 | 格式 | 全集 | win1 | win2 | win3 | win4 | win5 |
|------|------|------|------|------|------|------|------|
| VDD.main.rpt | 文本 | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| VDD.layerbased_ir.rpt | 文本 | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| VDD_dynpwr.rpt | 文本 | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| VDD.pgv_table.rpt | 文本 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| EIVDB/EIV/*.blob | 二进制 | ✅ | ✅ | ✅ | ✅ | ? | ? |
| voltus_rail.worstcase | 二进制 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| ReportDB/ir.db | 二进制 | ✅ | ✅ | ✅ | ✅ | ? | ? |
| ir_linear.gif | 图片 | ✅ | ✅ | ✅ | ✅ | ? | ? |
| VDD.instpower.gz | 压缩 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
