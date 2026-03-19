# Project Library — VCD Worst-Case Power Waveform Selection

> 项目目标：通过信号翻转率分析，从 VCD 仿真波形中筛选最恶劣功耗窗口，压缩 VCD 文件体积，同时不影响芯片功耗验证（IR Drop）的有效性。

---

## 全局目录结构

```
Classify/
├── code/                       # Python 源码（核心工具）
│   ├── parse_vcd_signal.py     # VCD 解析器（核心库）
│   ├── vcd_to_jsonl.py         # VCD → JSONL 转换
│   ├── jsonl_bit_diff.py       # 逐 bit 有符号差分
│   ├── jsonl_toggle_mark.py    # 逐 bit 翻转标记（XOR）
│   ├── diff_to_html.py         # 差分热力图可视化（Plotly）
│   ├── toggles_to_html.py      # 翻转率热力图可视化（Plotly）
│   ├── vcd_validator.py        # VCD 格式合规校验
│   └── mhtml_to_md.py          # Claude 聊天 MHTML → Markdown
│
├── data/                       # 输入数据（VCD 源文件）
│   ├── sim_output.vcd          # 主测试 VCD（124 信号，嵌套 scope）
│   └── random_test.vcd         # 小型测试 VCD（4 信号，单 scope）
│
├── output/                     # 输出（.gitignore 管理）
│   ├── sim_output.jsonl        # vcd_to_jsonl 输出
│   ├── *.html                  # 可视化 HTML
│   └── des_demo_summary.md     # DES3 设计全流程总结
│
├── des_demo/                   # EDA 后端实验项目（DES3 加密核）
│   ├── README.md               # 项目说明
│   ├── rtl/                    # RTL 源码（Verilog）
│   ├── netlist/                # Genus 综合后网表
│   ├── sdc/                    # 时序约束
│   ├── testbench/              # VCS 仿真 Testbench
│   ├── vcd/                    # 仿真 VCD + VCS 编译产物
│   ├── script/                 # EDA 脚本（Genus / Innovus / Voltus）
│   └── db/                     # EDA 数据库 & 分析结果
│       ├── des3.v / .def / .spef / .enc   # 后端物理设计文件
│       ├── power/              # 功耗分析结果（avg / per-window）
│       ├── rail_power/         # IR Drop 分析（v15 完整版）
│       ├── rail_power_v15/     # IR Drop 分析（v15 分窗版）
│       ├── analyse/            # 覆盖率分析脚本 & 结果
│       └── *.md                # 分析框架文档
│
├── skills/                     # 技能文档库
│   ├── vcd_format.md           # VCD 格式合规检查清单
│   ├── parse_vcd_signal.md     # 信号解析算法说明
│   ├── compare_vcd_waveform.md # VCD 波形回归对比
│   └── VMware_SSH_Setup_Log.md # SSH 远程 EDA 环境配置
│
├── skills.md                   # 技能索引 + Self-Check Protocol
├── temp/                       # 临时文件（工作总结等）
├── .gitignore                  # Git 忽略规则
└── prj_lib.md                  # 本文件
```

---

## 一、code/ — Python 源码

### 1.1 parse_vcd_signal.py（核心库）
| 属性 | 值 |
|------|-----|
| 行数 | ~360 |
| 角色 | VCD 解析器，全项目的基础依赖 |

**类 `VCDSignalParser`：**
- `parse_header()` — 解析 VCD 头部（scope / variable / timescale）
- `list_unique_signals(exclude_params, exclude_tasks)` — 每个 VCD 符号一条记录，去重 + 过滤
- `parse_all_waveforms(exclude_params, exclude_tasks)` — 单遍扫描提取全部信号波形
- `extract_waveform(signal_name, start, end)` — 单信号时间窗提取

**多 scope 支持**：scope_type 跟踪、in_task 标志、同名信号自动消歧。

**CLI**：
```bash
python parse_vcd_signal.py <vcd> [signal] [--list] [--start T] [--end T]
```

---

### 1.2 vcd_to_jsonl.py（VCD → JSONL）
| 属性 | 值 |
|------|-----|
| 行数 | ~94 |
| 角色 | 将 VCD 转为合并 JSONL 格式（每行一个时间点） |

- 实现 "hold-last-value" 语义，每个时间点输出所有信号的完整状态
- 输出：`{"time": 0, "signals": {"sig1": "0", "sig2": "1"}}`

```bash
python vcd_to_jsonl.py data/sim_output.vcd [--output-dir output/]
```

---

### 1.3 jsonl_bit_diff.py（逐 bit 差分）
| 属性 | 值 |
|------|-----|
| 行数 | ~111 |
| 角色 | 计算相邻时间点的逐 bit 有符号差分（+1 / -1 / 0） |

- 输出：`{"time": 100, "signals": {"sig1": [1, -1], "sig2": [0]}}`
- 用途：标记上升沿（+1）和下降沿（-1）

```bash
python jsonl_bit_diff.py output/sim_output.jsonl [-o output/diff.jsonl]
```

---

### 1.4 jsonl_toggle_mark.py（逐 bit 翻转标记）
| 属性 | 值 |
|------|-----|
| 行数 | ~113 |
| 角色 | XOR 标记每个 bit 是否发生翻转 |

- 输出：`{"time": 100, "signals": {"sig1": "10", "sig2": "1"}}`（1 = 翻转，0 = 未变）

```bash
python jsonl_toggle_mark.py output/sim_output.jsonl [-o output/toggles.jsonl]
```

---

### 1.5 diff_to_html.py（差分热力图）
| 属性 | 值 |
|------|-----|
| 行数 | ~177 |
| 角色 | 将 bit-diff JSONL 可视化为 Plotly 交互热力图 |

- 上方：逐信号热力图（红 = 上升沿，蓝 = 下降沿）
- 下方：每时间点总上升/下降 bit 堆叠柱状图

```bash
python diff_to_html.py output/diff.jsonl [-o output/diff.html]
```

---

### 1.6 toggles_to_html.py（翻转率热力图）
| 属性 | 值 |
|------|-----|
| 行数 | ~167 |
| 角色 | 将 toggle-mark JSONL 可视化为翻转率热力图 |

- 上方：逐信号翻转率热力图（YlOrRd 色阶，0.0 ~ 1.0）
- 下方：每时间点总翻转 bit 数柱状图

```bash
python toggles_to_html.py output/toggles.jsonl [-o output/toggles.html]
```

---

### 1.7 vcd_validator.py（VCD 校验器）
| 属性 | 值 |
|------|-----|
| 行数 | ~145 |
| 角色 | 校验 VCD 文件是否符合 IEEE 1364 标准 |

- 检查项：头部结构、变量定义、符号唯一性、值变化格式、时间单调性
- 支持与参考 VCD 的结构对比

```bash
python vcd_validator.py <file.vcd> [--ref reference.vcd]
```

---

### 1.8 mhtml_to_md.py（辅助工具）
| 属性 | 值 |
|------|-----|
| 行数 | ~291 |
| 角色 | 从 Claude.ai 导出的 MHTML 聊天记录提取为 Markdown |

```bash
python mhtml_to_md.py data/chat.mhtml [-o output/chat.md]
```

---

## 二、data/ — 输入数据

| 文件 | 说明 |
|------|------|
| `sim_output.vcd` | 主测试 VCD，124 信号，嵌套 scope（tb_top → u_soc → 子模块） |
| `random_test.vcd` | 小型测试 VCD，4 信号，单 scope，用于快速验证 |

---

## 三、output/ — 输出

| 路径 | 生成者 | 说明 |
|------|--------|------|
| `sim_output.jsonl` | vcd_to_jsonl | 合并 JSONL |
| `*.html` | 各可视化脚本 | 交互 HTML 图表 |
| `des_demo_summary.md` | 文档 | DES3 设计全流程总结 |

---

## 四、des_demo/ — EDA 后端实验项目

### 设计概览
- **芯片**：Triple DES (3DES) 加密核，51 级流水线，100 MHz
- **工艺**：ASAP7 7nm PDK
- **标称电压**：0.7V，最差 IR Drop 0.033V（Vmin = 0.667V）

### 4.1 rtl/ — RTL 源码
| 文件 | 功能 |
|------|------|
| `des3.v` | 顶层 3DES 模块 |
| `des.v` | 单级 DES 核心 |
| `crp.v` | 密钥旋转 / 处理 |
| `key_sel.v` | 密钥选择逻辑（39KB，最大文件） |
| `sbox1~8.v` | S-Box 查找表（8 个文件） |

### 4.2 netlist/ — 综合网表
- `des3_netlist.v` — Genus 生成的门级网表（5.1MB，~94K 行）

### 4.3 sdc/ — 时序约束
- `des3.sdc` — 100 MHz 时钟，51 级多周期路径约束

### 4.4 testbench/ — 仿真
- `des3_test_po_vcd.v` — VCS Testbench（10 组测试向量，时钟生成，VCD 输出）

### 4.5 vcd/ — 仿真波形
- `test.vcd` — 完整仿真 VCD（5.8MB）
- `vcs.sh` — VCS 执行脚本

### 4.6 script/ — EDA 工具脚本

| 路径 | 工具 | 功能 |
|------|------|------|
| `script/genus/genus.tcl` | Genus | 综合流程脚本 |
| `script/innovus/innovus.tcl` | Innovus | P&R 流程（布局、电源网格、引脚） |
| `script/innovus/full_irdrop_v15.tcl` | Voltus | 完整 IR Drop 分析流程（v15） |
| `script/innovus/load_design_v15.tcl` | Innovus | 设计加载（v15） |
| `script/innovus/rerun_rail_v20.tcl` | Innovus | v20 IR Drop 重跑（失败，待调试） |
| `script/innovus/power_analyze.tcl` | Voltus | 功耗分析设置 |
| `script/innovus/rail_analyze.tcl` | Voltus | Rail 分析设置 |

### 4.7 db/ — EDA 数据库

#### 物理设计文件
| 文件 | 大小 | 说明 |
|------|------|------|
| `des3.def` | 38.7MB | 布局 DEF |
| `des3.spef` | 33.9MB | 寄生参数 |
| `des3.v` | 6.3MB | 后端网表 |
| `des3.enc` | — | Innovus 加密设计文件 |
| `des3.enc.dat/` | — | PDK / 库文件 |

#### power/ — 功耗分析
| 子目录 | 说明 |
|--------|------|
| `avg/` | 原始全 VCD 功耗分析 |
| `avg_v15/` | v15 全 VCD 功耗分析 |
| `avg_v15_win1~5/` | 分窗功耗（每窗 2370ns） |

#### rail_power/ & rail_power_v15/ — IR Drop 分析

**关键报告文件**（`Reports/VDD/` 下）：
| 报告 | 内容 |
|------|------|
| `VDD.main.rpt` | 全局摘要：Vmin、IR Drop、Ipeak、Violations |
| `VDD.layerbased_ir.rpt` | 逐层 IR Drop（M1 ~ M7） |
| `VDD_dynpwr.rpt` | 动态峰值电流 |
| `VDD.pgv_table.rpt` | 标准单元利用率 |
| `EIVDB/*.blob` | 二进制电压分布数据 |

**分窗数据完整性**：
| 窗口 | main.rpt | layerbased_ir.rpt | dynpwr.rpt | 状态 |
|------|:---:|:---:|:---:|------|
| Full (v15) | ✅ | ✅ | ✅ | 完整 |
| win1 | ✅ | ✅ | ✅ | 完整 |
| win2 | ✅ | ✅ | ✅ | 完整 |
| win3 | ❌ | ✅ | ✅ | 缺 main.rpt |
| win4, win5 | ❌ | ❌ | ❌ | 仅 pgv_table.rpt |

#### analyse/ — 覆盖率分析
| 文件 | 说明 |
|------|------|
| `coverage_tier1.py` | Phase 1 覆盖率计算脚本（~550 行） |
| `results/coverage_tier1.csv` | 单窗口覆盖率指标 |
| `results/coverage_combination.csv` | 多窗口组合覆盖率 |
| `results/coverage_report.md` | Markdown 格式报告 |
| `continue_task.md` | Phase 2 续接任务 & 待解决问题 |

**覆盖率指标**：
- **C₁** = (Vnom - Vmin_sub) / (Vnom - Vmin_full) — IR Drop 覆盖率
- **C_peak** = Ipeak_sub / Ipeak_full — 峰值电流覆盖率
- **C_layer** = IRdrop_sub(l) / IRdrop_full(l) — 逐层覆盖率
- **C_violation** = 违规一致性 PASS/FAIL

**当前结果**：
| 窗口 | C₁ | C_peak | C_layer_min |
|------|-----|--------|------------|
| win1 | 81.8% | 98.4% | 45.8% |
| win2 | 100% | 100% | 94.2% |
| win1+win2 | 100% | 100% | 94.2% |

#### 框架文档（db/ 下）
| 文件 | 说明 |
|------|------|
| `coverage_analysis_guide.md` | 可用数据目录 & 分析优先级 |
| `irdrop_coverage_framework.md` | 三级覆盖率指标体系（C₁/C₂/C₃） |
| `coverage_calculation_plan.md` | 四阶段实施计划 |

---

## 五、skills/ — 技能文档

| 文件 | 用途 |
|------|------|
| `vcd_format.md` | VCD IEEE 1364 格式 8 项合规清单 |
| `parse_vcd_signal.md` | 信号提取算法：符号表 → 波形映射 |
| `compare_vcd_waveform.md` | 双 VCD 回归对比（PASS/FAIL + mismatch 表） |
| `VMware_SSH_Setup_Log.md` | SSH 远程 EDA 环境配置记录 |

---

## 六、数据流总览

```
                    JSONL 分析流水线
                    ═══════════════
  sim_output.vcd
       │
       ├──→ vcd_to_jsonl      ──→ sim_output.jsonl
       ├──→ jsonl_bit_diff    ──→ *_diff.jsonl     ──→ diff_to_html    ──→ diff.html
       └──→ jsonl_toggle_mark ──→ *_toggles.jsonl  ──→ toggles_to_html ──→ toggles.html

                    EDA 验证流程
                    ═══════════
  des_demo/vcd/test.vcd
       │
       ├──→ [Voltus] 全 VCD 功耗 + IR Drop ──→ rail_power_v15/ (基线)
       ├──→ [Voltus] 分窗功耗 + IR Drop     ──→ avg_v15_win1~5/ → rail_power_v15_win1~5/
       └──→ [coverage_tier1.py] 覆盖率计算  ──→ analyse/results/
```

---

## 七、快速命令参考

```bash
# JSONL 分析链
python code/vcd_to_jsonl.py data/sim_output.vcd
python code/jsonl_bit_diff.py output/sim_output.jsonl
python code/jsonl_toggle_mark.py output/sim_output.jsonl
python code/diff_to_html.py output/sim_output_diff.jsonl
python code/toggles_to_html.py output/sim_output_toggles.jsonl

# 信号查看
python code/parse_vcd_signal.py data/sim_output.vcd --list
python code/parse_vcd_signal.py data/sim_output.vcd tb_top.clk

# VCD 校验
python code/vcd_validator.py output/compressed.vcd --ref data/sim_output.vcd

# 覆盖率分析
python des_demo/db/analyse/coverage_tier1.py --db-root des_demo/db
```
