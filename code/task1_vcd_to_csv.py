#!/usr/bin/env python3
"""
Task 1: VCD -> CSV
Extracts every signal from a VCD file into individual CSVs and a combined CSV.
Also writes signal_manifest.json consumed by later pipeline steps.
"""
import sys
import csv
import json
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from parse_vcd_signal import VCDSignalParser


def vcd_to_csvs(vcd_path: str, output_dir: str) -> dict:
    """
    Main entry point for Task 1.
    Returns the manifest dict (also written to signal_manifest.json).
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    vcd = VCDSignalParser(vcd_path)
    vcd.parse_header()

    # Get unique signals (one per VCD symbol), filtering out parameters and task vars
    unique_sigs = vcd.list_unique_signals(exclude_params=True, exclude_tasks=True)
    sig_names = [s["name"] for s in unique_sigs]

    # ── One-pass load of all waveforms (with same filtering) ──────────
    print(f"  Parsing VCD (one pass, {len(sig_names)} signals)...")
    all_waveforms = vcd.parse_all_waveforms(exclude_params=True, exclude_tasks=True)

    # ── Per-signal CSVs ───────────────────────────────────────────────
    manifest_signals = []
    for sig_info in unique_sigs:
        sig = sig_info["name"]
        wf = all_waveforms.get(sig, [])
        safe = sig.replace("[", "_").replace("]", "_").replace(" ", "_") \
                  .replace(":", "_").replace(".", "_")
        csv_file = out / (safe + ".csv")
        with open(csv_file, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["time", "value"])
            writer.writerows(wf)
        print(f"  OK  {sig:40s} -> {csv_file.name}  ({len(wf)} transitions)")

        manifest_signals.append({
            "name": sig,
            "full_name": sig_info["full_name"],
            "type": sig_info["type"],
            "width": sig_info["width"],
            "symbol": sig_info["symbol"],
            "csv_file": csv_file.name,
        })

    # ── Combined CSV (all signals, hold-last-value, time-aligned) ─────
    combined_path = out / "all_signals_combined.csv"
    _write_combined_csv(sig_names, all_waveforms, combined_path)
    print(f"  OK  combined -> {combined_path.name}")

    # ── signal_manifest.json ──────────────────────────────────────────
    manifest = {
        "vcd_source": str(Path(vcd_path).resolve()),
        "timescale": vcd.timescale,
        "scope": vcd.top_scope,
        "signals": manifest_signals,
    }
    manifest_path = out / "signal_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"  OK  manifest -> {manifest_path.name}")

    return manifest


def _write_combined_csv(signals: list, waveforms: dict, output_path: Path) -> None:
    """
    Write time-aligned combined CSV.
    Each row represents a time point where at least one signal changed.
    All columns carry the current (hold-last-value) state of every signal.
    """
    # Build {time -> {signal -> value}} from sparse waveforms
    changes_at: dict = defaultdict(dict)
    for sig, wf in waveforms.items():
        for t, v in wf:
            changes_at[t][sig] = v

    sorted_times = sorted(changes_at.keys())
    current_values = {sig: "" for sig in signals}

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["time"] + signals)
        for t in sorted_times:
            # Update any signal that changed at this time
            for sig, val in changes_at[t].items():
                if sig in current_values:
                    current_values[sig] = val
            writer.writerow([t] + [current_values[sig] for sig in signals])


def main():
    vcd_file = Path(__file__).parent.parent / "data" / "random_test.vcd"
    output_dir = Path(__file__).parent.parent / "output"

    print("=" * 60)
    print("Task 1: VCD -> CSV")
    print("=" * 60)
    print(f"Input : {vcd_file}")
    print(f"Output: {output_dir}")
    print()

    manifest = vcd_to_csvs(str(vcd_file), str(output_dir))

    print()
    print("=" * 60)
    print("Task 1 complete.")
    print(f"  Signals  : {len(manifest['signals'])}")
    print(f"  Timescale: {manifest['timescale']}")
    print(f"  Scope    : {manifest['scope']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
