#!/usr/bin/env python3
"""
Traditional Vector Profiling — Power Matrix Generation

Algorithm (based on Wen et al. ICCAD 2023):
  Divide simulation time into fixed-size windows (default 20 ns).
  Divide chip area into M×N tiles (default 50×50).
  For each window t and tile (iy, ix), compute total power:
    P[t][iy][ix] = Σ_{inst ∈ tile} (P_sw + P_int + P_leak)  [mW]

Power model per instance per window:
    P_sw   = Σ_toggles × 0.5 × C_net_pF × V_DD² × 1e3 / window_ns  [mW]
    P_int  = Σ_toggles × lookup_energy(cell, C_fF, slew_ps) / window_ns × 1e-3 [mW]
    P_leak = leakage_pW × 1e-9                                                   [mW]

Output:
  JSON with power_matrix_mW [T][ny][mx] and avg_power_mW [T].

Usage:
  python code/traditional_select.py \
      --toggles sim_result/intermediate/input_toggles.jsonl \
      --vcd input.vcd --lib-power report/lib_power.json \
      --net-cap report/net_cap.json --def design.def \
      --window-ns 20 --mx 50 --ny 50 \
      --json-out sim_result/report/report.json
"""

import argparse
import json
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from parse_vcd_signal import VCDSignalParser


# ══════════════════════════════════════════════════════════════════════════════
# DEF parsing (inlined from vcd_def_mapper.py)
# ══════════════════════════════════════════════════════════════════════════════

def parse_def_units(def_path):
    with open(def_path, encoding='utf-8') as f:
        for line in f:
            m = re.match(r'UNITS DISTANCE MICRONS (\d+)', line.strip())
            if m:
                return int(m.group(1))
            if line.strip().startswith('COMPONENTS') or line.strip().startswith('PINS'):
                break
    return 4000


def parse_def_components(def_path):
    """{inst_name: (x_dbu, y_dbu, cell_type)}"""
    components = {}
    in_section = False
    buf = ''
    with open(def_path, encoding='utf-8') as f:
        for line in f:
            s = line.strip()
            if not in_section:
                if s.startswith('COMPONENTS '):
                    in_section = True
                continue
            if s == 'END COMPONENTS':
                break
            buf += ' ' + s
            if ';' not in s:
                continue
            entry = buf.strip()
            buf = ''
            m = re.match(r'^-\s+(\S+)\s+(\S+)', entry)
            if not m:
                continue
            inst = m.group(1).replace('\\[', '[').replace('\\]', ']')
            cell = m.group(2)
            pm = re.search(r'PLACED\s*\(\s*(-?\d+)\s+(-?\d+)\s*\)', entry)
            if not pm:
                pm = re.search(r'FIXED\s*\(\s*(-?\d+)\s+(-?\d+)\s*\)', entry)
            if pm:
                components[inst] = (int(pm.group(1)), int(pm.group(2)), cell)
    return components


def _full_name_to_def_path(full_name, top_scope):
    """Convert VCD full_name (dot-separated) to DEF inst path (slash-separated).
    Strips testbench scope and one more level (design top instance).
    """
    parts = full_name.split('.')
    if parts and parts[0] == top_scope:
        parts = parts[1:]
    if parts:
        parts = parts[1:]
    return '/'.join(parts)


def _full_name_to_net_path(full_name, top_scope):
    """Convert VCD full_name to DEF/SPEF net path.
    Strips testbench AND design instantiation level (same as _full_name_to_def_path).
    e.g. test.u0.u2.CTS_16 → u2/CTS_16
    """
    parts = full_name.split('.')
    if parts and parts[0] == top_scope:
        parts = parts[1:]
    if parts:
        parts = parts[1:]
    return '/'.join(parts)


_OUTPUT_PINS = {'Y', 'Q', 'QN', 'Z', 'ZN', 'CO', 'S', 'SN'}


def parse_def_nets_drivers(def_path):
    """{net_name: driver_inst_name}  (output pin = Y/Q/QN/Z/ZN/...)"""
    drivers = {}
    in_nets = False
    cur_net = None
    driver_found = False

    with open(def_path, encoding='utf-8') as f:
        for line in f:
            s = line.strip()
            if not in_nets:
                if s.startswith('NETS '):
                    in_nets = True
                continue
            if s == 'END NETS':
                break

            # New net entry
            if s.startswith('- ') and not s.startswith('- ('):
                cur_net = s[2:].split()[0].replace('\\[', '[').replace('\\]', ']')
                driver_found = False
                continue

            if cur_net is None:
                continue

            # End of this net's connections (routing or source line)
            if s.startswith('+ ') or s == ';':
                continue

            # Connection line: ( inst pin ) ...
            if not driver_found and '( ' in s:
                for m in re.finditer(r'\(\s*(\S+)\s+(\S+)\s*\)', s):
                    inst = m.group(1).replace('\\[', '[').replace('\\]', ']')
                    pin  = m.group(2)
                    if pin in _OUTPUT_PINS:
                        drivers[cur_net] = inst
                        driver_found = True
                        break

    return drivers


# ══════════════════════════════════════════════════════════════════════════════
# LUT interpolation
# ══════════════════════════════════════════════════════════════════════════════

def lookup_energy(cell_data, C_load_fF, slew_ps=40):
    """Linear interpolation in internal_power LUT.

    Returns average energy per toggle in fJ.
    Falls back to table mean if indices not available.
    """
    table = cell_data.get('energy_table_fJ')
    if table is None:
        return 0.0

    idx_slew = cell_data.get('index_slew_ps')
    idx_load = cell_data.get('index_load_fF')

    if not idx_slew or not idx_load:
        # flat mean
        flat = [v for row in table for v in row]
        return sum(flat) / len(flat) if flat else 0.0

    # find slew row index (nearest)
    row_idx = 0
    for k, s in enumerate(idx_slew):
        if abs(s - slew_ps) < abs(idx_slew[row_idx] - slew_ps):
            row_idx = k

    row = table[row_idx] if row_idx < len(table) else table[-1]

    # interpolate in load dimension
    if C_load_fF <= idx_load[0]:
        return row[0]
    if C_load_fF >= idx_load[-1]:
        return row[-1]
    for k in range(len(idx_load) - 1):
        if idx_load[k] <= C_load_fF <= idx_load[k + 1]:
            t = (C_load_fF - idx_load[k]) / (idx_load[k + 1] - idx_load[k])
            return row[k] + t * (row[k + 1] - row[k])
    return row[-1]


# ══════════════════════════════════════════════════════════════════════════════
# Signal → power param mapping
# ══════════════════════════════════════════════════════════════════════════════

def build_signal_power_map(vcd_path, lib_power, net_cap, def_components,
                           def_net_drivers, dbu_scale, tile_bounds, mx, ny, slew_ps):
    """
    Returns {sig_name: {C_net_pF, energy_int_fJ, leakage_pW, tile: (iy, ix)}}

    Mapping chain:
      VCD signal full_name
        → net_path (strip testbench, use /)
        → net_cap (SPEF)  +  driver inst (DEF NETS)
        → driver inst → cell_type (DEF COMPONENTS)
        → lib_power (Liberty LUT)
        → tile (physical position)
    """
    parser = VCDSignalParser(vcd_path)
    signals = parser.list_unique_signals()
    top_scope = parser.top_scope

    x_min, x_max, y_min, y_max = tile_bounds
    tile_w = (x_max - x_min) / mx if mx > 0 else 1
    tile_h = (y_max - y_min) / ny if ny > 0 else 1

    # Global fallbacks (used when a signal can't be fully mapped)
    all_energies = []
    all_leakages = []
    for cell in lib_power.values():
        table = cell.get('energy_table_fJ')
        if table:
            flat = [v for row in table for v in row]
            all_energies.extend(flat)
        if cell.get('leakage_pW', 0) > 0:
            all_leakages.append(cell['leakage_pW'])
    avg_energy_fJ  = sum(all_energies) / len(all_energies) if all_energies else 1.0
    avg_leakage_pW = sum(all_leakages) / len(all_leakages) if all_leakages else 100.0
    avg_cap_pF     = sum(net_cap.values()) / len(net_cap) if net_cap else 0.001

    result = {}
    n_mapped = 0
    n_fallback = 0

    for sig in signals:
        sig_name  = sig['name']
        full_name = sig['full_name']

        # ── net path (used for SPEF and DEF NETS lookup) ──────────────────────
        net_path = _full_name_to_net_path(full_name, top_scope)

        # ── SPEF capacitance ──────────────────────────────────────────────────
        C_pF = net_cap.get(net_path, avg_cap_pF)

        # ── DEF NETS → driver instance → DEF COMPONENTS ──────────────────────
        driver_inst = def_net_drivers.get(net_path)
        comp = def_components.get(driver_inst) if driver_inst else None

        tile       = None
        leakage_pW = avg_leakage_pW
        energy_fJ  = avg_energy_fJ

        if comp is not None:
            x_dbu, y_dbu, cell_type = comp
            x_um = x_dbu / dbu_scale
            y_um = y_dbu / dbu_scale
            ix = min(max(int((x_um - x_min) / tile_w), 0), mx - 1)
            iy = min(max(int((y_um - y_min) / tile_h), 0), ny - 1)
            tile = (iy, ix)

            cell_data = lib_power.get(cell_type)
            if cell_data:
                leakage_pW = cell_data.get('leakage_pW', avg_leakage_pW)
                energy_fJ  = lookup_energy(cell_data, C_pF * 1000, slew_ps)
            n_mapped += 1
        else:
            n_fallback += 1

        result[sig_name] = {
            'C_net_pF':      C_pF,
            'energy_int_fJ': energy_fJ,
            'leakage_pW':    leakage_pW,
            'tile':          tile,
        }

    print(f'  Signals total={len(signals)}  mapped={n_mapped}  fallback={n_fallback}')
    return result


# ══════════════════════════════════════════════════════════════════════════════
# Tile bounds from DEF
# ══════════════════════════════════════════════════════════════════════════════

def compute_tile_bounds(def_components, dbu_scale):
    """Return (x_min_um, x_max_um, y_min_um, y_max_um) from DEF components."""
    if not def_components:
        return (0, 1000, 0, 1000)
    xs = [x / dbu_scale for x, y, _ in def_components.values()]
    ys = [y / dbu_scale for x, y, _ in def_components.values()]
    return min(xs), max(xs), min(ys), max(ys)


# ══════════════════════════════════════════════════════════════════════════════
# Power matrix computation
# ══════════════════════════════════════════════════════════════════════════════

def compute_power_matrix(toggles_path, signal_map, T, t_max, vdd, window_ns,
                         mx, ny):
    """
    Stream toggle JSONL → build power_matrix[T][ny][mx] (mW per tile).

    Returns:
        power_matrix : list[list[list[float]]]  shape [T][ny][mx], values in mW
        avg_power    : list[float]              shape [T], average over all tiles per window
    """
    window_ticks = t_max / T

    # Accumulate switching + internal energy (fJ) per window per tile
    energy_tile = [[[0.0] * mx for _ in range(ny)] for _ in range(T)]

    # Leakage power per tile (constant, same for all windows)
    leakage_tile = [[0.0] * mx for _ in range(ny)]

    for params in signal_map.values():
        tile = params.get('tile')
        if tile is None:
            continue
        iy, ix = tile
        leakage_tile[iy][ix] += params['leakage_pW'] * 1e-9  # pW → mW

    print(f'  Streaming {toggles_path} ...')
    line_count = 0

    with open(toggles_path, encoding='utf-8') as f:
        for line in f:
            line_count += 1
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            t_tick = obj.get('time', 0)
            win_idx = min(int(t_tick / window_ticks), T - 1)

            for sig_name, toggle_str in obj.get('signals', {}).items():
                n_toggles = toggle_str.count('1')
                if n_toggles == 0:
                    continue
                params = signal_map.get(sig_name)
                if params is None or params['tile'] is None:
                    continue
                iy, ix = params['tile']

                # Switching energy: E = 0.5 × C_pF × V² × 1e3 fJ
                E_sw_fJ  = 0.5 * params['C_net_pF'] * vdd**2 * 1e3
                E_int_fJ = params['energy_int_fJ']
                energy_tile[win_idx][iy][ix] += n_toggles * (E_sw_fJ + E_int_fJ)

    print(f'  Processed {line_count} JSONL lines')

    # Convert energy → power (mW) and build matrix
    power_matrix = [[[0.0] * mx for _ in range(ny)] for _ in range(T)]
    avg_power = []

    for t in range(T):
        total_power = 0.0
        for iy in range(ny):
            for ix in range(mx):
                P_sw_int = energy_tile[t][iy][ix] / window_ns * 1e-3  # fJ/ns → mW
                P_leak   = leakage_tile[iy][ix]                        # mW
                p = P_sw_int + P_leak
                power_matrix[t][iy][ix] = round(p, 6)
                total_power += p
        avg_power.append(round(total_power / (mx * ny), 6))

    return power_matrix, avg_power


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def get_t_max(toggles_path):
    """Find maximum time tick in toggle JSONL."""
    t_max = 0
    with open(toggles_path, encoding='utf-8') as f:
        for line in f:
            try:
                t = json.loads(line).get('time', 0)
                if t > t_max:
                    t_max = t
            except json.JSONDecodeError:
                pass
    return t_max


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

def main():
    p = argparse.ArgumentParser(
        description='Traditional vector profiling: power matrix generation'
    )
    p.add_argument('--toggles',      required=True,  help='Toggle JSONL from jsonl_toggle_mark.py')
    p.add_argument('--vcd',          required=True,  help='Original VCD file')
    p.add_argument('--lib-power',    required=True,  help='lib_power.json from parse_lib_power.py')
    p.add_argument('--net-cap',      required=True,  help='net_cap.json from parse_spef.py')
    p.add_argument('--def',          required=True,  dest='def_file', help='DEF file')
    p.add_argument('--window-ns',    type=float, default=20.0, help='Window size in ns (default: 20)')
    p.add_argument('--mx',           type=int, default=50,   help='Tile columns (default: 50)')
    p.add_argument('--ny',           type=int, default=50,   help='Tile rows (default: 50)')
    p.add_argument('--vdd',          type=float, default=0.7, help='Supply voltage V')
    p.add_argument('--slew-ps',      type=float, default=40.0, help='Fixed input slew for LUT lookup (ps)')
    p.add_argument('--timescale-ps', type=float, default=10.0, help='VCD timescale in ps')
    p.add_argument('--json-out',     required=True, help='Output JSON report path')
    args = p.parse_args()

    # ── load data ─────────────────────────────────────────────────────────────
    print('Loading lib_power.json ...')
    with open(args.lib_power) as f:
        lib_power = json.load(f)
    print(f'  {len(lib_power)} cell types loaded')

    print('Loading net_cap.json ...')
    with open(args.net_cap) as f:
        net_cap = json.load(f)
    print(f'  {len(net_cap)} nets loaded')

    print(f'Parsing DEF: {args.def_file} ...')
    dbu_scale  = parse_def_units(args.def_file)
    def_comps  = parse_def_components(args.def_file)
    print(f'  {len(def_comps)} instances, DBU scale={dbu_scale}')
    print(f'  Parsing DEF NETS for driver mapping ...')
    def_net_drivers = parse_def_nets_drivers(args.def_file)
    print(f'  {len(def_net_drivers)} nets with driver found')

    # ── tile setup ────────────────────────────────────────────────────────────
    tile_bounds = compute_tile_bounds(def_comps, dbu_scale)
    print(f'  Chip extent: x=[{tile_bounds[0]:.1f}, {tile_bounds[1]:.1f}] um  '
          f'y=[{tile_bounds[2]:.1f}, {tile_bounds[3]:.1f}] um')

    # ── signal mapping ────────────────────────────────────────────────────────
    print(f'Building signal power map (VCD={args.vcd}) ...')
    signal_map = build_signal_power_map(
        args.vcd, lib_power, net_cap, def_comps,
        def_net_drivers, dbu_scale, tile_bounds, args.mx, args.ny, args.slew_ps
    )

    # ── time parameters ───────────────────────────────────────────────────────
    print(f'Scanning toggle JSONL for t_max ...')
    t_max = get_t_max(args.toggles)
    window_ticks = args.window_ns * 1000 / args.timescale_ps  # ns → ticks
    T = math.ceil(t_max / window_ticks) if t_max > 0 else 1
    window_ns = args.window_ns
    print(f'  t_max={t_max} ticks  window={window_ticks:.1f} ticks = {window_ns:.2f} ns')
    print(f'  T={T} windows')

    # ── compute power matrix ──────────────────────────────────────────────────
    print(f'Computing power matrix ({T}×{args.ny}×{args.mx}) ...')
    power_matrix, avg_power = compute_power_matrix(
        args.toggles, signal_map, T, t_max,
        args.vdd, window_ns, args.mx, args.ny
    )

    # ── summary stats ─────────────────────────────────────────────────────────
    all_avg = avg_power
    print(f'  avg_power range: min={min(all_avg):.4g}  max={max(all_avg):.4g} mW')

    # ── JSON report ───────────────────────────────────────────────────────────
    report = {
        'parameters': {
            'window_ns': window_ns,
            'T': T,
            'mx': args.mx,
            'ny': args.ny,
            'vdd': args.vdd,
            'slew_ps': args.slew_ps,
            'timescale_ps': args.timescale_ps,
            't_max_ticks': t_max,
        },
        'power_matrix_mW': power_matrix,   # [T][ny][mx]
        'avg_power_mW': avg_power,          # [T]
    }

    os.makedirs(os.path.dirname(os.path.abspath(args.json_out)), exist_ok=True)
    with open(args.json_out, 'w') as f:
        json.dump(report, f)
    sz_mb = os.path.getsize(args.json_out) / 1e6
    print(f'Report → {args.json_out}  ({sz_mb:.1f} MB)')


if __name__ == '__main__':
    main()
