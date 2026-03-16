# VCD Worst-Case Power Extractor - Tool Guide

Extracts the highest-toggle (worst-case power) waveform windows from a VCD file
and rebuilds a compressed VCD suitable for chip power verification.

---

## Quick Start

```bash
# Full pipeline in one command
python code/run_pipeline.py data/random_test.vcd

# With custom settings
python code/run_pipeline.py data/random_test.vcd \
    --window-size 5 10 \
    --threshold 0.8 \
    --output-dir results/ \
    --validate
```

Output files land in `output/` (or `--output-dir`):
- `worst_case_5cycles.vcd`  — compressed VCD (5-cycle windows)
- `worst_case_10cycles.vcd` — compressed VCD (10-cycle windows)

---

## Pipeline Steps

| Step | Script | Input | Output |
|------|--------|-------|--------|
| 1 | `task1_vcd_to_csv.py` | `*.vcd` | per-signal CSVs + `signal_manifest.json` |
| 2 | `task2_count_toggles.py` | signal CSVs + manifest | `toggle_counts_<N>cycles.csv` |
| 4 | `task4_extract_worst_case.py` | toggle counts | `worst_case_<N>cycles.csv` |
| 5 | `task5_csv_to_vcd.py` | worst-case CSV + manifest | `worst_case_<N>cycles.vcd` |

Run steps individually if needed:

```bash
python code/task1_vcd_to_csv.py
python code/task2_count_toggles.py
python code/task4_extract_worst_case.py
python code/task5_csv_to_vcd.py
```

---

## Core Library: parse_vcd_signal.py

```python
from parse_vcd_signal import VCDSignalParser

vcd = VCDSignalParser("data/random_test.vcd")
vcd.parse_header()

# List signals with metadata
for s in vcd.list_base_signals():
    print(vcd.get_signal_info(s))  # {name, type, width, symbol, full_name}

# Extract one signal (streaming)
result = vcd.extract_waveform("clk", start_time=0, end_time=100)
print(result["waveform"])  # [(time, value), ...]

# Extract ALL signals in one file pass (preferred for bulk use)
all_wf = vcd.parse_all_waveforms()  # {signal_name: [(time, value), ...]}
```

CLI:
```bash
python code/parse_vcd_signal.py data/random_test.vcd --list
python code/parse_vcd_signal.py data/random_test.vcd clk
python code/parse_vcd_signal.py data/random_test.vcd clk --csv output/clk.csv
```

---

## Validation

```bash
python code/vcd_validator.py output/worst_case_5cycles.vcd
python code/vcd_validator.py output/worst_case_5cycles.vcd --ref data/random_test.vcd
```

---

## Waveform Visualisation

Single-signal HTML viewer (from CSV):

```bash
python code/waveform_viewer.py output/clk.csv --title "clk" --output clk.html
```

Open the `.html` file in any browser.

---

## signal_manifest.json

Written by Task 1, read by Tasks 2, 4, 5. Example:

```json
{
  "vcd_source": "/path/to/sim.vcd",
  "timescale": "1 ns",
  "scope": "tb_top",
  "signals": [
    {"name": "clk",  "type": "reg",     "width": 1, "symbol": "!", "csv_file": "clk.csv"},
    {"name": "seed", "type": "integer", "width": 32, "symbol": "\"", "csv_file": "seed.csv"}
  ]
}
```

---

## Worst-Case Identification Logic

See `skills/worst_case_identification.md` for full algorithm description.

Summary:
1. Count total signal toggles in every N-cycle window
2. `threshold = max_toggles * threshold_pct`  (default 70%)
3. Keep windows where `toggle_count >= threshold`
4. Rebuild VCD from those windows only
