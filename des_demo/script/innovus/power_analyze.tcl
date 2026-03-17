# Power analysis

# Configure dynamic, vector-based power analysis and enable binary DB output
set_power_analysis_mode \
    -method dynamic_vectorbased \
    -power_grid_library ./des3_pg/techonly.cl \
    -create_binary_db true \
    -current_generation_method avg \

# Load switching activity from VCD within the target scope and time window
# TODO change VCD file path, start time, end time if needed
read_activity_file \
    -format VCD ../../vcd/test.vcd \
    -scope test/u0 \
    -start 4000ns \
    -end 5000ns

# Set transient simulation resolution for dynamic power
set_dynamic_power_simulation \
    -resolution 1ns

# Generate average power report to the database path
report_power -o ../../db/power/avg