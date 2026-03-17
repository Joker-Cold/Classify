# 文件说明文档


**结果数据输出目录**
- **`db/`**: 工具生成的数据库与结果（DEF/**SPEF**/功耗分析/电压降分析等）。
  - **[db/des3.v](db/des3.v#L1-L10)**: 布局布线后的Verilog文件。
  - `db/power/avg`为avg模式下的功耗分析结果。
  - `db/rail_power/PD_25C_dynamic_1` 为电压降分析结果
  - `db/des3.enc.dat/libs/mmmc` 为所使用的工艺库

**RTL（行为/结构代码）**
- `rtl/`

**综合（Synthesis）结果**
- **[netlist/des3_netlist.v](netlist/des3_netlist.v#L1-L6)**: Genus 合成输出的门级 netlist。

**约束 / 工具脚本**
- **[sdc/des3.sdc](sdc/des3.sdc#L1-L16)**: 时序约束文件。
- **`script/genus/genus.tcl`**: Genus 综合流程脚本（读取 RTL、生成 netlist，输出路径为 `netlist/des3_netlist.v`）。参见 [genus.tcl](script/genus/genus.tcl#L1-L12)。
- **`script/innovus/innovus.tcl`**: Innovus 布局布线脚本（floorplan、power 网格、引脚布局等；含 ASAP7 相关设置）。

**VCD生成有关脚本及结果**
- **[testbench/des3_test_po_vcd.v](testbench/des3_test_po_vcd.v#L1-L8)**: 仿真测试平台，包含多个测试向量、时钟生成并输出 `test.vcd`。
- **[vcd/test.vcd](vcd/test.vcd)**: 仿真生成的 **VCD** 波形文件（二进制/文本大文件，直接打开或用波形查看工具分析）。
- **`vcd/vcs.sh`**: 输出VCD文件的命令脚本。
