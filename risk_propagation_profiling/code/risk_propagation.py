#!/usr/bin/env python3
"""
Risk Propagation Profiling — 热点传播风险评估

基于 Green 函数的 IR-drop 风险传播算法（Wen et al.），
支持三种可插拔传播核函数：欧氏距离、指数衰减、对数衰减。

输入：
  report.json — 来自 Traditional_Vector_Profiling，包含 power_matrix_mW[T][ny][mx]

输出：
  risk_<kernel>.json — 风险矩阵 risk_matrix[T][ny][mx] + worst_per_window[T]

用法：
  python code/risk_propagation.py \
      --report ../Traditional_Vector_Profiling/sim_result/report/report.json \
      --kernel all --alpha 5 \
      --output-dir sim_result/
"""

import argparse
import json
import math
import os
import time


# ══════════════════════════════════════════════════════════════════════════════
# 传播核函数
# ══════════════════════════════════════════════════════════════════════════════

def kernel_euclidean(dx, dy):
    """欧氏距离核：G = 1 / sqrt(dx² + dy²)"""
    d = math.sqrt(dx * dx + dy * dy)
    return 1.0 / d


def kernel_exponential(dx, dy):
    """指数衰减核：G = exp(-sqrt(dx² + dy²))"""
    d = math.sqrt(dx * dx + dy * dy)
    return math.exp(-d)


def kernel_logarithmic(dx, dy):
    """对数衰减核：G = 1 / ln(1 + sqrt(dx² + dy²))"""
    d = math.sqrt(dx * dx + dy * dy)
    return 1.0 / math.log(1.0 + d)


KERNELS = {
    'euclidean':   kernel_euclidean,
    'exponential': kernel_exponential,
    'logarithmic': kernel_logarithmic,
}


# ══════════════════════════════════════════════════════════════════════════════
# 预计算相对核矩阵
# ══════════════════════════════════════════════════════════════════════════════

def build_relative_kernel(ny, mx, alpha, kernel_func):
    """预计算相对传播核矩阵 G_rel[2*ny-1][2*mx-1]。

    G_rel[di + ny - 1][dj + mx - 1] 表示偏移 (di, dj) 处的核值。
    di, dj 范围: [-(ny-1), ny-1] × [-(mx-1), mx-1]

    当 di=0, dj=0 时使用 alpha（自影响因子）。
    """
    h = 2 * ny - 1
    w = 2 * mx - 1
    G = [[0.0] * w for _ in range(h)]

    for di in range(-(ny - 1), ny):
        for dj in range(-(mx - 1), mx):
            ri = di + ny - 1
            rj = dj + mx - 1
            if di == 0 and dj == 0:
                G[ri][rj] = alpha
            else:
                G[ri][rj] = kernel_func(di, dj)

    return G


# ══════════════════════════════════════════════════════════════════════════════
# 预计算归一化矩阵（分母）
# ══════════════════════════════════════════════════════════════════════════════

def build_normalization_map(ny, mx, G_rel):
    """对每个 tile (i, j)，计算 Σ G_rel[i-p, j-q] 对所有 (p, q) 的求和。

    即全 1 功率图与 G 的卷积结果，用于归一化。
    返回 norm[ny][mx]。
    """
    norm = [[0.0] * mx for _ in range(ny)]

    for i in range(ny):
        for j in range(mx):
            s = 0.0
            for p in range(ny):
                ri = i - p + ny - 1
                row = G_rel[ri]
                for q in range(mx):
                    rj = j - q + mx - 1
                    s += row[rj]
            norm[i][j] = s

    return norm


# ══════════════════════════════════════════════════════════════════════════════
# 计算单窗口风险评分
# ══════════════════════════════════════════════════════════════════════════════

def compute_risk_window(P_t, ny, mx, G_rel, norm):
    """对单个窗口的功率图 P_t[ny][mx] 计算风险评分 S_t[ny][mx]。

    S_t[i][j] = Σ_pq P_t[p][q] * G_rel[i-p, j-q]  /  norm[i][j]

    返回 (S_t, worst_score, worst_tile)
    """
    S_t = [[0.0] * mx for _ in range(ny)]
    worst_score = 0.0
    worst_tile = (0, 0)

    for i in range(ny):
        for j in range(mx):
            num = 0.0
            for p in range(ny):
                ri = i - p + ny - 1
                g_row = G_rel[ri]
                p_row = P_t[p]
                for q in range(mx):
                    rj = j - q + mx - 1
                    num += p_row[q] * g_row[rj]

            score = num / norm[i][j] if norm[i][j] > 0 else 0.0
            S_t[i][j] = round(score, 6)

            if score > worst_score:
                worst_score = score
                worst_tile = (i, j)

    return S_t, worst_score, worst_tile


# ══════════════════════════════════════════════════════════════════════════════
# 主流程
# ══════════════════════════════════════════════════════════════════════════════

def run_propagation(power_matrix, parameters, kernel_name, alpha):
    """运行单种核函数的完整传播流程。

    返回 (risk_matrix, worst_per_window, worst_tiles)
    """
    T = parameters['T']
    ny = parameters['ny']
    mx = parameters['mx']

    kernel_func = KERNELS[kernel_name]

    print(f'\n{"="*60}')
    print(f'核函数: {kernel_name}  alpha={alpha}  网格={ny}x{mx}  窗口数={T}')
    print(f'{"="*60}')

    # 预计算核矩阵
    t0 = time.time()
    G_rel = build_relative_kernel(ny, mx, alpha, kernel_func)
    print(f'  核矩阵预计算完成 ({2*ny-1}x{2*mx-1})  [{time.time()-t0:.2f}s]')

    # 预计算归一化
    t0 = time.time()
    norm = build_normalization_map(ny, mx, G_rel)
    print(f'  归一化矩阵计算完成  [{time.time()-t0:.2f}s]')

    # 逐窗口计算
    risk_matrix = []
    worst_per_window = []
    worst_tiles = []

    t0 = time.time()
    for t in range(T):
        S_t, w_score, w_tile = compute_risk_window(
            power_matrix[t], ny, mx, G_rel, norm
        )
        risk_matrix.append(S_t)
        worst_per_window.append(round(w_score, 6))
        worst_tiles.append(list(w_tile))

        if (t + 1) % 100 == 0 or t == T - 1:
            elapsed = time.time() - t0
            rate = (t + 1) / elapsed if elapsed > 0 else 0
            print(f'  窗口 {t+1}/{T}  [{elapsed:.1f}s, {rate:.1f} win/s]')

    return risk_matrix, worst_per_window, worst_tiles


def save_report(output_path, kernel_name, alpha, parameters,
                risk_matrix, worst_per_window, worst_tiles):
    """保存风险报告 JSON。"""
    report = {
        'kernel': kernel_name,
        'alpha': alpha,
        'parameters': parameters,
        'worst_per_window': worst_per_window,
        'worst_tiles': worst_tiles,
        'risk_matrix': risk_matrix,
    }

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(report, f)

    sz_mb = os.path.getsize(output_path) / 1e6
    print(f'  报告 → {output_path}  ({sz_mb:.1f} MB)')


def print_comparison(results):
    """打印多核函数比较表。"""
    print(f'\n{"="*60}')
    print('核函数比较摘要')
    print(f'{"="*60}')
    print(f'{"核函数":<15} {"最大风险分":>10} {"最差窗口":>8} {"最差Tile":>12}')
    print('-' * 50)
    for name, wpw, wt in results:
        max_idx = max(range(len(wpw)), key=lambda i: wpw[i])
        print(f'{name:<15} {wpw[max_idx]:>10.4f} {max_idx:>8} '
              f'({wt[max_idx][0]:>2},{wt[max_idx][1]:>2})')

    # top-10 窗口交集
    k = min(10, len(results[0][1]))
    sets = []
    for name, wpw, _ in results:
        ranked = sorted(range(len(wpw)), key=lambda i: wpw[i], reverse=True)
        sets.append(set(ranked[:k]))

    if len(sets) >= 2:
        common = sets[0]
        for s in sets[1:]:
            common = common & s
        print(f'\nTop-{k} 窗口交集大小: {len(common)} / {k}')
        if common:
            print(f'共同窗口: {sorted(common)}')


def main():
    p = argparse.ArgumentParser(
        description='风险传播分析：基于可插拔核函数的 IR-drop 热点传播'
    )
    p.add_argument('--report', required=True,
                   help='report.json 路径（来自 Traditional_Vector_Profiling）')
    p.add_argument('--kernel', default='all',
                   choices=['euclidean', 'exponential', 'logarithmic', 'all'],
                   help='传播核函数（默认: all）')
    p.add_argument('--alpha', type=float, default=5.0,
                   help='自影响因子（默认: 5.0）')
    p.add_argument('--output-dir', default='sim_result',
                   help='输出目录（默认: sim_result/）')
    args = p.parse_args()

    # 加载功率矩阵
    print(f'加载 {args.report} ...')
    with open(args.report) as f:
        data = json.load(f)

    power_matrix = data['power_matrix_mW']
    parameters = data['parameters']
    T = parameters['T']
    ny = parameters['ny']
    mx = parameters['mx']
    print(f'  功率矩阵: [{T}][{ny}][{mx}]')

    # 确定要运行的核函数
    if args.kernel == 'all':
        kernel_list = ['euclidean', 'exponential', 'logarithmic']
    else:
        kernel_list = [args.kernel]

    # 运行传播
    comparison = []
    for kname in kernel_list:
        risk_matrix, worst_per_window, worst_tiles = run_propagation(
            power_matrix, parameters, kname, args.alpha
        )

        out_path = os.path.join(args.output_dir, 'report', f'risk_{kname}.json')
        save_report(out_path, kname, args.alpha, parameters,
                    risk_matrix, worst_per_window, worst_tiles)

        comparison.append((kname, worst_per_window, worst_tiles))

    # 比较
    if len(comparison) > 1:
        print_comparison(comparison)

    print('\n完成。')


if __name__ == '__main__':
    main()
