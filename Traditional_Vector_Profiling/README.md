# Traditional Vector Profiling — 功耗矩阵生成

基于 Wen et al. ICCAD 2023 中描述的传统向量分析功率模型。

将仿真时间划分为固定大小的窗口（默认 20 ns），芯片区域划分为 M×N 的 tile 网格（默认 50×50），输出每个 tile 在每个窗口下的功耗矩阵 `[T][ny][mx]`（mW）以及每个窗口的平均功耗向量 `[T]`。

## 功率模型

```
P_inst,t = P_switching + P_internal + P_leakage

P_sw   = Σ_toggles × 0.5 × C_net_pF × V_DD² × 1e3 / window_ns  [mW]
P_int  = Σ_toggles × lookup_energy(lib_LUT, C_load_fF, slew_ps) / window_ns × 1e-3  [mW]
P_leak = leakage_pW × 1e-9  [mW]

power_matrix[t][iy][ix] = Σ_{inst ∈ tile(iy,ix)} P_inst,t   [mW]
avg_power[t] = mean(power_matrix[t])                          [mW]
```

## 环境要求

- Python 3.8+，无第三方依赖

## 目录结构

```
traditional_classify/
├── README.md
├── code/
│   ├── parse_lib_power.py      ← .lib目录 → 每种cell的LUT功率参数JSON
│   ├── parse_spef.py           ← SPEF文件 → 每条net的总电容JSON
│   ├── traditional_select.py   ← 主脚本：功耗矩阵生成+JSON报告
│   ├── vcd_to_jsonl.py         ← 预处理: VCD → JSONL
│   ├── jsonl_toggle_mark.py    ← 预处理: JSONL → Toggle JSONL
│   ├── parse_vcd_signal.py     ← 依赖库（vcd_to_jsonl 内部使用）
│   └── unused/
│       └── vcd_splice.py       ← 备用：VCD拼接/选窗相关函数
├── example_data/
│   └── README_inputs.md        ← 输入文件路径说明
└── sim_result/
    ├── intermediate/           ← toggle JSONL 等中间文件
    └── report/                 ← lib_power.json / net_cap.json / report.json
```

## 输入文件

| 文件 | 说明 |
|---|---|
| `input.vcd` | 原始 VCD 仿真波形 |
| `design.spef` | Innovus 导出的 SPEF 寄生参数（提供 net 电容） |
| `design.def` | Innovus 导出的 DEF 物理版图（提供 instance 位置和 cell 类型） |
| `mmmc/*.lib` | ASAP7/其他工艺库 Liberty 文件（提供功率 LUT） |

## 完整流程

### Step 1：VCD → Toggle JSONL（预处理）

```bash
python code/vcd_to_jsonl.py input.vcd --output-dir sim_result/intermediate/
python code/jsonl_toggle_mark.py sim_result/intermediate/input.jsonl
```

### Step 2：解析 Liberty 功率参数

```bash
python code/parse_lib_power.py \
    --lib-dir path/to/mmmc/ \
    --out sim_result/report/lib_power.json
```

输出：`lib_power.json` — 每种 cell 的 leakage_pW + 7×7 energy LUT

### Step 3：解析 SPEF 网络电容

```bash
python code/parse_spef.py \
    --spef design.spef \
    --out sim_result/report/net_cap.json
```

输出：`net_cap.json` — 每条 net 的总电容（pF）

### Step 4：生成功耗矩阵

```bash
python code/traditional_select.py \
    --toggles   sim_result/intermediate/input_toggles.jsonl \
    --vcd       input.vcd \
    --lib-power sim_result/report/lib_power.json \
    --net-cap   sim_result/report/net_cap.json \
    --def       design.def \
    --window-ns 20  --mx 50  --ny 50 \
    --timescale-ps 10 \
    --json-out  sim_result/report/report.json
```

## 参数说明

| 参数 | 默认 | 说明 |
|---|---|---|
| `--window-ns` | 20 | 时间窗口大小（ns），T = ceil(总时间 / window_ns) |
| `--mx` / `--ny` | 50 | tile 网格列数 / 行数 |
| `--vdd` | 0.7 | 电源电压 V |
| `--slew-ps` | 40 | LUT 查表用的固定 input slew（ps） |
| `--timescale-ps` | 10 | VCD timescale（ps），需与 VCD 头部一致 |

## 输出说明

### JSON 报告

```json
{
  "parameters": {
    "window_ns": 20, "T": 500, "mx": 50, "ny": 50,
    "vdd": 0.7, "slew_ps": 40, "timescale_ps": 10, "t_max_ticks": 1000000
  },
  "power_matrix_mW": [[[...], ...], ...],
  "avg_power_mW": [0.123, 0.456, ...]
}
```

- `power_matrix_mW`: 形状 `[T][ny][mx]`，每个 tile 每个窗口的总功耗（mW）
- `avg_power_mW`: 形状 `[T]`，每个窗口所有 tile 的平均功耗（mW）

## 一键运行（des3 示例）

```bash
cd F:/GraduatePrj/Classify/traditional_classify

python code/vcd_to_jsonl.py ../des_demo/vcd/test.vcd \
    --output-dir sim_result/intermediate/

python code/jsonl_toggle_mark.py sim_result/intermediate/test.jsonl

python code/parse_lib_power.py \
    --lib-dir ../des_demo/db/des3.enc.dat/libs/mmmc/ \
    --out sim_result/report/lib_power.json

python code/parse_spef.py \
    --spef ../des_demo/db/des3.spef \
    --out sim_result/report/net_cap.json

python code/traditional_select.py \
    --toggles   sim_result/intermediate/test_toggles.jsonl \
    --vcd       ../des_demo/vcd/test.vcd \
    --lib-power sim_result/report/lib_power.json \
    --net-cap   sim_result/report/net_cap.json \
    --def       ../des_demo/db/des3.def \
    --window-ns 20  --mx 50  --ny 50 \
    --timescale-ps 10 \
    --json-out  sim_result/report/report.json
```
