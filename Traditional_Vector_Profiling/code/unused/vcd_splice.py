#!/usr/bin/env python3
"""
Unused VCD splice utilities — moved from traditional_select.py.
Kept for potential future use (top-k window selection + VCD splicing).
"""

import re


def _parse_vc_line(s):
    m = re.match(r'^([01xzXZ])(.+)$', s)
    if m:
        return m.group(2), s
    m = re.match(r'^b([01xzXZ]+)\s+(.+)$', s)
    if m:
        return m.group(2).strip(), s
    return None


def _find_interval(t, intervals, hint):
    n = len(intervals)
    if 0 <= hint < n:
        s, e = intervals[hint]
        if s <= t < e:
            return hint
        if hint + 1 < n:
            s2, e2 = intervals[hint + 1]
            if s2 <= t < e2:
                return hint + 1
    for i, (s, e) in enumerate(intervals):
        if s <= t < e:
            return i
        if s > t:
            break
    return -1


def expand_and_merge(selected_set, kt, t_max, warmup_ticks):
    win_size = t_max / kt
    intervals = []
    for j in sorted(selected_set):
        win_start = int(j * win_size)
        win_end   = int((j + 1) * win_size)
        ext_start = max(0, win_start - warmup_ticks)
        intervals.append((ext_start, win_end))
    if not intervals:
        return []
    intervals.sort()
    merged = [intervals[0]]
    for start, end in intervals[1:]:
        ps, pe = merged[-1]
        if start <= pe:
            merged[-1] = (ps, max(pe, end))
        else:
            merged.append((start, end))
    return merged


def splice_vcd_v2(vcd_path, merged_intervals, output_path):
    if not merged_intervals:
        return {}

    sym_width = {}
    header_lines = []
    with open(vcd_path, encoding='utf-8') as f:
        for line in f:
            header_lines.append(line)
            s = line.strip()
            m = re.match(r'\$var\s+\S+\s+(\d+)\s+(\S+)\s+', s)
            if m:
                sym_width[m.group(2)] = int(m.group(1))
            if s.startswith('$enddefinitions'):
                break

    interval_offsets = []
    cumulative = 0
    for start, end in merged_intervals:
        interval_offsets.append(cumulative - start)
        cumulative += (end - start)

    stats = {'n_changes': 0, 'n_times': 0,
             'n_segments': len(merged_intervals),
             'total_output_ticks': cumulative}

    # Pass 1: capture boundary states
    boundary_states = {}
    last_values = {}
    next_boundary = 0

    with open(vcd_path, encoding='utf-8') as f:
        in_val = in_dv = False
        for line in f:
            s = line.strip()
            if not s:
                continue
            if not in_val:
                if s.startswith('$enddefinitions'):
                    in_val = True
                continue
            if s == '$dumpvars':
                in_dv = True; continue
            if s == '$end' and in_dv:
                in_dv = False; continue
            if s.startswith('#'):
                try:
                    t = int(s[1:])
                except ValueError:
                    continue
                while (next_boundary < len(merged_intervals) and
                       t >= merged_intervals[next_boundary][0]):
                    boundary_states[next_boundary] = dict(last_values)
                    next_boundary += 1
                if next_boundary >= len(merged_intervals):
                    break
                continue
            if s.startswith('$'):
                continue
            parsed = _parse_vc_line(s)
            if parsed:
                sym, raw = parsed
                last_values[sym] = raw
    while next_boundary < len(merged_intervals):
        boundary_states[next_boundary] = dict(last_values)
        next_boundary += 1

    print(f'  Boundary states: {len(boundary_states)} intervals')

    # Pass 2: write output
    with open(vcd_path, encoding='utf-8') as fin, \
         open(output_path, 'w', encoding='utf-8') as fout:
        for hl in header_lines:
            fout.write(hl)
        fout.write('\n')

        in_val = in_dumpvars = False
        active_idx = -1
        last_written_idx = -1

        def write_dumpvars(iidx, t):
            nonlocal last_written_idx
            s_tick, e_tick = merged_intervals[iidx]
            fout.write(f'$comment segment {iidx+1}: #{s_tick}~#{e_tick} $end\n')
            out_t = t + interval_offsets[iidx]
            fout.write(f'#{out_t}\n')
            fout.write('$dumpvars\n')
            state = boundary_states.get(iidx, {})
            for sym in sorted(state):
                fout.write(state[sym] + '\n')
            for sym, w in sym_width.items():
                if sym not in state:
                    fout.write(f"x{sym}\n" if w == 1 else f"b{'x'*w} {sym}\n")
            fout.write('$end\n')
            last_written_idx = iidx
            stats['n_times'] += 1

        for line in fin:
            s = line.strip()
            if not s:
                continue
            if not in_val:
                if s.startswith('$enddefinitions'):
                    in_val = True
                continue
            if s == '$dumpvars':
                in_dumpvars = True; continue
            if s == '$end' and in_dumpvars:
                in_dumpvars = False; continue
            if s.startswith('#'):
                try:
                    t = int(s[1:])
                except ValueError:
                    continue
                new_idx = _find_interval(t, merged_intervals, active_idx)
                if new_idx >= 0 and new_idx != last_written_idx:
                    write_dumpvars(new_idx, t)
                    active_idx = new_idx
                elif new_idx >= 0:
                    active_idx = new_idx
                    fout.write(f'#{t + interval_offsets[new_idx]}\n')
                    stats['n_times'] += 1
                else:
                    active_idx = -1
                continue
            if s.startswith('$'):
                continue
            if active_idx >= 0:
                fout.write(line)
                stats['n_changes'] += 1

    return stats


def build_tile_areas(tile_bounds, mx, ny):
    """Returns tile_area_um2[ny][mx]."""
    x_min, x_max, y_min, y_max = tile_bounds
    tile_w = (x_max - x_min) / mx
    tile_h = (y_max - y_min) / ny
    area = tile_w * tile_h
    return [[area] * mx for _ in range(ny)]
