set_clock_latency -source -early -max -rise  -127.616 [get_ports {clk}] -clock core_clk 
set_clock_latency -source -early -max -fall  -126.804 [get_ports {clk}] -clock core_clk 
set_clock_latency -source -late -max -rise  -127.616 [get_ports {clk}] -clock core_clk 
set_clock_latency -source -late -max -fall  -126.804 [get_ports {clk}] -clock core_clk 
