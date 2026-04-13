# Coverage Analysis — 双维度热点覆盖率评估

对 Voltus Dynamic IR Drop 仿真结果（原始 VCD vs 压缩 VCD）计算两个覆盖率指标：

| 指标 | 公式 | 含义 |
|---|---|---|
| **C_int** | `V_comp_max / V_orig_max × 100%` | 强度覆盖率：压缩后最坏 IR Drop 是否保真 |
| **C_k**   | `P_{top-k}` (严格全命中率)        | 位置覆盖率：top-k 热点位置是否保留    |

## 目录结构

```
coverage_analysis/
├── README.md
├── code/
│   ├── evaluate.py       ← 主脚本：计算 C_int + C_k，输出 JSON 报告
│   └── parse_iv.py       ← 解析 Voltus .iv 文件 → {inst: ir_drop_mV}
├── example_data/
│   ├── orig.iv           ← 原始 VCD 仿真的 Voltus instance voltage 文件
│   └── comp.iv           ← 压缩 VCD 仿真的 Voltus instance voltage 文件
└── result/               ← 输出目录（JSON 报告）
```

## 环境要求

- Python 3.8+，无第三方依赖

## 输入文件

Voltus 仿真完成后，每次运行会生成 `VDD_VSS.iv`（或 `VDD_VSS.worst.iv`）：

```
<voltus_db>/Reports/VDD_VSS.iv
```

对**原始 VCD** 和**压缩 VCD** 各跑一次 Voltus，得到两个 `.iv` 文件，即为本模块的输入。

## 用法

### 单组对比

```bash
python code/evaluate.py \
    --orig example_data/orig.iv \
    --comp example_data/comp.iv
```

### 多组对比（批量 N 次运行）

准备 `runs.txt`，每行一对 `orig.iv  comp.iv`：

```
/path/run1/VDD_VSS.iv  /path/run1_comp/VDD_VSS.iv
/path/run2/VDD_VSS.iv  /path/run2_comp/VDD_VSS.iv
```

```bash
python code/evaluate.py --runs runs.txt --out result/report.json
```

### 参数说明

| 参数 | 说明 |
|---|---|
| `--orig` | 原始仿真 .iv 文件路径 |
| `--comp` | 压缩仿真 .iv 文件路径 |
| `--runs` | 批量对比文本文件（与 --orig/--comp 互斥） |
| `--ks`   | k 值列表，默认 `1 3 5 10` |
| `--out`  | 输出 JSON 报告路径（不指定则打印到 stdout）|

## 输出示例

```
  orig.iv vs comp.iv  C_int=97.07%  top-1=HIT

========== Coverage Evaluation Report ==========
  Runs    : 1
  C_int   : mean=97.07%  min=97.07%  std=0.00%
  C_k     : k=1: 100.0%  k=3: 100.0%  k=5: 100.0%  k=10: 100.0%
  Verdict : PASS
=================================================
```

### JSON 报告字段

```json
{
  "summary": {
    "n_runs": 1,
    "C_int_mean_%": 97.07,
    "C_int_min_%":  97.07,
    "C_int_std_%":  0.0,
    "C_k_%": {"1": 100.0, "3": 100.0, "5": 100.0, "10": 100.0}
  },
  "verdict": "PASS",
  "per_run": [...]
}
```

## 判定准则

| 条件 | Verdict |
|---|---|
| C_int_min ≥ 95% **且** C_k(1) ≥ 90% | **PASS** |
| 其中一个满足 | **MARGINAL** |
| 两者均不满足 | **FAIL** |

## 一键运行示例（example_data）

```bash
cd F:/GraduatePrj/Classify/coverage_analysis
python code/evaluate.py --orig example_data/orig.iv --comp example_data/comp.iv --out result/report.json
```
