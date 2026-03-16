#!/usr/bin/env python3
"""
Task 2: Count signal toggles per clock-cycle window.
Reads signal_manifest.json + individual CSVs produced by Task 1.
Generates toggle_counts_<N>cycles.csv for each requested window size.
"""
import sys
import csv
import json
from pathlib import Path
from typing import Dict, List, Tuple


def load_manifest(output_dir: Path) -> dict:
    path = output_dir / "signal_manifest.json"
    if not path.exists():
        raise FileNotFoundError(f"signal_manifest.json not found in {output_dir}. Run Task 1 first.")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def read_csv_waveform(csv_path: Path) -> List[Tuple[int, str]]:
    wf = []
    with open(csv_path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            wf.append((int(row["time"]), row["value"]))
    return wf


def extract_rising_edges(clk_wf: List[Tuple[int, str]]) -> List[int]:
    """Return sorted list of timestamps of every clock rising edge (0->1)."""
    edges = []
    prev = None
    for t, v in clk_wf:
        if v in ("0", "1"):
            if prev == "0" and v == "1":
                edges.append(t)
            prev = v
    return edges


def count_toggles_in_window(wf: List[Tuple[int, str]],
                             t_start: int, t_end: int,
                             prev_val: str) -> Tuple[int, str]:
    """
    Count value changes in [t_start, t_end] for one signal.
    Returns (toggle_count, last_value_seen).
    prev_val: the signal value just before t_start.
    """
    count = 0
    cur = prev_val
    for t, v in wf:
        if t < t_start:
            continue
        if t > t_end:
            break
        if cur is not None and v != cur:
            count += 1
        cur = v
    return count, cur if cur is not None else prev_val


def value_before(wf: List[Tuple[int, str]], t_start: int) -> str:
    """Return the last known value strictly before t_start."""
    last = None
    for t, v in wf:
        if t >= t_start:
            break
        last = v
    return last


def count_toggles_all_windows(
    signal_wfs: Dict[str, List[Tuple[int, str]]],
    clk_signal: str,
    window_cycles: int,
    output_path: Path,
) -> dict:
    """
    Compute toggle counts for every sliding window of `window_cycles` clock periods.
    Windows are anchored at consecutive rising edges (non-overlapping start).
    Writes results to output_path CSV and returns statistics.
    """
    clk_wf = signal_wfs[clk_signal]
    edges = extract_rising_edges(clk_wf)
    print(f"    {len(edges)} rising edges found")

    if len(edges) < window_cycles + 1:
        print(f"    Not enough clock edges for window size {window_cycles}")
        return {}

    # Exclude all clock-related signals (any signal whose base name is 'clk')
    data_signals = []
    for s in signal_wfs:
        base = s.split(".")[-1] if "." in s else s
        if base == "clk":
            continue
        data_signals.append(s)

    results = []
    max_toggles = 0

    for i in range(len(edges) - window_cycles):
        t_start = edges[i]
        t_end = edges[i + window_cycles] - 1  # one tick before next window

        total = 0
        for sig in data_signals:
            wf = signal_wfs[sig]
            prev = value_before(wf, t_start)
            n, _ = count_toggles_in_window(wf, t_start, t_end, prev)
            total += n

        results.append({
            "window_index": i + 1,
            "window_start_time": t_start,
            "window_end_time": t_end,
            "toggle_count": total,
        })
        if total > max_toggles:
            max_toggles = total

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["window_index", "window_start_time",
                                               "window_end_time", "toggle_count"])
        writer.writeheader()
        writer.writerows(results)

    max_win = next((r for r in results if r["toggle_count"] == max_toggles), None)
    return {
        "total_windows": len(results),
        "window_cycles": window_cycles,
        "max_toggles": max_toggles,
        "max_window": max_win["window_index"] if max_win else None,
        "data_signals": data_signals,
    }


def run(output_dir: Path, window_sizes: List[int]) -> None:
    manifest = load_manifest(output_dir)

    # ── Preload all waveforms ONCE ────────────────────────────────────
    print("  Loading waveforms...")
    signal_wfs: Dict[str, List[Tuple[int, str]]] = {}

    for sig_info in manifest["signals"]:
        name = sig_info["name"]
        csv_path = output_dir / sig_info["csv_file"]
        signal_wfs[name] = read_csv_waveform(csv_path)
        print(f"    Loaded {name:40s}  ({len(signal_wfs[name])} transitions)")

    # ── Robust clock detection ─────────────────────────────────────────
    clk_signal = _find_clock_signal(signal_wfs, manifest)
    print(f"    Clock signal: {clk_signal}")

    # ── Count toggles for each window size ───────────────────────────
    all_stats = {}
    for ws in window_sizes:
        print(f"\n  Window = {ws} clock cycles")
        out_csv = output_dir / f"toggle_counts_{ws}cycles.csv"
        stats = count_toggles_all_windows(signal_wfs, clk_signal, ws, out_csv)
        all_stats[ws] = stats
        if stats:
            print(f"    Windows  : {stats['total_windows']}")
            print(f"    Max toggles: {stats['max_toggles']}  (window #{stats['max_window']})")
            print(f"    Output   : {out_csv.name}")

    return all_stats


def _find_clock_signal(signal_wfs: Dict[str, List[Tuple[int, str]]],
                       manifest: dict) -> str:
    """Find the best clock signal from the manifest.

    Priority: 1) exact name 'clk', 2) name ending with '.clk' or containing 'clk',
    3) among candidates, prefer width==1 with most toggles.
    """
    sig_meta = {s["name"]: s for s in manifest["signals"]}
    candidates = []
    for name in signal_wfs:
        base = name.split(".")[-1] if "." in name else name
        if base == "clk":
            w = sig_meta.get(name, {}).get("width", 1)
            if w == 1:
                candidates.append(name)

    if not candidates:
        # Fallback: any signal with 'clk' in name and width==1
        for name in signal_wfs:
            if "clk" in name.lower():
                w = sig_meta.get(name, {}).get("width", 1)
                if w == 1:
                    candidates.append(name)

    if not candidates:
        raise ValueError("No clock signal found in manifest. "
                         "Need a 1-bit signal named 'clk'.")

    # If exact 'clk' (no scope prefix) exists, prefer it
    for c in candidates:
        if c == "clk":
            return c

    # Otherwise pick the one with most transitions (most likely the real clock)
    best = max(candidates, key=lambda c: len(signal_wfs[c]))
    return best


def main():
    output_dir = Path(__file__).parent.parent / "output"
    window_sizes = [5, 10]

    print("=" * 60)
    print("Task 2: Count toggles per clock-cycle window")
    print("=" * 60)

    run(output_dir, window_sizes)

    print()
    print("=" * 60)
    print("Task 2 complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
