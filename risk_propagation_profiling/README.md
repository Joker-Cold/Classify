# Risk Propagation Profiling — 热点传播风险评估

基于 Green 函数的 IR-drop 风险传播算法（Wen et al.），支持三种可插拔传播核函数。

## 核函数

| 核函数 | G(r, r') 当 r ≠ r' | G(r, r') 当 r = r' |
|--------|---------------------|---------------------|
| euclidean（论文原始） | 1 / sqrt(dx² + dy²) | alpha |
| exponential | exp(-sqrt(dx² + dy²)) | alpha |
| logarithmic | 1 / ln(1 + sqrt(dx² + dy²)) | alpha |

## 用法

```bash
python code/risk_propagation.py \
    --report ../Traditional_Vector_Profiling/sim_result/report/report.json \
    --kernel all --alpha 5 \
    --output-dir sim_result/
```

## 输入

- `report.json` — 来自 Traditional_Vector_Profiling，包含 `power_matrix_mW[T][ny][mx]` 和 `parameters`

## 输出

- `sim_result/report/risk_<kernel>.json` — 风险矩阵 + 每窗口最差评分
