# =============================================================
# pr_flow.tcl — Innovus P&R for DMA_slow (ISPD2012 contest)
# Physical backend: ASAP7 tech LEF + contest cell LEF
# Top cell  : DMA_slow  (note: ISPD2012 top module name = DMA_slow)
# Clock     : ispd_clk / mclk, period 900ps
# Utilization: 70%
# =============================================================

set SCRIPT_DIR   [file dirname [file normalize [info script]]]
set CIRCUIT_DIR  [file dirname $SCRIPT_DIR]
# Layout on remote server:
#   CIRCUIT_DIR  = ~/data/test_sim_output/DMA_slow
#   TSIMOUT_DIR  = ~/data/test_sim_output         (one up)
#   PROJ_ROOT    = ~/data                         (two up = Classify equivalent)
set TSIMOUT_DIR  [file dirname $CIRCUIT_DIR]
set PROJ_ROOT    [file dirname $TSIMOUT_DIR]
set DES_DEMO_ENC [file normalize "$PROJ_ROOT/des_demo/db/des3.enc.dat"]
# NOTE: test_circuit/ispd2012 does NOT exist on remote server
# Files were uploaded to test_sim_output/{circuit}/src/ and test_sim_output/lib/
set SHARED_SCRIPTS [file normalize "$TSIMOUT_DIR/scripts"]

# ---- Cell top name ----
set TOP_CELL    DMA_slow

# ---- LEF files: ASAP7 tech first, then contest cell macros ----
set ASAP7_TECH_LEF   $DES_DEMO_ENC/libs/lef/asap7_tech_4x_201209.lef
set CONTEST_CELL_LEF $SHARED_SCRIPTS/contest_cells.lef

# ---- Generate contest_cells.lef if not present ----
if {![file exists $CONTEST_CELL_LEF]} {
    puts "INFO: contest_cells.lef not found. Generating via gen_contest_lef.py ..."
    set rc [catch {exec python3 $SHARED_SCRIPTS/gen_contest_lef.py \
        $TSIMOUT_DIR/lib/contest.lib $CONTEST_CELL_LEF} msg]
    if {$rc != 0} {
        error "ERROR: Failed to generate contest_cells.lef: $msg"
    }
    puts "INFO: contest_cells.lef generated."
}

# ---- Other paths ----
set NETLIST   $CIRCUIT_DIR/src/DMA_slow.v
set MMMC_FILE $SCRIPT_DIR/contest.mmmc
set DB_DIR    $CIRCUIT_DIR/src

file mkdir $DB_DIR

set OUT_DEF  $DB_DIR/${TOP_CELL}.def
set OUT_V    $DB_DIR/${TOP_CELL}.v
set OUT_ENC  $DB_DIR/${TOP_CELL}.enc

# ---- Init design ----
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

# ASAP7 7nm process node
# Innovus v20: -process 7 (no -node flag, that's v21+)
setDesignMode -process 7

setMultiCpuUsage -localCpu 8

setNanoRouteMode -routeBottomRoutingLayer 2
setNanoRouteMode -routeTopRoutingLayer    7

# ---- Global net connect ----
globalNetConnect VDD -type pgpin -pin VDD -inst *
globalNetConnect VSS -type pgpin -pin VSS -inst *

# ---- Floorplan ----
# ASAP7 cell parameters: height=1.08um, grid=0.216um
set CELL_HEIGHT  1.08
set CELL_HGRID   0.216

set FP_RING_OFFSET  0.384
set FP_RING_WIDTH   2.176
set FP_RING_SPACE   0.384
set FP_MARGIN [expr {$FP_RING_SPACE + 2*$FP_RING_WIDTH + $FP_RING_OFFSET + 1.5}]

set TARGET_UTILIZATION  0.70
set ASPECT_RATIO        1.0

floorPlan -site asap7sc7p5t \
    -r $ASPECT_RATIO $TARGET_UTILIZATION \
    $FP_MARGIN $FP_MARGIN $FP_MARGIN $FP_MARGIN

# ---- Power ring (M6/M7, matching innovus.tcl geometry) ----
setAddRingMode \
    -ring_target default \
    -orthogonal_only true \
    -stacked_via_top_layer   Pad \
    -stacked_via_bottom_layer M1 \
    -via_using_exact_crossover_size 1 \
    -skip_via_on_pin {standardcell} \
    -skip_via_on_wire_shape {noshape}

addRing -nets {VDD VSS} -type core_rings -follow core \
    -layer {top M7 bottom M7 left M6 right M6} \
    -width $FP_RING_WIDTH \
    -spacing $FP_RING_SPACE \
    -offset $FP_RING_OFFSET \
    -center 0

# ---- M2 horizontal follow-rail stripes ----
addStripe -skip_via_on_wire_shape blockring \
    -direction horizontal \
    -set_to_set_distance [expr {2 * $CELL_HEIGHT}] \
    -skip_via_on_pin Standardcell \
    -stacked_via_top_layer  M1 \
    -stacked_via_bottom_layer M1 \
    -layer M2 -width 0.072 -nets {VDD} \
    -start_from bottom -start_offset -0.044 -stop_offset -0.044

addStripe -skip_via_on_wire_shape blockring \
    -direction horizontal \
    -set_to_set_distance [expr {2 * $CELL_HEIGHT}] \
    -skip_via_on_pin Standardcell \
    -stacked_via_top_layer  M1 \
    -stacked_via_bottom_layer M1 \
    -layer M2 -width 0.072 -nets {VSS} \
    -start_from bottom \
    -start_offset [expr {$CELL_HEIGHT - 0.044}] \
    -stop_offset -0.044

# ---- M3 vertical power stripes ----
set m3w    0.936
set m3sp   0.360
set m3p2p  12.960

addStripe -skip_via_on_wire_shape Noshape \
    -set_to_set_distance $m3p2p \
    -skip_via_on_pin Standardcell \
    -stacked_via_top_layer   Pad \
    -stacked_via_bottom_layer M2 \
    -spacing $m3sp \
    -xleft_offset $m3sp \
    -layer M3 -width $m3w \
    -nets {VDD VSS} \
    -start_from left

# ---- M4 horizontal power stripes ----
set m4w   0.864
set m4sp  0.864
set m4p2p 21.6

addStripe -skip_via_on_wire_shape Noshape \
    -direction horizontal \
    -set_to_set_distance $m4p2p \
    -skip_via_on_pin Standardcell \
    -stacked_via_top_layer   M7 \
    -stacked_via_bottom_layer M3 \
    -spacing $m4sp \
    -layer M4 -width $m4w \
    -nets {VDD VSS} \
    -start_from bottom

# ---- S-route core pins ----
setSrouteMode -reset
setSrouteMode -viaConnectToShape {noshape}
sroute -connect {corePin} \
    -layerChangeRange {M1(1) M7(7)} \
    -blockPinTarget {nearestTarget} \
    -floatingStripeTarget {blockring padring ring stripe ringpin blockpin followpin} \
    -deleteExistingRoutes \
    -allowJogging 0 \
    -crossoverViaLayerRange {M1(1) Pad(10)} \
    -nets {VDD VSS} \
    -allowLayerChange 0 \
    -targetViaLayerRange {M1(1) Pad(10)}

editPowerVia -add_vias 1 -orthogonal_only 0

# ---- Pin assignment (wrapped in catch — non-fatal if pins are 'cover' status) ----
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

# ---- Placement ----
# NOTE: Using placeDesign (not place_opt_design) to avoid Innovus v20 crash
# in timing-driven placement with non-ASAP7 contest cells. For ISPD2012 power
# analysis, timing closure is not required — we only need a valid placed DEF.
colorizePowerMesh
placeDesign

# ---- CTS ----
# Suppress ccopt errors so they don't abort script execution (Innovus v20)
suppressMessage IMPCCOPT-2196
suppressMessage IMPCCOPT-1183
suppressMessage IMPCCOPT-1182
suppressMessage IMPPTN-963

if {[catch {ccopt_design} cts_err]} {
    puts "WARN: ccopt_design failed: $cts_err"
    puts "INFO: Skipping CTS (OK for power analysis)"
}

set_interactive_constraint_modes [all_constraint_modes -active]
if {[catch {reset_propagated_clock [all_clocks]}]} {}
if {[catch {set_propagated_clock [all_clocks]}]} {}
if {[catch {legalizePin}]} {}

# ---- Routing ----
routeDesign

# Rebuild power vias (non-fatal)
if {[catch {
    editPowerVia -delete_vias 1 -top_layer 7 -bottom_layer 6
    editPowerVia -delete_vias 1 -top_layer 6 -bottom_layer 5
    editPowerVia -delete_vias 1 -top_layer 5 -bottom_layer 4
    editPowerVia -delete_vias 1 -top_layer 4 -bottom_layer 3
    editPowerVia -delete_vias 1 -top_layer 3 -bottom_layer 2
    editPowerVia -delete_vias 1 -top_layer 2 -bottom_layer 1
    editPowerVia -add_vias 1
} via_err]} {
    puts "WARN: editPowerVia rebuild: $via_err"
}

# NOTE: Skipping optDesign to avoid Innovus locale crash on this server.

# ---- Generate power pad coordinate files for Voltus ----
# These are written once after P&R and reused by all Voltus runs.
set pad_vdd_file $SCRIPT_DIR/ring_pads_vdd.ppl
set pad_vss_file $SCRIPT_DIR/ring_pads_vss.ppl

proc gen_ring_pads {filename} {
    # Query actual core bounding box
    set bbox [dbget top.fplan.corebox]
    set llx [lindex $bbox 0];  set lly [lindex $bbox 1]
    set urx [lindex $bbox 2];  set ury [lindex $bbox 3]
    set cx  [expr {($llx + $urx) / 2.0}]
    set cy  [expr {($lly + $ury) / 2.0}]
    set fp [open $filename w]
    # 8 pads: 4 corners + midpoints of each side
    puts $fp "$llx $lly"
    puts $fp "$urx $lly"
    puts $fp "$urx $ury"
    puts $fp "$llx $ury"
    puts $fp "$cx  $lly"
    puts $fp "$cx  $ury"
    puts $fp "$llx $cy"
    puts $fp "$urx $cy"
    close $fp
    puts "INFO: Pad file written: $filename"
}
gen_ring_pads $pad_vdd_file
gen_ring_pads $pad_vss_file

# ---- Write outputs ----
set defOutLefVia 1
set defOutLefNDR 1
defOut -netlist -routing -allLayers $OUT_DEF
saveNetlist $OUT_V
saveDesign  $OUT_ENC

puts "============================================"
puts "P&R DONE for $TOP_CELL"
puts "  DEF     : $OUT_DEF"
puts "  Netlist : $OUT_V"
puts "  Enc db  : $OUT_ENC"
puts "  VDD pads: $pad_vdd_file"
puts "  VSS pads: $pad_vss_file"
puts "============================================"
