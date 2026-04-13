#!/usr/bin/env python3
"""
从 Voltus .iv 文件 + DEF 文件提取可视化数据。

输出：
  result/ir_drop_map.csv      每个 instance 的 IR Drop（orig/comp/delta），含坐标
  result/hotspot_topk.csv     top-k 热点实例对比表
  result/summary.json         覆盖率指标汇总

Usage:
  python code/extract_results.py \
      --orig  result/reference_full.iv \
      --comp  result/traditional_comp.iv \
      --def   path/to/design.def \
      --out   result/
"""

import argparse
import csv
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from parse_iv import parse_iv


# ── DEF component parser (inline) ────────────────────────────────────────────

def parse_def_components(def_path):
    """Returns {inst_name: (x_um, y_um, cell_type)}"""
    components = {}
    in_section = False
    buf = ''
    units = 4000

    with open(def_path, encoding='utf-8') as f:
        for line in f:
            s = line.strip()
            if not in_section:
                m = re.match(r'UNITS DISTANCE MICRONS (\d+)', s)
                if m:
                    units = int(m.group(1))
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
                x_um = int(pm.group(1)) / units
                y_um = int(pm.group(2)) / units
                components[inst] = (x_um, y_um, cell)
    return components


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--orig', required=True, help='Reference (full VCD) .iv file')
    p.add_argument('--comp', required=True, help='Compressed VCD .iv file')
    p.add_argument('--def',  required=True, dest='def_file', help='DEF layout file')
    p.add_argument('--out',  default='result/', help='Output directory')
    p.add_argument('--topk', type=int, default=20, help='Top-k hotspots to report')
    args = p.parse_args()

    os.makedirs(args.out, exist_ok=True)

    # ── load .iv ──────────────────────────────────────────────────────────────
    print('Parsing orig .iv ...')
    orig, nominal = parse_iv(args.orig)
    print(f'  {len(orig)} instances, Vnom={nominal}V')

    print('Parsing comp .iv ...')
    comp, _ = parse_iv(args.comp)
    print(f'  {len(comp)} instances')

    # ── load DEF positions ────────────────────────────────────────────────────
    print('Parsing DEF components ...')
    def_comps = parse_def_components(args.def_file)
    print(f'  {len(def_comps)} instances with position')

    # ── build unified table (orig instances only) ─────────────────────────────
    rows = []
    for inst, drop_orig in orig.items():
        drop_comp = comp.get(inst)       # may be None if not in comp
        x_um, y_um, cell = def_comps.get(inst, (None, None, ''))
        delta = (drop_comp - drop_orig) if drop_comp is not None else None
        rows.append({
            'inst':        inst,
            'cell':        cell,
            'x_um':        round(x_um, 3) if x_um is not None else '',
            'y_um':        round(y_um, 3) if y_um is not None else '',
            'ir_orig_mV':  round(drop_orig, 4),
            'ir_comp_mV':  round(drop_comp, 4) if drop_comp is not None else '',
            'delta_mV':    round(delta, 4) if delta is not None else '',
        })

    # Sort by orig IR drop descending
    rows.sort(key=lambda r: r['ir_orig_mV'], reverse=True)

    # ── write ir_drop_map.csv ─────────────────────────────────────────────────
    map_path = os.path.join(args.out, 'ir_drop_map.csv')
    fieldnames = ['inst', 'cell', 'x_um', 'y_um',
                  'ir_orig_mV', 'ir_comp_mV', 'delta_mV']
    with open(map_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f'Saved → {map_path}  ({len(rows)} rows)')

    # ── write hotspot_topk.csv ────────────────────────────────────────────────
    k = args.topk
    # top-k by orig
    topk_orig = rows[:k]
    # top-k by comp (among instances that appear in comp)
    comp_rows = [r for r in rows if r['ir_comp_mV'] != '']
    comp_rows_sorted = sorted(comp_rows, key=lambda r: r['ir_comp_mV'], reverse=True)
    topk_comp = comp_rows_sorted[:k]

    # build ranked comparison
    orig_rank = {r['inst']: i+1 for i, r in enumerate(rows)}
    comp_rank  = {r['inst']: i+1 for i, r in enumerate(comp_rows_sorted)}

    hotspot_rows = []
    seen = set()
    for r in topk_orig + topk_comp:
        if r['inst'] in seen:
            continue
        seen.add(r['inst'])
        hotspot_rows.append({
            'inst':          r['inst'],
            'cell':          r['cell'],
            'x_um':          r['x_um'],
            'y_um':          r['y_um'],
            'ir_orig_mV':    r['ir_orig_mV'],
            'ir_comp_mV':    r['ir_comp_mV'],
            'delta_mV':      r['delta_mV'],
            'rank_orig':     orig_rank.get(r['inst'], ''),
            'rank_comp':     comp_rank.get(r['inst'], ''),
            'in_orig_topk':  'Y' if r['inst'] in {x['inst'] for x in topk_orig} else '',
            'in_comp_topk':  'Y' if r['inst'] in {x['inst'] for x in topk_comp} else '',
        })
    hotspot_rows.sort(key=lambda r: r['rank_orig'] if r['rank_orig'] != '' else 9999)

    hs_path = os.path.join(args.out, f'hotspot_top{k}.csv')
    hs_fields = ['inst', 'cell', 'x_um', 'y_um',
                 'ir_orig_mV', 'ir_comp_mV', 'delta_mV',
                 'rank_orig', 'rank_comp', 'in_orig_topk', 'in_comp_topk']
    with open(hs_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=hs_fields)
        writer.writeheader()
        writer.writerows(hotspot_rows)
    print(f'Saved → {hs_path}  ({len(hotspot_rows)} rows)')

    # ── compute coverage metrics ──────────────────────────────────────────────
    v_orig_max = max(orig.values())
    v_comp_max = max(comp.values())
    c_int = v_comp_max / v_orig_max * 100

    def topk_set(data, k_):
        return set(sorted(data, key=data.get, reverse=True)[:k_])

    orig_topk = {kk: topk_set(orig, kk) for kk in [1, 3, 5, 10]}

    # For comp, only instances present in comp
    c_k = {}
    for kk in [1, 3, 5, 10]:
        ot = orig_topk[kk]
        ct = topk_set(comp, kk)
        c_k[kk] = int(ot.issubset(ct))

    # ── write summary.json ────────────────────────────────────────────────────
    summary = {
        'nominal_voltage_V':    nominal,
        'n_instances_orig':     len(orig),
        'n_instances_comp':     len(comp),
        'n_instances_def':      len(def_comps),
        'ir_orig_max_mV':       round(v_orig_max, 4),
        'ir_comp_max_mV':       round(v_comp_max, 4),
        'ir_orig_min_mV':       round(min(orig.values()), 4),
        'ir_comp_min_mV':       round(min(comp.values()), 4),
        'ir_orig_mean_mV':      round(sum(orig.values()) / len(orig), 4),
        'ir_comp_mean_mV':      round(sum(comp.values()) / len(comp), 4),
        'worst_inst_orig':      max(orig, key=orig.get),
        'worst_inst_comp':      max(comp, key=comp.get),
        'C_int_%':              round(c_int, 2),
        'C_k':                  {f'k={k}': ('HIT' if v else 'MISS') for k, v in c_k.items()},
        'verdict':              'PASS' if c_int >= 95 and c_k[1] else (
                                'MARGINAL' if c_int >= 95 or c_k[1] else 'FAIL'),
        'top1_orig':            max(orig, key=orig.get),
        'top1_comp':            max(comp, key=comp.get),
        'top1_match':           max(orig, key=orig.get) == max(comp, key=comp.get),
    }

    sum_path = os.path.join(args.out, 'summary.json')
    with open(sum_path, 'w') as f:
        json.dump(summary, f, indent=2)
    print(f'Saved → {sum_path}')

    # ── console summary ───────────────────────────────────────────────────────
    print()
    print('='*52)
    print(f'  C_int       : {c_int:.2f}%')
    ck_str = ' | '.join(f'k={k}: {"HIT" if v else "MISS"}' for k, v in c_k.items())
    print(f'  C_k         : {ck_str}')
    print(f'  worst orig  : {summary["worst_inst_orig"]}  {v_orig_max:.3f}mV')
    print(f'  worst comp  : {summary["worst_inst_comp"]}  {v_comp_max:.3f}mV')
    print(f'  top-1 match : {"YES" if summary["top1_match"] else "NO"}')
    print('='*52)


if __name__ == '__main__':
    main()
