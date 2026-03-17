
  #===================================================
  # 适配 Innovus v15 的设计加载脚本
  #===================================================

  # 基本设置
  set init_design_uniquify 1
  set init_design_netlisttype Verilog
  set init_design_settop 1

  # 顶层模块
  set init_top_cell des3

  # 读入布局布线后的 Verilog 网表
  set init_verilog {../../db/des3.v}

  # 读入 LEF（工艺 + 标准单元）
  set init_lef_file { \
      ../../db/des3.enc.dat/libs/lef/asap7_tech_4x_201209.lef \
      ../../db/des3.enc.dat/libs/lef/asap7sc7p5t_28_L_4x_220121a.lef \
      ../../db/des3.enc.dat/libs/lef/asap7sc7p5t_28_SL_4x_220121a.lef \
  }

  # 电源/地网络
  set init_pwr_net VDD
  set init_gnd_net VSS

  # MMMC 配置（使用 viewDefinition.tcl）
  set init_mmmc_file ../../db/des3.enc.dat/viewDefinition.tcl

  # 初始化设计
  init_design

  # 读入 DEF（包含 floorplan + placement + routing）
  defIn ../../db/des3.def

  # 连接 PG pin
  globalNetConnect VDD -type pgpin -pin VDD -inst *
  globalNetConnect VSS -type pgpin -pin VSS -inst *

  # 设置多核
  setMultiCpuUsage -localCpu 8