#!/usr/bin/env python3
"""
VCD Worst-Case Power Pipeline
==============================
Runs all 5 steps to compress a VCD file to its worst-case power windows.

Usage:
    python run_pipeline.py data/random_test.vcd
    python run_pipeline.py data/random_test.vcd --window-size 10 --threshold 0.8
    python run_pipeline.py data/random_test.vcd --output-dir results/ --validate

Pipeline:
    Step 1  VCD -> per-signal CSVs + signal_manifest.json
    Step 2  Count signal toggles per clock-cycle window
    Step 3  3D signal waveform visualization (interactive HTML)
    Step 4  Extract worst-case windows -> CSV3
    Step 5  CSV3 -> compressed VCD
"""
import argparse
import sys
from pathlib import Path

# Make sure code/ is on the path regardless of CWD
sys.path.insert(0, str(Path(__file__).parent))

from task1_vcd_to_csv import vcd_to_csvs
from task2_count_toggles import run as run_task2
from task4_extract_worst_case import run as run_task4
from task3_visualize import run as run_task3
from task5_csv_to_vcd import run as run_task5


def banner(title: str) -> None:
    print()
    print("=" * 60)
    print(title)
    print("=" * 60)


def main():
    p = argparse.ArgumentParser(
        description="Compress VCD to worst-case power windows"
    )
    p.add_argument("vcd_file", help="Input VCD file path")
    p.add_argument("--output-dir", default=None,
                   help="Output directory (default: <vcd_dir>/output/)")
    p.add_argument("--window-size", type=int, nargs="+", default=[5, 10],
                   help="Clock-cycle window size(s) (default: 5 10)")
    p.add_argument("--threshold", type=float, default=0.7,
                   help="Worst-case threshold 0.0-1.0 (default: 0.7 = 70%%)")
    p.add_argument("--validate", action="store_true",
                   help="Run VCD validator on output files")
    args = p.parse_args()

    vcd_file = Path(args.vcd_file).resolve()
    if not vcd_file.exists():
        print(f"ERROR: VCD file not found: {vcd_file}")
        sys.exit(1)

    output_dir = Path(args.output_dir).resolve() if args.output_dir else \
                 vcd_file.parent.parent / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    window_sizes = args.window_size
    threshold = args.threshold

    print(f"Input VCD   : {vcd_file}")
    print(f"Output dir  : {output_dir}")
    print(f"Window sizes: {window_sizes}")
    print(f"Threshold   : {int(threshold * 100)}%")

    # ── Step 1 ─────────────────────────────────────────────────────
    banner("Step 1: VCD -> CSV")
    vcd_to_csvs(str(vcd_file), str(output_dir))

    # ── Step 2 ─────────────────────────────────────────────────────
    banner("Step 2: Count toggles per clock-cycle window")
    run_task2(output_dir, window_sizes)

    # ── Step 3 ─────────────────────────────────────────────────────
    banner("Step 3: 3D Signal Visualization")
    run_task3(output_dir)

    # ── Step 4 ─────────────────────────────────────────────────────
    banner("Step 4: Extract worst-case windows")
    run_task4(output_dir, window_sizes, threshold)

    # ── Step 5 ─────────────────────────────────────────────────────
    banner("Step 5: CSV3 -> VCD")
    run_task5(output_dir, window_sizes)

    # ── Optional validation ────────────────────────────────────────
    if args.validate:
        banner("Validation")
        from vcd_validator import validate_vcd
        original_result = validate_vcd(str(vcd_file))
        print(f"Original VCD : {'PASS' if not original_result['issues'] else 'ISSUES'}")
        for ws in window_sizes:
            out_vcd = output_dir / f"worst_case_{ws}cycles.vcd"
            if out_vcd.exists():
                res = validate_vcd(str(out_vcd))
                status = "PASS" if not res["issues"] else f"FAIL ({len(res['issues'])} issues)"
                print(f"worst_case_{ws}cycles.vcd : {status}")
                if res["issues"]:
                    for iss in res["issues"]:
                        print("  " + iss)

    # ── Summary ────────────────────────────────────────────────────
    print()
    print("=" * 60)
    print("Pipeline complete. Output files:")
    for ws in window_sizes:
        out_vcd = output_dir / f"worst_case_{ws}cycles.vcd"
        if out_vcd.exists():
            size_kb = out_vcd.stat().st_size / 1024
            orig_kb = vcd_file.stat().st_size / 1024
            ratio = size_kb / orig_kb * 100 if orig_kb > 0 else 0
            print(f"  {out_vcd.name:<35}  {size_kb:6.1f} KB  ({ratio:.0f}% of original)")
    print("=" * 60)


if __name__ == "__main__":
    main()
