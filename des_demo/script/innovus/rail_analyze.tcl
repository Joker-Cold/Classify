# Rail Analysis

# Define power/ground nets, voltages, and IR-drop thresholds
set_pg_nets -net VSS -voltage 0 -threshold 0.1
set_pg_nets -net VDD -voltage 0.7 -threshold 0.651

# Provide ring power-pad coordinate files (xy format)
set_power_pads -net VDD -format xy -file ./ring_pads_vdd.ppl
set_power_pads -net VSS -format xy -file ./ring_pads_vss.ppl

# Load dynamic power waveforms (ptiavg) for rail analysis
set_power_data -format current {../../db/power/avg/dynamic_VDD.ptiavg ../../db/power/avg/dynamic_VSS.ptiavg}

# Configure rail dynamic analysis: method, accuracy, and power-grid library
set_rail_analysis_mode \
    -method dynamic \
    -accuracy xd \
    -power_grid_library ./des3_pg/techonly.cl

# Define analysis domain, binding power and ground nets
set_rail_analysis_domain -name PD -pwrnets VDD -gndnets VSS

# Run rail analysis and emit report path
analyze_rail -type domain -output ../../db/rail_power PD