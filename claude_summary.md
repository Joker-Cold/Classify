# VCD最坏功耗波形筛选项目 - Claude理解总结

## 项目目标

本项目的核心目标是：**从VCD（Value Change Dump）仿真波形文件中，智能筛选出引起最坏功耗情况的波形时间段，从而压缩VCD文件体积，同时保证压缩后的VCD文件放入芯片验证（如功耗分析、时序验证）时效果不受影响。**

### 核心假设
- 信号跳变（Toggle）次数越多 → 动态功耗越高
- 因此，跳变最频繁的时间窗口 = 功耗最坏情况（Worst-Case Power）
- 保留这些窗口的波形数据即可代表最坏功耗场景

---

## 项目整体流水线

```
原始VCD文件 (data/random_test.vcd)
         │
         ▼  [任务1: task1_vcd_to_csv.py]
每个信号的CSV + signal_manifest.json
         │
         ▼  [任务2: task2_count_toggles.py]
跳变次数统计CSV (output/toggle_counts_5cycles.csv / 10cycles.csv)
         │
         ▼  [任务4: task4_extract_worst_case.py]  ← 核心筛选步骤
最坏情况数据CSV (output/worst_case_5cycles.csv / 10cycles.csv)
         │
         ▼  [任务5: task5_csv_to_vcd.py]
压缩后的VCD文件 (output/worst_case_5cycles.vcd / 10cycles.vcd)
         │
         ▼  [验证: vcd_validator.py]
验证VCD格式正确性
```

**一键运行：**
```bash
python code/run_pipeline.py data/random_test.vcd [--window-size 5 10] [--threshold 0.7] [--validate]
```

---

## 各模块详细说明

### 核心工具：`code/parse_vcd_signal.py`
- **功能**：VCD文件解析器，项目的基础工具
- **核心类**：`VCDSignalParser`
- **主要API**：
  - `parse_header()` — 解析VCD头部（scope/var/timescale），建立信号→符号映射
  - `parse_all_waveforms()` — 一次扫描提取所有信号波形，返回 `{signal_name: [(time, value), ...]}`
  - `list_base_signals()` — 返回去重后的基础信号名列表
  - `get_signal_info(name)` — 返回信号元数据 `{name, type, width, symbol, full_name}`
  - `extract_waveform(name, start_time, end_time)` — 提取单信号波形（支持时间范围过滤）

---

### 任务1：`code/task1_vcd_to_csv.py` — VCD转CSV
- 调用 `VCDSignalParser` 提取VCD中所有信号
- 为每个信号生成独立CSV（格式：`time, value`）
- 生成 `signal_manifest.json`，记录每个信号的名称、类型、位宽、符号、CSV文件路径
- 测试数据中的信号：`clk`（时钟）、`seed`（整数参数）、`circle`（参数）、`rand_sig [4:0]`（5位向量）

---

### 任务2：`code/task2_count_toggles.py` — 统计跳变次数
- 从 `signal_manifest.json` 读取信号列表和CSV路径（无硬编码）
- 从 `clk.csv` 提取时钟上升沿，确定每个时钟周期的起始时间
- 以X个时钟周期为一个窗口，统计每窗口内**非时钟信号**的总跳变次数
- **输出CSV2格式**：`window_index, window_start_time, window_end_time, toggle_count`
- 支持多窗口大小（默认5周期和10周期）

---

### 任务4：`code/task4_extract_worst_case.py` — 提取最坏情况窗口（核心算法）

**最坏情况识别算法（详见 `skills/worst_case_identification.md`）**：
```
1. 读取所有窗口的跳变次数
2. 找到全局最大跳变次数 max_toggles
3. 计算阈值 threshold = max_toggles × 70%
4. 筛选所有 toggle_count >= threshold 的窗口 → 最坏情况窗口
5. 按跳变次数降序排序
6. 提取这些窗口内的信号变化数据 → CSV3
```

- **阈值70%**：可调整，捕捉所有高活跃时段，而不只是唯一的最大值点
- CSV3格式：时间对齐的多信号综合CSV，只包含最坏窗口内的时间点

---

### 任务5：`code/task5_csv_to_vcd.py` — CSV还原为VCD
- 读取CSV3文件 + `signal_manifest.json`（从manifest动态读取信号类型/位宽，无硬编码）
- 重建完整的VCD头部（`$date`, `$version`, `$timescale`, `$scope`, `$var`声明）
- 生成 `$dumpvars` 初始值段
- 按时间顺序输出所有值变化
- 自动处理标量信号（`0!` / `1!`格式）和向量信号（`b10101 "`格式）

---

### 辅助工具

| 文件 | 功能 |
|------|------|
| `code/vcd_validator.py` | 按照IEEE VCD标准验证VCD文件格式合法性，检查scope平衡、符号定义、时间单调性等 |
| `code/waveform_viewer.py` | 从单信号CSV生成HTML波形可视化页面 |
| `code/run_pipeline.py` | 统一流水线入口，一键执行全流程 |

---

## Skills文档（`skills/`目录）

| 文件 | 技能名称 | 内容摘要 |
|------|---------|---------|
| `skills.md` | **AI角色定位 + Skills索引** | HDL+Python协同设计专家角色定义，代码自查协议，所有skills索引 |
| `vcd_format.md` | **VCD格式合规检查** | IEEE VCD格式规范：header结构、变量定义、值变化格式、合法性检查清单 |
| `parse_vcd_signal.md` | **VCD信号解析** | 从VCD提取指定信号完整波形的算法和输出格式 |
| `vcd_to_csv.md` | **VCD转CSV** | VCD波形文件转换为CSV数据集的流程和格式规范 |
| `toggle_count.md` | **跳变次数统计** | 基于时钟周期窗口的信号跳变计数算法（任务2） |
| `worst_case_identification.md` | **最坏情况识别** | 70%阈值标准和完整识别流程（核心算法，任务3/4） |
| `csv_to_vcd.md` | **CSV重建VCD** | 从CSV3+manifest重建标准VCD文件的规范（任务5） |
| `compare_vcd_waveform.md` | **VCD波形对比** | 对比两个VCD的信号波形（回归测试/压缩验证） |
| `WAVEFORM_TOOLS.md` | **工具快速参考** | 项目所有工具的命令行用法和快速上手指南 |

---

## 数据文件

- **输入**：`data/random_test.vcd` — 测试用VCD，包含4个信号，时钟10ns翻转一次
- **输出目录**：`output/` — 所有中间CSV、signal_manifest.json和最终VCD

### signal_manifest.json 格式
```json
{
  "vcd_source": "/path/to/sim.vcd",
  "timescale": "1 ns",
  "scope": "tb_top",
  "signals": [
    {"name": "clk",  "type": "reg",     "width": 1,  "symbol": "!", "csv_file": "clk.csv"},
    {"name": "seed", "type": "integer", "width": 32, "symbol": "\"", "csv_file": "seed.csv"}
  ]
}
```

---

## 关键技术细节

### VCD格式要点
- 标量值变化格式：`<value><symbol>`，如 `0!` `1!`
- 向量值变化格式：`b<binary> <symbol>`，如 `b10101 "`
- 时间标记：`#<整数>`，必须单调递增
- scope/upscope必须平衡

### 信号跳变计数规则
- 从窗口起始时间前的最后一个值开始作为基准
- 窗口内每次值变化（无论标量或向量）计数+1
- **clk信号不参与跳变统计**（作为时钟参考使用）

### 最坏情况阈值策略
- 默认70%阈值 → 适合一般功耗分析
- 可调为85% → 严格时序检查（更少窗口，更极端场景）
- 可调为60% → 寻找更多候选窗口
- 连续高活跃窗口可合并为一段较长的压力测试区间

---

## 当前局限与可改进方向

详细分析见 `py_improve_plan.md`，优先级摘要：

| 优先级 | 问题 | 涉及文件 |
|--------|------|---------|
| 🔴 Critical | 综合CSV迭代器拷贝Bug | task1_vcd_to_csv.py |
| 🔴 Critical | 最坏窗口初始值回溯不完整 | task4_extract_worst_case.py |
| 🔴 Critical | task5符号池只有15个 | task5_csv_to_vcd.py |
| 🟡 Important | task2每窗口重读CSV，性能极差 | task2_count_toggles.py |
| 🟡 Important | vcd_validator状态机不完整 | vcd_validator.py |

---

## 项目价值与应用场景

- **功耗签核（Power Sign-off）**：将完整仿真VCD压缩为只含最坏功耗场景的VCD，送入Voltus等工具做快速功耗分析
- **压力测试向量生成**：提取信号活动最频繁的时段作为测试向量，用于验证芯片极限工况
- **仿真加速**：减少VCD文件体积，降低后续分析工具的处理时间
- **时序分析**：高跳变密度时段也是最可能出现时序违规的地方，可重点验证
