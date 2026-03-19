#!/usr/bin/env python3
"""
JSONL Toggle Marker
Reads a combined JSONL file and outputs a new JSONL with per-bit XOR toggle marks.
For multi-bit signals (e.g. 110 -> 011), the output is the bitwise XOR result (101).
For scalar signals (0/1), the output is 0 or 1.
The first time point is always all zeros.

Usage:
    python jsonl_toggle_mark.py output/sim_output.jsonl
    python jsonl_toggle_mark.py output/sim_output.jsonl -o output/sim_output_toggles.jsonl
"""
import json
import sys
import argparse
from pathlib import Path


def _bitwise_xor(prev: str, curr: str) -> str:
    """
    Compute per-bit XOR between two VCD value strings.
    e.g. prev="110", curr="011" -> "101"
    Pads the shorter string with leading '0' to align widths.
    x/z bits are treated as '0' for XOR purposes.
    """
    # Normalize x/z to 0
    prev = prev.replace("x", "0").replace("z", "0").replace("X", "0").replace("Z", "0")
    curr = curr.replace("x", "0").replace("z", "0").replace("X", "0").replace("Z", "0")

    # Align widths by zero-padding
    width = max(len(prev), len(curr))
    prev = prev.zfill(width)
    curr = curr.zfill(width)

    return "".join("1" if p != c else "0" for p, c in zip(prev, curr))


def mark_toggles(input_path: str, output_path: str) -> Path:
    """
    Read a combined JSONL file, output a per-bit toggle-marked JSONL.
    For scalar signals: {"sig": "0"} or {"sig": "1"}
    For vector signals: {"sig": "101"} (bitwise XOR with previous value)
    First time point is always all zeros.
    """
    inp = Path(input_path)
    out = Path(output_path)

    prev_values = None
    line_count = 0

    with open(inp, "r", encoding="utf-8") as fin, \
         open(out, "w", encoding="utf-8") as fout:
        for line in fin:
            record = json.loads(line)
            signals = record["signals"]

            if prev_values is None:
                # First time point: all zeros, matching each signal's width
                toggled = {}
                for name, val in signals.items():
                    toggled[name] = "0" * max(len(val), 1)
            else:
                toggled = {}
                for name, val in signals.items():
                    prev = prev_values.get(name, "")
                    toggled[name] = _bitwise_xor(prev, val)

            fout.write(json.dumps(
                {"time": record["time"], "signals": toggled},
                ensure_ascii=False
            ) + "\n")

            prev_values = signals
            line_count += 1

    print(f"  OK  {out.name}  ({line_count} time points)")
    return out


def main():
    p = argparse.ArgumentParser(description="Mark signal toggles in JSONL")
    p.add_argument("input", help="Input combined JSONL file")
    p.add_argument("-o", "--output", default=None,
                   help="Output file (default: <input_stem>_toggles.jsonl)")
    args = p.parse_args()

    inp = Path(args.input).resolve()
    if not inp.exists():
        print(f"ERROR: File not found: {inp}")
        sys.exit(1)

    if args.output:
        out = Path(args.output).resolve()
    else:
        out = inp.parent / f"{inp.stem}_toggles.jsonl"

    print("=" * 60)
    print("JSONL Toggle Marker")
    print("=" * 60)
    print(f"Input : {inp}")
    print(f"Output: {out}")
    print()

    mark_toggles(str(inp), str(out))

    print()
    print(f"Done. Output: {out}")
    print("=" * 60)


if __name__ == "__main__":
    main()
