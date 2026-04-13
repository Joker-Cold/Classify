#!/usr/bin/env python3
"""
Spatial-Temporal Window Selection for VCD Compression

Combines physical location grid (mx×ny) with time windows (kt) to select
the highest-toggle windows per region, then splices selected intervals
into a compressed VCD with warmup periods.

Usage:
    python code/spatial_temporal_select.py \
        --location output/signal_location_map.csv \
        --toggles output/test_toggles.jsonl \
        --vcd des_demo/vcd/test.vcd \
        --mx 10 --ny 10 --kt 20 --top 2 \
        --warmup-cycles 10 --clock-ns 50 --timescale-ps 10 \
        --output output/selected_spatial.vcd \
        --html output/spatial_temporal_selection.html \
        --json-out output/spatial_temporal_selection.json
"""
import argparse
import csv
import json
import math
import os
import re
import sys
from pathlib import Path


# ── Data Loading ─────────────────────────────────────────────────────

def load_locations(csv_path: str) -> dict:
    """Load signal → (x_um, y_um) from CSV."""
    loc = {}
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row["signal_name"]
            if row["x_um"] and row["y_um"]:
                loc[name] = (float(row["x_um"]), float(row["y_um"]))
    return loc


# ── Spatial Grid ─────────────────────────────────────────────────────

def build_spatial_grid(locations: dict, mx: int, ny: int):
    """Assign each signal to a grid cell.

    Returns:
        signal_to_cell: {signal_name: (ix, iy)}
        bbox: (x_min, x_max, y_min, y_max, cell_w, cell_h)
    """
    xs = [v[0] for v in locations.values()]
    ys = [v[1] for v in locations.values()]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)

    # Small padding to avoid edge issues
    dx = (x_max - x_min) * 0.001 or 1.0
    dy = (y_max - y_min) * 0.001 or 1.0
    x_max += dx
    y_max += dy

    cell_w = (x_max - x_min) / mx
    cell_h = (y_max - y_min) / ny

    signal_to_cell = {}
    for name, (x, y) in locations.items():
        ix = min(int((x - x_min) / cell_w), mx - 1)
        iy = min(int((y - y_min) / cell_h), ny - 1)
        signal_to_cell[name] = (ix, iy)

    bbox = (x_min, x_max, y_min, y_max, cell_w, cell_h)
    return signal_to_cell, bbox


# ── 3D Toggle Matrix Construction ────────────────────────────────────

def build_toggle_matrix(jsonl_path: str, signal_to_cell: dict,
                        mx: int, ny: int, kt: int):
    """Stream JSONL once to build toggle_3d[iy][ix][j] and toggle_time[j].

    Returns:
        toggle_3d: 3D list [ny][mx][kt]
        toggle_time: 1D list [kt] — total toggles per time window
        t_max: maximum time tick seen
        n_lines: number of JSONL lines processed
        sig_toggles: {signal_name: total_toggle_count}
        sig_win_toggles: {signal_name: [toggle_per_window_j, ...]}
    """
    # First pass: find t_max for window boundaries
    t_max = 0
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            t = rec["time"]
            if t > t_max:
                t_max = t

    if t_max == 0:
        print("ERROR: No time data in JSONL", file=sys.stderr)
        sys.exit(1)

    win_size = t_max / kt  # ticks per window

    # Initialize matrices
    toggle_3d = [[[0] * kt for _ in range(mx)] for _ in range(ny)]
    toggle_time = [0] * kt
    sig_toggles = {}       # per-signal total toggle count
    sig_win_toggles = {}   # per-signal per-window toggle list

    # Second pass: accumulate toggles
    n_lines = 0
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            t = rec["time"]
            j = min(int(t / win_size), kt - 1)  # time window index
            n_lines += 1

            for sig, val in rec["signals"].items():
                tc = val.count("1")
                if tc == 0:
                    continue
                sig_toggles[sig] = sig_toggles.get(sig, 0) + tc
                if sig not in sig_win_toggles:
                    sig_win_toggles[sig] = [0] * kt
                sig_win_toggles[sig][j] += tc
                cell = signal_to_cell.get(sig)
                if cell is None:
                    continue
                ix, iy = cell
                toggle_3d[iy][ix][j] += tc
                toggle_time[j] += tc

    return toggle_3d, toggle_time, t_max, n_lines, sig_toggles, sig_win_toggles


# ── Per-Region Top-T Selection ───────────────────────────────────────

def select_per_region(toggle_3d, mx: int, ny: int, kt: int, top_t: int):
    """For each grid cell, pick top-T time windows by toggle count.

    Returns:
        selected_set: set of window indices
        region_picks: {(ix,iy): [list of (window_idx, toggle_count)]}
        win_region_count: [kt] — how many regions selected each window
    """
    selected_set = set()
    region_picks = {}
    win_region_count = [0] * kt

    for iy in range(ny):
        for ix in range(mx):
            row = toggle_3d[iy][ix]
            # Skip empty cells
            total = sum(row)
            if total == 0:
                continue

            # Sort window indices by toggle count descending
            ranked = sorted(range(kt), key=lambda j: row[j], reverse=True)
            picks = []
            for j in ranked[:top_t]:
                if row[j] > 0:
                    picks.append((j, row[j]))
                    selected_set.add(j)
                    win_region_count[j] += 1
            if picks:
                region_picks[(ix, iy)] = picks

    return selected_set, region_picks, win_region_count


# ── Cluster Filter ────────────────────────────────────────────────────

def cluster_filter(selected_set: set, kt: int, min_cluster: int):
    """Keep only windows that belong to clusters of >= min_cluster
    consecutive (or near-consecutive with gap<=1) selected windows.

    This eliminates isolated windows that would each need an expensive
    $dumpvars segment, achieving better VCD compression.

    Returns: filtered set of window indices.
    """
    if min_cluster <= 1:
        return selected_set

    sorted_wins = sorted(selected_set)
    if not sorted_wins:
        return selected_set

    # Group into clusters: windows within gap<=1 of each other
    clusters = []
    current = [sorted_wins[0]]
    for w in sorted_wins[1:]:
        if w - current[-1] <= 2:  # allow gap of 1 unselected window
            current.append(w)
        else:
            clusters.append(current)
            current = [w]
    clusters.append(current)

    # Keep only clusters with enough windows
    filtered = set()
    for cl in clusters:
        if len(cl) >= min_cluster:
            filtered.update(cl)

    return filtered


# ── Warmup + Merge ───────────────────────────────────────────────────

def expand_and_merge(selected_set: set, kt: int, t_max: int,
                     warmup_ticks: int):
    """Expand selected windows with warmup, merge overlapping intervals.

    Returns:
        merged: list of (start_tick, end_tick) tuples, sorted
    """
    win_size = t_max / kt
    intervals = []
    for j in sorted(selected_set):
        win_start = int(j * win_size)
        win_end = int((j + 1) * win_size)
        # Extend warmup before window start
        ext_start = max(0, win_start - warmup_ticks)
        intervals.append((ext_start, win_end))

    if not intervals:
        return []

    # Sort and merge overlapping/adjacent intervals
    intervals.sort()
    merged = [intervals[0]]
    for start, end in intervals[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))

    return merged


# ── Multi-Segment VCD Splice ─────────────────────────────────────────

def _parse_vc_line(s: str):
    """Parse a value-change line, return (symbol, raw_line) or None."""
    m = re.match(r"^([01xzXZ])(.+)$", s)
    if m:
        return m.group(2), s
    m = re.match(r"^b([01xzXZ]+)\s+(.+)$", s)
    if m:
        return m.group(2).strip(), s
    return None



def _find_interval(t: int, intervals: list, hint: int) -> int:
    """Find which interval contains time t, or -1 if none.
    Uses hint (last known index) for fast sequential scanning.
    """
    n = len(intervals)
    # Check hint first
    if 0 <= hint < n:
        s, e = intervals[hint]
        if s <= t < e:
            return hint
        # Check next interval
        if hint + 1 < n:
            s2, e2 = intervals[hint + 1]
            if s2 <= t < e2:
                return hint + 1

    # Linear scan (intervals are sorted, usually few)
    for i, (s, e) in enumerate(intervals):
        if s <= t < e:
            return i
        if s > t:
            break
    return -1


def splice_vcd_v2(vcd_path: str, merged_intervals: list,
                  output_path: str) -> dict:
    """Single-pass VCD splice: extract merged intervals with time remapping.

    Strategy: two passes over VCD body.
    Pass 1 (before first interval start): collect hold-last-value state only.
    Pass 2 (full stream): at each interval entry, write $dumpvars from state
    collected BEFORE that timestamp, then for the entry timestamp and all
    subsequent timestamps inside the interval, write value changes normally.

    Key: $dumpvars uses state from the tick BEFORE the interval start, so
    value changes AT the interval start appear as real transitions (no
    duplicate symbols).
    """
    if not merged_intervals:
        return {}

    # Parse header for symbol widths
    sym_width = {}
    header_lines = []
    with open(vcd_path, "r", encoding="utf-8") as f:
        for line in f:
            header_lines.append(line)
            s = line.strip()
            m = re.match(r"\$var\s+\S+\s+(\d+)\s+(\S+)\s+", s)
            if m:
                sym_width[m.group(2)] = int(m.group(1))
            if s.startswith("$enddefinitions"):
                break

    # Build time offset table (continuous output time)
    interval_offsets = []
    cumulative = 0
    for start, end in merged_intervals:
        interval_offsets.append(cumulative - start)
        cumulative += (end - start)

    stats = {"n_changes": 0, "n_times": 0, "n_segments": len(merged_intervals),
             "total_output_ticks": cumulative}

    # ── Pass 1: Collect hold-last-value state at each interval boundary ──
    # For each interval, we need the signal state just BEFORE start_tick.
    # We collect snapshots at each boundary by streaming once.
    boundary_states = {}  # interval_idx → {sym: raw_line}
    last_values = {}
    current_time = -1

    with open(vcd_path, "r", encoding="utf-8") as f:
        in_val = False
        in_dv = False
        next_boundary = 0  # index of next interval whose state we need

        for line in f:
            s = line.strip()
            if not s:
                continue
            if not in_val:
                if s.startswith("$enddefinitions"):
                    in_val = True
                continue
            if s == "$dumpvars":
                in_dv = True
                continue
            if s == "$end" and in_dv:
                in_dv = False
                continue
            if s.startswith("#"):
                try:
                    t = int(s[1:])
                except ValueError:
                    continue
                # Before updating current_time, check if we've reached
                # a boundary — snapshot state from BEFORE this timestamp
                while (next_boundary < len(merged_intervals) and
                       t >= merged_intervals[next_boundary][0]):
                    boundary_states[next_boundary] = dict(last_values)
                    next_boundary += 1
                current_time = t
                if next_boundary >= len(merged_intervals):
                    break
                continue
            if s.startswith("$"):
                continue
            parsed = _parse_vc_line(s)
            if parsed:
                sym, raw = parsed
                last_values[sym] = raw

        # Handle intervals that start at or after the last timestamp
        while next_boundary < len(merged_intervals):
            boundary_states[next_boundary] = dict(last_values)
            next_boundary += 1

    print(f"  Boundary states captured for {len(boundary_states)} intervals")

    # ── Pass 2: Write output VCD ──
    with open(vcd_path, "r", encoding="utf-8") as fin, \
         open(output_path, "w", encoding="utf-8") as fout:

        # Write header
        for hl in header_lines:
            fout.write(hl)
        fout.write("\n")

        in_val = False
        in_dumpvars = False
        active_idx = -1
        last_written_idx = -1

        def write_dumpvars(interval_idx: int, t: int):
            """Write segment $dumpvars using pre-captured state."""
            nonlocal last_written_idx
            seg_num = interval_idx + 1
            s_tick, e_tick = merged_intervals[interval_idx]
            fout.write(f"$comment segment {seg_num}: "
                       f"#{s_tick}~#{e_tick} $end\n")
            out_t = t + interval_offsets[interval_idx]
            fout.write(f"#{out_t}\n")
            fout.write("$dumpvars\n")
            state = boundary_states.get(interval_idx, {})
            for sym in sorted(state.keys()):
                fout.write(state[sym] + "\n")
            for sym, w in sym_width.items():
                if sym not in state:
                    if w == 1:
                        fout.write(f"x{sym}\n")
                    else:
                        fout.write(f"b{'x' * w} {sym}\n")
            fout.write("$end\n")
            last_written_idx = interval_idx
            stats["n_times"] += 1

        for line in fin:
            s = line.strip()
            if not s:
                continue

            if not in_val:
                if s.startswith("$enddefinitions"):
                    in_val = True
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
                except ValueError:
                    continue

                new_idx = _find_interval(t, merged_intervals, active_idx)

                if new_idx >= 0 and new_idx != last_written_idx:
                    # Entering a new interval — write $dumpvars
                    write_dumpvars(new_idx, t)
                    active_idx = new_idx
                    # The entry timestamp is already written by write_dumpvars
                elif new_idx >= 0:
                    # Continuing in same interval — write timestamp
                    active_idx = new_idx
                    out_t = t + interval_offsets[new_idx]
                    fout.write(f"#{out_t}\n")
                    stats["n_times"] += 1
                else:
                    active_idx = -1

                continue

            if s.startswith("$"):
                continue

            # Value change — write only if inside an active interval
            if active_idx >= 0:
                fout.write(line)
                stats["n_changes"] += 1

    return stats


# ── HTML Visualization ───────────────────────────────────────────────

def generate_html(toggle_time: list, toggle_3d: list,
                  mx: int, ny: int, kt: int,
                  selected_set: set, win_region_count: list,
                  merged_intervals: list, t_max: int,
                  warmup_ticks: int, bbox: tuple,
                  stats: dict, top_t: int,
                  locations: dict, sig_toggles: dict,
                  sig_win_toggles: dict,
                  html_path: str):
    """Generate interactive Plotly HTML with 4 panels:
    1. Timeline bar chart (top, full width)
    2. Signal location scatter plot (middle left)
    3. Grid heatmap — total toggles (middle right)
    4. Grid heatmap — selected windows only (bottom right)
    Plus sidebar with stats.
    """
    win_size = t_max / kt
    timescale_ns = 10 / 1000  # 10ps in ns

    # ── Timeline data ──
    times_ns = [round(j * win_size * timescale_ns, 2) for j in range(kt)]
    bar_colors = ["rgba(255,80,80,0.8)" if j in selected_set
                  else "rgba(100,149,237,0.6)" for j in range(kt)]

    # ── Grid heatmaps ──
    spatial_total = [[0] * mx for _ in range(ny)]
    spatial_selected = [[0] * mx for _ in range(ny)]
    for iy in range(ny):
        for ix in range(mx):
            spatial_total[iy][ix] = sum(toggle_3d[iy][ix])
            spatial_selected[iy][ix] = sum(
                toggle_3d[iy][ix][j] for j in range(kt) if j in selected_set)

    x_min, x_max, y_min, y_max, cell_w, cell_h = bbox
    x_labels = [round(x_min + (i + 0.5) * cell_w, 1) for i in range(mx)]
    y_labels = [round(y_min + (i + 0.5) * cell_h, 1) for i in range(ny)]

    spatial_total_log = [[round(math.log10(v + 1), 3) for v in row]
                         for row in spatial_total]
    spatial_sel_log = [[round(math.log10(v + 1), 3) for v in row]
                       for row in spatial_selected]

    # ── Location scatter data ──
    # Downsample: keep top 8000 signals by toggle count for performance
    MAX_SCATTER = 8000
    scatter_items = [(sig, locations[sig], sig_toggles.get(sig, 0))
                     for sig in locations if sig in sig_toggles]
    scatter_items.sort(key=lambda x: -x[2])
    if len(scatter_items) > MAX_SCATTER:
        scatter_items = scatter_items[:MAX_SCATTER]

    sc_x = [item[1][0] for item in scatter_items]
    sc_y = [item[1][1] for item in scatter_items]
    sc_tc = [item[2] for item in scatter_items]
    sc_log = [round(math.log10(v + 1), 3) for v in sc_tc]
    sc_names = [item[0][:30] for item in scatter_items]  # truncate for hover

    # Per-signal selected-window toggle count
    sc_sel_tc = []
    for sig, _, _ in scatter_items:
        wt = sig_win_toggles.get(sig)
        if wt:
            sc_sel_tc.append(sum(wt[j] for j in range(kt) if j in selected_set))
        else:
            sc_sel_tc.append(0)
    sc_sel_log = [round(math.log10(v + 1), 3) for v in sc_sel_tc]

    # ── Interval shapes for timeline ──
    interval_shapes = []
    for idx, (s, e) in enumerate(merged_intervals):
        s_ns = s * timescale_ns
        e_ns = e * timescale_ns
        interval_shapes.append(
            f'{{"type":"rect","xref":"x","yref":"paper",'
            f'"x0":{s_ns},"x1":{e_ns},'
            f'"y0":0,"y1":1,'
            f'"fillcolor":"rgba(255,215,0,0.15)",'
            f'"line":{{"color":"gold","width":2,"dash":"dash"}},'
            f'"layer":"below"}}'
        )

    # ── Grid lines on scatter to show cell boundaries ──
    grid_shapes_scatter = []
    for i in range(1, mx):
        gx = x_min + i * cell_w
        grid_shapes_scatter.append(
            f'{{"type":"line","xref":"x2","yref":"y2",'
            f'"x0":{gx},"x1":{gx},"y0":{y_min},"y1":{y_max},'
            f'"line":{{"color":"rgba(255,255,255,0.15)","width":1}}}}'
        )
    for i in range(1, ny):
        gy = y_min + i * cell_h
        grid_shapes_scatter.append(
            f'{{"type":"line","xref":"x2","yref":"y2",'
            f'"x0":{x_min},"x1":{x_max},"y0":{gy},"y1":{gy},'
            f'"line":{{"color":"rgba(255,255,255,0.15)","width":1}}}}'
        )

    # ── Stats ──
    total_toggles = sum(toggle_time)
    selected_toggles = sum(toggle_time[j] for j in selected_set)
    total_sim_ns = t_max * timescale_ns
    total_selected_ticks = sum(e - s for s, e in merged_intervals)
    compression = total_selected_ticks / t_max * 100 if t_max > 0 else 0
    n_active_regions = sum(1 for iy in range(ny) for ix in range(mx)
                           if spatial_total[iy][ix] > 0)
    n_scatter = len(scatter_items)

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Spatial-Temporal Window Selection</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:'Segoe UI',sans-serif; background:#1a1a2e; color:#eee; }}
.header {{ padding:12px 20px; background:#16213e; border-bottom:2px solid #0f3460; }}
.header h1 {{ font-size:18px; font-weight:600; }}
.header .sub {{ font-size:11px; color:#a0a0b0; margin-top:3px; }}
.layout {{ display:flex; height:calc(100vh - 56px); }}
.panels {{ flex:1; display:grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: 260px 1fr 1fr;
  gap: 2px; padding: 2px; }}
#timeline {{ grid-column: 1 / -1; }}
.sidebar {{ width:240px; background:#16213e; padding:12px; overflow-y:auto;
           border-left:1px solid #0f3460; font-size:12px; }}
.sidebar h3 {{ color:#e94560; margin:10px 0 5px; font-size:13px; }}
.stat {{ margin-bottom:6px; }}
.stat .label {{ font-size:10px; color:#888; text-transform:uppercase; }}
.stat .value {{ font-size:15px; font-weight:700; }}
table {{ width:100%; border-collapse:collapse; font-size:10px; margin-top:4px; }}
th,td {{ padding:2px 4px; text-align:left; border-bottom:1px solid #333; }}
th {{ color:#e94560; }}
.tab-bar {{ display:flex; gap:4px; margin-bottom:6px; }}
.tab-btn {{ padding:4px 10px; font-size:11px; cursor:pointer; border:1px solid #444;
  border-radius:4px; background:#1a1a2e; color:#aaa; }}
.tab-btn.active {{ background:#0f3460; color:#fff; border-color:#e94560; }}
</style>
</head>
<body>
<div class="header">
  <h1>Spatial-Temporal Window Selection — Compression Result</h1>
  <div class="sub">Grid: {mx}&times;{ny} | Time Windows: {kt} | Top-T: {top_t}
    | Warmup: {warmup_ticks} ticks ({warmup_ticks * timescale_ns:.0f}ns)
    | Selected: {len(selected_set)}/{kt} windows
    | Compression: {compression:.1f}% time kept</div>
</div>
<div class="layout">
  <div class="panels">
    <div id="timeline"></div>
    <div id="location"></div>
    <div id="heatmap_total"></div>
    <div id="location_sel"></div>
    <div id="heatmap_sel"></div>
  </div>
  <div class="sidebar">
    <h3>Summary</h3>
    <div class="stat"><div class="label">Simulation</div>
      <div class="value">{total_sim_ns:.0f} ns</div></div>
    <div class="stat"><div class="label">Total Toggles</div>
      <div class="value">{total_toggles:,}</div></div>
    <div class="stat"><div class="label">Selected Toggles</div>
      <div class="value">{selected_toggles:,} ({selected_toggles/total_toggles*100:.1f}%)</div></div>
    <div class="stat"><div class="label">Time Kept</div>
      <div class="value">{compression:.1f}%</div></div>
    <div class="stat"><div class="label">Active Regions</div>
      <div class="value">{n_active_regions} / {mx*ny}</div></div>
    <div class="stat"><div class="label">Merged Intervals</div>
      <div class="value">{len(merged_intervals)}</div></div>
    <div class="stat"><div class="label">Signals Plotted</div>
      <div class="value">{n_scatter:,} (top by toggle)</div></div>

    <h3>Selected Windows</h3>
    <table>
      <tr><th>Win</th><th>Time (ns)</th><th>Votes</th><th>Toggles</th></tr>
      {"".join(
          f'<tr><td>{j}</td>'
          f'<td>{times_ns[j]:.0f}</td>'
          f'<td>{win_region_count[j]}</td>'
          f'<td>{toggle_time[j]:,}</td></tr>'
          for j in sorted(selected_set)
      )}
    </table>

    <h3>Merged Intervals</h3>
    <table>
      <tr><th>#</th><th>Range (ns)</th><th>Duration</th></tr>
      {"".join(
          f'<tr><td>{i+1}</td>'
          f'<td>{s*timescale_ns:.0f}~{e*timescale_ns:.0f}</td>'
          f'<td>{(e-s)*timescale_ns:.0f}ns</td></tr>'
          for i,(s,e) in enumerate(merged_intervals)
      )}
    </table>
  </div>
</div>

<script>
var darkBg = '#1a1a2e';

// ═══════════════════════════════════════════════════════════
// 1. Timeline bar chart (top, full width)
// ═══════════════════════════════════════════════════════════
Plotly.newPlot('timeline', [{{
  x: {json.dumps(times_ns)},
  y: {json.dumps(toggle_time)},
  type: 'bar',
  marker: {{ color: {json.dumps(bar_colors)} }},
  hovertemplate: 'Win %{{pointNumber}}<br>%{{x:.0f}} ns<br>Toggles: %{{y:,}}<extra></extra>',
  width: {win_size * timescale_ns * 0.85}
}}], {{
  title: {{ text:'Timeline: Toggle per Window  (red = selected, gold band = merged interval)',
            font:{{size:13,color:'#ccc'}} }},
  paper_bgcolor: darkBg, plot_bgcolor: darkBg,
  xaxis: {{ title:'Time (ns)', color:'#aaa', gridcolor:'#333' }},
  yaxis: {{ title:'Toggle Count', color:'#aaa', gridcolor:'#333' }},
  shapes: [{",".join(interval_shapes)}],
  margin: {{ t:36, b:36, l:56, r:8 }}
}}, {{responsive:true}});

// ═══════════════════════════════════════════════════════════
// 2. Location scatter — ALL windows (middle left)
// ═══════════════════════════════════════════════════════════
Plotly.newPlot('location', [{{
  x: {json.dumps(sc_x)},
  y: {json.dumps(sc_y)},
  mode: 'markers',
  type: 'scattergl',
  marker: {{
    size: 3,
    color: {json.dumps(sc_log)},
    colorscale: 'Hot', reversescale: true,
    colorbar: {{ title:'log10(tog+1)', titleside:'right',
                 titlefont:{{color:'#ccc',size:10}}, tickfont:{{color:'#ccc',size:9}},
                 len:0.9 }},
    opacity: 0.7
  }},
  text: {json.dumps(sc_names)},
  customdata: {json.dumps(sc_tc)},
  hovertemplate: '%{{text}}<br>(%{{x:.1f}}, %{{y:.1f}}) um<br>Toggles: %{{customdata:,}}<extra></extra>'
}}], {{
  title: {{ text:'Signal Location — Total Toggle (all windows)',
            font:{{size:12,color:'#ccc'}} }},
  paper_bgcolor: darkBg, plot_bgcolor: darkBg,
  xaxis: {{ title:'X (um)', color:'#aaa', gridcolor:'#333', scaleanchor:'y' }},
  yaxis: {{ title:'Y (um)', color:'#aaa', gridcolor:'#333' }},
  shapes: [{",".join(grid_shapes_scatter)}],
  margin: {{ t:32, b:32, l:48, r:8 }}
}}, {{responsive:true}});

// ═══════════════════════════════════════════════════════════
// 3. Grid heatmap — total toggles (middle right)
// ═══════════════════════════════════════════════════════════
Plotly.newPlot('heatmap_total', [{{
  z: {json.dumps(spatial_total_log)},
  x: {json.dumps(x_labels)},
  y: {json.dumps(y_labels)},
  type: 'heatmap',
  colorscale: 'Hot', reversescale: true,
  customdata: {json.dumps(spatial_total)},
  hovertemplate: '(%{{x:.0f}}, %{{y:.0f}}) um<br>Toggles: %{{customdata:,}}<extra></extra>',
  colorbar: {{ title:'log10(tog+1)', titleside:'right',
               titlefont:{{color:'#ccc',size:10}}, tickfont:{{color:'#ccc',size:9}} }}
}}], {{
  title: {{ text:'Grid Heatmap — Total Toggle ({mx}&times;{ny})',
            font:{{size:12,color:'#ccc'}} }},
  paper_bgcolor: darkBg, plot_bgcolor: darkBg,
  xaxis: {{ title:'X (um)', color:'#aaa', gridcolor:'#333', scaleanchor:'y' }},
  yaxis: {{ title:'Y (um)', color:'#aaa', gridcolor:'#333' }},
  margin: {{ t:32, b:32, l:48, r:8 }}
}}, {{responsive:true}});

// ═══════════════════════════════════════════════════════════
// 4. Location scatter — SELECTED windows only (bottom left)
//    Reuse same positions, show selected-window toggle as color
// ═══════════════════════════════════════════════════════════
Plotly.newPlot('location_sel', [{{
  x: {json.dumps(sc_x)},
  y: {json.dumps(sc_y)},
  mode: 'markers',
  type: 'scattergl',
  marker: {{
    size: 3,
    color: {json.dumps(sc_sel_log)},
    colorscale: 'Hot', reversescale: true,
    colorbar: {{ title:'log10(tog+1)', titleside:'right',
                 titlefont:{{color:'#ccc',size:10}}, tickfont:{{color:'#ccc',size:9}},
                 len:0.9 }},
    opacity: 0.7
  }},
  text: {json.dumps(sc_names)},
  customdata: {json.dumps([[s, t] for s, t in zip(sc_sel_tc, sc_tc)])},
  hovertemplate: '%{{text}}<br>(%{{x:.1f}}, %{{y:.1f}}) um<br>Selected: %{{customdata[0]:,}} / Total: %{{customdata[1]:,}}<extra></extra>'
}}], {{
  title: {{ text:'Signal Location — Selected Window Toggle Only',
            font:{{size:12,color:'#ccc'}} }},
  paper_bgcolor: darkBg, plot_bgcolor: darkBg,
  xaxis: {{ title:'X (um)', color:'#aaa', gridcolor:'#333', scaleanchor:'y' }},
  yaxis: {{ title:'Y (um)', color:'#aaa', gridcolor:'#333' }},
  shapes: [{",".join(grid_shapes_scatter)}],
  margin: {{ t:32, b:32, l:48, r:8 }}
}}, {{responsive:true}});

// ═══════════════════════════════════════════════════════════
// 5. Grid heatmap — selected windows only (bottom right)
// ═══════════════════════════════════════════════════════════
Plotly.newPlot('heatmap_sel', [{{
  z: {json.dumps(spatial_sel_log)},
  x: {json.dumps(x_labels)},
  y: {json.dumps(y_labels)},
  type: 'heatmap',
  colorscale: 'Hot', reversescale: true,
  customdata: {json.dumps(spatial_selected)},
  hovertemplate: '(%{{x:.0f}}, %{{y:.0f}}) um<br>Selected Toggles: %{{customdata:,}}<extra></extra>',
  colorbar: {{ title:'log10(tog+1)', titleside:'right',
               titlefont:{{color:'#ccc',size:10}}, tickfont:{{color:'#ccc',size:9}} }}
}}], {{
  title: {{ text:'Grid Heatmap — Selected Windows Only ({mx}&times;{ny})',
            font:{{size:12,color:'#ccc'}} }},
  paper_bgcolor: darkBg, plot_bgcolor: darkBg,
  xaxis: {{ title:'X (um)', color:'#aaa', gridcolor:'#333', scaleanchor:'y' }},
  yaxis: {{ title:'Y (um)', color:'#aaa', gridcolor:'#333' }},
  margin: {{ t:32, b:32, l:48, r:8 }}
}}, {{responsive:true}});
</script>
</body>
</html>"""

    os.makedirs(os.path.dirname(os.path.abspath(html_path)), exist_ok=True)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  HTML: {html_path}")


# ── JSON Report ──────────────────────────────────────────────────────

def write_json_report(json_path: str, args, t_max: int,
                      selected_set: set, win_region_count: list,
                      toggle_time: list, merged_intervals: list,
                      region_picks: dict, stats: dict,
                      mx: int, ny: int, kt: int):
    timescale_ns = args.timescale_ps / 1000
    win_size = t_max / kt

    total_toggles = sum(toggle_time)
    selected_toggles = sum(toggle_time[j] for j in selected_set)
    total_selected_ticks = sum(e - s for s, e in merged_intervals)

    report = {
        "parameters": {
            "mx": mx, "ny": ny, "kt": kt, "top_t": args.top,
            "warmup_cycles": args.warmup_cycles,
            "clock_ns": args.clock_ns,
            "timescale_ps": args.timescale_ps,
            "warmup_ticks": int(args.warmup_cycles * args.clock_ns * 1000
                                / args.timescale_ps),
        },
        "simulation": {
            "t_max_ticks": t_max,
            "t_max_ns": round(t_max * timescale_ns, 2),
            "total_toggles": total_toggles,
        },
        "selection": {
            "n_windows_selected": len(selected_set),
            "n_windows_total": kt,
            "selected_window_indices": sorted(selected_set),
            "selected_toggles": selected_toggles,
            "toggle_coverage_pct": round(
                selected_toggles / total_toggles * 100, 2)
            if total_toggles > 0 else 0,
        },
        "merged_intervals": [
            {"start_tick": s, "end_tick": e,
             "start_ns": round(s * timescale_ns, 2),
             "end_ns": round(e * timescale_ns, 2),
             "duration_ns": round((e - s) * timescale_ns, 2)}
            for s, e in merged_intervals
        ],
        "compression": {
            "output_ticks": total_selected_ticks,
            "output_ns": round(total_selected_ticks * timescale_ns, 2),
            "ratio_pct": round(
                total_selected_ticks / t_max * 100, 2) if t_max > 0 else 0,
        },
        "per_window_detail": [
            {"index": j,
             "start_ns": round(j * win_size * timescale_ns, 2),
             "end_ns": round((j + 1) * win_size * timescale_ns, 2),
             "toggles": toggle_time[j],
             "region_votes": win_region_count[j],
             "selected": j in selected_set}
            for j in range(kt)
        ],
    }

    os.makedirs(os.path.dirname(os.path.abspath(json_path)), exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"  JSON: {json_path}")


# ── Main ─────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(
        description="Spatial-Temporal Window Selection for VCD Compression")
    p.add_argument("--location", required=True,
                   help="signal_location_map.csv path")
    p.add_argument("--toggles", required=True,
                   help="JSONL toggle file path")
    p.add_argument("--vcd", required=True,
                   help="Input VCD file path")
    p.add_argument("--mx", type=int, default=10,
                   help="Grid columns (default: 10)")
    p.add_argument("--ny", type=int, default=10,
                   help="Grid rows (default: 10)")
    p.add_argument("--kt", type=int, default=20,
                   help="Number of time windows (default: 20)")
    p.add_argument("--top", type=int, default=2,
                   help="Top-T windows per region (default: 2)")
    p.add_argument("--warmup-cycles", type=int, default=10,
                   help="Warmup cycles before each window (default: 10)")
    p.add_argument("--min-cluster", type=int, default=1,
                   help="Minimum cluster size: discard isolated windows, "
                        "keep only clusters of >= N adjacent selected windows "
                        "(default: 1 = no filtering)")
    p.add_argument("--clock-ns", type=float, default=50.0,
                   help="Clock period in ns (default: 50)")
    p.add_argument("--timescale-ps", type=float, default=10.0,
                   help="VCD timescale in ps (default: 10)")
    p.add_argument("--output", required=True,
                   help="Output compressed VCD path")
    p.add_argument("--html", default=None,
                   help="Output HTML visualization path")
    p.add_argument("--json-out", default=None,
                   help="Output JSON report path")
    args = p.parse_args()

    mx, ny, kt, top_t = args.mx, args.ny, args.kt, args.top
    warmup_ticks = int(args.warmup_cycles * args.clock_ns * 1000
                       / args.timescale_ps)

    print("=" * 60)
    print("  Spatial-Temporal Window Selection")
    print("=" * 60)
    print(f"  Grid: {mx}x{ny} | Windows: {kt} | Top-T: {top_t}")
    print(f"  Warmup: {args.warmup_cycles} cycles = {warmup_ticks} ticks "
          f"({args.warmup_cycles * args.clock_ns:.0f} ns)")
    print()

    # Step 1: Load locations
    print("[1/7] Loading physical locations...")
    locations = load_locations(args.location)
    print(f"  {len(locations)} signals with coordinates")

    # Step 2: Build spatial grid
    print(f"[2/7] Building {mx}x{ny} spatial grid...")
    signal_to_cell, bbox = build_spatial_grid(locations, mx, ny)
    print(f"  {len(signal_to_cell)} signals assigned to grid cells")

    # Step 3: Build 3D toggle matrix
    print(f"[3/7] Building 3D toggle matrix ({ny}x{mx}x{kt})...")
    toggle_3d, toggle_time, t_max, n_lines, sig_toggles, sig_win_toggles = \
        build_toggle_matrix(args.toggles, signal_to_cell, mx, ny, kt)
    timescale_ns = args.timescale_ps / 1000
    print(f"  JSONL lines: {n_lines}, t_max: {t_max} ticks "
          f"({t_max * timescale_ns:.0f} ns)")
    print(f"  Total toggles: {sum(toggle_time):,}")

    # Step 4: Per-region selection
    print(f"[4/7] Selecting top-{top_t} windows per region...")
    selected_set, region_picks, win_region_count = select_per_region(
        toggle_3d, mx, ny, kt, top_t)
    print(f"  Selected {len(selected_set)}/{kt} unique time windows")
    print(f"  Active regions (non-zero): "
          f"{len(region_picks)}/{mx * ny}")

    # Step 4.5: Cluster filter
    if args.min_cluster > 1:
        before = len(selected_set)
        selected_set = cluster_filter(selected_set, kt, args.min_cluster)
        print(f"  Cluster filter (min={args.min_cluster}): "
              f"{before} → {len(selected_set)} windows")

    # Step 5: Warmup + merge
    print("[5/7] Expanding warmup + merging intervals...")
    merged = expand_and_merge(selected_set, kt, t_max, warmup_ticks)
    total_merged_ticks = sum(e - s for s, e in merged)
    print(f"  {len(merged)} merged intervals, "
          f"total: {total_merged_ticks} ticks "
          f"({total_merged_ticks * timescale_ns:.0f} ns, "
          f"{total_merged_ticks / t_max * 100:.1f}%)")
    for i, (s, e) in enumerate(merged):
        print(f"    [{i + 1}] #{s}~#{e}  "
              f"({s * timescale_ns:.0f}~{e * timescale_ns:.0f} ns, "
              f"duration {(e - s) * timescale_ns:.0f} ns)")

    # Step 6: Splice VCD
    print("[6/7] Splicing VCD...")
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    stats = splice_vcd_v2(args.vcd, merged, args.output)
    in_size = os.path.getsize(args.vcd)
    out_size = os.path.getsize(args.output)
    print(f"  Segments: {stats.get('n_segments', 0)}")
    print(f"  Time points: {stats.get('n_times', 0)}")
    print(f"  Value changes: {stats.get('n_changes', 0)}")
    print(f"  Size: {in_size:,} → {out_size:,} bytes "
          f"({out_size / in_size * 100:.1f}%)")

    # Step 7: Outputs
    print("[7/7] Writing reports...")
    if args.html:
        generate_html(toggle_time, toggle_3d, mx, ny, kt,
                      selected_set, win_region_count,
                      merged, t_max, warmup_ticks, bbox,
                      stats, top_t, locations, sig_toggles,
                      sig_win_toggles, args.html)
    if args.json_out:
        write_json_report(args.json_out, args, t_max,
                          selected_set, win_region_count,
                          toggle_time, merged,
                          region_picks, stats, mx, ny, kt)

    print()
    print("=" * 60)
    print("  Done.")
    print("=" * 60)


if __name__ == "__main__":
    main()
