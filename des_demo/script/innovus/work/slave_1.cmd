setvar temp_directory_name /tmp/innovus_temp_65366_IC_IC_3lzmeZ/
setvar enable_scheduler true 
setvar use_cell_id true
setvar use_high_accuracy_for_rc_reduction false
setvar disable_rc_reduction_in_solver false
setvar enable_report_db true
setvar analysis_output_directory ../../db/rail_power_v15/PD_25C_dynamic_1//VSS
setvar enable_central_report true
setvar enable_backward_compatibility_symlink true
setvar work_directory_name ./work
setvar library_name ./des3_pg_v15/techonly.cl
layout_file /tmp/innovus_temp_65366_IC_IC_3lzmeZ/eps_out_65366.def.gz 
setvar temperature 25
setvar vsrc_search_distance 50
power_pin_supply_tolerance 0 0.3
setvar powerpin_location_file /home/IC/Desktop/des_demo/script/innovus/./ring_pads_vss.ppl
setvar use_toplevel_pins false
use_cell_view type standard fast
use_cell_view type macro fast
use_cell_view type io fast
use_cell_view type powergate fast
setvar voltus_accuracy_mode xd
setvar voltus_analysis_mode dynamic
current_data_file reset
current_data_file scale=1 ../../db/power/avg_v15/dynamic_VDD.ptiavg
current_data_file scale=1 ../../db/power/avg_v15/dynamic_VSS.ptiavg
cell_power_file 1 0.7
setvar mge_load_static_pti true
setvar cluster_via_size 25
setvar cluster_via1_ports true
setvar ignore_fillers true
setvar ignore_fillers_with_cap true
setvar hierarchy_char /
setvar nga_enabled true
setvar nga_max_partitions 1
setvar report_msmv_format true
setvar report_grid_weak_conn true
setvar report_cell_grid_weak_conn false
setvar ignore_shorts true
setvar speed_ms 0
setvar enable_new_pkg_solver false
setvar max_cpu 2
setvar decap_sync_switching_file 1
setvar dc_state_file_processing_mode 1
setvar enable_threadpool_iv true
setvar use_new_eiv true
setvar eiv_report_old true
setvar eiv_report_auto true
setvar eiv_report_net false
setvar report_voltage_drop false
setvar eiv_threshold -1000000000.000000
setvar enable_procinfo_more false
setvar enable_procinfo_indent false
setvar debug_ibb false
setvar debug_minst false
setvar debug_mpin false
setvar find_unique_uti_files true
setvar enable_smg false
setvar enable_dist_report_generation false
setvar read_pincap_from_uti false
setvar enable_fast_exit false
nga_setvar nga_limit_number_of_steps {true}
