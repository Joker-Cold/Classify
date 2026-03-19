# PI 仿真覆盖率计算方案

> 基于 coverage_analysis_guide.md、rail_power_v15_win1_guide.md、irdrop_coverage_framework.md 综合制定
> 日期：2026-03-18

---

## 一、目标

量化评估各最坏窗口子集（win1~win5）的 IR Drop 仿真结果相对于全集仿真结果的覆盖率，回答：

> **保留哪些窗口、保留几个窗口，才能在 PI sign-off 中达到足够的覆盖率？**

---

## 二、数据清单与可用性

### 2.1 全集 (Ground Truth)

| 数据 | 路径 | 状态 |
|------|------|------|
| VDD.main.rpt | `rail_power_v15/PD_25C_dynamic_1/Reports/VDD/VDD.main.rpt` | ✅ |
| VDD.layerbased_ir.rpt | `rail_power_v15/PD_25C_dynamic_1/Reports/VDD/VDD.layerbased_ir.rpt` | ✅ |
| VDD_dynpwr.rpt | `rail_power_v15/PD_25C_dynamic_1/Reports/VDD/VDD_dynpwr.rpt` | ✅ |
| VDD.instpower.gz | `rail_power_v15/PD_25C_dynamic_1/VDD/VDD.instpower.gz` | ✅ |

### 2.2 子集

| 窗口 | main.rpt | layerbased_ir.rpt | dynpwr.rpt | instpower.gz |
|------|----------|-------------------|------------|--------------|
| win1 | ✅ | ✅ | ✅ | ✅ |
| win2 | ✅ | ✅ | ✅ | ✅ |
| win3 | ❌ | ✅ | ✅ | ✅ |
| win4 | ❌ | ❌ | ❌ | ✅ |
| win5 | ❌ | ❌ | ❌ | ✅ |

> **结论**：win1/win2 数据完整可做全部指标；win3 缺 main.rpt，可做逐层分析和动态功耗分析；win4/win5 报告缺失严重，需重新运行 Voltus `report_rail` 补全。

---

## 三、覆盖率指标体系（三级）

### 第一级：全局指标（立即可算，文本报告）

#### C₁ — 全局最坏 IR Drop 捕获率

$$C_1 = \frac{V_{nom} - V_{min,sub}}{V_{nom} - V_{min,full}} = \frac{\text{IRdrop}_{sub,max}}{\text{IRdrop}_{full,max}}$$

- **数据来源**：`VDD.main.rpt` → M1 Min Voltage
- **参数**：V_nom = 0.700V

| 场景 | V_min | IRdrop | C₁ |
|------|-------|--------|----|
| 全集 | 0.667V | 0.033V | — (基准) |
| win1 | 0.673V | 0.027V | **81.8%** |
| win2 | 0.667V | 0.033V | **100.0%** |
| win1∪win2 | min(0.673, 0.667) = 0.667V | 0.033V | **100.0%** |

#### C_peak — 峰值电流捕获率

$$C_{peak} = \frac{I_{peak,sub}}{I_{peak,full}}$$

- **数据来源**：`VDD.main.rpt` 或 `VDD_dynpwr.rpt` → Peak Dynamic Current

| 场景 | I_peak | C_peak |
|------|--------|--------|
| 全集 | 16.486mA | — |
| win1 | 16.215mA | **98.4%** |
| win2 | 16.490mA | **100.0%** |
| win3 | 17.206mA | **104.4%** (超越全集) |

#### C_layer — 逐层 IR Drop 捕获率

$$C_{layer}(l) = \frac{\text{IRdrop}_{sub}(l)}{\text{IRdrop}_{full}(l)}, \quad l \in \{M1, M2, ..., M7\}$$

- **数据来源**：`VDD.layerbased_ir.rpt`
- 综合评分可取各层平均或取最小值：$C_{layer,avg} = \frac{1}{N}\sum_l C_{layer}(l)$

#### C_violation — 违例一致性

- **数据来源**：`VDD.main.rpt` → Violations
- 判定逻辑：若全集有违例，子集也能检出 → Pass；若全集无违例，子集也无违例 → Pass
- 当前全集和所有子集均为 0 violation → **全部 Pass**

---

### 第二级：空间分布指标（需解析 instpower 或在 Innovus 中导出）

#### C₂ — Hotspot 检出率 (Recall / Precision / F1)

$$\mathcal{H}_{full} = \{v \mid \text{IRdrop}_{full}(v) > \theta\}$$
$$C_2 = \frac{|\mathcal{H}_{sub} \cap \mathcal{H}_{full}|}{|\mathcal{H}_{full}|}$$

- **阈值** θ = V_nom × 7% = 0.049V（即 V_eff < 0.651V 为 hotspot）
- **数据获取方案**（二选一）：

| 方案 | 数据来源 | 难度 | 精度 |
|------|---------|------|------|
| **A: Innovus Tcl 导出** | `report_power_rail_results -instance_voltage` → CSV | 中 | 高（逐 instance） |
| **B: 解析 instpower.gz** | `VDD/VDD.instpower.gz` → 逐 instance 功耗 | 低 | 中（功耗代替电压） |

**推荐方案 A**：在 Innovus 中运行以下 Tcl 脚本，导出逐 instance 电压：

```tcl
# 在已加载 rail 分析结果的 Innovus session 中执行
# 对全集和每个子集分别运行
proc export_instance_voltage {output_csv} {
    set fout [open $output_csv w]
    puts $fout "instance,worst_voltage,avg_voltage"
    foreach inst [dbGet top.insts.name] {
        set wv [get_power_rail_results -instance $inst -type worst_voltage]
        set av [get_power_rail_results -instance $inst -type avg_voltage]
        puts $fout "$inst,$wv,$av"
    }
    close $fout
}

export_instance_voltage "instance_voltage_full.csv"
```

#### C₃ — 分位数捕获率

$$C_3 = \frac{Q_{99\%}(\text{IRdrop}_{sub})}{Q_{99\%}(\text{IRdrop}_{full})}$$

- **数据来源**：同 C₂，需要逐 instance/tile 的电压分布
- 取 99th percentile 对比，比最大值更鲁棒

---

### 第三级：辅助/定性指标

| 指标 | 数据来源 | 用途 |
|------|---------|------|
| GIF 热力图对比 | `ir_linear.gif`, `VDD_VSS.worst_eiv.gif` | 论文配图，直观对比空间分布 |
| 分布相似度 (Wasserstein) | 逐 instance 电压分布 | 量化分布偏移程度 |
| Toggle-IRDrop 相关性 | `voltus_power.togglestats` + IR Drop 结果 | 验证"高 toggle → 高 IR Drop"假设 |

---

## 四、计算方案分步实施

### Phase 1：第一级指标自动化计算（立即可做）

**目标**：编写 Python 脚本，自动解析文本报告，计算 C₁、C_peak、C_layer、C_violation

**输入文件**：
```
rail_power_v15/PD_25C_dynamic_1/Reports/VDD/VDD.main.rpt          # 全集
rail_power_v15_win{1,2}/.../ PD_25C_dynamic_2/Reports/VDD/VDD.main.rpt  # 子集
rail_power_v15{_win1,_win2,...}/.../ Reports/VDD/VDD.layerbased_ir.rpt   # 逐层
rail_power_v15{_win1,_win2,...}/.../ Reports/VDD/VDD_dynpwr.rpt          # 动态功耗
```

**脚本逻辑**：

```python
# coverage_tier1.py 伪代码
import re, os

def parse_main_rpt(filepath):
    """从 VDD.main.rpt 提取关键指标"""
    text = open(filepath).read()
    min_v = float(re.search(r'Minimum Voltage\s*:\s*([\d.]+)', text).group(1))
    max_v = float(re.search(r'Maximum Voltage\s*:\s*([\d.]+)', text).group(1))
    avg_v = float(re.search(r'Average Voltage\s*:\s*([\d.]+)', text).group(1))
    peak_i = float(re.search(r'Peak Dynamic.*?:\s*([\d.eE+-]+)', text).group(1))
    violations = int(re.search(r'Violations\s*:\s*(\d+)', text).group(1))
    return { 'min_v': min_v, 'max_v': max_v, 'avg_v': avg_v,
             'peak_i': peak_i, 'violations': violations }

def parse_layerbased_rpt(filepath):
    """从 VDD.layerbased_ir.rpt 提取逐层 IR Drop"""
    # 返回 dict: { 'M1': irdrop_value, 'M2': ..., ... }
    ...

def calc_coverage(full_data, sub_data, Vnom=0.700):
    """计算第一级覆盖率指标"""
    irdrop_full = Vnom - full_data['min_v']
    irdrop_sub  = Vnom - sub_data['min_v']

    C1 = irdrop_sub / irdrop_full if irdrop_full > 0 else 1.0
    C_peak = sub_data['peak_i'] / full_data['peak_i']
    C_violation = 'PASS' if (full_data['violations'] == 0 and sub_data['violations'] == 0) \
                         or (full_data['violations'] > 0 and sub_data['violations'] > 0) \
                  else 'FAIL'

    return { 'C1': C1, 'C_peak': C_peak, 'C_violation': C_violation }
```

**输出**：Markdown 表格 + CSV 文件，包含每个窗口和组合窗口的覆盖率。

---

### Phase 2：补全缺失报告（win3/win4/win5）

**目标**：对 win3~win5 补充生成 `VDD.main.rpt`

**方法**：在 Innovus 中加载对应的 rail 分析数据库，重新执行报告生成：

```tcl
# 对每个缺失窗口执行
read_power_rail_results -rail_directory rail_power_v15_winN/rail_power_v15_winN/PD_25C_dynamic_2/VDD

# 重新生成报告
report_rail -output_dir rail_power_v15_winN/.../Reports \
    -type all \
    -net VDD
```

或者直接在 `rerun_rail_v15.tcl` 脚本中添加对应窗口的报告生成步骤。

---

### Phase 3：第二级指标计算（Hotspot 覆盖率）

**目标**：计算 C₂ (Hotspot Recall/Precision/F1) 和 C₃ (分位数捕获率)

**步骤**：

1. **在 Innovus 中导出逐 instance 最坏电压**（使用 Phase 2 的 Tcl 脚本扩展）：
   ```tcl
   # export_inst_voltage.tcl
   # 对全集和每个子集分别运行
   set nets {VDD}
   foreach net $nets {
       read_power_rail_results -rail_directory <path>/VDD
       set fp [open "inst_voltage_<label>.csv" w]
       puts $fp "inst_name,worst_v,avg_v,x,y"
       foreach_in_collection inst [get_cells *] {
           set name [get_property $inst full_name]
           set wv   [get_property $inst worst_voltage]
           set av   [get_property $inst avg_voltage]
           set x    [get_property $inst origin_x]
           set y    [get_property $inst origin_y]
           puts $fp "$name,$wv,$av,$x,$y"
       }
       close $fp
   }
   ```

2. **Python 计算 C₂ 和 C₃**：
   ```python
   import pandas as pd
   import numpy as np

   Vnom = 0.700
   theta = Vnom * 0.07  # 0.049V, 对应 V_eff < 0.651V

   df_full = pd.read_csv("inst_voltage_full.csv")
   df_sub  = pd.read_csv("inst_voltage_win1.csv")

   df_full['irdrop'] = Vnom - df_full['worst_v']
   df_sub ['irdrop'] = Vnom - df_sub ['worst_v']

   # C2: Hotspot 检出率
   H_full = set(df_full[df_full['irdrop'] > theta]['inst_name'])
   H_sub  = set(df_sub [df_sub ['irdrop'] > theta]['inst_name'])

   recall    = len(H_sub & H_full) / len(H_full) if len(H_full) > 0 else 1.0
   precision = len(H_sub & H_full) / len(H_sub)  if len(H_sub)  > 0 else 1.0
   F1 = 2 * recall * precision / (recall + precision) if (recall + precision) > 0 else 0

   # C3: 分位数捕获率
   C3_99  = np.percentile(df_sub['irdrop'], 99)  / np.percentile(df_full['irdrop'], 99)
   C3_999 = np.percentile(df_sub['irdrop'], 99.9) / np.percentile(df_full['irdrop'], 99.9)
   ```

---

### Phase 4：多窗口组合分析

**目标**：评估不同窗口组合的联合覆盖率，找到最优子集

**方法**：对于 N 个窗口，枚举所有组合 $\binom{N}{k}$，k = 1, 2, ..., N：

```python
from itertools import combinations

windows = ['win1', 'win2', 'win3', 'win4', 'win5']
results = []

for k in range(1, len(windows) + 1):
    for combo in combinations(windows, k):
        # 联合子集 = 所有窗口的 union
        # 对于全局指标：取各窗口中的最坏值
        # 对于 Hotspot：取各窗口 hotspot 的并集
        combined_irdrop_max = max(sub_data[w]['irdrop_max'] for w in combo)
        combined_peak_i     = max(sub_data[w]['peak_i'] for w in combo)

        C1_combo = combined_irdrop_max / full_data['irdrop_max']
        results.append({
            'combination': '+'.join(combo),
            'num_windows': k,
            'C1': C1_combo,
            'C_peak': combined_peak_i / full_data['peak_i']
        })

# 找出达到 C1 >= 95% 的最小窗口数
df_results = pd.DataFrame(results)
sufficient = df_results[df_results['C1'] >= 0.95].sort_values('num_windows')
print("达到 95% 覆盖率的最小组合：")
print(sufficient.head())
```

---

## 五、预期输出

### 5.1 覆盖率汇总表（示例）

| 子集 | C₁ (最坏IR) | C_peak (峰值电流) | C_layer_avg (逐层均值) | C₂ Recall | C₂ F1 | C₃ (99th) |
|------|------------|-------------------|----------------------|-----------|--------|-----------|
| win1 | 81.8% | 98.4% | ~72% | TBD | TBD | TBD |
| win2 | 100.0% | 100.0% | ~95% | TBD | TBD | TBD |
| win3 | TBD | 104.4% | ~93% | TBD | TBD | TBD |
| win1+win2 | 100.0% | 100.0% | ~95% | TBD | TBD | TBD |
| win1+win2+win3 | 100.0% | 104.4% | TBD | TBD | TBD | TBD |

### 5.2 输出文件列表

| 文件 | 内容 |
|------|------|
| `coverage_tier1_results.csv` | 第一级指标（C₁, C_peak, C_layer, C_violation）|
| `coverage_tier2_results.csv` | 第二级指标（C₂, C₃）|
| `coverage_combination_analysis.csv` | 多窗口组合覆盖率 |
| `coverage_report.md` | 综合覆盖率分析报告（含图表）|
| `coverage_heatmap_comparison.png` | 全集 vs 子集 IR Drop 空间对比图 |

---

## 六、执行优先级与依赖关系

```
Phase 1 (立即)  ──→  Phase 4-部分 (仅用第一级指标做组合分析)
     │
     ▼
Phase 2 (需 Innovus)  ──→  Phase 3 (需 Innovus 导出)  ──→  Phase 4-完整
```

| Phase | 依赖 | 预估工作 |
|-------|------|---------|
| Phase 1 | 无，纯 Python 文本解析 | 编写 1 个 Python 脚本 |
| Phase 2 | 需要 Innovus license + 设计数据库 | 修改 Tcl 脚本，运行 Voltus |
| Phase 3 | 需要 Phase 2 完成 + Innovus 导出 CSV | 编写 Tcl 导出脚本 + Python 分析脚本 |
| Phase 4 | Phase 1 完成即可开始部分分析 | 扩展 Python 脚本 |

---

## 七、关键注意事项

1. **全集路径为 `PD_25C_dynamic_1`，子集路径为 `PD_25C_dynamic_2`**——这是 Voltus 的分析 ID 差异，不影响对比有效性，但脚本中需正确映射。

2. **win3 的 VDD.main.rpt 缺失**——其 `dynpwr.rpt` 显示峰值电流 17.206mA > 全集 16.486mA，说明 win3 可能捕获了全集中未聚焦的极端瞬态，具有重要分析价值，应优先补全其报告。

3. **多窗口"联合"的定义**：对于全局指标（C₁, C_peak），联合 = 取各窗口最坏值；对于空间指标（C₂），联合 = 取各窗口 hotspot 集合的并集，逐 instance 取最坏电压。

4. **阈值选择**：当前设计 VDD 阈值为 0.651V（7% margin），建议同时计算 5% 和 10% margin 下的 C₂，以展示灵敏度分析。

5. **C₁ > 100% 的情况**（如 win3 的 C_peak = 104.4%）：说明子集在该窗口中激发了比全集时序平均更极端的瞬态电流。这是合理的——全集的"最坏"是所有窗口中的最坏，而单窗口可能在局部时间段更极端。应按 min(C, 1.0) 截断或单独标注。
