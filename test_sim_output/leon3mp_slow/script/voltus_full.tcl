# =============================================================
# voltus_full.tcl — Full VCD IR Drop analysis for leon3mp_slow
# Backend: ASAP7 tech LEF + contest cell LEF + ASAP7 QRC
# VDD = 0.7V, threshold = 0.651V
# NOTE: 649K cells — use localCpu 8
# =============================================================

set SCRIPT_DIR   [file dirname [file normalize [info script]]]
set CIRCUIT_DIR  [file dirname $SCRIPT_DIR]
set TSIMOUT_DIR  [file dirname $CIRCUIT_DIR]
set PROJ_ROOT    [file dirname $TSIMOUT_DIR]
set DES_DEMO_ENC [file normalize "$PROJ_ROOT/des_demo/db/des3.enc.dat"]
set SHARED_SCR   [file normalize "$TSIMOUT_DIR/scripts"]

set TOP_CELL    leon3mp_slow
set SRC_DIR     $CIRCUIT_DIR/src
set VCD_FILE    $CIRCUIT_DIR/vcd/sim.vcd
set VCD_SCOPE   tb/u0
set OUT_POWER   $CIRCUIT_DIR/sim_data/full/power
set OUT_RAIL    $CIRCUIT_DIR/sim_data/full/rail
set PG_LIB_DIR  $SCRIPT_DIR/pg_lib_full

file mkdir $OUT_POWER
file mkdir $OUT_RAIL

set init_design_uniquify        1
set init_design_netlisttype     Verilog
set init_design_settop          1
set init_top_cell               $TOP_CELL
set init_verilog                $SRC_DIR/${TOP_CELL}.v
set init_lef_file               [list \
    $DES_DEMO_ENC/libs/lef/asap7_tech_4x_201209.lef \
    $SHARED_SCR/contest_cells.lef \
]
set init_pwr_net                VDD
set init_gnd_net                VSS
set init_mmmc_file              $SCRIPT_DIR/contest.mmmc

init_design
defIn $SRC_DIR/${TOP_CELL}.def

globalNetConnect VDD -type pgpin -pin VDD -inst *
globalNetConnect VSS -type pgpin -pin VSS -inst *
setMultiCpuUsage -localCpu 8

set_pg_library_mode -celltype techonly \
    -extraction_tech_file \
    $DES_DEMO_ENC/libs/mmmc/rc_typ_25/qrcTechFile_typ03_scaled4xV06
generate_pg_library -output $PG_LIB_DIR

set_power_analysis_mode -reset
set_power_analysis_mode \
    -method dynamic_vectorbased \
    -create_binary_db true \
    -current_generation_method avg

read_activity_file -format VCD $VCD_FILE -scope $VCD_SCOPE

set_dynamic_power_simulation -resolution 1ns
report_power -o $OUT_POWER/dynamic

set_pg_nets -net VDD -voltage 0.7  -threshold 0.651
set_pg_nets -net VSS -voltage 0.0  -threshold 0.1
set_power_pads -net VDD -format xy -file $SCRIPT_DIR/ring_pads_vdd.ppl
set_power_pads -net VSS -format xy -file $SCRIPT_DIR/ring_pads_vss.ppl

set_power_data -format current \
    [list $OUT_POWER/dynamic/dynamic_VDD.ptiavg \
          $OUT_POWER/dynamic/dynamic_VSS.ptiavg]

set_rail_analysis_mode \
    -method dynamic -accuracy xd \
    -power_grid_library $PG_LIB_DIR/techonly.cl \
    -limit_number_of_steps false

set_rail_analysis_domain -name PD -pwrnets VDD -gndnets VSS
analyze_rail -type domain -output $OUT_RAIL/rail_full PD

puts "Voltus full DONE: $TOP_CELL power=$OUT_POWER rail=$OUT_RAIL"
