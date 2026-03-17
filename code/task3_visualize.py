#!/usr/bin/env python3
"""
Task 3: 3D Signal Visualization
Reads all_signals_combined.csv and generates interactive 3D waveform plots
grouped by signal module, output as HTML files using plotly.
"""
import csv
import re
import sys
from pathlib import Path

import plotly.graph_objects as go

# ── Signal grouping rules ──────────────────────────────────────────────
# Each entry: (group_name, list of prefix patterns)
# A signal matches the first group whose pattern it hits; unmatched → "misc"
GROUP_RULES = [
    ("gpio",    [r"^gpio_"]),
    ("spi",     [r"^spi_", r"^cs_n", r"^sclk"]),
    ("uart",    [r"^uart_", r"^rx_", r"^tx_"]),
    ("irq",     [r"^irq_"]),
    ("sram",    [r"^sram_"]),
    ("ahb_bus", [r"^haddr", r"^htrans", r"^hwdata", r"^hwrite",
                 r"^hsize", r"^hrdata", r"^hready", r"^hresp"]),
    ("pwr",     [r"^pwr_", r"^slp_"]),
    ("ctrl",    [r"^u_soc_u_"]),
]


def _value_to_int(val: str) -> int:
    """Convert a VCD binary string to an integer. x/z treated as 0."""
    if not val:
        return 0
    cleaned = val.replace("x", "0").replace("z", "0").replace("X", "0").replace("Z", "0")
    try:
        return int(cleaned, 2)
    except ValueError:
        try:
            return int(cleaned)
        except ValueError:
            return 0


def _classify_signal(name: str) -> str:
    """Return the group name for a signal based on GROUP_RULES."""
    lower = name.lower()
    for group_name, patterns in GROUP_RULES:
        for pat in patterns:
            if re.match(pat, lower):
                return group_name
    return "misc"


def _load_combined_csv(csv_path: Path):
    """Load all_signals_combined.csv → (times[], signal_names[], values[][])"""
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        signal_names = header[1:]  # skip "time"

        times = []
        rows = []
        for row in reader:
            times.append(int(row[0]))
            rows.append(row[1:])

    return times, signal_names, rows


def _build_group_data(signal_names, times, rows):
    """Group signals and convert values to integers.
    Returns {group_name: (sig_names_in_group, z_matrix)} where
    z_matrix[sig_idx][time_idx] = integer value.
    """
    # Classify each signal
    groups = {}
    for idx, name in enumerate(signal_names):
        g = _classify_signal(name)
        groups.setdefault(g, []).append((idx, name))

    result = {}
    for g, members in groups.items():
        sig_names = [name for _, name in members]
        col_indices = [idx for idx, _ in members]
        z_matrix = []
        for ci in col_indices:
            z_row = [_value_to_int(rows[t][ci]) for t in range(len(times))]
            z_matrix.append(z_row)
        result[g] = (sig_names, z_matrix)

    return result


def _generate_3d_html(group_name, sig_names, times, z_matrix, output_path):
    """Generate an interactive 3D plot for one signal group."""
    fig = go.Figure()

    for i, (name, z_row) in enumerate(zip(sig_names, z_matrix)):
        fig.add_trace(go.Scatter3d(
            x=times,
            y=[i] * len(times),
            z=z_row,
            mode="lines",
            name=name,
            line=dict(width=3),
            hovertemplate=(
                f"<b>{name}</b><br>"
                "Time: %{x}<br>"
                "Value: %{z}<extra></extra>"
            ),
        ))

    fig.update_layout(
        title=f"3D Waveform — {group_name} ({len(sig_names)} signals)",
        scene=dict(
            xaxis_title="Time",
            yaxis=dict(
                title="Signal",
                tickvals=list(range(len(sig_names))),
                ticktext=sig_names,
            ),
            zaxis_title="Value",
        ),
        width=1200,
        height=800,
        margin=dict(l=0, r=0, t=40, b=0),
    )

    fig.write_html(str(output_path), include_plotlyjs="cdn")
    print(f"  OK  {group_name:12s} -> {output_path.name}  ({len(sig_names)} signals)")


def run(output_dir, combined_csv_name="all_signals_combined.csv"):
    """Main entry point for Task 3."""
    out = Path(output_dir)
    csv_path = out / combined_csv_name
    if not csv_path.exists():
        print(f"  ERROR: {csv_path} not found. Run Task 1 first.")
        return

    print(f"  Reading {csv_path.name}...")
    times, signal_names, rows = _load_combined_csv(csv_path)
    print(f"  {len(signal_names)} signals, {len(times)} time points")

    group_data = _build_group_data(signal_names, times, rows)

    generated = []
    for g in sorted(group_data.keys()):
        sig_names, z_matrix = group_data[g]
        out_html = out / f"waveform_3d_{g}.html"
        _generate_3d_html(g, sig_names, times, z_matrix, out_html)
        generated.append(out_html.name)

    print(f"  Generated {len(generated)} 3D plots")
    return generated


def main():
    output_dir = Path(__file__).parent.parent / "output"
    print("=" * 60)
    print("Task 3: 3D Signal Visualization")
    print("=" * 60)
    print(f"Output: {output_dir}")
    print()
    run(str(output_dir))
    print()
    print("=" * 60)
    print("Task 3 complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
