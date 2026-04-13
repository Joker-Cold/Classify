#!/usr/bin/env python3
"""
Parse ASAP7 Liberty (.lib) files and extract per-cell power parameters.

Output JSON:
{
  "CellName": {
    "leakage_pW": float,
    "index_slew_ps": [7 floats],
    "index_load_fF": [7 floats],
    "energy_table_fJ": [[7x7 matrix]]  # avg over all internal_power rise+fall
  }, ...
}

Usage:
  python code/parse_lib_power.py --lib-dir path/to/mmmc/ --out result/lib_power.json
"""

import argparse
import glob
import json
import os
import re
import sys


# ── helpers ───────────────────────────────────────────────────────────────────

def _floats(text):
    return [float(x) for x in re.findall(r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?', text)]


def _mat_add(a, b):
    rows = min(len(a), len(b))
    result = []
    for r in range(rows):
        cols = min(len(a[r]), len(b[r]))
        result.append([a[r][c] + b[r][c] for c in range(cols)])
    return result


def _mat_scale(a, s):
    return [[v * s for v in row] for row in a]


def _collect_block(lines, start):
    """Read lines from `start` until a line containing ');' is found.
    Returns (flat_floats, next_i).
    """
    buf = ''
    i = start
    while i < len(lines):
        buf += lines[i]
        if ');' in lines[i]:
            i += 1
            break
        i += 1
    return _floats(buf), i


# ── per-file parser ───────────────────────────────────────────────────────────

def parse_lib_file(path):
    """Returns {cell_name: {leakage_pW, index_slew_ps, index_load_fF, energy_table_fJ}}"""
    cells = {}

    with open(path, encoding='utf-8', errors='replace') as f:
        lines = f.readlines()

    # Leakage unit
    leak_scale = 1.0
    for line in lines[:60]:
        m = re.search(r'leakage_power_unit\s*:\s*"([\d.]+)\s*(\w+)"', line)
        if m:
            val, unit = float(m.group(1)), m.group(2).lower()
            factors = {'fw': 1e-3, 'pw': 1.0, 'nw': 1e3, 'uw': 1e6}
            leak_scale = val * factors.get(unit, 1.0)
            break

    # --- State machine (manual i, no auto-increment) ---
    # States
    GLOBAL = 0; IN_CELL = 1; IN_LEAK = 2; IN_IPWR = 3; IN_RISE = 4; IN_FALL = 5

    state = GLOBAL
    depth = 0

    cell_d = leak_d = ipwr_d = rise_d = fall_d = None
    cell_name = None
    leak_vals = []
    energy_sum = None; energy_cnt = 0
    idx_slew = None; idx_load = None
    cur_idx1 = cur_idx2 = cur_rise = cur_fall = None

    i = 0
    N = len(lines)
    while i < N:
        raw = lines[i].strip()
        opens  = raw.count('{')
        closes = raw.count('}')

        # ── ENTRY checks (uses opens but NOT yet applied) ─────────────────────

        if state == GLOBAL:
            m = re.match(r'cell\s*\(([^)]+)\)\s*\{', raw)
            if m and opens > 0:
                depth  += opens - closes
                cell_d  = depth
                state   = IN_CELL
                cell_name = m.group(1).strip('"')
                leak_vals = []; energy_sum = None; energy_cnt = 0
                idx_slew = idx_load = None
                i += 1; continue

        elif state == IN_CELL:
            if re.match(r'leakage_power\s*\(\)', raw) and opens > 0:
                depth  += opens - closes
                leak_d  = depth
                state   = IN_LEAK
                i += 1; continue
            if re.match(r'internal_power\s*\(\)', raw) and opens > 0:
                depth  += opens - closes
                ipwr_d  = depth
                state   = IN_IPWR
                cur_idx1 = cur_idx2 = cur_rise = cur_fall = None
                i += 1; continue

        elif state == IN_LEAK:
            vm = re.search(r'value\s*:\s*([-+\d.eE]+)', raw)
            if vm:
                leak_vals.append(float(vm.group(1)))

        elif state == IN_IPWR:
            if re.match(r'rise_power\s*\(', raw) and opens > 0:
                depth  += opens - closes
                rise_d  = depth
                state   = IN_RISE
                cur_idx1 = cur_idx2 = cur_rise = None
                i += 1; continue
            if re.match(r'fall_power\s*\(', raw) and opens > 0:
                depth  += opens - closes
                fall_d  = depth
                state   = IN_FALL
                cur_idx1 = cur_idx2 = cur_fall = None
                i += 1; continue

        elif state in (IN_RISE, IN_FALL):
            if re.match(r'index_1\s*\(', raw):
                vals, i = _collect_block(lines, i)
                cur_idx1 = vals
                continue   # i already advanced past closing );
            if re.match(r'index_2\s*\(', raw):
                vals, i = _collect_block(lines, i)
                cur_idx2 = vals
                continue
            if re.match(r'values\s*\(', raw):
                vals, i = _collect_block(lines, i)
                rows = len(cur_idx1) if cur_idx1 else 7
                cols = len(cur_idx2) if cur_idx2 else 7
                mat = [vals[r * cols:(r + 1) * cols] for r in range(rows)
                       if (r + 1) * cols <= len(vals)]
                if state == IN_RISE:
                    cur_rise = mat
                    if cur_idx1 and idx_slew is None: idx_slew = cur_idx1
                    if cur_idx2 and idx_load is None: idx_load = cur_idx2
                else:
                    cur_fall = mat
                continue

        # ── Apply depth change ────────────────────────────────────────────────
        depth += opens - closes

        # ── EXIT checks ───────────────────────────────────────────────────────

        if state == IN_RISE and depth < rise_d:
            if cur_rise:
                energy_sum = (_mat_add(energy_sum, cur_rise)
                              if energy_sum else [r[:] for r in cur_rise])
                energy_cnt += 1
            state = IN_IPWR
            i += 1; continue

        if state == IN_FALL and depth < fall_d:
            if cur_fall:
                energy_sum = (_mat_add(energy_sum, cur_fall)
                              if energy_sum else [r[:] for r in cur_fall])
                energy_cnt += 1
            state = IN_IPWR
            i += 1; continue

        if state == IN_IPWR and depth < ipwr_d:
            state = IN_CELL
            i += 1; continue

        if state == IN_LEAK and depth < leak_d:
            state = IN_CELL
            i += 1; continue

        if state == IN_CELL and depth < cell_d:
            leakage_pW = (
                sum(leak_vals) / len(leak_vals) * leak_scale
                if leak_vals else 0.0
            )
            avg_table = (
                _mat_scale(energy_sum, 1.0 / energy_cnt)
                if energy_sum and energy_cnt > 0 else None
            )
            cells[cell_name] = {
                'leakage_pW':      round(leakage_pW, 4),
                'index_slew_ps':   idx_slew,
                'index_load_fF':   idx_load,
                'energy_table_fJ': avg_table,
            }
            state = GLOBAL; cell_name = None
            i += 1; continue

        i += 1

    return cells


# ── main ──────────────────────────────────────────────────────────────────────

def parse_lib_dir(lib_dir):
    all_cells = {}
    lib_files = sorted(glob.glob(os.path.join(lib_dir, '*.lib')))
    if not lib_files:
        sys.exit(f'No .lib files found in {lib_dir}')
    for path in lib_files:
        print(f'  {os.path.basename(path)} ...', end=' ', flush=True)
        cells = parse_lib_file(path)
        all_cells.update(cells)
        print(f'{len(cells)} cells')
    return all_cells


def main():
    p = argparse.ArgumentParser(description='Parse Liberty .lib → power param JSON')
    p.add_argument('--lib-dir', required=True)
    p.add_argument('--out',     required=True)
    args = p.parse_args()

    cells = parse_lib_dir(args.lib_dir)
    print(f'Total: {len(cells)} cells  '
          f'({sum(1 for v in cells.values() if v["energy_table_fJ"] is not None)} with LUT)')

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, 'w') as f:
        json.dump(cells, f, indent=2)
    print(f'Saved → {args.out}')


if __name__ == '__main__':
    main()
