# des_demo 项目总结

## 设计概述

- **设计名称**: des3 (Triple DES 加密引擎)
- **工艺节点**: ASAP7 7nm FinFET
- **时钟频率**: 100 MHz (周期 10ns)
- **流水线深度**: 51 级 (输入到输出延迟 51 个时钟周期)
- **数据位宽**: 64-bit 加密/解密
- **密钥大小**: 3 × 56-bit (共 168 bit，3DES 标准)
- **功能**: 流水线化的 3DES 加密硬件加速器，支持加密和解密模式

---

## 目录结构与关键文件

### 1. rtl/ — RTL 源码 (12 个 Verilog 模块)

| 文件 | 作用 |
|------|------|
| **des3.v** | 顶层模块 — 3 级流水线: DES(key1) → DES(~key2) → DES(key3)，含密钥流水线寄存器 |
| **des.v** | 单级 DES 引擎 — 16 轮迭代，含初始/终止置换、密钥调度、L/R 寄存器链 |
| **crp.v** | Cipher Round Permutation — DES 核心轮函数 (S-box + 置换 + XOR) |
| **key_sel.v** | 密钥调度模块 — 从 56-bit 主密钥生成 16 个 48-bit 子密钥 |
| **sbox1.v ~ sbox8.v** | 8 个 S-Box 替换表 — 6-bit 输入 → 4-bit 输出的组合逻辑查找表 |

### 2. netlist/ — 综合后网表

| 文件 | 大小 | 作用 |
|------|------|------|
| **des3_netlist.v** | 5.0 MB (94K 行) | Genus 综合产出的门级网表，使用 ASAP7 标准单元 (OAI/AOI/NAND/NOR 等) |

### 3. sdc/ — 时序约束

| 文件 | 作用 |
|------|------|
| **des3.sdc** | 主约束文件 — 100 MHz 时钟, 输入/输出延迟 40%, 51 周期 multi-cycle path, 时钟不确定性 ±300ps(setup)/±150ps(hold) |
| **des3_new.sdc** | 备份/变体约束文件 |

### 4. testbench/ — 仿真激励

| 文件 | 作用 |
|------|------|
| **des3_test_po_vcd.v** | 门级仿真 testbench — 10 组测试向量 (加密+解密)，产生 test.vcd 波形，含 51 级移位寄存器匹配流水线延迟 |

### 5. script/ — EDA 流程脚本

#### script/genus/ (逻辑综合)

| 文件 | 作用 |
|------|------|
| **genus.tcl** | Genus 综合脚本 — 读入 12 个 RTL 文件 + ASAP7 库 (LVT/SLVT)，执行 syn_generic → syn_map → syn_opt |
| **genus.log** | 综合日志 (含面积/时序报告) |
| **fv/des3/read_libs.tcl** | 形式验证库加载脚本 |

#### script/innovus/ (布局布线)

| 文件 | 作用 |
|------|------|
| **innovus.tcl** | 主 P&R 脚本 (详见下方 TCL 详解) |
| **des3.mmmc** | 多模多角设置 — TT corner, rc_typ_25 RC 角, 25°C |
| **power_analyze.tcl** | 动态功耗分析 — VCD 驱动, 1ns 分辨率 |
| **rail_analyze.tcl** | IR Drop 分析 — 动态 xd 精度, VDD/VSS 域 |
| **load_design_v15.tcl** | v15 兼容设计加载 — 用 init_design + defIn 替代 restoreDesign |
| **full_irdrop_v15.tcl** | v15 一键脚本 — 设计加载 + 功耗分析 + IR Drop 分析全流程 |
| **.qor_metric.tcl** | QoR 指标记录 — Rail 分析结果的量化指标 |
| **des3.spef** | 寄生参数提取结果 (33 MB) |
| **innovus.cmd / cmd1~7** | 各阶段增量命令 (放置/CTS/布线等) |

### 6. db/ — 后端输出数据库

| 文件/目录 | 大小 | 作用 |
|-----------|------|------|
| **des3.def** | 37 MB | Design Exchange Format — 完整物理版图 (单元坐标、布线、电源网络拓扑) |
| **des3.spef** | 33 MB | SPEF 寄生参数 — 所有 net 的 RC 寄生，用于精确时序/功耗仿真 |
| **des3.v** | 6.1 MB | 布局布线后网表 — 含物理标注，可做 SDF 反标 |
| **des3.enc / des3.enc.dat/** | — | Innovus 数据库 (布线/放置/时钟树/电源等压缩数据) |
| **power/** | — | 功耗分析结果 (平均动态功耗) |
| **rail_power/** | — | IR Drop 分析结果 (电源网格电压降) |
| **rail_power_v15/** | — | IR Drop 分析结果 (v15 版本) |

### 7. vcd/ — VCS 仿真输出

| 文件 | 大小 | 作用 |
|------|------|------|
| **test.vcd** | 5.6 MB | 门级仿真 VCD 波形 — 10 组测试向量的全部信号翻转记录 |
| **vcs.sh** | 2.2 KB | VCS 编译+仿真脚本 — 编译门级网表 + testbench + ASAP7 库模型，带 SPEF 反标 |
| **simv** | 1.2 MB | VCS 编译产出的可执行文件 |
| **csrc/, simv.daidir/** | — | VCS 编译中间文件 (可忽略) |

---

## 完整设计流程

```
RTL (12 个 Verilog 模块)
    │
    ▼
逻辑综合 (Cadence Genus)
    • 输入: RTL + ASAP7 库 + des3.sdc
    • 流程: syn_generic → syn_map → syn_opt
    • 输出: des3_netlist.v (94K 行门级网表)
    │
    ▼
布局布线 (Cadence Innovus)
    • 输入: des3_netlist.v + des3.mmmc + innovus.tcl
    • 流程: Floorplan → 电源网格 → Placement → CTS → Route → 寄生提取
    • 输出: des3.def (37M) + des3.spef (33M) + des3.v (后端网表)
    │
    ▼
签核验证
    • 功耗分析: power_analyze.tcl → power/ 报告
    • IR Drop: rail_analyze.tcl → rail_power/ 结果 (Voltus)
    │
    ▼
门级仿真 (Synopsys VCS)
    • 输入: 后端 des3.v + des3.spef (SDF 反标) + testbench
    • 输出: test.vcd (5.6 MB 波形文件)
```

---

## TCL 脚本详解

### genus.tcl — 逻辑综合

```
输入: 12 个 RTL 文件 + 10 个 ASAP7 timing lib (LVT/SLVT) + 3 个 LEF + des3.sdc
流程: read_hdl → elaborate → read_sdc → syn_generic → syn_map → syn_opt → write_hdl
输出: ../../netlist/des3_netlist.v
```

关键配置：
- 库: ASAP7 LVT + SLVT (AO, INVBUF, OA, SEQ, SIMPLE 各两个变体)
- 约束: des3.sdc (100 MHz, 51-cycle MCP)

### innovus.tcl — 布局布线主流程

支持 Innovus v17-21，含条件分支处理版本差异。完整流程如下：

| 阶段 | 关键命令 | 说明 |
|------|---------|------|
| **初始化** | `init_design`, `setDesignMode -process 7` | 加载网表/库/约束，设 7nm 工艺 |
| **电源连接** | `globalNetConnect VDD/VSS` | 所有 instance 的 pgpin 连接 |
| **Floorplan** | `floorPlan` | 70% 利用率, 1:1 长宽比, 单元高度 1.08µm |
| **Well Tap** | `addWellTap` | TAPCELL 间距 12.96µm |
| **Pin 放置** | `editPin`, `legalizePin` | 输入引脚→左侧, 输出引脚→右侧, M3 层 |
| **电源环** | `addRing` | M7(上下) + M6(左右), 宽 2.176µm, 偏移 0.384µm |
| **M2 行轨** | `addStripe` | 每行标准单元的 VDD/VSS 水平轨, 宽 0.072µm |
| **M3 纵条** | `addStripe` | 垂直电源条, 宽 0.936µm, 间距 12.96µm |
| **M4 横条** | `addStripe` | 水平电源条, 宽 0.864µm, 间距 21.6µm |
| **电源布线** | `sroute` | M1-M7 堆叠 via 连接 |
| **放置** | `place_opt_design` | 放置 + 时序优化, setup/hold 目标 20ps |
| **Tie 单元** | `addTieHiLo` | 最大扇出 5, 使用 SLVT tie cell |
| **CTS** | `ccopt_design` | 时钟树综合 + 优化 |
| **布线** | `routeDesign` | 全局 + 详细布线 |
| **后优化** | `optDesign -postRoute` / `-hold` | OCV + SI 感知的时序优化 |
| **输出** | `defOut`, `saveNetlist`, `saveDesign` | DEF + Verilog + .enc 数据库 |

电源网格层次结构：
```
M7 ── 核心环 (top/bottom)
M6 ── 核心环 (left/right)
M4 ── 水平二级条纹 (0.864µm, 21.6µm 间距)
M3 ── 垂直一级条纹 (0.936µm, 12.96µm 间距)
M2 ── 行级水平轨 (0.072µm, 每行一对)
M1 ── 单元内布线, 通过 via 连接到上层
```

### des3.mmmc — 多模多角配置

单角分析 (非多 PVT 扫描)：
- **Library Set "tc"**: 10 个 ASAP7 TT corner timing lib
- **RC Corner "rc_typ_25"**: QRC 典型寄生模型 @ 25°C
- **Delay Corner "delay_tc"**: tc + rc_typ_25
- **Analysis View "view_tc"**: setup 和 hold 均使用同一 view

### power_analyze.tcl — 动态功耗分析

```tcl
set_power_analysis_mode -method dynamic_vectorbased \
    -power_grid_library ./des3_pg/techonly.cl \
    -create_binary_db true \
    -current_generation_method avg
read_activity_file -format VCD ../../vcd/test.vcd \
    -scope test/u0 -start 4000ns -end 5000ns
set_dynamic_power_simulation -resolution 1ns
report_power -o ../../db/power/avg
```

关键参数：
- VCD 范围: testbench 中 `test/u0` 实例, 4000-5000ns 时间窗口
- 时间分辨率: 1ns
- 输出: `.ptiavg` 格式的 VDD/VSS 电流波形

### rail_analyze.tcl — IR Drop 分析

```tcl
set_pg_nets -net VDD -voltage 0.7 -threshold 0.651   # 7% margin
set_pg_nets -net VSS -voltage 0   -threshold 0.1
set_power_pads -net VDD -format xy -file ./ring_pads_vdd.ppl
set_power_pads -net VSS -format xy -file ./ring_pads_vss.ppl
set_power_data -format current {dynamic_VDD.ptiavg dynamic_VSS.ptiavg}
set_rail_analysis_mode -method dynamic -accuracy xd \
    -power_grid_library ./des3_pg/techonly.cl
set_rail_analysis_domain -name PD -pwrnets VDD -gndnets VSS
analyze_rail -type domain -output ../../db/rail_power PD
```

输出: 电压热力图 (ir_linear.gif) + 详细报告 (.main.rpt)

### full_irdrop_v15.tcl — v15 一键全流程

整合了 3 个步骤，解决 v19→v15 兼容性问题：

```
Step 1: 设计加载 (init_design + defIn, 替代不兼容的 restoreDesign)
Step 2: 功耗分析 (set_power_analysis_mode -reset 去掉 v19 的 .cl 引用)
Step 3: IR Drop  (generate_pg_library 在 v15 中重新生成兼容的 PG Library)
```

### viewDefinition.tcl — 内嵌 MMMC (自动生成)

- 功能与 des3.mmmc 相同，但使用 `::IMEX::libVar` 相对路径
- 嵌入在 `.enc.dat` 中，用于 restoreDesign 时自动加载
- 所有库/QRC/SDC 文件均引用 .enc.dat 内部副本

---

## Innovus v15 兼容性问题与解决 (来自实操记录)

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| `restoreDesign` SEGV 崩溃 | `.enc.dat` 由 v19 生成，v15 无法解析 | 改用 `init_design` + `defIn` 从标准格式加载 |
| `techonly.cl` 版本不匹配 | v19 PG Library 格式版本 12, v15 只支持 3-8 | `generate_pg_library` 在 v15 中重新生成 |
| Rail 分析缺 `-power_grid_library` | v15 中该参数为必填 | 先 `generate_pg_library`, 再指定新生成的 .cl |
| `sfe.session` 解析失败 | v19 残留的 work/ 目录格式不兼容 | `file delete -force ./work` 后重跑 |

## IR Drop 分析结果 (v15 实测)

| 网络 | 标称电压 | 阈值 | 最大 IR Drop | 最差层 | 违例数 |
|------|---------|------|-------------|--------|--------|
| VDD | 0.700V | 0.651V | 33.16mV (4.74%) | M1 | 0 PASS |
| VSS | 0.000V | 0.100V | 31.92mV | M6 | 0 PASS |
| **VDD-VSS 联合** | — | — | **64mV (9.1%)** | — | **0 PASS** |

最低有效电压 0.636V, 平均 0.663V, VDD 最低 0.667V (距阈值 0.651V 有 16mV 裕量)。

---

## 与本项目(Classify)的关联

本项目的核心目标是对 VCD 文件进行最坏功耗窗口筛选。des_demo 提供了完整的物理后端数据：

- **test.vcd** → 信号翻转活动源数据
- **des3.spef** → 每条 net 的寄生电容 $C_k$ (功耗加权)
- **des3.def** → 每个 instance 的 $(x,y)$ 坐标 (空间区域划分)
- **des3_netlist.v / des3.v** → 逻辑连接关系 (互斥 net 约束推断)

这四类文件正好对应之前讨论的"基于多源文件的 VCD 测试向量覆盖率评估方案"中的全部输入。
