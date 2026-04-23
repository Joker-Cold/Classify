# DMA_slow — VCD 文件说明

| 文件 | 方法 | 命中窗口 | 保留时段/总时段 | 段数 | 大小 |
|---|---|---:|---:|---:|---:|
| `sim.vcd` | 原始完整 VCD | - | 100% | - | 5859 KB |
| `DMA_slow_hotspot_t0.8_traditional.vcd` | traditional (toggle) | 7/97 | 13899/192600 (7.2%) | 5 | 4156 KB |
| `DMA_slow_hotspot_t0.8_euclidean.vcd` | risk / euclidean | 7/97 | 13899/192600 (7.2%) | 5 | 4156 KB |
| `DMA_slow_hotspot_t0.8_exponential.vcd` | risk / exponential | 7/97 | 13899/192600 (7.2%) | 5 | 4156 KB |
| `DMA_slow_hotspot_t0.8_logarithmic.vcd` | risk / logarithmic | 6/97 | 11912/192600 (6.2%) | 5 | 4193 KB |

## 命名规则
- `<circuit>_hotspot_t0.8_traditional.vcd` — 基于传统 toggle 统计
- `<circuit>_hotspot_t0.8_<kernel>.vcd` — 基于 risk_propagation (euclidean / exponential / logarithmic 三种核函数)

选窗策略：评分 >= 0.8 * max(worst_per_window) 的窗口被保留。

## 生成命令
```bash
python worst_k_windows/code/select_worst_k.py \
    --risk-report analysis/report/{traditional|risk_<kernel>}.json \
    --threshold-ratio 0.8 --top-k 10 \
    --vcd vcd/sim.vcd \
    --output-dir analysis/worst_k_t08/
```

## 对应报告
- JSON 报告: `../analysis/worst_k_t08/report/worst_k_<method>.json`
- 含 `hotspot_windows`（用于 VCD 裁剪的热点集合）和 `top_k_windows`（top-10 参考）