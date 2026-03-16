# 工作总结：sim_output.vcd 流水线适配与运行

> 初始指令：阅读skill.md，claude_summary.md，以data里sim_output.vcd为初始数据文件，执行的任务项目

## 执行日期
2026-03-13

## 任务概述
将原本仅支持简单 VCD（4信号、单层 scope）的最坏功耗波形筛选流水线，适配到真实 SoC 仿真输出 `sim_output.vcd`（124个有效信号、多层嵌套 scope、多字符符号）。

## 修改的文件

### 1. code/parse_vcd_signal.py — 多 scope 支持
- 新增 `scope_types` 列表，记录每层 scope 的类型（module/task/function/begin）
- `_parse_var_definition` 增加 `scope_type` 和 `in_task` 字段到 `symbol_table`
- `parse_all_waveforms` 增加名称冲突检测：多个不同符号映射同一 base name 时用 `full_name` 消歧
- 新增 `list_unique_signals()` 方法：每个 VCD symbol 恰好返回一个条目，支持过滤 parameter 和 task 变量
- 新增 `exclude_params` / `exclude_tasks` 参数给 `parse_all_waveforms`

### 2. code/task1_vcd_to_csv.py — 信号过滤
- 使用 `list_unique_signals(exclude_params=True, exclude_tasks=True)` 替代 `list_base_signals()`
- CSV 文件名支持 `.` 字符（scope 分隔符）的安全替换

### 3. code/task2_count_toggles.py — 鲁棒时钟检测
- 新增 `_find_clock_signal()` 函数：优先匹配顶层 `clk`，回退到含 "clk" 的 1-bit 信号中 toggle 最多的
- 排除所有 clock 别名信号（base name 为 "clk" 的所有层级信号）不参与跳变统计
- 修复了 `run` 函数中代码结构断裂的问题

## 运行结果

| 项目 | 值 |
|------|------|
| 输入文件 | data/sim_output.vcd (44.7 KB) |
| 有效信号数 | 124（过滤掉 parameter 和 task 变量后） |
| 时钟信号 | clk (201 transitions, 100 rising edges) |
| 时钟排除 | clk + u_soc.u_pwr_ctrl.clk (2个clk别名) |
| 数据信号 | 122 |

### 跳变统计
| 窗口大小 | 总窗口数 | 最大跳变 | 最大跳变窗口 | 最坏窗口数(70%) |
|----------|----------|----------|-------------|-----------------|
| 5 cycles | 95 | 203 | #71 | 35 |
| 10 cycles | 90 | 404 | #70 | 33 |

### 压缩结果
| 输出文件 | 大小 | 压缩比 | 验证 |
|----------|------|--------|------|
| worst_case_5cycles.vcd | 28.7 KB | 64% | PASS |
| worst_case_10cycles.vcd | 28.9 KB | 65% | PASS |

## Self-Check Report

### Python (VCD处理)
- [x] 逐行读取 — parse_all_waveforms 使用流式读取
- [x] 路径兼容性 — 使用 pathlib
- [x] 硬编码检查 — 所有信号信息从 signal_manifest.json 动态读取
- [x] 符号池检查 — task5 使用 itertools.product 生成无限符号
- [x] 初始值回溯 — task4 的 value_at_or_before 回溯到窗口开始前
- [x] 正则表达式 — 覆盖标量 `[01xzXZ]<sym>` 和向量 `b<binary> <sym>` 格式

### 临时文件
- [x] 本总结输出到 temp/ 文件夹

### 向后兼容
- [x] random_test.vcd（单层 scope、4信号）仍可正常运行
