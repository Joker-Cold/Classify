#!/usr/bin/env python3
"""
VCD + DEF → HTML 一键流水线

给定 VCD 波形文件和 DEF 物理版图文件, 自动执行:
  1. VCD → JSONL (hold-last-value)
  2. JSONL → Toggle JSONL (XOR toggle 标记)
  3. VCD + DEF → 信号坐标 CSV
  4. 空间时间选窗 → 压缩 VCD + 可视化 HTML + JSON 报告

Usage:
    python code/run_pipeline.py --vcd input.vcd --def design.def
    python code/run_pipeline.py --vcd input.vcd --def design.def -o result/
    python code/run_pipeline.py --vcd input.vcd --def design.def --kt 200 --top 1 --min-cluster 4
"""
import argparse
import os
import re
import sys
import time
from pathlib import Path

# Ensure sibling modules are importable
sys.path.insert(0, str(Path(__file__).parent))

from vcd_to_jsonl import vcd_to_jsonl
from jsonl_toggle_mark import mark_toggles
from vcd_def_mapper import (
    parse_def_units, parse_def_components, parse_def_pins,
    parse_def_nets, parse_vcd_signals, build_mapping, write_csv,
)
from parse_vcd_signal import VCDSignalParser
from spatial_temporal_select import (
    load_locations, build_spatial_grid, build_toggle_matrix,
    select_per_region, cluster_filter, expand_and_merge,
    splice_vcd_v2, generate_html, write_json_report,
)


def detect_timescale_ps(vcd_path: str) -> float:
    """Read $timescale from VCD header, return value in picoseconds."""
    with open(vcd_path, "r", encoding="utf-8") as f:
        in_ts = False
        for line in f:
            s = line.strip()
            if s.startswith("$timescale"):
                in_ts = True
                # might be on same line: $timescale 10ps $end
                rest = s.replace("$timescale", "").replace("$end", "").strip()
                if rest:
                    return _parse_timescale(rest)
                continue
            if in_ts:
                s = s.replace("$end", "").strip()
                if s:
                    return _parse_timescale(s)
                continue
            if s.startswith("$scope") or s.startswith("$var"):
                break  # past header
    print("  WARNING: Could not detect $timescale, defaulting to 10ps")
    return 10.0


def _parse_timescale(s: str) -> float:
    """Parse timescale string like '10ps', '1ns' into picoseconds."""
    m = re.match(r"(\d+)\s*(s|ms|us|ns|ps|fs)", s.strip())
    if not m:
        print(f"  WARNING: Cannot parse timescale '{s}', defaulting to 10ps")
        return 10.0
    val = int(m.group(1))
    unit = m.group(2)
    multipliers = {"fs": 0.001, "ps": 1, "ns": 1000, "us": 1e6, "ms": 1e9, "s": 1e12}
    return val * multipliers[unit]


def main():
    p = argparse.ArgumentParser(
        description="VCD + DEF → Spatial-Temporal HTML (一键流水线)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    # Required inputs
    p.add_argument("--vcd", required=True, help="输入 VCD 波形文件")
    p.add_argument("--def", dest="def_file", required=True,
                   help="输入 DEF 物理版图文件")
    p.add_argument("-o", "--output-dir", default=None,
                   help="输出目录 (默认: ./output/)")

    # Spatial-temporal parameters
    p.add_argument("--mx", type=int, default=10, help="空间网格列数 (默认 10)")
    p.add_argument("--ny", type=int, default=10, help="空间网格行数 (默认 10)")
    p.add_argument("--kt", type=int, default=200,
                   help="时间窗口数 (默认 200)")
    p.add_argument("--top", type=int, default=1,
                   help="每 region 选 top-T 窗口 (默认 1)")
    p.add_argument("--min-cluster", type=int, default=4,
                   help="簇过滤阈值 (默认 4)")
    p.add_argument("--warmup-cycles", type=int, default=5,
                   help="Warmup 周期数 (默认 5)")
    p.add_argument("--clock-ns", type=float, default=50.0,
                   help="时钟周期 ns (默认 50)")

    # Optional overrides
    p.add_argument("--timescale-ps", type=float, default=None,
                   help="VCD timescale (ps), 默认自动检测")
    p.add_argument("--skip-vcd", action="store_true",
                   help="跳过 VCD 压缩输出 (只生成 HTML + JSON)")

    args = p.parse_args()

    vcd_path = Path(args.vcd).resolve()
    def_path = Path(args.def_file).resolve()

    if not vcd_path.exists():
        print(f"ERROR: VCD not found: {vcd_path}", file=sys.stderr)
        sys.exit(1)
    if not def_path.exists():
        print(f"ERROR: DEF not found: {def_path}", file=sys.stderr)
        sys.exit(1)

    out_dir = Path(args.output_dir).resolve() if args.output_dir else \
              Path.cwd() / "output"
    out_dir.mkdir(parents=True, exist_ok=True)

    stem = vcd_path.stem  # e.g. "test" from "test.vcd"

    # Detect timescale
    if args.timescale_ps is not None:
        timescale_ps = args.timescale_ps
    else:
        timescale_ps = detect_timescale_ps(str(vcd_path))
    timescale_ns = timescale_ps / 1000.0

    warmup_ticks = int(args.warmup_cycles * args.clock_ns * 1000
                       / timescale_ps)

    print("=" * 64)
    print("  VCD + DEF → Spatial-Temporal HTML Pipeline")
    print("=" * 64)
    print(f"  VCD       : {vcd_path}")
    print(f"  DEF       : {def_path}")
    print(f"  Output    : {out_dir}")
    print(f"  Timescale : {timescale_ps} ps (auto)" if args.timescale_ps is None
          else f"  Timescale : {timescale_ps} ps (manual)")
    print(f"  Grid      : {args.mx}x{args.ny}")
    print(f"  Windows   : kt={args.kt}, top={args.top}, min-cluster={args.min_cluster}")
    print(f"  Warmup    : {args.warmup_cycles} cycles = {warmup_ticks} ticks")
    print()
    t_start = time.time()

    # ── Step 1: VCD → JSONL ──────────────────────────────────────────
    print("[1/5] VCD → JSONL ...")
    jsonl_path = out_dir / f"{stem}.jsonl"
    if jsonl_path.exists():
        print(f"  SKIP (already exists: {jsonl_path.name})")
    else:
        jsonl_path = Path(vcd_to_jsonl(str(vcd_path), str(out_dir)))
    print()

    # ── Step 2: JSONL → Toggle JSONL ─────────────────────────────────
    print("[2/5] JSONL → Toggle JSONL ...")
    toggles_path = out_dir / f"{stem}_toggles.jsonl"
    if toggles_path.exists():
        print(f"  SKIP (already exists: {toggles_path.name})")
    else:
        mark_toggles(str(jsonl_path), str(toggles_path))
    print()

    # ── Step 3: VCD + DEF → Location CSV ─────────────────────────────
    print("[3/5] VCD + DEF → Location CSV ...")
    location_csv = out_dir / f"{stem}_location.csv"
    if location_csv.exists():
        print(f"  SKIP (already exists: {location_csv.name})")
    else:
        units = parse_def_units(str(def_path))
        print(f"  DEF UNITS = {units}")
        components = parse_def_components(str(def_path))
        print(f"  Components: {len(components)}")
        pins = parse_def_pins(str(def_path))
        print(f"  Pins: {len(pins)}")
        nets = parse_def_nets(str(def_path))
        print(f"  Nets: {len(nets)}")
        vcd_parser = VCDSignalParser(str(vcd_path))
        vcd_parser.parse_header()
        vcd_signals = parse_vcd_signals(str(vcd_path))
        print(f"  VCD signals: {len(vcd_signals)}")
        results = build_mapping(vcd_signals, components, pins, nets,
                                vcd_parser.top_scope, units)
        write_csv(results, str(location_csv))
        mapped = sum(1 for r in results if r["x_um"] is not None)
        print(f"  Mapped: {mapped}/{len(results)}")
    print()

    # ── Step 4: Spatial-Temporal Selection ────────────────────────────
    print("[4/5] Spatial-Temporal Window Selection ...")
    mx, ny, kt, top_t = args.mx, args.ny, args.kt, args.top

    locations = load_locations(str(location_csv))
    print(f"  {len(locations)} signals with coordinates")

    signal_to_cell, bbox = build_spatial_grid(locations, mx, ny)

    toggle_3d, toggle_time, t_max, n_lines, sig_toggles, sig_win_toggles = \
        build_toggle_matrix(str(toggles_path), signal_to_cell, mx, ny, kt)
    print(f"  JSONL: {n_lines} lines, t_max={t_max} ticks "
          f"({t_max * timescale_ns:.0f} ns)")
    print(f"  Total toggles: {sum(toggle_time):,}")

    selected_set, region_picks, win_region_count = select_per_region(
        toggle_3d, mx, ny, kt, top_t)
    print(f"  Per-region top-{top_t}: {len(selected_set)}/{kt} windows")

    if args.min_cluster > 1:
        before = len(selected_set)
        selected_set = cluster_filter(selected_set, kt, args.min_cluster)
        print(f"  Cluster filter (min={args.min_cluster}): "
              f"{before} → {len(selected_set)} windows")

    merged = expand_and_merge(selected_set, kt, t_max, warmup_ticks)
    total_ticks = sum(e - s for s, e in merged)
    print(f"  Merged: {len(merged)} intervals, "
          f"{total_ticks * timescale_ns:.0f} ns "
          f"({total_ticks / t_max * 100:.1f}% of sim)")
    print()

    # ── Step 5: Generate outputs ─────────────────────────────────────
    print("[5/5] Generating outputs ...")

    # VCD splice
    vcd_out = out_dir / f"{stem}_compressed.vcd"
    if not args.skip_vcd:
        stats = splice_vcd_v2(str(vcd_path), merged, str(vcd_out))
        in_sz = os.path.getsize(str(vcd_path))
        out_sz = os.path.getsize(str(vcd_out))
        print(f"  VCD: {in_sz:,} → {out_sz:,} bytes ({out_sz/in_sz*100:.1f}%)")
    else:
        stats = {}
        print("  VCD: skipped (--skip-vcd)")

    # HTML visualization
    html_out = out_dir / f"{stem}_spatial_temporal.html"

    # Build a namespace-like object for write_json_report
    class Args:
        pass
    fake_args = Args()
    fake_args.timescale_ps = timescale_ps
    fake_args.warmup_cycles = args.warmup_cycles
    fake_args.clock_ns = args.clock_ns
    fake_args.top = top_t
    fake_args.min_cluster = args.min_cluster

    generate_html(toggle_time, toggle_3d, mx, ny, kt,
                  selected_set, win_region_count,
                  merged, t_max, warmup_ticks, bbox,
                  stats, top_t, locations, sig_toggles,
                  sig_win_toggles, str(html_out))

    # JSON report
    json_out = out_dir / f"{stem}_report.json"
    write_json_report(str(json_out), fake_args, t_max,
                      selected_set, win_region_count,
                      toggle_time, merged,
                      region_picks, stats, mx, ny, kt)

    elapsed = time.time() - t_start
    print()
    print("=" * 64)
    print(f"  Done in {elapsed:.1f}s")
    print(f"  HTML : {html_out}")
    print(f"  JSON : {json_out}")
    if not args.skip_vcd:
        print(f"  VCD  : {vcd_out}")
    print("=" * 64)


if __name__ == "__main__":
    main()
