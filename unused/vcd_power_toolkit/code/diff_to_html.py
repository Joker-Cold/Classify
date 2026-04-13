#!/usr/bin/env python3
"""
Diff JSONL -> Interactive HTML Heatmap
Visualizes per-bit signed diff (+1/-1/0) as a diverging heatmap:
  Blue = falling edges (bits going 1->0)
  White = no change
  Red  = rising edges (bits going 0->1)

Two views:
  1. Per-signal heatmap: net diff sum (rising - falling bits) per signal per time
  2. Bottom bar: total rising/falling edges across all signals per time

Usage:
    python diff_to_html.py output/sim_output_diff.jsonl
    python diff_to_html.py output/sim_output_diff.jsonl -o output/custom.html
"""
import json
import sys
import argparse
from pathlib import Path

import plotly.graph_objects as go
from plotly.subplots import make_subplots


def load_diff(jsonl_path: str):
    """Load diff JSONL -> (times[], sig_names[], records[])
    Each record's signals maps name -> list of ints (+1/-1/0).
    """
    records = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            records.append(json.loads(line))

    times = [r["time"] for r in records]
    sig_names = list(records[0]["signals"].keys())
    return times, sig_names, records


def generate_html(jsonl_path: str, output_path: str):
    """Generate interactive HTML from diff JSONL."""
    times, sig_names, records = load_diff(jsonl_path)
    n_sigs = len(sig_names)
    n_times = len(times)

    # Build matrices
    # net_diff[sig][time] = sum of per-bit diffs (positive = more rising, negative = more falling)
    # rise_count[sig][time] = count of +1 bits
    # fall_count[sig][time] = count of -1 bits
    net_diff = []
    rise_count = []
    fall_count = []
    hover_text = []

    for name in sig_names:
        nd_row, rc_row, fc_row, ht_row = [], [], [], []
        for i, r in enumerate(records):
            bits = r["signals"][name]
            rises = sum(1 for b in bits if b == 1)
            falls = sum(1 for b in bits if b == -1)
            net = rises - falls
            nd_row.append(net)
            rc_row.append(rises)
            fc_row.append(falls)
            width = len(bits)
            # Show compact bit-diff string: +/−/·
            diff_str = "".join("+" if b == 1 else ("-" if b == -1 else "·") for b in bits)
            if width > 32:
                diff_str = diff_str[:32] + "…"
            ht_row.append(
                f"<b>{name}</b> [{width}b]<br>"
                f"Time: {times[i]}<br>"
                f"Rising: {rises}  Falling: {falls}<br>"
                f"Diff: {diff_str}"
            )
        net_diff.append(nd_row)
        rise_count.append(rc_row)
        fall_count.append(fc_row)
        hover_text.append(ht_row)

    # Total rising/falling per time point
    total_rise = [sum(rise_count[s][t] for s in range(n_sigs)) for t in range(n_times)]
    total_fall = [sum(fall_count[s][t] for s in range(n_sigs)) for t in range(n_times)]

    # Find symmetric color range
    z_max = max(max(abs(v) for v in row) for row in net_diff) or 1

    fig = make_subplots(
        rows=2, cols=1,
        row_heights=[0.78, 0.22],
        shared_xaxes=True,
        vertical_spacing=0.06,
        subplot_titles=[
            "Per-Signal Net Bit Diff (red=rising, blue=falling)",
            "Total Rising / Falling Edges (all signals)",
        ],
    )

    # ── Heatmap ────────────────────────────────────────────────
    fig.add_trace(go.Heatmap(
        z=net_diff,
        x=times,
        y=sig_names,
        text=hover_text,
        hoverinfo="text",
        colorscale="RdBu_r",  # red=positive(rising), blue=negative(falling)
        zmid=0,
        zmin=-z_max,
        zmax=z_max,
        colorbar=dict(title="Net Diff", y=0.58, len=0.60),
    ), row=1, col=1)

    # ── Bottom: stacked rising/falling bars ────────────────────
    fig.add_trace(go.Bar(
        x=times, y=total_rise,
        name="Rising (+1)",
        marker_color="firebrick",
        hovertemplate="Time: %{x}<br>Rising bits: %{y}<extra></extra>",
    ), row=2, col=1)

    fig.add_trace(go.Bar(
        x=times, y=[-v for v in total_fall],
        name="Falling (-1)",
        marker_color="steelblue",
        hovertemplate="Time: %{x}<br>Falling bits: %{customdata}<extra></extra>",
        customdata=total_fall,
    ), row=2, col=1)

    fig.update_layout(
        title=f"Bit-Level Diff — {Path(jsonl_path).stem} ({n_sigs} signals, {n_times} time points)",
        height=max(700, n_sigs * 8 + 250),
        width=1400,
        barmode="relative",
        legend=dict(orientation="h", y=-0.05),
        xaxis2_title="Time",
        yaxis=dict(dtick=1, tickfont=dict(size=7)),
        yaxis2_title="Edges",
    )

    out = Path(output_path)
    fig.write_html(str(out), include_plotlyjs="cdn")
    print(f"  OK  {out.name}  ({n_sigs} signals × {n_times} time points)")
    return out


def main():
    p = argparse.ArgumentParser(description="Visualize bit-diff JSONL as HTML")
    p.add_argument("input", help="Input diff JSONL file")
    p.add_argument("-o", "--output", default=None,
                   help="Output HTML file (default: <input_stem>.html)")
    args = p.parse_args()

    inp = Path(args.input).resolve()
    if not inp.exists():
        print(f"ERROR: File not found: {inp}")
        sys.exit(1)

    out = Path(args.output).resolve() if args.output else \
          inp.parent / f"{inp.stem}.html"

    print("=" * 60)
    print("Diff JSONL -> HTML Heatmap")
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
