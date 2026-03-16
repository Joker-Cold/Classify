#!/usr/bin/env python3
"""
Task 4: Extract worst-case windows -> CSV3.
Reads toggle_counts_<N>cycles.csv, applies the 70% threshold from
skills/worst_case_identification.md, then writes a time-aligned CSV
containing only data from the worst-case windows.
"""
import sys
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple


def load_manifest(output_dir: Path) -> dict:
    path = output_dir / "signal_manifest.json"
    if not path.exists():
        raise FileNotFoundError(f"signal_manifest.json not found. Run Task 1 first.")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def read_toggle_counts(csv_path: Path) -> List[dict]:
    rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append({
                "window_index": int(row["window_index"]),
                "window_start_time": int(row["window_start_time"]),
                "window_end_time": int(row["window_end_time"]),
                "toggle_count": int(row["toggle_count"]),
            })
    return rows


def identify_worst_windows(windows: List[dict], threshold_pct: float = 0.7) -> Tuple[List[dict], dict]:
    """
    Return (worst_windows, stats).
    worst_windows are those with toggle_count >= max * threshold_pct,
    sorted descending by toggle_count.
    """
    if not windows:
        return [], {}
    max_t = max(w["toggle_count"] for w in windows)
    threshold = max_t * threshold_pct
    worst = [w for w in windows if w["toggle_count"] >= threshold]
    worst.sort(key=lambda w: w["toggle_count"], reverse=True)
    return worst, {
        "total_windows": len(windows),
        "max_toggles": max_t,
        "threshold": threshold,
        "threshold_pct": int(threshold_pct * 100),
        "worst_count": len(worst),
    }


def read_csv_waveform(csv_path: Path) -> List[Tuple[int, str]]:
    wf = []
    with open(csv_path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            wf.append((int(row["time"]), row["value"]))
    return wf


def value_at_or_before(wf: List[Tuple[int, str]], t: int) -> str:
    """Return the last known value at or before time t."""
    last = None
    for wt, wv in wf:
        if wt > t:
            break
        last = wv
    return last if last is not None else ""


def generate_worst_case_csv(
    signal_wfs: Dict[str, List[Tuple[int, str]]],
    signals: List[str],
    worst_windows: List[dict],
    output_path: Path,
) -> int:
    """
    Write CSV3: one row per time point that falls inside any worst-case window.
    Each row contains all signal values (hold-last-value semantics).
    Returns number of rows written.
    """
    # Build merged set of time points inside worst windows
    # Build change-map: {time: {signal: value}}
    changes_at: Dict[int, Dict[str, str]] = defaultdict(dict)
    worst_intervals = [(w["window_start_time"], w["window_end_time"]) for w in worst_windows]

    def in_worst(t: int) -> bool:
        return any(s <= t <= e for s, e in worst_intervals)

    for sig in signals:
        for t, v in signal_wfs.get(sig, []):
            if in_worst(t):
                changes_at[t][sig] = v

    # Also add window boundary times so each window has at least one row
    for s, e in worst_intervals:
        changes_at.setdefault(s, {})
        changes_at.setdefault(e, {})

    sorted_times = sorted(changes_at.keys())
    if not sorted_times:
        return 0

    # Get initial value for every signal just before first time point
    first_t = sorted_times[0]
    current_values = {sig: value_at_or_before(signal_wfs.get(sig, []), first_t)
                      for sig in signals}

    rows = 0
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["time"] + signals)
        for t in sorted_times:
            if not in_worst(t):
                continue
            # Apply changes at this time
            for sig, val in changes_at[t].items():
                current_values[sig] = val
            writer.writerow([t] + [current_values[sig] for sig in signals])
            rows += 1

    return rows


def run(output_dir: Path, window_sizes: List[int], threshold_pct: float = 0.7) -> None:
    manifest = load_manifest(output_dir)

    # Preload all waveforms
    print("  Loading waveforms...")
    signal_wfs: Dict[str, List[Tuple[int, str]]] = {}
    signals = [s["name"] for s in manifest["signals"]]
    for sig_info in manifest["signals"]:
        name = sig_info["name"]
        csv_path = output_dir / sig_info["csv_file"]
        signal_wfs[name] = read_csv_waveform(csv_path)

    for ws in window_sizes:
        toggle_csv = output_dir / f"toggle_counts_{ws}cycles.csv"
        if not toggle_csv.exists():
            print(f"  SKIP  {toggle_csv.name} not found (run Task 2 first)")
            continue

        print(f"\n  Window = {ws} clock cycles  (threshold={int(threshold_pct*100)}%)")
        windows = read_toggle_counts(toggle_csv)
        worst, stats = identify_worst_windows(windows, threshold_pct)

        print(f"    Total windows   : {stats['total_windows']}")
        print(f"    Max toggles     : {stats['max_toggles']}")
        print(f"    Threshold       : {stats['threshold_pct']}% = {stats['threshold']:.1f}")
        print(f"    Worst windows   : {stats['worst_count']}")

        out_csv = output_dir / f"worst_case_{ws}cycles.csv"
        rows = generate_worst_case_csv(signal_wfs, signals, worst, out_csv)
        print(f"    Output rows     : {rows}")
        print(f"    Output file     : {out_csv.name}")


def main():
    output_dir = Path(__file__).parent.parent / "output"
    window_sizes = [5, 10]

    print("=" * 60)
    print("Task 4: Extract worst-case windows -> CSV3")
    print("=" * 60)

    run(output_dir, window_sizes)

    print()
    print("=" * 60)
    print("Task 4 complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
