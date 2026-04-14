#!/bin/bash
# ==============================================================================
# run_vcs.sh — ISPD2012 电路 VCS 门级仿真脚本
#
# 用法:
#   ./run_vcs.sh <circuit_name>
#   例: ./run_vcs.sh DMA_slow
#
# 前置条件:
#   1. 已运行 gen_cell_models.py 生成 contest_cells.v
#   2. 已运行 gen_testbench.py 生成 testbench
#   3. VCS 环境已配置
# ==============================================================================

set -e

CIRCUIT="$1"
if [ -z "$CIRCUIT" ]; then
    echo "用法: $0 <circuit_name>"
    echo "  可选: DMA_slow, des_perf_slow, vga_lcd_slow, leon3mp_slow"
    exit 1
fi

# --- 路径配置 ---
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"
ISPD_DIR="${BASE_DIR}/../test_circuit/ispd2012"
CIRCUIT_DIR="${BASE_DIR}/${CIRCUIT}"

# 源文件
NETLIST="${ISPD_DIR}/${CIRCUIT}/${CIRCUIT}.v"
CELL_MODELS="${ISPD_DIR}/lib/contest_cells.v"
TESTBENCH="${CIRCUIT_DIR}/testbench/tb_${CIRCUIT}.v"

# 输出
VCD_FILE="${CIRCUIT_DIR}/vcd/sim.vcd"
SIMV_EXEC="${CIRCUIT_DIR}/vcd/simv"
COMPILE_LOG="${CIRCUIT_DIR}/vcd/vcs_compile.log"
SIM_LOG="${CIRCUIT_DIR}/vcd/sim.log"

# --- 检查文件 ---
for f in "$NETLIST" "$CELL_MODELS" "$TESTBENCH"; do
    if [ ! -f "$f" ]; then
        echo "ERROR: 文件不存在: $f"
        exit 1
    fi
done

echo "============================================"
echo " VCS 仿真: $CIRCUIT"
echo "============================================"
echo "  网表:     $NETLIST"
echo "  Cell 模型: $CELL_MODELS"
echo "  Testbench: $TESTBENCH"
echo "  VCD 输出:  $VCD_FILE"
echo ""

# --- 1. VCS 编译 ---
echo "--- [1/2] VCS 编译 ---"
cd "${CIRCUIT_DIR}/vcd"

vcs \
    -full64 -LDFLAGS -Wl,--no-as-needed \
    -sverilog \
    +v2k \
    -timescale=1ps/1ps \
    -debug_access+all \
    +notimingchecks \
    -l "$COMPILE_LOG" \
    "$CELL_MODELS" \
    "$NETLIST" \
    "$TESTBENCH" \
    -o "$SIMV_EXEC"

if [ ! -f "$SIMV_EXEC" ]; then
    echo "ERROR: VCS 编译失败, 查看 $COMPILE_LOG"
    exit 1
fi
echo "--- VCS 编译成功 ---"

# --- 2. 运行仿真 ---
echo "--- [2/2] 运行仿真 ---"
chmod +x "$SIMV_EXEC"
"$SIMV_EXEC" -l "$SIM_LOG"

if [ -f "$VCD_FILE" ]; then
    VCD_SIZE=$(du -h "$VCD_FILE" | cut -f1)
    echo ""
    echo "============================================"
    echo " 仿真完成: $VCD_FILE ($VCD_SIZE)"
    echo "============================================"
else
    echo "ERROR: VCD 文件未生成, 查看 $SIM_LOG"
    exit 1
fi
