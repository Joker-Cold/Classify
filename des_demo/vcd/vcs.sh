#!/bin/bash

# ==============================================================================
# VCS Gate-Level Simulation Script for VCD Generation
# ==============================================================================

# --- 1. 设置文件和路径 ---

# 设计文件
# 注意：这是 P&R 后的最终网表
GATE_NETLIST="../db/des3.v" 

# Testbench 文件
TESTBENCH="../testbench/des3_test_po_vcd.v" # 假设 testbench 在当前目录

# 工艺库的 Verilog 模型 (仿真必需)
# 使用通配符包含所有需要的库文件
LIB_FILES="../../../lib/asap7sc7p5t_*.v" 

# SPEF 文件 (用于反标精确的 RC 延迟)
# 注意：这是 P&R 后生成的
SPEF_FILE="../db/des3.spef"

# Testbench 中 DUT 的顶层实例路径 (用于 SDF 反标)
SDF_SCOPE="test.u0"

# 输出的 VCD 文件名 (应与 $dumpfile 中指定的名称一致)
VCD_FILE="test.vcd"

# VCS 编译后生成的可执行文件名
SIMV_EXEC="simv"

# --- 2. VCS 编译步骤 ---
# 使用 vcs 命令进行编译

echo "--- Starting VCS Compilation ---"
vcs \
    -full64 -LDFLAGS -Wl,--no-as-needed \
    -sverilog \
    +v2k \
    -timescale=1ps/1ps \
    -debug_access+all \
    +neg_tchk \
    +notimingchecks \
    -l vcs_compile.log \
    \
    -fsdb \
    $LIB_FILES \
    $GATE_NETLIST \
    $TESTBENCH \
    \
    -o $SIMV_EXEC

# 检查编译是否成功
if [ ! -f "$SIMV_EXEC" ]; then
    echo "VCS compilation failed. Check vcs_compile.log for errors."
    exit 1
fi
echo "--- VCS Compilation Successful ---"


# --- 3. VCS 仿真步骤 ---
# 运行编译生成的可执行文件 (simv)

echo "--- Starting Simulation to generate VCD ---"
chmod +x $SIMV_EXEC
./$SIMV_EXEC \
    +sdfverbose \
    +sdf_file=${SPEF_FILE}::${SDF_SCOPE} \
    -l sim.log

# 检查仿真是否成功以及 VCD 文件是否生成
if [ -f "$VCD_FILE" ]; then
    echo "--- Simulation Finished. VCD file '$VCD_FILE' generated successfully. ---"
else
    echo "Simulation failed or VCD file was not generated. Check sim.log for errors."
    exit 1
fi

# ==============================================================================
# 脚本结束
# ==============================================================================