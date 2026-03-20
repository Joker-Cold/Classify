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


def parse_totalcurrent(filepath: Path) -> float:
    """解析 VDD.avg*.totalcurrent, 返回 Ipeak (A). 找不到返回 0."""
    if not filepath.exists():
        return 0.0
    peak = 0.0
    for line in filepath.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if len(parts) >= 3:
            try:
                val = float(parts[2])
                if val > peak:
                    peak = val
            except ValueError:
                continue
    return peak


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
# v15 路径映射: (目录前缀, 内部路径)
FULL_SET_PATH_V15 = ("rail_power_v15", "PD_25C_dynamic_1/Reports/VDD")
WIN_PATHS_V15 = {
    "win1": ("rail_power_v15_win1/rail_power_v15_win1", "PD_25C_dynamic_2/Reports/VDD"),
    "win2": ("rail_power_v15_win2/rail_power_v15_win2", "PD_25C_dynamic_2/Reports/VDD"),
    "win3": ("rail_power_v15_win3/rail_power_v15_win3", "PD_25C_dynamic_2/Reports/VDD"),
    "win4": ("rail_power_v15_win4/rail_power_v15_win4", "PD_25C_dynamic_2/Reports/VDD"),
    "win5": ("rail_power_v15_win5/rail_power_v15_win5", "PD_25C_dynamic_2/Reports/VDD"),
}

# v20 路径映射: sim_data/ 下的扁平结构
# 报告文件名带后缀: VDD.main_{tag}.rpt
FULL_SET_PATH_V20 = ("sim_data/rail_v20_full", "VDD")
WIN_PATHS_V20 = {
    "eq_win1": ("sim_data/rail_v20_win1", "VDD"),
    "eq_win2": ("sim_data/rail_v20_win2", "VDD"),
    "eq_win3": ("sim_data/rail_v20_win3", "VDD"),
    "eq_win4": ("sim_data/rail_v20_win4", "VDD"),
    "eq_win5": ("sim_data/rail_v20_win5", "VDD"),
    "algo_win1": ("sim_data/algo_grid_win1/rail/Reports", "VDD"),
    "algo_win2": ("sim_data/algo_grid_win2/rail/Reports", "VDD"),
}

# v20 power 路径映射: (目录前缀, totalcurrent 文件名)
V20_POWER_PATHS = {
    "full":      ("sim_data/power_v20_full",          "VDD.avg_full.totalcurrent"),
    "eq_win1":   ("sim_data/power_v20_win1",          "VDD.avg_win1.totalcurrent"),
    "eq_win2":   ("sim_data/power_v20_win2",          "VDD.avg_win2.totalcurrent"),
    "eq_win3":   ("sim_data/power_v20_win3",          "VDD.avg_win3.totalcurrent"),
    "eq_win4":   ("sim_data/power_v20_win4",          "VDD.avg_win4.totalcurrent"),
    "eq_win5":   ("sim_data/power_v20_win5",          "VDD.avg_win5.totalcurrent"),
    "algo_win1": ("sim_data/algo_grid_win1/power",    "VDD.avg.totalcurrent"),
    "algo_win2": ("sim_data/algo_grid_win2/power",    "VDD.avg.totalcurrent"),
}

# v20 文件名后缀映射 (tag 用于匹配 VDD.main_{tag}.rpt)
V20_FILE_TAGS = {
    "full": "full",
    "eq_win1": "win1", "eq_win2": "win2", "eq_win3": "win3",
    "eq_win4": "win4", "eq_win5": "win5",
    "algo_win1": "", "algo_win2": "",  # algo 窗口无后缀
}


def _find_rpt(rpt_dir: Path, base: str, tag: str) -> Path:
    """查找报告文件，尝试带后缀和不带后缀两种命名"""
    # 优先带后缀: VDD.main_full.rpt
    if tag:
        suffixed = rpt_dir / f"{base}_{tag}.rpt"
        if suffixed.exists():
            return suffixed
    # 不带后缀: VDD.main.rpt
    plain = rpt_dir / f"{base}.rpt"
    return plain


def load_window(db_root: Path, prefix: str, subpath: str, name: str,
                file_tag: str = "") -> WindowData:
    rpt_dir = db_root / prefix / subpath
    wd = WindowData(name=name)
    wd.main = parse_main_rpt(_find_rpt(rpt_dir, "VDD.main", file_tag))
    wd.layers = parse_layerbased_ir(_find_rpt(rpt_dir, "VDD.layerbased_ir", file_tag))
    wd.dynpwr = parse_dynpwr(_find_rpt(rpt_dir, "VDD_dynpwr", file_tag))
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
    c_margin: float | None = None    # margin(sub) / margin(full)
    c_overall: float | None = None   # min(C1, C_layer_min, C_margin)


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

    # --- C_margin: margin(sub) / margin(full) ---
    if full.main and sub.main and full.main.threshold > 0:
        margin_full = full.main.vmin - full.main.threshold
        margin_sub = sub.main.vmin - sub.main.threshold
        if margin_full != 0:
            res.c_margin = margin_sub / margin_full

    # --- C_overall: min of available metrics ---
    metrics = [v for v in [res.c1, res.c_layer_min, res.c_margin] if v is not None]
    if metrics:
        res.c_overall = min(metrics)

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
    c_margin: float | None = None
    c_overall: float | None = None


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

    # --- C_margin: use worst (lowest) Vmin across windows ---
    if full.main and full.main.threshold > 0 and vmins:
        margin_full = full.main.vmin - full.main.threshold
        worst_vmin_margin = min(vmins)
        margin_sub = worst_vmin_margin - full.main.threshold
        if margin_full != 0:
            res.c_margin = margin_sub / margin_full

    # --- C_overall ---
    metrics = [v for v in [res.c1, res.c_layer_min, res.c_margin] if v is not None]
    if metrics:
        res.c_overall = min(metrics)

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

    headers = ["window", "C1", "C_peak", "C_layer_avg", "C_layer_min",
               "C_margin", "C_overall", "C_violation"]
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
                fmt_pct(r.c_margin),
                fmt_pct(r.c_overall),
                r.c_violation,
            ]
            for l in all_layers:
                row.append(fmt_pct(r.c_layer.get(l)))
            w.writerow(row)


def write_combination_csv(results: list[CombinationResult], filepath: Path):
    headers = ["windows", "C1", "C_peak", "C_layer_avg", "C_layer_min",
               "C_margin", "C_overall", "C_violation"]
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
                fmt_pct(r.c_margin),
                fmt_pct(r.c_overall),
                r.c_violation,
            ])


def _verdict(c_overall: float | None) -> str:
    """判定: >=90% PASS, 80~90% MARGINAL, <80% FAIL"""
    if c_overall is None:
        return "N/A"
    if c_overall >= 0.9:
        return "PASS"
    if c_overall >= 0.8:
        return "MARGINAL"
    return "FAIL"


def write_tradeoff_csv(
    single: list[CoverageResult],
    combos: list[CombinationResult],
    durations: dict[str, int],
    full_duration: int,
    filepath: Path,
):
    """写 trade-off CSV: 压缩率 vs 覆盖率"""
    rows = []
    # 单窗口
    for r in single:
        dur = durations.get(r.window, 0)
        if dur > 0:
            ratio = dur / full_duration
            rows.append((r.window, dur, ratio, r.c1, r.c_layer_min, r.c_margin, r.c_overall))
    # 组合
    for r in combos:
        win_names = r.windows.split("+")
        dur = sum(durations.get(n, 0) for n in win_names)
        if dur > 0:
            ratio = dur / full_duration
            rows.append((r.windows, dur, ratio, r.c1, r.c_layer_min, r.c_margin, r.c_overall))
    # 按压缩率排序
    rows.sort(key=lambda x: x[2])

    headers = ["windows", "duration_ns", "compression_ratio",
               "C1", "C_layer_min", "C_margin", "C_overall"]
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
        for name, dur, ratio, c1, clm, cm, co in rows:
            w.writerow([name, dur, f"{ratio*100:.1f}%",
                        fmt_pct(c1), fmt_pct(clm), fmt_pct(cm), fmt_pct(co)])


def write_markdown_report(
    single: list[CoverageResult],
    combos: list[CombinationResult],
    full: WindowData,
    windows: list[WindowData],
    filepath: Path,
    version: str = "v15",
    window_descs: dict[str, str] | None = None,
    durations: dict[str, int] | None = None,
    full_duration: int = 0,
):
    lines = []
    lines.append(f"# IR Drop Coverage Report ({version})\n")

    # --- 全集参考值 ---
    lines.append("## Reference (Full VCD)\n")
    if full.main:
        ir_drop = full.main.vnom - full.main.vmin
        lines.append(f"- **Vnom**: {full.main.vnom} V")
        lines.append(f"- **Vmin**: {full.main.vmin} V")
        lines.append(f"- **Worst IR drop**: {ir_drop:.4f} V ({ir_drop*1000:.1f} mV)")
        ipeak = get_ipeak(full)
        if ipeak and ipeak > 0:
            lines.append(f"- **Ipeak**: {ipeak:.3f} mA")
        lines.append(f"- **Violations**: {full.main.num_violations}")
        lines.append(f"- **Threshold**: {full.main.threshold} V")
    lines.append("")

    if full.layers:
        lines.append("### Layer-based IR Drop (Full VCD)\n")
        lines.append("| Layer | IR Drop (V) | Range |")
        lines.append("|-------|-------------|-------|")
        for l in full.layers:
            lines.append(f"| {l.layer} | {l.ir_drop} | {l.v_high} -> {l.v_low} |")
        lines.append("")

    # --- 窗口说明 ---
    if window_descs:
        lines.append("## Window Definitions\n")
        lines.append("| Window | Description |")
        lines.append("|--------|-------------|")
        for wname, desc in window_descs.items():
            lines.append(f"| {wname} | {desc} |")
        lines.append("")

    # --- 各窗口数据摘要 ---
    lines.append("## Window Data Summary\n")
    lines.append("| Window | Vmin (V) | IR Drop (mV) | Violations | Data |")
    lines.append("|--------|----------|--------------|------------|------|")
    for w in windows:
        if w.main:
            vmin = f"{w.main.vmin}"
            ir_mv = f"{(w.main.vnom - w.main.vmin)*1000:.1f}"
        else:
            vmin = "N/A"
            ir_mv = "N/A"
        viol = str(w.main.num_violations) if w.main else "N/A"
        sources = []
        if w.main:
            sources.append("main")
        if w.layers:
            sources.append("layer")
        if w.dynpwr:
            sources.append("dynpwr")
        lines.append(f"| {w.name} | {vmin} | {ir_mv} | {viol} | {', '.join(sources) or 'none'} |")
    lines.append("")

    # --- 单窗口覆盖率 ---
    lines.append("## Single Window Coverage\n")

    # 收集所有层名
    all_layers = []
    for r in single:
        for l in r.c_layer:
            if l not in all_layers:
                all_layers.append(l)

    hdr = "| Window | C1 | C_layer_avg | C_layer_min | C_margin | C_overall | C_violation |"
    sep = "|--------|------|-------------|-------------|----------|-----------|-------------|"
    for l in all_layers:
        hdr += f" {l} |"
        sep += "------|"
    lines.append(hdr)
    lines.append(sep)

    for r in single:
        row = (f"| {r.window} | {fmt_pct(r.c1)} | {fmt_pct(r.c_layer_avg)} "
               f"| {fmt_pct(r.c_layer_min)} | {fmt_pct(r.c_margin)} "
               f"| {fmt_pct(r.c_overall)} | {r.c_violation} |")
        for l in all_layers:
            row += f" {fmt_pct(r.c_layer.get(l))} |"
        lines.append(row)
    lines.append("")

    # --- 多窗口组合覆盖率 ---
    if combos:
        lines.append("## Multi-Window Combination Coverage\n")
        lines.append("| Windows | C1 | C_layer_avg | C_layer_min | C_margin | C_overall | C_violation |")
        lines.append("|---------|------|-------------|-------------|----------|-----------|-------------|")
        for r in combos:
            lines.append(
                f"| {r.windows} | {fmt_pct(r.c1)} "
                f"| {fmt_pct(r.c_layer_avg)} | {fmt_pct(r.c_layer_min)} "
                f"| {fmt_pct(r.c_margin)} | {fmt_pct(r.c_overall)} | {r.c_violation} |"
            )
        lines.append("")

    # --- Trade-off: Coverage vs Compression ---
    if durations and full_duration > 0:
        lines.append("## Trade-off: Coverage vs Compression\n")
        # 收集数据点
        tradeoff_rows = []
        for r in single:
            dur = durations.get(r.window, 0)
            if dur > 0:
                ratio = dur / full_duration * 100
                tradeoff_rows.append((r.window, dur, ratio, r.c_overall))
        for r in combos:
            win_names = r.windows.split("+")
            dur = sum(durations.get(n, 0) for n in win_names)
            if dur > 0:
                ratio = dur / full_duration * 100
                tradeoff_rows.append((r.windows, dur, ratio, r.c_overall))
        tradeoff_rows.sort(key=lambda x: x[2])

        lines.append("| Windows | Duration (ns) | Compression | C_overall | Verdict |")
        lines.append("|---------|--------------|-------------|-----------|---------|")
        for name, dur, ratio, co in tradeoff_rows:
            lines.append(
                f"| {name} | {dur} | {ratio:.1f}% | {fmt_pct(co)} | {_verdict(co)} |"
            )
        lines.append("")

    # --- 判定结果 ---
    lines.append("## Verdict Summary\n")
    lines.append("Criteria: C_overall >= 90% → **PASS**, 80~90% → **MARGINAL**, <80% → **FAIL**\n")
    lines.append("### Single Windows\n")
    for r in single:
        v = _verdict(r.c_overall)
        lines.append(f"- **{r.window}**: C_overall={fmt_pct(r.c_overall)} → **{v}**")
    lines.append("")
    if combos:
        lines.append("### Combinations\n")
        for r in combos:
            v = _verdict(r.c_overall)
            lines.append(f"- **{r.windows}**: C_overall={fmt_pct(r.c_overall)} → **{v}**")
        lines.append("")

    filepath.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# 主函数
# ---------------------------------------------------------------------------
def _run_analysis(db_root: Path, results_dir: Path, version: str,
                  full_path: tuple, win_paths: dict, file_tags: dict,
                  window_descs: dict[str, str],
                  combo_groups: list[list[str]] | None = None,
                  durations: dict[str, int] | None = None,
                  full_duration: int = 0,
                  power_paths: dict[str, tuple[str, str]] | None = None):
    """通用分析流程: 加载数据 → 计算覆盖率 → 输出"""
    suffix = f"_{version}" if version != "v15" else ""

    # 加载全集
    full_prefix, full_sub = full_path
    full_tag = file_tags.get("full", "")
    full = load_window(db_root, full_prefix, full_sub, "full", file_tag=full_tag)
    if not full.main and not full.layers:
        print(f"ERROR: Full-set reports not found for {version}!")
        return
    print(f"[{version}] Full-set: Vmin={full.main.vmin if full.main else 'N/A'}")

    # 加载各窗口
    windows = []
    for name, (prefix, subpath) in win_paths.items():
        tag = file_tags.get(name, "")
        wd = load_window(db_root, prefix, subpath, name, file_tag=tag)
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
            print(f"  {name}: [{', '.join(sources)}]")
        else:
            print(f"  {name}: no reports, skipping")

    if not windows:
        print(f"ERROR: No window data for {version}!")
        return

    # --- 从 power 报告补充 Ipeak (totalcurrent) ---
    if power_paths:
        all_wd = {"full": full}
        all_wd.update({w.name: w for w in windows})
        for wname, wd in all_wd.items():
            if wname in power_paths:
                pdir, pfile = power_paths[wname]
                ipeak_a = parse_totalcurrent(db_root / pdir / pfile)
                if ipeak_a > 0:
                    ipeak_ma = ipeak_a * 1000  # A → mA
                    # 注入到 dynpwr (不覆盖已有 rail 数据)
                    if not wd.dynpwr:
                        wd.dynpwr = DynPwrData()
                    if wd.dynpwr.ipeak_loaded <= 0:
                        wd.dynpwr.ipeak_loaded = ipeak_a
                    print(f"  {wname}: Ipeak from totalcurrent = {ipeak_ma:.3f} mA")

    # --- 单窗口覆盖率 ---
    single_results = []
    print(f"\n=== [{version}] Single Window Coverage ===")
    print(f"{'Window':<12} {'C1':>8} {'C_layer_avg':>12} {'C_layer_min':>12} {'C_margin':>10} {'C_overall':>10} {'Violation':>10}")
    print("-" * 78)
    for w in windows:
        cov = compute_coverage(full, w)
        single_results.append(cov)
        print(f"{cov.window:<12} {fmt_pct(cov.c1):>8} "
              f"{fmt_pct(cov.c_layer_avg):>12} {fmt_pct(cov.c_layer_min):>12} "
              f"{fmt_pct(cov.c_margin):>10} {fmt_pct(cov.c_overall):>10} {cov.c_violation:>10}")

    # --- 多窗口组合覆盖率 ---
    combo_results = []
    if combo_groups:
        # 使用指定的组合分组
        print(f"\n=== [{version}] Multi-Window Combinations ===")
        win_map = {w.name: w for w in windows}
        for group in combo_groups:
            members = [win_map[n] for n in group if n in win_map]
            if len(members) >= 2:
                cr = compute_combination(full, members)
                combo_results.append(cr)
                print(f"  {cr.windows:<30} C1={fmt_pct(cr.c1):>8} "
                      f"C_layer_min={fmt_pct(cr.c_layer_min):>8}")
    elif len(windows) >= 2:
        # 默认: 全排列组合
        for r in range(2, len(windows) + 1):
            for combo in combinations(windows, r):
                cr = compute_combination(full, list(combo))
                combo_results.append(cr)

    # --- 写出文件 ---
    csv1 = results_dir / f"coverage_tier1{suffix}.csv"
    csv2 = results_dir / f"coverage_combination{suffix}.csv"
    md_path = results_dir / f"coverage_report{suffix}.md"

    write_single_csv(single_results, csv1)
    print(f"\nSaved: {csv1}")

    if combo_results:
        write_combination_csv(combo_results, csv2)
        print(f"Saved: {csv2}")

    write_markdown_report(single_results, combo_results, full, windows, md_path,
                          version=version, window_descs=window_descs,
                          durations=durations, full_duration=full_duration)
    print(f"Saved: {md_path}")

    # Trade-off CSV
    if durations and full_duration > 0:
        tradeoff_csv = results_dir / f"tradeoff{suffix}.csv"
        write_tradeoff_csv(single_results, combo_results, durations,
                           full_duration, tradeoff_csv)
        print(f"Saved: {tradeoff_csv}")


# 窗口时长 (ns), 用于计算压缩率
V20_WINDOW_DURATIONS = {
    "eq_win1": 2370, "eq_win2": 2370, "eq_win3": 2370,
    "eq_win4": 2370, "eq_win5": 2370,
    "algo_win1": 600, "algo_win2": 500,
}
V20_FULL_DURATION = 11850  # ns

# 窗口说明
V20_WINDOW_DESCS = {
    "eq_win1": "等分窗口 1: 0 ~ 2370ns (2370ns)",
    "eq_win2": "等分窗口 2: 2370 ~ 4740ns (2370ns)",
    "eq_win3": "等分窗口 3: 4740 ~ 7110ns (2370ns)",
    "eq_win4": "等分窗口 4: 7110 ~ 9480ns (2370ns)",
    "eq_win5": "等分窗口 5: 9480 ~ 11850ns (2370ns)",
    "algo_win1": "算法选窗 1: 3790 ~ 4390ns (600ns, Phase 1, depletion_ratio=0.7)",
    "algo_win2": "算法选窗 2: 9600 ~ 10100ns (500ns, Phase 2, depletion_ratio=0.7)",
}

# 有意义的组合 (避免 7 窗口全排列爆炸)
V20_COMBO_GROUPS = [
    # 算法选窗组合
    ["algo_win1", "algo_win2"],
    # 等分最佳 vs 算法
    ["eq_win2", "eq_win4"],
    ["eq_win2", "eq_win5"],
    # 等分全部
    ["eq_win1", "eq_win2", "eq_win3", "eq_win4", "eq_win5"],
    # 算法 + 等分最佳
    ["algo_win1", "algo_win2", "eq_win2"],
]


def main():
    script_dir = Path(__file__).resolve().parent  # analyse/
    db_root = script_dir.parent                   # db/

    if "--db-root" in sys.argv:
        idx = sys.argv.index("--db-root")
        if idx + 1 < len(sys.argv):
            db_root = Path(sys.argv[idx + 1])

    results_dir = script_dir / "results"
    results_dir.mkdir(exist_ok=True)

    print(f"DB root: {db_root}")

    # 确定运行版本
    version = "v20"  # 默认 v20
    if "--v15" in sys.argv:
        version = "v15"
    elif "--version" in sys.argv:
        idx = sys.argv.index("--version")
        if idx + 1 < len(sys.argv):
            version = sys.argv[idx + 1]

    if version == "v15":
        _run_analysis(db_root, results_dir, "v15",
                      FULL_SET_PATH_V15, WIN_PATHS_V15,
                      {n: "" for n in ["full"] + list(WIN_PATHS_V15)},
                      {})
    else:
        _run_analysis(db_root, results_dir, "v20",
                      FULL_SET_PATH_V20, WIN_PATHS_V20, V20_FILE_TAGS,
                      V20_WINDOW_DESCS, V20_COMBO_GROUPS,
                      durations=V20_WINDOW_DURATIONS,
                      full_duration=V20_FULL_DURATION,
                      power_paths=V20_POWER_PATHS)


if __name__ == "__main__":
    main()
