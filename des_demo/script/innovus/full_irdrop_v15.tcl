#===================================================
# 完整 IR Drop 分析流程（适配 Innovus v15）
# 将 VCD 分为 5 个时间窗口，依次进行功耗 + IR Drop 分析
# VCD 总时长: 11850ns (timescale 10ps, 最后时间戳 #1185000)
#===================================================

# Step 1: 加载设计 (只做一次)
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
setMultiCpuUsage -localCpu 4

# Step 2: 生成 PG Library (只做一次)
set_pg_library_mode -celltype techonly \
    -extraction_tech_file ../../db/des3.enc.dat/libs/mmmc/rc_typ_25/qrcTechFile_typ03_scaled4xV06
generate_pg_library -output ./des3_pg_v15

# Step 3: 循环 5 个时间窗口，依次功耗分析 + IR Drop 分析
set windows {
    {0ns     2370ns}
    {2370ns  4740ns}
    {4740ns  7110ns}
    {7110ns  9480ns}
    {9480ns  11850ns}
}

set idx 0
foreach win $windows {
    incr idx
    set t_start [lindex $win 0]
    set t_end   [lindex $win 1]
    puts "========================================"
    puts "=== Window $idx / 5: $t_start ~ $t_end ==="
    puts "========================================"

    # --- 功耗分析 ---
    set_power_analysis_mode -reset
    set_power_analysis_mode \
        -method dynamic_vectorbased \
        -create_binary_db true \
        -current_generation_method avg
    read_activity_file -format VCD ../../vcd/test.vcd \
        -scope test/u0 \
        -start $t_start \
        -end $t_end
    set_dynamic_power_simulation -resolution 1ns
    report_power -o ../../db/power/avg_v15_win${idx}

    # --- IR Drop 分析 ---
    set_pg_nets -net VDD -voltage 0.7 -threshold 0.651
    set_pg_nets -net VSS -voltage 0   -threshold 0.1
    set_power_pads -net VDD -format xy -file ./ring_pads_vdd.ppl
    set_power_pads -net VSS -format xy -file ./ring_pads_vss.ppl
    set_power_data -format current \
        [list ../../db/power/avg_v15_win${idx}/dynamic_VDD.ptiavg \
              ../../db/power/avg_v15_win${idx}/dynamic_VSS.ptiavg]
    set_rail_analysis_mode \
        -method dynamic \
        -accuracy xd \
        -power_grid_library ./des3_pg_v15/techonly.cl \
        -limit_number_of_steps false
    set_rail_analysis_domain -name PD -pwrnets VDD -gndnets VSS
    analyze_rail -type domain -output ../../db/rail_power_v15_win${idx} PD

    puts "=== Window $idx done ==="
}

puts "========================================"
puts "=== All 5 windows completed ==="
puts "========================================"
