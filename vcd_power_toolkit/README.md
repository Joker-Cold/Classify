# VCD Power Analysis Toolkit

从 VCD 波形文件中自动选取 worst-case 功耗窗口，生成压缩 VCD 和可视化报告，
用于芯片 IR Drop 验证。

## 环境要求

- Python >= 3.8
- 安装依赖：`pip install -r requirements.txt`
- 仅需 `plotly`（可视化），其余均为 Python 标准库

## 目录结构

```
vcd_power_toolkit/
├── README.md                  ← 本文件
├── requirements.txt           ← pip 依赖
├── code/                      ← 所有脚本
│   ├── parse_vcd_signal.py    ← VCD 解析核心库 (被多个脚本 import)
│   ├── vcd_to_jsonl.py        ← VCD → JSONL 转换
│   ├── jsonl_bit_diff.py      ← JSONL 逐 bit 差分
│   ├── jsonl_toggle_mark.py   ← JSONL toggle 标记
│   ├── diff_to_html.py        ← 差分热力图可视化
│   ├── toggles_to_html.py     ← Toggle 热力图可视化
│   ├── toggle_heatmap.py      ← Toggle 时空热力图 (独立)
│   ├── select_worst_window.py ← Phase-Aware 选窗核心算法 (库)
│   ├── find_worst_window.py   ← 选窗命令行入口 (调用 select_worst_window)
│   ├── vcd_slicer.py          ← VCD 时间窗口切割
│   ├── vcd_validator.py       ← VCD 格式校验
│   ├── vcd_def_mapper.py      ← VCD 信号 → DEF 物理坐标映射
│   ├── spatial_temporal_select.py ← 空间-时间联合选窗 + 可视化
│   └── coverage_tier1.py      ← Voltus IR Drop 覆盖率分析
├── docs/                      ← 算法文档
│   ├── algorithm_worst_window.md  ← MAVIREC 算法伪代码 + 实验结果
│   └── spatial_temporal_guide.md  ← 空间-时间选窗使用指南
└── example_output/            ← 示例输出 (供参考)
    ├── algo_win1_visualization.html ← 算法窗口可视化 HTML
    ├── algo_win1_visualization.json ← 算法窗口 JSON 报告
    ├── coverage_report_v20.md       ← IR Drop 覆盖率报告
    └── coverage_tier1_v20.csv       ← 覆盖率数据 CSV
```

## 脚本依赖关系

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

> **注意**：`parse_vcd_signal.py` 和 `select_worst_window.py` 是被其他脚本
> `import` 的库文件。运行调用者脚本时，需确保它们在同一目录（`code/`）或在
> `PYTHONPATH` 中。

---

## 完整工作流

下面用一个完整例子演示：从原始 VCD 到最终 worst-case 选窗 + 可视化。

### 前置：准备输入文件

| 文件 | 说明 | 来源 |
|------|------|------|
| `test.vcd` | 原始仿真 VCD 波形 | EDA 工具 (VCS/Xcelium) |
| `design.def` | DEF 物理版图 (可选, 用于空间分析) | Innovus/ICC2 导出 |

### Step 1: VCD → JSONL

将 VCD 转为 JSONL 格式（每行一个时间步，hold-last-value 填充）。

```bash
cd code
python vcd_to_jsonl.py <path_to>/test.vcd
```

**输出**：`<同级目录>/output/test.jsonl`

### Step 2: Toggle 标记

对 JSONL 做逐 bit XOR，标记每个时间步的 toggle。

```bash
python jsonl_toggle_mark.py <path_to>/output/test.jsonl
```

**输出**：`<同级目录>/output/test_toggles.jsonl`

### Step 3: Toggle 可视化 (可选)

生成 toggle 热力图 HTML，快速观察活跃时段。

```bash
python toggles_to_html.py <path_to>/output/test_toggles.jsonl
```

**输出**：`<同级目录>/output/test_toggles.html` — 浏览器打开即可。

### Step 4: Worst-Case 选窗

用 Phase-Aware 算法选出 worst-case 功耗窗口。

```bash
python find_worst_window.py \
    --toggles <path_to>/output/test_toggles.jsonl \
    --clock-ns 50 \
    --depletion-ratio 0.7 \
    --html <output_dir>/window_selection.html \
    --json <output_dir>/window_selection.json
```

**关键参数**：

| 参数 | 默认 | 说明 |
|------|------|------|
| `--clock-ns` | 50.0 | 时钟周期 (ns) |
| `--depletion-ratio` | 0.7 | 退耦电容耗尽比，决定在持续活跃阶段的哪个位置取窗口 |
| `--window-ns` | 500.0 | 窗口宽度 (ns) |
| `--max-windows` | 2 | 最多选几个窗口 |

**输出**：
- `window_selection.html` — 交互式可视化（Phase 检测 + 窗口选择）
- `window_selection.json` — JSON 报告（窗口起止时间、toggle 统计）

#### 带空间集中度评分 (需要 DEF)

如果有 DEF 文件，先生成信号物理坐标映射：

```bash
python vcd_def_mapper.py \
    --vcd <path_to>/test.vcd \
    --def <path_to>/design.def \
    --output <output_dir>/signal_location_map.csv \
    --html <output_dir>/signal_location.html
```

然后选窗时加 `--def` 和 `--vcd` 启用空间评分：

```bash
python find_worst_window.py \
    --toggles <path_to>/output/test_toggles.jsonl \
    --def <path_to>/design.def \
    --vcd <path_to>/test.vcd \
    --clock-ns 50 --depletion-ratio 0.7 \
    --html <output_dir>/window_selection.html
```

### Step 5: VCD 切割

根据选窗结果，从原始 VCD 中切出 worst-case 时间段。

```bash
python vcd_slicer.py <path_to>/test.vcd \
    --start-ns 3790 --end-ns 4390 \
    -o <output_dir>/test_win1.vcd

python vcd_slicer.py <path_to>/test.vcd \
    --start-ns 9600 --end-ns 10100 \
    -o <output_dir>/test_win2.vcd
```

> `--start-ns` 和 `--end-ns` 来自 Step 4 的 JSON 报告。
> 输出 VCD 的时间轴从 #0 开始重映射，`$dumpvars` 写在 #0，信号从切割偏移处开始。

### Step 6: 切片 VCD 可视化

对切出的每段 VCD 生成空间-时间联合可视化。

```bash
# 先生成切片的 toggle JSONL
python vcd_to_jsonl.py <output_dir>/test_win1.vcd
python jsonl_toggle_mark.py <output_dir>/output/test_win1.jsonl

# 运行空间-时间可视化
python spatial_temporal_select.py \
    --location <output_dir>/signal_location_map.csv \
    --toggles  <output_dir>/output/test_win1_toggles.jsonl \
    --vcd      <output_dir>/test_win1.vcd \
    --mx 10 --ny 10 --kt 12 --top 1 \
    --warmup-cycles 0 --min-cluster 1 \
    --clock-ns 50 --timescale-ps 10 \
    --output   <output_dir>/win1_spatial_selected.vcd \
    --html     <output_dir>/win1_visualization.html \
    --json-out <output_dir>/win1_visualization.json
```

**HTML 包含 5 个面板**：

| 面板 | 内容 |
|------|------|
| Timeline | Toggle 柱状图，红色=选中窗口 |
| Location (Total) | 信号坐标散点图，颜色=总 toggle |
| Heatmap (Total) | 网格热力图，全时间步聚合 |
| Location (Selected) | 散点图，仅选中窗口 toggle |
| Heatmap (Selected) | 网格热力图，仅选中窗口 |

### Step 7: VCD 校验 (可选)

```bash
python vcd_validator.py <output_dir>/test_win1.vcd
```

### Step 8: IR Drop 覆盖率分析 (需 Voltus/Innovus 仿真结果)

将切片 VCD 送入 Innovus `analyze_rail` 后，用 `coverage_tier1.py` 对比覆盖率：

```bash
python coverage_tier1.py --v20 --base-dir <path_to>/db/analyse
```

**输出**：
- `coverage_tier1_v20.csv` — 各窗口覆盖率
- `coverage_report_v20.md` — Markdown 报告

> 此脚本需要修改内部路径常量以适配你的目录结构，详见脚本顶部 `FULL_SET_PATH_V20`
> 和 `WIN_PATHS_V20`。

---

## 一键流程 (快速参考)

```bash
cd code

# 1. VCD → JSONL → Toggle
python vcd_to_jsonl.py       ../data/test.vcd
python jsonl_toggle_mark.py  ../output/test.jsonl

# 2. (可选) DEF → 坐标映射
python vcd_def_mapper.py --vcd ../data/test.vcd --def ../data/design.def \
    --output ../output/signal_location_map.csv

# 3. 选窗
python find_worst_window.py --toggles ../output/test_toggles.jsonl \
    --clock-ns 50 --depletion-ratio 0.7 \
    --html ../output/window_selection.html --json ../output/window_selection.json

# 4. 切割 (根据 JSON 里的窗口时间)
python vcd_slicer.py ../data/test.vcd --start-ns START --end-ns END \
    -o ../output/test_win.vcd

# 5. 切片可视化
python vcd_to_jsonl.py       ../output/test_win.vcd
python jsonl_toggle_mark.py  ../output/output/test_win.jsonl
python spatial_temporal_select.py \
    --location ../output/signal_location_map.csv \
    --toggles  ../output/output/test_win_toggles.jsonl \
    --vcd      ../output/test_win.vcd \
    --mx 10 --ny 10 --kt 12 --top 1 \
    --warmup-cycles 0 --min-cluster 1 \
    --clock-ns 50 --timescale-ps 10 \
    --output ../output/win_spatial.vcd \
    --html   ../output/win_visualization.html
```

---

## 算法详情

详见 `docs/algorithm_worst_window.md`：
- MAVIREC 算法完整伪代码（5 个 Algorithm）
- Mermaid 流程图
- 符号表 & 参数推导
- 实验验证数据 (vs Voltus ground truth)

## 空间-时间选窗详情

详见 `docs/spatial_temporal_guide.md`：
- 参数调优建议
- 历次调参对比表
- 可视化面板说明
