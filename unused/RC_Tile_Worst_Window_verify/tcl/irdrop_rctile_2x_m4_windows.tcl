#===================================================
# RC-Tile m4 (beta-budget=10%) IR Drop - test_2x.vcd
# 9 windows, beta=9.41%, VCD: test_2x_rctile_m4.vcd
# spliced total: 2250 ns
# win01: orig 2350~2600ns   (cycle 47~51,  cluster edge)
# win02: orig 4150~4400ns   (cycle 83~87,  cluster-A)
# win03: orig 5450~5700ns   (cycle 109~113)
# win04: orig 14250~14500ns (cycle 285~289, near true worst)
# win05: orig 15250~15500ns (cycle 305~309, near true worst)
# win06: orig 15850~16100ns (cycle 317~321)
# win07: orig 16450~16700ns (cycle 329~333, argmax rank1)
# win08: orig 17050~17300ns (cycle 341~345)
# win09: orig 17650~17900ns (cycle 353~357)
#===================================================

set init_design_uniquify 1
set init_design_netlisttype Verilog
set init_design_settop 1
set init_top_cell des3
set init_verilog {../../db/des3.v}
set init_lef_file {
    ../../db/des3.enc.dat/libs/lef/asap7_tech_4x_201209.lef
    ../../db/des3.enc.dat/libs/lef/asap7sc7p5t_28_L_4x_220121a.lef
    ../../db/des3.enc.dat/libs/lef/asap7sc7p5t_28_SL_4x_220121a.lef
}
set init_pwr_net VDD
set init_gnd_net VSS
set init_mmmc_file ../../db/des3.enc.dat/viewDefinition.tcl
init_design
defIn ../../db/des3.def
globalNetConnect VDD -type pgpin -pin VDD -inst *
globalNetConnect VSS -type pgpin -pin VSS -inst *
setMultiCpuUsage -localCpu 8

set windows {
    {0.0    250.0}
    {250.0  500.0}
    {500.0  750.0}
    {750.0  1000.0}
    {1000.0 1250.0}
    {1250.0 1500.0}
    {1500.0 1750.0}
    {1750.0 2000.0}
    {2000.0 2250.0}
}

set idx 0
foreach win $windows {
    incr idx
    set t_s [lindex $win 0]
    set t_e [lindex $win 1]
    puts "=== 2x_m4 win[format %02d $idx]: spliced ${t_s}~${t_e}ns ==="
    set_power_analysis_mode -reset
    set_power_analysis_mode -method dynamic_vectorbased \
        -create_binary_db true -current_generation_method avg
    read_activity_file -format VCD ../../vcd/test_2x_rctile_m4.vcd \
        -scope test/u0 -start ${t_s}ns -end ${t_e}ns
    set_dynamic_power_simulation -resolution 1ns
    report_power -o ../../db/power/avg_v20_rctile_2x_m4_win[format %02d $idx]
    set_pg_nets -net VDD -voltage 0.7 -threshold 0.651
    set_pg_nets -net VSS -voltage 0   -threshold 0.1
    set_power_pads -net VDD -format xy -file ./ring_pads_vdd_clean.ppl
    set_power_pads -net VSS -format xy -file ./ring_pads_vss_clean.ppl
    set_power_data -format current [list \
        ../../db/power/avg_v20_rctile_2x_m4_win[format %02d $idx]/dynamic_VDD.ptiavg \
        ../../db/power/avg_v20_rctile_2x_m4_win[format %02d $idx]/dynamic_VSS.ptiavg]
    set_rail_analysis_mode -method dynamic -accuracy xd \
        -power_grid_library ./des3_pg_v20/techonly.cl \
        -limit_number_of_steps false
    set_rail_analysis_domain -name PD -pwrnets VDD -gndnets VSS
    analyze_rail -type domain \
        -output ../../db/rail_power_v20_rctile_2x_m4_win[format %02d $idx] PD
    puts "=== 2x_m4 win[format %02d $idx] done ==="
}

puts "=== All rctile_2x_m4 windows completed ==="
exit
