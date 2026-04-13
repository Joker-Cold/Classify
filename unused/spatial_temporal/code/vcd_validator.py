#!/usr/bin/env python3
"""
VCD Format Validator
Checks a VCD file for compliance with IEEE 1364 VCD dump format.
Usage: python vcd_validator.py <file.vcd> [--ref reference.vcd]
"""
import argparse
import re
from pathlib import Path


def validate_vcd(file_path: str) -> dict:
    """
    Validate VCD format. Returns {'issues': [...], 'symbols': set, 'n_times': int}.
    An empty 'issues' list means the file is valid.
    """
    issues = []
    defined_symbols: set = set()
    times = []
    current_time = None
    state = "header"   # header | dumpvars | values | dumpoff

    with open(file_path, "r", encoding="utf-8") as f:
        for lineno, raw in enumerate(f, 1):
            s = raw.strip()
            if not s:
                continue

            # ── Header ────────────────────────────────────────────────
            if state == "header":
                if s == "$enddefinitions $end":
                    state = "values"
                    continue
                if s.startswith("$var"):
                    parts = s.split()
                    # minimum: $var type width symbol name $end
                    if len(parts) < 6 or parts[-1] != "$end":
                        issues.append(f"Line {lineno}: malformed $var: {s!r}")
                    else:
                        sym = parts[3]
                        if sym in defined_symbols:
                            issues.append(f"Line {lineno}: duplicate symbol {sym!r}")
                        defined_symbols.add(sym)
                        try:
                            w = int(parts[2])
                            if w <= 0:
                                issues.append(f"Line {lineno}: width must be >0")
                        except ValueError:
                            issues.append(f"Line {lineno}: non-integer width in $var")
                continue

            # ── Value section ─────────────────────────────────────────
            if s == "$dumpvars":
                state = "dumpvars"
                continue
            if s == "$dumpoff":
                state = "dumpoff"
                continue
            if s == "$dumpon":
                state = "dumpvars"   # treat same as dumpvars
                continue
            if s == "$end":
                if state in ("dumpvars", "dumpoff"):
                    state = "values"
                continue

            if state in ("values", "dumpvars"):
                if s.startswith("#"):
                    try:
                        t = int(s[1:])
                        if times and t < times[-1]:
                            issues.append(f"Line {lineno}: non-monotonic time {t} < {times[-1]}")
                        times.append(t)
                        current_time = t
                    except ValueError:
                        issues.append(f"Line {lineno}: invalid time token {s!r}")
                    continue

                if s.startswith("$"):
                    continue  # skip $comment etc.

                # Value change
                _check_value_change(s, lineno, defined_symbols, issues)

    # Final checks
    if state == "header":
        issues.append("Missing $enddefinitions")

    return {"issues": issues, "symbols": defined_symbols, "n_times": len(times)}


def _check_value_change(s: str, lineno: int, defined_symbols: set, issues: list) -> None:
    """Validate one value-change line and append any issues."""
    # Vector: b<binary> <symbol>
    m = re.match(r"^b([01xzXZ]+)\s+(\S+)$", s)
    if m:
        sym = m.group(2)
        if sym not in defined_symbols:
            issues.append(f"Line {lineno}: undefined symbol {sym!r}")
        return
    # Scalar: <value><symbol>
    m = re.match(r"^([01xzXZ])(\S+)$", s)
    if m:
        sym = m.group(2)
        if sym not in defined_symbols:
            issues.append(f"Line {lineno}: undefined symbol {sym!r}")
        return
    # Unknown format
    issues.append(f"Line {lineno}: unrecognised value-change line: {s!r}")


def main():
    p = argparse.ArgumentParser(description="Validate VCD file format")
    p.add_argument("vcd_file", help="VCD file to validate")
    p.add_argument("--ref", help="Reference VCD (compare structure)")
    args = p.parse_args()

    print(f"Validating: {args.vcd_file}")
    result = validate_vcd(args.vcd_file)

    if result["issues"]:
        print(f"  FAIL  ({len(result['issues'])} issue(s) found)")
        for issue in result["issues"]:
            print("    " + issue)
    else:
        print(f"  PASS  ({result['n_times']} time points, {len(result['symbols'])} signals)")

    if args.ref:
        print(f"\nReference: {args.ref}")
        ref_result = validate_vcd(args.ref)
        if ref_result["issues"]:
            print("  Reference file has issues - skipping comparison")
        else:
            # Symbol count comparison
            ns = len(result["symbols"])
            nr = len(ref_result["symbols"])
            print(f"  Signals: test={ns}, ref={nr}  {'OK' if ns == nr else 'MISMATCH'}")
            nt = result["n_times"]
            ntr = ref_result["n_times"]
            print(f"  Time points: test={nt}, ref={ntr}")


if __name__ == "__main__":
    main()
