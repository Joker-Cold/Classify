# des_perf_slow — VCD 文件说明

| 文件 | 方法 | 命中窗口 | 保留时段/总时段 | 段数 | 大小 |
|---|---|---:|---:|---:|---:|
| `sim.vcd` | 原始完整 VCD | - | 100% | - | 61411 KB |
| `des_perf_slow_hotspot_t0.8_traditional.vcd` | traditional (toggle) | 26/97 | 51623/192600 (26.8%) | 23 | 46115 KB |
| `des_perf_slow_hotspot_t0.8_euclidean.vcd` | risk / euclidean | 17/97 | 33753/192600 (17.5%) | 17 | 37397 KB |

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