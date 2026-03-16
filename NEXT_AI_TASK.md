# 下一个 AI 的任务说明

## 项目状态：流水线已完成并通过 SoC VCD 验证 ✅

核心流水线（task1→task2→task4→task5）已实现，并已在真实 SoC 仿真输出 `sim_output.vcd`（124信号、多层嵌套scope）上成功运行。
详细项目说明见 `claude_summary.md`，本次工作总结见 `temp/sim_output_pipeline_summary.md`。

---

## 当前代码结构

```
code/
├── parse_vcd_signal.py     # VCD解析器（核心基础库）⭐ — 支持多scope消歧、过滤parameter/task
├── task1_vcd_to_csv.py     # 步骤1：VCD → 信号CSV + signal_manifest.json
├── task2_count_toggles.py  # 步骤2：统计每窗口跳变次数（鲁棒时钟检测）
├── task4_extract_worst_case.py  # 步骤4：提取最坏情况窗口
├── task5_csv_to_vcd.py     # 步骤5：CSV → 压缩VCD
├── run_pipeline.py         # 一键运行全流程
├── vcd_validator.py        # VCD格式验证工具
└── waveform_viewer.py      # HTML单信号波形可视化

data/
├── random_test.vcd         # 测试VCD（4个信号，单层scope）
└── sim_output.vcd          # 真实SoC仿真VCD（124信号，多层嵌套scope）

output/                     # 所有中间文件和最终输出
skills/                     # AI技能文档
temp/                       # 工作总结和临时文件
```

---

## 最近完成的工作（2026-03-13）

1. **parse_vcd_signal.py 多scope适配**：scope_type记录、信号名冲突消歧、list_unique_signals()
2. **task1 过滤逻辑**：排除 parameter 类型和 task scope 变量
3. **task2 鲁棒时钟检测**：_find_clock_signal() 自动识别顶层时钟
4. **成功运行 sim_output.vcd**：输出 VCD 全部 PASS，压缩比 64-65%

---

## 下一步任务建议

如果你是接手这个项目的AI，请先阅读 `skills.md` 中的索引，找到相关skills文档参考。
如有延续任务，参见 `continue_task.md`。

---

## 一键运行验证

```bash
# 简单测试VCD
python code/run_pipeline.py data/random_test.vcd --window-size 5 10 --threshold 0.7 --validate

# 真实SoC VCD
python code/run_pipeline.py data/sim_output.vcd --window-size 5 10 --threshold 0.7 --validate
```

所有输出VCD应通过 `PASS` 验证。
