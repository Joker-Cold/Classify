# IR Drop Coverage Tier-1 Report

## Reference (Full-set)

- **Vnom**: 0.7 V
- **Vmin**: 0.667 V
- **IR drop (Vnom-Vmin)**: 0.0330 V
- **Ipeak**: 16.485 mA
- **Violations**: 0
- **Threshold**: 0.651 V

### Layer-based IR Drop (Full-set)

| Layer | IR Drop (V) | Range |
|-------|-------------|-------|
| M7 | 0.0298 | 0.7 -> 0.67 |
| M6 | 0.0298 | 0.7 -> 0.67 |
| M5 | 0.0288 | 0.699 -> 0.67 |
| M4 | 0.0295 | 0.699 -> 0.669 |
| M3 | 0.0294 | 0.698 -> 0.669 |
| M2 | 0.0292 | 0.698 -> 0.669 |
| M1 | 0.0312 | 0.698 -> 0.667 |

## Window Data Summary

| Window | Vmin | Ipeak (mA) | Violations | Data |
|--------|------|------------|------------|------|
| win1 | 0.673 | 16.215 | 0 | main, layer, dynpwr |
| win2 | 0.667 | 16.490 | 0 | main, layer, dynpwr |
| win3 | N/A | 17.206 | N/A | layer, dynpwr |

## Single Window Coverage

| Window | C1 | C_peak | C_layer_avg | C_layer_min | C_violation | M7 | M6 | M5 | M4 | M3 | M2 | M1 |
|--------|------|--------|-------------|-------------|-------------|------|------|------|------|------|------|------|
| win1 | 81.8% | 98.4% | 65.0% | 45.8% | PASS | 47.0% | 48.0% | 45.8% | 82.0% | 78.2% | 77.7% | 76.3% |
| win2 | 100.0% | 100.0% | 97.3% | 94.2% | PASS | 100.0% | 100.0% | 98.3% | 98.6% | 95.2% | 94.2% | 94.6% |
| win3 | N/A | 104.4% | 95.6% | 92.5% | N/A | 100.0% | 100.0% | 95.5% | 94.6% | 93.5% | 92.5% | 92.9% |

## Multi-Window Combination Coverage

| Windows | C1 | C_peak | C_layer_avg | C_layer_min | C_violation |
|---------|------|--------|-------------|-------------|-------------|
| win1+win2 | 100.0% | 100.0% | 97.3% | 94.2% | PASS |
| win1+win3 | 81.8% | 104.4% | 95.6% | 92.5% | PASS |
| win2+win3 | 100.0% | 104.4% | 97.3% | 94.2% | PASS |
| win1+win2+win3 | 100.0% | 104.4% | 97.3% | 94.2% | PASS |
