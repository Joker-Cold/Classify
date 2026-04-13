# RC-Tile Worst-Window IR Drop Comparison

> Reference: `full` VDD peak drop = **26.00 mV** (@ interval 4050 ns)

## Per-case summary (VDD)

| Case | Vmin (V) | Vavg (V) | **Peak drop (mV)** | Worst interval (ns) | Violations | Drop ratio vs full |
|---|---|---|---|---|---|---|
| `full` | 0.6740 | 0.6810 | **26.00** | 4050 | 0 | 1.000 |
| `algo_win1` | 0.6740 | 0.6850 | **26.00** | 300 | 0 | 1.000 |
| `algo_win2` | 0.6740 | 0.6850 | **26.00** | 300 | 0 | 1.000 |
| `spatial` | 0.6710 | 0.6790 | **29.00** | 3806 | 0 | 1.115 |
| `rctile_win1` (m0)  | 0.6750 | 0.6820 | **25.00** | 3350 | 0 | 0.962 |
| `rctile_m1_win1`    | 0.6750 | 0.6820 | **25.00** | 3350 | 0 | 0.962 |
| `rctile_m1b_win1`   | 0.6750 | 0.6830 | **25.00** | 1550 | 0 | 0.962 |
| `rctile_m2_win1`    | 0.6790 | 0.6860 | **21.00** | 50   | 0 | 0.808 |
| `rctile_m3_win1` (cluster1, orig 3950~4200ns) | 0.6740 | 0.6850 | **26.00** | 100  | 0 | **1.000** |
| `rctile_m3_win2` (cluster2, orig 10650~10900ns) | 0.6800 | 0.6860 | **20.00** | 100  | 0 | 0.769 |
| **`rctile_m3` (combined max)** | **0.6740** | — | **26.00** | — | 0 | **1.000** |
| `rctile_m4_win1` (test.vcd, budget 10%) | — | — | **26.00** | — | 0 | **1.000** |
| **`rctile_m4` (test.vcd combined, 3 窗口)** | — | — | **26.00** | — | 0 | **1.000** |

### test_2x.vcd 对照 (m3 vs m4 vs spatial_temporal)

| 算法 | 窗口数 | β | combined peak drop (mV) | ratio vs spatial |
|---|---|---|---|---|
| `rctile_m3` (top-K=2) | 2 | 2.09% | **30.00** | 0.882 |
| `rctile_m4` (budget=10%) | 9 | 9.41% | **30.00** | 0.882 |
| `rctile_m5a` (α=0.5, neighbor) | 9 | 9.41% | **30.00** | 0.882 |
| `rctile_m6a` (gap=5, Python-only, **SKIPPED Innovus**) | 9 | 9.41% | — | — |
| `spatial_temporal` | 20 | 30.9% | **34.00** | 1.000 |

- **m6a Python-only 结论** (2026-04-09): 将 `--min-gap-cycles` 从 10 降到 5 后,**前 6 个窗口与 m5a 字节级一致** (同 i_start/i_end/score),仅 rank 7-9 重洗到另外三个已知高活动 cluster (2850/3550/16050 ns)。cycle 298-304 (14895~15264 ns, 真实 34 mV worst) 在两者中都未进入 top-9,且相邻 rank 在 α=0.5 neighbor 打分下仍 ≥13。
  - **gap relaxation is not the blocker**: 298-304 与已选 argmax (291, 305) 已相距 7 cycles, gap=5 不会抑制它——真正的瓶颈是 raw score 本身。减小 gap 反而让选窗更集中在已知 cluster 内部,远离 PG 弱区。
  - **决策**: 跳过 M6-A Innovus 运行 (6/9 窗口不变 → 可预测 peak=30 mV, 零新信息), 直接进入 M6-C (`--k-min 4`, L=9 宽窗) 攻击公式偏差。

**m4 test_2x.vcd 9 窗口逐窗 Innovus 明细** (β=9.41%):

| win | 原始时间 (ns) | Vmin (V) | peak drop (mV) |
|---|---|---|---|
| win01 | 2350~2600 | 0.673 | 27 |
| win02 | 4150~4400 | 0.670 | 30 |
| win03 | 5450~5700 | 0.676 | 24 |
| win04 | 14250~14500 | 0.673 | 27 |
| win05 | 15250~15500 | 0.671 | 29 |
| win06 | 15850~16100 | 0.670 | 30 |
| win07 | 16450~16700 | 0.670 | 30 |
| win08 | 17050~17300 | 0.673 | 27 |
| win09 | 17650~17900 | 0.679 | 21 |

- **combined = 30 mV**,与 m3 (2 窗口) 完全相同;spatial_temporal 的 34 mV 来自 cycle 298~305 (14895~15264 ns),落在 m4 win05 之外但相邻 win06/win07 也未能捕获到该 ns 级 peak。
- **m4 关键结论**: budget=10% 放大窗口数 (2→9) **不能弥补打分偏差**——Python `e_t = max_k P_{t,k}` 模型把真实 worst hotspot (cycle 298~305, Innovus 实测 34 mV) 排在 rank > 9 之外,无论怎么抬 β,只要 score 公式不变,都抓不到该 hotspot。
- **m4 vs m3 平手证明**: 问题根源不是"窗口数量不够",而是**打分公式有系统偏差**,`max_k P_{t,k}` 无法感知 PG 弱区的空间邻接效应 (同一个 tile 周围 tile 共同贡献下,PG 末端压降会被放大,但 `max_k` 只看单 tile 峰值)。
- **下一步 m5 方向**: 改打分公式引入空间邻接加权,参考 Hu2025 多特征方案。

## Per-case summary (VSS)

| Case | Vmin (V) | Vavg (V) | Vmax (V) | Worst interval (ns) | Violations |
|---|---|---|---|---|---|
| `full` | nan | nan | nan | 4050 | 0 |
| `algo_win1` | nan | nan | nan | 300 | 0 |
| `algo_win2` | nan | nan | nan | 300 | 0 |
| `spatial` | nan | nan | nan | 3806 | 0 |
| `rctile_win1` | nan | nan | nan | 2550 | 0 |

## Notes

- `Peak drop` = nominal VDD (0.700 V) − measured Vmin
- `Drop ratio vs full` ≥ 0.95 表示压缩 VCD 充分复现 full 的 IR drop 峰值
- Worst interval 是 Innovus 报告中 dynamic IR drop 最大瞬时所在的 ns (在拼接 VCD 的本地时间轴)
- **m0/m1/m1b 三轮 worst interval 映射回原始时间均为 9850 ns** (cycle 197):
  - m0/m1 窗口 6500~10050 ns → 3350 spliced = 9850 原始
  - m1b 窗口 8300~11850 ns → 1550 spliced = 9850 原始
  - 即不论窗口起点在哪,只要包住 cycle 197,Innovus 都把它判为本窗最坏
- **关键发现**: Python peak-tile e_t 把 cycle 197 @ 9850 ns 排在 ~rank 13 (e_t≈943),低于 cluster ② (cycle 215, e_t=1029) 和 cluster ① (cycle 81, e_t=1014);而 Innovus 实测显示 cycle 197 才是本数据集 8300~10050 ns 区间内的真实最坏。**Python 的 peak-tile 排序与 Innovus 有系统性偏差** → 单纯改 ρ (m1b) 不能突破 25 mV 的 plateau。
- **m2 小窗对照**: 强制 L=5 cycles, center=argmax(e_t)=cycle 215 → 窗口 [212, 217) = ns 10600~10850。β 骤降到 2.1% (14× 提升),但 ratio 跌到 0.808,peak drop 仅 21 mV @ 10650 ns (Innovus 在 5 cycle 内取 cycle 213,与 Python argmax 偏差 2 cycle)。
  - **机理**: m0/m1/m1b 的 71-cycle 窗口**意外包住了** cycle 197 @ 9850 ns(那才是 Innovus 眼中的区域最坏),这是"边带救场";m2 紧窗完全不含 cycle 197,失去救场 → 21 mV 是 cluster ② 的真实本地 drop。
  - **推论**: 本设计中 cluster ②(10750 ns 附近)的 IR drop 实际弱于 cluster ①(4050 ns,Innovus 的 full worst)和 cycle 197(9850 ns,局部 hotspot)。Python peak-tile score 对 cluster ② 的 rank#1 判定错误,**全设计** full worst 是 cluster ① @ cycle 81 @ 4050 ns (full 报告)。
  - **要命中 full worst**: 必须把窗口打到 cluster ① 附近;目前 1-phase 单窗口配置下,Python 的 argmax 选了 cluster ② 而不是 cluster ①(e_t 1029 vs 1014,1.5% 领先),除非 (a) 把 phase 切碎 (k_theta↑ / gap=0) (b) 在一个 phase 内取 top-K argmax 而不是 argmax 单峰。
- **m3 top-K=2 结论** (2026-04-08): `--small-window --top-k 2 --min-gap-cycles 10` 在同一 phase 内取 top-2 非相邻 argmax,同时生成 win1 (cluster1, cycle 81) 和 win2 (cluster2, cycle 215)。
  - win1 (spliced 0~250ns = orig 3950~4200ns): peak drop **26 mV** @ 100ns → 精确命中 full worst ✅
  - win2 (spliced 250~500ns = orig 10650~10900ns): peak drop **20 mV** → cluster2 本地 worst
  - **combined ratio = 1.000**, beta_out = **4.2%** (10/238 cycles, 24x 压缩)
  - m3 是首个在 beta < 5% 的同时达到 ratio = 1.000 的配置,验证 top-K argmax 策略有效。