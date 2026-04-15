#!/usr/bin/env python3
"""
Worst-K Windows Selection — 热点窗口选取与 VCD 裁剪

从风险报告中按阈值（默认 ≥ max_worst 的 60%）选取热点窗口生成压缩 VCD，
同时在报告中展示 top-k 最差窗口。
可独立于 risk_propagation_profiling 使用，只要输入 JSON 包含
worst_per_window[T] 和 parameters.t_max_ticks、parameters.T。

输入：
  risk_<kernel>.json — 来自 risk_propagation_profiling（或任意兼容格式）
  original.vcd      — 原始 VCD 文件

输出：
  worst_k_<kernel>.json — 选取报告（top-k 窗口索引、评分）
  worst_k_<kernel>.vcd  — 压缩 VCD（仅含 top-k 窗口时段）

用法：
  python code/select_worst_k.py \
      --risk-report ../risk_propagation_profiling/sim_result/report/risk_euclidean.json \
      --top-k 10 \
      --vcd ../Traditional_Vector_Profiling/sim_result/vcd/traditional.vcd \
      --output-dir sim_result/
"""

import argparse
import json
import os
import re
import sys


# ══════════════════════════════════════════════════════════════════════════════
# VCD 裁剪工具（来自 Traditional_Vector_Profiling/code/unused/vcd_splice.py）
# ══════════════════════════════════════════════════════════════════════════════

def expand_and_merge(selected_indices, T, t_max, warmup_ticks):
    """将窗口索引集合扩展为带预热的时钟区间并合并重叠。

    Args:
        selected_indices: 被选中的窗口索引列表
        T: 总窗口数
        t_max: 最大时钟数
        warmup_ticks: 预热时钟数

    Returns:
        merged: 合并后的 (start, end) 区间列表
    """
    win_size = t_max / T
    intervals = []
    for j in sorted(selected_indices):
        win_start = int(j * win_size)
        win_end = int((j + 1) * win_size)
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


def _parse_vc_line(s):
    """解析单行 VCD value change。"""
    m = re.match(r'^([01xzXZ])(.+)$', s)
    if m:
        return m.group(2), s
    m = re.match(r'^b([01xzXZ]+)\s+(.+)$', s)
    if m:
        return m.group(2).strip(), s
    return None


def _find_interval(t, intervals, hint):
    """快速查找时间戳 t 所属的区间索引。"""
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


def splice_vcd_v2(vcd_path, merged_intervals, output_path):
    """两遍 VCD 裁剪：提取选定区间并重映射时间。

    第一遍：收集每个区间边界处的信号状态（hold-last-value）。
    第二遍：在每个区间入口写 $dumpvars，然后写区间内的 value changes。
    """
    if not merged_intervals:
        return {}

    # 解析 header
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

    # 时间偏移表
    interval_offsets = []
    cumulative = 0
    for start, end in merged_intervals:
        interval_offsets.append(cumulative - start)
        cumulative += (end - start)

    stats = {'n_changes': 0, 'n_times': 0,
             'n_segments': len(merged_intervals),
             'total_output_ticks': cumulative}

    # 第一遍：收集每段入口的 hold-last-value 状态 + 段内出现过 value change 的信号集合
    # （只 dump 段内真正变化的信号，避免大规模电路下 dumpvars 冗余开销）
    boundary_states = {}
    segment_signals = [set() for _ in merged_intervals]
    last_values = {}
    next_boundary = 0
    cur_seg = -1  # 当前时间戳所属段索引（-1 表示不在任何段内）

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
                in_dv = True
                continue
            if s == '$end' and in_dv:
                in_dv = False
                continue
            if s.startswith('#'):
                try:
                    t = int(s[1:])
                except ValueError:
                    continue
                # 到达或越过若干段边界 → 为每个被越过的段记录入口状态
                while (next_boundary < len(merged_intervals) and
                       t >= merged_intervals[next_boundary][0]):
                    boundary_states[next_boundary] = dict(last_values)
                    next_boundary += 1
                # 判断当前时间戳落在哪个段
                cur_seg = _find_interval(t, merged_intervals, cur_seg)
                continue
            if s.startswith('$'):
                continue
            parsed = _parse_vc_line(s)
            if parsed:
                sym, raw = parsed
                last_values[sym] = raw
                if cur_seg >= 0:
                    segment_signals[cur_seg].add(sym)

    while next_boundary < len(merged_intervals):
        boundary_states[next_boundary] = dict(last_values)
        next_boundary += 1

    total_active = sum(len(s) for s in segment_signals)
    n_all = len(sym_width)
    print(f'  边界状态: {len(boundary_states)} 个区间')
    print(f'  段内活跃信号: 合计 {total_active}  (全量 {n_all} × {len(merged_intervals)}段'
          f' = {n_all*len(merged_intervals)}，裁剪比 '
          f'{100*(1 - total_active/max(1, n_all*len(merged_intervals))):.1f}%)')

    # 第二遍：写输出 VCD
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
            active = segment_signals[iidx]
            # 仅 dump 段内实际发生 value change 的信号入口值
            # 段内无变化的信号：toggle 数固定为 0，initial value 不影响功耗分析
            for sym in sorted(active):
                if sym in state:
                    fout.write(state[sym] + '\n')
                else:
                    # 段内首次变化前无已知值：用 x 占位，交由段内首次 VC 覆盖
                    w = sym_width.get(sym, 1)
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
                in_dumpvars = True
                continue
            if s == '$end' and in_dumpvars:
                in_dumpvars = False
                continue
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


# ══════════════════════════════════════════════════════════════════════════════
# Top-K 选取
# ══════════════════════════════════════════════════════════════════════════════

def _entry(idx, worst_per_window, worst_tiles, max_score):
    e = {
        'window_idx': idx,
        'worst_score': worst_per_window[idx],
        'score_ratio': (worst_per_window[idx] / max_score) if max_score > 0 else 0.0,
    }
    if worst_tiles is not None:
        e['worst_tile'] = worst_tiles[idx]
    return e


def select_top_k(worst_per_window, worst_tiles, k):
    """选取 top-k 最差窗口（仅用于报告）。"""
    T = len(worst_per_window)
    k = min(k, T)
    max_score = max(worst_per_window) if T else 0.0
    ranked = sorted(range(T), key=lambda i: worst_per_window[i], reverse=True)
    return [_entry(i, worst_per_window, worst_tiles, max_score) for i in ranked[:k]]


def select_hotspots(worst_per_window, worst_tiles, threshold_ratio):
    """选取热点窗口：评分 ≥ threshold_ratio × max(worst_per_window)。

    Args:
        threshold_ratio: 阈值比例（如 0.6 表示 ≥ 最差值 60%）

    Returns:
        hotspots: 按评分降序排列的窗口条目列表
        max_score: 最差评分
        threshold: 实际阈值分数
    """
    T = len(worst_per_window)
    if T == 0:
        return [], 0.0, 0.0
    max_score = max(worst_per_window)
    threshold = threshold_ratio * max_score
    selected = [i for i in range(T) if worst_per_window[i] >= threshold]
    selected.sort(key=lambda i: worst_per_window[i], reverse=True)
    return ([_entry(i, worst_per_window, worst_tiles, max_score) for i in selected],
            max_score, threshold)


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

def main():
    p = argparse.ArgumentParser(
        description='最差窗口选取：从风险报告中选取 top-k 窗口并生成压缩 VCD'
    )
    p.add_argument('--risk-report', required=True,
                   help='风险报告 JSON 路径（需含 worst_per_window 和 parameters）')
    p.add_argument('--threshold-ratio', type=float, default=0.6,
                   help='热点阈值比例：评分 ≥ ratio × max(worst) 的窗口被选中（默认: 0.6）')
    p.add_argument('--top-k', type=int, default=10,
                   help='报告中附加展示的 top-k 窗口数（仅用于报告，不影响 VCD 选取；默认: 10）')
    p.add_argument('--vcd', required=True,
                   help='原始 VCD 文件路径')
    p.add_argument('--warmup-ticks', type=int, default=0,
                   help='每个窗口前的预热时钟数（默认: 0）')
    p.add_argument('--output-dir', default='sim_result',
                   help='输出目录（默认: sim_result/）')
    args = p.parse_args()

    # 加载风险报告
    print(f'加载 {args.risk_report} ...')
    with open(args.risk_report) as f:
        data = json.load(f)

    worst_per_window = data['worst_per_window']
    worst_tiles = data.get('worst_tiles')
    parameters = data['parameters']
    kernel_name = data.get('kernel', 'unknown')
    T = parameters['T']
    t_max = parameters['t_max_ticks']

    print(f'  核函数: {kernel_name}  窗口数: {T}  t_max: {t_max}')

    # 阈值选取热点（用于 VCD 裁剪）
    hotspots, max_score, threshold = select_hotspots(
        worst_per_window, worst_tiles, args.threshold_ratio)
    # Top-K（仅用于报告展示）
    top_k_list = select_top_k(worst_per_window, worst_tiles, args.top_k)

    print(f'\n最差评分: {max_score:.4f}   阈值 (≥{args.threshold_ratio*100:.0f}%): {threshold:.4f}')
    print(f'命中热点窗口: {len(hotspots)} / {T}  '
          f'(时间占比 {len(hotspots)/T*100:.1f}%)')

    def _print_rows(rows):
        print(f'  {"排名":>4}  {"窗口":>6}  {"评分":>10}  {"占比":>7}  {"Tile":>10}')
        print('  ' + '-' * 46)
        for rank, entry in enumerate(rows, 1):
            tile_str = f'({entry["worst_tile"][0]},{entry["worst_tile"][1]})' \
                if 'worst_tile' in entry else 'N/A'
            print(f'  {rank:>4}  {entry["window_idx"]:>6}  '
                  f'{entry["worst_score"]:>10.4f}  '
                  f'{entry["score_ratio"]*100:>6.1f}%  {tile_str:>10}')

    print(f'\nTop-{args.top_k} 最差窗口（报告用）:')
    _print_rows(top_k_list)

    show_n = min(len(hotspots), 20)
    print(f'\n热点窗口（前 {show_n} / {len(hotspots)}）:')
    _print_rows(hotspots[:show_n])

    # 保存选取报告
    report_path = os.path.join(args.output_dir, 'report',
                               f'worst_k_{kernel_name}.json')
    os.makedirs(os.path.dirname(os.path.abspath(report_path)), exist_ok=True)

    report = {
        'kernel': kernel_name,
        'threshold_ratio': args.threshold_ratio,
        'threshold_score': threshold,
        'max_score': max_score,
        'n_hotspots': len(hotspots),
        'top_k': args.top_k,
        'warmup_ticks': args.warmup_ticks,
        'parameters': parameters,
        'hotspot_windows': hotspots,
        'top_k_windows': top_k_list,
    }
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    print(f'\n选取报告 → {report_path}')

    # VCD 裁剪（使用热点窗口）
    selected_indices = [e['window_idx'] for e in hotspots]
    if not selected_indices:
        print('\n未命中任何热点窗口，跳过 VCD 裁剪。')
        return
    merged = expand_and_merge(selected_indices, T, t_max, args.warmup_ticks)

    print(f'\n区间合并: {len(selected_indices)} 个窗口 → {len(merged)} 个区间')
    for i, (s, e) in enumerate(merged):
        print(f'  区间 {i+1}: #{s} ~ #{e}  '
              f'(长度 {e-s} ticks)')

    vcd_out = os.path.join(args.output_dir, 'vcd',
                           f'worst_k_{kernel_name}.vcd')
    os.makedirs(os.path.dirname(os.path.abspath(vcd_out)), exist_ok=True)

    print(f'\n裁剪 VCD: {args.vcd} → {vcd_out}')
    stats = splice_vcd_v2(args.vcd, merged, vcd_out)

    sz_kb = os.path.getsize(vcd_out) / 1e3
    print(f'  输出 VCD: {sz_kb:.1f} KB')
    print(f'  统计: {stats}')
    print('\n完成。')


if __name__ == '__main__':
    main()
