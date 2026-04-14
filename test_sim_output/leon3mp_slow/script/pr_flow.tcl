# =============================================================
# pr_flow.tcl — Innovus P&R for leon3mp_slow (ISPD2012 contest)
# Physical backend: ASAP7 tech LEF + contest cell LEF
# Top cell  : leon3mp_slow
# Clock     : ispd_clk / mclk, period 1800ps
# Utilization: 70%, ASAP7 7nm process node
# NOTE: 649K cells — denser power grid, 16 CPUs recommended
# =============================================================

set PR_SCRIPT_DIR   [file dirname [file normalize [info script]]]
set PR_CIRCUIT_DIR  [file dirname $PR_SCRIPT_DIR]
set PR_TSIMOUT_DIR  [file dirname $PR_CIRCUIT_DIR]
set PR_PROJ_ROOT    [file dirname $PR_TSIMOUT_DIR]

set PR_DES_ENC      [file normalize "$PR_PROJ_ROOT/des_demo/db/des3.enc.dat"]
set PR_SHARED_SCR   [file normalize "$PR_TSIMOUT_DIR/scripts"]

set TOP_CELL  leon3mp_slow

set PR_TECH_LEF  $PR_DES_ENC/libs/lef/asap7_tech_4x_201209.lef
set PR_CELL_LEF  $PR_SHARED_SCR/contest_cells.lef

if {![file exists $PR_CELL_LEF]} {
    puts "INFO: Generating contest_cells.lef ..."
    set _rc [catch {exec python3 $PR_SHARED_SCR/gen_contest_lef.py \
        $PR_TSIMOUT_DIR/lib/contest.lib $PR_CELL_LEF} _msg]
    if {$_rc != 0} { error "gen_contest_lef.py failed: $_msg" }
    puts "INFO: Done."
}

set PR_NETLIST   $PR_CIRCUIT_DIR/src/${TOP_CELL}.v
set PR_MMMC      $PR_SCRIPT_DIR/contest.mmmc
set PR_DB_DIR    $PR_CIRCUIT_DIR/src

file mkdir $PR_DB_DIR

set OUT_DEF  $PR_DB_DIR/${TOP_CELL}.def
set OUT_V    $PR_DB_DIR/${TOP_CELL}.v
set OUT_ENC  $PR_DB_DIR/${TOP_CELL}.enc

set init_design_uniquify        1
set init_design_netlisttype     Verilog
set init_design_settop          1
set init_top_cell               $TOP_CELL
set init_verilog                $PR_NETLIST
set init_lef_file               [list $PR_TECH_LEF $PR_CELL_LEF]
set init_pwr_net                VDD
set init_gnd_net                VSS
set init_mmmc_file              $PR_MMMC

init_design

setDesignMode -process 7
setMultiCpuUsage -localCpu 16
setNanoRouteMode -routeBottomRoutingLayer 2
setNanoRouteMode -routeTopRoutingLayer    7

globalNetConnect VDD -type pgpin -pin VDD -inst *
globalNetConnect VSS -type pgpin -pin VSS -inst *

set PR_CELL_H    1.08
set PR_RING_OFF  0.384
set PR_RING_W    2.176
set PR_RING_SP   0.384
set PR_MARGIN    [expr {$PR_RING_SP + 2*$PR_RING_W + $PR_RING_OFF + 1.5}]

floorPlan -site asap7sc7p5t \
    -r 1.0 0.70 \
    $PR_MARGIN $PR_MARGIN $PR_MARGIN $PR_MARGIN

setAddRingMode \
    -ring_target default -orthogonal_only true \
    -stacked_via_top_layer Pad -stacked_via_bottom_layer M1 \
    -via_using_exact_crossover_size 1 \
    -skip_via_on_pin {standardcell} -skip_via_on_wire_shape {noshape}

addRing -nets {VDD VSS} -type core_rings -follow core \
    -layer {top M7 bottom M7 left M6 right M6} \
    -width $PR_RING_W -spacing $PR_RING_SP -offset $PR_RING_OFF -center 0

addStripe -skip_via_on_wire_shape blockring \
    -direction horizontal \
    -set_to_set_distance [expr {2 * $PR_CELL_H}] \
    -skip_via_on_pin Standardcell \
    -stacked_via_top_layer M1 -stacked_via_bottom_layer M1 \
    -layer M2 -width 0.072 -nets {VDD} \
    -start_from bottom -start_offset -0.044 -stop_offset -0.044

addStripe -skip_via_on_wire_shape blockring \
    -direction horizontal \
    -set_to_set_distance [expr {2 * $PR_CELL_H}] \
    -skip_via_on_pin Standardcell \
    -stacked_via_top_layer M1 -stacked_via_bottom_layer M1 \
    -layer M2 -width 0.072 -nets {VSS} \
    -start_from bottom \
    -start_offset [expr {$PR_CELL_H - 0.044}] -stop_offset -0.044

# Denser M3 stripes for 649K-cell design
addStripe -skip_via_on_wire_shape Noshape \
    -set_to_set_distance 8.640 \
    -skip_via_on_pin Standardcell \
    -stacked_via_top_layer Pad -stacked_via_bottom_layer M2 \
    -spacing 0.360 -xleft_offset 0.360 \
    -layer M3 -width 0.936 -nets {VDD VSS} -start_from left

addStripe -skip_via_on_wire_shape Noshape \
    -direction horizontal \
    -set_to_set_distance 21.6 \
    -skip_via_on_pin Standardcell \
    -stacked_via_top_layer M7 -stacked_via_bottom_layer M3 \
    -spacing 0.864 -layer M4 -width 0.864 \
    -nets {VDD VSS} -start_from bottom

# Extra M5 horizontal stripes for large IR drop coverage
addStripe -skip_via_on_wire_shape Noshape \
    -direction horizontal \
    -set_to_set_distance 43.2 \
    -skip_via_on_pin Standardcell \
    -stacked_via_top_layer M7 -stacked_via_bottom_layer M4 \
    -spacing 1.728 -layer M5 -width 1.728 \
    -nets {VDD VSS} -start_from bottom

setSrouteMode -reset
setSrouteMode -viaConnectToShape {noshape}
sroute -connect {corePin} \
    -layerChangeRange {M1(1) M7(7)} \
    -blockPinTarget {nearestTarget} \
    -floatingStripeTarget {blockring padring ring stripe ringpin blockpin followpin} \
    -deleteExistingRoutes -allowJogging 0 \
    -crossoverViaLayerRange {M1(1) Pad(10)} \
    -nets {VDD VSS} -allowLayerChange 0 \
    -targetViaLayerRange {M1(1) Pad(10)}

editPowerVia -add_vias 1 -orthogonal_only 0

setPinAssignMode -pinEditInBatch true
catch {editPin -fixOverlap 1 -spreadDirection clockwise \
    -side Left  -layer 3 -spreadType side \
    -pin [get_ports -filter {direction==in}]}
catch {editPin -fixOverlap 1 -spreadDirection clockwise \
    -side Right -layer 3 -spreadType side \
    -pin [get_ports -filter {direction==out}]}
catch {editPin -snap TRACK -pin *}
setPinAssignMode -pinEditInBatch false
catch {legalizePin}

setOptMode -holdTargetSlack 0.020 -setupTargetSlack 0.020
colorizePowerMesh
place_opt_design

ccopt_design
set_interactive_constraint_modes [all_constraint_modes -active]
reset_propagated_clock [all_clocks]
set_propagated_clock [all_clocks]
legalizePin

routeDesign

editPowerVia -delete_vias 1 -top_layer 7 -bottom_layer 6
editPowerVia -delete_vias 1 -top_layer 6 -bottom_layer 5
editPowerVia -delete_vias 1 -top_layer 5 -bottom_layer 4
editPowerVia -delete_vias 1 -top_layer 4 -bottom_layer 3
editPowerVia -delete_vias 1 -top_layer 3 -bottom_layer 2
editPowerVia -delete_vias 1 -top_layer 2 -bottom_layer 1
editPowerVia -add_vias 1

setAnalysisMode -analysisType onChipVariation
setSIMode -enable_glitch_report true -enable_delay_report true
optDesign -postRoute
optDesign -postRoute -hold

set PR_PAD_VDD  $PR_SCRIPT_DIR/ring_pads_vdd.ppl
set PR_PAD_VSS  $PR_SCRIPT_DIR/ring_pads_vss.ppl

proc write_pads_from_corebox {fname} {
    set bb [dbget top.fplan.corebox]
    set x0 [lindex $bb 0];  set y0 [lindex $bb 1]
    set x1 [lindex $bb 2];  set y1 [lindex $bb 3]
    set mx [expr {($x0+$x1)/2.0}];  set my [expr {($y0+$y1)/2.0}]
    set qx1 [expr {($x0*3+$x1)/4.0}];  set qx3 [expr {($x0+$x1*3)/4.0}]
    set qy1 [expr {($y0*3+$y1)/4.0}];  set qy3 [expr {($y0+$y1*3)/4.0}]
    set fh [open $fname w]
    # 12 pads for large design: corners + 1/4 + midpoints + 3/4 marks
    puts $fh "$x0 $y0";   puts $fh "$x1 $y0"
    puts $fh "$x1 $y1";   puts $fh "$x0 $y1"
    puts $fh "$qx1 $y0";  puts $fh "$mx $y0";  puts $fh "$qx3 $y0"
    puts $fh "$qx1 $y1";  puts $fh "$mx $y1";  puts $fh "$qx3 $y1"
    puts $fh "$x0 $qy1";  puts $fh "$x0 $my";  puts $fh "$x0 $qy3"
    puts $fh "$x1 $qy1";  puts $fh "$x1 $my";  puts $fh "$x1 $qy3"
    close $fh
    puts "INFO: Written $fname"
}
write_pads_from_corebox $PR_PAD_VDD
write_pads_from_corebox $PR_PAD_VSS

set defOutLefVia 1
set defOutLefNDR 1
defOut -netlist -routing -allLayers $OUT_DEF
saveNetlist $OUT_V
saveDesign  $OUT_ENC

puts "P&R DONE: $TOP_CELL | DEF=$OUT_DEF"
