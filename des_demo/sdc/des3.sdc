# ==============================================================================
# SDC (Synopsys Design Constraints) for 'des3' Pipelined Design
#
# Target Technology: asap7 (7nm FinFET)
# Target Clock Freq: 100 MHz (10 ns period)
#
# Design Characteristics from Testbench Analysis:
# - Pipelined architecture (new data every cycle).
# - Latency of 51 clock cycles from input to output.
#
# Note: ASAP7 library units are ps for time and fF for capacitance.
# 100 MHz -> 10 ns -> 10,000 ps
# ==============================================================================

# --- 1. SDC Version ---
set sdc_version 2.0

# --- 2. Port Definitions (for clarity and reusability) ---
#    [IMPORTANT]: These port names are based on your Verilog module 'des3'.
set CLK_PORT     [get_ports {clk}]
set DECRYPT_PORT [get_ports {decrypt}]
set KEY1_INPUTS  [get_ports {key1[*]}]
set KEY2_INPUTS  [get_ports {key2[*]}]
set KEY3_INPUTS  [get_ports {key3[*]}]
set DATA_INPUTS  [get_ports {desIn[*]}]
set DATA_OUTPUTS [get_ports {desOut[*]}]

# Group all I/O ports for easier constraint application
set ALL_INPUTS_EXCEPT_CLK [remove_from_collection [all_inputs] $CLK_PORT]
set ALL_OUTPUTS           [all_outputs]

# --- 3. Primary Clock Definition ---
set CLK_NAME "core_clk"
# The period is defined in the library's time units (ps for ASAP7)
set CLK_PERIOD 10000.0  ;# 10,000 ps = 10 ns = 100 MHz

create_clock -name $CLK_NAME -period $CLK_PERIOD $CLK_PORT

# --- 4. Clock Characteristics ---
# These values are reasonable starting points for a 7nm process.
set_clock_uncertainty -setup 300.0 [get_clocks $CLK_NAME]  ;# 3% of period for setup
set_clock_uncertainty -hold  150.0 [get_clocks $CLK_NAME]  ;# 1.5% of period for hold
set_clock_transition  -max   500.0 [all_clocks]            ;# 5% of period for transition

# --- 5. I/O Driving Cell and Load ---
# This section models the external environment of the chip.

# Assume inputs are driven by a typical flip-flop from the same library.
# SDFXTP_X2 is a standard D-Flip-Flop in the ASAP7 library.
# set_driving_cell \
#     -lib_cell SDFXTP_X2 \
#     -pin Q \
#     $ALL_INPUTS_EXCEPT_CLK

# Assume the output drives a load equivalent to 4 standard inverters.
# The input capacitance of SINV_X2 is ~0.58fF. 4 * 0.58fF = 2.32fF.
# set_load 2.32 $ALL_OUTPUTS

# --- 6. I/O Path Delays (Input and Output Constraints) ---
# This section defines the timing budget for paths outside this module.
# Since this is a pipelined design, we assume the inputs and outputs
# are registered externally, so we can allocate roughly half a cycle
# for external paths and half for internal paths.
set INPUT_DELAY  [expr $CLK_PERIOD * 0.4] ;# 40% of period for external input path
set OUTPUT_DELAY [expr $CLK_PERIOD * 0.4] ;# 40% of period for external output path

set_input_delay  -max $INPUT_DELAY  -clock $CLK_NAME $ALL_INPUTS_EXCEPT_CLK
set_input_delay  -min [expr $INPUT_DELAY * 0.5] -clock $CLK_NAME $ALL_INPUTS_EXCEPT_CLK

set_output_delay -max $OUTPUT_DELAY -clock $CLK_NAME $ALL_OUTPUTS
set_output_delay -min [expr $OUTPUT_DELAY * 0.5] -clock $CLK_NAME $ALL_OUTPUTS

# --- 7. Timing Exceptions ---
# This section is for telling the tool about paths that should be treated
# differently from the default single-cycle analysis.

# CRITICAL: The testbench shows a 51-cycle latency from input to output.
# This is a classic multi-cycle path (MCP) scenario.
# If we don't specify this, the tool will try to make the entire 51-stage
# pipeline finish in ONE cycle, which is impossible and will fail synthesis.
echo "Info: Applying 51-cycle multicycle path constraint for DES3 computation."
set_multicycle_path 51 -setup -from [all_inputs] -to [all_outputs]
set_multicycle_path 50 -hold  -from [all_inputs] -to [all_outputs]

# The 'decrypt' signal is a control signal that is stable for many cycles
# during a test run. It is not a high-speed data path.
# The MCP above already covers it, but we could also set it as a false path
# if we wanted to completely ignore its timing for setup/hold, though
# the MCP is a more accurate representation.
# Example (optional): set_false_path -from $DECRYPT_PORT

# --- 8. Other Design Rules (Optional but Recommended) ---
# These constraints help the tool manage electrical properties.

# Set a global maximum fanout limit to prevent a single gate from driving too many loads.
# set_max_fanout 16 [current_design]

# Set a global maximum transition time limit on nets to ensure good signal integrity.
# set_max_transition 800.0 [current_design] ;# 8% of clock period

# ======================= End of SDC File =======================