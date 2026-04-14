# des_demo 源文件

## 电路信息
- **名称**: DES3 三重 DES 加密核
- **规模**: ~64K cells (ASAP7 7nm)
- **时钟**: 100 MHz (10ns period), 51-cycle multi-cycle path
- **I/O**: 320-bit input (3×key + plaintext + expected), 64-bit output

## 源文件路径

| 文件 | 路径 |
|------|------|
| RTL 源码 | `Classify/des_demo/rtl/` (des3.v, des.v, key_sel.v, sbox1-8.v, crp.v) |
| 综合网表 | `Classify/des_demo/netlist/des3_netlist.v` |
| 后端网表 | `Classify/des_demo/db/des3.v` |
| DEF | `Classify/des_demo/db/des3.def` |
| SPEF | `Classify/des_demo/db/des3.spef` |
| SDC | `Classify/des_demo/sdc/des3.sdc` |
| Testbench | `Classify/des_demo/testbench/des3_test_po_vcd.v` |
| 工艺库 | `Classify/des_demo/db/des3.enc.dat/libs/mmmc/` |

## 已有仿真数据
- VCD: `Classify/des_demo/vcd/test.vcd` (5.8 MB)
- Voltus 结果: `Classify/des_demo/db/sim_data/`
