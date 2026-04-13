#!/usr/bin/env python3
"""
Dual-dimension hotspot coverage evaluation for VCD compression.

Metrics
-------
  C_int = V_comp_max / V_orig_max × 100%    (intensity coverage)
  C_k   = P_{top-k}                          (locality coverage, fraction)

Usage — single pair:
  python code/evaluate.py --orig orig.iv --comp comp.iv

Usage — multiple pairs (one orig.iv comp.iv per line in a text file):
  python code/evaluate.py --runs runs.txt

Output JSON is printed to stdout or written with --out.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from parse_iv import parse_iv

KS_DEFAULT = (1, 3, 5, 10)


# ── per-pair ──────────────────────────────────────────────────────────────────

def _topk(data: dict, k: int) -> set:
    """Instance names with the k highest IR drops."""
    return set(sorted(data, key=data.__getitem__, reverse=True)[:k])


def eval_pair(orig_path: str, comp_path: str, ks=KS_DEFAULT) -> dict:
    orig, _ = parse_iv(orig_path)
    comp, _ = parse_iv(comp_path)

    if not orig:
        raise ValueError(f"No data parsed from {orig_path}")
    if not comp:
        raise ValueError(f"No data parsed from {comp_path}")

    v_orig_max = max(orig.values())
    v_comp_max = max(comp.values())
    c_int = v_comp_max / v_orig_max * 100

    hit_topk = {k: int(_topk(orig, k).issubset(_topk(comp, k))) for k in ks}

    return {
        "orig": orig_path,
        "comp": comp_path,
        "v_orig_max_mV": round(v_orig_max, 3),
        "v_comp_max_mV": round(v_comp_max, 3),
        "C_int_%": round(c_int, 2),
        "hit_topk": hit_topk,
    }


# ── multi-run aggregation ─────────────────────────────────────────────────────

def aggregate(results: list, ks=KS_DEFAULT) -> dict:
    n = len(results)
    c_ints = [r["C_int_%"] for r in results]
    mean_ci = sum(c_ints) / n
    std_ci = (sum((x - mean_ci) ** 2 for x in c_ints) / n) ** 0.5
    c_k = {
        str(k): round(sum(r["hit_topk"][k] for r in results) / n * 100, 1)
        for k in ks
    }
    return {
        "n_runs":        n,
        "C_int_mean_%":  round(mean_ci, 2),
        "C_int_min_%":   round(min(c_ints), 2),
        "C_int_std_%":   round(std_ci, 2),
        "C_k_%":         c_k,
    }


def verdict(summary: dict) -> str:
    c_int_ok = summary["C_int_min_%"] >= 95.0
    c1_ok    = float(summary["C_k_%"].get("1", 0)) >= 90.0
    if c_int_ok and c1_ok:
        return "PASS"
    if c_int_ok or c1_ok:
        return "MARGINAL"
    return "FAIL"


# ── reporting ─────────────────────────────────────────────────────────────────

def print_summary(summary: dict, verd: str) -> None:
    ck_str = "  ".join(f"k={k}: {v}%" for k, v in summary["C_k_%"].items())
    print()
    print("========== Coverage Evaluation Report ==========")
    print(f"  Runs    : {summary['n_runs']}")
    print(f"  C_int   : mean={summary['C_int_mean_%']:.2f}%"
          f"  min={summary['C_int_min_%']:.2f}%"
          f"  std={summary['C_int_std_%']:.2f}%")
    print(f"  C_k     : {ck_str}")
    print(f"  Verdict : {verd}")
    print("=================================================")
    print()


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Coverage evaluation for VCD compression (C_int + C_k)"
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--orig", help="Original Voltus .iv file")
    src.add_argument("--runs", help="Text file: one 'orig.iv  comp.iv' per line")
    parser.add_argument("--comp", help="Compressed .iv file (required with --orig)")
    parser.add_argument("--ks", nargs="+", type=int, default=list(KS_DEFAULT),
                        metavar="K", help="k values for C_k  (default: 1 3 5 10)")
    parser.add_argument("--out", metavar="PATH", help="Write JSON report to file")
    args = parser.parse_args()

    ks = tuple(sorted(set(args.ks)))

    # build pair list
    if args.orig:
        if not args.comp:
            parser.error("--comp is required when using --orig")
        pairs = [(args.orig, args.comp)]
    else:
        pairs = []
        with open(args.runs) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    pairs.append((parts[0], parts[1]))
        if not pairs:
            sys.exit("No valid pairs found in runs file.")

    # evaluate
    results = []
    for orig_p, comp_p in pairs:
        try:
            r = eval_pair(orig_p, comp_p, ks)
            results.append(r)
            hit1 = "HIT" if r["hit_topk"].get(1) else "MISS"
            print(f"  {os.path.basename(orig_p)} vs {os.path.basename(comp_p)}"
                  f"  C_int={r['C_int_%']:.2f}%  top-1={hit1}")
        except Exception as exc:
            print(f"  ERROR: {exc}", file=sys.stderr)

    if not results:
        sys.exit("No pairs evaluated successfully.")

    summary = aggregate(results, ks)
    verd    = verdict(summary)
    print_summary(summary, verd)

    report = {"summary": summary, "verdict": verd, "per_run": results}
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w") as f:
            json.dump(report, f, indent=2)
        print(f"Report saved → {args.out}")
    else:
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
