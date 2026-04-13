#===================================================
# RC-Tile m3: top-k=2 small-window IR Drop analysis
# Window 1 (spliced 0~250ns)   = orig 3950~4200ns   cluster1 (cycle 81, full worst)
# Window 2 (spliced 250~500ns) = orig 10650~10900ns  cluster2 (cycle 215, argmax)
# beta_out = 4.2%  (10/238 cycles)
#===================================================

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

puts "=== m3 Window 1: orig 3950~4200ns / spliced 0~250ns (cluster1, full worst) ==="

set_power_analysis_mode -reset
set_power_analysis_mode \
    -method dynamic_vectorbased \
    -create_binary_db true \
    -current_generation_method avg
read_activity_file -format VCD ../../vcd/test_rctile_m3.vcd \
    -scope test/u0 \
    -start 0ns \
    -end 250ns
set_dynamic_power_simulation -resolution 1ns
report_power -o ../../db/power/avg_v20_rctile_m3_win1

set_pg_nets -net VDD -voltage 0.7 -threshold 0.651
set_pg_nets -net VSS -voltage 0   -threshold 0.1
set_power_pads -net VDD -format xy -file ./ring_pads_vdd_clean.ppl
set_power_pads -net VSS -format xy -file ./ring_pads_vss_clean.ppl
set_power_data -format current \
    [list ../../db/power/avg_v20_rctile_m3_win1/dynamic_VDD.ptiavg \
          ../../db/power/avg_v20_rctile_m3_win1/dynamic_VSS.ptiavg]
set_rail_analysis_mode \
    -method dynamic \
    -accuracy xd \
    -power_grid_library ./des3_pg_v20/techonly.cl \
    -limit_number_of_steps false
set_rail_analysis_domain -name PD -pwrnets VDD -gndnets VSS
analyze_rail -type domain -output ../../db/rail_power_v20_rctile_m3_win1 PD

puts "=== m3 Window 1 done ==="

puts "=== m3 Window 2: orig 10650~10900ns / spliced 250~500ns (cluster2) ==="

set_power_analysis_mode -reset
set_power_analysis_mode \
    -method dynamic_vectorbased \
    -create_binary_db true \
    -current_generation_method avg
read_activity_file -format VCD ../../vcd/test_rctile_m3.vcd \
    -scope test/u0 \
    -start 250ns \
    -end 500ns
set_dynamic_power_simulation -resolution 1ns
report_power -o ../../db/power/avg_v20_rctile_m3_win2

set_pg_nets -net VDD -voltage 0.7 -threshold 0.651
set_pg_nets -net VSS -voltage 0   -threshold 0.1
set_power_pads -net VDD -format xy -file ./ring_pads_vdd_clean.ppl
set_power_pads -net VSS -format xy -file ./ring_pads_vss_clean.ppl
set_power_data -format current \
    [list ../../db/power/avg_v20_rctile_m3_win2/dynamic_VDD.ptiavg \
          ../../db/power/avg_v20_rctile_m3_win2/dynamic_VSS.ptiavg]
set_rail_analysis_mode \
    -method dynamic \
    -accuracy xd \
    -power_grid_library ./des3_pg_v20/techonly.cl \
    -limit_number_of_steps false
set_rail_analysis_domain -name PD -pwrnets VDD -gndnets VSS
analyze_rail -type domain -output ../../db/rail_power_v20_rctile_m3_win2 PD

puts "=== m3 Window 2 done ==="

puts "=== All rctile_m3 windows completed ==="
exit
