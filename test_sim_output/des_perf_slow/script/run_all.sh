#!/bin/bash
# =============================================================
# run_all.sh — Sequential P&R + Voltus for des_perf_slow
# Usage: bash run_all.sh [traditional|risk_propagation]
# =============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CIRCUIT_DIR="$(dirname "$SCRIPT_DIR")"
METHOD="${1:-traditional}"

source /etc/profile
export CDS_BASE=/data/Installed_tools/cadence
export INNOVUS201_HOME=$CDS_BASE/INNOVUS201
export CDS_LIC_FILE='20030@hzhb-Super-Server:5280@hzhb-Super-Server:5209@hzhb-Super-Server:5220@hzhb-Super-Server:5230@hzhb-Super-Server'
export PATH=$INNOVUS201_HOME/tools/bin:$PATH

echo "============================================"
echo "des_perf_slow P&R + Voltus pipeline"
echo "Method: $METHOD"
echo "============================================"

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

echo "[2/4] Running Innovus P&R ..."
innovus -nowin -init "$SCRIPT_DIR/pr_flow.tcl" \
        -log "$SCRIPT_DIR/pr_flow.log" 2>&1 | tee "$SCRIPT_DIR/pr_flow.stdout"
echo "      P&R complete."

echo "[3/4] Running Voltus (full VCD) ..."
innovus -nowin -init "$SCRIPT_DIR/voltus_full.tcl" \
        -log "$SCRIPT_DIR/voltus_full.log" 2>&1 | tee "$SCRIPT_DIR/voltus_full.stdout"
echo "      Voltus full done."

echo "[4/4] Running Voltus (compressed VCD, method=$METHOD) ..."
VCD_COMPRESSED="$CIRCUIT_DIR/vcd/des_perf_slow_compressed_${METHOD}.vcd"
if [ ! -f "$VCD_COMPRESSED" ]; then
    echo "  WARNING: $VCD_COMPRESSED not found."
    echo "  Please run local VCD compression first, then re-run: bash $0 $METHOD"
    exit 1
fi

export METHOD="$METHOD"
innovus -nowin -init "$SCRIPT_DIR/voltus_compressed.tcl" \
        -log "$SCRIPT_DIR/voltus_compressed_${METHOD}.log" \
        2>&1 | tee "$SCRIPT_DIR/voltus_compressed_${METHOD}.stdout"
echo "      Voltus compressed ($METHOD) done."

echo "ALL STEPS COMPLETE for des_perf_slow"
