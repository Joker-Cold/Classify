#!/bin/bash
# run_all.sh - 批量运行所有测试电路的分析流程
# 用法: ./run_all.sh [target]
#   target: analyze | coverage | all | clean (默认 all)

set -e

CIRCUITS="des_demo DMA_slow des_perf_slow vga_lcd_slow leon3mp_slow"
TARGET="${1:-all}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "============================================"
echo " 批量测试: target=$TARGET"
echo " 电路: $CIRCUITS"
echo "============================================"

PASS=0
FAIL=0

for circuit in $CIRCUITS; do
    echo ""
    echo "--------------------------------------------"
    echo " [$circuit] 开始 $TARGET"
    echo "--------------------------------------------"

    if make -C "$SCRIPT_DIR/$circuit" "$TARGET"; then
        echo " [$circuit] $TARGET 完成"
        PASS=$((PASS + 1))
    else
        echo " [$circuit] $TARGET 失败!"
        FAIL=$((FAIL + 1))
    fi
done

echo ""
echo "============================================"
echo " 汇总: $PASS 成功, $FAIL 失败 (共 $(echo $CIRCUITS | wc -w) 个电路)"
echo "============================================"

[ $FAIL -eq 0 ] || exit 1
