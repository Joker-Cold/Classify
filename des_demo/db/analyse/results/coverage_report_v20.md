# IR Drop Coverage Report (v20)

## Reference (Full VCD)

- **Vnom**: 0.7 V
- **Vmin**: 0.674 V
- **Worst IR drop**: 0.0260 V (26.0 mV)
- **Ipeak**: 15.180 mA
- **Violations**: 0
- **Threshold**: 0.651 V

### Layer-based IR Drop (Full VCD)

| Layer | IR Drop (V) | Range |
|-------|-------------|-------|
| M6 | 0.0232 | 0.7 -> 0.677 |
| M5 | 0.0232 | 0.7 -> 0.677 |
| M4 | 0.0219 | 0.699 -> 0.677 |
| M3 | 0.0227 | 0.698 -> 0.676 |
| M2 | 0.0221 | 0.698 -> 0.675 |
| M1 | 0.0216 | 0.697 -> 0.675 |
| LISD | 0.0232 | 0.697 -> 0.674 |

## Window Definitions

| Window | Description |
|--------|-------------|
| eq_win1 | 等分窗口 1: 0 ~ 2370ns (2370ns) |
| eq_win2 | 等分窗口 2: 2370 ~ 4740ns (2370ns) |
| eq_win3 | 等分窗口 3: 4740 ~ 7110ns (2370ns) |
| eq_win4 | 等分窗口 4: 7110 ~ 9480ns (2370ns) |
| eq_win5 | 等分窗口 5: 9480 ~ 11850ns (2370ns) |
| algo_win1 | 算法选窗 1: 3790 ~ 4390ns (600ns, Phase 1, depletion_ratio=0.7) |
| algo_win2 | 算法选窗 2: 9600 ~ 10100ns (500ns, Phase 2, depletion_ratio=0.7) |

## Window Data Summary

| Window | Vmin (V) | IR Drop (mV) | Violations | Data |
|--------|----------|--------------|------------|------|
| eq_win1 | 0.676 | 24.0 | 0 | main, layer, dynpwr |
| eq_win2 | 0.674 | 26.0 | 0 | main, layer, dynpwr |
| eq_win3 | 0.678 | 22.0 | 0 | main, layer, dynpwr |
| eq_win4 | 0.675 | 25.0 | 0 | main, layer, dynpwr |
| eq_win5 | 0.675 | 25.0 | 0 | main, layer, dynpwr |
| algo_win1 | 0.674 | 26.0 | 0 | main, layer, dynpwr |
| algo_win2 | 0.674 | 26.0 | 0 | main, layer, dynpwr |

## Single Window Coverage

| Window | C1 | C_layer_avg | C_layer_min | C_margin | C_overall | C_violation | M6 | M5 | M4 | M3 | M2 | M1 | LISD |
|--------|------|-------------|-------------|----------|-----------|-------------|------|------|------|------|------|------|------|
| eq_win1 | 92.3% | 75.9% | 56.6% | 108.7% | 56.6% | PASS | 57.3% | 57.3% | 56.6% | 91.2% | 89.1% | 89.4% | 90.1% |
| eq_win2 | 100.0% | 102.7% | 100.0% | 100.0% | 100.0% | PASS | 100.0% | 100.0% | 101.8% | 102.2% | 104.1% | 105.6% | 105.2% |
| eq_win3 | 84.6% | 80.9% | 79.9% | 117.4% | 79.9% | PASS | 80.2% | 81.0% | 79.9% | 81.5% | 80.5% | 80.6% | 82.3% |
| eq_win4 | 96.2% | 87.3% | 76.3% | 104.3% | 76.3% | PASS | 76.3% | 76.3% | 76.3% | 96.5% | 95.0% | 95.8% | 95.3% |
| eq_win5 | 96.2% | 98.6% | 95.7% | 104.3% | 95.7% | PASS | 95.7% | 96.1% | 98.2% | 97.8% | 99.5% | 101.4% | 101.3% |
| algo_win1 | 100.0% | 103.5% | 100.0% | 100.0% | 100.0% | PASS | 100.0% | 100.0% | 102.7% | 103.1% | 105.4% | 106.9% | 106.5% |
| algo_win2 | 100.0% | 103.5% | 100.0% | 100.0% | 100.0% | PASS | 100.0% | 100.0% | 102.7% | 103.1% | 105.4% | 106.9% | 106.5% |

## Multi-Window Combination Coverage

| Windows | C1 | C_layer_avg | C_layer_min | C_margin | C_overall | C_violation |
|---------|------|-------------|-------------|----------|-----------|-------------|
| algo_win1+algo_win2 | 100.0% | 103.5% | 100.0% | 100.0% | 100.0% | PASS |
| eq_win2+eq_win4 | 100.0% | 102.7% | 100.0% | 100.0% | 100.0% | PASS |
| eq_win2+eq_win5 | 100.0% | 102.7% | 100.0% | 100.0% | 100.0% | PASS |
| eq_win1+eq_win2+eq_win3+eq_win4+eq_win5 | 100.0% | 102.7% | 100.0% | 100.0% | 100.0% | PASS |
| algo_win1+algo_win2+eq_win2 | 100.0% | 103.5% | 100.0% | 100.0% | 100.0% | PASS |

## Trade-off: Coverage vs Compression

| Windows | Duration (ns) | Compression | C_overall | Verdict |
|---------|--------------|-------------|-----------|---------|
| algo_win2 | 500 | 4.2% | 100.0% | PASS |
| algo_win1 | 600 | 5.1% | 100.0% | PASS |
| algo_win1+algo_win2 | 1100 | 9.3% | 100.0% | PASS |
| eq_win1 | 2370 | 20.0% | 56.6% | FAIL |
| eq_win2 | 2370 | 20.0% | 100.0% | PASS |
| eq_win3 | 2370 | 20.0% | 79.9% | FAIL |
| eq_win4 | 2370 | 20.0% | 76.3% | FAIL |
| eq_win5 | 2370 | 20.0% | 95.7% | PASS |
| algo_win1+algo_win2+eq_win2 | 3470 | 29.3% | 100.0% | PASS |
| eq_win2+eq_win4 | 4740 | 40.0% | 100.0% | PASS |
| eq_win2+eq_win5 | 4740 | 40.0% | 100.0% | PASS |
| eq_win1+eq_win2+eq_win3+eq_win4+eq_win5 | 11850 | 100.0% | 100.0% | PASS |

## Verdict Summary

Criteria: C_overall >= 90% → **PASS**, 80~90% → **MARGINAL**, <80% → **FAIL**

### Single Windows

- **eq_win1**: C_overall=56.6% → **FAIL**
- **eq_win2**: C_overall=100.0% → **PASS**
- **eq_win3**: C_overall=79.9% → **FAIL**
- **eq_win4**: C_overall=76.3% → **FAIL**
- **eq_win5**: C_overall=95.7% → **PASS**
- **algo_win1**: C_overall=100.0% → **PASS**
- **algo_win2**: C_overall=100.0% → **PASS**

### Combinations

- **algo_win1+algo_win2**: C_overall=100.0% → **PASS**
- **eq_win2+eq_win4**: C_overall=100.0% → **PASS**
- **eq_win2+eq_win5**: C_overall=100.0% → **PASS**
- **eq_win1+eq_win2+eq_win3+eq_win4+eq_win5**: C_overall=100.0% → **PASS**
- **algo_win1+algo_win2+eq_win2**: C_overall=100.0% → **PASS**
