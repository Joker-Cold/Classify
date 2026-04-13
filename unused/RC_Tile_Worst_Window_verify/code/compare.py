"""Compare IR-drop reports across full/algo/spatial/rctile baselines.

Parses Innovus VDD.main.rpt / VSS.main.rpt to extract:
  - Min / Avg / Max IR drop (V)
  - Dynamic Worst Case Interval (ns)
  - Number of violations
Then computes peak-drop reproduction ratio vs `full` baseline.
"""
from __future__ import annotations

import re
import argparse
from pathlib import Path
from typing import Any

VNOMINAL = 0.700  # VDD nominal


def parse_main_rpt(path: Path) -> dict[str, Any]:
    txt = path.read_text(errors="replace")
    out: dict[str, Any] = {"file": str(path)}
    m = re.search(
        r"Minimum, Average, Maximum IR drop:\s*([0-9.]+)V?\s+([0-9.]+)V?\s+([0-9.]+)V?",
        txt,
    )
    if m:
        vmin, vavg, vmax = (float(x) for x in m.groups())
        out.update(v_min=vmin, v_avg=vavg, v_max=vmax)
        # IR drop = nominal - measured  (smaller measured V => larger drop)
        out["drop_max_mV"] = (VNOMINAL - vmin) * 1000
        out["drop_avg_mV"] = (VNOMINAL - vavg) * 1000
    m = re.search(r"Dynamic Worst Case Interval:\s*(\d+)\s*\(([\d.]+)us\)", txt)
    if m:
        out["worst_interval_ns"] = int(m.group(1))
        out["worst_interval_us"] = float(m.group(2))
    m = re.search(r"Number of Violations:\s*(\d+)", txt)
    if m:
        out["n_violations"] = int(m.group(1))
    return out


def find_main_rpt(case_dir: Path, net: str) -> Path | None:
    for p in case_dir.rglob(f"{net}.main.rpt"):
        return p
    return None


CASES = [
    ("full",        "results/full"),
    ("algo_win1",   "results/algo/win1"),
    ("algo_win2",   "results/algo/win2"),
    ("spatial",     "results/spatial"),
    ("rctile_win1", "results/rctile"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".", help="verify project root")
    ap.add_argument("--output", default="results.md")
    args = ap.parse_args()

    root = Path(args.root)
    rows: list[dict[str, Any]] = []
    for name, rel in CASES:
        case_dir = root / rel
        row: dict[str, Any] = {"case": name, "dir": rel}
        for net in ("VDD", "VSS"):
            rpt = find_main_rpt(case_dir, net)
            if rpt is None:
                continue
            data = parse_main_rpt(rpt)
            for k, v in data.items():
                if k == "file":
                    continue
                row[f"{net}_{k}"] = v
        rows.append(row)

    # Reference: full's VDD drop_max
    ref = next((r for r in rows if r["case"] == "full"), None)
    ref_drop = ref.get("VDD_drop_max_mV") if ref else None

    # Build markdown
    lines: list[str] = []
    lines.append("# RC-Tile Worst-Window IR Drop Comparison\n")
    lines.append(f"> Reference: `full` VDD peak drop = **{ref_drop:.2f} mV** "
                 f"(@ interval {ref.get('VDD_worst_interval_ns','?')} ns)\n" if ref_drop else "")
    lines.append("## Per-case summary (VDD)\n")
    lines.append("| Case | Vmin (V) | Vavg (V) | **Peak drop (mV)** | Worst interval (ns) | Violations | Drop ratio vs full |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in rows:
        vmin = r.get("VDD_v_min", float("nan"))
        vavg = r.get("VDD_v_avg", float("nan"))
        dmax = r.get("VDD_drop_max_mV", float("nan"))
        wint = r.get("VDD_worst_interval_ns", "?")
        nv   = r.get("VDD_n_violations", "?")
        ratio = (dmax / ref_drop) if (ref_drop and dmax == dmax) else float("nan")
        lines.append(
            f"| `{r['case']}` | {vmin:.4f} | {vavg:.4f} | **{dmax:.2f}** | {wint} | {nv} | {ratio:.3f} |"
        )

    lines.append("\n## Per-case summary (VSS)\n")
    lines.append("| Case | Vmin (V) | Vavg (V) | Vmax (V) | Worst interval (ns) | Violations |")
    lines.append("|---|---|---|---|---|---|")
    for r in rows:
        lines.append(
            f"| `{r['case']}` | "
            f"{r.get('VSS_v_min', float('nan')):.4f} | "
            f"{r.get('VSS_v_avg', float('nan')):.4f} | "
            f"{r.get('VSS_v_max', float('nan')):.4f} | "
            f"{r.get('VSS_worst_interval_ns','?')} | "
            f"{r.get('VSS_n_violations','?')} |"
        )

    lines.append("\n## Notes\n")
    lines.append("- `Peak drop` = nominal VDD (0.700 V) − measured Vmin")
    lines.append("- `Drop ratio vs full` ≥ 0.95 表示压缩 VCD 充分复现 full 的 IR drop 峰值")
    lines.append("- Worst interval 是 Innovus 报告中 dynamic IR drop 最大瞬时所在的 ns")

    out_path = root / args.output
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out_path}")
    for r in rows:
        print(r)


if __name__ == "__main__":
    main()
