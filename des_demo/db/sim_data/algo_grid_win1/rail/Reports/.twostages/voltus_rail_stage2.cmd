# Voltus_rail Command File

#Result directory
setvar output_directory_name ../../db/rail_power_v20_algo_win1

#Distributed processing setting
setvar max_cpu 8
setvar nga_enabled true
nga_dp_hosts max_cpu=8 mode=local time_out=0

#Layout Files
layout_file /tmp/innovus_temp_694076_hzhb-Super-Server_myzhu_YizYIH/eps_out_694076.def.gz

#Cell Library
cell_library ./des3_pg_v20/techonly.cl
setvar tesla_accuracy_mode xd
use_cell_view type standard fast
use_cell_view type macro fast
use_cell_view type io fast
use_cell_view type powergate fast
setvar power_up_fast_mode true
setvar report_msmv_format true
setvar compress_powergrid_database false
setvar hierarchy_char /
setvar use_cell_id true
nga_setvar nga_enable_new_transient_analysis true
setvar enable_smx true
setvar ignore_shorts true
setvar enable_manufacturing_effects false
setvar cluster_via1_ports true
setvar ignore_fillers true
setvar ignore_fillers_with_cap true
setvar gif_resolution_option low
setvar gif_zoom_topcell_diearea false
setvar keep_log false
setvar enable_report_db true
setvar eiv_report_auto true
nga_setvar nga_current_redistribution true
setvar mge_load_static_pti false
net_voltage VDD 0.7 0.651
power_pin_supply_tolerance 0.49 0.91 net=VDD
net_voltage VSS 0 0.1
power_pin_supply_tolerance 0 0.3 net=VSS
power_domain PD pwrnet="VDD" gndnet="VSS"
current_data_file ../../db/power/avg_v20_algo_win1/dynamic_VDD.ptiavg
current_data_file ../../db/power/avg_v20_algo_win1/dynamic_VSS.ptiavg
power_pin VDD file=/home/myzhu/data/des_demo/script/innovus/./ring_pads_vdd_clean.ppl
power_pin VSS file=/home/myzhu/data/des_demo/script/innovus/./ring_pads_vss_clean.ppl
analyze PD 0.7 dynamic 0.10 ir tc iv vc dd pi pv
