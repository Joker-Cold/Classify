#!/usr/bin/env python3
"""
JSONL Per-Bit Diff
Computes per-bit signed difference between consecutive time points.
  0->1 = +1,  1->0 = -1,  same = 0
For multi-bit signals the result is a list of per-bit diffs.
First time point is always all zeros.

Usage:
    python jsonl_bit_diff.py output/sim_output.jsonl
    python jsonl_bit_diff.py output/sim_output.jsonl -o output/sim_output_diff.jsonl
"""
import json
import sys
import argparse
from pathlib import Path


def _normalize_bits(val: str, width: int) -> list:
    """Convert a VCD value string to a list of ints, zero-padded to width.
    x/z treated as 0."""
    cleaned = val.replace("x", "0").replace("z", "0").replace("X", "0").replace("Z", "0")
    try:
        bits = [int(c) for c in cleaned]
    except ValueError:
        bits = [0] * max(len(val), 1)
    # Zero-pad on the left to match width
    if len(bits) < width:
        bits = [0] * (width - len(bits)) + bits
    return bits


def _bitwise_diff(prev: str, curr: str) -> list:
    """Compute per-bit difference: curr_bit - prev_bit for each bit position.
    Returns list of ints: +1, -1, or 0."""
    width = max(len(prev), len(curr), 1)
    prev_bits = _normalize_bits(prev, width)
    curr_bits = _normalize_bits(curr, width)
    return [c - p for p, c in zip(prev_bits, curr_bits)]


def compute_diff(input_path: str, output_path: str) -> Path:
    """Read combined JSONL, output per-bit diff JSONL.
    Each signal value becomes a list of ints (+1/-1/0) per bit."""
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
                diff = {}
                for name, val in signals.items():
                    width = max(len(val), 1)
                    diff[name] = [0] * width
            else:
                diff = {}
                for name, val in signals.items():
                    prev = prev_values.get(name, "")
                    diff[name] = _bitwise_diff(prev, val)

            fout.write(json.dumps(
                {"time": record["time"], "signals": diff},
                ensure_ascii=False
            ) + "\n")

            prev_values = signals
            line_count += 1

    print(f"  OK  {out.name}  ({line_count} time points)")
    return out


def main():
    p = argparse.ArgumentParser(description="Compute per-bit diff on JSONL")
    p.add_argument("input", help="Input combined JSONL file")
    p.add_argument("-o", "--output", default=None,
                   help="Output file (default: <input_stem>_diff.jsonl)")
    args = p.parse_args()

    inp = Path(args.input).resolve()
    if not inp.exists():
        print(f"ERROR: File not found: {inp}")
        sys.exit(1)

    out = Path(args.output).resolve() if args.output else \
          inp.parent / f"{inp.stem}_diff.jsonl"

    print("=" * 60)
    print("JSONL Per-Bit Diff")
    print("=" * 60)
    print(f"Input : {inp}")
    print(f"Output: {out}")
    print()

    compute_diff(str(inp), str(out))

    print()
    print(f"Done. Output: {out}")
    print("=" * 60)


if __name__ == "__main__":
    main()
