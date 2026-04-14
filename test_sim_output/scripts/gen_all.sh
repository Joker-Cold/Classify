#!/bin/bash
# ==============================================================================
# gen_all.sh — 一键生成所有 ISPD2012 电路的 cell 模型 + testbench
#
# 用法:
#   ./gen_all.sh [--num-vectors 200]
#
# 生成:
#   1. test_circuit/ispd2012/lib/contest_cells.v  (cell 行为模型, 只需生成一次)
#   2. {circuit}/testbench/tb_{circuit}.v          (每个电路的 testbench)
# ==============================================================================

set -e

NUM_VECTORS="${1:-200}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"
ISPD_DIR="${BASE_DIR}/../test_circuit/ispd2012"

CIRCUITS="DMA_slow des_perf_slow vga_lcd_slow leon3mp_slow"

echo "============================================"
echo " 生成 cell 模型 + testbench"
echo " 测试向量数: $NUM_VECTORS"
echo "============================================"
echo ""

# --- Step 1: 生成 cell 行为模型 ---
CELL_MODELS="${ISPD_DIR}/lib/contest_cells.v"
if [ -f "$CELL_MODELS" ]; then
    echo "[跳过] Cell 模型已存在: $CELL_MODELS"
else
    echo "[1] 生成 cell 行为模型..."
    python3 "$SCRIPT_DIR/gen_cell_models.py" \
        --lib "${ISPD_DIR}/lib/contest.lib" \
        --output "$CELL_MODELS"
fi
echo ""

# --- Step 2: 为每个电路生成 testbench ---
for circuit in $CIRCUITS; do
    echo "--------------------------------------------"
    echo " [$circuit] 生成 testbench"
    echo "--------------------------------------------"

    NETLIST="${ISPD_DIR}/${circuit}/${circuit}.v"
    SDC="${ISPD_DIR}/${circuit}/${circuit}.sdc"
    TB_OUT="${BASE_DIR}/${circuit}/testbench/tb_${circuit}.v"

    if [ ! -f "$NETLIST" ]; then
        echo "  WARNING: 网表不存在: $NETLIST, 跳过"
        continue
    fi

    python3 "$SCRIPT_DIR/gen_testbench.py" \
        --netlist "$NETLIST" \
        --sdc "$SDC" \
        --output "$TB_OUT" \
        --num-vectors "$NUM_VECTORS" \
        --vcd-file "sim.vcd"

    echo ""
done

echo "============================================"
echo " 全部生成完成!"
echo " 下一步: 在远程服务器运行 run_vcs.sh <circuit>"
echo "============================================"
