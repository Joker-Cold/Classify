#===================================================
# 算法选窗 IR Drop 分析（Innovus v20.10）
# Phase-Aware + Grid空间集中度 选出的 2 个 worst-case 窗口
# Window 1: 3790ns ~ 4390ns (600ns, Phase 1)
# Window 2: 9600ns ~ 10100ns (500ns, Phase 2)
# 使用已切割的 VCD（时间已重映射到 #0 起始）
#===================================================

# Step 1: 加载设计
set init_design_uniquify 1
set init_design_netlisttype Verilog
set init_design_settop 1
set init_top_cell des3
set init_verilog {../../db/des3.v}
set init_lef_file { \
    ../../db/des3.enc.dat/libs/lef/asap7_tech_4x_201209.lef \
    ../../db/des3.enc.dat/libs/lef/asap7sc7p5t_28_L_4x_220121a.lef \
    ../../db/des3.enc.dat/libs/lef/asap7sc7p5t_28_SL_4x_220121a.lef \
}
set init_pwr_net VDD
set init_gnd_net VSS
set init_mmmc_file ../../db/des3.enc.dat/viewDefinition.tcl
init_design
defIn ../../db/des3.def
globalNetConnect VDD -type pgpin -pin VDD -inst *
globalNetConnect VSS -type pgpin -pin VSS -inst *
setMultiCpuUsage -localCpu 8

# Step 2: 复用已有 PG Library（跳过 generate_pg_library）
# des3_pg_v20/ 已在之前的 full_irdrop_v20_full.tcl 中生成

# ===== Window 1: 3790ns ~ 4390ns (切片VCD: 0~640ns, 信号从40ns开始) =====
puts "========================================"
puts "=== Algo Window 1: 3790ns ~ 4390ns ==="
puts "========================================"

# --- 功耗分析 ---
set_power_analysis_mode -reset
set_power_analysis_mode \
    -method dynamic_vectorbased \
    -create_binary_db true \
    -current_generation_method avg
read_activity_file -format VCD ../../vcd/test_win1_algo.vcd \
    -scope test/u0 \
    -start 0ns \
    -end 640ns
set_dynamic_power_simulation -resolution 1ns
report_power -o ../../db/power/avg_v20_algo_win1

# --- IR Drop 分析 ---
set_pg_nets -net VDD -voltage 0.7 -threshold 0.651
set_pg_nets -net VSS -voltage 0   -threshold 0.1
set_power_pads -net VDD -format xy -file ./ring_pads_vdd_clean.ppl
set_power_pads -net VSS -format xy -file ./ring_pads_vss_clean.ppl
set_power_data -format current \
    [list ../../db/power/avg_v20_algo_win1/dynamic_VDD.ptiavg \
          ../../db/power/avg_v20_algo_win1/dynamic_VSS.ptiavg]
set_rail_analysis_mode \
    -method dynamic \
    -accuracy xd \
    -power_grid_library ./des3_pg_v20/techonly.cl \
    -limit_number_of_steps false
set_rail_analysis_domain -name PD -pwrnets VDD -gndnets VSS
analyze_rail -type domain -output ../../db/rail_power_v20_algo_win1 PD

puts "=== Algo Window 1 done ==="

# ===== Window 2: 9600ns ~ 10100ns (切片VCD: 0~550ns, 信号从50ns开始) =====
puts "========================================"
puts "=== Algo Window 2: 9600ns ~ 10100ns ==="
puts "========================================"

# --- 功耗分析 ---
set_power_analysis_mode -reset
set_power_analysis_mode \
    -method dynamic_vectorbased \
    -create_binary_db true \
    -current_generation_method avg
read_activity_file -format VCD ../../vcd/test_win2_algo.vcd \
    -scope test/u0 \
    -start 0ns \
    -end 550ns
set_dynamic_power_simulation -resolution 1ns
report_power -o ../../db/power/avg_v20_algo_win2

# --- IR Drop 分析 ---
set_pg_nets -net VDD -voltage 0.7 -threshold 0.651
set_pg_nets -net VSS -voltage 0   -threshold 0.1
set_power_pads -net VDD -format xy -file ./ring_pads_vdd_clean.ppl
set_power_pads -net VSS -format xy -file ./ring_pads_vss_clean.ppl
set_power_data -format current \
    [list ../../db/power/avg_v20_algo_win2/dynamic_VDD.ptiavg \
          ../../db/power/avg_v20_algo_win2/dynamic_VSS.ptiavg]
set_rail_analysis_mode \
    -method dynamic \
    -accuracy xd \
    -power_grid_library ./des3_pg_v20/techonly.cl \
    -limit_number_of_steps false
set_rail_analysis_domain -name PD -pwrnets VDD -gndnets VSS
analyze_rail -type domain -output ../../db/rail_power_v20_algo_win2 PD

puts "=== Algo Window 2 done ==="

puts "========================================"
puts "=== All algo windows completed ==="
puts "========================================"
exit
