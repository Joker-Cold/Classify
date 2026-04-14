# leon3mp_slow 源文件

## 电路信息
- **名称**: LEON3 SPARC V8 处理器核
- **规模**: 649,191 cells (540,352 组合 + 108,839 时序)
- **I/O**: 254 inputs / 79 outputs
- **来源**: Gaisler Research (IWLS 2005 / ISPD 2012)
- **类型**: 完整 CPU 处理器（寄存器堆 + ALU + 乘法器 + Cache）

## 源文件路径

| 文件 | 路径 |
|------|------|
| 门级网表 | `Classify/test_circuit/ispd2012/leon3mp_slow/leon3mp_slow.v` (73 MB) |
| SDC | `Classify/test_circuit/ispd2012/leon3mp_slow/leon3mp_slow.sdc` |
| SPEF | `Classify/test_circuit/ispd2012/leon3mp_slow/leon3mp_slow.spef` |
| 工艺库 | `Classify/test_circuit/ispd2012/lib/contest.lib` (331 cell types) |

## 注意
- 最大规模电路（649K cells, 73MB 网表），仿真和分析耗时较长
- 门级网表，无 RTL 源码
- 需自行编写 testbench 或提供 VCD
- 无 DEF 文件
