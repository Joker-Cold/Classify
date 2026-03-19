# Spatial-Temporal Window Selection

将芯片物理空间 (mx×ny grid) 与仿真时间 (kt windows) 两个维度结合,
从每个物理区域分别选出 toggle 最高的 top-T 个时间窗口,
经 cluster 过滤 + warmup 展开后, 拼接成压缩 VCD。

## 快速开始

```bash
# 推荐配置: kt=200, top=1, warmup=5, min-cluster=4
python code/spatial_temporal_select.py \
    --location output/signal_location_map.csv \
    --toggles  output/test_toggles.jsonl \
    --vcd      des_demo/vcd/test.vcd \
    --mx 10 --ny 10 --kt 200 --top 1 \
    --warmup-cycles 5 --min-cluster 4 \
    --clock-ns 50 --timescale-ps 10 \
    --output   spatial_temporal/selected_spatial.vcd \
    --html     spatial_temporal/spatial_temporal_selection.html \
    --json-out spatial_temporal/spatial_temporal_selection.json
```

## 输入文件

| 文件 | 说明 | 生成方式 |
|------|------|---------|
| `output/signal_location_map.csv` | 信号物理坐标 (x_um, y_um) | `python code/vcd_def_mapper.py` |
| `output/test_toggles.jsonl` | 逐时间步 toggle 标记 | `python code/jsonl_toggle_mark.py` |
| `des_demo/vcd/test.vcd` | 原始 VCD 波形 | Synopsys VCS 仿真输出 |

## 输出文件

| 文件 | 说明 |
|------|------|
| `selected_spatial.vcd` | 压缩后 VCD (多段拼接, 时间连续重映射) |
| `spatial_temporal_selection.html` | 交互式可视化 (5 个面板, Plotly) |
| `spatial_temporal_selection.json` | JSON 报告 (参数、选窗详情、压缩率) |

## 参数说明

| 参数 | 默认 | 说明 |
|------|------|------|
| `--mx` | 10 | 空间网格列数 |
| `--ny` | 10 | 空间网格行数 |
| `--kt` | 20 | 时间窗口数 (推荐 100~200, 越大越精细) |
| `--top` | 2 | 每个 region 选出 top-T 个窗口 |
| `--min-cluster` | 1 | 簇过滤阈值: 丢弃孤立窗口, 仅保留 >=N 个相邻窗口组成的簇 |
| `--warmup-cycles` | 10 | 每段窗口前的 warmup 周期数 (让退耦电容稳定) |
| `--clock-ns` | 50.0 | 时钟周期 (ns) |
| `--timescale-ps` | 10.0 | VCD timescale (ps) |

### 关键参数: `--min-cluster`

每段 VCD 拼接都需要写入全量 `$dumpvars` (42k 信号的完整状态),
段数越多 overhead 越大。`--min-cluster` 通过丢弃时间轴上孤立的窗口,
只保留密集簇, 大幅减少段数, 实现真正的体积压缩。

### 调参建议

| 场景 | kt | top | warmup | min-cluster | 效果 |
|------|-----|-----|--------|-------------|------|
| 粗筛 (baseline) | 20 | 2 | 10 | 1 | ~94% 时间, 无压缩 |
| 精细无过滤 | 200 | 1 | 5 | 1 | 49% 时间, 94% 体积 |
| **推荐** | **200** | **1** | **5** | **4** | **40% 时间, 78% 体积** |
| 激进压缩 | 200 | 1 | 5 | 5+ | 更少时间, 需验证覆盖率 |

核心权衡:
- **kt 越大** → 时间粒度越细, 选择越精确, 但碎片化风险增加
- **top 越小** → 压缩率越高, 但可能遗漏某些区域的 worst-case
- **min-cluster 越大** → 段数越少, 体积压缩越好, 但丢弃更多窗口
- **warmup-cycles** → 5 周期对 50ns 时钟已够, 10 是保守值

## 算法流程

```
1. 加载信号物理坐标 (CSV)
2. 构建 mx×ny 空间网格, 每个信号分配到 grid cell
3. 构建 3D toggle 矩阵: toggle_3d[iy][ix][j] (ny × mx × kt)
4. 每个 grid cell 按 toggle 降序选 top-T 个 time window
5. Union 所有 region 的选择 → selected_set
6. Cluster 过滤: 丢弃孤立窗口, 保留密集簇 (min-cluster)
7. 每个选中窗口前扩展 warmup, 合并重叠区间
8. 两遍 VCD 拼接 (Pass 1: 采集边界状态, Pass 2: 流式写入)
9. 生成可视化 HTML + JSON 报告
```

## 可视化面板 (HTML)

打开 `spatial_temporal_selection.html` 后可看到 5 个交互面板:

| 面板 | 位置 | 内容 |
|------|------|------|
| Timeline | 顶部 (全宽) | 每个时间窗口的 toggle 柱状图, 红色=选中, 金色带=合并区间 |
| Location (Total) | 中左 | 信号坐标散点图, 颜色=总 toggle (含网格线) |
| Heatmap (Total) | 中右 | mx×ny 网格热力图, 全部时间窗口 toggle 聚合 |
| Location (Selected) | 下左 | 信号坐标散点图, 颜色=仅选中窗口的 toggle |
| Heatmap (Selected) | 下右 | mx×ny 网格热力图, 仅选中窗口 toggle 聚合 |

右侧 sidebar 显示统计摘要、选窗列表和合并区间。

## 验证

```bash
# 检查输出 VCD 格式 (79 个 duplicate symbol 警告来自源 VCD 的层次化别名, 正常)
python code/vcd_validator.py spatial_temporal/selected_spatial.vcd

# 查看 JSON 报告
python -c "import json; d=json.load(open('spatial_temporal/spatial_temporal_selection.json')); \
  print(f'Selected: {d[\"selection\"][\"n_windows_selected\"]}/{d[\"selection\"][\"n_windows_total\"]}'); \
  print(f'Toggle coverage: {d[\"selection\"][\"toggle_coverage_pct\"]}%'); \
  print(f'Time kept: {d[\"compression\"][\"ratio_pct\"]}%')"
```

## 当前最佳结果 (kt=200, top=1, warmup=5, min-cluster=4)

| 指标 | 值 |
|------|-----|
| 选中窗口 | 38 / 200 (19%) |
| Toggle 覆盖 | 37.3% |
| 时间保留 | 40.3% |
| 合并区间 | 3 段 |
| VCD 体积 | 77.8% (5.8 MB → 4.5 MB) |

### 历次调参对比

| 配置 | 选中窗口 | 时间占比 | VCD 体积 |
|------|---------|---------|---------|
| kt=20, top=2, warmup=10 | 18/20 | 94.2% | 120.5% |
| kt=100, top=2, warmup=10 | 22/100 | 86.3% | 141.3% |
| kt=200, top=1, warmup=5 | 62/200 | 79.5% | 120.0% |
| kt=200, top=1, warmup=0 | 62/200 | 31.0% | 303.5% (51段) |
| kt=200, top=1, warmup=5, **mc=3** | 44/200 | 49.0% | 94.0% |
| kt=200, top=1, warmup=5, **mc=4** | **38/200** | **40.3%** | **77.8%** |
