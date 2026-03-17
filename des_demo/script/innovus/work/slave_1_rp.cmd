net_voltage VSS 0 0.1
net_voltage VDD 0.7 0.651
setvar analysis_power_domain PD
power_domain PD pwrnet="VDD" gndnet="VSS"
setvar enable_dist_report_generation false
setvar powerpin_location_file /home/IC/Desktop/des_demo/script/innovus/./ring_pads_vss.ppl
setvar enable_eiv_decap_opt 0
setvar enable_threadpool_iv true
setvar dc_state_file_processing_mode 1
setvar eiv_generate_domain_gif false
setvar use_cell_id true
setvar use_new_eiv true
setvar eiv_report_old true
setvar eiv_report_auto true
setvar eiv_report_net false
setvar report_voltage_drop false
setvar eiv_threshold -1000000000.000000
setvar ignore_incomplete_net false
current_data_file scale=1 ../../db/power/avg_v15/dynamic_VDD.ptiavg
current_data_file scale=1 ../../db/power/avg_v15/dynamic_VSS.ptiavg
setvar gif_resolution_option low
setvar gif_zoom_topcell_diearea false
setvar gif_voltage_drop false
setvar enable_procinfo_more false
setvar enable_procinfo_indent false
setvar debug_ibb false
setvar debug_minst false
setvar debug_mpin false
setvar max_cpu 2
