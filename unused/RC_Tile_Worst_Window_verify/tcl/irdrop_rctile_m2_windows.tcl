#===================================================
# RC-Tile + Phase-Aware 算法选窗 IR Drop 分析 (Innovus v20.10)
# m2: small-window mode (--small-window)
#   - generate_windows: L = 2*k_min + 1 = 5 cycles, center = argmax(e_t in phase)
#   - 参数 rho / eta 被忽略; 积分建模外包给 Innovus (动态 rail, 1ns resolution)
#   - peak-tile e_t + max-window score (inherited from m1)
# 算法: find_worst_window.py  (8x8 tile grid, phase-aware, RC-weighted)
# 参数: n_grid=8, k_theta=1.0, k_min=2, --small-window
#
# 选出 1 个 worst-case 窗口 (原始时间):
#   Window 1: 10600ns ~ 10850ns  (5 cycles, 250ns, argmax @ cycle 215 = 10750ns)
#   m2 score = 1029.131   (= e_t peak @ cycle 215)
# 压缩率 beta_out = 2.1% (5/238 cycles)  — 相比 m0/m1/m1b 的 29.83% 大幅下降
# 拼接 VCD 时间已重映射到 #0,本段对应 0 ~ 250ns
#===================================================

# Step 1: 加载设计 (照抄 irdrop_algo_windows.tcl)
set init_design_uniquify 1
set init_design_netlisttype Verilog
set init_design_settop 1
set init_top_cell des3
set init_verilog {../../db/des3.v}
set init_lef_file { \
    ../../db/des3.enc.dat/libs/lef/asap7_tech_4x_201209.lef \
    ../../db/des3.enc.dat/libs/lef/asap7sc7p5t_28_L_4x_220121a.lef \
    ../../db/des3.enc.dat/libs/lef/asap7sc7p5t_28_SL_4x_220121a.lef \
}
set init_pwr_net VDD
set init_gnd_net VSS
set init_mmmc_file ../../db/des3.enc.dat/viewDefinition.tcl
init_design
defIn ../../db/des3.def
globalNetConnect VDD -type pgpin -pin VDD -inst *
globalNetConnect VSS -type pgpin -pin VSS -inst *
setMultiCpuUsage -localCpu 8

# Step 2: 复用已有 PG Library (skip generate_pg_library)

# ===== RC-Tile_m2 Window 1: 原始 10600~10850ns (拼接VCD: 0~250ns) =====
puts "========================================"
puts "=== RC-Tile_m2 Window 1: 10600ns ~ 10850ns (orig) / 0~250ns (spliced) ==="
puts "========================================"

# --- 功耗分析 ---
set_power_analysis_mode -reset
set_power_analysis_mode \
    -method dynamic_vectorbased \
    -create_binary_db true \
    -current_generation_method avg
read_activity_file -format VCD ../../vcd/test_rctile_m2.vcd \
    -scope test/u0 \
    -start 0ns \
    -end 250ns
set_dynamic_power_simulation -resolution 1ns
report_power -o ../../db/power/avg_v20_rctile_m2_win1

# --- IR Drop 分析 ---
set_pg_nets -net VDD -voltage 0.7 -threshold 0.651
set_pg_nets -net VSS -voltage 0   -threshold 0.1
set_power_pads -net VDD -format xy -file ./ring_pads_vdd_clean.ppl
set_power_pads -net VSS -format xy -file ./ring_pads_vss_clean.ppl
set_power_data -format current \
    [list ../../db/power/avg_v20_rctile_m2_win1/dynamic_VDD.ptiavg \
          ../../db/power/avg_v20_rctile_m2_win1/dynamic_VSS.ptiavg]
set_rail_analysis_mode \
    -method dynamic \
    -accuracy xd \
    -power_grid_library ./des3_pg_v20/techonly.cl \
    -limit_number_of_steps false
set_rail_analysis_domain -name PD -pwrnets VDD -gndnets VSS
analyze_rail -type domain -output ../../db/rail_power_v20_rctile_m2_win1 PD

puts "=== RC-Tile_m2 Window 1 done ==="

puts "========================================"
puts "=== All rctile_m2 windows completed ==="
puts "========================================"
exit
