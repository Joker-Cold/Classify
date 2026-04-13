#!/usr/bin/env python3
"""Toggle Heatmap Generator

Combines physical location data (signal_location_map.csv) with toggle counts
(test_toggles.jsonl) to produce an interactive Plotly 2D heatmap showing
spatial distribution of switching activity on the chip.

Usage:
    python code/toggle_heatmap.py \
        --location output/signal_location_map.csv \
        --toggles output/test_toggles.jsonl \
        --html output/toggle_heatmap.html \
        [--grid 50] [--log]
"""
import csv
import json
import argparse
import math
import os


def load_locations(csv_path: str) -> dict:
    """Load signal → (x_um, y_um) from CSV.  Returns {signal_name: (x, y)}."""
    loc = {}
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row["signal_name"]
            if row["x_um"] and row["y_um"]:
                loc[name] = (float(row["x_um"]), float(row["y_um"]))
    return loc


def count_toggles(jsonl_path: str) -> dict:
    """Sum total toggle bits per signal across all time steps.

    Each JSONL line: {"time": t, "signals": {"sig": "01010..."}}.
    Toggle count = number of '1' bits summed over all time steps.
    """
    totals = {}
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            for sig, val in rec["signals"].items():
                totals[sig] = totals.get(sig, 0) + val.count("1")
    return totals


def build_grid(locations: dict, toggles: dict, grid_n: int):
    """Aggregate toggle counts into a 2D grid.

    Returns (grid_2d, x_edges, y_edges, point_data).
    grid_2d[iy][ix] = total toggle count in that cell.
    point_data = list of (x, y, toggle_count) for scatter overlay.
    """
    # Collect mapped points
    points = []
    for sig, (x, y) in locations.items():
        tc = toggles.get(sig, 0)
        points.append((x, y, tc, sig))

    if not points:
        return [], [], [], []

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)

    # Small padding to avoid edge issues
    dx = (x_max - x_min) * 0.001 or 1.0
    dy = (y_max - y_min) * 0.001 or 1.0
    x_max += dx
    y_max += dy

    cell_w = (x_max - x_min) / grid_n
    cell_h = (y_max - y_min) / grid_n

    # Build grid
    grid = [[0] * grid_n for _ in range(grid_n)]
    for x, y, tc, _ in points:
        ix = min(int((x - x_min) / cell_w), grid_n - 1)
        iy = min(int((y - y_min) / cell_h), grid_n - 1)
        grid[iy][ix] += tc

    # Edge coordinates (cell centers for axis labels)
    x_edges = [round(x_min + (i + 0.5) * cell_w, 2) for i in range(grid_n)]
    y_edges = [round(y_min + (i + 0.5) * cell_h, 2) for i in range(grid_n)]

    return grid, x_edges, y_edges, points


def write_html(grid, x_edges, y_edges, points, html_path: str,
               use_log: bool, grid_n: int):
    """Generate interactive Plotly heatmap HTML."""
    # Stats
    total_signals = len(points)
    total_toggles = sum(p[2] for p in points)
    max_cell = max(max(row) for row in grid) if grid else 0

    # Apply log scale if requested
    if use_log:
        display_grid = []
        for row in grid:
            display_grid.append([math.log10(v + 1) for v in row])
        colorbar_title = "log₁₀(toggles + 1)"
    else:
        display_grid = grid
        colorbar_title = "Toggle Count"

    grid_json = json.dumps(display_grid)
    x_json = json.dumps(x_edges)
    y_json = json.dumps(y_edges)
    raw_grid_json = json.dumps(grid)

    # Top-10 hottest cells
    cells = []
    for iy in range(grid_n):
        for ix in range(grid_n):
            cells.append((grid[iy][ix], x_edges[ix], y_edges[iy]))
    cells.sort(key=lambda c: -c[0])
    top10 = cells[:10]
    top10_html = "".join(
        f"<tr><td>{i+1}</td><td>({c[1]:.1f}, {c[2]:.1f})</td><td>{c[0]:,}</td></tr>"
        for i, c in enumerate(top10)
    )

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Toggle Heatmap — Spatial Switching Activity</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', sans-serif; background: #1a1a2e; color: #eee; }}
        .header {{ padding: 16px 24px; background: #16213e; border-bottom: 2px solid #0f3460; }}
        .header h1 {{ font-size: 20px; font-weight: 600; }}
        .header .sub {{ font-size: 13px; color: #a0a0b0; margin-top: 4px; }}
        .container {{ display: flex; height: calc(100vh - 70px); }}
        #plot {{ flex: 1; }}
        .sidebar {{ width: 280px; background: #16213e; padding: 16px; overflow-y: auto;
                    border-left: 1px solid #0f3460; }}
        .sidebar h3 {{ font-size: 14px; margin-bottom: 8px; color: #e94560; }}
        .stat {{ margin-bottom: 12px; }}
        .stat .label {{ font-size: 11px; color: #888; text-transform: uppercase; }}
        .stat .value {{ font-size: 18px; font-weight: 700; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 12px; margin-top: 6px; }}
        th, td {{ padding: 4px 6px; text-align: left; border-bottom: 1px solid #333; }}
        th {{ color: #e94560; }}
        .controls {{ margin-top: 16px; }}
        .controls label {{ font-size: 12px; color: #aaa; }}
        .controls select, .controls input {{ margin-top: 4px; width: 100%;
            padding: 4px; background: #0f3460; color: #eee; border: 1px solid #555; }}
    </style>
</head>
<body>
<div class="header">
    <h1>Toggle Heatmap — Chip Spatial Switching Activity</h1>
    <div class="sub">Grid: {grid_n}×{grid_n} | Signals: {total_signals:,} | Total toggles: {total_toggles:,}</div>
</div>
<div class="container">
    <div id="plot"></div>
    <div class="sidebar">
        <div class="stat">
            <div class="label">Total Signals (mapped)</div>
            <div class="value">{total_signals:,}</div>
        </div>
        <div class="stat">
            <div class="label">Total Toggles</div>
            <div class="value">{total_toggles:,}</div>
        </div>
        <div class="stat">
            <div class="label">Peak Cell Toggles</div>
            <div class="value">{max_cell:,}</div>
        </div>
        <h3>Top-10 Hottest Cells</h3>
        <table>
            <tr><th>#</th><th>Location (um)</th><th>Toggles</th></tr>
            {top10_html}
        </table>
    </div>
</div>
<script>
var zData = {grid_json};
var rawData = {raw_grid_json};
var xLabels = {x_json};
var yLabels = {y_json};

var heatmap = {{
    z: zData,
    x: xLabels,
    y: yLabels,
    type: "heatmap",
    colorscale: "Hot",
    reversescale: true,
    colorbar: {{
        title: "{colorbar_title}",
        titleside: "right",
        titlefont: {{ color: "#ccc" }},
        tickfont: {{ color: "#ccc" }}
    }},
    hovertemplate: "X: %{{x:.1f}} um<br>Y: %{{y:.1f}} um<br>Toggles: %{{customdata:,}}<extra></extra>",
    customdata: rawData
}};

var layout = {{
    paper_bgcolor: "#1a1a2e",
    plot_bgcolor: "#1a1a2e",
    xaxis: {{
        title: {{ text: "X (um)", font: {{ color: "#aaa" }} }},
        tickfont: {{ color: "#888" }},
        gridcolor: "#333",
        scaleanchor: "y"
    }},
    yaxis: {{
        title: {{ text: "Y (um)", font: {{ color: "#aaa" }} }},
        tickfont: {{ color: "#888" }},
        gridcolor: "#333"
    }},
    margin: {{ t: 10, l: 60, r: 10, b: 50 }}
}};

Plotly.newPlot("plot", [heatmap], layout, {{ responsive: true }});
</script>
</body>
</html>"""

    os.makedirs(os.path.dirname(os.path.abspath(html_path)), exist_ok=True)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"HTML written: {html_path}")


def main():
    p = argparse.ArgumentParser(
        description="Generate toggle heatmap from physical locations + toggle JSONL")
    p.add_argument("--location", required=True, help="signal_location_map.csv")
    p.add_argument("--toggles", required=True, help="test_toggles.jsonl")
    p.add_argument("--html", required=True, help="Output HTML path")
    p.add_argument("--grid", type=int, default=50,
                   help="Grid resolution N×N (default: 50)")
    p.add_argument("--log", action="store_true",
                   help="Use log10 color scale for better contrast")
    args = p.parse_args()

    print("Loading physical locations...")
    locations = load_locations(args.location)
    print(f"  {len(locations)} signals with coordinates")

    print("Counting toggles from JSONL...")
    toggles = count_toggles(args.toggles)
    print(f"  {len(toggles)} signals with toggle data")

    # Match stats
    matched = sum(1 for s in toggles if s in locations)
    print(f"  Matched (location + toggles): {matched}")

    print(f"Building {args.grid}×{args.grid} grid...")
    grid, x_edges, y_edges, points = build_grid(locations, toggles, args.grid)

    if not grid:
        print("ERROR: No data to plot")
        return

    total = sum(sum(row) for row in grid)
    max_cell = max(max(row) for row in grid)
    print(f"  Total toggles on grid: {total:,}")
    print(f"  Peak cell: {max_cell:,}")

    write_html(grid, x_edges, y_edges, points, args.html, args.log, args.grid)
    print("Done.")


if __name__ == "__main__":
    main()
