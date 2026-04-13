# 面向 IR Drop 签核的双维度热点覆盖率指标

## 一、指标 1：强度覆盖率 $C_{\text{int}}$

$$C_{\text{int}} = \frac{V^{\text{comp}}_{\max}}{V^{\text{orig}}_{\max}} \times 100\%$$

其中 $V_{\max} = \max_{t,\, i} V(t, i)$ 为全局最大 IR Drop（**位置盲，Definition 1a**）。

- $C_{\text{int}} = 100\%$：压缩无损
- $C_{\text{int}} < 100\%$：欠估计（危险）
- $C_{\text{int}} > 100\%$：过估计（保守）

**报告方式**：对 $N$ 组 VCD 报告均值 / 最小值 / 标准差
**目标**：$C_{\text{int}} \geq 95\%$（对齐 Hu 2025 的 3.89% 误差）

---

## 二、指标 2：位置覆盖率 $C_k$

$$C_k = P_{\text{top-}k} = \frac{1}{N} \sum_{n=1}^{N} \mathbb{1}\!\left[ S^{\text{comp}}_n \supseteq S^{\text{orig}}_n \right]$$

- $S^{\text{orig}}_n$：第 $n$ 组原始 VCD 分析的 top-$k$ 热点位置集合
- $S^{\text{comp}}_n$：压缩 VCD 分析的 top-$k$ 热点位置集合
- 命中判定：**严格全命中**，位置 $(t, i)$ 精确匹配（零容差）

**报告方式**：$k \in \{1, 3, 5, 10\}$ 四条曲线
**目标**：$P_{\text{top-1}} \geq 90\%$（对齐 Wen ICCAD 2023）

---

## 三、实现（伪代码）

```python
import numpy as np

def C_int(V_orig, V_comp):
    """强度覆盖率（单组 VCD），返回百分比"""
    return V_comp.max() / V_orig.max() * 100

def hit_topk(V_orig, V_comp, k):
    """单组 top-k 严格全命中"""
    idx_orig = set(np.argpartition(V_orig.ravel(), -k)[-k:])
    idx_comp = set(np.argpartition(V_comp.ravel(), -k)[-k:])
    return int(idx_orig.issubset(idx_comp))

def evaluate(runs, ks=(1, 3, 5, 10)):
    """
    runs: list of (V_orig, V_comp) pairs
    """
    c_vals = [C_int(o, c) for o, c in runs]
    return {
        "C_int_mean": np.mean(c_vals),
        "C_int_min":  np.min(c_vals),
        "C_k": {k: np.mean([hit_topk(o, c, k) for o, c in runs]) for k in ks},
    }
```

---

## 四、联合解读

| $C_{\text{int}}$ | $P_{\text{top-}k}$ | 结论                         |
| ---------------- | ------------------ | ---------------------------- |
| 高               | 高                 | 压缩方案可用于签核           |
| 高               | 低                 | 值对但位置乱，ECO 定位不可靠 |
| 低               | 高                 | 位置对但系统性欠估计         |
| 低               | 低                 | 压缩方案失败                 |

两个指标同时满足，才判定压缩后 VCD 在 DVD 签核意义下保持了等价覆盖率。

---

## 五、文献对齐

| 指标               | 对齐文献                                             |
| ------------------ | ---------------------------------------------------- |
| $C_{\text{int}}$   | Hu et al., ACM TODAES 2025（max error 3.89%）        |
| $C_1$（$k=1$）     | Wen et al., ICCAD 2023（worst-window 命中概率 4.3×） |
| $C_k$（$k>1$）曲线 | 本文将 Wen 的 $k=1$ 定义推广至 top-$k$               |
