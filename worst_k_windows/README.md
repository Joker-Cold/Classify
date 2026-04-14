# Worst-K Windows Selection — 最差窗口选取与 VCD 裁剪

从风险报告中选取 top-k 最差窗口，生成压缩 VCD。

## 用法

```bash
python code/select_worst_k.py \
    --risk-report ../risk_propagation_profiling/sim_result/report/risk_euclidean.json \
    --top-k 10 \
    --vcd ../Traditional_Vector_Profiling/sim_result/vcd/traditional.vcd \
    --output-dir sim_result/
```

## 输入

- `risk_<kernel>.json` — 来自 risk_propagation_profiling（或任意含 `worst_per_window[T]` 和 `parameters` 的 JSON）
- `traditional.vcd` — 原始 VCD 文件

## 输出

- `sim_result/report/worst_k_<kernel>.json` — 选取报告（top-k 窗口索引、评分）
- `sim_result/vcd/worst_k_<kernel>.vcd` — 压缩 VCD（仅含 top-k 窗口时段）

## 独立使用

该模块可独立于 risk_propagation_profiling 使用。只要输入 JSON 包含以下字段即可：
- `worst_per_window`: 长度为 T 的数组
- `parameters.T`: 总窗口数
- `parameters.t_max_ticks`: 最大时钟数
- `kernel`（可选）: 核函数名称，用于输出文件命名
