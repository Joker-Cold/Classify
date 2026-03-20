# Project Library — VCD Worst-Case Power Waveform Selection

> 项目目标：通过信号翻转率分析，从 VCD 仿真波形中筛选最恶劣功耗窗口，压缩 VCD 文件体积，同时不影响芯片功耗验证（IR Drop）的有效性。

---

## 全局目录结构

```
Classify/
├── vcd_power_toolkit/             # ★ 主工具包（完整发布版）
│   ├── README.md                  # 使用指南 & 完整工作流
│   ├── requirements.txt           # pip 依赖 (plotly)
│   ├── code/                      # 全部 14 个 Python 脚本
│   │   ├── parse_vcd_signal.py    # VCD 解析核心库
│   │   ├── vcd_to_jsonl.py        # VCD → JSONL 转换
│   │   ├── jsonl_bit_diff.py      # 逐 bit 有符号差分
│   │   ├── jsonl_toggle_mark.py   # 逐 bit 翻转标记（XOR）
│   │   ├── diff_to_html.py        # 差分热力图可视化
│   │   ├── toggles_to_html.py     # 翻转率热力图可视化
│   │   ├── toggle_heatmap.py      # 时空 toggle 热力图
│   │   ├── select_worst_window.py # Phase-Aware 选窗核心算法（库）
│   │   ├── find_worst_window.py   # 选窗 CLI（调用 select_worst_window）
│   │   ├── vcd_slicer.py          # VCD 时间窗口切割
│   │   ├── vcd_validator.py       # VCD 格式校验
│   │   ├── vcd_def_mapper.py      # VCD 信号 → DEF 物理坐标
│   │   ├── spatial_temporal_select.py # 空间-时间联合选窗
│   │   └── coverage_tier1.py      # ★ Voltus IR Drop 覆盖率分析
│   ├── docs/                      # 算法文档
│   │   ├── algorithm_worst_window.md  # MAVIREC 算法伪代码
│   │   └── spatial_temporal_guide.md  # 空间-时间选窗参数指南
│   └── example_output/            # 示例输出
│       ├── algo_win1_visualization.{html,json}
│       ├── coverage_report_v20.md
│       └── coverage_tier1_v20.csv
│
├── spatial_temporal/              # 空间-时间选窗精简包
│   ├── README.md
│   ├── code/                      # 6 个脚本子集
│   │   ├── parse_vcd_signal.py
│   │   ├── vcd_to_jsonl.py
│   │   ├── jsonl_toggle_mark.py
│   │   ├── vcd_def_mapper.py
│   │   ├── vcd_validator.py
│   │   └── spatial_temporal_select.py
│   └── example_data/              # 示例数据
│
├── vcd_def2html/                  # 旧版 DEF→HTML 流程（遗留）
│   ├── README.md
│   └── code/                      # 含 run_pipeline.py 等 7 个脚本
│
├── docs/                          # 顶层算法文档
│   ├── algorithm_worst_window.md  # MAVIREC 算法论文级伪代码
│   ├── algorithm_worst_window.html
│   └── paper_MAVIREC_summary.md   # 研究总结 & 相关工作
│
├── code/                          # [已清空] 原开发目录，代码已移入 toolkit
│
├── des_demo/                      # EDA 后端实验项目（DES3 加密核）
│   ├── README.md
│   ├── rtl/                       # RTL 源码（Verilog）
│   ├── netlist/                   # Genus 综合后网表
│   ├── sdc/                       # 时序约束
│   ├── testbench/                 # VCS 仿真 Testbench（含 2x 版本）
│   ├── vcd/                       # 仿真 VCD（含算法选窗切片）
│   ├── script/                    # EDA 脚本（Genus / Innovus / Voltus）
│   └── db/                        # EDA 数据库 & 分析结果
│       ├── des3.{v,def,spef,enc}  # 后端物理设计文件
│       ├── power/                 # 功耗分析（avg / per-window）
│       ├── rail_power/            # IR Drop 分析（v15 完整版）
│       ├── sim_data/              # ★ v20 Voltus 仿真数据（完整版）
│       │   ├── power_v20_{full,win1~5}/   # 功耗（等分5窗+全集）
│       │   ├── rail_v20_{full,win1~5}/    # IR Drop（等分5窗+全集）
│       │   └── algo_grid_win{1,2}/        # 算法选窗 IR Drop
│       └── analyse/               # ★ 覆盖率分析脚本 & 结果
│
├── output/                        # 生成输出（.gitignore 管理）
├── .gitignore
└── prj_lib.md                     # 本文件
```

**已删除**（2026-03-19 精简）：
- `code/*.py` — 全部迁移至 `vcd_power_toolkit/code/`
- `data/` — 测试 VCD 已整合至 `des_demo/vcd/`
- `skills/` & `skills.md` — 技能文档库（不再维护）

---

## 一、vcd_power_toolkit/ — 主工具包

> 所有活跃代码的 single source of truth，完整工作流见 `vcd_power_toolkit/README.md`

### 脚本依赖关系

```
parse_vcd_signal.py (核心 VCD 解析器)
    ↑ import
    ├── vcd_to_jsonl.py
    ├── vcd_slicer.py
    └── vcd_def_mapper.py

select_worst_window.py (选窗算法库)
    ↑ import
    └── find_worst_window.py
```

### 1.1 parse_vcd_signal.py（核心库，~358 行）

**类 `VCDSignalParser`：**
- `parse_header()` — 解析 VCD 头部（scope / variable / timescale）
- `list_unique_signals(exclude_params, exclude_tasks)` — 每个 VCD 符号一条记录，去重 + 过滤
- `parse_all_waveforms(exclude_params, exclude_tasks)` — 单遍扫描提取全部信号波形
- `extract_waveform(signal_name, start, end)` — 单信号时间窗提取

**多 scope 支持**：scope_type 跟踪、in_task 标志、同名信号自动消歧。

### 1.2 JSONL 分析链

| 脚本 | 行数 | 功能 |
|------|------|------|
| `vcd_to_jsonl.py` | ~94 | VCD → 合并 JSONL（hold-last-value） |
| `jsonl_bit_diff.py` | ~111 | 相邻时间点逐 bit 有符号差分（+1/-1/0） |
| `jsonl_toggle_mark.py` | ~113 | XOR 翻转标记（1=翻转，0=未变） |
| `diff_to_html.py` | ~177 | Plotly 差分热力图（红=上升沿，蓝=下降沿） |
| `toggles_to_html.py` | ~167 | Plotly 翻转率热力图 |
| `toggle_heatmap.py` | ~276 | 时空 toggle 热力图（独立可视化） |

### 1.3 select_worst_window.py（Phase-Aware 选窗算法，~554 行）

**核心函数**：
- `aggregate_by_clock(data, clock_ns)` — 按时钟周期聚合 toggle 统计
- `detect_phases(cycles, threshold)` — 检测连续高活跃相位
- `select_windows(phases, budget, depletion_ratio)` — 基于退耦耗尽估计选窗
- `generate_html()` — 可视化输出

**支持两种输入**：Voltus togglestats 文件 / JSONL toggle 文件

### 1.4 find_worst_window.py（选窗 CLI，~480 行）

Phase-Aware + 空间集中度选窗，两种空间模式：
- **Grid 模式**（`--vcd` + `--def`）：DEF 坐标 → NxN 网格（默认 8x8）
- **Scope 模式**（仅 `--vcd`）：VCD scope 层次结构

集中度公式：`σ = max(group_toggle)/total`，`effective = total × (1+α×σ)`

**关键**：空间评分不用于 Phase 检测，仅用于窗口排序。

### 1.5 VCD 辅助工具

| 脚本 | 行数 | 功能 |
|------|------|------|
| `vcd_slicer.py` | ~258 | VCD 时间窗口切割 |
| `vcd_validator.py` | ~145 | IEEE 1364 VCD 合规校验 |
| `vcd_def_mapper.py` | ~484 | VCD 信号 → DEF 物理坐标映射 |
| `spatial_temporal_select.py` | ~1004 | 空间-时间联合选窗 + 可视化 |

### 1.6 coverage_tier1.py（★ 覆盖率分析，~660 行）

自动解析 Voltus Rail Analysis 报告，计算子集相对全集的覆盖率。

**指标定义**：
- **C₁** = (Vnom - Vmin_sub) / (Vnom - Vmin_full) — IR Drop 覆盖率
- **C_peak** = Ipeak_sub / Ipeak_full — 峰值电流覆盖率
- **C_layer(l)** = IRdrop_sub(l) / IRdrop_full(l) — 逐层 IR Drop 覆盖率
- **C_layer_avg / C_layer_min** — 各层均值 / 最小值
- **C_violation** — 违规一致性（PASS/FAIL）

**数据结构**：`MainRptData`（main.rpt）, `LayerIR`（layerbased_ir.rpt）, `DynPwrData`（dynpwr.rpt）, `WindowData`

**输入报告**（Voltus 生成）：
| 报告文件 | 提取信息 |
|----------|----------|
| `VDD.main.rpt` | Vnom, Vmin, Ipeak, Violations |
| `VDD.layerbased_ir.rpt` | 逐层 IR Drop（M1~M7, LISD） |
| `VDD_dynpwr.rpt` | 动态峰值电流 |

---

## 二、des_demo/ — EDA 后端实验项目

### 设计概览
- **芯片**：Triple DES (3DES) 加密核，51 级流水线，100 MHz
- **工艺**：ASAP7 7nm PDK
- **标称电压**：0.7V，最差 IR Drop 0.026V（Vmin = 0.674V，v20 基线）

### 2.1 RTL & 综合

| 文件 | 功能 |
|------|------|
| `rtl/des3.v` | 顶层 3DES 模块 |
| `rtl/des.v` | 单级 DES 核心 |
| `rtl/crp.v` | 密钥旋转 / 处理 |
| `rtl/key_sel.v` | 密钥选择逻辑 |
| `rtl/sbox1~8.v` | S-Box 查找表 × 8 |
| `netlist/des3_netlist.v` | Genus 综合网表（5.1MB，~94K 行） |
| `sdc/des3.sdc` | 100 MHz 时钟，51 级多周期路径 |

### 2.2 VCD 向量仿真

**Testbench**：
| 文件 | 说明 |
|------|------|
| `testbench/des3_test_po_vcd.v` | VCS Testbench（10 组加密测试向量，VCD dump） |
| `testbench/des3_test_po_vcd_2x.v` | 2x 版本 Testbench |

**仿真 VCD 文件**（`vcd/` 目录）：
| 文件 | 说明 |
|------|------|
| `test.vcd` | 完整仿真 VCD（5.8MB，42K+ 信号） |
| `test_2x.vcd` | 2x 变体 VCD |
| `test_selected.vcd` | 手动选窗 VCD |
| `test_win1_algo.vcd` | 算法选窗 1（3790~4390ns，600ns） |
| `test_win2_algo.vcd` | 算法选窗 2（9600~10100ns，500ns） |
| `vcs.sh` | VCS 编译执行脚本 |

**仿真流程**：
```
RTL + Testbench → VCS 编译 → 仿真运行 → VCD dump
  ↓                                        ↓
netlist (Genus)                      test.vcd (42K+ signals)
```

### 2.3 EDA 工具脚本

| 路径 | 工具 | 功能 |
|------|------|------|
| `script/genus/genus.tcl` | Genus | 综合流程 |
| `script/innovus/innovus.tcl` | Innovus | P&R（布局、电源网格、引脚） |
| `script/innovus/load_design_v15.tcl` | Innovus | v15 设计加载 |
| `script/innovus/full_irdrop_v15.tcl` | Voltus | v15 完整 IR Drop 分析 |
| `script/innovus/rerun_rail_v15.tcl` | Voltus | v15 Rail 分析重跑 |
| `script/innovus/irdrop_algo_windows.tcl` | Voltus | ★ 算法选窗 IR Drop 分析（v20） |
| `script/innovus/power_analyze.tcl` | Voltus | 功耗分析设置 |
| `script/innovus/rail_analyze.tcl` | Voltus | Rail 分析设置 |

### 2.4 物理设计文件（`db/`）

| 文件 | 大小 | 说明 |
|------|------|------|
| `des3.def` | 38.7MB | 布局 DEF（914K 行） |
| `des3.spef` | 33.9MB | 寄生参数 |
| `des3.v` | 6.3MB | 后端网表 |
| `des3.enc` | — | Innovus 加密设计 |

### 2.5 Voltus 仿真数据（★ `db/sim_data/`，v20 完整版）

v20 Voltus 动态分析结果，含全 VCD + 等分5窗 + 算法选窗：

| 子目录 | 说明 | 窗口范围 |
|--------|------|----------|
| `power_v20_full/` | 全 VCD 功耗 | 0~11850ns |
| `power_v20_win{1~5}/` | 等分窗口功耗 | 每窗 2370ns |
| `rail_v20_full/` | 全 VCD IR Drop（基线） | 0~11850ns |
| `rail_v20_win{1~5}/` | 等分窗口 IR Drop | 每窗 2370ns |
| `algo_grid_win1/` | 算法选窗 1 IR Drop | 3790~4390ns |
| `algo_grid_win2/` | 算法选窗 2 IR Drop | 9600~10100ns |

### 2.6 覆盖率分析（★ `db/analyse/`）

| 文件 | 说明 |
|------|------|
| `coverage_tier1.py` | Phase 1 覆盖率计算脚本（~550 行，与 toolkit 版本独立） |
| `continue_task.md` | Phase 2 续接任务 & 待解决问题 |
| `v20_rail_analysis_summary.md` | v20 Rail 分析结果总结 |

**输出**（`results/` 目录）：
| 文件 | 说明 |
|------|------|
| `coverage_tier1_v20.csv` | v20 单窗口覆盖率 |
| `coverage_combination_v20.csv` | v20 多窗口组合覆盖率 |
| `coverage_report_v20.md` | ★ v20 覆盖率完整报告 |
| `coverage_tier1.csv` | v15 单窗口覆盖率 |
| `coverage_combination.csv` | v15 组合覆盖率 |
| `coverage_report.md` | v15 覆盖率报告 |
| `window_selection.{html,json}` | 选窗可视化 |

**v20 覆盖率结果**（基线：Vnom=0.7V, Vmin=0.674V, IR Drop=26mV）：

| 窗口 | C₁ | C_layer_avg | C_layer_min | C_violation |
|------|-----|-------------|-------------|-------------|
| eq_win1 | 92.3% | 75.9% | 56.6% | PASS |
| eq_win2 | 100% | 102.7% | 100% | PASS |
| eq_win3 | 84.6% | 80.9% | 79.9% | PASS |
| eq_win4 | 96.2% | 87.3% | 76.3% | PASS |
| eq_win5 | 96.2% | 98.6% | 95.7% | PASS |
| **algo_win1** | **100%** | **103.5%** | **100%** | **PASS** |
| **algo_win2** | **100%** | **103.5%** | **100%** | **PASS** |

> 算法选窗（algo_win1/2）以不到全 VCD 10% 的时长达到 100% 的 IR Drop 覆盖率。

**组合覆盖**：
- `algo_win1 + algo_win2`：C₁=100%, C_layer_min=100%
- `eq_win2 + eq_win4`：C₁=100%, C_layer_min=100%

### 2.7 框架文档

| 文件 | 说明 |
|------|------|
| `db/irdrop_coverage_framework.md` | 三级覆盖率指标体系（C₁/C₂/C₃） |
| `db/coverage_calculation_plan.md` | 四阶段实施计划 |
| `db/coverage_analysis_guide.md` | 可用数据目录 & 分析优先级 |

---

## 三、docs/ — 算法文档

| 文件 | 说明 |
|------|------|
| `algorithm_worst_window.md` | MAVIREC 算法论文级伪代码 + Mermaid 流程图 |
| `algorithm_worst_window.html` | HTML 渲染版 |
| `paper_MAVIREC_summary.md` | 研究总结 & 相关工作 |

---

## 四、辅助模块

### 4.1 spatial_temporal/（空间-时间选窗精简包）

仅含空间-时间联合选窗所需的最小脚本集（6 个），附带 README 和示例数据。适合独立部署。

### 4.2 vcd_def2html/（遗留）

旧版 VCD→DEF→HTML 流程，含 `run_pipeline.py`。功能已被 `vcd_power_toolkit` 替代。

---

## 五、数据流总览

```
               ┌─────────────────────────────────────────────────┐
               │            VCD Power Analysis Toolkit           │
               └─────────────────────────────────────────────────┘

  ① JSONL 分析链
  ═══════════════
  test.vcd
      │
      ├──→ vcd_to_jsonl      ──→ test.jsonl
      ├──→ jsonl_bit_diff    ──→ *_diff.jsonl     ──→ diff_to_html    ──→ diff.html
      └──→ jsonl_toggle_mark ──→ *_toggles.jsonl  ──→ toggles_to_html ──→ toggles.html

  ② 选窗 & 切割
  ═══════════════
  *_toggles.jsonl + (可选 test.vcd + des3.def)
      │
      ├──→ find_worst_window ──→ 窗口排序报告 + 可视化 HTML
      └──→ vcd_slicer        ──→ test_win1_algo.vcd / test_win2_algo.vcd

  ③ EDA 验证（Voltus）
  ═══════════════════
  test_win{1,2}_algo.vcd + des3.{v,def,spef}
      │
      ├──→ [Voltus] 功耗分析   ──→ power_v20_*/
      ├──→ [Voltus] IR Drop    ──→ rail_v20_* / algo_grid_win*/
      └──→ coverage_tier1.py   ──→ coverage_report_v20.md (覆盖率验证)
```

---

## 六、快速命令参考

```bash
# 进入工具包
cd vcd_power_toolkit/code

# JSONL 分析链
python vcd_to_jsonl.py <path>/test.vcd
python jsonl_toggle_mark.py output/test.jsonl
python toggles_to_html.py output/test_toggles.jsonl

# Phase-Aware 选窗
python find_worst_window.py output/test_toggles.jsonl --window-ns 1185

# 空间集中度选窗（Grid 模式）
python find_worst_window.py output/test_toggles.jsonl --window-ns 1185 \
    --vcd ../des_demo/vcd/test.vcd --def ../des_demo/db/des3.def

# VCD 切割
python vcd_slicer.py ../des_demo/vcd/test.vcd --start 3790 --end 4390

# VCD 校验
python vcd_validator.py output/sliced.vcd --ref ../des_demo/vcd/test.vcd

# 覆盖率分析
python coverage_tier1.py --db-root ../des_demo/db
```
