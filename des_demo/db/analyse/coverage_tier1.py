#!/usr/bin/env python3
"""
Phase 1 覆盖率第一级指标自动计算

解析 Voltus Rail Analysis 报告，计算子集 (win1~win5) 相对全集的覆盖率指标。

指标定义:
  C1         = (Vnom - Vmin_sub) / (Vnom - Vmin_full)        从 main.rpt
  C_peak     = Ipeak_sub / Ipeak_full                        从 main.rpt 或 dynpwr.rpt
  C_layer(l) = IRdrop_sub(l) / IRdrop_full(l)  per layer     从 layerbased_ir.rpt
  C_layer_avg, C_layer_min = 各层 C_layer 的均值/最小值
  C_violation = 违例一致性 (PASS/FAIL)

用法:
  python analyse/coverage_tier1.py [--db-root <path>]
"""

import re
import csv
import os
import sys
from pathlib import Path
from itertools import combinations
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------
@dataclass
class MainRptData:
    vnom: float = 0.0
    vmin: float = 0.0
    vavg: float = 0.0
    vmax: float = 0.0
    threshold: float = 0.0
    ipeak_specified: float = 0.0
    ipeak_loaded: float = 0.0
    num_violations: int = 0


@dataclass
class LayerIR:
    layer: str = ""
    ir_drop: float = 0.0
    v_high: float = 0.0
    v_low: float = 0.0
    elements: int = 0


@dataclass
class DynPwrData:
    ipeak_loaded: float = 0.0
    ipeak_used: float = 0.0


@dataclass
class WindowData:
    name: str = ""
    main: MainRptData | None = None
    layers: list[LayerIR] = field(default_factory=list)
    dynpwr: DynPwrData | None = None


# ---------------------------------------------------------------------------
# 解析函数
# ---------------------------------------------------------------------------
def parse_main_rpt(filepath: Path) -> MainRptData | None:
    """解析 VDD.main.rpt"""
    if not filepath.exists():
        return None
    text = filepath.read_text(encoding="utf-8", errors="replace")
    data = MainRptData()

    # Voltage: 0.7
    m = re.search(r"^Voltage:\s+([\d.]+)", text, re.MULTILINE)
    if m:
        data.vnom = float(m.group(1))

    # Threshold: 0.651
    m = re.search(r"^Threshold:\s+([\d.]+)", text, re.MULTILINE)
    if m:
        data.threshold = float(m.group(1))

    # Minimum, Average, Maximum IR drop: 0.667V  0.682V  0.700V
    m = re.search(
        r"Minimum,\s*Average,\s*Maximum\s+IR\s+drop:\s+([\d.]+)V\s+([\d.]+)V\s+([\d.]+)V",
        text,
    )
    if m:
        data.vmin = float(m.group(1))
        data.vavg = float(m.group(2))
        data.vmax = float(m.group(3))

    # Peak Dynamic Current Specified: 16.485mA
    m = re.search(r"Peak Dynamic Current Specified:\s+([\d.]+)mA", text)
    if m:
        data.ipeak_specified = float(m.group(1))

    # Peak Dynamic Current Loaded: 16.485mA
    m = re.search(r"Peak Dynamic Current Loaded:\s+([\d.]+)mA", text)
    if m:
        data.ipeak_loaded = float(m.group(1))

    # Number of Violations: 0
    m = re.search(r"Number of Violations:\s+(\d+)", text)
    if m:
        data.num_violations = int(m.group(1))

    return data


def parse_layerbased_ir(filepath: Path) -> list[LayerIR]:
    """解析 VDD.layerbased_ir.rpt (pipe 分隔表格)"""
    if not filepath.exists():
        return []
    layers = []
    for line in filepath.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("Layer") or line.startswith("---"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 4:
            continue
        layer_name = parts[0]
        try:
            ir_drop = float(parts[1])
        except ValueError:
            continue
        # parse "0.7      -> 0.67"
        range_match = re.match(r"([\d.]+)\s*->\s*([\d.]+)", parts[2])
        v_high, v_low = 0.0, 0.0
        if range_match:
            v_high = float(range_match.group(1))
            v_low = float(range_match.group(2))
        elements = int(parts[3]) if len(parts) > 3 else 0
        layers.append(LayerIR(layer_name, ir_drop, v_high, v_low, elements))
    return layers


def parse_dynpwr(filepath: Path) -> DynPwrData | None:
    """解析 VDD_dynpwr.rpt"""
    if not filepath.exists():
        return None
    text = filepath.read_text(encoding="utf-8", errors="replace")
    data = DynPwrData()
    m = re.search(r"peak of dynamic current loaded\s*=\s*([\d.eE+-]+)", text)
    if m:
        data.ipeak_loaded = float(m.group(1))
    m = re.search(r"peak of dynamic current used\s*=\s*([\d.eE+-]+)", text)
    if m:
        data.ipeak_used = float(m.group(1))
    return data


# ---------------------------------------------------------------------------
# 数据加载
# ---------------------------------------------------------------------------
# 路径映射: (目录前缀, 内部路径)
FULL_SET_PATH = ("rail_power_v15", "PD_25C_dynamic_1/Reports/VDD")
WIN_PATHS = {
    "win1": ("rail_power_v15_win1/rail_power_v15_win1", "PD_25C_dynamic_2/Reports/VDD"),
    "win2": ("rail_power_v15_win2/rail_power_v15_win2", "PD_25C_dynamic_2/Reports/VDD"),
    "win3": ("rail_power_v15_win3/rail_power_v15_win3", "PD_25C_dynamic_2/Reports/VDD"),
    "win4": ("rail_power_v15_win4/rail_power_v15_win4", "PD_25C_dynamic_2/Reports/VDD"),
    "win5": ("rail_power_v15_win5/rail_power_v15_win5", "PD_25C_dynamic_2/Reports/VDD"),
}


def load_window(db_root: Path, prefix: str, subpath: str, name: str) -> WindowData:
    rpt_dir = db_root / prefix / subpath
    wd = WindowData(name=name)
    wd.main = parse_main_rpt(rpt_dir / "VDD.main.rpt")
    wd.layers = parse_layerbased_ir(rpt_dir / "VDD.layerbased_ir.rpt")
    wd.dynpwr = parse_dynpwr(rpt_dir / "VDD_dynpwr.rpt")
    return wd


def get_ipeak(wd: WindowData) -> float | None:
    """从 main.rpt 或 dynpwr.rpt 获取 Ipeak (mA)"""
    if wd.main and wd.main.ipeak_loaded > 0:
        return wd.main.ipeak_loaded
    if wd.dynpwr and wd.dynpwr.ipeak_loaded > 0:
        # dynpwr 单位是 A, 转为 mA
        return wd.dynpwr.ipeak_loaded * 1000
    return None


# ---------------------------------------------------------------------------
# 覆盖率计算
# ---------------------------------------------------------------------------
@dataclass
class CoverageResult:
    window: str = ""
    c1: float | None = None          # IR drop coverage
    c_peak: float | None = None      # peak current coverage
    c_layer: dict[str, float] = field(default_factory=dict)  # per-layer
    c_layer_avg: float | None = None
    c_layer_min: float | None = None
    c_violation: str = "N/A"         # PASS / FAIL / N/A


def compute_coverage(full: WindowData, sub: WindowData) -> CoverageResult:
    res = CoverageResult(window=sub.name)

    # --- C1: (Vnom - Vmin_sub) / (Vnom - Vmin_full) ---
    if full.main and sub.main and full.main.vnom > 0:
        denom = full.main.vnom - full.main.vmin
        if denom > 0:
            numer = full.main.vnom - sub.main.vmin
            res.c1 = numer / denom

    # --- C_peak ---
    ipeak_full = get_ipeak(full)
    ipeak_sub = get_ipeak(sub)
    if ipeak_full and ipeak_sub and ipeak_full > 0:
        res.c_peak = ipeak_sub / ipeak_full

    # --- C_layer ---
    if full.layers and sub.layers:
        full_map = {l.layer: l.ir_drop for l in full.layers}
        for sl in sub.layers:
            if sl.layer in full_map and full_map[sl.layer] > 0:
                res.c_layer[sl.layer] = sl.ir_drop / full_map[sl.layer]
        if res.c_layer:
            vals = list(res.c_layer.values())
            res.c_layer_avg = sum(vals) / len(vals)
            res.c_layer_min = min(vals)

    # --- C_violation ---
    if full.main and sub.main:
        full_v = full.main.num_violations
        sub_v = sub.main.num_violations
        # PASS if violations match (both 0 or both >0)
        if (full_v == 0 and sub_v == 0) or (full_v > 0 and sub_v > 0):
            res.c_violation = "PASS"
        else:
            res.c_violation = "FAIL"

    return res


# ---------------------------------------------------------------------------
# 多窗口组合覆盖率
# ---------------------------------------------------------------------------
@dataclass
class CombinationResult:
    windows: str = ""          # e.g. "win1+win2"
    c1: float | None = None
    c_peak: float | None = None
    c_layer_avg: float | None = None
    c_layer_min: float | None = None
    c_violation: str = "N/A"


def compute_combination(full: WindowData, subs: list[WindowData]) -> CombinationResult:
    """多窗口取 worst-case: min voltage -> max IR drop, max peak current"""
    names = "+".join(s.name for s in subs)
    res = CombinationResult(windows=names)

    # --- C1: take worst (lowest) Vmin across windows ---
    vmins = []
    for s in subs:
        if s.main and s.main.vmin > 0:
            vmins.append(s.main.vmin)
    if vmins and full.main and full.main.vnom > 0:
        denom = full.main.vnom - full.main.vmin
        if denom > 0:
            worst_vmin = min(vmins)
            res.c1 = (full.main.vnom - worst_vmin) / denom

    # --- C_peak: take max Ipeak across windows ---
    ipeaks = []
    for s in subs:
        ip = get_ipeak(s)
        if ip is not None:
            ipeaks.append(ip)
    ipeak_full = get_ipeak(full)
    if ipeaks and ipeak_full and ipeak_full > 0:
        res.c_peak = max(ipeaks) / ipeak_full

    # --- C_layer: take max IR drop per layer across windows ---
    if full.layers:
        full_map = {l.layer: l.ir_drop for l in full.layers}
        combined_layer = {}
        for s in subs:
            for sl in s.layers:
                if sl.layer in full_map:
                    if sl.layer not in combined_layer or sl.ir_drop > combined_layer[sl.layer]:
                        combined_layer[sl.layer] = sl.ir_drop
        c_layers = {}
        for layer, ir in combined_layer.items():
            if full_map.get(layer, 0) > 0:
                c_layers[layer] = ir / full_map[layer]
        if c_layers:
            vals = list(c_layers.values())
            res.c_layer_avg = sum(vals) / len(vals)
            res.c_layer_min = min(vals)

    # --- C_violation: PASS if any window captures violations ---
    violations_full = full.main.num_violations if full.main else None
    violations_subs = []
    for s in subs:
        if s.main:
            violations_subs.append(s.main.num_violations)
    if violations_full is not None and violations_subs:
        if violations_full == 0 and all(v == 0 for v in violations_subs):
            res.c_violation = "PASS"
        elif violations_full > 0 and any(v > 0 for v in violations_subs):
            res.c_violation = "PASS"
        else:
            res.c_violation = "FAIL"

    return res


# ---------------------------------------------------------------------------
# 输出
# ---------------------------------------------------------------------------
def fmt_pct(val: float | None) -> str:
    if val is None:
        return "N/A"
    return f"{val * 100:.1f}%"


def write_single_csv(results: list[CoverageResult], filepath: Path):
    """写单窗口覆盖率 CSV"""
    # 收集所有层名
    all_layers = []
    for r in results:
        for l in r.c_layer:
            if l not in all_layers:
                all_layers.append(l)

    headers = ["window", "C1", "C_peak", "C_layer_avg", "C_layer_min", "C_violation"]
    headers += [f"C_layer_{l}" for l in all_layers]

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
        for r in results:
            row = [
                r.window,
                fmt_pct(r.c1),
                fmt_pct(r.c_peak),
                fmt_pct(r.c_layer_avg),
                fmt_pct(r.c_layer_min),
                r.c_violation,
            ]
            for l in all_layers:
                row.append(fmt_pct(r.c_layer.get(l)))
            w.writerow(row)


def write_combination_csv(results: list[CombinationResult], filepath: Path):
    headers = ["windows", "C1", "C_peak", "C_layer_avg", "C_layer_min", "C_violation"]
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
        for r in results:
            w.writerow([
                r.windows,
                fmt_pct(r.c1),
                fmt_pct(r.c_peak),
                fmt_pct(r.c_layer_avg),
                fmt_pct(r.c_layer_min),
                r.c_violation,
            ])


def write_markdown_report(
    single: list[CoverageResult],
    combos: list[CombinationResult],
    full: WindowData,
    windows: list[WindowData],
    filepath: Path,
):
    lines = []
    lines.append("# IR Drop Coverage Tier-1 Report\n")

    # --- 全集参考值 ---
    lines.append("## Reference (Full-set)\n")
    if full.main:
        lines.append(f"- **Vnom**: {full.main.vnom} V")
        lines.append(f"- **Vmin**: {full.main.vmin} V")
        lines.append(f"- **IR drop (Vnom-Vmin)**: {full.main.vnom - full.main.vmin:.4f} V")
        lines.append(f"- **Ipeak**: {full.main.ipeak_loaded} mA")
        lines.append(f"- **Violations**: {full.main.num_violations}")
        lines.append(f"- **Threshold**: {full.main.threshold} V")
    lines.append("")

    if full.layers:
        lines.append("### Layer-based IR Drop (Full-set)\n")
        lines.append("| Layer | IR Drop (V) | Range |")
        lines.append("|-------|-------------|-------|")
        for l in full.layers:
            lines.append(f"| {l.layer} | {l.ir_drop} | {l.v_high} -> {l.v_low} |")
        lines.append("")

    # --- 各窗口数据摘要 ---
    lines.append("## Window Data Summary\n")
    lines.append("| Window | Vmin | Ipeak (mA) | Violations | Data |")
    lines.append("|--------|------|------------|------------|------|")
    for w in windows:
        vmin = f"{w.main.vmin}" if w.main else "N/A"
        ipeak = get_ipeak(w)
        ipeak_s = f"{ipeak:.3f}" if ipeak else "N/A"
        viol = str(w.main.num_violations) if w.main else "N/A"
        sources = []
        if w.main:
            sources.append("main")
        if w.layers:
            sources.append("layer")
        if w.dynpwr:
            sources.append("dynpwr")
        lines.append(f"| {w.name} | {vmin} | {ipeak_s} | {viol} | {', '.join(sources) or 'none'} |")
    lines.append("")

    # --- 单窗口覆盖率 ---
    lines.append("## Single Window Coverage\n")

    # 收集所有层名
    all_layers = []
    for r in single:
        for l in r.c_layer:
            if l not in all_layers:
                all_layers.append(l)

    hdr = "| Window | C1 | C_peak | C_layer_avg | C_layer_min | C_violation |"
    sep = "|--------|------|--------|-------------|-------------|-------------|"
    for l in all_layers:
        hdr += f" {l} |"
        sep += "------|"
    lines.append(hdr)
    lines.append(sep)

    for r in single:
        row = f"| {r.window} | {fmt_pct(r.c1)} | {fmt_pct(r.c_peak)} | {fmt_pct(r.c_layer_avg)} | {fmt_pct(r.c_layer_min)} | {r.c_violation} |"
        for l in all_layers:
            row += f" {fmt_pct(r.c_layer.get(l))} |"
        lines.append(row)
    lines.append("")

    # --- 多窗口组合覆盖率 ---
    if combos:
        lines.append("## Multi-Window Combination Coverage\n")
        lines.append("| Windows | C1 | C_peak | C_layer_avg | C_layer_min | C_violation |")
        lines.append("|---------|------|--------|-------------|-------------|-------------|")
        for r in combos:
            lines.append(
                f"| {r.windows} | {fmt_pct(r.c1)} | {fmt_pct(r.c_peak)} "
                f"| {fmt_pct(r.c_layer_avg)} | {fmt_pct(r.c_layer_min)} | {r.c_violation} |"
            )
        lines.append("")

    filepath.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# 主函数
# ---------------------------------------------------------------------------
def main():
    # 确定 db_root
    script_dir = Path(__file__).resolve().parent  # analyse/
    db_root = script_dir.parent                   # db/

    # 支持命令行覆盖
    if "--db-root" in sys.argv:
        idx = sys.argv.index("--db-root")
        if idx + 1 < len(sys.argv):
            db_root = Path(sys.argv[idx + 1])

    results_dir = script_dir / "results"
    results_dir.mkdir(exist_ok=True)

    print(f"DB root: {db_root}")

    # 加载全集
    full = load_window(db_root, *FULL_SET_PATH, "full")
    if not full.main and not full.layers:
        print("ERROR: Full-set reports not found!")
        sys.exit(1)
    print(f"Full-set loaded: Vmin={full.main.vmin if full.main else 'N/A'}, "
          f"Ipeak={get_ipeak(full)} mA")

    # 加载各窗口
    windows = []
    for name, (prefix, subpath) in WIN_PATHS.items():
        wd = load_window(db_root, prefix, subpath, name)
        has_data = wd.main or wd.layers or wd.dynpwr
        if has_data:
            windows.append(wd)
            sources = []
            if wd.main:
                sources.append("main")
            if wd.layers:
                sources.append(f"layer({len(wd.layers)})")
            if wd.dynpwr:
                sources.append("dynpwr")
            print(f"  {name}: loaded [{', '.join(sources)}]")
        else:
            print(f"  {name}: no reports found, skipping")

    if not windows:
        print("ERROR: No window data found!")
        sys.exit(1)

    # --- 单窗口覆盖率 ---
    single_results = []
    print("\n=== Single Window Coverage ===")
    print(f"{'Window':<8} {'C1':>8} {'C_peak':>8} {'C_layer_avg':>12} {'C_layer_min':>12} {'Violation':>10}")
    print("-" * 62)
    for w in windows:
        cov = compute_coverage(full, w)
        single_results.append(cov)
        print(f"{cov.window:<8} {fmt_pct(cov.c1):>8} {fmt_pct(cov.c_peak):>8} "
              f"{fmt_pct(cov.c_layer_avg):>12} {fmt_pct(cov.c_layer_min):>12} {cov.c_violation:>10}")

    # --- 多窗口组合覆盖率 ---
    combo_results = []
    if len(windows) >= 2:
        print("\n=== Multi-Window Combinations ===")
        print(f"{'Windows':<20} {'C1':>8} {'C_peak':>8} {'C_layer_avg':>12} {'C_layer_min':>12} {'Violation':>10}")
        print("-" * 74)
        for r in range(2, len(windows) + 1):
            for combo in combinations(windows, r):
                cr = compute_combination(full, list(combo))
                combo_results.append(cr)
                print(f"{cr.windows:<20} {fmt_pct(cr.c1):>8} {fmt_pct(cr.c_peak):>8} "
                      f"{fmt_pct(cr.c_layer_avg):>12} {fmt_pct(cr.c_layer_min):>12} {cr.c_violation:>10}")

    # --- 写出文件 ---
    csv1 = results_dir / "coverage_tier1.csv"
    csv2 = results_dir / "coverage_combination.csv"
    md_path = results_dir / "coverage_report.md"

    write_single_csv(single_results, csv1)
    print(f"\nSaved: {csv1}")

    if combo_results:
        write_combination_csv(combo_results, csv2)
        print(f"Saved: {csv2}")

    write_markdown_report(single_results, combo_results, full, windows, md_path)
    print(f"Saved: {md_path}")


if __name__ == "__main__":
    main()
