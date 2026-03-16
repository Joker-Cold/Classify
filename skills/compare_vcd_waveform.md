# Skill: Compare VCD Waveforms

## Goal

Compare the waveform of a specific signal between two VCD files.

This skill helps detect simulation differences between:

- RTL versions
- synthesis changes
- regression testing

---

## When to Use

Use this skill when:

- validating RTL modifications
- debugging unexpected behavior
- running regression tests

Example:


compare_vcd_waveform old.vcd new.vcd data_out


---

## Input

Required:

- VCD file A
- VCD file B
- signal name

Example:


reference.vcd
test.vcd
signal: valid


---

## Workflow

1. Parse both VCD files
2. Extract waveform for target signal
3. Normalize timestamps
4. Compare value changes
5. Report mismatches

---

## Signal Extraction

Use symbol mapping:


$var wire 1 ! clk $end


Symbol table example:


clk -> !
valid -> "
data -> #


---

## Waveform Representation

Example:

File A


(0,0)
(10,1)
(20,0)


File B


(0,0)
(10,0)
(20,1)


---

## Comparison Logic

Pseudo algorithm:


merge_timestamps()

for each timestamp:
if value_a != value_b:
record mismatch


---

## Output

### Match Case


Signal: valid
Comparison result: PASS
Waveforms are identical


---

### Mismatch Case


Signal: valid

Mismatch detected:

Time FileA FileB
10 1 0
20 0 1


---

## Advanced Checks

Optional features:

### Toggle comparison


toggle_count_A = 120
toggle_count_B = 118


---

### Time drift detection

Detect when waveform timing diverges.

---

### First mismatch location


First mismatch: time 430ns


---

## Use in Regression Testing

Typical automated flow:


simulate_reference
simulate_new

compare_vcd_waveform reference.vcd new.vcd signal


Fail regression if mismatch detected.

---

## Output Status


PASS
FAIL


---

## Common Issues

| Problem                | Cause              |
| ---------------------- | ------------------ |
| Different timescale    | timescale mismatch |
| Signal missing         | optimized away     |
| Different reset timing | simulation setup   |

---

## Compatible Simulators

- VCS
- Verilator
- Icarus Verilog
- Questa