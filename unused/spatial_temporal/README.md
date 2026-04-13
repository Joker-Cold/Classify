# Spatial-Temporal Window Selection — 独立部署包

将芯片物理空间 (mx×ny grid) 与仿真时间 (kt windows) 两个维度结合,
从每个物理区域分别选出 toggle 最高的 top-T 个时间窗口,
经 cluster 过滤 + warmup 展开后, 拼接成压缩 VCD。

## 环境要求

- Python 3.8+
- 无第三方依赖 (全部使用 Python 标准库)
- 可视化 HTML 在浏览器中打开时需联网加载 Plotly CDN

## 目录结构

```
spatial_temporal/
├── README.md                  ← 本文件
├── code/
│   ├── spatial_temporal_select.py   ← 主脚本: 空间时间选窗 + VCD 拼接
│   ├── parse_vcd_signal.py          ← VCD 解析器 (被上游脚本依赖)
│   ├── vcd_to_jsonl.py              ← Step 1: VCD → JSONL
│   ├── jsonl_toggle_mark.py         ← Step 2: JSONL → Toggle JSONL
│   ├── vcd_def_mapper.py            ← Step 3: VCD + DEF → 坐标 CSV
│   └── vcd_validator.py             ← 辅助: 验证 VCD 格式
└── example_data/
    ├── sample_location.csv          ← 坐标 CSV 格式参考 (9 行)
    └── sample_toggles.jsonl         ← Toggle JSONL 格式参考 (3 行)
```

## 完整流程 (从零开始)

### 前置: 准备输入文件

你需要 3 个文件:

| 文件 | 说明 |
|------|------|
| `input.vcd` | VCS/Xcelium 仿真输出的 VCD 波形文件 |
| `design.def` | Innovus/ICC2 导出的 DEF 物理版图文件 |
| *(自动生成)* | 中间产物由下面的 Step 1~3 生成 |

### Step 1: VCD → JSONL (逐时间点的信号值)

```bash
python code/vcd_to_jsonl.py input.vcd --output-dir output/
```

输出: `output/input.jsonl` — 每行一个 JSON, 包含该时间点所有信号的值 (hold-last-value 填充)。

格式参考 `example_data/sample_toggles.jsonl`:
```json
{"time": 0, "signals": {"sig_a": "0", "sig_b": "1010", ...}}
{"time": 5000, "signals": {"sig_a": "1", "sig_b": "0110", ...}}
```

### Step 2: JSONL → Toggle JSONL (逐时间点的翻转标记)

```bash
python code/jsonl_toggle_mark.py output/input.jsonl
```

输出: `output/input_toggles.jsonl` — 与输入格式相同, 但值变为 XOR toggle 标记
(`1` = 该 bit 在这个时间步翻转了, `0` = 未翻转)。

### Step 3: VCD + DEF → 信号坐标 CSV

```bash
python code/vcd_def_mapper.py --vcd input.vcd --def design.def --output output/signal_location_map.csv
```

输出: `output/signal_location_map.csv` — 每个信号的物理坐标。

格式参考 `example_data/sample_location.csv`:
```csv
signal_name,scope,width,x_um,y_um,source_type,cell_type
CTS_16,test.u0.u2,1,337.248,289.296,net_driver,BUFx6f_ASAP7_75t_SL
```

### Step 4: 空间时间选窗 + VCD 压缩 (主脚本)

```bash
python code/spatial_temporal_select.py \
    --location output/signal_location_map.csv \
    --toggles  output/input_toggles.jsonl \
    --vcd      input.vcd \
    --mx 10 --ny 10 --kt 200 --top 1 \
    --warmup-cycles 5 --min-cluster 4 \
    --clock-ns 50 --timescale-ps 10 \
    --output   output/compressed.vcd \
    --html     output/visualization.html \
    --json-out output/report.json
```

### Step 5: 验证输出 VCD

```bash
python code/vcd_validator.py output/compressed.vcd
```

> 注: 如果源 VCD 存在层次化信号别名 (同一 symbol 在不同 scope 出现),
> validator 会报 "duplicate symbol" 警告, 这是 VCS 生成的 VCD 特性, 不影响使用。

## 一键运行示例 (复制即用)

假设你的文件为 `my_design.vcd` 和 `my_design.def`:

```bash
# 生成中间数据
python code/vcd_to_jsonl.py my_design.vcd --output-dir output/
python code/jsonl_toggle_mark.py output/my_design.jsonl
python code/vcd_def_mapper.py --vcd my_design.vcd --def my_design.def --output output/signal_location_map.csv

# 空间时间选窗压缩
python code/spatial_temporal_select.py \
    --location output/signal_location_map.csv \
    --toggles  output/my_design_toggles.jsonl \
    --vcd      my_design.vcd \
    --mx 10 --ny 10 --kt 200 --top 1 \
    --warmup-cycles 5 --min-cluster 4 \
    --clock-ns 50 --timescale-ps 10 \
    --output   output/compressed.vcd \
    --html     output/visualization.html \
    --json-out output/report.json

# 验证
python code/vcd_validator.py output/compressed.vcd
```

## 参数说明

### spatial_temporal_select.py 参数

| 参数 | 默认 | 说明 |
|------|------|------|
| `--location` | *(必填)* | 信号坐标 CSV (Step 3 输出) |
| `--toggles` | *(必填)* | Toggle JSONL (Step 2 输出) |
| `--vcd` | *(必填)* | 原始 VCD 文件 |
| `--mx` | 10 | 空间网格列数 |
| `--ny` | 10 | 空间网格行数 |
| `--kt` | 20 | 时间窗口数 (推荐 100~200) |
| `--top` | 2 | 每个 region 选 top-T 个窗口 |
| `--min-cluster` | 1 | 簇过滤: 丢弃孤立窗口, 保留 >=N 个相邻窗口的簇 |
| `--warmup-cycles` | 10 | 每段前的 warmup 周期数 |
| `--clock-ns` | 50.0 | 时钟周期 (ns) |
| `--timescale-ps` | 10.0 | VCD timescale (ps), 需与 VCD 文件一致 |
| `--output` | *(必填)* | 输出压缩 VCD 路径 |
| `--html` | *(可选)* | 输出可视化 HTML 路径 |
| `--json-out` | *(可选)* | 输出 JSON 报告路径 |

### 适配你的设计

需要修改的参数:
- `--clock-ns`: 改为你设计的时钟周期
- `--timescale-ps`: 改为你 VCD 文件头 `$timescale` 的值 (常见: 1ps/10ps/100ps/1ns)
- `--mx`, `--ny`: 根据芯片规模调整网格粒度

### 调参建议

| 参数 | 增大效果 | 减小效果 |
|------|---------|---------|
| `kt` | 时间粒度更细, 选择更精确 | 粒度粗, 每个窗口跨度大 |
| `top` | 覆盖更多区域热点, 压缩率低 | 只选最热窗口, 压缩率高 |
| `min-cluster` | 段数少, VCD 体积小, 丢弃孤立热点 | 保留更多窗口, 段数多 |
| `warmup-cycles` | 退耦电容状态更准确, 但区间更长 | 区间短, 初始状态可能不准 |

### 推荐配置

| 场景 | kt | top | warmup | min-cluster | 预期效果 |
|------|-----|-----|--------|-------------|---------|
| 快速验证 | 50 | 2 | 5 | 2 | ~60% 时间 |
| **推荐** | **200** | **1** | **5** | **4** | **~40% 时间, ~78% 体积** |
| 激进压缩 | 200 | 1 | 3 | 5 | ~30% 时间, 需检查覆盖率 |

## 输出说明

### 可视化 HTML (5 个交互面板)

| 面板 | 位置 | 内容 |
|------|------|------|
| Timeline | 顶部 | 每个时间窗口 toggle 柱状图, 红色=选中, 金色带=合并区间 |
| Location (Total) | 中左 | 信号坐标散点图, 颜色=总 toggle |
| Heatmap (Total) | 中右 | mx×ny 网格热力图, 所有窗口聚合 |
| Location (Selected) | 下左 | 信号坐标散点图, 颜色=仅选中窗口的 toggle |
| Heatmap (Selected) | 下右 | mx×ny 网格热力图, 仅选中窗口聚合 |

### JSON 报告字段

```
parameters       — 运行参数
simulation       — 仿真总时长、总 toggle
selection        — 选中窗口数、toggle 覆盖率
merged_intervals — 合并后的时间区间列表
compression      — 压缩率 (时间占比、体积)
per_window_detail — 每个窗口的详细信息 (toggle、投票数、是否选中)
```

## 算法简述

```
1. 加载信号物理坐标 + toggle 数据
2. 物理空间划分为 mx×ny 网格, 每个信号归入对应 cell
3. 时间轴等分为 kt 个窗口
4. 构建 3D toggle 矩阵: toggle_3d[iy][ix][j]
5. 每个 cell 按 toggle 降序投票选 top-T 个窗口, 全部 union
6. Cluster 过滤: 丢弃孤立窗口, 只保留 >=min_cluster 的密集簇
7. 每个窗口前扩展 warmup, 合并重叠/相邻区间
8. 两遍扫描 VCD: Pass 1 采集边界信号状态, Pass 2 流式拼接
   每段写 $dumpvars + 时间重映射, 段间插入 $comment 标记
9. 输出可视化 HTML + JSON 报告
```

## 已验证结果 (des3 测试设计, 42k 信号)

| 配置 | 选中窗口 | 时间占比 | VCD 体积 |
|------|---------|---------|---------|
| kt=20, top=2, warmup=10 | 18/20 | 94.2% | 120.5% |
| kt=200, top=1, warmup=5 | 62/200 | 79.5% | 120.0% |
| kt=200, top=1, warmup=5, mc=3 | 44/200 | 49.0% | 94.0% |
| **kt=200, top=1, warmup=5, mc=4** | **38/200** | **40.3%** | **77.8%** |
