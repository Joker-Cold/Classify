# Project Library — VCD 功耗压缩与 IR Drop 覆盖率验证

> 项目目标：基于信号翻转率和物理功耗模型，对 VCD 仿真波形进行时空功耗分析，筛选高风险窗口并压缩 VCD 文件体积，同时保证芯片 IR Drop 验证覆盖率。

---

## 全局目录结构

```
Classify/
├── Traditional_Vector_Profiling/    # ★ 传统向量分析（功耗矩阵生成）
│   ├── README.md
│   ├── code/
│   │   ├── traditional_select.py    ← 主脚本：功耗矩阵 [T][ny][mx] + 平均功耗 [T]
│   │   ├── parse_lib_power.py       ← .lib → cell 功率参数 JSON
│   │   ├── parse_spef.py            ← SPEF → net 电容 JSON
│   │   ├── vcd_to_jsonl.py          ← VCD → JSONL
│   │   ├── jsonl_toggle_mark.py     ← JSONL → Toggle JSONL
│   │   ├── parse_vcd_signal.py      ← VCD 解析核心库
│   │   └── unused/
│   │       └── vcd_splice.py        ← 备用：top-k 选窗 + VCD 拼接函数
│   ├── example_data/
│   └── sim_result/                  ← 中间产物（.gitignore）
│
├── coverage_analysis/               # ★ IR Drop 覆盖率分析
│   ├── README.md
│   ├── code/
│   │   ├── evaluate.py              ← 双维度覆盖率评估（C_int + C_k）
│   │   ├── extract_results.py       ← Voltus .iv 结果提取
│   │   ├── parse_iv.py              ← .iv 文件解析
│   │   └── visualize_hotspot.py     ← Plotly 热点可视化
│   ├── coverage_meth.md
│   └── result/                      ← 评估结果
│
├── vcd_def2html/                    # 空间-时间选窗一键流程（DEF→HTML 可视化）
│   ├── README.md
│   └── code/                        # 7 个脚本
│       ├── run_pipeline.py          ← 一键流水线：VCD+DEF → HTML+VCD+JSON
│       ├── spatial_temporal_select.py ← 空间-时间联合选窗 + VCD 拼接
│       ├── vcd_def_mapper.py        ← VCD 信号 → DEF 物理坐标
│       ├── vcd_validator.py         ← VCD 格式校验
│       ├── parse_vcd_signal.py
│       ├── vcd_to_jsonl.py
│       └── jsonl_toggle_mark.py
│
├── docs/                            # 算法文档 & 论文材料
│   ├── final_prj.md                 ← 毕业设计论文目录结构
│   ├── midterm_report.md            ← 中期报告
│   ├── work_have_done.md            ← 工作总结
│   ├── traditional_classify.md      ← 传统分类方法论
│   ├── risk_propagation_profiling.md ← 风险传播分析
│   ├── coverage_methodology.md      ← 覆盖率评估方法论
│   ├── paper_MAVIREC_summary.md     ← MAVIREC 研究总结
│   └── paper_Hu2025_VCD_summary.md  ← Hu2025 论文解读
│
├── des_demo/                        # EDA 后端实验项目（DES3 加密核）
│   ├── README.md
│   ├── rtl/                         # RTL 源码
│   ├── netlist/                     # Genus 综合网表
│   ├── sdc/                         # 时序约束
│   ├── testbench/                   # VCS Testbench
│   ├── vcd/                         # 仿真 VCD
│   ├── script/                      # EDA 脚本（Genus / Innovus / Voltus）
│   └── db/                          # EDA 数据库
│       ├── des3.{v,def,spef,enc}    # 后端物理设计文件
│       ├── des3.enc.dat/libs/mmmc/  # Liberty 工艺库
│       ├── power/                   # 功耗分析
│       ├── rail_power/              # IR Drop 分析
│       └── analyse/                 # 覆盖率分析脚本 & 结果
│
├── unused/                          # 归档（旧版算法，保留备用）
│   ├── vcd_power_toolkit/           # 旧主工具包（Phase-Aware + 覆盖率）
│   └── spatial_temporal/            # 旧空间-时间选窗精简包
│
├── .gitignore
└── prj_lib.md                       # 本文件
```

---

## 一、Traditional_Vector_Profiling/ — 传统向量分析（★ 当前主算法）

> 基于 Wen et al. ICCAD 2023，通过 Liberty 功率模型计算每个 tile 在每个时间窗口的功耗，输出功耗矩阵。

### 算法概要

```
输入：VCD + SPEF + Liberty .lib + DEF
时间分窗：固定 window_ns（默认 20 ns），T = ceil(总时间 / window_ns)
空间分块：M×N tile 网格（默认 50×50）
功率模型：P = P_sw + P_int + P_leak（每信号每窗口）
输出：power_matrix_mW [T][ny][mx] + avg_power_mW [T]
```

### 脚本说明

| 脚本 | 功能 |
|------|------|
| `traditional_select.py` | 主脚本：读取预处理数据 → 信号功率映射 → 功耗矩阵计算 → JSON 输出 |
| `parse_lib_power.py` | 解析 Liberty .lib → 每种 cell 的 leakage_pW + 7×7 energy LUT |
| `parse_spef.py` | 解析 SPEF → 每条 net 的总电容 (pF) |
| `vcd_to_jsonl.py` | VCD → 合并 JSONL（hold-last-value） |
| `jsonl_toggle_mark.py` | JSONL → Toggle JSONL（逐 bit XOR 翻转标记） |
| `parse_vcd_signal.py` | VCD 解析核心库（`VCDSignalParser` 类） |

### 功率模型

```
P_sw   = Σ_toggles × 0.5 × C_net_pF × V_DD² × 1e3 / window_ns  [mW]
P_int  = Σ_toggles × lookup_energy(cell, C_fF, slew_ps) / window_ns × 1e-3  [mW]
P_leak = leakage_pW × 1e-9  [mW]

power_matrix[t][iy][ix] = Σ_{inst ∈ tile(iy,ix)} (P_sw + P_int + P_leak)
avg_power[t] = mean(power_matrix[t])
```

### 信号映射链

```
VCD signal full_name
  → 去掉 testbench scope + design top（dot→slash）
  → SPEF 查电容 C_pF
  → DEF NETS 查 driver instance（输出引脚 Y/Q/QN/Z/ZN/CO/S/SN）
  → DEF COMPONENTS 查 cell_type + 物理坐标 (x_dbu, y_dbu)
  → Liberty LUT 查 energy_fJ + leakage_pW（线性插值）
  → 坐标 → tile (iy, ix) 映射
```

### 完整流程

```bash
cd Traditional_Vector_Profiling

# Step 1: VCD → Toggle JSONL
python code/vcd_to_jsonl.py input.vcd --output-dir sim_result/intermediate/
python code/jsonl_toggle_mark.py sim_result/intermediate/input.jsonl

# Step 2: 解析 Liberty 功率参数
python code/parse_lib_power.py --lib-dir mmmc/ --out sim_result/report/lib_power.json

# Step 3: 解析 SPEF 网络电容
python code/parse_spef.py --spef design.spef --out sim_result/report/net_cap.json

# Step 4: 生成功耗矩阵
python code/traditional_select.py \
    --toggles sim_result/intermediate/input_toggles.jsonl \
    --vcd input.vcd --lib-power sim_result/report/lib_power.json \
    --net-cap sim_result/report/net_cap.json --def design.def \
    --window-ns 20 --mx 50 --ny 50 \
    --json-out sim_result/report/report.json
```

### 参数说明

| 参数 | 默认 | 说明 |
|------|------|------|
| `--window-ns` | 20 | 时间窗口大小（ns） |
| `--mx` / `--ny` | 50 | tile 网格列数 / 行数 |
| `--vdd` | 0.7 | 电源电压 V |
| `--slew-ps` | 40 | LUT 查表固定 input slew（ps） |
| `--timescale-ps` | 10 | VCD timescale（ps） |

---

## 二、coverage_analysis/ — IR Drop 覆盖率分析

> 评估 VCD 压缩后的 Voltus 仿真结果相对原始全集的覆盖程度。

### 双维度覆盖率指标

| 指标 | 定义 | 含义 |
|------|------|------|
| **C_int** | V_comp_max / V_orig_max | 强度覆盖率：最差 IR Drop 是否被保留 |
| **C_k** | top-k 热点命中率 | 空间覆盖率：最热的 k 个位置是否仍在 top-k |

**通过标准**：C_int_min ≥ 95% AND C_k(1) ≥ 90%

### 脚本说明

| 脚本 | 功能 |
|------|------|
| `evaluate.py` | 主评估脚本：计算 C_int 和 C_k |
| `extract_results.py` | 从 Voltus .iv + DEF 提取可视化数据 |
| `parse_iv.py` | 解析 Voltus instance voltage (.iv) 文件 |
| `visualize_hotspot.py` | Plotly 热点可视化 HTML |

### 输入

两组 Voltus .iv 文件：原始全集仿真结果 vs 压缩后仿真结果。

---

## 三、vcd_def2html/ — 空间-时间选窗可视化

> 一键流水线：VCD + DEF → 空间-时间联合选窗 → HTML 交互可视化 + 压缩 VCD。

```
输入: VCD + DEF
  ↓ run_pipeline.py
  ├── VCD → JSONL → Toggle JSONL
  ├── DEF → 坐标映射
  ├── 空间-时间联合选窗（mx×ny 网格 × kt 窗口）
  └── 输出: HTML（5 面板 Plotly 可视化）+ 压缩 VCD + JSON 报告
```

---

## 四、des_demo/ — EDA 后端实验项目

### 设计概览

- **芯片**：Triple DES (3DES) 加密核，51 级流水线，100 MHz
- **工艺**：ASAP7 7nm PDK
- **标称电压**：0.7V

### 目录说明

| 目录 | 说明 |
|------|------|
| `rtl/` | RTL 源码（des3.v, des.v, crp.v, key_sel.v, sbox1~8.v） |
| `netlist/` | Genus 综合网表（des3_netlist.v，5.1MB） |
| `sdc/` | 时序约束（100 MHz，51 级多周期路径） |
| `testbench/` | VCS Testbench（10 组加密向量） |
| `vcd/` | 仿真 VCD（test.vcd, 42K+ 信号） |
| `script/` | EDA 脚本（Genus / Innovus / Voltus） |
| `db/des3.{def,spef,v}` | 后端物理设计文件（DEF 38.7MB, SPEF 33.9MB） |
| `db/des3.enc.dat/libs/mmmc/` | ASAP7 Liberty 工艺库 |
| `db/power/` | Voltus 功耗分析结果 |
| `db/rail_power/` | Voltus IR Drop 分析结果 |
| `db/analyse/` | 覆盖率分析脚本 & 结果 |

---

## 五、docs/ — 算法文档 & 论文材料

| 文件 | 说明 |
|------|------|
| `final_prj.md` | 毕业设计论文目录结构 |
| `midterm_report.md` | 中期报告 |
| `work_have_done.md` | 工作总结 |
| `traditional_classify.md` | 传统分类方法论 |
| `risk_propagation_profiling.md` | 风险传播分析 |
| `coverage_methodology.md` | PI 仿真覆盖率评估方法论 |
| `paper_MAVIREC_summary.md` | MAVIREC 研究总结 & 相关工作 |
| `paper_Hu2025_VCD_summary.md` | Hu2025 论文解读（TODAES 2025，ML 辅助 VCD） |

---

## 六、unused/ — 归档模块

旧版算法保留备用，不再活跃开发。

| 模块 | 说明 |
|------|------|
| `vcd_power_toolkit/` | 旧主工具包（Phase-Aware 选窗 + MAVIREC + 覆盖率分析，15 脚本） |
| `spatial_temporal/` | 旧空间-时间选窗精简包（6 脚本） |

> 注：旧版 RC_Tile_Worst_Window 及其验证目录已在之前的精简中移除/归档。

---

## 七、数据流总览

```
                ┌───────────────────────────────────────────────────────┐
                │       VCD Power Matrix & Coverage Analysis            │
                └───────────────────────────────────────────────────────┘

  ① 传统功耗矩阵生成（Traditional_Vector_Profiling/）
  ═══════════════════════════════════════════════════
  test.vcd ──→ vcd_to_jsonl ──→ jsonl_toggle_mark ──→ test_toggles.jsonl
                                                            │
  *.lib ──→ parse_lib_power ──→ lib_power.json ──┐          │
  *.spef ──→ parse_spef ──→ net_cap.json ────────┤          │
  *.def ─────────────────────────────────────────┘          │
                                                            ↓
                                                   traditional_select.py
                                                            │
                                                            ↓
                                                   report.json
                                                   ├── power_matrix_mW [T][ny][mx]
                                                   └── avg_power_mW [T]

  ② 覆盖率分析（coverage_analysis/）
  ════════════════════════════════════
  Voltus .iv（原始全集） + Voltus .iv（压缩后）
      │
      ├──→ evaluate.py     ──→ coverage.json（C_int, C_k）
      ├──→ extract_results ──→ ir_drop_map.csv + hotspot_top20.csv
      └──→ visualize_hotspot ──→ hotspot_visualization.html

  ③ 空间-时间可视化选窗（vcd_def2html/）
  ═══════════════════════════════════════
  test.vcd + des3.def
      │
      └──→ run_pipeline.py ──→ HTML 可视化 + 压缩 VCD + JSON 报告
```

---

## 八、快速命令参考

```bash
# ===== 传统功耗矩阵（在 Docker grj-dev 中执行） =====
cd Traditional_Vector_Profiling

docker exec grj-dev python /app/Classify/Traditional_Vector_Profiling/code/vcd_to_jsonl.py \
    /app/Classify/des_demo/vcd/test.vcd --output-dir /app/Classify/Traditional_Vector_Profiling/sim_result/intermediate/

docker exec grj-dev python /app/Classify/Traditional_Vector_Profiling/code/jsonl_toggle_mark.py \
    /app/Classify/Traditional_Vector_Profiling/sim_result/intermediate/test.jsonl

docker exec grj-dev python /app/Classify/Traditional_Vector_Profiling/code/parse_lib_power.py \
    --lib-dir /app/Classify/des_demo/db/des3.enc.dat/libs/mmmc/ \
    --out /app/Classify/Traditional_Vector_Profiling/sim_result/report/lib_power.json

docker exec grj-dev python /app/Classify/Traditional_Vector_Profiling/code/parse_spef.py \
    --spef /app/Classify/des_demo/db/des3.spef \
    --out /app/Classify/Traditional_Vector_Profiling/sim_result/report/net_cap.json

docker exec grj-dev python /app/Classify/Traditional_Vector_Profiling/code/traditional_select.py \
    --toggles /app/Classify/Traditional_Vector_Profiling/sim_result/intermediate/test_toggles.jsonl \
    --vcd /app/Classify/des_demo/vcd/test.vcd \
    --lib-power /app/Classify/Traditional_Vector_Profiling/sim_result/report/lib_power.json \
    --net-cap /app/Classify/Traditional_Vector_Profiling/sim_result/report/net_cap.json \
    --def /app/Classify/des_demo/db/des3.def \
    --window-ns 20 --mx 50 --ny 50 --timescale-ps 10 \
    --json-out /app/Classify/Traditional_Vector_Profiling/sim_result/report/report.json
```
