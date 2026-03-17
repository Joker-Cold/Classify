#######################################################
#                                                     
#  Innovus Command Logging File                     
#  Created on Fri Dec 19 21:09:33 2025                
#                                                     
#######################################################

#@(#)CDS: Innovus v19.10-p002_1 (64bit) 04/19/2019 15:18 (Linux 2.6.32-431.11.2.el6.x86_64)
#@(#)CDS: NanoRoute 19.10-p002_1 NR190418-1643/19_10-UB (database version 18.20, 458.7.1) {superthreading v1.51}
#@(#)CDS: AAE 19.10-b002 (64bit) 04/19/2019 (Linux 2.6.32-431.11.2.el6.x86_64)
#@(#)CDS: CTE 19.10-p002_1 () Apr 19 2019 06:39:48 ( )
#@(#)CDS: SYNTECH 19.10-b001_1 () Apr  4 2019 03:00:51 ( )
#@(#)CDS: CPE v19.10-p002
#@(#)CDS: IQuantus/TQuantus 19.1.0-e101 (64bit) Thu Feb 28 10:29:46 PST 2019 (Linux 2.6.32-431.11.2.el6.x86_64)

set_global _enable_mmmc_by_default_flow      $CTE::mmmc_default
suppressMessage ENCEXT-2799
getVersion
set init_design_uniquify 1
set init_verilog ../../netlist/des3_netlist.v
set init_design_netlisttype Verilog
set init_design_settop 1
set init_top_cell des3
set init_lef_file {../../../../techlef/asap7_tech_4x_201209.lef ../../../../lef/scaled/asap7sc7p5t_28_L_4x_220121a.lef ../../../../lef/scaled/asap7sc7p5t_28_SL_4x_220121a.lef}
set fp_core_cntl aspect
set fp_aspect_ratio 1.0000
set extract_shrink_factor 1.0
set init_assign_buffer 0
set init_pwr_net VDD
set init_gnd_net VSS
set init_cpf_file {}
set init_mmmc_file ./des3.mmmc
init_design
setDesignMode -process 7
setMultiCpuUsage -localCpu 8
setNanoRouteMode -routeBottomRoutingLayer 2
setNanoRouteMode -routeTopRoutingLayer 7
globalNetConnect VDD -type pgpin -pin VDD -inst *
globalNetConnect VSS -type pgpin -pin VSS -inst *
floorPlan -site asap7sc7p5t -r 1.0 0.7 6.22 6.22 6.22 6.22
addWellTap -cell TAPCELL_ASAP7_75t_L -cellInterval 12.960 -inRowOffset 1.296
setPinAssignMode -pinEditInBatch true
editPin -fixOverlap 1 -spreadDirection clockwise -side Left -layer 3 -spreadType side -pin {{desIn[0]} {desIn[1]} {desIn[2]} {desIn[3]} {desIn[4]} {desIn[5]} {desIn[6]} {desIn[7]} {desIn[8]} {desIn[9]} {desIn[10]} {desIn[11]} {desIn[12]} {desIn[13]} {desIn[14]} {desIn[15]} {desIn[16]} {desIn[17]} {desIn[18]} {desIn[19]} {desIn[20]} {desIn[21]} {desIn[22]} {desIn[23]} {desIn[24]} {desIn[25]} {desIn[26]} {desIn[27]} {desIn[28]} {desIn[29]} {desIn[30]} {desIn[31]} {desIn[32]} {desIn[33]} {desIn[34]} {desIn[35]} {desIn[36]} {desIn[37]} {desIn[38]} {desIn[39]} {desIn[40]} {desIn[41]} {desIn[42]} {desIn[43]} {desIn[44]} {desIn[45]} {desIn[46]} {desIn[47]} {desIn[48]} {desIn[49]} {desIn[50]} {desIn[51]} {desIn[52]} {desIn[53]} {desIn[54]} {desIn[55]} {desIn[56]} {desIn[57]} {desIn[58]} {desIn[59]} {desIn[60]} {desIn[61]} {desIn[62]} {desIn[63]} {key1[0]} {key1[1]} {key1[2]} {key1[3]} {key1[4]} {key1[5]} {key1[6]} {key1[7]} {key1[8]} {key1[9]} {key1[10]} {key1[11]} {key1[12]} {key1[13]} {key1[14]} {key1[15]} {key1[16]} {key1[17]} {key1[18]} {key1[19]} {key1[20]} {key1[21]} {key1[22]} {key1[23]} {key1[24]} {key1[25]} {key1[26]} {key1[27]} {key1[28]} {key1[29]} {key1[30]} {key1[31]} {key1[32]} {key1[33]} {key1[34]} {key1[35]} {key1[36]} {key1[37]} {key1[38]} {key1[39]} {key1[40]} {key1[41]} {key1[42]} {key1[43]} {key1[44]} {key1[45]} {key1[46]} {key1[47]} {key1[48]} {key1[49]} {key1[50]} {key1[51]} {key1[52]} {key1[53]} {key1[54]} {key1[55]} {key2[0]} {key2[1]} {key2[2]} {key2[3]} {key2[4]} {key2[5]} {key2[6]} {key2[7]} {key2[8]} {key2[9]} {key2[10]} {key2[11]} {key2[12]} {key2[13]} {key2[14]} {key2[15]} {key2[16]} {key2[17]} {key2[18]} {key2[19]} {key2[20]} {key2[21]} {key2[22]} {key2[23]} {key2[24]} {key2[25]} {key2[26]} {key2[27]} {key2[28]} {key2[29]} {key2[30]} {key2[31]} {key2[32]} {key2[33]} {key2[34]} {key2[35]} {key2[36]} {key2[37]} {key2[38]} {key2[39]} {key2[40]} {key2[41]} {key2[42]} {key2[43]} {key2[44]} {key2[45]} {key2[46]} {key2[47]} {key2[48]} {key2[49]} {key2[50]} {key2[51]} {key2[52]} {key2[53]} {key2[54]} {key2[55]} {key3[0]} {key3[1]} {key3[2]} {key3[3]} {key3[4]} {key3[5]} {key3[6]} {key3[7]} {key3[8]} {key3[9]} {key3[10]} {key3[11]} {key3[12]} {key3[13]} {key3[14]} {key3[15]} {key3[16]} {key3[17]} {key3[18]} {key3[19]} {key3[20]} {key3[21]} {key3[22]} {key3[23]} {key3[24]} {key3[25]} {key3[26]} {key3[27]} {key3[28]} {key3[29]} {key3[30]} {key3[31]} {key3[32]} {key3[33]} {key3[34]} {key3[35]} {key3[36]} {key3[37]} {key3[38]} {key3[39]} {key3[40]} {key3[41]} {key3[42]} {key3[43]} {key3[44]} {key3[45]} {key3[46]} {key3[47]} {key3[48]} {key3[49]} {key3[50]} {key3[51]} {key3[52]} {key3[53]} {key3[54]} {key3[55]} {decrypt} {clk}}
editPin -fixOverlap 1 -spreadDirection clockwise -side Right -layer 3 -spreadType side -pin {{desOut[0]} {desOut[1]} {desOut[2]} {desOut[3]} {desOut[4]} {desOut[5]} {desOut[6]} {desOut[7]} {desOut[8]} {desOut[9]} {desOut[10]} {desOut[11]} {desOut[12]} {desOut[13]} {desOut[14]} {desOut[15]} {desOut[16]} {desOut[17]} {desOut[18]} {desOut[19]} {desOut[20]} {desOut[21]} {desOut[22]} {desOut[23]} {desOut[24]} {desOut[25]} {desOut[26]} {desOut[27]} {desOut[28]} {desOut[29]} {desOut[30]} {desOut[31]} {desOut[32]} {desOut[33]} {desOut[34]} {desOut[35]} {desOut[36]} {desOut[37]} {desOut[38]} {desOut[39]} {desOut[40]} {desOut[41]} {desOut[42]} {desOut[43]} {desOut[44]} {desOut[45]} {desOut[46]} {desOut[47]} {desOut[48]} {desOut[49]} {desOut[50]} {desOut[51]} {desOut[52]} {desOut[53]} {desOut[54]} {desOut[55]} {desOut[56]} {desOut[57]} {desOut[58]} {desOut[59]} {desOut[60]} {desOut[61]} {desOut[62]} {desOut[63]}}
editPin -snap TRACK -pin *
setPinAssignMode -pinEditInBatch false
legalizePin
setAddRingMode -ring_target default -extend_over_row 0 -ignore_rows 0 -avoid_short 0 -skip_crossing_trunks none -stacked_via_top_layer Pad -stacked_via_bottom_layer M1 -via_using_exact_crossover_size 1 -orthogonal_only true -skip_via_on_pin {  standardcell } -skip_via_on_wire_shape {  noshape }
addRing -nets {VDD VSS} -type core_rings -follow core -layer {top M7 bottom M7 left M6 right M6} -width 2.176 -spacing 0.384 -offset 0.384 -center 0 -threshold 0 -jog_distance 0 -snap_wire_center_to_grid None
addStripe -skip_via_on_wire_shape blockring -direction horizontal -set_to_set_distance 2.16 -skip_via_on_pin Standardcell -stacked_via_top_layer M1 -layer M2 -width 0.072 -nets VDD -stacked_via_bottom_layer M1 -start_from bottom -snap_wire_center_to_grid None -start_offset -0.044 -stop_offset -0.044
addStripe -skip_via_on_wire_shape blockring -direction horizontal -set_to_set_distance 2.16 -skip_via_on_pin Standardcell -stacked_via_top_layer M1 -layer M2 -width 0.072 -nets VSS -stacked_via_bottom_layer M1 -start_from bottom -snap_wire_center_to_grid None -start_offset 1.036 -stop_offset -0.044
addStripe -skip_via_on_wire_shape Noshape -set_to_set_distance 12.960 -skip_via_on_pin Standardcell -stacked_via_top_layer Pad -spacing 0.360 -xleft_offset 0.360 -layer M3 -width 0.936 -nets {VDD VSS} -stacked_via_bottom_layer M2 -start_from left
addStripe -skip_via_on_wire_shape Noshape -direction horizontal -set_to_set_distance 21.6 -skip_via_on_pin Standardcell -stacked_via_top_layer M7 -spacing 0.864 -layer M4 -width 0.864 -nets {VDD VSS} -stacked_via_bottom_layer M3 -start_from bottom
setSrouteMode -reset
setSrouteMode -viaConnectToShape { noshape }
sroute -connect { corePin } -layerChangeRange { M1(1) M7(1) } -blockPinTarget { nearestTarget } -floatingStripeTarget { blockring padring ring stripe ringpin blockpin followpin } -deleteExistingRoutes -allowJogging 0 -crossoverViaLayerRange { M1(1) Pad(10) } -nets { VDD VSS } -allowLayerChange 0 -targetViaLayerRange { M1(1) Pad(10) }
editPowerVia -add_vias 1 -orthogonal_only 0
verify_drc
setOptMode -holdTargetSlack 0.020
setOptMode -setupTargetSlack 0.020
colorizePowerMesh
place_opt_design
setTieHiLoMode -maxFanout 5
addTieHiLo -prefix TIE -cell {TIELOx1_ASAP7_75t_SL TIEHIx1_ASAP7_75t_SL}
ccopt_design
all_constraint_modes -active
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
setSIMode -enable_glitch_report true
setSIMode -enable_glitch_propagation true
setSIMode -enable_delay_report true
optDesign -postRoute
optDesign -postRoute -hold
report_noise -threshold 0.2
report_noise -bumpy_waveform
set defOutLefVia 1
set defOutLefNDR 1
defOut -netlist -routing -allLayers ../../db/des3.def
saveNetlist ../../db/des3.v
saveDesign ../../db/des3.enc
rcOut -spef des3.spef
set_power_analysis_mode -method dynamic_vectorbased -power_grid_library ./des3_pg/techonly.cl -create_binary_db true -current_generation_method avg
read_activity_file -format VCD ../../vcd/test.vcd -scope test/u0 -start 4000ns -end 5000ns
set_dynamic_power_simulation -resolution 1ns
report_power -o ../../db/power/avg
set_pg_nets -net VSS -voltage 0 -threshold 0.1
set_pg_nets -net VDD -voltage 0.7 -threshold 0.651
set_power_pads -net VDD -format xy -file ./ring_pads_vdd.ppl
set_power_pads -net VSS -format xy -file ./ring_pads_vss.ppl
set_power_data -format current {../../db/power/avg/dynamic_VDD.ptiavg ../../db/power/avg/dynamic_VSS.ptiavg}
set_rail_analysis_mode -method dynamic -accuracy xd -power_grid_library ./des3_pg/techonly.cl
set_rail_analysis_domain -name PD -pwrnets VDD -gndnets VSS
analyze_rail -type domain -output ../../db/rail_power PD
rcOut -spef ../../db/des3.spef
