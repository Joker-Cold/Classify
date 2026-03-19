#===================================================
# 补跑 IR Drop 分析 win3-5（win1/2 已成功）
# 修复: PPL 文件去掉注释行, 加 -limit_number_of_steps false
#===================================================

# Step 1: 加载设计
source load_design_v15.tcl

# Step 2: 生成 PG Library
set_pg_library_mode -celltype techonly \
    -extraction_tech_file ../../db/des3.enc.dat/libs/mmmc/rc_typ_25/qrcTechFile_typ03_scaled4xV06
generate_pg_library -output ./des3_pg_v15

# Step 3: 只跑 win3, win4, win5
foreach idx {3 4 5} {
    puts "========================================"
    puts "=== Rail Analysis Window $idx / 5 ==="
    puts "========================================"

    set_pg_nets -net VDD -voltage 0.7 -threshold 0.651
    set_pg_nets -net VSS -voltage 0   -threshold 0.1
    set_power_pads -net VDD -format xy -file ./ring_pads_vdd_clean.ppl
    set_power_pads -net VSS -format xy -file ./ring_pads_vss_clean.ppl
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

    puts "=== Window $idx rail done ==="
}

puts "========================================"
puts "=== Windows 3-5 rail completed ==="
puts "========================================"
