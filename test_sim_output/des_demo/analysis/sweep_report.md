# des_demo (des3) Threshold Sweep Report

- Full VCD: `11,005,488` bytes  
- Full worst drop: **80.64 mV**  
- Instances: 64179
- Layers (full IR drop V): M6=0.0235, M5=0.0235, M4=0.022, M3=0.0315, M2=0.0302, M1=0.0297, LISD=0.0311

## Per-cell metrics

| kernel | t | comp% | Worst drop (mV) | C_int (%) | J@10 | J@50 | J@100 |
|---|---|---|---|---|---|---|---|
| full | full |  | 80.64 | 100.0 |  |  |  |
| traditional | 0.5 | 152.02 | 1.82 | 2.257 | 0.0 | 0.0 | 0.0 |
| euclidean | 0.5 | 101.98 | 80.64 | 100.0 | 1.0 | 1.0 | 1.0 |
| exponential | 0.5 | 152.02 | 1.82 | 2.257 | 0.0 | 0.0 | 0.0 |
| logarithmic | 0.5 | 101.98 | 80.64 | 100.0 | 1.0 | 1.0 | 1.0 |
| traditional | 0.6 | 152.02 | 1.82 | 2.257 | 0.0 | 0.0 | 0.0 |
| euclidean | 0.6 | 148.95 | 1.75 | 2.17 | 0.0 | 0.0 | 0.0 |
| exponential | 0.6 | 152.02 | 1.82 | 2.257 | 0.0 | 0.0 | 0.0 |
| logarithmic | 0.6 | 101.98 | 80.64 | 100.0 | 1.0 | 1.0 | 1.0 |
| traditional | 0.7 | 152.02 | 1.82 | 2.257 | 0.0 | 0.0 | 0.0 |
| euclidean | 0.7 | 147.92 | 1.75 | 2.17 | 0.0 | 0.0 | 0.0 |
| exponential | 0.7 | 152.02 | 1.82 | 2.257 | 0.0 | 0.0 | 0.0 |
| logarithmic | 0.7 | 148.12 | 1.75 | 2.17 | 0.0 | 0.0 | 0.0 |
| traditional | 0.8 | 72.15 | 1.79 | 2.22 | 0.0 | 0.0 | 0.0 |
| euclidean | 0.8 | 143.89 | 1.76 | 2.183 | 0.0 | 0.0 | 0.0 |
| exponential | 0.8 | 87.14 | 1.76 | 2.183 | 0.0 | 0.0 | 0.0 |
| logarithmic | 0.8 | 139.48 | 1.77 | 2.195 | 0.0 | 0.0 | 0.0 |
| traditional | 0.9 | 51.99 | 1.79 | 2.22 | 0.0 | 0.0 | 0.0 |
| euclidean | 0.9 | 119.41 | 1.78 | 2.207 | 0.0 | 0.0 | 0.0 |
| exponential | 0.9 | 58.71 | 1.79 | 2.22 | 0.0 | 0.0 | 0.0 |
| logarithmic | 0.9 | 113.72 | 1.8 | 2.232 | 0.0 | 0.0 | 0.0 |
| traditional | 0.95 | 23.76 | 1.78 | 2.207 | 0.0 | 0.0 | 0.0 |
| euclidean | 0.95 | 54.0 | 1.79 | 2.22 | 0.0 | 0.0 | 0.0 |
| exponential | 0.95 | 29.06 | 1.78 | 2.207 | 0.0 | 0.0 | 0.0 |
| logarithmic | 0.95 | 102.6 | 1.8 | 2.232 | 0.0 | 0.0 | 0.0 |

## Highlights

- **traditional**: best C_int = 2.257% (t=0.5, comp=152.02%); smallest comp = 23.76% (t=0.95, C_int=2.207%)
- **euclidean**: best C_int = 100.0% (t=0.5, comp=101.98%); smallest comp = 54.0% (t=0.95, C_int=2.22%)
- **exponential**: best C_int = 2.257% (t=0.5, comp=152.02%); smallest comp = 29.06% (t=0.95, C_int=2.207%)
- **logarithmic**: best C_int = 100.0% (t=0.5, comp=101.98%); smallest comp = 101.98% (t=0.5, C_int=100.0%)
