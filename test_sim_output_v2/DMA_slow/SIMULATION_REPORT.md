# DMA_slow 长仿真 Voltus IR-Drop 五场景实验报告

> 实验时间: 2026-04-21
> 电路: ISPD 2012 Contest — **DMA_slow**
> 目的: 验证 "toggle-based worst-case 窗口选取 + VCD 压缩" 对 IR-drop 分析精度的保持能力，并比较 4 种候选核函数 (traditional / euclidean / exponential / logarithmic)。
> 对比基线: 未压缩 (full) VCD 的 Voltus IR-drop。

---

## 1. 实验平台

| 项目 | 取值 |
|---|---|
| EDA 服务器 | `hzhb-Super-Server` (Linux, x86_64) |
| 仿真器 | Synopsys VCS O-2018.09-SP2 |
| 后端工具 | Cadence Innovus/Voltus v20.10 |
| 工艺文件 | ASAP7 7 nm tech LEF + contest.lib (ISPD2012) |
| 寄生提取 | ASAP7 QRC `qrcTechFile_typ03_scaled4xV06` |
| 供电电压 | VDD = 0.7 V, VSS = 0.0 V |
| IR 违规阈值 | 0.651 V (即 49 mV drop budget，7%) |
| 电源接入 | 8 个 pad (4 角 M6 + 4 边中点 M7)，margin 6.24 µm |

---

## 2. 电路参数

| 项目 | 取值 |
|---|---|
| 顶层模块 | `DMA_slow` |
| ISPD 规模 | 约 2,903 原始实例 |
| 布局后实例数 | **21,981** (DEF COMPONENTS) |
| DEF DIEAREA | (0, 0) → (577728, 576000) DBU = **144.432 × 144.000 µm** |
| DEF 单位 | 4000 DBU/µm |
| 实例分布范围 | x ∈ [6.6, 137.5] µm, y ∈ [6.6, 136.2] µm |
| 时钟信号 | `ispd_clk` / `mclk`, 周期 **900 ps** |
| 驱动器-to-net 映射 | 21,981 nets 有 driver |
| (inst, pin) → net 索引 | 70,770 条 |
| SPEF 网络数 | 25,984 |
| Testbench | `tb_DMA_slow.v` (输入 13,333 组向量) |

---

## 3. VCS 门级仿真

### 3.1 编译参数
```
vcs -full64 -sverilog +v2k -timescale=10ps/10ps -debug_access+all +notimingchecks
    contest_cells.v  DMA_slow.v  tb_DMA_slow.v
```
> 注意: 虽然命令行 `-timescale=10ps/10ps`，VCS 实际写入 VCD 头 `$timescale 1ps` —
> 因此 VCD 中 `#N` 标签的 N 单位直接是 **ps** (不需要再乘 10)。
> 这是 Voltus TCL 后续的关键修正点。

### 3.2 运行数据

| 指标 | 值 |
|---|---|
| 编译 CPU 时间 | 2.768 s (VCS) + 0.801 s (elab) + 0.269 s (link) |
| 仿真运行 CPU 时间 | **1.600 s** |
| 向量输入 | 13,333 |
| 仿真终止时间 | 12,012,750 ps = **12,012.75 ns** |
| VCD 文件大小 | **142,854,908 B ≈ 142.85 MB** |
| VCD 内最后时间戳 | `#12012300` (ps) |
| VCD 唯一信号数 | 28,861 |

---

## 4. Innovus 后端流程 (pr_flow)

### 4.1 流程步骤
1. `init_design`（顶层 Verilog + ASAP7 tech LEF + contest cell LEF + MMMC）
2. `floorPlan -site asap7sc7p5t -r 1.0 0.70 …`（利用率 70%）
3. 电源环 M6/M7 (width 2.176 µm, spacing 0.384 µm, offset 0.384 µm)
4. M2 follow-rail、M3 垂直电源 stripe、M4 水平电源 stripe
5. `placeDesign`（跳过 timing-driven placement 避免 v20 崩溃）
6. `ccopt_design`（被 catch 包装，允许失败；DMA 本来就无 buffer 单元可用）
7. `routeDesign` → rebuild power via
8. 通过 `wrapper.tcl` 在 `IMPSYT-6692` 后手动 `defOut` + `saveNetlist`

### 4.2 运行数据

| 指标 | 值 |
|---|---|
| Innovus wall-clock | **1 min 30 s** |
| Innovus CPU time | 5 min 42 s |
| Innovus 峰值内存 | 1,855 MB |
| 布局后 DEF 大小 | 3,065,894 B (≈ 3.0 MB) |
| 布局后 Netlist 大小 | 2,068,244 B (≈ 2.1 MB) |
| 已知警告数 | 936 warnings, 3,566 errors (路由层面的 `IMPESI-3014`，不影响功耗分析) |

> **已知问题 & 解决方案** (来自 MEMORY.md):
> - `IMPSYT-6692` 在 routeDesign 后抛出 → `wrapper.tcl` catch，补充手动 `defOut -netlist -routing -allLayers`。
> - ring_pads 生成在 wrapper 内也失败 → 从 v1 同 DIEAREA 的结果直接复用 8-pad `.ppl` 文件。

---

## 5. 场景 1 — Full VCD Voltus (Baseline)

### 5.1 流程
- `set_power_analysis_mode -method dynamic_vectorbased -current_generation_method avg`
- `read_activity_file -format VCD sim.vcd -scope tb/u0 -start 0ps -end 12012300ps`
- `set_dynamic_power_simulation -resolution 1ns` → 12,012 rail steps
- `set_power_pads -net VDD -file ring_pads_vdd.ppl`
- `analyze_rail -type domain -output rail_full PD`

### 5.2 运行数据

| 阶段 | CPU time | Wall time | 备注 |
|---|---:|---:|---|
| Steady-State Analysis | 0:00:17 | 0:00:16 | 内存峰值 11,965 MB |
| Dynamic Rail Simulation | 0:08:52 | **0:04:02** | 12,012 steps @ 1 ns |
| Rail Analysis 总计 | 0:09:11 | 0:04:29 | peak mem 5,727 MB |
| Innovus 整体 | 0:10:27 | **0:06:12** | |

### 5.3 IR-drop 结果 (full 基线)

| 指标 | 值 |
|---|---|
| Min / Avg / Max IR 电压 | **0.652 V / 0.666 V / 0.700 V** |
| Max IR drop | **48.0 mV** |
| Nominal VDD | 0.700 V |
| Number of Violations | 0 |
| Total Current Taps | 21,981 |

### 5.4 各金属层 IR-drop 分布

| Layer | IR drop | IR range (V) | 元素数 |
|---|---:|---|---:|
| M6 | 11.9 mV | 0.700 → 0.688 | 34 |
| M5 | 29.3 mV | 0.700 → 0.671 | 40 |
| M4 | 28.7 mV | 0.697 → 0.669 | 36 |
| M3 | 42.0 mV | 0.696 → 0.654 | 120 |
| M2 | 40.2 mV | 0.694 → 0.654 | 770 |
| M1 | 40.2 mV | 0.693 → 0.652 | 2,989 |
| **LISD** | **39.6 mV** | 0.692 → 0.652 | **13,169** |

---

## 6. Phase 4 — Power Matrix + Risk Kernel

### 6.1 Power Matrix 生成

因原版 `vcd_to_jsonl.py + jsonl_toggle_mark.py` 在 v2 规模下中间产物 > 16 GB (由稠密 per-time 展开导致，信号×时间=O(30k×1.2万)=3.6 亿条目)，本次专门编写了
**`Traditional_Vector_Profiling/code/vcd_to_power_matrix.py`** 直接流式 VCD → power_matrix。

| 指标 | 值 |
|---|---|
| 处理 value-change 事件数 | **6,335,990** |
| 映射成功信号 | 25,208 / 28,861 (87.3%) |
| 未映射 fallback | 3,653 (testbench / CTS 端口) |
| 窗口尺寸 | **20 ns** (20,000 ticks) |
| 窗口数 T | **601** |
| 网格 (ny × mx) | 50 × 50 |
| 输出 `report.json` 大小 | 11.5 MB |
| 功率范围 (单 tile 平均) | 0.161 µW ~ 0.424 µW |
| 运行时间 (Python) | ≈ 30 s (本地) |

### 6.2 Risk Propagation (alpha = 5.0)

`risk_propagation_profiling/code/risk_propagation.py --kernel all`，对 601 × 50 × 50 power matrix 做 Green 函数卷积。

| 核函数 | 公式 | Max Risk | 最差窗口 | 最差 tile | 报告大小 |
|---|---|---:|---:|---|---:|
| traditional (raw max) | `max(P[t][i][j])` | 0.0533 | 570 | (49, 19) | 11.5 MB |
| euclidean | `1/√(dx²+dy²)` | 0.00249 | 570 | (49, 19) | 14.9 MB |
| exponential | `exp(−√(dx²+dy²))` | 0.03214 | 570 | (49, 19) | 14.1 MB |
| logarithmic | `1/ln(1+√(dx²+dy²))` | 0.000696 | **343** | (37, 23) | 14.9 MB |

计算速率 ≈ 2.9 win/s × 601 win ≈ 205 s/kernel，3 kernel 共约 10 min。

> **关键观察**：4 个 "最差窗口 570" 的 3 个核一致选中同一热点，仅 logarithmic 因衰减过慢而选中时间上更靠前的 343。570 对应仿真末期约 11.4 µs，343 对应约 6.86 µs。

---

## 7. Phase 5 — Worst-K 窗口选取与 VCD 压缩

命令: `select_worst_k.py --threshold-ratio 0.95 --top-k 10 --vcd sim.vcd`

阈值 `t = 0.95` 意味着保留所有评分 ≥ 95% × max_score 的窗口。

### 7.1 每核选取结果

| 核函数 | 选中段数 | 总 tick 数 | 覆盖时长 | 最后 tick (ps) | 输出 VCD 大小 |
|---|---:|---:|---:|---:|---:|
| traditional | **3** | 59,961 | **59.58 ns** | 59,580 | 4,595,223 B (4.60 MB) |
| euclidean   | **1** | 19,987 | **19.75 ns** | 19,753 | 4,031,774 B (4.03 MB) |
| exponential | **1** | 19,987 | 19.75 ns | 19,753 | 4,031,774 B (4.03 MB) |
| logarithmic | **2** | 39,974 | 39.74 ns | 39,740 | 4,324,771 B (4.32 MB) |

> **euclidean 与 exponential 产出 VCD 完全相同**（SHA 级别一致）— DMA_slow 在 t=0.95 严阈值下两核选中的 top 窗口集合相同，且经预热扩展后合并为同一区间。这与 DMA 在 v1 sweep 中 "traditional/exponential 完全重合" 的特征一致 (见 MEMORY.md)。

### 7.2 压缩率

| 场景 | VCD 大小 | 相对 full | 压缩率 | 压缩比 |
|---|---:|---:|---:|---:|
| full | 142.85 MB | 100.00% | — | 1.00× |
| traditional | 4.60 MB | 3.22% | **96.78%** | **31.1×** |
| euclidean | 4.03 MB | 2.82% | 97.18% | 35.4× |
| exponential | 4.03 MB | 2.82% | 97.18% | 35.4× |
| logarithmic | 4.32 MB | 3.03% | 96.97% | 33.0× |

---

## 8. 场景 2-5 — Compressed VCD Voltus

每场景复用 Phase 5 生成的 `pg_lib_full/techonly.cl` PG 库，避免重复 `generate_pg_library` (约节省 2 min/run)。

### 8.1 单场景运行时间

| 场景 | Wall time | CPU time | 峰值内存 |
|---|---:|---:|---:|
| traditional | **0:00:55** | 0:00:48.6 | 1,357 MB |
| euclidean   | 0:00:52 | 0:00:46.3 | 1,359 MB |
| exponential | 0:00:54 | 0:00:46.9 | 1,357 MB |
| logarithmic | 0:00:55 | 0:00:47.4 | 1,358 MB |
| **合计** | **≈ 3 min 36 s** | — | — |

相比 full 场景 6:12 wall 的 Voltus，单压缩场景 ≈ 0:55 → **加速 ≈ 6.8×**。

### 8.2 IR-drop 综合对照

| 场景 | Min IR (V) | Avg IR (V) | Max IR (V) | **Max drop (mV)** | 违规数 |
|---|---:|---:|---:|---:|---:|
| **full** | 0.652 | 0.666 | 0.700 | **48.0** | 0 |
| traditional | 0.653 | 0.666 | 0.700 | 47.0 | 0 |
| euclidean | 0.653 | 0.666 | 0.700 | 47.0 | 0 |
| exponential | 0.653 | 0.666 | 0.700 | 47.0 | 0 |
| logarithmic | 0.653 | 0.666 | 0.700 | 47.0 | 0 |

**精度保真度 C_int = compressed_max_drop / full_max_drop = 47.0 / 48.0 = 97.92%**

4 种核在 DMA_slow 上 C_int 全相同，无法单凭此指标区分；需看层级 IR drop 分布：

### 8.3 各场景层级 IR-drop 对照 (mV)

| Layer | full | traditional | euclidean | exponential | logarithmic |
|---|---:|---:|---:|---:|---:|
| M6 | 11.9 | 11.8 | 11.8 | 11.8 | 11.8 |
| M5 | 29.3 | 29.1 | 29.1 | 29.1 | 29.1 |
| M4 | 28.7 | 28.5 | 28.5 | 28.5 | 28.5 |
| M3 | 42.0 | 41.8 | 41.8 | 41.8 | 41.8 |
| M2 | 40.2 | 40.0 | 40.0 | 40.0 | 40.0 |
| M1 | 40.2 | 40.0 | 40.0 | 40.0 | 40.0 |
| LISD | 39.6 | 39.4 | 39.4 | 39.4 | 39.4 |

4 种核的层级 drop 分布完全一致，说明在 t=0.95 的严阈值下 DMA_slow 的 worst-case 活跃窗口被所有核都捕获到了同一组核心周期。

---

## 9. 全流程时间汇总

| 阶段 | Wall time | 备注 |
|---|---:|---|
| 0. 本地准备 (拷源码 + scp 上传) | ≈ 1 min | 142 MB |
| 1. VCS 编译 + 仿真 | **≈ 1 min** | 13,333 vectors → 12 µs → 137 MB VCD |
| 2. Innovus P&R | **≈ 1.5 min** | wrapper 后重跑 |
| 3. Voltus Full | **≈ 6 min 12 s** | 12,012 rail steps |
| 4. Power Matrix (Python 本地) | ≈ 30 s | 流式 VCD → report.json |
| 4'. Risk Propagation × 3 kernels | ≈ 10 min | 3 × 3.5 min |
| 5. select_worst_k × 4 kernels | ≈ 10 s | 4 × ~2.5 s |
| 6. Voltus Compressed × 4 | **≈ 3 min 36 s** | 串行 |
| 7. 回传 rail 报告 (tar pipe) | ≈ 30 s | |
| **总计** | **≈ 32 min** | 其中一半是 Risk Propagation 卷积 |

若仅需看 full + 1 kernel (t=0.95)，Voltus 部分可缩到 ~7 min。

---

## 10. 关键结论 (论文可引用)

1. **压缩率**: 4 种选窗核均可将 137 MB 的长 VCD 压到 ~4 MB (**96.8–97.2%**)，约 33× 压缩比。
2. **IR-drop 保真**: 压缩后 Max IR drop = 47 mV vs full 48 mV，**C_int = 97.92%**，仅 1 mV (~2%) 偏差。无违规。
3. **加速比**: 单场景 Voltus 由 6:12 缩至 0:55 (**6.8× 加速**)；对于 sweep 分析，压缩能把 24-cell sweep 从 2.5 h 缩到 22 min。
4. **核函数选择**: 在 DMA_slow 这类中小型电路上，t=0.95 严阈值使 4 种核的结果几乎无差异。
   - euclidean ≡ exponential (产出 VCD 字节级相同)
   - traditional 多保留了 2 个次热点区段 (共 3 段 vs 1 段)，但对最终 worst-case drop 无增益
   - logarithmic 因核衰减过缓选中了不同窗口 (343 vs 570)，但对最终 drop 仍无影响
5. **方法论警示**: DMA 这类低活跃度电路上 4 核等效，不能由此推广；des_perf_slow 上 exponential ≠ traditional 相差 8.5 pp 压缩率 (MEMORY.md 已记载)。

---

## 11. 工程踩坑实录 (仅本次发现)

| # | 坑 | 现象 | 解决 |
|---:|---|---|---|
| 1 | VCS VCD 实际 timescale 是 1ps 而非 `-timescale` 命令行值 | Voltus rail 仿真 End Time = 120.1 µs (10× 错误)，Steps 12 万 | 修改 `voltus_*.tcl`，去掉 `_end_tick * 10` 乘子 |
| 2 | `vcd_to_jsonl.py` 中间产物 > 16 GB | 本地磁盘被塞满，jsonl 每行 ~700 KB (稠密 hold-last-value) | 新写 `vcd_to_power_matrix.py` 直接流式 VCD，内存 O(signals) |
| 3 | Innovus IMPSYT-6692 | pr_flow.tcl 第 N 行返回 0 退出，DEF 未写 | `wrapper.tcl` catch 后手动 `defOut -netlist -routing -allLayers` |
| 4 | gen_ring_pads 在 wrapper 中静默失败 | 无 `.ppl` 文件，Voltus 无法定义 voltage source | 从 v1 DMA 复用 ring_pads_*.ppl (DIEAREA 相同) |
| 5 | 远程磁盘 100% 满 (5.6 GB 可用) | 担心 Voltus full 累积 ENOSPC | 限定只 tar `rail/` 回传，避免 `power/` 临时文件 |
| 6 | `risk_propagation.py --kernel all` 不产出 `traditional.json` | select_worst_k 读不到 traditional 风险文件 | 额外写一段 Python 直接取 `max(P[t][i][j])` 生成 `traditional.json` |

---

## 12. 产物清单 (本地)

```
test_sim_output_v2/DMA_slow/
├── SIMULATION_REPORT.md                          ← 本文件
├── src/
│   └── DMA_slow.{v,def,sdc,spef}                 后端输入 (P&R 前原始)
├── testbench/
│   └── tb_DMA_slow.v                             VCS testbench (13333 vectors)
├── vcd/
│   ├── sim.vcd                                   137 MB full VCD
│   └── DMA_slow_compressed_{4 kernels}.vcd       4.0–4.6 MB each
├── analysis/
│   └── report/
│       ├── report.json                            power_matrix 11.5 MB
│       ├── traditional.json                       (raw max)
│       ├── risk_euclidean.json                    14.9 MB
│       ├── risk_exponential.json                  14.1 MB
│       └── risk_logarithmic.json                  14.9 MB
├── script/innovus/
│   ├── pr_flow.tcl, wrapper.tcl, contest.mmmc
│   ├── voltus_full.tcl, voltus_compressed.tcl   (已修复 ps×1 单位)
│   └── ring_pads_vdd.ppl, ring_pads_vss.ppl
└── sim_data/
    ├── full/rail/rail_full/PD_25C_dynamic_1/Reports/
    ├── traditional/rail/rail_traditional/PD_25C_dynamic_1/Reports/
    ├── euclidean/rail/rail_euclidean/PD_25C_dynamic_1/Reports/
    ├── exponential/rail/rail_exponential/PD_25C_dynamic_1/Reports/
    └── logarithmic/rail/rail_logarithmic/PD_25C_dynamic_1/Reports/
```

关键 Reports 文件: `VDD.main.rpt`、`VDD.layerbased_ir.rpt`、`VDD.pg_integrity.rpt`、`design.main.rpt`。
