#!/bin/bash
# =============================================================
# run_all.sh — Sequential P&R + Voltus for DMA_slow
# Usage: bash run_all.sh [traditional|risk_propagation]
# =============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CIRCUIT_DIR="$(dirname "$SCRIPT_DIR")"
METHOD="${1:-traditional}"

# ---- Cadence environment ----
source /etc/profile
export INNOVUS201_HOME=/data/Installed_tools/cadence/INNOVUS201
export PATH=$INNOVUS201_HOME/tools/bin:$PATH
# CDS_LIC_FILE is set by /etc/profile (local .dat files)

echo "============================================"
echo "DMA_slow P&R + Voltus pipeline"
echo "Method: $METHOD"
echo "============================================"

# ---- Step 1: Generate LEF if needed ----
TSIMOUT_DIR="$(dirname "$CIRCUIT_DIR")"
SHARED_SCRIPTS="$TSIMOUT_DIR/scripts"
if [ ! -f "$SHARED_SCRIPTS/contest_cells.lef" ]; then
    echo "[1/4] Generating contest_cells.lef ..."
    python3 "$SHARED_SCRIPTS/gen_contest_lef.py" \
        "$TSIMOUT_DIR/lib/contest.lib" "$SHARED_SCRIPTS/contest_cells.lef"
    echo "      contest_cells.lef generated."
else
    echo "[1/4] contest_cells.lef already exists, skipping."
fi

# ---- Step 2: P&R ----
echo "[2/4] Running Innovus P&R ..."
innovus -nowin -init "$SCRIPT_DIR/innovus/pr_flow.tcl" \
        -log "$SCRIPT_DIR/pr_flow.log" 2>&1 | tee "$SCRIPT_DIR/pr_flow.stdout"
echo "      P&R complete."

# ---- Step 3: Full VCD Voltus ----
echo "[3/4] Running Voltus (full VCD) ..."
innovus -nowin -init "$SCRIPT_DIR/innovus/voltus_full.tcl" \
        -log "$SCRIPT_DIR/voltus_full.log" 2>&1 | tee "$SCRIPT_DIR/voltus_full.stdout"
echo "      Voltus full done."

# ---- Step 4: Compressed VCD Voltus ----
echo "[4/4] Running Voltus (compressed VCD, method=$METHOD) ..."
# PAUSE: compressed VCD must be generated locally first and placed at:
#   $CIRCUIT_DIR/vcd/DMA_compressed_${METHOD}.vcd
VCD_COMPRESSED="$CIRCUIT_DIR/vcd/DMA_slow_compressed_${METHOD}.vcd"
if [ ! -f "$VCD_COMPRESSED" ]; then
    echo "  WARNING: $VCD_COMPRESSED not found."
    echo "  Please run local VCD compression first, then re-run:"
    echo "    bash $0 $METHOD"
    exit 1
fi

export METHOD="$METHOD"
innovus -nowin -init "$SCRIPT_DIR/innovus/voltus_compressed.tcl" \
        -log "$SCRIPT_DIR/voltus_compressed_${METHOD}.log" \
        2>&1 | tee "$SCRIPT_DIR/voltus_compressed_${METHOD}.stdout"
echo "      Voltus compressed ($METHOD) done."

echo "============================================"
echo "ALL STEPS COMPLETE for DMA_slow"
echo "============================================"
