# Risk Propagation 向量分析算法

> 来源：*Risk Propagation Based Vector Profiling for High Coverage Dynamic IR-Drop Analysis* (Wen et al.)

## 输入

| 输入 | 说明 |
|------|------|
| 功率密度图 P | T 张 m×n 的tile功率密度图，每张对应一个波形窗口，由功率分析工具生成 |
| Tile网格形状 (m, n) | 物理tile网格的行列数（实验中使用 50×50） |
| 自影响因子 α̂ | 控制tile自身功耗的IR-drop权重（实验中设为 5） |
| 选择数量 k | 需要选出的top-k个高风险窗口数 |

## 输出

| 输出 | 说明 |
|------|------|
| 窗口索引列表 τ | 包含 k 个最高风险窗口的编号 |
| IR-drop风险评分图 S | k 张 m×n 的评分图，标识每个窗口中IR-drop高风险区域 |

## 核心公式

### Eq. 3：IR-drop风险评分

对窗口 t 中的 tile r(x,y)，其IR-drop风险评分为：

```
              Σ_{r'∈R}  P_{r',t} · G(r, r')
S_{r,t} = ─────────────────────────────────────
              Σ_{r'∈R}  1 · G(r, r')
```

- **分子**：所有tile的功率密度，以Green函数为权重的加权求和。表示tile r处受到的总IR-drop（自身 + 周围传播）
- **分母**：所有tile功率密度均为1时的加权求和。归一化因子，消除边界效应，使功率均匀分布时评分也均匀

### Eq. 4：Green函数（分段定义）

```
            ⎧  1 / √((x-x')² + (y-y')²)    当 r ≠ r'（不同tile）
G(r, r') =  ⎨
            ⎩  α                              当 r = r'（同一tile）
```

- **r ≠ r'**：使用欧氏距离的倒数，模拟IR-drop随距离衰减的传播。距离越远，传播的IR-drop越小
- **r = r'**：自影响因子 α，表示tile自身功耗引起的IR-drop强度
  - α 大 → tile的IR-drop主要由自身功耗决定
  - α 小 → tile的IR-drop主要由周围传播决定
  - 取值范围 1~∞，实验中 α=5

**简化假设**：PDN线宽受设计规则约束、布线均匀（尤其在multi-pattern层），因此用自由空间Green函数（忽略边界条件）近似即可。

## 算法流程 (Algorithm 1)

### 阶段一：预计算Green函数

```
输入：tile网格 R (m×n), 自影响因子 α̂
输出：Green函数数组 G，大小 (m·n) × m × n

对每个源tile r'(p,q) ∈ R:          // 可并行
    对每个目标tile r(i,j) ∈ R:
        if r == r':
            G[p*m+q, i, j] = α̂
        else:
            G[p*m+q, i, j] = 1 / √((i-p)² + (j-q)²)
```

- 只依赖网格形状，**计算一次，所有窗口复用**
- 网格形状改变时需要重新计算
- 不同tile的计算相互独立，可并行

### 阶段二：对每个窗口计算评分图

```
输入：功率密度图 P (T张 m×n), Green函数 G
输出：评分图 S (T张 m×n), 全局最差评分 Sworst (T个标量)

对每个窗口 t = 1,2,...,T:            // 可并行
    对每个tile r(i,j) ∈ R:
        numerator   = Σ_{r'(p,q)∈R}  P_t[p,q] · G[p*m+q, i, j]
        denominator = Σ_{r'(p,q)∈R}  1        · G[p*m+q, i, j]
        S_t[i,j] = numerator / denominator
    Sworst[t] = max(S_t)             // 该窗口的全局最差评分
```

- 不同窗口的计算相互独立，可并行

### 阶段三：选择top-k窗口

```
τ = Sworst 中最大的 k 个值对应的窗口索引
S = 这 k 个窗口对应的评分图
返回 τ, S
```

## 计算复杂度

| 阶段 | 复杂度 | 说明 |
|------|--------|------|
| Green函数预计算 | O((m·n)²) | 一次性，可并行 |
| 单窗口评分图 | O((m·n)²) | 本质是功率图与Green函数核的"卷积" |
| 所有窗口评分 | O(T · (m·n)²) | 可并行 |
| 窗口选择 | O(T·log k) | top-k排序 |

实验配置：50×50网格，8进程并行，运行时间比传统方法仅增加 4%~9%。
