#!/usr/bin/env python3
"""
Find Worst-Case Power Window — Phase-Aware + Spatial Concentration

Combines two dimensions for accurate IR Drop worst-case identification:
  1. Time: Phase-Aware depletion model (reuses select_worst_window.py core)
  2. Space: Toggle concentration scoring (DEF physical grid or VCD scope)

Usage:
    # Basic (Phase-Aware only, no spatial analysis)
    python find_worst_window.py output/test_toggles.jsonl --window-ns 1185

    # Physical grid mode (DEF + VCD, highest accuracy)
    python find_worst_window.py output/test_toggles.jsonl --window-ns 1185 \
        --vcd des_demo/vcd/test.vcd --def des_demo/db/des3.def --grid-size 8

    # Scope mode (VCD only, backward compatible)
    python find_worst_window.py output/test_toggles.jsonl --window-ns 1185 \
        --vcd des_demo/vcd/test.vcd

    # Advanced parameters
    python find_worst_window.py output/test_toggles.jsonl --window-ns 1185 \
        --vcd des_demo/vcd/test.vcd --def des_demo/db/des3.def \
        --clock-ns 50 --depletion-ratio 0.7 --spatial-weight 1.0 --top 3
"""
import json
import sys
import argparse
from collections import defaultdict
from pathlib import Path

# Reuse Phase-Aware core from select_worst_window
from select_worst_window import (
    CycleStat, Phase, Window,
    aggregate_by_clock, detect_phases, select_windows,
    generate_html, print_report,
)


# ── Spatial Analysis ────────────────────────────────────────────────

def build_scope_map(vcd_path: str, depth: int = 2):
    """Build signal_name -> module mapping from VCD header.

    Uses parse_vcd_signal.py to extract scope hierarchy. Maps each signal's
    disambiguated name (matching JSONL keys) to its module at `depth`.

    Returns:
        dict: disambiguated_signal_name -> module_name
    """
    from parse_vcd_signal import VCDSignalParser

    parser = VCDSignalParser(vcd_path)
    parser.parse_header()

    # Use list_unique_signals to get the same disambiguated names as JSONL
    unique_sigs = parser.list_unique_signals(
        exclude_params=True, exclude_tasks=True)

    signal_to_module = {}
    for entry in unique_sigs:
        # full_name: "test.u0.u2.desOut [63:0]"
        # disambiguated name (entry["name"]): might be "u0.u2.desOut [63:0]"
        full = entry["full_name"]
        parts = full.split(".")
        # Extract module at given depth from scope hierarchy
        if len(parts) > depth:
            module = ".".join(parts[:depth])
        elif len(parts) > 1:
            module = ".".join(parts[:-1])
        else:
            module = parts[0]
        signal_to_module[entry["name"]] = module

    return signal_to_module


def build_grid_map(vcd_path: str, def_path: str, grid_size: int = 8):
    """Build signal_name -> grid_cell mapping from DEF physical coordinates.

    Uses vcd_def_mapper.py to parse DEF and map VCD signals to (x, y).
    Divides chip bounding box into grid_size x grid_size cells.

    Returns:
        dict: disambiguated_signal_name -> "grid_R{row}_C{col}"
    """
    from vcd_def_mapper import (
        parse_def_units, parse_def_components, parse_def_pins,
        parse_def_nets, parse_vcd_signals, build_mapping,
    )
    from parse_vcd_signal import VCDSignalParser

    # Parse DEF
    units = parse_def_units(def_path)
    components = parse_def_components(def_path)
    pins = parse_def_pins(def_path)
    nets = parse_def_nets(def_path)

    # Parse VCD signals
    vcd_signals = parse_vcd_signals(vcd_path)
    vcd_parser = VCDSignalParser(vcd_path)
    vcd_parser.parse_header()

    # Build mapping
    results = build_mapping(vcd_signals, components, pins, nets,
                            vcd_parser.top_scope, units)

    # Compute bounding box from mapped signals
    mapped = [r for r in results if r["x_um"] is not None]
    if not mapped:
        print("WARNING: No signals mapped to physical locations, "
              "falling back to scope mode")
        return None

    xs = [r["x_um"] for r in mapped]
    ys = [r["y_um"] for r in mapped]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)

    # Avoid division by zero for degenerate layouts
    x_span = x_max - x_min if x_max > x_min else 1.0
    y_span = y_max - y_min if y_max > y_min else 1.0

    # Assign each signal to a grid cell
    signal_to_grid = {}
    for r in results:
        if r["x_um"] is None:
            signal_to_grid[r["signal_name"]] = "_unmapped"
            continue
        col = int((r["x_um"] - x_min) / x_span * grid_size)
        row = int((r["y_um"] - y_min) / y_span * grid_size)
        # Clamp to [0, grid_size-1]
        col = min(col, grid_size - 1)
        row = min(row, grid_size - 1)
        signal_to_grid[r["signal_name"]] = f"grid_R{row}_C{col}"

    n_cells = len(set(v for v in signal_to_grid.values() if v != "_unmapped"))
    print(f"  Grid: {grid_size}x{grid_size} ({n_cells} occupied cells), "
          f"chip bbox: ({x_min:.1f},{y_min:.1f})~({x_max:.1f},{y_max:.1f}) um")

    return signal_to_grid


def load_toggles_with_spatial(toggles_path: str, signal_to_group: dict,
                              timescale_ps: float = 10.0,
                              spatial_weight: float = 1.0):
    """Load JSONL toggles with per-group spatial concentration scoring.

    Groups can be modules (scope mode) or grid cells (grid mode).

    For each time point, computes:
        concentration = max(group_toggle) / total_toggle
        effective_score = total_toggle * (1 + alpha * concentration)

    Returns:
        list of (time_ns, effective_score)
        list of (time_ns, raw_toggle_count)  — for reference
        dict: per-timepoint spatial info for reporting
    """
    raw_data = []        # (time_ns, raw_count)
    scored_data = []     # (time_ns, effective_score)
    spatial_info = {}    # time_ns -> {group_toggles, concentration}

    with open(toggles_path, "r", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            t_ticks = rec["time"]
            t_ns = t_ticks * timescale_ps / 1000.0

            # Group toggles by spatial group
            group_toggles = defaultdict(int)
            total = 0
            for sig_name, toggle_bits in rec["signals"].items():
                cnt = toggle_bits.count("1")
                total += cnt
                group = signal_to_group.get(sig_name, "_unknown")
                group_toggles[group] += cnt

            raw_data.append((t_ns, total))

            if total > 0:
                max_group_toggle = max(group_toggles.values())
                concentration = max_group_toggle / total
            else:
                concentration = 0.0

            effective = total * (1.0 + spatial_weight * concentration)
            scored_data.append((t_ns, int(effective)))

            spatial_info[t_ns] = {
                "group_toggles": dict(group_toggles),
                "concentration": concentration,
            }

    return scored_data, raw_data, spatial_info


def load_toggles_plain(toggles_path: str, timescale_ps: float = 10.0):
    """Load JSONL toggles without spatial analysis (fallback when no VCD).

    Returns:
        list of (time_ns, toggle_count)
    """
    data = []
    with open(toggles_path, "r", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            t_ticks = rec["time"]
            t_ns = t_ticks * timescale_ps / 1000.0
            cnt = sum(v.count("1") for v in rec["signals"].values())
            data.append((t_ns, cnt))
    return data


# ── Report ──────────────────────────────────────────────────────────

def print_spatial_report(spatial_info: dict, windows: list,
                         spatial_mode: str = "scope"):
    """Print spatial concentration analysis for selected windows."""
    label = "Grid Cell" if spatial_mode == "grid" else "Module"
    print()
    print(f"  Spatial Concentration Analysis ({spatial_mode} mode):")
    print("  " + "-" * 60)

    # Aggregate per-group stats within each window
    for i, w in enumerate(windows):
        group_totals = defaultdict(int)
        n_points = 0
        for t_ns, info in spatial_info.items():
            if w.start_ns <= t_ns <= w.end_ns:
                for grp, cnt in info["group_toggles"].items():
                    group_totals[grp] += cnt
                n_points += 1

        if not group_totals:
            continue

        total = sum(group_totals.values())
        sorted_grps = sorted(group_totals.items(), key=lambda x: -x[1])

        print(f"\n  Window {i+1} ({w.start_ns:.0f}~{w.end_ns:.0f}ns):")
        print(f"    {label:<35} {'Toggles':>10} {'Share':>8}")
        print("    " + "-" * 55)
        for grp, cnt in sorted_grps[:5]:  # Top 5 groups
            share = cnt / total * 100 if total > 0 else 0
            print(f"    {grp:<35} {cnt:>10,} {share:>7.1f}%")
        if len(sorted_grps) > 5:
            rest = sum(cnt for _, cnt in sorted_grps[5:])
            print(f"    {'(others)':<35} {rest:>10,} "
                  f"{rest/total*100:>7.1f}%")

        win_conc = max(group_totals.values()) / total if total > 0 else 0
        print(f"    Window concentration: {win_conc:.2f}")


# ── Main ────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(
        description="Find worst-case power window (Phase-Aware + Spatial)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("toggles_file",
                   help="Input toggles JSONL file (from jsonl_toggle_mark.py)")
    p.add_argument("--vcd", default=None,
                   help="VCD file for spatial concentration analysis")
    p.add_argument("--def", dest="def_path", default=None,
                   help="DEF file for physical grid-based spatial analysis "
                        "(requires --vcd)")
    p.add_argument("--grid-size", type=int, default=8,
                   help="Grid division size NxN (default: 8)")

    # Window specification (one of these required)
    win_grp = p.add_mutually_exclusive_group()
    win_grp.add_argument("--window-ns", type=float, default=None,
                         help="Window width in nanoseconds")
    win_grp.add_argument("--window-ticks", type=int, default=None,
                         help="Window width in VCD ticks")

    # Phase-Aware parameters
    p.add_argument("--clock-ns", type=float, default=50.0,
                   help="Clock period in ns (default: 50)")
    p.add_argument("--depletion-ratio", type=float, default=0.7,
                   help="Depletion sampling position ratio (default: 0.7)")
    p.add_argument("--timescale-ps", type=float, default=10.0,
                   help="JSONL timescale in ps (default: 10)")

    # Spatial parameters
    p.add_argument("--spatial-weight", type=float, default=1.0,
                   help="Spatial concentration weight alpha (default: 1.0)")
    p.add_argument("--scope-depth", type=int, default=2,
                   help="Scope hierarchy depth for module grouping (default: 2)")

    # Output control
    p.add_argument("--top", type=int, default=3,
                   help="Number of top windows to show (default: 3)")
    p.add_argument("--budget", type=float, default=None,
                   help="Budget ratio for Phase-Aware selection "
                        "(default: auto from --window-ns)")
    p.add_argument("--html", default=None,
                   help="Output HTML visualization path")
    p.add_argument("--json-out", default=None,
                   help="Output window info as JSON")

    args = p.parse_args()

    toggles_file = Path(args.toggles_file).resolve()
    if not toggles_file.exists():
        print(f"ERROR: File not found: {toggles_file}", file=sys.stderr)
        sys.exit(1)

    # ── Load data ──
    print("=" * 70)
    print("  Find Worst-Case Power Window (Phase-Aware + Spatial)")
    print("=" * 70)
    print(f"  Input: {toggles_file}")

    use_spatial = args.vcd is not None
    spatial_mode = None  # "grid", "scope", or None

    if args.def_path and not args.vcd:
        print("WARNING: --def requires --vcd, ignoring --def", file=sys.stderr)

    if use_spatial:
        vcd_path = Path(args.vcd).resolve()
        if not vcd_path.exists():
            print(f"ERROR: VCD file not found: {vcd_path}", file=sys.stderr)
            sys.exit(1)
        print(f"  VCD:   {vcd_path}")

        # Choose spatial mode: grid (DEF+VCD) or scope (VCD only)
        signal_to_group = None
        if args.def_path:
            def_path = Path(args.def_path).resolve()
            if not def_path.exists():
                print(f"ERROR: DEF file not found: {def_path}",
                      file=sys.stderr)
                sys.exit(1)
            print(f"  DEF:   {def_path}")
            print(f"  Mode:  Phase-Aware + Grid spatial "
                  f"({args.grid_size}x{args.grid_size}, "
                  f"alpha={args.spatial_weight})")
            signal_to_group = build_grid_map(
                str(vcd_path), str(def_path), args.grid_size)
            if signal_to_group is not None:
                spatial_mode = "grid"

        if signal_to_group is None:
            # Fallback to scope mode
            print(f"  Mode:  Phase-Aware + Scope spatial "
                  f"(depth={args.scope_depth}, alpha={args.spatial_weight})")
            signal_to_group = build_scope_map(str(vcd_path), args.scope_depth)
            spatial_mode = "scope"

        scored_data, raw_data, spatial_info = load_toggles_with_spatial(
            str(toggles_file), signal_to_group,
            args.timescale_ps, args.spatial_weight)
    else:
        print("  Mode:  Phase-Aware only (no VCD spatial analysis)")
        scored_data = load_toggles_plain(str(toggles_file), args.timescale_ps)
        raw_data = scored_data
        spatial_info = None

    if not scored_data:
        print("ERROR: No data loaded", file=sys.stderr)
        sys.exit(1)

    total_time_ns = scored_data[-1][0]
    print()

    # ── Compute budget from window-ns if specified ──
    if args.budget is not None:
        budget_ratio = args.budget
    elif args.window_ns is not None:
        budget_ratio = args.window_ns / total_time_ns
    elif args.window_ticks is not None:
        window_ns = args.window_ticks * args.timescale_ps / 1000.0
        budget_ratio = window_ns / total_time_ns
    else:
        # Default: 10% budget
        budget_ratio = 0.1

    # ── Phase-Aware pipeline ──
    # Always use raw toggle data for phase detection (thresholds are
    # calibrated for raw values; spatial scoring would distort them)
    raw_cycle_stats = aggregate_by_clock(raw_data, args.clock_ns)
    phases = detect_phases(raw_cycle_stats)

    if not phases:
        print("WARNING: No active phases detected", file=sys.stderr)
        print("  Falling back to entire simulation range")
        active = [c for c in raw_cycle_stats if c.toggle_sum > 0]
        if active:
            phases = [Phase(
                start_cycle=active[0].index,
                end_cycle=active[-1].index,
                cycles=active,
                total_toggles=sum(c.toggle_sum for c in active),
                avg_toggles=sum(c.toggle_sum for c in active) / len(active),
                peak_toggles=max(c.toggle_sum for c in active),
            )]
        else:
            print("ERROR: No toggle data found", file=sys.stderr)
            sys.exit(1)

    # ── Select windows ──
    # If spatial scoring is enabled, build spatially-weighted cycle stats
    # for window selection (higher concentration → prefer that phase)
    if use_spatial:
        scored_cycle_stats = aggregate_by_clock(scored_data, args.clock_ns)
        # Re-rank phases by spatially-weighted total
        for phase in phases:
            phase_scored_total = sum(
                c.toggle_sum for c in scored_cycle_stats
                if phase.start_ns <= c.time_ns <= phase.end_ns)
            # Store weighted score for sorting (higher = worse IR drop risk)
            phase._spatial_score = phase_scored_total
    else:
        scored_cycle_stats = raw_cycle_stats

    windows = select_windows(
        phases, total_time_ns,
        budget_ratio=budget_ratio,
        clock_ns=args.clock_ns,
        depletion_ratio=args.depletion_ratio,
    )

    # Limit to top N, ranking by spatial score if available
    if len(windows) > args.top:
        windows = sorted(windows, key=lambda w: -w.toggle_sum)[:args.top]

    # Ensure toggle sums reflect raw (not spatial-weighted) counts
    for w in windows:
        w.toggle_sum = sum(c.toggle_sum for c in raw_cycle_stats
                           if w.start_ns <= c.time_ns <= w.end_ns)

    print_report(raw_data, raw_cycle_stats, phases, windows, total_time_ns)

    # ── Spatial report ──
    if use_spatial and spatial_info:
        print_spatial_report(spatial_info, windows, spatial_mode)

    # ── HTML visualization ──
    if args.html:
        generate_html(raw_cycle_stats, phases, windows, args.html,
                      args.clock_ns)

    # ── JSON output ──
    if args.json_out:
        out = {
            "total_time_ns": total_time_ns,
            "budget_ratio": budget_ratio,
            "spatial_mode": spatial_mode,
            "spatial_weight": args.spatial_weight if use_spatial else None,
            "grid_size": args.grid_size if spatial_mode == "grid" else None,
            "phases": [
                {"id": i + 1, "start_ns": ph.start_ns, "end_ns": ph.end_ns,
                 "n_active": ph.n_active,
                 "avg_toggles": round(ph.avg_toggles),
                 "peak_toggles": ph.peak_toggles}
                for i, ph in enumerate(phases)
            ],
            "windows": [
                {"id": i + 1, "start_ns": w.start_ns, "end_ns": w.end_ns,
                 "duration_ns": w.duration_ns, "toggle_sum": w.toggle_sum,
                 "phase_id": w.phase_id + 1}
                for i, w in enumerate(windows)
            ],
        }
        Path(args.json_out).write_text(
            json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\n  JSON output: {args.json_out}")

    print()
    print("=" * 70)


if __name__ == "__main__":
    main()
