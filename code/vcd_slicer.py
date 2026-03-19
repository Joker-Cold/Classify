#!/usr/bin/env python3
"""
VCD Time Window Slicer
Extracts a time window [start, end] from a VCD file and produces a new,
self-contained VCD with time stamps remapped to start from #0.

The output VCD:
  - Has the same header (date/version/timescale/scope/var) as the original
  - Contains a $dumpvars block at #0 with hold-last-value state at start_time
  - Includes only value changes within [start_time, end_time]
  - Remaps timestamps: new_time = original_time - start_time

Usage:
    python vcd_slicer.py input.vcd --start 210000 --end 328500 -o output.vcd
    python vcd_slicer.py input.vcd --start-ns 2100 --end-ns 3285 -o output.vcd
"""
import sys
import re
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from parse_vcd_signal import VCDSignalParser


def slice_vcd(vcd_path: str, start_tick: int, end_tick: int,
              output_path: str) -> None:
    """
    Extract a time window from a VCD file.

    Strategy:
    1. Copy the entire header verbatim (up to and including $enddefinitions $end)
    2. Compute hold-last-value for all signals at start_tick using parse_all_waveforms
       context, but do it efficiently by streaming.
    3. Write $dumpvars block at #0 with initial state
    4. Stream value changes in [start_tick, end_tick], remapping time
    """
    parser = VCDSignalParser(vcd_path)
    parser.parse_header()

    # Build symbol -> width map for formatting
    sym_width = {}
    for sym, info in parser.symbol_table.items():
        sym_width[sym] = info["width"]

    # ── Pass 1: Compute hold-last-value state BEFORE start_tick ──────
    # Collect signal values strictly BEFORE start_tick so that the
    # $dumpvars block represents the state one time-step before the
    # window.  This way value changes AT start_tick become real
    # transitions inside the sliced VCD (no edge-toggle loss).
    print(f"  Pass 1: Computing signal state before #{start_tick}...")
    last_values = {}  # symbol -> raw value-change line (ready to write)
    current_time = 0
    prev_time = 0  # tracks time point just before start_tick
    in_val = False
    in_dumpvars = False

    with open(vcd_path, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            if s.startswith("$enddefinitions"):
                in_val = True
                continue
            if not in_val:
                continue

            if s == "$dumpvars":
                in_dumpvars = True
                continue
            if s == "$end" and in_dumpvars:
                in_dumpvars = False
                continue

            if s.startswith("#"):
                try:
                    t = int(s[1:])
                    if t >= start_tick:
                        break
                    current_time = t
                    prev_time = t
                except ValueError:
                    pass
                continue
            if s.startswith("$"):
                continue

            # Parse value change and store by symbol
            parsed = _parse_vc_line(s)
            if parsed:
                sym, raw_line = parsed
                if sym in sym_width:
                    last_values[sym] = raw_line

    print(f"    {len(last_values)} signals have defined values "
          f"(state at #{prev_time}, before window)")

    # ── Pass 2: Write output VCD ─────────────────────────────────────
    print(f"  Pass 2: Writing sliced VCD...")
    n_changes = 0
    n_times = 0

    with open(vcd_path, "r", encoding="utf-8") as fin, \
         open(output_path, "w", encoding="utf-8") as fout:

        # Phase A: Copy header verbatim
        header_done = False
        for line in fin:
            fout.write(line)
            if line.strip().startswith("$enddefinitions"):
                header_done = True
                break

        if not header_done:
            print("ERROR: No $enddefinitions found in VCD")
            sys.exit(1)

        # Phase B: Write #0 + $dumpvars with initial state
        fout.write("\n")
        fout.write("#0\n")
        fout.write("$dumpvars\n")
        for sym in sorted(last_values.keys()):
            fout.write(last_values[sym] + "\n")
        # For signals not yet assigned, write x
        for sym, width in sym_width.items():
            if sym not in last_values:
                if width == 1:
                    fout.write(f"x{sym}\n")
                else:
                    fout.write(f"b{'x' * width} {sym}\n")
        fout.write("$end\n")

        # Phase C: Stream value changes in [start_tick, end_tick]
        # Time offset is based on prev_time (the time point whose state
        # is captured in $dumpvars), so start_tick maps to a positive
        # timestamp and its toggles appear as real transitions.
        time_offset = prev_time  # new_t = original_t - prev_time
        current_time = 0
        in_window = False

        for line in fin:
            s = line.strip()
            if not s:
                continue

            if s.startswith("#"):
                try:
                    t = int(s[1:])
                except ValueError:
                    continue
                current_time = t

                if t > end_tick:
                    break

                if t >= start_tick:
                    in_window = True
                    new_t = t - time_offset
                    fout.write(f"#{new_t}\n")
                    n_times += 1
                continue

            if s.startswith("$"):
                continue

            if in_window:
                fout.write(line)
                n_changes += 1

    new_end = end_tick - prev_time
    new_start = start_tick - prev_time
    print(f"    Time points written: {n_times} (+ #0 dumpvars)")
    print(f"    Value changes: {n_changes}")
    print(f"    Mapping: #{prev_time}(dumpvars)->{0}, "
          f"#{start_tick}->{new_start}, #{end_tick}->{new_end}")


def _parse_vc_line(s: str):
    """Parse a value-change line, return (symbol, raw_line) or None."""
    # Scalar: <val><symbol>
    m = re.match(r"^([01xzXZ])(.+)$", s)
    if m:
        return m.group(2), s
    # Vector: b<bits> <symbol>
    m = re.match(r"^b([01xzXZ]+)\s+(.+)$", s)
    if m:
        return m.group(2).strip(), s
    return None


def main():
    p = argparse.ArgumentParser(description="Slice a VCD file by time window")
    p.add_argument("vcd_file", help="Input VCD file")
    p.add_argument("--start", type=int, default=None,
                   help="Start time in VCD ticks")
    p.add_argument("--end", type=int, default=None,
                   help="End time in VCD ticks")
    p.add_argument("--start-ns", type=float, default=None,
                   help="Start time in nanoseconds")
    p.add_argument("--end-ns", type=float, default=None,
                   help="End time in nanoseconds")
    p.add_argument("--timescale-ps", type=float, default=10.0,
                   help="Timescale in picoseconds (default: 10)")
    p.add_argument("-o", "--output", required=True,
                   help="Output VCD file path")
    args = p.parse_args()

    # Resolve tick values
    if args.start is not None:
        start_tick = args.start
    elif args.start_ns is not None:
        start_tick = int(args.start_ns * 1000 / args.timescale_ps)
    else:
        print("ERROR: Specify --start or --start-ns")
        sys.exit(1)

    if args.end is not None:
        end_tick = args.end
    elif args.end_ns is not None:
        end_tick = int(args.end_ns * 1000 / args.timescale_ps)
    else:
        print("ERROR: Specify --end or --end-ns")
        sys.exit(1)

    vcd_file = Path(args.vcd_file).resolve()
    if not vcd_file.exists():
        print(f"ERROR: VCD file not found: {vcd_file}")
        sys.exit(1)

    output_file = Path(args.output).resolve()
    output_file.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("VCD Time Window Slicer")
    print("=" * 60)
    ps = args.timescale_ps
    print(f"Input : {vcd_file}")
    print(f"Output: {output_file}")
    print(f"Window: #{start_tick} ~ #{end_tick}  "
          f"({start_tick * ps / 1000:.1f}ns ~ {end_tick * ps / 1000:.1f}ns)")
    print()

    slice_vcd(str(vcd_file), start_tick, end_tick, str(output_file))

    # Report file sizes
    in_size = vcd_file.stat().st_size
    out_size = output_file.stat().st_size
    ratio = out_size / in_size * 100 if in_size > 0 else 0
    print()
    print(f"  Input size : {in_size:,} bytes")
    print(f"  Output size: {out_size:,} bytes ({ratio:.1f}%)")
    print()
    print("=" * 60)


if __name__ == "__main__":
    main()
