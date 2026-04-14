# des_perf_slow 源文件

## 电路信息
- **名称**: DES Performance 加密数据通路
- **规模**: 111,229 cells (102,427 组合 + 8,802 时序)
- **I/O**: 234 inputs / 140 outputs
- **来源**: OpenCores (IWLS 2005 / ISPD 2012)
- **类型**: 加密数据通路，多级流水线

## 源文件路径

| 文件 | 路径 |
|------|------|
| 门级网表 | `Classify/test_circuit/ispd2012/des_perf_slow/des_perf_slow.v` (8.3 MB) |
| SDC | `Classify/test_circuit/ispd2012/des_perf_slow/des_perf_slow.sdc` |
| SPEF | `Classify/test_circuit/ispd2012/des_perf_slow/des_perf_slow.spef` |
| 工艺库 | `Classify/test_circuit/ispd2012/lib/contest.lib` (331 cell types) |

## 注意
- 与 des_demo 同为 DES 加密类电路，可交叉验证
- 门级网表，无 RTL 源码
- 需自行编写 testbench 或提供 VCD
- 无 DEF 文件
