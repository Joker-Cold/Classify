# 测试电路仿真输出

VCD 功耗分析工具链的多电路测试框架。对 5 个不同规模/类型的电路进行完整的
**RTL → 综合 → 布局布线 → VCD 仿真 → Voltus 功耗/IR Drop 分析 → 覆盖率评估** 流程。

> 参考流程：`F:\GraduatePrj\refer\EDA工具快速上手指南：从RTL到DVD分析 - CC98论坛.md`
> 参考实例：`F:\GraduatePrj\Classify\test_circuit\demo\benchmark\des_demo`（完整可运行的 des3 示例）

## 电路概览

| 序号 | 目录 | 电路名称 | 规模 (cells) | 类型 | 来源 |
|------|------|---------|-------------|------|------|
| 1 | `des_demo/` | DES3 加密核 | ~64K | 加密核 (Crypto) | OpenCores + asap7 (demo 参考电路) |
| 2 | `DMA_slow/` | DMA 控制器 | 25K | 存储控制器 (Datapath+Control) | ISPD2012 基准 |
| 3 | `des_perf_slow/` | DES Performance | 111K | 加密数据通路 (Crypto) | ISPD2012 基准 |
| 4 | `vga_lcd_slow/` | VGA/LCD 控制器 | 165K | 显示控制器 (Display) | ISPD2012 基准 |
| 5 | `leon3mp_slow/` | LEON3 SPARC CPU | 649K | 处理器 (CPU) | ISPD2012 基准 |

ISPD2012 电路均选用 `_slow` 变体（宽松时钟约束），仿真更稳定。

## 工具版本

| 工具 | 版本 | 用途 |
|------|------|------|
| Genus | v19（demo）/ v20（服务器） | RTL 综合 |
| Innovus | v19（demo）/ v20（服务器） | Floorplan / Place / Route / 寄生提取 |
| VCS | 2020 | RTL/门级仿真，生成 VCD |
| Voltus | 集成于 Innovus | Power & Rail (IR Drop) 分析 |

工艺库：`asap7sc7p5t_28`（7nm 开源工艺，见 `test_circuit/demo/{lib,lef,techlef,qrc}`）。
ISPD2012 电路使用混合物理后端：ASAP7 tech LEF + 自生成 contest cell LEF（详见 `../docs/Part4.md`）。

## 目录结构规范

参照 `test_circuit/demo/benchmark/des_demo` 的组织方式，每个电路目录按以下标准结构组织：

```
{circuit}/
├── src/                            # 源文件路径记录
│   └── README.md                   # ISPD2012: 指向外部网表/SDC/SPEF；远端服务器上同时含源文件副本
├── testbench/                      # testbench 文件 (tb_*.v)
├── script/                         # EDA 脚本
│   ├── run_all.sh                  # 驱动脚本：P&R → Voltus(full) → Voltus(compressed)
│   └── innovus/                    # Innovus/Voltus tcl 脚本（对齐 demo/script/innovus）
│       ├── pr_flow.tcl             # Floorplan + Place + Route（ISPD2012 无 RTL，跳过 Genus）
│       ├── voltus_full.tcl         # Voltus 功耗 + Rail，对完整 VCD
│       ├── voltus_compressed.tcl   # Voltus 功耗 + Rail，对压缩 VCD
│       └── contest.mmmc            # MMMC 视图配置
├── vcd/                            # VCS 仿真波形（远端服务器生成，拷回本地）
│   ├── sim.vcd                     # 原始完整 VCD
│   └── {circuit}_compressed_*.vcd  # 各算法压缩后的 VCD（traditional / risk_propagation）
├── sim_data/                       # Voltus 对不同 VCD 的运行结果（对比实验）
│   ├── full/                       # 完整 VCD 基准
│   │   ├── power/
│   │   └── rail/{VDD,VSS}/
│   ├── traditional/                # Traditional_Vector_Profiling 选窗
│   │   ├── power/
│   │   └── rail/{VDD,VSS}/
│   └── risk_propagation/           # risk_propagation_profiling 选窗
│       ├── power/
│       └── rail/{VDD,VSS}/
└── Makefile                        # Python 分析 + 覆盖率评估自动化

# 仅在 Python 分析运行后生成（按需）：
#   analysis/{toggles.jsonl, power_matrix.json, report.json, coverage/*.csv}
```

> **与 demo 的差异**：demo（`test_circuit/demo/benchmark/des_demo`）包含 `rtl/`、`sdc/`、`netlist/`、`db/` 和 `script/genus/`，因为它从 RTL 出发完整走流程；而 ISPD2012 电路是**预综合网表**，故省略 `rtl/`、`sdc/`、`netlist/`、`script/genus/`，把源文件路径写入 `src/README.md` 指向外部。

## 仿真流程（对齐 CC98 指南 + demo 实例）

### Stage 1：Synthesis（综合） — *ISPD2012 电路跳过*

**仅 demo 需要**。ISPD2012 电路已提供预综合网表，直接进入 Stage 2。

demo 流程：
```bash
cd test_circuit/demo/benchmark/des_demo/script/genus
genus -f genus.tcl
```

### Stage 2：Floorplan & Place & Route（布局布线）

**输入**：网表（demo：`netlist/*.v`；ISPD2012：`src/` 下门级网表）、工艺库
**输出**：`db/{circuit}.def`、`db/{circuit}.v`、`db/{circuit}.enc` + `db/{circuit}.enc.dat/`

```bash
# ISPD2012 电路（本项目）：
cd {circuit}/script
bash run_all.sh            # 内部调用 innovus/pr_flow.tcl + innovus/voltus_*.tcl

# 或单独运行 P&R：
innovus -nowin -init script/innovus/pr_flow.tcl
```

参考 `demo/benchmark/des_demo/script/innovus/innovus.tcl`。

### Stage 2.5：SPEF 提取（Optional）

Innovus 环境中执行：

```tcl
rcOut -spef ../../db/{circuit}.spef
```

### Stage 3：VCD Dumping（VCS 仿真）

**输入**：Innovus 输出的门级网表 `db/{circuit}.v`、testbench、`db/{circuit}.spef`
**输出**：`vcd/sim.vcd`

```bash
# 共享脚本（所有 ISPD2012 电路）：
bash test_sim_output/scripts/run_vcs.sh {circuit}

# demo 参考：
cd test_circuit/demo/benchmark/des_demo/vcd && bash vcs.sh
```

VCS 需要 `-start` / `-end` 参数控制 dump 区间。

### Stage 4：Power & Rail Analysis（Voltus 功耗 / IR Drop 分析）

**输入**：Innovus 数据库 `db/{circuit}.enc`、VCD 波形
**输出**：`db/power/`、`db/rail_power/`（demo 风格）或 `sim_data/{full,traditional,risk_propagation}/{power,rail}/`（对比实验风格）

```bash
# ISPD2012 电路（本项目，Power + Rail 合并在一个 tcl 中）：
innovus -nowin -init {circuit}/script/innovus/voltus_full.tcl       # 对 full VCD
innovus -nowin -init {circuit}/script/innovus/voltus_compressed.tcl # 对压缩 VCD

# demo 参考（Power / Rail 分开）：
cd test_circuit/demo/benchmark/des_demo/script/innovus
innovus
  > restoreDesign ../../db/des3.enc
  > source ./power_analyze.tcl       # → db/power/avg
  > source ./rail_analyze.tcl        # → db/rail_power
```

**Voltus pad 文件格式**：4 列 `name x y layer`，坐标须在 ring 金属上。

#### 已知坑：Windows 写出的 VCD 带 CRLF 行尾 → Voltus 拒读

Python 在 Windows 下用 `open(path, 'w')` 默认的 `newline=None` 会把所有
`\n` 翻译成 `\r\n`。CRLF VCD 喂给 `read_activity_file` 会立刻报错：

```
** ERROR: (VOLTUS_POWR-1735):  [<vcd> line 3, col 6] syntax error
** ERROR: (VOLTUS_POWR-1151): Voltus Power Analysis was unable to complete
          during the processing of VCD.
```

该错误对 `voltus` 独立二进制、`innovus -init voltus_*.tcl` 包壳两种调用方式都一视同仁，
因为 VCD parser 是 Voltus 引擎内置的同一份代码。

**根治**：`worst_k_windows/code/select_worst_k.py` 写 VCD 时显式 `newline='\n'`：

```python
# splice_vcd_v2(): 强制 LF 以兼容 Voltus
with open(output_path, 'w', encoding='utf-8', newline='\n') as fout:
    ...
```

**已有 CRLF VCD 的应急处理**：上传后远端 `sed -i 's/\r$//' <vcd>`，
或本地跑 `bash worst_k_windows/code/regen_t08_all.sh` 一键重生成。

### Stage 5：对比实验（本项目核心）

对同一电路用三组 VCD 运行 Voltus，比较选窗算法的覆盖率：

```bash
make voltus-full            # 原始完整 VCD   → sim_data/full/{power,rail}/
make voltus-traditional     # 传统向量选窗   → sim_data/traditional/{power,rail}/
make voltus-risk            # risk 传播选窗 → sim_data/risk_propagation/{power,rail}/
```

### Stage 6：Python 分析 + 覆盖率评估（Docker grj-dev）

```bash
make analyze     # VCD → JSONL → Toggle → 功率矩阵 → 选窗 → 压缩
make coverage    # 对比 full vs traditional/risk_propagation 的覆盖率
make all         # 全流程
```

## sim_data 文件格式说明

### power/ 目录（Voltus 功耗分析输出）

| 文件 | 格式 | 说明 |
|------|------|------|
| `dynamic_VDD.ptiavg` | 二进制 (Cadence PTI) | VDD 平均电流波形 |
| `dynamic_VSS.ptiavg` | 二进制 (Cadence PTI) | VSS 平均电流波形 |
| `VDD.totalcurrent` | 文本 (Index Time Current) | VDD 时序电流数据 |
| `VDD.togglestats` | 文本 | Toggle 统计 |

### rail/ 目录（Voltus IR Drop 分析输出）

| 文件 | 格式 | 说明 |
|------|------|------|
| `VDD_VSS.iv` | 文本 (Voltus VERSION 3.0) | 实例级 IR/EIV 数据，含每个 cell 的电压降 |
| `VDD_VSS.worst.iv` | 文本 | 最差违例实例 |
| `design.main.rpt` | 文本 | 设计级 IR Drop 汇总 |
| `VDD/VDD.main.rpt` | 文本 | VDD 网络主报告（Vmin/Vavg/Vmax） |
| `VDD/VDD.layerbased_ir.rpt` | 文本 | 逐金属层 IR Drop 分布 |
| `VDD/VDD.pg_integrity.rpt` | 文本 | 电源网格完整性检查 |
| `VDD/*.gif` | 图像 | IR Drop 可视化（grid/iv/ir 等） |
| `VSS/` | 同上 | VSS 网络对应报告 |

## 可视化

以 GUI 形式启动 Innovus，导入 Power/Rail 分析结果可查看 DVD 热力图：

```bash
innovus
  > restoreDesign ../../db/{circuit}.enc
  > # File → Import → Power/Rail results
```

## 远程服务器执行

ISPD2012 电路的 Innovus v20 / Voltus 流程在远程服务器上运行（本地仅保存结果）：

```bash
ssh -p 2223 myzhu@10.98.193.24
cd ~/data/test_sim_output/{circuit}/
source /etc/profile
export LC_ALL=C
export LD_PRELOAD=...libstdc++.so.6     # 规避 Innovus v20 locale crash
```

Innovus v20 的已知问题及 workaround 详见 `../docs/Part4.md`：
- `optDesign` locale crash → wrapper.tcl + LD_PRELOAD
- `ccopt` 无 buffer 单元 → `suppressMessage` + `catch`
- IMPSYT-6692 → wrapper.tcl `catch` 后手动 `defOut`

## 批量运行

```bash
./run_all.sh          # 对所有电路顺序执行 Stage 1 ~ Stage 6
```

## 当前进度（2026-04-15 更新）

| 电路 | Synthesis | P&R | VCD | Voltus full | traditional | risk_prop | Hotspot Compare |
|------|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| des_demo        | ✅ | ✅ | ✅ | ✅ | —  | —  | — |
| DMA_slow        | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| des_perf_slow   | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| vga_lcd_slow    | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| leon3mp_slow    | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

**全部 4 个 ISPD2012 电路完成三路 Voltus（full / traditional / risk_propagation）
对比与 top-K 热点分析。** 汇总与效率分析分别见 `analysis_summary.md`
和 `runtime_efficiency.md`。

## 实验结果速览（见对应文档）

### 精度（`analysis_summary.md`）

| 电路 | Worst drop (full) | C_int (trad / risk) | 最佳 risk Jaccard |
|------|------:|:--:|:--:|
| DMA_slow      |  103.42 mV  | 99.97 % / 99.97 % | 0.65 @ k=500 |
| des_perf_slow |  447.21 mV  | 99.30 % / 97.81 % | 0.15 @ k=500 |
| vga_lcd_slow  |  640.58 mV  | 99.81 % / 99.84 % | 0.25 @ k=10  |
| leon3mp_slow  | 3582.98 mV ¹ | 99.88 % / 99.73 % | 0.30 @ k=50  |

¹ leon3mp worst drop 远超 0.7 V 供电电压本身，因 ASAP7 tech LEF 的 PG 网络
对 649K 实例严重欠饱和（仅 8 个 pad、无 bump 数组）。此为基准设计本身的
局限，不影响算法对比有效性。

### 效率（`runtime_efficiency.md`）

所有 Voltus run 在同一 host `hzhb-Super-Server`（Intel Xeon Platinum 8475B /
528 GB RAM）以 `setMultiCpuUsage -localCpu 4` 跑。4 核 Voltus 工况下：

| 电路 | full Innovus Wall / CPU | compressed Wall / CPU (trad) | **端到端加速 (CPU)** |
|------|:--:|:--:|:--:|
| DMA_slow      |  (约 1 min)         |   —    |  ~1.4 × |
| des_perf_slow | **1:57 / 3:19**    | 1:26 / 1:51 | **1.79 ×** |
| vga_lcd_slow  | 约 2 min            | 1:32 / 2:05 | ~1.5 × |
| leon3mp_slow  | **5:14 / 14:55**   | **3:46 / 7:28** | **2.00 ×** |

**关键点**：`design.main.rpt` 只记录 Rail 子阶段（111 s Wall @ leon3mp-full），
而真正耗时的 "Writing Current Files"（Power 阶段，与 VCD 时间线性相关）
在 leon3mp full 上吃掉 **CPU 4 m 52 s**。压缩 VCD 将其砍到 16 s（**≈20 ×**），
Dynamic Rail Simulation 亦砍到 ~6 s（**≈14 ×**）—— 这两个计算核心合并
节省 **~10 ×** CPU，稀释固定开销后端到端仍得 **2 × CPU / 1.4 × Wall**。

## 相关产物清单

每个电路下：
- `sim_data/{full,traditional,risk_propagation}/rail/` — `VDD_VSS.iv`、
  `Reports/design.main.rpt`、`Reports/VDD/*.rpt` + `*.gif` 热力图
- `analysis/hotspot_compare.{json,html}` — 三路方法 top-K 热点并排 Plotly 可视化
- `analysis/{toggles.jsonl, power_matrix.json, report/*.json, vcd/worst_k_*.vcd}`
  — Python 选窗中间数据

顶层汇总文档：
- `analysis_summary.md` — 精度 & Jaccard 对比
- `runtime_efficiency.md` — 阶段级耗时分解 & 加速比
- `../docs/Part4.md` — ISPD2012 混合后端 + Innovus v20 workaround 备忘

## 压缩率-精度扫描经验 (Phase 1/2, 2026-04-16)

**矩阵**：4 kernel × 6 threshold = 24 cells/电路。产物放在 `{circuit}/analysis/{sweep_results.csv, sweep_pareto.html, sweep_report.md}`。

### 流水线三件套（结构同构，电路间只需换名字）
- **本地 VCD 再生**：`worst_k_windows/code/sweep_{circuit}.sh` — 调 `select_worst_k.py` 产 24 个 `{circuit}_hotspot_t{T}_{kernel}.vcd`（LF 行尾已强制）。
- **远程 Voltus 扫描**：`{circuit}/script/run_sweep_remote.sh` — `setsid + nohup` 启动，`voltus_hotspot.tcl` 读 `METHOD`+`THRESH` env var；`skip-existing` 基于 rail 报告存在性。
- **本地聚合**：`{circuit}/analysis/aggregate_sweep.py` — 解析 `VDD_VSS.iv`/`VDD.main.rpt`/`VDD.layerbased_ir.rpt`，算 C_int / Jaccard@K / layer ratio，导 CSV + Plotly + MD。

### 结论对比

| 电路 | Full worst drop | Pareto 甜点 | 压缩% | C_int | J@10 |
|---|---:|:---|:---:|:---:|:---:|
| DMA_slow (2.9K inst)     | 103.4 mV | traditional/exponential t=0.95 | 65% | 100.1% | 0.18 |
| DMA_slow (2.9K inst)     | 103.4 mV | logarithmic t=0.5 (Jaccard 王) | 90% | 99.7%  | 0.54 |
| des_perf_slow (49K inst) | 447.2 mV | **traditional t=0.7** | 78% | 100.4% | 0.33 |

### 关键坑 & 经验
1. **"剔除 exponential" 不普适**：DMA 上 exp≡traditional，des_perf 上两者在 t=0.6 压缩率差 8.5pp — kernel 等价性受功率矩阵稀疏度影响，跨电路需独立验证。
2. **电路规模 ↑ ⇒ Jaccard ↓**：49K 实例的 des_perf J@10 峰值仅 0.33（DMA 0.54）。Top-K 静态匹配对大电路不公平，C_int 更具稳健性。
3. **ENOSPC 磁盘坑**：EDA 服务器 /（916G）常年 100% 满，des_perf 跑到 t=0.95 logarithmic 时 Voltus 报 `VOLTUS_POWR-1151 errno 28`。清理策略：完成 cell 的 `sim_data/t*/power/` 可删（~900 MB/电路）、`logs/sweep/run_t*/` 工作目录可删；`rail/.../Reports/` 必保。
4. **VCD 大小 ≠ 压缩率单调性的代理**：`logarithmic t=0.95` 可能只选出几百实例、VCD 极小但 C_int 也崩（DMA 97.3% / des_perf 93%）— 高阈值 × 空间扩散核的组合在小电路尤其脆弱。
5. **risk_propagation.py 输出坑**：脚本内部 `os.path.join(args.output_dir, 'report', ...)`，传 `--output-dir report/` 会变 `report/report/risk_*.json`。传父目录 `analysis/` 即可。
6. **exp 核的自权重 alpha=5** 意味着中心 tile 权重是临位 exp(-1)≈0.37 的 13 倍 — 窗口排序里自身 toggle 权重压倒空间项；当功率图稀疏时退化为 traditional，不稀疏时显著发散。
