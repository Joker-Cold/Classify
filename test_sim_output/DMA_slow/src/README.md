# DMA_slow 源文件

## 电路信息
- **名称**: DMA 直接存储访问控制器
- **规模**: 25,301 cells (23,109 组合 + 2,192 时序)
- **I/O**: 683 inputs / 276 outputs
- **来源**: Faraday Technology Corporation (IWLS 2005 / ISPD 2012)
- **类型**: 存储控制器，Datapath + Control

## 源文件路径

| 文件 | 路径 |
|------|------|
| 门级网表 | `Classify/test_circuit/ispd2012/DMA_slow/DMA_slow.v` (2.1 MB) |
| SDC | `Classify/test_circuit/ispd2012/DMA_slow/DMA_slow.sdc` |
| SPEF | `Classify/test_circuit/ispd2012/DMA_slow/DMA_slow.spef` |
| 工艺库 | `Classify/test_circuit/ispd2012/lib/contest.lib` (331 cell types) |

## 注意
- 门级网表，无 RTL 源码
- 需自行编写 testbench 或提供 VCD
- 无 DEF 文件，需通过 P&R 生成（或跳过空间分析）
