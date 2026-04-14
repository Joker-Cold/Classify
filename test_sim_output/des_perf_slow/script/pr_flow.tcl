# =============================================================
# pr_flow.tcl — Innovus P&R for des_perf_slow (ISPD2012 contest)
# Physical backend: ASAP7 tech LEF + contest cell LEF
# Top cell  : des_perf_slow  (note: ISPD2012 top module name = des_perf_slow)
# Clock     : ispd_clk / mclk, period 900ps
# Utilization: 70%
# =============================================================

set SCRIPT_DIR   [file dirname [file normalize [info script]]]
set CIRCUIT_DIR  [file dirname $SCRIPT_DIR]
set TSIMOUT_DIR  [file dirname $CIRCUIT_DIR]
set PROJ_ROOT    [file dirname $TSIMOUT_DIR]
set DES_DEMO_ENC [file normalize "$PROJ_ROOT/des_demo/db/des3.enc.dat"]
set SHARED_SCRIPTS [file normalize "$TSIMOUT_DIR/scripts"]

set TOP_CELL    des_perf_slow

set ASAP7_TECH_LEF   $DES_DEMO_ENC/libs/lef/asap7_tech_4x_201209.lef
set CONTEST_CELL_LEF $SHARED_SCRIPTS/contest_cells.lef

if {![file exists $CONTEST_CELL_LEF]} {
    puts "INFO: Generating contest_cells.lef ..."
    set _rc [catch {exec python3 $SHARED_SCRIPTS/gen_contest_lef.py \
        $TSIMOUT_DIR/lib/contest.lib $CONTEST_CELL_LEF} _msg]
    if {$_rc != 0} { error "gen_contest_lef.py failed: $_msg" }
    puts "INFO: Done."
}

# Netlist uploaded to src/ on remote server
set NETLIST   $CIRCUIT_DIR/src/${TOP_CELL}.v
set MMMC_FILE $SCRIPT_DIR/contest.mmmc
set DB_DIR    $CIRCUIT_DIR/src

file mkdir $DB_DIR

set OUT_DEF  $DB_DIR/${TOP_CELL}.def
set OUT_V    $DB_DIR/${TOP_CELL}.v
set OUT_ENC  $DB_DIR/${TOP_CELL}.enc

set init_design_uniquify        1
set init_design_netlisttype     Verilog
set init_design_settop          1
set init_top_cell               $TOP_CELL
set init_verilog                $NETLIST
set init_lef_file               [list $ASAP7_TECH_LEF $CONTEST_CELL_LEF]
set init_pwr_net                VDD
set init_gnd_net                VSS
set init_mmmc_file              $MMMC_FILE

init_design

setDesignMode -process 7
setMultiCpuUsage -localCpu 8
setNanoRouteMode -routeBottomRoutingLayer 2
setNanoRouteMode -routeTopRoutingLayer    7

globalNetConnect VDD -type pgpin -pin VDD -inst *
globalNetConnect VSS -type pgpin -pin VSS -inst *

set CELL_HEIGHT  1.08
set FP_RING_OFFSET  0.384
set FP_RING_WIDTH   2.176
set FP_RING_SPACE   0.384
set FP_MARGIN [expr {$FP_RING_SPACE + 2*$FP_RING_WIDTH + $FP_RING_OFFSET + 1.5}]

floorPlan -site asap7sc7p5t \
    -r 1.0 0.70 \
    $FP_MARGIN $FP_MARGIN $FP_MARGIN $FP_MARGIN

setAddRingMode \
    -ring_target default -orthogonal_only true \
    -stacked_via_top_layer Pad -stacked_via_bottom_layer M1 \
    -via_using_exact_crossover_size 1 \
    -skip_via_on_pin {standardcell} -skip_via_on_wire_shape {noshape}

addRing -nets {VDD VSS} -type core_rings -follow core \
    -layer {top M7 bottom M7 left M6 right M6} \
    -width $FP_RING_WIDTH -spacing $FP_RING_SPACE \
    -offset $FP_RING_OFFSET -center 0

addStripe -skip_via_on_wire_shape blockring \
    -direction horizontal \
    -set_to_set_distance [expr {2 * $CELL_HEIGHT}] \
    -skip_via_on_pin Standardcell \
    -stacked_via_top_layer M1 -stacked_via_bottom_layer M1 \
    -layer M2 -width 0.072 -nets {VDD} \
    -start_from bottom -start_offset -0.044 -stop_offset -0.044

addStripe -skip_via_on_wire_shape blockring \
    -direction horizontal \
    -set_to_set_distance [expr {2 * $CELL_HEIGHT}] \
    -skip_via_on_pin Standardcell \
    -stacked_via_top_layer M1 -stacked_via_bottom_layer M1 \
    -layer M2 -width 0.072 -nets {VSS} \
    -start_from bottom \
    -start_offset [expr {$CELL_HEIGHT - 0.044}] -stop_offset -0.044

addStripe -skip_via_on_wire_shape Noshape \
    -set_to_set_distance 12.960 \
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
    -side Left -layer 3 -spreadType side \
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

set pad_vdd_file $SCRIPT_DIR/ring_pads_vdd.ppl
set pad_vss_file $SCRIPT_DIR/ring_pads_vss.ppl

proc gen_ring_pads {filename} {
    set bbox [dbget top.fplan.corebox]
    set llx [lindex $bbox 0]; set lly [lindex $bbox 1]
    set urx [lindex $bbox 2]; set ury [lindex $bbox 3]
    set cx [expr {($llx+$urx)/2.0}]; set cy [expr {($lly+$ury)/2.0}]
    set fp [open $filename w]
    puts $fp "$llx $lly"; puts $fp "$urx $lly"
    puts $fp "$urx $ury"; puts $fp "$llx $ury"
    puts $fp "$cx  $lly"; puts $fp "$cx  $ury"
    puts $fp "$llx $cy";  puts $fp "$urx $cy"
    close $fp
    puts "INFO: Pad file written: $filename"
}
gen_ring_pads $pad_vdd_file
gen_ring_pads $pad_vss_file

set defOutLefVia 1; set defOutLefNDR 1
defOut -netlist -routing -allLayers $OUT_DEF
saveNetlist $OUT_V
saveDesign  $OUT_ENC

puts "P&R DONE: $TOP_CELL  DEF=$OUT_DEF"
