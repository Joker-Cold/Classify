#!/usr/bin/env python3
"""
Parse a Cadence SPEF file and extract total capacitance per net.

SPEF format (relevant sections):
  *C_UNIT 1 PF
  *NAME_MAP
  *1 u0/some_net_name
  ...
  *D_NET *1 0.000256538    ← net_id, total_cap in C_UNIT

Output JSON: {net_name: total_cap_pF}

Usage:
  python code/parse_spef.py --spef des3.spef --out result/net_cap.json
"""

import argparse
import json
import os
import re
import sys


def parse_spef(path):
    """
    Returns (net_cap, c_unit_scale) where:
        net_cap      : {net_name: total_cap_pF}
        c_unit_scale : multiply raw *D_NET value by this to get pF
    """
    c_unit_pF = 1.0   # default: values already in pF

    name_map = {}      # {*id: full_net_name}
    net_cap  = {}      # {net_name: cap_pF}

    section = None     # 'NAME_MAP' | 'NETS' | None

    with open(path, encoding='utf-8', errors='replace') as f:
        for line in f:
            raw = line.strip()
            if not raw or raw.startswith('//'):
                continue

            # ── header: capacitance unit ──────────────────────────────────
            m = re.match(r'\*C_UNIT\s+([\d.eE+\-]+)\s+(\w+)', raw)
            if m:
                val, unit = float(m.group(1)), m.group(2).upper()
                # convert to pF
                factors = {'FF': 1e-3, 'PF': 1.0, 'NF': 1e3, 'UF': 1e6}
                c_unit_pF = val * factors.get(unit, 1.0)
                continue

            # ── section markers ───────────────────────────────────────────
            if raw == '*NAME_MAP':
                section = 'NAME_MAP'
                continue
            if raw.startswith('*PORTS') or raw.startswith('*CONN') \
                    or raw.startswith('*CAP') or raw.startswith('*RES'):
                section = 'SKIP'
                continue
            if raw.startswith('*D_NET'):
                section = 'NETS'
                # also process this line below

            # ── NAME_MAP section ──────────────────────────────────────────
            if section == 'NAME_MAP':
                m = re.match(r'\*(\d+)\s+(.+)', raw)
                if m:
                    name_map[f'*{m.group(1)}'] = m.group(2).strip()
                continue

            # ── D_NET line (total cap) ────────────────────────────────────
            if section == 'NETS' and raw.startswith('*D_NET'):
                parts = raw.split()
                if len(parts) >= 3:
                    net_id = parts[1]          # e.g. *1
                    try:
                        cap_raw = float(parts[2])
                    except ValueError:
                        continue
                    cap_pF = cap_raw * c_unit_pF
                    # resolve net name
                    net_name = name_map.get(net_id, net_id.lstrip('*'))
                    net_cap[net_name] = cap_pF
                # next lines are *CONN/*CAP/*RES — skip until next *D_NET
                section = 'SKIP'
                continue

    return net_cap, c_unit_pF


def main():
    parser = argparse.ArgumentParser(description="Parse SPEF → per-net total capacitance JSON")
    parser.add_argument('--spef', required=True, help='SPEF file path')
    parser.add_argument('--out',  required=True, help='Output JSON path')
    args = parser.parse_args()

    if not os.path.isfile(args.spef):
        sys.exit(f"SPEF not found: {args.spef}")

    print(f"Parsing {args.spef} ...")
    net_cap, unit = parse_spef(args.spef)
    print(f"C_UNIT scale: {unit} pF   |   Nets extracted: {len(net_cap)}")

    if net_cap:
        caps = list(net_cap.values())
        print(f"Cap range: min={min(caps):.6g} pF  max={max(caps):.6g} pF  mean={sum(caps)/len(caps):.6g} pF")

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, 'w') as f:
        json.dump(net_cap, f, indent=2)
    print(f"Saved → {args.out}")


if __name__ == '__main__':
    main()
