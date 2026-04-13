#!/usr/bin/env python3
"""
Phase-Aware Multi-Window Worst-Case Selection
基于活跃相位分段和退耦耗尽位置估计的 VCD 窗口筛选方法

支持两种输入:
  1. Voltus togglestats 文件 (--togglestats)
  2. JSONL toggle 文件 (--jsonl, 由 jsonl_toggle_mark.py 生成)

Usage:
    # 从 Voltus togglestats 选窗
    python select_worst_window.py --togglestats voltus_power.togglestats --budget 0.1

    # 从 JSONL toggle 文件选窗
    python select_worst_window.py --jsonl output/sim_output_toggles.jsonl --budget 0.1

    # 指定时钟周期和采样位置
    python select_worst_window.py --togglestats voltus_power.togglestats \\
        --budget 0.1 --clock-ns 50 --depletion-ratio 0.7

    # 输出 HTML 可视化
    python select_worst_window.py --togglestats voltus_power.togglestats \\
        --budget 0.1 --html output/window_selection.html
"""
import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path


# ── Data Structures ──────────────────────────────────────────────────

@dataclass
class CycleStat:
    """一个时钟周期的统计."""
    index: int          # 周期序号
    time_ns: float      # 起始时间 (ns)
    toggle_sum: int     # 该周期内的翻转总数


@dataclass
class Phase:
    """一段连续高活跃的相位."""
    start_cycle: int
    end_cycle: int      # inclusive
    cycles: list        # list of CycleStat
    total_toggles: int = 0
    avg_toggles: float = 0.0
    peak_toggles: int = 0

    @property
    def n_active(self) -> int:
        return len(self.cycles)

    @property
    def start_ns(self) -> float:
        return self.cycles[0].time_ns if self.cycles else 0.0

    @property
    def end_ns(self) -> float:
        return self.cycles[-1].time_ns if self.cycles else 0.0

    @property
    def duration_ns(self) -> float:
        return self.end_ns - self.start_ns


@dataclass
class Window:
    """选中的时间窗口."""
    start_ns: float
    end_ns: float
    phase_id: int
    toggle_sum: int = 0
    reason: str = ""

    @property
    def duration_ns(self) -> float:
        return self.end_ns - self.start_ns


# ── Parsers ──────────────────────────────────────────────────────────

def parse_togglestats(filepath: str) -> list[tuple[float, int]]:
    """解析 Voltus togglestats 文件.

    Returns: [(time_ns, toggle_count), ...]
    """
    data = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("*"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                time_s = float(parts[0])
                count = int(parts[1])
                data.append((time_s * 1e9, count))  # 转为 ns
    return data


def parse_jsonl_toggles(filepath: str, timescale_ps: float = 10.0) -> list[tuple[float, int]]:
    """解析 JSONL toggle 文件.

    Returns: [(time_ns, toggle_count), ...]
    """
    data = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            t_ticks = rec["time"]
            t_ns = t_ticks * timescale_ps / 1000.0
            cnt = sum(v.count("1") for v in rec["signals"].values())
            data.append((t_ns, cnt))
    return data


# ── Core Algorithm ───────────────────────────────────────────────────

def aggregate_by_clock(raw_data: list[tuple[float, int]],
                       clock_ns: float) -> list[CycleStat]:
    """将原始时间序列按时钟周期聚合."""
    if not raw_data:
        return []

    cycles = {}
    for t_ns, count in raw_data:
        idx = int(t_ns / clock_ns)
        if idx not in cycles:
            cycles[idx] = CycleStat(index=idx, time_ns=idx * clock_ns,
                                    toggle_sum=0)
        cycles[idx].toggle_sum += count

    return [cycles[k] for k in sorted(cycles.keys())]


def detect_phases(cycle_stats: list[CycleStat],
                  clock_only_threshold: int = 200,
                  ma_window: int = 5) -> list[Phase]:
    """检测活跃相位.

    采用移动平均 (MA) 分段: 将活跃周期的 toggle 水平做 MA 平滑后,
    按水平变化自动切分为 HIGH / MED / LOW 三级, HIGH 和 MED 段合并为 Phase,
    LOW 段作为 Phase 分界.

    Args:
        cycle_stats: 按时钟周期聚合的统计列表
        clock_only_threshold: 纯时钟翻转的阈值 (低于此值视为非活跃)
        ma_window: 移动平均窗口大小 (活跃周期数)
    """
    # 提取活跃周期
    active_cycles = [c for c in cycle_stats if c.toggle_sum > clock_only_threshold]

    if not active_cycles:
        return []

    n = len(active_cycles)

    # 计算移动平均
    half_w = ma_window // 2
    ma_values = []
    for i in range(n):
        start = max(0, i - half_w)
        end = min(n, i + half_w + 1)
        avg = sum(active_cycles[j].toggle_sum for j in range(start, end)) / (end - start)
        ma_values.append(avg)

    # 计算自适应阈值: 基于活跃周期 toggle 分布
    sorted_toggles = sorted(c.toggle_sum for c in active_cycles)
    median_toggle = sorted_toggles[n // 2]
    p75 = sorted_toggles[int(n * 0.75)]

    # HIGH: MA >= 0.8 * p75, MED: MA >= 0.5 * median, LOW: below
    thresh_high = 0.8 * p75
    thresh_med = 0.5 * median_toggle

    # 给每个活跃周期打标签
    labels = []  # "H", "M", "L"
    for ma in ma_values:
        if ma >= thresh_high:
            labels.append("H")
        elif ma >= thresh_med:
            labels.append("M")
        else:
            labels.append("L")

    # 合并连续的 H/M 段为 Phase, L 段作为分界
    # 允许单个 L 夹在 H/M 之间时不分段 (短暂波动)
    phases = []
    current_cycles_buf = []

    for i in range(n):
        if labels[i] in ("H", "M"):
            current_cycles_buf.append(active_cycles[i])
        else:
            # L 段: 检查是否为短暂波动 (前后都是 H/M)
            look_ahead = min(i + 3, n)
            future_active = any(labels[j] in ("H", "M") for j in range(i + 1, look_ahead))

            if future_active and current_cycles_buf:
                # 短暂低谷, 继续当前 Phase
                current_cycles_buf.append(active_cycles[i])
            else:
                # 真正的分界
                if current_cycles_buf:
                    phases.append(_make_phase(current_cycles_buf))
                    current_cycles_buf = []

    if current_cycles_buf:
        phases.append(_make_phase(current_cycles_buf))

    return phases


def _make_phase(cycles: list[CycleStat]) -> Phase:
    total = sum(c.toggle_sum for c in cycles)
    peak = max(c.toggle_sum for c in cycles)
    return Phase(
        start_cycle=cycles[0].index,
        end_cycle=cycles[-1].index,
        cycles=list(cycles),
        total_toggles=total,
        avg_toggles=total / len(cycles),
        peak_toggles=peak,
    )


def select_windows(phases: list[Phase], total_time_ns: float,
                   budget_ratio: float = 0.1,
                   clock_ns: float = 50.0,
                   depletion_ratio: float = 0.7,
                   min_phase_cycles: int = 3) -> list[Window]:
    """Phase-aware 多窗口选择.

    Args:
        phases: 检测到的活跃相位列表
        total_time_ns: 仿真总时长 (ns)
        budget_ratio: 预算比例 (默认 0.1 = 1/10)
        clock_ns: 时钟周期 (ns)
        depletion_ratio: 采样位置比例 (默认 0.7 = Phase 70% 处)
        min_phase_cycles: 最少活跃周期数才纳入选择

    Returns:
        选中的窗口列表
    """
    total_budget_ns = total_time_ns * budget_ratio

    # 过滤太小的 Phase
    major_phases = [p for p in phases if p.n_active >= min_phase_cycles]

    if not major_phases:
        # fallback: 取所有 Phase
        major_phases = phases

    # 按活跃周期数加权分配预算
    total_active = sum(p.n_active for p in major_phases)

    windows = []
    used_budget = 0.0

    for pid, phase in enumerate(major_phases):
        # 按比例分配
        alloc_ns = total_budget_ns * phase.n_active / total_active

        # 对齐到时钟周期 (向上取整到偶数个周期，含时钟+数据)
        alloc_cycles = max(2, int(alloc_ns / clock_ns / 2) * 2)
        alloc_ns = alloc_cycles * clock_ns

        # 采样中心: Phase 起点 + depletion_ratio × Phase 持续时间
        sample_center = phase.start_ns + depletion_ratio * phase.duration_ns

        # 窗口边界
        win_start = sample_center - alloc_ns / 2
        win_end = sample_center + alloc_ns / 2

        # 边界裁剪
        if win_start < phase.start_ns - clock_ns:
            win_start = phase.start_ns - clock_ns
            win_end = win_start + alloc_ns
        if win_end > phase.end_ns + clock_ns:
            win_end = phase.end_ns + clock_ns
            win_start = win_end - alloc_ns

        win_start = max(0, win_start)
        win_end = min(total_time_ns, win_end)

        # 统计窗口内的实际 toggle
        toggle_sum = sum(c.toggle_sum for c in phase.cycles
                         if win_start <= c.time_ns <= win_end)

        windows.append(Window(
            start_ns=win_start,
            end_ns=win_end,
            phase_id=pid,
            toggle_sum=toggle_sum,
            reason=(f"Phase {pid+1}: {phase.start_ns:.0f}~{phase.end_ns:.0f}ns, "
                    f"n={phase.n_active}, avg={phase.avg_toggles:.0f}, "
                    f"peak={phase.peak_toggles}"),
        ))
        used_budget += (win_end - win_start)

    return windows


# ── Visualization ────────────────────────────────────────────────────

def generate_html(cycle_stats: list[CycleStat], phases: list[Phase],
                  windows: list[Window], output_path: str,
                  clock_ns: float = 50.0):
    """生成 Plotly HTML 可视化."""
    # 只取活跃周期 (非纯时钟)
    active = [c for c in cycle_stats if c.toggle_sum > 200]
    times = [c.time_ns for c in active]
    toggles = [c.toggle_sum for c in active]

    # Phase 颜色区域
    phase_shapes = []
    phase_colors = [
        "rgba(173,216,230,0.2)", "rgba(144,238,144,0.2)",
        "rgba(255,218,185,0.2)", "rgba(221,160,221,0.2)",
        "rgba(255,255,180,0.2)", "rgba(200,200,200,0.2)",
    ]
    for i, p in enumerate(phases):
        color = phase_colors[i % len(phase_colors)]
        phase_shapes.append(
            f'{{"type":"rect","xref":"x","yref":"paper",'
            f'"x0":{p.start_ns},"x1":{p.end_ns + clock_ns},'
            f'"y0":0,"y1":1,'
            f'"fillcolor":"{color}","line":{{"width":0}},'
            f'"layer":"below"}}'
        )

    # 窗口高亮区域
    win_shapes = []
    for w in windows:
        win_shapes.append(
            f'{{"type":"rect","xref":"x","yref":"paper",'
            f'"x0":{w.start_ns},"x1":{w.end_ns},'
            f'"y0":0,"y1":1,'
            f'"fillcolor":"rgba(255,0,0,0.15)","line":{{"color":"red","width":2,"dash":"dash"}},'
            f'"layer":"below"}}'
        )

    # Phase 标注
    annotations = []
    for i, p in enumerate(phases):
        mid = (p.start_ns + p.end_ns) / 2
        annotations.append(
            f'{{"x":{mid},"y":1.05,"xref":"x","yref":"paper",'
            f'"text":"Phase {i+1}<br>avg={p.avg_toggles:.0f}","showarrow":false,'
            f'"font":{{"size":10}}}}'
        )

    # Window 标注
    for w in windows:
        mid = (w.start_ns + w.end_ns) / 2
        annotations.append(
            f'{{"x":{mid},"y":-0.08,"xref":"x","yref":"paper",'
            f'"text":"Win {w.phase_id+1}<br>{w.start_ns:.0f}~{w.end_ns:.0f}ns",'
            f'"showarrow":false,"font":{{"size":9,"color":"red"}}}}'
        )

    all_shapes = phase_shapes + win_shapes

    html = f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<title>Phase-Aware Window Selection</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
</head><body>
<div id="chart" style="width:100%;height:600px;"></div>
<script>
var trace = {{
    x: {times},
    y: {toggles},
    type: 'bar',
    marker: {{color: 'steelblue'}},
    name: 'Toggle Count',
    width: {clock_ns * 0.8}
}};
var layout = {{
    title: 'Toggle Profile with Phase-Aware Window Selection',
    xaxis: {{title: 'Time (ns)'}},
    yaxis: {{title: 'Toggle Count per Clock Cycle'}},
    shapes: [{",".join(all_shapes)}],
    annotations: [{",".join(annotations)}],
    margin: {{b: 80, t: 60}}
}};
Plotly.newPlot('chart', [trace], layout);
</script>
</body></html>"""

    Path(output_path).write_text(html, encoding="utf-8")
    print(f"  HTML visualization: {output_path}")


# ── Report ───────────────────────────────────────────────────────────

def print_report(raw_data: list[tuple[float, int]],
                 cycle_stats: list[CycleStat],
                 phases: list[Phase],
                 windows: list[Window],
                 total_time_ns: float):
    """打印分析报告."""
    total_toggles = sum(t for _, t in raw_data)
    active_cycles = [c for c in cycle_stats if c.toggle_sum > 200]

    print("=" * 70)
    print("  Phase-Aware Multi-Window Worst-Case Selection")
    print("=" * 70)
    print()

    # 基本统计
    print(f"  Simulation time:  {total_time_ns:.1f} ns")
    print(f"  Total toggles:    {total_toggles:,}")
    print(f"  Active cycles:    {len(active_cycles)} / {len(cycle_stats)}")
    print()

    # Phase 信息
    print("  Detected Phases:")
    print(f"  {'#':<4} {'Range (ns)':<25} {'Cycles':>7} {'Avg':>8} "
          f"{'Peak':>8} {'Total':>10}")
    print("  " + "-" * 68)
    for i, p in enumerate(phases):
        print(f"  {i+1:<4} {p.start_ns:>8.0f} ~ {p.end_ns:<8.0f}"
              f"     {p.n_active:>5}  {p.avg_toggles:>8.0f} "
              f"{p.peak_toggles:>8} {p.total_toggles:>10,}")
    print()

    # 选中窗口
    total_win = sum(w.duration_ns for w in windows)
    total_win_toggles = sum(w.toggle_sum for w in windows)

    print("  Selected Windows:")
    print(f"  {'#':<4} {'Range (ns)':<25} {'Duration':>10} {'Toggles':>10} "
          f"{'Source'}")
    print("  " + "-" * 75)
    for i, w in enumerate(windows):
        print(f"  {i+1:<4} {w.start_ns:>8.0f} ~ {w.end_ns:<8.0f}"
              f"     {w.duration_ns:>7.0f}ns  {w.toggle_sum:>10,}  "
              f"{w.reason}")
    print()
    print(f"  Total selected:  {total_win:.0f} ns "
          f"({total_win/total_time_ns*100:.1f}% of simulation)")
    print(f"  Toggle coverage: {total_win_toggles:,} "
          f"({total_win_toggles/total_toggles*100:.1f}% of total)")
    print()
    print("=" * 70)


# ── Main ─────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(
        description="Phase-Aware Multi-Window Worst-Case Selection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--togglestats", help="Voltus togglestats 文件路径")
    src.add_argument("--jsonl", help="JSONL toggle 文件路径 (jsonl_toggle_mark.py 输出)")

    p.add_argument("--budget", type=float, default=0.1,
                   help="预算比例, 默认 0.1 (1/10)")
    p.add_argument("--clock-ns", type=float, default=50.0,
                   help="时钟周期 (ns), 默认 50")
    p.add_argument("--depletion-ratio", type=float, default=0.7,
                   help="退耦耗尽采样位置比例, 默认 0.7")
    p.add_argument("--min-phase-cycles", type=int, default=3,
                   help="Phase 最少活跃周期数, 默认 3")
    p.add_argument("--timescale-ps", type=float, default=10.0,
                   help="JSONL timescale (ps), 默认 10")
    p.add_argument("--html", default=None,
                   help="输出 HTML 可视化路径")
    p.add_argument("--json-out", default=None,
                   help="输出窗口信息为 JSON")

    args = p.parse_args()

    # ── 加载数据 ──
    if args.togglestats:
        filepath = Path(args.togglestats).resolve()
        if not filepath.exists():
            print(f"ERROR: File not found: {filepath}", file=sys.stderr)
            sys.exit(1)
        print(f"  Input: {filepath}")
        raw_data = parse_togglestats(str(filepath))
    else:
        filepath = Path(args.jsonl).resolve()
        if not filepath.exists():
            print(f"ERROR: File not found: {filepath}", file=sys.stderr)
            sys.exit(1)
        print(f"  Input: {filepath}")
        raw_data = parse_jsonl_toggles(str(filepath), args.timescale_ps)

    if not raw_data:
        print("ERROR: No data loaded", file=sys.stderr)
        sys.exit(1)

    total_time_ns = raw_data[-1][0]

    # ── 按时钟周期聚合 ──
    cycle_stats = aggregate_by_clock(raw_data, args.clock_ns)

    # ── 检测相位 ──
    phases = detect_phases(cycle_stats)

    if not phases:
        print("WARNING: No active phases detected", file=sys.stderr)
        sys.exit(1)

    # ── 选择窗口 ──
    windows = select_windows(
        phases, total_time_ns,
        budget_ratio=args.budget,
        clock_ns=args.clock_ns,
        depletion_ratio=args.depletion_ratio,
        min_phase_cycles=args.min_phase_cycles,
    )

    # ── 报告 ──
    print_report(raw_data, cycle_stats, phases, windows, total_time_ns)

    # ── 可视化 ──
    if args.html:
        generate_html(cycle_stats, phases, windows, args.html, args.clock_ns)

    # ── JSON 输出 ──
    if args.json_out:
        out = {
            "total_time_ns": total_time_ns,
            "budget_ratio": args.budget,
            "phases": [
                {"id": i + 1, "start_ns": p.start_ns, "end_ns": p.end_ns,
                 "n_active": p.n_active, "avg_toggles": round(p.avg_toggles),
                 "peak_toggles": p.peak_toggles}
                for i, p in enumerate(phases)
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
        print(f"  JSON output: {args.json_out}")


if __name__ == "__main__":
    main()
