# VCD + DEF → HTML 一键可视化工具

给定 VCD 波形文件和 DEF 物理版图文件，一条命令生成:
- 空间-时间选窗可视化 HTML（5 个交互面板）
- 压缩后的 VCD 文件
- JSON 分析报告

## 环境要求

- Python 3.8+
- 无第三方依赖（全部使用 Python 标准库）
- 浏览器打开 HTML 时需联网（加载 Plotly CDN）

## 一条命令

```bash
python code/run_pipeline.py --vcd your_design.vcd --def your_design.def
```

输出默认在 `./output/` 目录下。

## 更多选项

```bash
python code/run_pipeline.py \
    --vcd  your_design.vcd \
    --def  your_design.def \
    -o     result/ \
    --kt 200 --top 1 --min-cluster 4 \
    --warmup-cycles 5 --clock-ns 50 \
    --skip-vcd   # 可选: 不生成压缩 VCD, 只要 HTML
```

## 输出文件

| 文件 | 说明 |
|------|------|
| `<stem>_spatial_temporal.html` | 交互式可视化 (浏览器打开) |
| `<stem>_compressed.vcd` | 压缩后 VCD |
| `<stem>_report.json` | JSON 分析报告 |
| `<stem>.jsonl` | 中间产物: 信号值 JSONL |
| `<stem>_toggles.jsonl` | 中间产物: Toggle JSONL |
| `<stem>_location.csv` | 中间产物: 信号坐标 CSV |

> `<stem>` 为输入 VCD 文件名（去掉扩展名）。
> 中间产物会自动缓存，重复运行会跳过已存在的步骤。

## 参数说明

| 参数 | 默认 | 说明 |
|------|------|------|
| `--vcd` | *(必填)* | VCD 波形文件 |
| `--def` | *(必填)* | DEF 物理版图文件 |
| `-o` | `./output/` | 输出目录 |
| `--mx` | 10 | 空间网格列数 |
| `--ny` | 10 | 空间网格行数 |
| `--kt` | 200 | 时间窗口数 |
| `--top` | 1 | 每个区域选 top-T 个窗口 |
| `--min-cluster` | 4 | 簇过滤阈值 (丢弃孤立窗口) |
| `--warmup-cycles` | 5 | 每段前 warmup 周期数 |
| `--clock-ns` | 50.0 | 时钟周期 (ns), 按你的设计修改 |
| `--timescale-ps` | *自动* | 从 VCD 头自动检测, 也可手动指定 |
| `--skip-vcd` | false | 只生成 HTML + JSON, 不压缩 VCD |

### 适配你的设计

**必须修改**:
- `--clock-ns`: 改为你设计的实际时钟周期

**可选调整**:
- `--kt`: 仿真时间长的设计可增大到 500~1000
- `--min-cluster`: 增大压缩率更高但丢弃更多窗口

## 可视化面板

HTML 文件包含 5 个 Plotly 交互面板:

| 面板 | 位置 | 内容 |
|------|------|------|
| Timeline | 顶部 | 时间窗口 toggle 柱状图, 红=选中, 金带=合并区间 |
| Location (Total) | 中左 | 信号物理坐标散点, 颜色=总 toggle |
| Heatmap (Total) | 中右 | 网格热力图, 全时间 toggle 聚合 |
| Location (Selected) | 下左 | 信号坐标散点, 颜色=仅选中窗口 toggle |
| Heatmap (Selected) | 下右 | 网格热力图, 仅选中窗口 toggle 聚合 |

## 内部流程

```
run_pipeline.py 内部自动执行 5 步:

1. VCD → JSONL           (vcd_to_jsonl.py)
2. JSONL → Toggle JSONL  (jsonl_toggle_mark.py)
3. VCD + DEF → 坐标 CSV  (vcd_def_mapper.py + parse_vcd_signal.py)
4. 空间时间选窗           (spatial_temporal_select.py)
5. 输出 HTML / VCD / JSON
```

## 目录结构

```
vcd_def2html/
├── README.md
└── code/
    ├── run_pipeline.py            ← 入口: 一条命令完成全部
    ├── spatial_temporal_select.py  ← 核心: 空间时间选窗 + VCD 拼接
    ├── parse_vcd_signal.py         ← VCD 解析器
    ├── vcd_to_jsonl.py             ← VCD → JSONL
    ├── jsonl_toggle_mark.py        ← JSONL → Toggle
    ├── vcd_def_mapper.py           ← VCD+DEF → 坐标映射
    └── vcd_validator.py            ← VCD 格式验证 (可单独使用)
```

全部 7 个 Python 文件，只依赖标准库，拷贝文件夹即可使用。
