# 测试电路仿真输出

VCD 功耗分析工具链的多电路测试框架。对 5 个不同规模/类型的电路进行完整的 VCD 压缩 → Voltus 功耗/IR Drop 仿真 → 覆盖率评估流程。

## 电路概览

| 序号 | 目录 | 电路名称 | 规模 (cells) | 类型 | 来源 |
|------|------|---------|-------------|------|------|
| 1 | `des_demo/` | DES3 加密核 | ~64K | 加密核 (Crypto) | `Classify/des_demo/`，已有完整数据 |
| 2 | `DMA_slow/` | DMA 控制器 | 25K | 存储控制器 (Datapath+Control) | ISPD2012 基准 |
| 3 | `des_perf_slow/` | DES Performance | 111K | 加密数据通路 (Crypto) | ISPD2012 基准 |
| 4 | `vga_lcd_slow/` | VGA/LCD 控制器 | 165K | 显示控制器 (Display) | ISPD2012 基准 |
| 5 | `leon3mp_slow/` | LEON3 SPARC CPU | 649K | 处理器 (CPU) | ISPD2012 基准 |

ISPD2012 电路均选用 `_slow` 变体（宽松时钟约束），仿真更稳定。

## 目录结构规范

每个电路目录按以下标准结构组织：

```
{circuit}/
├── src/                            # 源文件路径记录
│   └── README.md                   # 网表/SDC/SPEF 原始路径
├── testbench/                      # testbench 文件
├── vcd/                            # VCD 仿真波形
│   ├── sim.vcd                     # 原始完整 VCD
│   └── sim_compressed_*.vcd        # 各算法压缩后的 VCD
├── sim_data/                       # 远程服务器 Voltus 仿真结果
│   ├── full/                       # 完整 VCD 基准结果
│   │   ├── power/                  # 功耗分析
│   │   └── rail/                   # IR Drop 分析
│   ├── traditional/                # Traditional_Vector_Profiling 选窗结果
│   │   ├── power/
│   │   └── rail/
│   └── risk_propagation/           # risk_propagation_profiling 选窗结果
│       ├── power/
│       └── rail/
├── analysis/                       # Python 工具链分析结果
│   ├── toggles.jsonl               # toggle 统计
│   ├── power_matrix.json           # 功率矩阵 [T][ny][mx]
│   ├── report.json                 # 汇总报告
│   └── coverage/                   # 覆盖率评估
│       ├── coverage_tier1.csv
│       └── coverage_report.md
└── Makefile                        # 自动化脚本
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

## 仿真流程

### Stage 1: 准备
- 确认源文件路径（见各电路 `src/README.md`）
- 编写/放入 testbench 到 `testbench/`

### Stage 2: VCD 仿真（远程服务器 VCS）
```bash
# 在远程服务器上
cd {circuit}
make sim              # 编译 + 仿真 → vcd/sim.vcd
```

### Stage 3: Voltus 功耗/IR Drop 仿真（远程服务器）
```bash
# 对完整 VCD 运行 Voltus
make voltus-full      # → sim_data/full/{power,rail}/

# 用 Traditional_Vector_Profiling 选窗压缩，再跑 Voltus
make voltus-traditional   # → sim_data/traditional/{power,rail}/

# 用 risk_propagation_profiling 选窗压缩，再跑 Voltus
make voltus-risk          # → sim_data/risk_propagation/{power,rail}/
```

### Stage 4: Python 分析 + 覆盖率评估（Docker grj-dev）
```bash
make analyze          # VCD → JSONL → Toggle → 功率矩阵 → 选窗 → 压缩
make coverage         # 对比 full vs traditional/risk_propagation 的覆盖率
make all              # 全流程
```

## 批量运行
```bash
./run_all.sh          # 对所有电路顺序执行
```
