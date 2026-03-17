# to modify this script, look for TODO markers

# the script is slightly different for different versions of innovus. please set this variable wit the version number
#set VERSION 17
#set VERSION 18
set VERSION 19
#set VERSION 20
# set VERSION 21

set init_design_uniquify 1

# TODO change gate-level netlist path if needed
set init_verilog {../../netlist/des3_netlist.v}

set init_design_netlisttype {Verilog}
set init_design_settop {1}

# TODO change top cell name if needed
set init_top_cell {des3}

# TODO change path if needed
set DB_PATH "../../db/"					
set LEF_PATH "../../../../lef/scaled"
set TLEF_PATH "../../../../techlef"

# set CELL_LEF "$LEF_PATH/asap7sc7p5t_28_L_4x_220121a.lef $LEF_PATH/asap7sc7p5t_28_SL_4x_220121a.lef $LEF_PATH/asap7sc7p5t_28_R_4x_220121a.lef"
# TODO change LEF files if needed
set CELL_LEF "$LEF_PATH/asap7sc7p5t_28_L_4x_220121a.lef $LEF_PATH/asap7sc7p5t_28_SL_4x_220121a.lef"
set TECH_LEF $TLEF_PATH/asap7_tech_4x_201209.lef

#tech lef first, cell lef later
set init_lef_file "$TECH_LEF $CELL_LEF"

set fp_core_cntl {aspect}
set fp_aspect_ratio {1.0000}
set extract_shrink_factor {1.0}
set init_assign_buffer {0}
set init_pwr_net {VDD}
set init_gnd_net {VSS}

# here starts the timing libraries
set init_cpf_file {}

# TODO change mmmc file if needed
set init_mmmc_file {./des3.mmmc}

init_design 

# settings begin here
# defines tech node
if {$VERSION <= 19} {
	setDesignMode -process 7 
} else {
	setDesignMode -process 7 -node N7
}

setMultiCpuUsage -localCpu 8

if {$VERSION <= 20} {
	setNanoRouteMode -routeBottomRoutingLayer 2
	setNanoRouteMode -routeTopRoutingLayer 7
} else {
	setDesignMode -bottomRoutingLayer 2
	setDesignMode -topRoutingLayer 7
}

#this is the VDD for the std cells
globalNetConnect VDD -type pgpin -pin VDD -inst * 

# and the VSS
globalNetConnect VSS -type pgpin -pin VSS -inst * 

# TODO change ultilizetion and aspect ratio if needed
set TARGET_UTILIZATION 0.7
set ASPECT_RATIO 1.0

set FP_RING_OFFSET 0.384
set FP_RING_WIDTH 2.176
set FP_RING_SPACE 0.384
set FP_RING_SIZE [expr {$FP_RING_SPACE + 2*$FP_RING_WIDTH + $FP_RING_OFFSET + 1.1}]
#set FP_RING_SIZE [expr {$FP_RING_SPACE + 2*$FP_RING_WIDTH + $FP_RING_OFFSET}]
set FP_TARGET 408
set FP_MUL 5
# important: these numbers cannot be chosen arbitrarily, otherwise all VDD/VSS stripes are offgrid or there are no valid vias that can drop on them 
# FP_TARGET is the only variable you can freely modify. this one determines the number of standard cell rows in your design
# FP_MUL controls the aspect ratio. FP_MUL = 5 gives you a perfectly square design
# the additional 0.1 is to account for situations where innovus snaps the fplan and the space becomes too narrow to fit the rings 

set cellheight [expr 0.270 * 4 ]
set cellhgrid  0.216

set fpxdim [expr $cellhgrid * $FP_TARGET*$FP_MUL]
set fpydim [expr $cellheight * $FP_TARGET ]

# this command prints the snapping rules, it is useful for debugging
fpiGetSnapRule

# floorPlan -site asap7sc7p5t -s $fpxdim $fpydim $FP_RING_SIZE $FP_RING_SIZE $FP_RING_SIZE $FP_RING_SIZE -noSnap
floorPlan -site asap7sc7p5t -r $ASPECT_RATIO $TARGET_UTILIZATION $FP_RING_SIZE $FP_RING_SIZE $FP_RING_SIZE $FP_RING_SIZE

# this is likely not perfect because some snapping is done by innovus. the commands below came with the reference script by ASU. 
#changeFloorplan -coreToBottom [expr $FP_RING_SIZE] 
#add_tracks -honor_pitch

# the interval setting matches the M3 stripes for saving some resources. 
addWellTap -cell TAPCELL_ASAP7_75t_L -cellInterval 12.960 -inRowOffset 1.296

if {$VERSION >= 21} {
	# this series of commands makes innovus 21 happy :)
	add_tracks -snap_m1_track_to_cell_pins
	add_tracks -mode replace -offsets {M5 vertical 0}
	deleteAllFPObjects
	addWellTap -cell TAPCELL_ASAP7_75t_L -cellInterval 12.960 -inRowOffset 1.296
}

# classic setting: all inputs on the left, all outputs on the right.
# setPinAssignMode -pinEditInBatch true
# editPin -fixOverlap 1 -unit MICRON -spreadDirection clockwise -side Left -layer 3 -spreadType center -spacing 2.016 -pin {PWRITE PENABLE PSEL PCLK PRESETn {PADDR[0]} {PADDR[1]} {PADDR[2]} {PADDR[3]} cs we {write_data[0]} {write_data[1]} {write_data[2]} {write_data[3]} {write_data[4]} {write_data[5]} {write_data[6]} {write_data[7]} {write_data[8]} {write_data[9]} {write_data[10]} {write_data[11]} {write_data[12]} {write_data[13]} {write_data[14]} {write_data[15]} {write_data[16]} {write_data[17]} {write_data[18]} {write_data[19]} {write_data[20]} {write_data[21]} {write_data[22]} {write_data[23]} {write_data[24]} {write_data[25]} {write_data[26]} {write_data[27]} {write_data[28]} {write_data[29]} {write_data[30]} {write_data[31]}}
# editPin -fixOverlap 1 -unit MICRON -spreadDirection clockwise -side Right -layer 3 -spreadType center -spacing 2 -pin {error {read_data[0]} {read_data[1]} {read_data[2]} {read_data[3]} {read_data[4]} {read_data[5]} {read_data[6]} {read_data[7]} {read_data[8]} {read_data[9]} {read_data[10]} {read_data[11]} {read_data[12]} {read_data[13]} {read_data[14]} {read_data[15]} {read_data[16]} {read_data[17]} {read_data[18]} {read_data[19]} {read_data[20]} {read_data[21]} {read_data[22]} {read_data[23]} {read_data[24]} {read_data[25]} {read_data[26]} {read_data[27]} {read_data[28]} {read_data[29]} {read_data[30]} {read_data[31]}}
# editPin -snap TRACK -pin *
# setPinAssignMode -pinEditInBatch false
# legalizePin

# 经典设置：所有输入在左侧，所有输出在右侧。
setPinAssignMode -pinEditInBatch true

# TODO change all input/output pins if needed
set all_input_pins {{desIn[0]} {desIn[1]} {desIn[2]} {desIn[3]} {desIn[4]} {desIn[5]} {desIn[6]} {desIn[7]} {desIn[8]} {desIn[9]} {desIn[10]} {desIn[11]} {desIn[12]} {desIn[13]} {desIn[14]} {desIn[15]} {desIn[16]} {desIn[17]} {desIn[18]} {desIn[19]} {desIn[20]} {desIn[21]} {desIn[22]} {desIn[23]} {desIn[24]} {desIn[25]} {desIn[26]} {desIn[27]} {desIn[28]} {desIn[29]} {desIn[30]} {desIn[31]} {desIn[32]} {desIn[33]} {desIn[34]} {desIn[35]} {desIn[36]} {desIn[37]} {desIn[38]} {desIn[39]} {desIn[40]} {desIn[41]} {desIn[42]} {desIn[43]} {desIn[44]} {desIn[45]} {desIn[46]} {desIn[47]} {desIn[48]} {desIn[49]} {desIn[50]} {desIn[51]} {desIn[52]} {desIn[53]} {desIn[54]} {desIn[55]} {desIn[56]} {desIn[57]} {desIn[58]} {desIn[59]} {desIn[60]} {desIn[61]} {desIn[62]} {desIn[63]} {key1[0]} {key1[1]} {key1[2]} {key1[3]} {key1[4]} {key1[5]} {key1[6]} {key1[7]} {key1[8]} {key1[9]} {key1[10]} {key1[11]} {key1[12]} {key1[13]} {key1[14]} {key1[15]} {key1[16]} {key1[17]} {key1[18]} {key1[19]} {key1[20]} {key1[21]} {key1[22]} {key1[23]} {key1[24]} {key1[25]} {key1[26]} {key1[27]} {key1[28]} {key1[29]} {key1[30]} {key1[31]} {key1[32]} {key1[33]} {key1[34]} {key1[35]} {key1[36]} {key1[37]} {key1[38]} {key1[39]} {key1[40]} {key1[41]} {key1[42]} {key1[43]} {key1[44]} {key1[45]} {key1[46]} {key1[47]} {key1[48]} {key1[49]} {key1[50]} {key1[51]} {key1[52]} {key1[53]} {key1[54]} {key1[55]} {key2[0]} {key2[1]} {key2[2]} {key2[3]} {key2[4]} {key2[5]} {key2[6]} {key2[7]} {key2[8]} {key2[9]} {key2[10]} {key2[11]} {key2[12]} {key2[13]} {key2[14]} {key2[15]} {key2[16]} {key2[17]} {key2[18]} {key2[19]} {key2[20]} {key2[21]} {key2[22]} {key2[23]} {key2[24]} {key2[25]} {key2[26]} {key2[27]} {key2[28]} {key2[29]} {key2[30]} {key2[31]} {key2[32]} {key2[33]} {key2[34]} {key2[35]} {key2[36]} {key2[37]} {key2[38]} {key2[39]} {key2[40]} {key2[41]} {key2[42]} {key2[43]} {key2[44]} {key2[45]} {key2[46]} {key2[47]} {key2[48]} {key2[49]} {key2[50]} {key2[51]} {key2[52]} {key2[53]} {key2[54]} {key2[55]} {key3[0]} {key3[1]} {key3[2]} {key3[3]} {key3[4]} {key3[5]} {key3[6]} {key3[7]} {key3[8]} {key3[9]} {key3[10]} {key3[11]} {key3[12]} {key3[13]} {key3[14]} {key3[15]} {key3[16]} {key3[17]} {key3[18]} {key3[19]} {key3[20]} {key3[21]} {key3[22]} {key3[23]} {key3[24]} {key3[25]} {key3[26]} {key3[27]} {key3[28]} {key3[29]} {key3[30]} {key3[31]} {key3[32]} {key3[33]} {key3[34]} {key3[35]} {key3[36]} {key3[37]} {key3[38]} {key3[39]} {key3[40]} {key3[41]} {key3[42]} {key3[43]} {key3[44]} {key3[45]} {key3[46]} {key3[47]} {key3[48]} {key3[49]} {key3[50]} {key3[51]} {key3[52]} {key3[53]} {key3[54]} {key3[55]} {decrypt} {clk}}
set all_output_pins {{desOut[0]} {desOut[1]} {desOut[2]} {desOut[3]} {desOut[4]} {desOut[5]} {desOut[6]} {desOut[7]} {desOut[8]} {desOut[9]} {desOut[10]} {desOut[11]} {desOut[12]} {desOut[13]} {desOut[14]} {desOut[15]} {desOut[16]} {desOut[17]} {desOut[18]} {desOut[19]} {desOut[20]} {desOut[21]} {desOut[22]} {desOut[23]} {desOut[24]} {desOut[25]} {desOut[26]} {desOut[27]} {desOut[28]} {desOut[29]} {desOut[30]} {desOut[31]} {desOut[32]} {desOut[33]} {desOut[34]} {desOut[35]} {desOut[36]} {desOut[37]} {desOut[38]} {desOut[39]} {desOut[40]} {desOut[41]} {desOut[42]} {desOut[43]} {desOut[44]} {desOut[45]} {desOut[46]} {desOut[47]} {desOut[48]} {desOut[49]} {desOut[50]} {desOut[51]} {desOut[52]} {desOut[53]} {desOut[54]} {desOut[55]} {desOut[56]} {desOut[57]} {desOut[58]} {desOut[59]} {desOut[60]} {desOut[61]} {desOut[62]} {desOut[63]}}

# TODO change the placement of input/output pins if needed
# --- 将所有输入引脚放置在左侧 ---
# editPin -fixOverlap 1 -unit MICRON -spreadDirection clockwise -side Left -layer 3 -spreadType center -spacing 2.016 -pin {{PADDR[0]} {PADDR[1]} {PADDR[2]} {PADDR[3]} {PWDATA[0]} {PWDATA[1]} {PWDATA[2]} {PWDATA[3]} {PWDATA[4]} {PWDATA[5]} {PWDATA[6]} {PWDATA[7]} {PWDATA[8]} {PWDATA[9]} {PWDATA[10]} {PWDATA[11]} {PWDATA[12]} {PWDATA[13]} {PWDATA[14]} {PWDATA[15]} {PWDATA[16]} {PWDATA[17]} {PWDATA[18]} {PWDATA[19]} {PWDATA[20]} {PWDATA[21]} {PWDATA[22]} {PWDATA[23]} {PWDATA[24]} {PWDATA[25]} {PWDATA[26]} {PWDATA[27]} {PWDATA[28]} {PWDATA[29]} {PWDATA[30]} {PWDATA[31]} {PWRITE} {PENABLE} {PSEL} {PCLK} {PRESETn}}
editPin -fixOverlap 1 -spreadDirection clockwise -side Left -layer 3 -spreadType side -pin $all_input_pins

# --- 将所有输出引脚放置在右侧 ---
# editPin -fixOverlap 1 -unit MICRON -spreadDirection clockwise -side Right -layer 3 -spreadType center -spacing 2.0 -pin {{int_ccf} {int_err} {dma_req_wr} {dma_req_rd} {PREADY} {PSLVERR} {PRDATA[0]} {PRDATA[1]} {PRDATA[2]} {PRDATA[3]} {PRDATA[4]} {PRDATA[5]} {PRDATA[6]} {PRDATA[7]} {PRDATA[8]} {PRDATA[9]} {PRDATA[10]} {PRDATA[11]} {PRDATA[12]} {PRDATA[13]} {PRDATA[14]} {PRDATA[15]} {PRDATA[16]} {PRDATA[17]} {PRDATA[18]} {PRDATA[19]} {PRDATA[20]} {PRDATA[21]} {PRDATA[22]} {PRDATA[23]} {PRDATA[24]} {PRDATA[25]} {PRDATA[26]} {PRDATA[27]} {PRDATA[28]} {PRDATA[29]} {PRDATA[30]} {PRDATA[31]}}
editPin -fixOverlap 1 -spreadDirection clockwise -side Right -layer 3 -spreadType side -pin $all_output_pins

# --- 将所有引脚对齐到最近的布线轨道 ---
editPin -snap TRACK -pin *

# --- 关闭批量编辑模式并合法化引脚位置 ---
setPinAssignMode -pinEditInBatch false
legalizePin

# now we are going to add the core ring using M6/M7
setAddRingMode -ring_target default -extend_over_row 0 -ignore_rows 0 -avoid_short 0 -skip_crossing_trunks none -stacked_via_top_layer Pad -stacked_via_bottom_layer M1 -via_using_exact_crossover_size 1 -orthogonal_only true -skip_via_on_pin {  standardcell } -skip_via_on_wire_shape {  noshape }
addRing -nets {VDD VSS} -type core_rings -follow core -layer {top M7 bottom M7 left M6 right M6} -width $FP_RING_WIDTH -spacing $FP_RING_SPACE -offset $FP_RING_OFFSET -center 0 -threshold 0 -jog_distance 0 -snap_wire_center_to_grid None

# now we are going to add M2 follow rails. on top of every standard cell row. we need to add VSS and VDD separately because the number of rows is not always odd. it is possible you need one extra stripe of VDD, but not VSS.
addStripe  -skip_via_on_wire_shape blockring \
    -direction horizontal \
    -set_to_set_distance [expr 2*$cellheight] \
    -skip_via_on_pin Standardcell \
    -stacked_via_top_layer  M1 \
    -layer M2 \
    -width 0.072 \
    -nets {VDD} \
    -stacked_via_bottom_layer M1 \
    -start_from bottom \
    -snap_wire_center_to_grid None \
    -start_offset -0.044 \
    -stop_offset -0.044

addStripe  -skip_via_on_wire_shape blockring \
    -direction horizontal \
    -set_to_set_distance [expr 2*$cellheight] \
    -skip_via_on_pin Standardcell \
    -stacked_via_top_layer  M1 \
    -layer M2 \
    -width 0.072 \
    -nets {VSS} \
    -stacked_via_bottom_layer M1 \
    -start_from bottom \
    -snap_wire_center_to_grid None \
    -start_offset [expr $cellheight -0.044] \
    -stop_offset -0.044

# now we are going to add vertical M3 stripes. the metal stack is very restrictive, it is not easy to use other metals because of assumptions made with respect to V2 and V1. 
set m3pwrwidth 0.936
set m3pwrspacing 0.360
set m3pwrset2setdist    12.960

# looks like this   |0.936|0.360|0.936|long space... repeat pattern 
# if the last vertical M3 stripe is too close to the edge of the core, it can create a DRC violation. this stripe can be deleted manually.

addStripe  -skip_via_on_wire_shape Noshape \
    -set_to_set_distance $m3pwrset2setdist \
    -skip_via_on_pin Standardcell \
    -stacked_via_top_layer Pad \
    -spacing $m3pwrspacing \
    -xleft_offset 0.360 \
    -layer M3 \
    -width $m3pwrwidth \
    -nets {VDD VSS} \
    -stacked_via_bottom_layer M2 \
    -start_from left

# innovus 17 does some unusual large via selection for the power grid and generates violations
# the commands below fix that
if {$VERSION == 17} {
	editPowerVia -delete_vias 1 -top_layer 4 -bottom_layer 3
	editPowerVia -add_vias 1
}

# now we are going to add horizontal M4 stripes. the metal stack is very restrictive, it is not easy to use other metals because of assumptions made with respect to V2 and V1. 
set m4pwrwidth 0.864
set m4pwrspacing 0.864
set m4pwrset2setdist 21.6

# looks like this   |0.864|0.864|0.864|long space... repeat pattern 
addStripe  -skip_via_on_wire_shape Noshape \
    -direction horizontal \
    -set_to_set_distance $m4pwrset2setdist \
    -skip_via_on_pin Standardcell \
    -stacked_via_top_layer M7 \
    -spacing $m4pwrspacing \
    -layer M4 \
    -width $m4pwrwidth \
    -nets {VDD VSS} \
    -stacked_via_bottom_layer M3 \
    -start_from bottom

setSrouteMode -reset
setSrouteMode -viaConnectToShape { noshape }
sroute -connect { corePin } -layerChangeRange { M1(1) M7(1) } -blockPinTarget { nearestTarget } -floatingStripeTarget { blockring padring ring stripe ringpin blockpin followpin } -deleteExistingRoutes -allowJogging 0 -crossoverViaLayerRange { M1(1) Pad(10) } -nets { VDD VSS } -allowLayerChange 0 -targetViaLayerRange { M1(1) Pad(10) }

editPowerVia -add_vias 1 -orthogonal_only 0

verify_drc

setOptMode -holdTargetSlack  0.020
setOptMode -setupTargetSlack 0.020

#setPlaceMode -place_detail_preroute_as_obs 3

# this helps verify_drc realize that some metals are colored. 
colorizePowerMesh


place_opt_design

# add tie hi lo at this point. could have been handled in genus too.
setTieHiLoMode -maxFanout 5
addTieHiLo -prefix TIE -cell {TIELOx1_ASAP7_75t_SL TIEHIx1_ASAP7_75t_SL}

# CTS
ccopt_design

set_interactive_constraint_modes [all_constraint_modes -active]
reset_propagated_clock [all_clocks]
if {$VERSION == 21} {
	set_propagated_clock [all_clocks]
	#update_io_latency -source -verbose
} else {
	set_propagated_clock [all_clocks]
}

legalizePin  

routeDesign

# for some versions of innovus, silly mistakes are made when assigning colors to vias on the power rings. these lines fix it.
editPowerVia -delete_vias 1 -top_layer 7 -bottom_layer 6	
editPowerVia -delete_vias 1 -top_layer 6 -bottom_layer 5
editPowerVia -delete_vias 1 -top_layer 5 -bottom_layer 4
editPowerVia -delete_vias 1 -top_layer 4 -bottom_layer 3
editPowerVia -delete_vias 1 -top_layer 3 -bottom_layer 2
editPowerVia -delete_vias 1 -top_layer 2 -bottom_layer 1
editPowerVia -add_vias 1
setAnalysisMode -analysisType onChipVariation
setSIMode -enable_glitch_report true
setSIMode -enable_glitch_propagation true
setSIMode -enable_delay_report true
optDesign -postRoute
optDesign -postRoute -hold

report_noise -threshold 0.2 
report_noise -bumpy_waveform 

# Writing out the def file and the netlist
set defOutLefVia 1
set defOutLefNDR 1

# TODO change the setup of output if needed
defOut -netlist -routing -allLayers ${DB_PATH}${init_top_cell}.def
saveNetlist ${DB_PATH}${init_top_cell}.v
saveDesign ${DB_PATH}${init_top_cell}.enc													

# setStreamOutMode -reset

# streamOut ./sha256_v${VERSION}.gds.gz \
    # -mapFile {../gds/gds2.map} \
    # -libName DesignLib \
    # -uniquifyCellNames \
    # -outputMacros \
    # -stripes 1 \
    # -mode ALL \
    # -units 4000 \
    # -reportFile ../report/top/gds_stream_out_final.rpt \
    # -merge { ../gds/asap7sc7p5t_28_L_220121a_scaled4x.gds  ../gds/asap7sc7p5t_28_SL_220121a_scaled4x.gds }
    ## -merge { ../gds/asap7sc7p5t_28_L_220121a_scaled4x.gds  ../gds/asap7sc7p5t_28_R_220121a_scaled4x.gds  ../gds/asap7sc7p5t_28_SL_220121a_scaled4x.gds  ../gds/asap7sc7p5t_28_SRAM_220121a_scaled4x.gds}




# final notes
# there is a lot more that this script could do to become more industry-like. 
# - The SDC should be more realistic. The in/out constraints are picked almost arbitrarily.
# - It should handle path groups. 
# - It could have better setup/hold targets
# - It should handle DFT/scan. 
# - It should/could have more OPT runs to help with convergence at the end. 
# - It should do signoff-quality checks at the end, but this requires external quantus and licenses. Some users might not have it, so the commands are not provided
