#!/usr/bin/env python3
"""
Lightweight SPEF parser for RC_Tile_Worst_Window.

Extracts per-net lumped capacitance and lumped resistance from SPEF.

Output:
    {net_name: {"c_load": float (fF), "r_net": float (Ohm)}}

Supported SPEF dialects: standard IEEE 1481 produced by Innovus / ICC2.

Algorithm:
    1. Parse *NAME_MAP section to build short_id -> full_name mapping.
    2. Walk *D_NET / *END blocks:
        - Sum *CAP entries -> c_load (fF)
        - Sum *RES entries -> r_net (Ohm)
    3. Resolve any *N<id> in net header to full hierarchical name.

This is a streaming parser; it does not build the full SPEF tree, only
the (c_load, r_net) per net needed by Stage 3 of the worst-case window
selection algorithm.
"""
import argparse
import csv
import os
import re
import sys


_NET_HDR = re.compile(r"^\*D_NET\s+(\S+)\s+([\d.eE+-]+)")
_NAME_MAP = re.compile(r"^\*(\d+)\s+(\S+)")


def parse_spef(spef_path: str) -> dict:
    """Parse SPEF, return {net_full_name: {"c_load": fF, "r_net": Ohm}}.

    Capacitance unit normalized to fF; resistance to Ohm.
    """
    name_map = {}            # short id -> full name
    nets = {}                # full name -> {c_load, r_net}

    cap_unit_scale = 1.0     # to fF
    res_unit_scale = 1.0     # to Ohm

    in_name_map = False
    in_dnet = False
    in_cap = False
    in_res = False

    cur_name = None
    cur_lumped = 0.0
    cur_cap_sum = 0.0
    cur_res_sum = 0.0

    def resolve(token: str) -> str:
        # Resolve a possible *<id> name reference (with optional :pin tail)
        if not token.startswith("*"):
            return token
        m = re.match(r"\*(\d+)(.*)", token)
        if not m:
            return token
        nid, tail = m.group(1), m.group(2)
        full = name_map.get(nid, token)
        return full + tail

    with open(spef_path, "r", encoding="utf-8", errors="ignore") as f:
        for raw in f:
            s = raw.strip()
            if not s:
                continue

            # ── Units (header) ────────────────────────────────────
            if s.startswith("*C_UNIT"):
                # *C_UNIT 1 PF / FF
                parts = s.split()
                if len(parts) >= 3:
                    val = float(parts[1])
                    unit = parts[2].upper()
                    if unit == "PF":
                        cap_unit_scale = val * 1000.0   # pF -> fF
                    elif unit == "FF":
                        cap_unit_scale = val
                    elif unit == "AF":
                        cap_unit_scale = val / 1000.0
                continue
            if s.startswith("*R_UNIT"):
                parts = s.split()
                if len(parts) >= 3:
                    val = float(parts[1])
                    unit = parts[2].upper()
                    if unit == "OHM":
                        res_unit_scale = val
                    elif unit == "KOHM":
                        res_unit_scale = val * 1000.0
                continue

            # ── Name map ──────────────────────────────────────────
            if s.startswith("*NAME_MAP"):
                in_name_map = True
                continue
            if in_name_map:
                if s.startswith("*PORTS") or s.startswith("*D_NET") or \
                   s.startswith("*DEFINE") or s.startswith("*POWER_NETS"):
                    in_name_map = False
                    # Fall through to process this line
                else:
                    m = _NAME_MAP.match(s)
                    if m:
                        name_map[m.group(1)] = m.group(2)
                    continue

            # ── D_NET block ───────────────────────────────────────
            if s.startswith("*D_NET"):
                m = _NET_HDR.match(s)
                if m:
                    cur_name = resolve(m.group(1))
                    try:
                        cur_lumped = float(m.group(2)) * cap_unit_scale
                    except ValueError:
                        cur_lumped = 0.0
                    cur_cap_sum = 0.0
                    cur_res_sum = 0.0
                    in_dnet = True
                    in_cap = False
                    in_res = False
                continue

            if in_dnet and s.startswith("*CONN"):
                in_cap = False
                in_res = False
                continue
            if in_dnet and s.startswith("*CAP"):
                in_cap = True
                in_res = False
                continue
            if in_dnet and s.startswith("*RES"):
                in_cap = False
                in_res = True
                continue
            if in_dnet and s.startswith("*END"):
                # Pick lumped if no detailed cap entries
                c = cur_cap_sum if cur_cap_sum > 0 else cur_lumped
                r = cur_res_sum
                if cur_name:
                    nets[cur_name] = {"c_load": c, "r_net": r}
                in_dnet = False
                in_cap = False
                in_res = False
                cur_name = None
                continue

            # Inside CAP / RES sections, lines look like:
            #   1 *123:nodeA 0.0123      (lumped/grounded cap)
            #   1 *123:nodeA *124:nodeB 0.0456  (coupling cap)
            #   1 *123:nodeA *124:nodeB 0.789   (resistor)
            if in_dnet and (in_cap or in_res):
                parts = s.split()
                if not parts:
                    continue
                # Last token should be the value
                try:
                    val = float(parts[-1])
                except ValueError:
                    continue
                if in_cap:
                    cur_cap_sum += val * cap_unit_scale
                else:
                    cur_res_sum += val * res_unit_scale

    return nets


def merge_into_location_csv(spef_nets: dict,
                            location_csv: str,
                            output_csv: str) -> int:
    """Augment a signal_location_map.csv with c_load + r_net columns
    by joining on signal_name (full hierarchical net name).

    Returns number of rows that received non-zero RC values.
    """
    rows = []
    n_hit = 0
    with open(location_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        for col in ("c_load", "r_net"):
            if col not in fieldnames:
                fieldnames.append(col)
        for row in reader:
            name = row.get("signal_name", "")
            rc = spef_nets.get(name)
            if rc is None:
                # Try with leading slash variant
                rc = spef_nets.get("/" + name) or spef_nets.get(name.lstrip("/"))
            if rc:
                row["c_load"] = f"{rc['c_load']:.6g}"
                row["r_net"] = f"{rc['r_net']:.6g}"
                n_hit += 1
            else:
                row.setdefault("c_load", "")
                row.setdefault("r_net", "")
            rows.append(row)

    os.makedirs(os.path.dirname(os.path.abspath(output_csv)), exist_ok=True)
    with open(output_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return n_hit


def main():
    p = argparse.ArgumentParser(
        description="SPEF parser: extract per-net (c_load, r_net) and "
                    "merge into a signal_location_map.csv")
    p.add_argument("--spef", required=True, help="Input SPEF file")
    p.add_argument("--location", default=None,
                   help="Optional signal_location_map.csv to augment")
    p.add_argument("--output", required=True,
                   help="Output CSV (augmented) or net RC dump")
    args = p.parse_args()

    print(f"[1/2] Parsing SPEF: {args.spef}")
    nets = parse_spef(args.spef)
    print(f"  Parsed {len(nets):,} nets")

    if args.location:
        print(f"[2/2] Merging into {args.location}")
        n_hit = merge_into_location_csv(nets, args.location, args.output)
        print(f"  {n_hit:,} / {len(nets):,} nets matched")
        print(f"  Output: {args.output}")
    else:
        # Standalone dump
        print(f"[2/2] Writing net RC dump: {args.output}")
        os.makedirs(os.path.dirname(os.path.abspath(args.output)) or ".",
                    exist_ok=True)
        with open(args.output, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["net_name", "c_load_fF", "r_net_ohm"])
            for name, rc in nets.items():
                w.writerow([name, f"{rc['c_load']:.6g}", f"{rc['r_net']:.6g}"])


if __name__ == "__main__":
    main()
