#!/usr/bin/env python3
"""
Toggle JSONL -> Interactive HTML Heatmap
Visualizes per-bit toggle activity as a heatmap:
  X = time, Y = signal, color = toggled bit count / total bits (toggle rate).

Usage:
    python toggles_to_html.py output/sim_output_toggles.jsonl
    python toggles_to_html.py output/sim_output_toggles.jsonl -o output/custom.html
"""
import json
import sys
import argparse
from pathlib import Path

import plotly.graph_objects as go
from plotly.subplots import make_subplots


def _toggle_rate(val: str) -> float:
    """Fraction of bits that toggled. '101' -> 2/3 ≈ 0.667, '0' -> 0.0"""
    if not val:
        return 0.0
    total = len(val)
    ones = val.count("1")
    return ones / total


def _toggle_count(val: str) -> int:
    """Number of bits that toggled."""
    return val.count("1") if val else 0


def load_toggles(jsonl_path: str):
    """Load toggles JSONL -> (times[], sig_names[], rate_matrix[][], count_matrix[][])
    rate_matrix[sig_idx][time_idx] = toggle rate (0.0~1.0)
    count_matrix[sig_idx][time_idx] = toggled bit count
    """
    records = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            records.append(json.loads(line))

    times = [r["time"] for r in records]
    sig_names = list(records[0]["signals"].keys())

    rate_matrix = []
    count_matrix = []
    for name in sig_names:
        rates = [_toggle_rate(r["signals"][name]) for r in records]
        counts = [_toggle_count(r["signals"][name]) for r in records]
        rate_matrix.append(rates)
        count_matrix.append(counts)

    return times, sig_names, rate_matrix, count_matrix


def _build_hover_text(sig_names, times, records):
    """Build custom hover text showing actual toggle bit-string."""
    text = []
    for name in sig_names:
        row = []
        for i, t in enumerate(times):
            val = records[i]["signals"][name]
            bits = len(val)
            ones = val.count("1")
            row.append(f"<b>{name}</b><br>Time: {t}<br>Toggle: {val}<br>{ones}/{bits} bits")
        text.append(row)
    return text


def generate_html(jsonl_path: str, output_path: str):
    """Generate an interactive heatmap HTML from toggles JSONL."""
    inp = Path(jsonl_path)

    # Load raw records for hover text
    with open(inp, "r", encoding="utf-8") as f:
        records = [json.loads(l) for l in f]

    times, sig_names, rate_matrix, count_matrix = load_toggles(jsonl_path)
    hover_text = _build_hover_text(sig_names, times, records)

    # ── Main heatmap: toggle rate per signal per time ──────────────
    fig = make_subplots(
        rows=2, cols=1,
        row_heights=[0.82, 0.18],
        shared_xaxes=True,
        vertical_spacing=0.06,
        subplot_titles=["Per-Signal Toggle Rate (bit-level)", "Total Toggle Count (all signals)"],
    )

    fig.add_trace(go.Heatmap(
        z=rate_matrix,
        x=times,
        y=sig_names,
        text=hover_text,
        hoverinfo="text",
        colorscale="YlOrRd",
        zmin=0,
        zmax=1,
        colorbar=dict(title="Toggle<br>Rate", y=0.58, len=0.64),
    ), row=1, col=1)

    # ── Bottom bar chart: total toggled bits across all signals per time
    total_per_time = [
        sum(count_matrix[s][t] for s in range(len(sig_names)))
        for t in range(len(times))
    ]

    fig.add_trace(go.Bar(
        x=times,
        y=total_per_time,
        marker_color="firebrick",
        name="Total toggles",
        hovertemplate="Time: %{x}<br>Total toggled bits: %{y}<extra></extra>",
    ), row=2, col=1)

    fig.update_layout(
        title=f"Signal Toggle Heatmap — {inp.stem} ({len(sig_names)} signals, {len(times)} time points)",
        height=max(600, len(sig_names) * 8 + 200),
        width=1400,
        showlegend=False,
        xaxis2_title="Time",
        yaxis=dict(dtick=1, tickfont=dict(size=7)),
        yaxis2_title="Toggled Bits",
    )

    out = Path(output_path)
    fig.write_html(str(out), include_plotlyjs="cdn")
    print(f"  OK  {out.name}  ({len(sig_names)} signals × {len(times)} time points)")
    return out


def main():
    p = argparse.ArgumentParser(description="Visualize toggle JSONL as HTML heatmap")
    p.add_argument("input", help="Input toggles JSONL file")
    p.add_argument("-o", "--output", default=None,
                   help="Output HTML file (default: <input_stem>.html)")
    args = p.parse_args()

    inp = Path(args.input).resolve()
    if not inp.exists():
        print(f"ERROR: File not found: {inp}")
        sys.exit(1)

    if args.output:
        out = Path(args.output).resolve()
    else:
        out = inp.parent / f"{inp.stem}.html"

    print("=" * 60)
    print("Toggle JSONL -> HTML Heatmap")
    print("=" * 60)
    print(f"Input : {inp}")
    print(f"Output: {out}")
    print()

    generate_html(str(inp), str(out))

    print()
    print(f"Done. Output: {out}")
    print("=" * 60)


if __name__ == "__main__":
    main()
