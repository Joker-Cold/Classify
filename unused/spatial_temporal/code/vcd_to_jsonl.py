#!/usr/bin/env python3
"""
VCD -> JSONL converter
Converts a VCD file into a single combined JSONL file where each line is a
JSON object representing one time point with all signal values (hold-last-value).

Usage:
    python vcd_to_jsonl.py data/sim_output.vcd
    python vcd_to_jsonl.py data/sim_output.vcd --output-dir output/
"""
import json
import sys
import argparse
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from parse_vcd_signal import VCDSignalParser


def vcd_to_jsonl(vcd_path: str, output_dir: str) -> Path:
    """
    Convert a VCD file to a single combined JSONL file.
    Each line: {"time": int, "signals": {"sig_name": "value", ...}}
    Returns the output file path.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    vcd = VCDSignalParser(vcd_path)
    vcd.parse_header()

    unique_sigs = vcd.list_unique_signals(exclude_params=True, exclude_tasks=True)
    sig_names = [s["name"] for s in unique_sigs]

    print(f"  Parsing VCD ({len(sig_names)} signals)...")
    all_waveforms = vcd.parse_all_waveforms(exclude_params=True, exclude_tasks=True)

    # Build {time -> {signal -> value}} from sparse waveforms
    changes_at: dict = defaultdict(dict)
    for sig, wf in all_waveforms.items():
        for t, v in wf:
            changes_at[t][sig] = v

    sorted_times = sorted(changes_at.keys())
    current_values = {sig: "" for sig in sig_names}

    vcd_name = Path(vcd_path).stem
    jsonl_path = out / f"{vcd_name}.jsonl"

    with open(jsonl_path, "w", encoding="utf-8") as f:
        for t in sorted_times:
            for sig, val in changes_at[t].items():
                if sig in current_values:
                    current_values[sig] = val
            record = {"time": t, "signals": dict(current_values)}
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"  OK  {jsonl_path.name}  ({len(sorted_times)} time points, {len(sig_names)} signals)")
    return jsonl_path


def main():
    p = argparse.ArgumentParser(description="Convert VCD to combined JSONL")
    p.add_argument("vcd_file", help="Input VCD file path")
    p.add_argument("--output-dir", default=None,
                   help="Output directory (default: <vcd_dir>/../output/)")
    args = p.parse_args()

    vcd_file = Path(args.vcd_file).resolve()
    if not vcd_file.exists():
        print(f"ERROR: VCD file not found: {vcd_file}")
        sys.exit(1)

    output_dir = Path(args.output_dir).resolve() if args.output_dir else \
                 vcd_file.parent.parent / "output"

    print("=" * 60)
    print("VCD -> JSONL")
    print("=" * 60)
    print(f"Input : {vcd_file}")
    print(f"Output: {output_dir}")
    print()

    jsonl_path = vcd_to_jsonl(str(vcd_file), str(output_dir))

    print()
    print(f"Done. Output: {jsonl_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
