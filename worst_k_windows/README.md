# Worst-K Windows Selection — 热点窗口选取与 VCD 裁剪

按**阈值比例**从风险报告中筛选热点窗口（默认：评分 ≥ `max(worst) × 60%`），
用选中窗口生成压缩 VCD。同时报告 top-k 最差窗口供参考。

压缩率不是固定的：随实际 toggle/risk 分布变化——活动越集中，压缩比越高。

## 用法

```bash
python code/select_worst_k.py \
    --risk-report ../risk_propagation_profiling/sim_result/report/risk_euclidean.json \
    --threshold-ratio 0.6 \
    --top-k 10 \
    --vcd ../Traditional_Vector_Profiling/sim_result/vcd/traditional.vcd \
    --output-dir sim_result/
```

## 参数

- `--threshold-ratio` 热点阈值比例，默认 `0.6`（选取评分 ≥ 最差值 60% 的窗口进 VCD）
- `--top-k` 报告中附加展示的 top-k 数（不影响 VCD 选取），默认 `10`
- `--warmup-ticks` 每个窗口前预热时钟数，默认 `0`

## 输入

- `risk_<kernel>.json` — 来自 risk_propagation_profiling（或任意含 `worst_per_window[T]` 和 `parameters` 的 JSON）
- `traditional.vcd` — 原始 VCD 文件

## 输出

- `sim_result/report/worst_k_<kernel>.json` — 选取报告，包含：
  - `max_score` / `threshold_score` / `n_hotspots`
  - `hotspot_windows`（用于 VCD 裁剪的全部热点）
  - `top_k_windows`（top-k 最差窗口）
- `sim_result/vcd/worst_k_<kernel>.vcd` — 压缩 VCD（仅含命中热点的窗口时段）

## 独立使用

该模块可独立于 risk_propagation_profiling 使用。只要输入 JSON 包含以下字段即可：
- `worst_per_window`: 长度为 T 的数组
- `parameters.T`: 总窗口数
- `parameters.t_max_ticks`: 最大时钟数
- `kernel`（可选）: 核函数名称，用于输出文件命名
