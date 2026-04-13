#!/usr/bin/env python3
"""
Worst-Case Power Noise Window Selection
=======================================

Implementation of the RC-Tile + Phase-Aware worst-case window selection
algorithm. See ../docs/algorithm_worst_window_lite.md for the full spec.

Pipeline:
    Stage 1  ClockCycleAggregation        — toggle JSONL → per-cycle c_i
    Stage 2  PhaseDetection               — binary active threshold + merge
    Stage 3  RCWeightedFingerprint        — I_k * R_k → P_t^total + sigma_top3
    Stage 4  PhaseDrivenWindowGeneration  — rho depletion sampling per phase
    Stage 5  Window scoring + VCD splice  — sum e_t per window, output VCD

Inputs:
    --location  signal_location_map.csv (with optional c_load, r_net columns)
    --toggles   toggle JSONL (output of jsonl_toggle_mark.py)
    --vcd       original VCD (for splicing)

Optional:
    --spef      SPEF file (will be parsed and joined into the location CSV)

Usage example:
    python code/find_worst_window.py \
        --location output/signal_location_rc.csv \
        --toggles  output/test_toggles.jsonl \
        --vcd      input.vcd \
        --clock-ns 50 --timescale-ps 10 \
        --n-grid 8 --k-theta 1.0 --rho 0.7 --eta 0.15 \
        --output   sim_result/vcd/worst_window.vcd \
        --html     sim_result/report/worst_window.html \
        --json-out sim_result/report/worst_window.json
"""
import argparse
import csv
import json
import math
import os
import re
import statistics
import sys
from pathlib import Path


# ═════════════════════════════════════════════════════════════════════
#  Data Loading
# ═════════════════════════════════════════════════════════════════════

def load_locations(csv_path: str) -> dict:
    """Load signal -> {x_um, y_um, c_load, r_net} from CSV.

    c_load / r_net columns are optional. Missing → defaults (1.0, 0.0).
    """
    loc = {}
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row["signal_name"]
            if not row.get("x_um") or not row.get("y_um"):
                continue
            try:
                x = float(row["x_um"])
                y = float(row["y_um"])
            except ValueError:
                continue
            c_load = row.get("c_load", "")
            r_net = row.get("r_net", "")
            try:
                c = float(c_load) if c_load else 1.0
            except ValueError:
                c = 1.0
            try:
                r = float(r_net) if r_net else 0.0
            except ValueError:
                r = 0.0
            loc[name] = {"x": x, "y": y, "c_load": c, "r_net": r}
    return loc


# ═════════════════════════════════════════════════════════════════════
#  Tile Mapping (fixed N_grid)
# ═════════════════════════════════════════════════════════════════════

def build_tile_map(locations: dict, n_grid: int):
    """Assign each signal to a tile index k in [0, N_grid^2).

    Returns:
        signal_to_tile: {signal_name: k}
        bbox: (x_min, x_max, y_min, y_max, L_tile_x, L_tile_y)
    """
    xs = [v["x"] for v in locations.values()]
    ys = [v["y"] for v in locations.values()]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)

    dx = (x_max - x_min) * 0.001 or 1.0
    dy = (y_max - y_min) * 0.001 or 1.0
    x_max += dx
    y_max += dy

    L_tile_x = (x_max - x_min) / n_grid
    L_tile_y = (y_max - y_min) / n_grid

    signal_to_tile = {}
    for name, info in locations.items():
        ix = min(int((info["x"] - x_min) / L_tile_x), n_grid - 1)
        iy = min(int((info["y"] - y_min) / L_tile_y), n_grid - 1)
        signal_to_tile[name] = iy * n_grid + ix
    return signal_to_tile, (x_min, x_max, y_min, y_max, L_tile_x, L_tile_y)


def aggregate_tile_resistance(locations: dict,
                              signal_to_tile: dict,
                              n_grid: int):
    """Compute hat_R_k = clip(R_k / median(R_k), 0.5, 2.5).

    R_k = mean(r_net) over signals in tile k. Tiles with no r_net data
    or all-zero get hat_R_k = 1.0.
    """
    K = n_grid * n_grid
    sum_r = [0.0] * K
    cnt_r = [0] * K
    for name, info in locations.items():
        r = info.get("r_net", 0.0)
        if r <= 0:
            continue
        k = signal_to_tile.get(name)
        if k is None:
            continue
        sum_r[k] += r
        cnt_r[k] += 1

    R_k = [0.0] * K
    for k in range(K):
        if cnt_r[k] > 0:
            R_k[k] = sum_r[k] / cnt_r[k]

    nonzero = [r for r in R_k if r > 0]
    if not nonzero:
        return [1.0] * K, False
    med = statistics.median(nonzero)
    hat_R = []
    for r in R_k:
        if r <= 0:
            hat_R.append(1.0)
        else:
            v = r / med if med > 0 else 1.0
            hat_R.append(max(0.5, min(2.5, v)))
    return hat_R, True


# ═════════════════════════════════════════════════════════════════════
#  Stage 1: Clock Cycle Aggregation
#  Stage 3: RC-Weighted Fingerprint
#  (Combined into a single JSONL pass for efficiency)
# ═════════════════════════════════════════════════════════════════════

def aggregate_and_fingerprint(jsonl_path: str,
                              locations: dict,
                              signal_to_tile: dict,
                              hat_R: list,
                              n_grid: int,
                              clock_ns: float,
                              timescale_ps: float):
    """Single pass over toggle JSONL.

    Computes:
        c_i           — per-cycle raw toggle total (for phase detection)
        I_tk[i][k]    — weighted current proxy per (cycle, tile)
        sig_toggles   — per-signal total toggle (for visualization)
        sig_cycle_tg  — per-signal per-cycle toggle (sparse, for HTML)
        t_max_ticks   — max VCD tick

    Note: We size arrays after a first scan to find the cycle count.
    """
    K = n_grid * n_grid
    clock_ticks = int(round(clock_ns * 1000.0 / timescale_ps))
    if clock_ticks <= 0:
        print("ERROR: clock_ticks computed as 0; check --clock-ns / "
              "--timescale-ps", file=sys.stderr)
        sys.exit(1)

    # First pass: find t_max
    t_max = 0
    n_lines = 0
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            n_lines += 1
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            t = rec.get("time", 0)
            if t > t_max:
                t_max = t
    if t_max == 0:
        print("ERROR: empty toggle JSONL", file=sys.stderr)
        sys.exit(1)

    N_c = (t_max // clock_ticks) + 1
    c_i = [0] * N_c                              # raw toggle per cycle
    I_tk = [[0.0] * K for _ in range(N_c)]       # weighted current per tile
    sig_toggles = {}

    # Second pass: accumulate
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            t = rec.get("time", 0)
            i = min(t // clock_ticks, N_c - 1)
            row_I = I_tk[i]
            row_c = 0
            for sig, val in rec.get("signals", {}).items():
                tc = val.count("1")
                if tc == 0:
                    continue
                row_c += tc
                sig_toggles[sig] = sig_toggles.get(sig, 0) + tc
                k = signal_to_tile.get(sig)
                if k is None:
                    continue
                info = locations.get(sig)
                w_s = info["c_load"] if info else 1.0
                row_I[k] += tc * w_s
            c_i[i] += row_c

    # Apply tile resistance: P_t,k = I_t,k * hat_R_k
    P_tk = [[I_tk[i][k] * hat_R[k] for k in range(K)] for i in range(N_c)]

    return {
        "c_i": c_i,
        "I_tk": I_tk,
        "P_tk": P_tk,
        "N_c": N_c,
        "K": K,
        "t_max_ticks": t_max,
        "clock_ticks": clock_ticks,
        "sig_toggles": sig_toggles,
        "n_lines": n_lines,
    }


def compute_scores(P_tk: list, N_c: int, K: int, *,
                   score_mode="peak",
                   n_grid=None,
                   neighbor_alpha=1.0,
                   cluster_k=1):
    """For each cycle, compute P_total, sigma_top3, e_t.

    e_t physical meaning (modification #1, peak-tile form):
        e_t[i] = max_k P_t,k[i]
    i.e. the worst single-tile instantaneous power in cycle i.
    IR drop is a *local* failure mode — what matters is the hottest
    tile, not the chip-wide sum. P_total / sigma_top3 are kept for
    diagnostics / visualization only.

    score_mode:
        "peak"     — original behaviour (default, backward-compatible)
        "neighbor" — m5a: Q_k = alpha*P_k + (1-alpha)*mean(P_neighbors),
                     e_t[i] = max_k Q_k  (requires n_grid)
        "cluster"  — m5b: e_t[i] = mean of top cluster_k tiles by P_t,k

    Returns: lists [P_total], [sigma_top3], [e_t] of length N_c.
    """
    P_total = [0.0] * N_c
    sigma_top3 = [0.0] * N_c
    e_t = [0.0] * N_c

    # Pre-compute neighbor list once for "neighbor" mode (m5a).
    # Uses actual neighbor count per tile: corner=3, edge=5, interior=8.
    neighbor_list = None
    if score_mode == "neighbor":
        N = n_grid
        neighbor_list = []
        for k in range(K):
            iy, ix = divmod(k, N)
            nbrs = []
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dy == 0 and dx == 0:
                        continue
                    ny, nx = iy + dy, ix + dx
                    if 0 <= ny < N and 0 <= nx < N:
                        nbrs.append(ny * N + nx)
            neighbor_list.append(nbrs)

    for i in range(N_c):
        row = P_tk[i]
        nonempty = [v for v in row if v > 0]
        total = sum(nonempty)
        P_total[i] = total
        if total <= 0:
            sigma_top3[i] = 0.0
            e_t[i] = 0.0
            continue
        if len(nonempty) >= 3:
            top3 = sorted(nonempty, reverse=True)[:3]
            sigma_top3[i] = sum(top3) / total
        else:
            sigma_top3[i] = 1.0

        if score_mode == "neighbor":
            alpha = neighbor_alpha
            best = 0.0
            for k in range(K):
                pk = row[k]
                nbrs = neighbor_list[k]
                nb_mean = sum(row[j] for j in nbrs) / len(nbrs) if nbrs else 0.0
                q = alpha * pk + (1.0 - alpha) * nb_mean
                if q > best:
                    best = q
            e_t[i] = best
        elif score_mode == "cluster":
            sorted_vals = sorted(row, reverse=True)
            top = [v for v in sorted_vals[:cluster_k] if v > 0]
            e_t[i] = (sum(top) / len(top)) if top else 0.0
        else:  # peak (default)
            e_t[i] = max(nonempty)

    return P_total, sigma_top3, e_t


# ═════════════════════════════════════════════════════════════════════
#  Stage 2: Phase Detection (binary, single threshold)
# ═════════════════════════════════════════════════════════════════════

def detect_phases(c_i: list, k_theta: float,
                  gap: int, n_min: int):
    """Two-level phase detection.

    Returns:
        phases: list of (i_start, i_end_exclusive)
        theta:  the active threshold used
    """
    nonzero = [c for c in c_i if c > 0]
    if not nonzero:
        return [], 0.0
    med = statistics.median(nonzero)
    theta = k_theta * med
    a = [1 if c > theta else 0 for c in c_i]

    # Merge consecutive 1-runs, allowing gaps of length <= `gap`
    phases = []
    i = 0
    N = len(a)
    while i < N:
        if a[i] != 1:
            i += 1
            continue
        # Start of a phase
        start = i
        end = i + 1
        while end < N:
            if a[end] == 1:
                end += 1
                continue
            # Check gap
            j = end
            while j < N and a[j] == 0:
                j += 1
            run0 = j - end
            if run0 <= gap and j < N:
                # Absorb the gap
                end = j
                continue
            break
        if (end - start) >= n_min:
            phases.append((start, end))
        i = end
    return phases, theta


# ═════════════════════════════════════════════════════════════════════
#  Stage 4: Phase-Driven Window Generation
# ═════════════════════════════════════════════════════════════════════

def pick_top_k_in_phase(ps: int, pe: int, e_t: list,
                        k_min: int, top_k: int, min_gap: int,
                        N_c: int,
                        beta_budget: float = 0.0,
                        n_total: int = 0) -> list:
    """Greedy non-overlapping argmax small windows inside one phase.

    Dual-termination (modification m4):
      - top_k > 0 and beta_budget == 0  → stop after top_k picks (m3)
      - top_k == 0 and beta_budget > 0  → stop when accumulated cycles / n_total
                                          would exceed beta_budget
      - top_k > 0 and beta_budget > 0   → both act as upper bounds; first
                                          satisfied stops the loop
      - top_k == 0 and beta_budget == 0 → fallback: treat as top_k=1 (m2)

    Window length is always L = 2*k_min + 1.
    Centers are chosen greedily: pick argmax of available cycles, then mask
    out ±min_gap cycles, repeat.
    """
    L = 2 * k_min + 1
    half = k_min
    phase_len = pe - ps
    mask = bytearray([1] * phase_len)  # 1 = available for picking

    # Fallback: both controls disabled → behave as top_k=1
    effective_top_k = top_k if (top_k > 0 or beta_budget > 0) else 1

    picks = []
    accum_cycles = 0

    while True:
        # Termination: top-K limit
        if effective_top_k > 0 and len(picks) >= effective_top_k:
            break
        # Termination: beta-budget limit (checked before adding next window)
        if beta_budget > 0 and n_total > 0 and len(picks) >= 1:
            if (accum_cycles + L) / n_total > beta_budget:
                break

        # Find argmax inside mask
        best_local, best_val = -1, float('-inf')
        for i in range(phase_len):
            if mask[i] and e_t[ps + i] > best_val:
                best_val = e_t[ps + i]
                best_local = i
        if best_local < 0:
            break  # no available cycle left

        picks.append(best_local)
        accum_cycles += L
        # Mask out ±min_gap neighbourhood to enforce separation
        for i in range(max(0, best_local - min_gap),
                       min(phase_len, best_local + min_gap + 1)):
            mask[i] = 0

    lo_clip = max(0, ps - 1)
    hi_clip = min(N_c, pe + 1)
    out = []
    for local in picks:
        c_star = ps + local
        wi_start = c_star - half
        wi_end = wi_start + L
        # Clip to phase ± 1 cycle
        if wi_start < lo_clip:
            wi_start = lo_clip
            wi_end = wi_start + L
        if wi_end > hi_clip:
            wi_end = hi_clip
            wi_start = max(lo_clip, wi_end - L)
        if wi_end - wi_start >= 1:
            out.append((wi_start, wi_end))
    return out


def generate_windows(phases: list,
                     N_c: int,
                     clock_ticks: int,
                     rho: float,
                     eta: float,
                     k_min: int,
                     e_t: list = None,
                     small_window: bool = False,
                     top_k: int = 0,
                     min_gap: int = 10,
                     beta_budget: float = 0.0):
    """Per phase, emit one window centered at depletion point t_s + rho*D.

    Window length n_j = max(K_min, ceil(2*eta*D_j)) cycles.

    Self-tune mode (modification m1b): if ``rho < 0`` and ``e_t`` is
    provided, the center is picked as ``argmax(e_t[ps:pe])`` — i.e. the
    phase-local peak of the peak-tile score — instead of the fixed
    fractional point ``ps + rho*D``. No new hyper-parameter.

    Small-window mode (modification m2, flag ``small_window``): overrides
    both ρ-center and η-length.  The window collapses to
    ``[c* - k_min, c* + k_min + 1]``, length ``L = 2*k_min + 1`` cycles,
    centered on ``c* = argmax(e_t[ps:pe])``.  Forces self-tune center.
    Rationale: delegate the time-integral to Innovus; keep only the
    instantaneous peak-tile argmax and let dynamic rail analysis find
    the true ns-resolution worst inside this tight bracket.

    Top-K mode (modification m3, ``top_k > 0``): only effective with
    ``small_window=True``.  Emits up to ``top_k`` non-overlapping windows
    per phase via greedy argmax with ``min_gap`` cycle separation between
    centers.

    Budget mode (modification m4, ``beta_budget > 0``): only effective with
    ``small_window=True``.  Continues picking until accumulated window cycles
    / N_c would exceed beta_budget.  ``top_k=0`` with ``beta_budget > 0``
    uses pure budget termination; both > 0 means first limit wins.
    ``top_k=0`` and ``beta_budget=0`` falls back to top_k=1 (m2 behaviour).

    Returns: list of (i_start, i_end_exclusive) — both in cycle units.
    """
    if small_window and min_gap < 2 * k_min + 1:
        print(f"  WARNING: --min-gap-cycles ({min_gap}) < window length "
              f"({2 * k_min + 1}); windows may overlap.", file=sys.stderr)

    self_tune = small_window or ((rho < 0) and (e_t is not None))
    windows = []
    for (ps, pe) in phases:
        D = pe - ps
        if D <= 0:
            continue
        if small_window:
            subset = pick_top_k_in_phase(ps, pe, e_t, k_min, top_k,
                                         min_gap, N_c,
                                         beta_budget=beta_budget,
                                         n_total=N_c)
            # Warn when top-K mode requested fewer picks than possible
            if top_k > 0 and len(subset) < top_k:
                print(f"  WARNING: Phase [{ps},{pe}]: only {len(subset)} "
                      f"< {top_k} picks available", file=sys.stderr)
            windows.extend(subset)
        else:
            n_j = max(k_min, math.ceil(2.0 * eta * D))
            # Center cycle index (float)
            if self_tune and e_t is not None:
                seg = e_t[ps:pe]
                # argmax inside phase, fall back to ps on empty
                local = max(range(len(seg)), key=lambda i: seg[i]) if seg else 0
                center = float(ps + local)
            else:
                center = ps + rho * D
            half = n_j / 2.0
            wi_start = int(round(center - half))
            wi_end = wi_start + n_j
            # Clip to phase ± 1 cycle
            lo = max(0, ps - 1)
            hi = min(N_c, pe + 1)
            if wi_start < lo:
                wi_start = lo
                wi_end = wi_start + n_j
            if wi_end > hi:
                wi_end = hi
                wi_start = max(lo, wi_end - n_j)
            if wi_end - wi_start < 1:
                continue
            windows.append((wi_start, wi_end))
    return windows


def score_windows(windows: list, e_t: list):
    """Modification #1: window score = max e_t in window (not sum).

    Rationale: combined with the peak-tile e_t in compute_scores, the
    final ranking key is

        S(W) = max_{t in W}  max_k  P_t,k

    i.e. the single worst (cycle, tile) pair contained in the window.
    This is the physical driver of the local IR drop peak; an integral
    over many moderate cycles can no longer dilute one true hotspot.
    """
    scored = []
    for (s, e) in windows:
        sc = max(e_t[s:e]) if e > s else 0.0
        scored.append({"start": s, "end": e, "score": sc})
    scored.sort(key=lambda x: -x["score"])
    return scored


def windows_to_tick_intervals(windows: list, clock_ticks: int):
    """Convert (start_cycle, end_cycle) to (start_tick, end_tick) intervals.

    Sorted by start_tick, no merging (phases are already disjoint).
    """
    iv = sorted([(s * clock_ticks, e * clock_ticks) for (s, e) in windows])
    return iv


# ═════════════════════════════════════════════════════════════════════
#  VCD Splicing (adapted from spatial_temporal_select.py)
# ═════════════════════════════════════════════════════════════════════

def _parse_vc_line(s: str):
    m = re.match(r"^([01xzXZ])(.+)$", s)
    if m:
        return m.group(2), s
    m = re.match(r"^b([01xzXZ]+)\s+(.+)$", s)
    if m:
        return m.group(2).strip(), s
    return None


def _find_interval(t: int, intervals: list, hint: int) -> int:
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


def splice_vcd(vcd_path: str, intervals: list, output_path: str) -> dict:
    """Two-pass VCD splicer with hold-last-value boundary state."""
    if not intervals:
        return {}

    sym_width = {}
    header_lines = []
    with open(vcd_path, "r", encoding="utf-8") as f:
        for line in f:
            header_lines.append(line)
            s = line.strip()
            m = re.match(r"\$var\s+\S+\s+(\d+)\s+(\S+)\s+", s)
            if m:
                sym_width[m.group(2)] = int(m.group(1))
            if s.startswith("$enddefinitions"):
                break

    interval_offsets = []
    cumulative = 0
    for (st, en) in intervals:
        interval_offsets.append(cumulative - st)
        cumulative += (en - st)

    stats = {"n_changes": 0, "n_times": 0, "n_segments": len(intervals),
             "total_output_ticks": cumulative}

    # Pass 1: capture boundary states
    boundary_states = {}
    last_values = {}

    with open(vcd_path, "r", encoding="utf-8") as f:
        in_val = False
        in_dv = False
        next_b = 0
        for line in f:
            s = line.strip()
            if not s:
                continue
            if not in_val:
                if s.startswith("$enddefinitions"):
                    in_val = True
                continue
            if s == "$dumpvars":
                in_dv = True
                continue
            if s == "$end" and in_dv:
                in_dv = False
                continue
            if s.startswith("#"):
                try:
                    t = int(s[1:])
                except ValueError:
                    continue
                while next_b < len(intervals) and t >= intervals[next_b][0]:
                    boundary_states[next_b] = dict(last_values)
                    next_b += 1
                if next_b >= len(intervals):
                    break
                continue
            if s.startswith("$"):
                continue
            parsed = _parse_vc_line(s)
            if parsed:
                sym, raw = parsed
                last_values[sym] = raw
        while next_b < len(intervals):
            boundary_states[next_b] = dict(last_values)
            next_b += 1

    # Pass 2: write output
    with open(vcd_path, "r", encoding="utf-8") as fin, \
         open(output_path, "w", encoding="utf-8") as fout:
        for hl in header_lines:
            fout.write(hl)
        fout.write("\n")

        in_val = False
        in_dv = False
        active = -1
        last_written = -1

        def write_dumpvars(idx, t):
            nonlocal last_written
            seg_num = idx + 1
            s_tick, e_tick = intervals[idx]
            fout.write(f"$comment segment {seg_num}: "
                       f"#{s_tick}~#{e_tick} $end\n")
            out_t = t + interval_offsets[idx]
            fout.write(f"#{out_t}\n")
            fout.write("$dumpvars\n")
            state = boundary_states.get(idx, {})
            for sym in sorted(state.keys()):
                fout.write(state[sym] + "\n")
            for sym, w in sym_width.items():
                if sym not in state:
                    if w == 1:
                        fout.write(f"x{sym}\n")
                    else:
                        fout.write(f"b{'x' * w} {sym}\n")
            fout.write("$end\n")
            last_written = idx
            stats["n_times"] += 1

        for line in fin:
            s = line.strip()
            if not s:
                continue
            if not in_val:
                if s.startswith("$enddefinitions"):
                    in_val = True
                continue
            if s == "$dumpvars":
                in_dv = True
                continue
            if s == "$end" and in_dv:
                in_dv = False
                continue
            if s.startswith("#"):
                try:
                    t = int(s[1:])
                except ValueError:
                    continue
                new_idx = _find_interval(t, intervals, active)
                if new_idx >= 0 and new_idx != last_written:
                    write_dumpvars(new_idx, t)
                    active = new_idx
                elif new_idx >= 0:
                    active = new_idx
                    out_t = t + interval_offsets[new_idx]
                    fout.write(f"#{out_t}\n")
                    stats["n_times"] += 1
                else:
                    active = -1
                continue
            if s.startswith("$"):
                continue
            if active >= 0:
                fout.write(line)
                stats["n_changes"] += 1

    return stats


# ═════════════════════════════════════════════════════════════════════
#  HTML Visualization
# ═════════════════════════════════════════════════════════════════════

def generate_html(html_path: str, args, ctx, scores):
    """4-panel HTML: timeline (c_i), e_t timeline, tile heatmap, phase table."""
    c_i = ctx["c_i"]
    e_t = ctx["e_t"]
    P_total = ctx["P_total"]
    sigma_top3 = ctx["sigma_top3"]
    hat_R = ctx["hat_R"]
    P_tk = ctx["P_tk"]
    N_c = ctx["N_c"]
    K = ctx["K"]
    n_grid = ctx["n_grid"]
    phases = ctx["phases"]
    windows = ctx["windows"]
    theta = ctx["theta"]
    bbox = ctx["bbox"]

    timescale_ns = args.timescale_ps / 1000.0
    cycle_ns = args.clock_ns
    times_ns = [round(i * cycle_ns, 2) for i in range(N_c)]

    # Color cycles by selection
    selected_cycles = set()
    for (s, e) in windows:
        for i in range(s, e):
            selected_cycles.add(i)
    bar_colors = ["rgba(255,80,80,0.85)" if i in selected_cycles
                  else "rgba(100,149,237,0.55)" for i in range(N_c)]

    # Phase shapes
    phase_shapes = []
    for ps, pe in phases:
        s_ns = ps * cycle_ns
        e_ns = pe * cycle_ns
        phase_shapes.append(
            f'{{"type":"rect","xref":"x","yref":"paper",'
            f'"x0":{s_ns},"x1":{e_ns},"y0":0,"y1":1,'
            f'"fillcolor":"rgba(255,215,0,0.10)",'
            f'"line":{{"color":"gold","width":1,"dash":"dot"}},'
            f'"layer":"below"}}'
        )

    # Window shapes
    window_shapes = []
    for ws, we in windows:
        s_ns = ws * cycle_ns
        e_ns = we * cycle_ns
        window_shapes.append(
            f'{{"type":"rect","xref":"x","yref":"paper",'
            f'"x0":{s_ns},"x1":{e_ns},"y0":0,"y1":1,'
            f'"fillcolor":"rgba(255,80,80,0.18)",'
            f'"line":{{"color":"#e94560","width":2}},'
            f'"layer":"below"}}'
        )

    # Aggregate tile P_total over all cycles for the heatmap
    P_grid = [[0.0] * n_grid for _ in range(n_grid)]
    for i in range(N_c):
        for k in range(K):
            iy = k // n_grid
            ix = k % n_grid
            P_grid[iy][ix] += P_tk[i][k]
    P_log = [[round(math.log10(v + 1), 3) for v in row] for row in P_grid]

    R_grid = [[hat_R[iy * n_grid + ix] for ix in range(n_grid)]
              for iy in range(n_grid)]

    x_min, x_max, y_min, y_max, lx, ly = bbox
    x_labels = [round(x_min + (i + 0.5) * lx, 1) for i in range(n_grid)]
    y_labels = [round(y_min + (i + 0.5) * ly, 1) for i in range(n_grid)]

    total_sim_ns = N_c * cycle_ns
    total_window_cycles = sum(e - s for (s, e) in windows)
    beta_out = total_window_cycles / N_c * 100 if N_c > 0 else 0

    # Sort phases / windows for sidebar tables
    phase_rows = []
    for j, (ps, pe) in enumerate(phases):
        D = pe - ps
        max_e = max(e_t[ps:pe]) if pe > ps else 0
        phase_rows.append((j + 1, ps * cycle_ns, pe * cycle_ns, D, max_e))

    window_rows = []
    for r in scores:
        ws, we = r["start"], r["end"]
        window_rows.append((ws * cycle_ns, we * cycle_ns, we - ws, r["score"]))

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Worst-Case Window Selection</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:'Segoe UI',sans-serif; background:#1a1a2e; color:#eee; }}
.header {{ padding:12px 20px; background:#16213e; border-bottom:2px solid #0f3460; }}
.header h1 {{ font-size:18px; font-weight:600; }}
.header .sub {{ font-size:11px; color:#a0a0b0; margin-top:3px; }}
.layout {{ display:flex; height:calc(100vh - 56px); }}
.panels {{ flex:1; display:grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: 240px 240px 1fr;
  gap: 2px; padding: 2px; }}
#bar_ci {{ grid-column: 1 / -1; }}
#bar_et {{ grid-column: 1 / -1; }}
.sidebar {{ width:260px; background:#16213e; padding:12px; overflow-y:auto;
           border-left:1px solid #0f3460; font-size:12px; }}
.sidebar h3 {{ color:#e94560; margin:10px 0 5px; font-size:13px; }}
.stat {{ margin-bottom:6px; }}
.stat .label {{ font-size:10px; color:#888; text-transform:uppercase; }}
.stat .value {{ font-size:15px; font-weight:700; }}
table {{ width:100%; border-collapse:collapse; font-size:10px; margin-top:4px; }}
th,td {{ padding:2px 4px; text-align:left; border-bottom:1px solid #333; }}
th {{ color:#e94560; }}
</style>
</head>
<body>
<div class="header">
  <h1>Worst-Case Window Selection — RC-Tile + Phase-Aware</h1>
  <div class="sub">N_grid: {n_grid}&times;{n_grid} | k_θ: {args.k_theta}
    | ρ: {args.rho} | η: {args.eta} | K_min: {args.k_min}
    | Phases: {len(phases)} | Windows: {len(windows)}
    | β_out: {beta_out:.1f}%</div>
</div>
<div class="layout">
  <div class="panels">
    <div id="bar_ci"></div>
    <div id="bar_et"></div>
    <div id="heatmap_p"></div>
    <div id="heatmap_r"></div>
  </div>
  <div class="sidebar">
    <h3>Summary</h3>
    <div class="stat"><div class="label">Simulation</div>
      <div class="value">{total_sim_ns:.0f} ns ({N_c} cycles)</div></div>
    <div class="stat"><div class="label">Active threshold θ</div>
      <div class="value">{theta:.0f}</div></div>
    <div class="stat"><div class="label">β_out</div>
      <div class="value">{beta_out:.1f}%</div></div>
    <div class="stat"><div class="label">Phases / Windows</div>
      <div class="value">{len(phases)} / {len(windows)}</div></div>

    <h3>Phases</h3>
    <table>
      <tr><th>#</th><th>Range (ns)</th><th>D</th><th>max e_t</th></tr>
      {"".join(f'<tr><td>{j}</td><td>{s:.0f}~{e:.0f}</td><td>{D}</td><td>{me:.0f}</td></tr>'
               for j, s, e, D, me in phase_rows)}
    </table>

    <h3>Windows (by score)</h3>
    <table>
      <tr><th>Range (ns)</th><th>n</th><th>score</th></tr>
      {"".join(f'<tr><td>{s:.0f}~{e:.0f}</td><td>{n}</td><td>{sc:.0f}</td></tr>'
               for s, e, n, sc in window_rows)}
    </table>
  </div>
</div>

<script>
var darkBg = '#1a1a2e';

Plotly.newPlot('bar_ci', [{{
  x: {json.dumps(times_ns)},
  y: {json.dumps(c_i)},
  type: 'bar',
  marker: {{ color: {json.dumps(bar_colors)} }},
  hovertemplate: 'Cycle %{{pointNumber}}<br>%{{x:.0f}} ns<br>c_i: %{{y:,}}<extra></extra>',
  width: {cycle_ns * 0.85}
}}], {{
  title: {{ text:'Stage 1: Per-Cycle Toggle Total c_i  '
            + '(red = selected, gold dashed = phase, red box = window)',
            font:{{size:13,color:'#ccc'}} }},
  paper_bgcolor: darkBg, plot_bgcolor: darkBg,
  xaxis: {{ title:'Time (ns)', color:'#aaa', gridcolor:'#333' }},
  yaxis: {{ title:'Toggle Count', color:'#aaa', gridcolor:'#333' }},
  shapes: [{",".join(phase_shapes + window_shapes)}],
  margin: {{ t:32, b:36, l:56, r:8 }}
}}, {{responsive:true}});

Plotly.newPlot('bar_et', [{{
  x: {json.dumps(times_ns)},
  y: {json.dumps([round(v, 2) for v in e_t])},
  type: 'bar',
  marker: {{ color: {json.dumps(bar_colors)} }},
  hovertemplate: 'Cycle %{{pointNumber}}<br>%{{x:.0f}} ns<br>e_t: %{{y:,.0f}}<extra></extra>',
  width: {cycle_ns * 0.85}
}}], {{
  title: {{ text:'Stage 3: Danger Score e_t = P_total · (1 + σ_top3)',
            font:{{size:13,color:'#ccc'}} }},
  paper_bgcolor: darkBg, plot_bgcolor: darkBg,
  xaxis: {{ title:'Time (ns)', color:'#aaa', gridcolor:'#333' }},
  yaxis: {{ title:'e_t', color:'#aaa', gridcolor:'#333' }},
  shapes: [{",".join(window_shapes)}],
  margin: {{ t:32, b:36, l:56, r:8 }}
}}, {{responsive:true}});

Plotly.newPlot('heatmap_p', [{{
  z: {json.dumps(P_log)},
  x: {json.dumps(x_labels)},
  y: {json.dumps(y_labels)},
  type: 'heatmap',
  colorscale: 'Hot', reversescale: true,
  colorbar: {{ title:'log10(P+1)', titleside:'right',
               titlefont:{{color:'#ccc',size:10}}, tickfont:{{color:'#ccc',size:9}} }},
}}], {{
  title: {{ text:'Tile Heatmap — Σ P_t,k (V_drop risk)',
            font:{{size:12,color:'#ccc'}} }},
  paper_bgcolor: darkBg, plot_bgcolor: darkBg,
  xaxis: {{ title:'X (um)', color:'#aaa', gridcolor:'#333', scaleanchor:'y' }},
  yaxis: {{ title:'Y (um)', color:'#aaa', gridcolor:'#333' }},
  margin: {{ t:32, b:32, l:48, r:8 }}
}}, {{responsive:true}});

Plotly.newPlot('heatmap_r', [{{
  z: {json.dumps(R_grid)},
  x: {json.dumps(x_labels)},
  y: {json.dumps(y_labels)},
  type: 'heatmap',
  colorscale: 'Viridis',
  colorbar: {{ title:'R̂_k', titleside:'right',
               titlefont:{{color:'#ccc',size:10}}, tickfont:{{color:'#ccc',size:9}} }},
}}], {{
  title: {{ text:'Tile Resistance R̂_k (clipped 0.5~2.5)',
            font:{{size:12,color:'#ccc'}} }},
  paper_bgcolor: darkBg, plot_bgcolor: darkBg,
  xaxis: {{ title:'X (um)', color:'#aaa', gridcolor:'#333', scaleanchor:'y' }},
  yaxis: {{ title:'Y (um)', color:'#aaa', gridcolor:'#333' }},
  margin: {{ t:32, b:32, l:48, r:8 }}
}}, {{responsive:true}});
</script>
</body>
</html>"""

    os.makedirs(os.path.dirname(os.path.abspath(html_path)), exist_ok=True)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  HTML: {html_path}")


# ═════════════════════════════════════════════════════════════════════
#  JSON Report
# ═════════════════════════════════════════════════════════════════════

def write_json_report(json_path: str, args, ctx, scores, splice_stats):
    N_c = ctx["N_c"]
    cycle_ns = args.clock_ns
    total_sim_ns = N_c * cycle_ns
    total_window_cycles = sum(e - s for (s, e) in ctx["windows"])
    beta_out = total_window_cycles / N_c if N_c > 0 else 0

    report = {
        "parameters": {
            "n_grid": args.n_grid,
            "k_theta": args.k_theta,
            "rho": args.rho,
            "eta": args.eta,
            "k_min": args.k_min,
            "gap": args.gap,
            "n_min": args.n_min,
            "clock_ns": args.clock_ns,
            "timescale_ps": args.timescale_ps,
        },
        "simulation": {
            "n_cycles": N_c,
            "t_max_ns": round(total_sim_ns, 2),
            "n_signals": len(ctx.get("sig_toggles", {})),
            "spef_used": ctx.get("spef_used", False),
        },
        "phases": [
            {"index": j + 1, "i_start": ps, "i_end": pe,
             "duration_cycles": pe - ps,
             "t_start_ns": round(ps * cycle_ns, 2),
             "t_end_ns": round(pe * cycle_ns, 2)}
            for j, (ps, pe) in enumerate(ctx["phases"])
        ],
        "windows": [
            {"i_start": r["start"], "i_end": r["end"],
             "n_cycles": r["end"] - r["start"],
             "t_start_ns": round(r["start"] * cycle_ns, 2),
             "t_end_ns": round(r["end"] * cycle_ns, 2),
             "score": round(r["score"], 3)}
            for r in scores
        ],
        "compression": {
            "beta_out": round(beta_out, 4),
            "beta_out_pct": round(beta_out * 100, 2),
            "n_phases": len(ctx["phases"]),
            "n_windows": len(ctx["windows"]),
        },
        "splice_stats": splice_stats or {},
    }
    os.makedirs(os.path.dirname(os.path.abspath(json_path)), exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"  JSON: {json_path}")


# ═════════════════════════════════════════════════════════════════════
#  Main
# ═════════════════════════════════════════════════════════════════════

def main():
    p = argparse.ArgumentParser(
        description="RC-Tile + Phase-Aware Worst-Case Window Selection")
    p.add_argument("--location", required=True,
                   help="signal_location_map.csv (with optional c_load,r_net)")
    p.add_argument("--toggles", required=True, help="toggle JSONL")
    p.add_argument("--vcd", required=True, help="input VCD file")
    p.add_argument("--spef", default=None,
                   help="optional SPEF file; if given, will be parsed and "
                        "joined into the location CSV in-memory")

    p.add_argument("--n-grid", type=int, default=8,
                   help="tile grid size N_grid (default: 8 → 64 tiles)")
    p.add_argument("--k-theta", type=float, default=1.0,
                   help="active threshold coefficient (default: 1.0)")
    p.add_argument("--rho", type=float, default=0.7,
                   help="decap depletion sampling ratio (default: 0.7);"
                        " pass a negative value (e.g. -1) to enable"
                        " self-tune mode — center = argmax(e_t in phase).")
    p.add_argument("--eta", type=float, default=0.15,
                   help="window half-width ratio (default: 0.15)")
    p.add_argument("--k-min", type=int, default=2,
                   help="minimum window cycles per phase (default: 2)")
    p.add_argument("--small-window", action="store_true",
                   help="m2: force window length = 2*k_min+1 cycles centred"
                        " on argmax(e_t in phase); ignores --rho and --eta")
    p.add_argument("--top-k", type=int, default=0,
                   help="m3: per-phase emit up to K non-overlapping argmax small"
                        " windows. 0 = governed by --beta-budget;"
                        " falls back to 1 if budget also 0."
                        " Only effective with --small-window.")
    p.add_argument("--min-gap-cycles", type=int, default=10,
                   help="m3/m4: min gap in cycles between two argmax centers in"
                        " the same phase (default 10)."
                        " Only effective with --small-window.")
    p.add_argument("--beta-budget", type=float, default=0.0,
                   help="m4: per-phase compression budget (e.g. 0.10 = 10%%)."
                        " When > 0, continues picking until accumulated beta"
                        " crosses budget. 0 = disabled, use --top-k instead."
                        " Only effective with --small-window.")
    p.add_argument("--score-mode", choices=["peak", "neighbor", "cluster"],
                   default="peak",
                   help="m5 scoring: 'peak'=current(default), "
                        "'neighbor'=spatial neighbor weighted (m5a), "
                        "'cluster'=top-K cluster mean (m5b).")
    p.add_argument("--neighbor-alpha", type=float, default=1.0,
                   help="m5a: blend weight for center tile vs 8-neighbors "
                        "(0.0-1.0, default 1.0 = pure peak). "
                        "Only effective with --score-mode neighbor.")
    p.add_argument("--cluster-k", type=int, default=1,
                   help="m5b: number of top tiles to average "
                        "(default 1 = pure peak). "
                        "Only effective with --score-mode cluster.")
    p.add_argument("--gap", type=int, default=1,
                   help="phase merge tolerance gap (default: 1)")
    p.add_argument("--n-min", type=int, default=3,
                   help="filter phases with D < n_min (default: 3)")

    p.add_argument("--clock-ns", type=float, default=50.0,
                   help="clock period in ns (default: 50)")
    p.add_argument("--timescale-ps", type=float, default=10.0,
                   help="VCD timescale in ps (default: 10)")

    p.add_argument("--output", required=True,
                   help="output spliced VCD path")
    p.add_argument("--html", default=None, help="output HTML report path")
    p.add_argument("--json-out", default=None, help="output JSON report path")
    args = p.parse_args()

    if not 0.0 <= args.neighbor_alpha <= 1.0:
        raise ValueError(f"--neighbor-alpha must be in [0,1], got {args.neighbor_alpha}")
    if args.cluster_k < 1:
        raise ValueError(f"--cluster-k must be >= 1, got {args.cluster_k}")

    print("=" * 60)
    print("  RC-Tile + Phase-Aware Worst-Case Window Selection")
    print("=" * 60)
    print(f"  N_grid: {args.n_grid}x{args.n_grid} ({args.n_grid**2} tiles)")
    print(f"  k_θ: {args.k_theta}  ρ: {args.rho}  η: {args.eta}  "
          f"K_min: {args.k_min}")
    if args.score_mode != "peak":
        extra = f"α={args.neighbor_alpha}" if args.score_mode == "neighbor" \
                else f"K={args.cluster_k}"
        print(f"  Score mode: {args.score_mode} ({extra})")
    print()

    # ── Step 1: Load locations (and optionally merge SPEF) ──
    print("[1/7] Loading signal locations...")
    locations = load_locations(args.location)
    print(f"  {len(locations):,} signals with coordinates")

    spef_used = False
    if args.spef:
        print(f"[1.5] Parsing SPEF: {args.spef}")
        from spef_parser import parse_spef
        nets = parse_spef(args.spef)
        n_hit = 0
        for name, info in locations.items():
            rc = (nets.get(name)
                  or nets.get("/" + name)
                  or nets.get(name.lstrip("/")))
            if rc:
                info["c_load"] = rc["c_load"] or 1.0
                info["r_net"] = rc["r_net"]
                n_hit += 1
        print(f"  SPEF nets: {len(nets):,}, matched: {n_hit:,}")
        spef_used = n_hit > 0

    # ── Step 2: Tile mapping + R_k ──
    print(f"[2/7] Building {args.n_grid}x{args.n_grid} tile map...")
    signal_to_tile, bbox = build_tile_map(locations, args.n_grid)
    hat_R, has_R = aggregate_tile_resistance(locations, signal_to_tile,
                                             args.n_grid)
    print(f"  Tile resistance: {'enabled (SPEF)' if has_R else 'unit (no SPEF data)'}")

    # ── Step 3: Aggregate + RC fingerprint (single pass) ──
    print("[3/7] Aggregating cycles + RC-weighted fingerprint...")
    ctx = aggregate_and_fingerprint(args.toggles, locations, signal_to_tile,
                                    hat_R, args.n_grid,
                                    args.clock_ns, args.timescale_ps)
    print(f"  JSONL lines: {ctx['n_lines']:,}")
    print(f"  N_c: {ctx['N_c']} cycles  "
          f"(t_max: {ctx['t_max_ticks']} ticks, "
          f"{ctx['t_max_ticks'] * args.timescale_ps / 1000:.0f} ns)")
    print(f"  Total toggles: {sum(ctx['c_i']):,}")

    P_total, sigma_top3, e_t = compute_scores(
        ctx["P_tk"], ctx["N_c"], ctx["K"],
        score_mode=args.score_mode,
        n_grid=args.n_grid,
        neighbor_alpha=args.neighbor_alpha,
        cluster_k=args.cluster_k,
    )
    ctx["P_total"] = P_total
    ctx["sigma_top3"] = sigma_top3
    ctx["e_t"] = e_t
    ctx["hat_R"] = hat_R
    ctx["bbox"] = bbox
    ctx["n_grid"] = args.n_grid
    ctx["spef_used"] = spef_used

    # ── Step 4: Phase detection ──
    print("[4/7] Detecting active phases...")
    phases, theta = detect_phases(ctx["c_i"], args.k_theta,
                                  args.gap, args.n_min)
    ctx["phases"] = phases
    ctx["theta"] = theta
    print(f"  θ = {args.k_theta} × median = {theta:.1f}")
    print(f"  Phases detected: {len(phases)}")
    for j, (ps, pe) in enumerate(phases):
        print(f"    [{j+1}] cycles {ps}~{pe-1}  "
              f"({ps * args.clock_ns:.0f}~{pe * args.clock_ns:.0f} ns, "
              f"D={pe-ps})")

    # ── Step 5: Window generation ──
    print("[5/7] Generating phase-driven windows...")
    windows = generate_windows(phases, ctx["N_c"], ctx["clock_ticks"],
                               args.rho, args.eta, args.k_min, e_t=e_t,
                               small_window=args.small_window,
                               top_k=args.top_k,
                               min_gap=args.min_gap_cycles,
                               beta_budget=args.beta_budget)
    ctx["windows"] = windows
    print(f"  Windows: {len(windows)}")
    for j, (ws, we) in enumerate(windows):
        print(f"    W{j+1}: cycles {ws}~{we-1}  "
              f"({ws * args.clock_ns:.0f}~{we * args.clock_ns:.0f} ns, "
              f"n={we-ws})")

    scores = score_windows(windows, e_t)
    total_w = sum(e - s for (s, e) in windows)
    beta_out = total_w / ctx["N_c"] * 100 if ctx["N_c"] > 0 else 0
    print(f"  β_out = {beta_out:.1f}%  "
          f"(window cycles {total_w} / total {ctx['N_c']})")

    if args.beta_budget > 0:
        L_w = 2 * args.k_min + 1
        actual_beta = len(windows) * L_w / ctx["N_c"] if ctx["N_c"] > 0 else 0
        target_k = math.ceil(args.beta_budget * ctx["N_c"] / L_w)
        print(f"  Budget mode: target_K={target_k}, actual_K={len(windows)}, "
              f"β={actual_beta:.1%}")
        if len(windows) < target_k:
            print(f"  WARNING: Only {len(windows)} < {target_k} windows fit "
                  f"within phase bounds", file=sys.stderr)

    # ── e_t top-20 diagnostic table ──
    N_c = ctx["N_c"]
    et_indexed = sorted(enumerate(e_t), key=lambda x: -x[1])[:20]
    print("  e_t top-20: rank | cycle |      t_ns |       e_t")
    for rank, (cyc, val) in enumerate(et_indexed, 1):
        t_ns = cyc * args.clock_ns
        print(f"    {rank:4d} | {cyc:5d} | {t_ns:9.1f} | {val:9.1f}")

    # ── Step 6: Splice VCD ──
    print("[6/7] Splicing VCD...")
    intervals = windows_to_tick_intervals(windows, ctx["clock_ticks"])
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    splice_stats = splice_vcd(args.vcd, intervals, args.output)
    in_size = os.path.getsize(args.vcd)
    out_size = os.path.getsize(args.output)
    print(f"  Segments: {splice_stats.get('n_segments', 0)}")
    print(f"  Time points: {splice_stats.get('n_times', 0)}")
    print(f"  Value changes: {splice_stats.get('n_changes', 0)}")
    print(f"  Size: {in_size:,} → {out_size:,} bytes "
          f"({out_size / in_size * 100:.1f}%)")

    # ── Step 7: Reports ──
    print("[7/7] Writing reports...")
    if args.html:
        generate_html(args.html, args, ctx, scores)
    if args.json_out:
        write_json_report(args.json_out, args, ctx, scores, splice_stats)

    print()
    print("=" * 60)
    print("  Done.")
    print("=" * 60)


if __name__ == "__main__":
    main()
