# RC-Tile Worst Window Selection — 独立部署包

基于 **RC 加权 tile 指纹 + Peak-Tile 危险度打分 + Top-K Phase-Aware 小窗** 的
最坏功耗噪声窗口筛选算法。从一段长 VCD 中自动定位若干"危险窗口",
拼接成压缩 VCD,用于下游 Voltus / Redhawk 等动态压降 (DVD) 分析。

**验证结果 (DES3, ASAP7, 11850ns VCD)**:
`--small-window --top-k 2` 以 **4.2% 的时长** (10/238 cycles) 实现 **ratio = 1.000** vs full IR Drop baseline。

算法详细说明见 [`../docs/algorithm_worst_window_lite.md`](../docs/algorithm_worst_window_lite.md)。

## 环境要求

- Python 3.8+
- 无第三方依赖 (全部使用 Python 标准库)
- 可视化 HTML 在浏览器中打开时需联网加载 Plotly CDN

## 目录结构

```
RC_Tile_Worst_Window/
├── README.md                  ← 本文件
├── code/
│   ├── find_worst_window.py         ← 主脚本: 危险窗口选择 + VCD 拼接
│   ├── spef_parser.py               ← SPEF 解析器: 提取每个 net 的 (c_load, r_net)
│   ├── parse_vcd_signal.py          ← VCD 解析器 (被上游脚本依赖)
│   ├── vcd_to_jsonl.py              ← Step 1: VCD → JSONL
│   ├── jsonl_toggle_mark.py         ← Step 2: JSONL → Toggle JSONL
│   ├── vcd_def_mapper.py            ← Step 3: VCD + DEF → 坐标 CSV
│   └── vcd_validator.py             ← 辅助: 验证 VCD 格式
├── example_data/
│   ├── sample_location.csv          ← 坐标 CSV 格式参考
│   └── sample_toggles.jsonl         ← Toggle JSONL 格式参考
└── sim_result/
    ├── intermediate/                ← 中间产物 (JSONL / Toggle / Location CSV)
    ├── report/                      ← HTML + JSON 报告
    └── vcd/                         ← 输出的压缩 VCD
```

## 完整流程 (从零开始)

### 前置: 准备输入文件

| 文件 | 必需 | 说明 |
|------|------|------|
| `input.vcd` | ✓ | VCS/Xcelium 仿真输出的 VCD 波形 |
| `design.def` | ✓ | Innovus/ICC2 导出的 DEF 物理版图 |
| `design.spef` | 可选 | SPEF 寄生参数 (无 SPEF 时降级为 R̂_k=1) |

### Step 1: VCD → JSONL (逐时间点的信号值)

```bash
python code/vcd_to_jsonl.py input.vcd --output-dir sim_result/intermediate/
```

输出: `sim_result/intermediate/input.jsonl`

### Step 2: JSONL → Toggle JSONL (逐时间点的翻转标记)

```bash
python code/jsonl_toggle_mark.py sim_result/intermediate/input.jsonl
```

输出: `sim_result/intermediate/input_toggles.jsonl`

### Step 3: VCD + DEF → 信号坐标 CSV

```bash
python code/vcd_def_mapper.py \
    --vcd input.vcd \
    --def design.def \
    --output sim_result/intermediate/signal_location_map.csv
```

### Step 4 (可选): SPEF → 给坐标 CSV 加上 c_load / r_net

```bash
python code/spef_parser.py \
    --spef design.spef \
    --location sim_result/intermediate/signal_location_map.csv \
    --output   sim_result/intermediate/signal_location_rc.csv
```

输出 CSV 在原列基础上增加 `c_load` (fF) 与 `r_net` (Ω) 两列。
若跳过本步,主脚本会自动以 `w_s=1`、`R̂_k=1` 的退化模式运行。

### Step 5: 危险窗口选择 + VCD 压缩 (主脚本)

```bash
python code/find_worst_window.py \
    --location sim_result/intermediate/signal_location_rc.csv \
    --toggles  sim_result/intermediate/input_toggles.jsonl \
    --vcd      input.vcd \
    --n-grid   8 \
    --k-theta  1.0 \
    --rho      0.7 \
    --eta      0.15 \
    --k-min    2 \
    --gap      1 \
    --n-min    3 \
    --clock-ns 50 --timescale-ps 10 \
    --output   sim_result/vcd/worst_window.vcd \
    --html     sim_result/report/visualization.html \
    --json-out sim_result/report/report.json
```

### Step 6: 验证输出 VCD

```bash
python code/vcd_validator.py sim_result/vcd/worst_window.vcd
```

## 一键运行示例 (复制即用)

```bash
# 中间数据
python code/vcd_to_jsonl.py my_design.vcd --output-dir sim_result/intermediate/
python code/jsonl_toggle_mark.py sim_result/intermediate/my_design.jsonl
python code/vcd_def_mapper.py --vcd my_design.vcd --def my_design.def \
    --output sim_result/intermediate/signal_location_map.csv
python code/spef_parser.py --spef my_design.spef \
    --location sim_result/intermediate/signal_location_map.csv \
    --output   sim_result/intermediate/signal_location_rc.csv

# 危险窗口选择
python code/find_worst_window.py \
    --location sim_result/intermediate/signal_location_rc.csv \
    --toggles  sim_result/intermediate/my_design_toggles.jsonl \
    --vcd      my_design.vcd \
    --output   sim_result/vcd/worst_window.vcd \
    --html     sim_result/report/visualization.html \
    --json-out sim_result/report/report.json

# 验证
python code/vcd_validator.py sim_result/vcd/worst_window.vcd
```

## 参数说明

### find_worst_window.py 参数

| 参数 | 默认 | 说明 |
|------|------|------|
| `--location` | *(必填)* | 信号坐标 CSV (可含 c_load, r_net 列) |
| `--toggles` | *(必填)* | Toggle JSONL (Step 2 输出) |
| `--vcd` | *(必填)* | 原始 VCD 文件 |
| `--spef` | *(可选)* | SPEF 文件 (如已在 location CSV 内 merge 则无需) |
| `--n-grid` | 8 | 物理网格边长 (生成 N_grid × N_grid 个 tile) |
| `--k-theta` | 1.0 | 活跃阈值倍率 θ = k_θ · median(c_i) |
| `--rho` | 0.7 | 窗口中心相对位置 (0=phase 起点, 1=phase 终点)，`--small-window` 时忽略 |
| `--eta` | 0.15 | 窗口半宽 = max(K_min, ⌈η · N_c⌉)，`--small-window` 时忽略 |
| `--k-min` | 2 | 窗口最小半宽 (周期数)；`--small-window` 时窗口长度 L = 2·k_min+1 |
| `--gap` | 1 | 相邻活跃 cycle 间允许的最大空洞,用于吸收 |
| `--n-min` | 3 | 单个 phase 最小持续 cycle 数 |
| `--small-window` | *(flag)* | 启用小窗模式：center=argmax(e_t)，L=2·k_min+1，废弃 rho/eta |
| `--top-k` | 1 | 每 phase 最多生成 K 个非重叠小窗 (仅 --small-window 有效；=1 时等同 m2) |
| `--min-gap-cycles` | 10 | 同 phase 内两个 argmax 中心的最小间隔 (单位: cycles，仅 --top-k>1 有效) |
| `--clock-ns` | 50.0 | 时钟周期 (ns) |
| `--timescale-ps` | 10.0 | VCD timescale (ps),需与 VCD 文件头一致 |
| `--output` | *(必填)* | 输出压缩 VCD 路径 |
| `--html` | *(可选)* | 输出可视化 HTML 路径 |
| `--json-out` | *(可选)* | 输出 JSON 报告路径 |

### 适配你的设计

需要修改的参数:
- `--clock-ns`:改为你设计的时钟周期
- `--timescale-ps`:改为你 VCD `$timescale` 的值
- `--n-grid`:根据芯片规模调整 (常用 4 / 6 / 8 / 10)

### 调参建议

| 参数 | 增大效果 | 减小效果 |
|------|---------|---------|
| `n-grid` | 空间粒度细,更易暴露局部热点 | 粒度粗,tile 数少 |
| `k-theta` | 活跃判定更严格,phase 数少 | phase 数多,易混入低活跃段 |
| `rho` | 窗口偏向 phase 后段 (更接近 ρ 耗尽) | 窗口偏向 phase 起点 |
| `eta` | 窗口更宽,覆盖更长 | 窗口更窄,压缩率更高 |
| `gap` | 容忍更多空洞,phase 更连续 | phase 更易被切碎 |

### 推荐配置

| 场景 | n_grid | k_θ | --small-window | --top-k | 备注 |
|------|--------|-----|----------------|---------|------|
| **推荐 (验证最优)** | 8 | 1.0 | ✓ | 2 | β=4.2%, ratio=1.000 (DES3 验证) |
| 单点最小压缩 | 8 | 1.0 | ✓ | 1 | β=2.1%, 仅覆盖 Python argmax cluster |
| 旧式宽窗 | 8 | 1.0 | — | — | β=29.8%, 保留 ρ-depletion 机制 |
| 高保真多窗 | 10 | 0.8 | ✓ | 3 | 覆盖更多潜在 hotspot，β≈6% |

## 输出说明

### 可视化 HTML (4 个交互面板)

| 面板 | 内容 |
|------|------|
| Cycle Toggle (c_i) | 每周期 toggle 计数柱状图,标出活跃 phase |
| Danger Score (e_t) | 每周期危险度 e_t = P_total · (1 + σ_top3),红色=选中窗口 |
| P heatmap | N_grid × N_grid 加权功率指纹 (整段聚合) |
| R̂ heatmap | N_grid × N_grid 归一化 tile 电阻代理 |

### JSON 报告字段

```
parameters       — 运行参数 (n_grid, k_theta, rho, eta, ...)
simulation       — 总 cycle 数、总 toggle、median(c_i)
phases           — 检测到的活跃 phase 列表 [{start, end, length}]
windows          — 选中窗口列表 [{phase_id, t_center, t_lo, t_hi, score}]
tile_resistance  — 每 tile 的 R̂_k
compression      — 时间占比、VCD 体积压缩率
```

## 算法简述 (5 阶段)

```
Stage 1: Cycle Aggregation
    扫描 toggle JSONL → 每周期总 toggle c_i
    median 阈值 θ = k_θ · median(c_i),标记活跃 cycle

Stage 2: Phase Detection
    连续活跃 cycle (允许 gap 个空洞) 合并为 phase
    丢弃长度 < n_min 的短 phase

Stage 3: RC-Weighted Tile Fingerprint
    芯片版图划分为 N_grid × N_grid tile
    每个 net 按其驱动单元落入 tile k
    tile 电阻代理 R̂_k:从 SPEF *RES 聚合后归一化到 [0.5, 2.5]
    每周期每 tile: I_t,k = Σ (toggle_i · w_s_i),  P_t,k = I_t,k · R̂_k

Stage 4: Danger Score  [m1 更新: peak-tile 形式]
    e_t = max_k P_t,k      (单 cycle 内最危险 tile 的 RC 加权功率)
    (原始: e_t = P_total*(1+σ_top3)，已废弃)

Stage 5: Phase-Aware Window Generation  [m2/m3 更新: top-K small-window]
    默认模式 (--small-window 未指定):
        窗口中心 t_c = t_s + ρ · (t_e - t_s)
        窗口半宽 r   = max(K_min, ⌈η · N_c⌉)
        每 phase 生成 1 个窗口
    small-window 模式 (--small-window):
        L = 2·k_min+1  (固定小窗长度)
        top-K 贪心: 在 phase 内依次选 argmax(e_t)，封锁 ±min_gap_cycles 后重选
        每 phase 最多生成 top_k 个非重叠小窗
        窗口分数 = max(e_t in window)  [而非 sum]

Stage 6: VCD Splice
    两遍扫描 VCD: Pass1 收集每段起点的边界状态,
    Pass2 写入 $dumpvars + 时间重映射,段间插入 $comment 标记
    生成 HTML 可视化 + JSON 报告
```

## 与上游 spatial_temporal 的关系

本工具与 [`../spatial_temporal/`](../spatial_temporal/) 共享 Step 1~3 的中间产物
(JSONL、Toggle JSONL、坐标 CSV) 与 VCD validator,可在同一份中间数据上并行运行。
区别在于 `find_worst_window.py` 引入 RC 加权 tile 指纹 + Top-3 集中度,
更贴近 V_R = IR 的物理过程,适合 DVD 风险窗口定位;
`spatial_temporal_select.py` 则面向纯 toggle 覆盖率压缩。
