# Skill: Rebuild VCD from CSV (CSV → VCD)

## Goal

Reconstruct a standards-compliant VCD file from:
1. A worst-case CSV file (CSV3) — time-aligned signal values for selected windows
2. `signal_manifest.json` — signal metadata (name, type, width, symbol)

This is task5 of the VCD compression pipeline. The output VCD must pass `vcd_validator.py` and be loadable by standard waveform tools (GTKWave, Verdi, etc.).

---

## When to Use

Use this skill when:
- Converting worst-case CSV data back to VCD format (task5)
- Reconstructing compressed VCD for power analysis tools
- Any CSV-to-VCD conversion where signal metadata is available

---

## Input

Required:
- `worst_case_<N>cycles.csv` (CSV3) — output of task4
- `signal_manifest.json` — written by task1

CSV3 format:
```csv
time,clk,seed,circle,rand_sig [4:0]
30,1,42,3,10101
40,0,42,3,10101
50,1,99,3,00110
...
```

signal_manifest.json excerpt:
```json
{
  "timescale": "1 ns",
  "scope": "tb_top",
  "signals": [
    {"name": "clk",  "type": "reg",     "width": 1,  "symbol": "!"},
    {"name": "seed", "type": "integer", "width": 32, "symbol": "\""}
  ]
}
```

---

## VCD Output Structure

```vcd
$date   <timestamp>   $end
$version   VCD Extractor 1.0   $end
$timescale   1 ns   $end
$scope module tb_top $end
$var reg 1 ! clk $end
$var integer 32 " seed $end
$var reg 5 # rand_sig [4:0] $end
$upscope $end
$enddefinitions $end
$dumpvars
0!
b00000000000000000000000000000000 "
b00000 #
$end
#30
1!
#40
0!
#50
b01100011 "
```

---

## Algorithm

### Step 1: Load Manifest
```python
import json
with open("signal_manifest.json") as f:
    manifest = json.load(f)

signals = manifest["signals"]   # list of {name, type, width, symbol}
timescale = manifest["timescale"]
scope = manifest["scope"]
```

### Step 2: Build Symbol Pool
Do NOT hardcode symbols. Assign dynamically from manifest:
```python
sym_map = {sig["name"]: sig["symbol"] for sig in signals}
```

If generating new symbols (not from manifest), use the full ASCII printable range:
```python
import itertools, string
printable = [c for c in string.printable if c not in ' \t\n\r\x0b\x0c']
# single-char: '!' .. '~'  (94 symbols)
# multi-char:  '!!' '!"' ... (unlimited)
def symbol_generator():
    for length in range(1, 4):
        for combo in itertools.product(printable, repeat=length):
            yield ''.join(combo)
```

### Step 3: Write VCD Header
```python
lines = []
lines.append(f"$date {datetime.now()} $end")
lines.append(f"$version VCD Extractor 1.0 $end")
lines.append(f"$timescale {timescale} $end")
lines.append(f"$scope module {scope} $end")
for sig in signals:
    lines.append(f"$var {sig['type']} {sig['width']} {sig['symbol']} {sig['name']} $end")
lines.append("$upscope $end")
lines.append("$enddefinitions $end")
```

### Step 4: Write $dumpvars (Initial Values)
Initial values must reflect each signal's **true state at the start of the first worst-case window**, not just the first row of CSV3.

```python
# Back-trace: for each signal, find its value at T0 = first timestamp in CSV3
# Option A: use the CSV3 first row (acceptable if task4 correctly backfills initial state)
# Option B: re-read original VCD to find last value before T0 (most accurate)

lines.append("$dumpvars")
for sig in signals:
    init_val = get_initial_value(sig, first_timestamp)
    lines.append(format_value_change(init_val, sig['symbol'], sig['width']))
lines.append("$end")
```

### Step 5: Write Value Changes
```python
prev_values = {sig['name']: None for sig in signals}

for row in csv3_rows:
    time = row['time']
    lines.append(f"#{time}")
    for sig in signals:
        val = row[sig['name']]
        if val != prev_values[sig['name']]:
            lines.append(format_value_change(val, sym_map[sig['name']], sig['width']))
            prev_values[sig['name']] = val
```

---

## Value Change Formatting

```python
def format_value_change(value, symbol, width):
    """Format a value change line for VCD output."""
    # Scalar (1-bit)
    if width == 1:
        return f"{value}{symbol}"       # e.g. "1!" or "0!"

    # Vector (multi-bit)
    # Pad binary string to full width
    if all(c in '01xzXZ' for c in str(value)):
        bin_str = str(value).zfill(width)
        return f"b{bin_str} {symbol}"   # e.g. "b10101 #"

    # Integer or other: convert to binary
    try:
        int_val = int(value)
        bin_str = format(int_val, f'0{width}b')
        return f"b{bin_str} {symbol}"
    except ValueError:
        return f"bx {symbol}"           # fallback for x/z
```

---

## Correctness Checklist

Before writing the output VCD, verify:

- [ ] Every symbol in `$dumpvars` and value-change lines appears in a `$var` declaration
- [ ] Time values are monotonically non-decreasing
- [ ] `$scope` and `$upscope` are balanced
- [ ] `$enddefinitions $end` is present
- [ ] `$dumpvars` block ends with `$end`
- [ ] Scalar signals use `<value><symbol>` (no space)
- [ ] Vector signals use `b<binary> <symbol>` (space before symbol)
- [ ] Symbol pool does not repeat (each signal has a unique symbol)
- [ ] Symbol pool supports more than 15 signals (use extended ASCII printable range)

---

## Common Issues

| Problem | Cause | Solution |
|---------|-------|---------|
| Hardcoded signal type/width | Legacy task5 code | Read from `signal_manifest.json` |
| Symbol collision (>15 signals) | Tiny symbol pool | Use `itertools.product` for multi-char symbols |
| Wrong initial state in `$dumpvars` | Taking CSV3 row 0 as initial | Back-trace to pre-window state from original VCD |
| Non-monotonic timestamps | Unsorted CSV3 | Sort rows by `time` before writing |
| Vector format wrong | Missing `b` prefix or space | Use `format_value_change()` above |

---

## Validation

After writing the VCD, run:
```bash
python code/vcd_validator.py output/worst_case_5cycles.vcd
python code/vcd_validator.py output/worst_case_5cycles.vcd --ref data/random_test.vcd
```

Expected output:
```
Header: PASS
Scope Structure: PASS
Variable Definitions: PASS
Enddefinitions: PASS
Time Sequence: PASS
Value Changes: PASS
Final Result: VALID VCD
```

---

## Typical Pipeline

```
worst_case_<N>cycles.csv  +  signal_manifest.json
              ↓
        csv_to_vcd (this skill)
              ↓
      worst_case_<N>cycles.vcd
              ↓
   vcd_validator → compare_vcd_waveform
```
