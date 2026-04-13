#===================================================
# spatial_temporal test_2x.vcd kt=200 top=1 warmup=5 mc=1
# 20 segments, beta=30.9%, VCD: compressed_2x_kt200_mc1.vcd
# spliced total: 7373.5 ns
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
    {0.0    357.75}
    {357.75  727.0}
    {727.0  1096.25}
    {1096.25 1465.5}
    {1465.5  1834.75}
    {1834.75 2204.0}
    {2204.0  2573.25}
    {2573.25 2942.5}
    {2942.5  3311.75}
    {3311.75 3681.0}
    {3681.0  4050.25}
    {4050.25 4419.5}
    {4419.5  4788.75}
    {4788.75 5158.0}
    {5158.0  5527.25}
    {5527.25 5896.5}
    {5896.5  6265.75}
    {6265.75 6635.0}
    {6635.0  7004.25}
    {7004.25 7373.5}
}

set idx 0
foreach win $windows {
    incr idx
    set t_s [lindex $win 0]
    set t_e [lindex $win 1]
    puts "=== spatial_2x win[format %02d $idx]: spliced ${t_s}~${t_e}ns ==="
    set_power_analysis_mode -reset
    set_power_analysis_mode -method dynamic_vectorbased -create_binary_db true -current_generation_method avg
    read_activity_file -format VCD ../../vcd/compressed_2x_kt200_mc1.vcd \
        -scope test/u0 -start ${t_s}ns -end ${t_e}ns
    set_dynamic_power_simulation -resolution 1ns
    report_power -o ../../db/power/avg_v20_spatial_2x_win[format %02d $idx]
    set_pg_nets -net VDD -voltage 0.7 -threshold 0.651
    set_pg_nets -net VSS -voltage 0   -threshold 0.1
    set_power_pads -net VDD -format xy -file ./ring_pads_vdd_clean.ppl
    set_power_pads -net VSS -format xy -file ./ring_pads_vss_clean.ppl
    set_power_data -format current [list \
        ../../db/power/avg_v20_spatial_2x_win[format %02d $idx]/dynamic_VDD.ptiavg \
        ../../db/power/avg_v20_spatial_2x_win[format %02d $idx]/dynamic_VSS.ptiavg]
    set_rail_analysis_mode -method dynamic -accuracy xd \
        -power_grid_library ./des3_pg_v20/techonly.cl -limit_number_of_steps false
    set_rail_analysis_domain -name PD -pwrnets VDD -gndnets VSS
    analyze_rail -type domain -output ../../db/rail_power_v20_spatial_2x_win[format %02d $idx] PD
    puts "=== spatial_2x win[format %02d $idx] done ==="
}

puts "=== All spatial_2x windows completed ==="
exit
