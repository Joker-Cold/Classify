#!/usr/bin/env python3
"""
Task 5: CSV3 -> VCD.
Reads worst_case_<N>cycles.csv and signal_manifest.json (for signal metadata),
then rebuilds a valid VCD file that can be used for chip verification.
"""
import sys
import csv
import json
from datetime import datetime
from itertools import product
from pathlib import Path
from typing import Dict, List, Tuple


# VCD printable symbol characters (0x21-0x7E, 94 chars, no space)
_SYMBOL_CHARS = [chr(i) for i in range(0x21, 0x7F)]


def _make_symbols(n: int) -> List[str]:
    """Generate n unique VCD symbols of minimum length."""
    symbols = []
    length = 1
    while len(symbols) < n:
        for combo in product(_SYMBOL_CHARS, repeat=length):
            symbols.append("".join(combo))
            if len(symbols) == n:
                return symbols
        length += 1
    return symbols


def load_manifest(output_dir: Path) -> dict:
    path = output_dir / "signal_manifest.json"
    if not path.exists():
        raise FileNotFoundError("signal_manifest.json not found. Run Task 1 first.")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def read_worst_case_csv(csv_path: Path) -> Tuple[List[str], List[dict]]:
    """Return (signal_names, rows) from a worst-case CSV."""
    signals = []
    rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        signals = [c for c in reader.fieldnames if c != "time"]
        for row in reader:
            r = {"time": int(row["time"])}
            for s in signals:
                r[s] = row.get(s, "")
            rows.append(r)
    return signals, rows


def _format_value(value: str, width: int) -> str:
    """Format a value for VCD output (scalar or vector prefix)."""
    if not value:
        return ""
    if width == 1:
        return value  # scalar: just the char
    return "b" + value  # vector: b<binary>


def csv_to_vcd(csv_path: Path, vcd_path: Path, manifest: dict) -> int:
    """
    Convert worst-case CSV to VCD.
    Signal metadata (type, width) comes from manifest.
    Returns number of data rows written.
    """
    # Build metadata lookup from manifest
    meta: Dict[str, dict] = {s["name"]: s for s in manifest["signals"]}
    timescale = manifest.get("timescale", "1 ns")
    scope = manifest.get("scope", "tb_top")

    signals, rows = read_worst_case_csv(csv_path)
    if not rows:
        print(f"    No data in {csv_path.name}, skipping")
        return 0

    # Assign fresh symbols (may differ from original VCD - that's OK)
    symbols = _make_symbols(len(signals))
    sym_map = dict(zip(signals, symbols))

    with open(vcd_path, "w", encoding="utf-8") as f:
        # ── Header ────────────────────────────────────────────────────
        f.write("$date\n")
        f.write("    " + datetime.now().strftime("%a %b %d %H:%M:%S %Y") + "\n")
        f.write("$end\n")
        f.write("$version\n")
        f.write("    VCD Worst-Case Extractor (task5_csv_to_vcd.py)\n")
        f.write("$end\n")
        f.write("$timescale\n")
        f.write("    " + timescale + "\n")
        f.write("$end\n\n")
        f.write("$scope module " + scope + " $end\n")
        for sig in signals:
            m = meta.get(sig, {})
            vtype = m.get("type", "reg")
            width = m.get("width", 1)
            sym = sym_map[sig]
            f.write(f"$var {vtype} {width} {sym} {sig} $end\n")
        f.write("$upscope $end\n\n")
        f.write("$enddefinitions $end\n\n")

        # ── $dumpvars: initial values from first row ──────────────────
        first_row = rows[0]
        f.write("#" + str(first_row["time"]) + "\n")
        f.write("$dumpvars\n")
        for sig in signals:
            val = first_row.get(sig, "")
            if not val:
                continue
            sym = sym_map[sig]
            width = meta.get(sig, {}).get("width", 1)
            fv = _format_value(val, width)
            if width == 1:
                f.write(fv + sym + "\n")
            else:
                f.write(fv + " " + sym + "\n")
        f.write("$end\n\n")

        # ── Value changes ─────────────────────────────────────────────
        prev_time = first_row["time"]
        prev_vals = {sig: first_row.get(sig, "") for sig in signals}

        for row in rows[1:]:
            t = row["time"]
            changed = [(sig, row[sig]) for sig in signals
                       if row[sig] and row[sig] != prev_vals[sig]]
            if not changed:
                continue
            if t != prev_time:
                f.write("#" + str(t) + "\n")
                prev_time = t
            for sig, val in changed:
                sym = sym_map[sig]
                width = meta.get(sig, {}).get("width", 1)
                fv = _format_value(val, width)
                if width == 1:
                    f.write(fv + sym + "\n")
                else:
                    f.write(fv + " " + sym + "\n")
                prev_vals[sig] = val

    return len(rows)


def run(output_dir: Path, window_sizes: List[int]) -> None:
    manifest = load_manifest(output_dir)

    for ws in window_sizes:
        csv_path = output_dir / f"worst_case_{ws}cycles.csv"
        vcd_path = output_dir / f"worst_case_{ws}cycles.vcd"
        if not csv_path.exists():
            print(f"  SKIP  {csv_path.name} not found (run Task 4 first)")
            continue
        print(f"\n  Converting {csv_path.name} ...")
        rows = csv_to_vcd(csv_path, vcd_path, manifest)
        print(f"    Rows written : {rows}")
        print(f"    Output VCD   : {vcd_path.name}")


def main():
    output_dir = Path(__file__).parent.parent / "output"
    window_sizes = [5, 10]

    print("=" * 60)
    print("Task 5: CSV3 -> VCD")
    print("=" * 60)

    run(output_dir, window_sizes)

    print()
    print("=" * 60)
    print("Task 5 complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
