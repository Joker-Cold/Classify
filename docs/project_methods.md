# 面向动态 IR-Drop 签核的 VCD 压缩算法全流程

> 本文档汇总项目四大算法模块的完整流程，从原始 VCD 波形到压缩 VCD 输出，再到覆盖率验证。

---

## 总体流程概览

```
                        ┌──────────────────────┐
                        │   原始 VCD 波形文件   │
                        └──────────┬───────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    ▼              ▼               │
        ┌───────────────┐  ┌─────────────┐        │
        │ Module 1      │  │ 物理设计文件 │        │
        │ Traditional   │  │ DEF / SPEF  │        │
        │ Vector        │  │ .lib        │        │
        │ Profiling     │  └──────┬──────┘        │
        └───────┬───────┘         │               │
                │                 │               │
                ▼                 │               │
     ┌─────────────────────┐     │               │
     │ power_matrix_mW     │◄────┘               │
     │ [T][ny][mx]         │                     │
     └─────────┬───────────┘                     │
               │                                  │
               ▼                                  │
     ┌─────────────────────┐                     │
     │ Module 2            │                     │
     │ Risk Propagation    │                     │
     │ Profiling           │                     │
     └─────────┬───────────┘                     │
               │                                  │
               ▼                                  │
     ┌─────────────────────┐                     │
     │ risk_matrix         │                     │
     │ worst_per_window[]  │                     │
     └─────────┬───────────┘                     │
               │                                  │
               ▼                                  │
     ┌─────────────────────┐                     │
     │ Module 3            │◄────────────────────┘
     │ Worst-K Window      │   (原始 VCD 用于拼接)
     │ Selection & Splice  │
     └─────────┬───────────┘
               │
               ▼
     ┌─────────────────────┐
     │ 压缩 VCD 文件       │
     └─────────┬───────────┘
               │
               ▼
     ┌─────────────────────┐     ┌──────────────┐
     │ Voltus 仿真         │────►│ .iv 文件     │
     │ (orig + comp)       │     │ (实例电压)   │
     └─────────────────────┘     └──────┬───────┘
                                        │
                                        ▼
                               ┌─────────────────┐
                               │ Module 4        │
                               │ Coverage        │
                               │ Analysis        │
                               └─────────────────┘
                                        │
                                        ▼
                               ┌─────────────────┐
                               │ C_int / C_k     │
                               │ PASS / FAIL     │
                               └─────────────────┘
```

---

## Module 1: Traditional Vector Profiling（传统向量分析）

> 来源：Wen et al., *Risk Propagation Based Vector Profiling for High Coverage Dynamic IR-Drop Analysis*, ICCAD 2023
>
> 代码路径：`Traditional_Vector_Profiling/code/`

### 1.1 目标

将原始 VCD 波形转换为空间-时间功率密度矩阵 `power_matrix_mW[T][ny][mx]`，量化每个 tile 在每个时间窗口内的功耗。

### 1.2 输入

| 输入 | 格式 | 说明 |
|------|------|------|
| VCD 波形文件 | `.vcd` | 仿真产生的信号翻转记录 |
| Liberty 功率库 | `.lib` | 每种 cell 的漏电功耗 (pW) + 内部能量 LUT (7×7, fJ) |
| 寄生参数文件 | `.spef` | 每条 net 的总电容 (pF) |
| 物理设计文件 | `.def` | instance 坐标、net 连接关系 |

### 1.3 算法流程

#### Step 1: VCD → Toggle JSONL

```
VCD ──vcd_to_jsonl.py──► combined JSONL (hold-last-value)
                              │
                    jsonl_toggle_mark.py
                              │
                              ▼
                       toggles JSONL (per-bit XOR)
```

- **VCD 解析** (`parse_vcd_signal.py`): 解析 `$scope` / `$var` 层次结构，支持多 scope 去歧义
- **Hold-last-value**: 每个时刻输出所有信号当前值，未变化信号保持上一时刻值
- **Toggle 标记**: 逐 bit 与前一时刻 XOR，输出翻转位图 `{sig: "010...1"}`

#### Step 2: 功率参数解析

```python
# parse_lib_power.py
lib_power = {
    "BUFx6f_ASAP7": {
        "leakage_pW": 123.4,
        "energy_lut_fJ": [[...], ...]   # 7×7: slew × load → fJ/toggle
    }
}

# parse_spef.py
net_cap = {
    "u2/net_001": 0.0032   # pF
}
```

#### Step 3: 信号→功率映射

对每个 VCD 信号建立完整映射链：

```
VCD 信号全名 → strip testbench → DEF net path
                                      │
                    ┌─────────────────┤
                    ▼                 ▼
              pin→net 反查      driver instance
                    │                 │
                    ▼                 ▼
              C_net (SPEF)      cell_type (DEF)
                                      │
                                      ▼
                              energy_int_fJ (.lib LUT)
                              leakage_pW (.lib)
                                      │
                    ┌─────────────────┤
                    ▼                 ▼
              tile (iy, ix)    power parameters
              (DEF 坐标→网格)
```

#### Step 4: 功率矩阵计算

对每个窗口 $t$ 中的每个 tile $(i_y, i_x)$，累加所有落入该 tile 的 instance 功耗：

$$P_{t}[i_y][i_x] = \sum_{\text{inst} \in \text{tile}} \left( P_{\text{sw}} + P_{\text{int}} + P_{\text{leak}} \right)$$

其中：

$$P_{\text{sw}} = n_{\text{toggles}} \times \frac{1}{2} C_{\text{net}} \times V_{DD}^2 \times \frac{10^3}{W_{\text{ns}}} \quad (\text{mW})$$

$$P_{\text{int}} = n_{\text{toggles}} \times \frac{E_{\text{int\_fJ}}}{W_{\text{ns}}} \times 10^{-3} \quad (\text{mW})$$

$$P_{\text{leak}} = P_{\text{leak\_pW}} \times 10^{-9} \quad (\text{mW})$$

- $C_{\text{net}}$: SPEF 寄生电容 (pF)
- $E_{\text{int\_fJ}}$: Liberty LUT 插值（双线性，slew × load 维度）
- $W_{\text{ns}}$: 窗口宽度 (ns)

### 1.4 输出

```json
{
  "parameters": {
    "window_ns": 20, "T": 593, "mx": 50, "ny": 50,
    "vdd": 0.7, "slew_ps": 40, "timescale_ps": 10
  },
  "power_matrix_mW": [[[...]]],   // [T][ny][mx]
  "avg_power_mW": [...]           // [T] 全芯片平均功耗
}
```

### 1.5 关键脚本

| 脚本 | 功能 |
|------|------|
| `traditional_select.py` | 主流程编排：DEF/SPEF/LIB → 信号映射 → 功率矩阵 |
| `parse_vcd_signal.py` | VCD header 解析，scope 层次感知 |
| `vcd_to_jsonl.py` | VCD → combined JSONL |
| `jsonl_toggle_mark.py` | JSONL → toggles JSONL (XOR) |
| `parse_lib_power.py` | Liberty .lib → leakage + energy LUT |
| `parse_spef.py` | SPEF → net capacitance |

---

## Module 2: Risk Propagation Profiling（风险传播分析）

> 来源：Wen et al., ICCAD 2023, Eq. 3
>
> 代码路径：`risk_propagation_profiling/code/`

### 2.1 目标

基于 Green 函数模型，将功率密度图转换为 IR-drop 风险评分图。每个 tile 的风险不仅取决于自身功耗，还受到周围 tile 的传播影响。

### 2.2 输入

| 输入 | 说明 |
|------|------|
| `power_matrix_mW[T][ny][mx]` | Module 1 的输出 |
| 传播核函数 $G(r, r')$ | euclidean / exponential / logarithmic |
| 自影响因子 $\alpha$ | 控制 tile 自身功耗权重（默认 5.0） |

### 2.3 核心公式

对窗口 $t$ 中的 tile $r(x, y)$，其 IR-drop 风险评分为：

$$S_{r,t} = \frac{\sum_{r' \in R} P_{r',t} \cdot G(r, r')}{\sum_{r' \in R} G(r, r')}$$

其中 $G(r, r')$ 为传播核函数：

| 核函数 | $r \neq r'$ | $r = r'$ | 衰减特性 |
|--------|-------------|----------|----------|
| **Euclidean** | $\frac{1}{\sqrt{\Delta x^2 + \Delta y^2}}$ | $\alpha$ | 慢衰减 (1/d)，远距离影响大 |
| **Exponential** | $\exp\left(-\sqrt{\Delta x^2 + \Delta y^2}\right)$ | $\alpha$ | 快衰减 ($e^{-d}$)，局部主导 |
| **Logarithmic** | $\frac{1}{\ln(1 + \sqrt{\Delta x^2 + \Delta y^2})}$ | $\alpha$ | 中等衰减 ($1/\ln d$) |

### 2.4 算法流程

```
Step 1: 构建相对核矩阵
    G_rel[(2ny-1) × (2mx-1)]  ← 预计算所有偏移量组合

Step 2: 构建归一化图
    norm[i][j] = Σ_pq G_rel[i-p][j-q]   (全1功率的卷积)

Step 3: 逐窗口计算风险评分
    For each window t:
        For each tile (i, j):
            S_t[i][j] = [Σ_pq P_t[p][q] × G_rel[i-p][j-q]] / norm[i][j]

Step 4: 追踪最差窗口
    worst_per_window[t] = max_{i,j} S_t[i][j]
    worst_tiles[t] = argmax_{i,j} S_t[i][j]
```

**计算复杂度**: 预计算 $O(n_y \cdot m_x)$，归一化 $O(n_y^2 \cdot m_x^2)$，逐窗口 $O(T \cdot n_y^2 \cdot m_x^2)$

### 2.5 输出

```json
{
  "kernel": "euclidean",
  "alpha": 5.0,
  "parameters": { "T": 593, "ny": 50, "mx": 50 },
  "worst_per_window": [0.000071, ...],   // 长度 T
  "worst_tiles": [[6, 4], ...],          // T 个 (row, col)
  "risk_matrix": [[[...]]]              // [T][ny][mx]
}
```

### 2.6 关键脚本

| 脚本 | 功能 |
|------|------|
| `risk_propagation.py` | 唯一入口：核函数构建 → 归一化 → 逐窗口风险计算 → JSON 输出 |

---

## Module 3: Worst-K Window Selection & VCD Splice（选窗与 VCD 拼接）

> 代码路径：`worst_k_windows/code/`

### 3.1 目标

基于风险评分排序，选出最具 IR-drop 风险的时间窗口，从原始 VCD 中提取对应片段拼接为压缩 VCD。

### 3.2 输入

| 输入 | 说明 |
|------|------|
| 风险报告 JSON | Module 2 的输出（`worst_per_window[]` + 参数） |
| 原始 VCD 文件 | 完整仿真波形 |
| `threshold_ratio` | 阈值比例（默认 0.6），选取 score ≥ ratio × max(score) 的窗口 |

### 3.3 算法流程

#### Step 1: 热点窗口选择

**模式 A — 离散热点选择（默认）**

```
max_score = max(worst_per_window)
threshold = threshold_ratio × max_score

selected = { i : worst_per_window[i] ≥ threshold }
```

选出的窗口数量由数据分布决定，典型地 threshold_ratio=0.6 时选出约 40% 的窗口。

**模式 B — 连续块选择（`--continuous`）**

```
K = |{ i : worst_per_window[i] ≥ threshold }|   // 目标块大小
best_start = argmax_{s} Σ_{i=s}^{s+K-1} worst_per_window[i]
selected = [best_start, best_start+1, ..., best_start+K-1]
```

适用于需要连续高活跃段（退耦电容持续耗尽场景）的选取。

#### Step 2: 窗口索引→时间区间映射与合并

```
window_size = t_max / T

For each selected window i:
    start[i] = i × window_size - warmup_ticks
    end[i]   = (i+1) × window_size

merged_intervals = merge_overlapping(sorted intervals)
```

- `warmup_ticks`: 可选预热时钟，补偿退耦电容充电周期
- 合并重叠区间，减少 `$dumpvars` 冗余

#### Step 3: 两遍 VCD 拼接

**Pass 1 — 收集边界状态**

```
遍历原始 VCD:
    维护 last_values[symbol] = 每个信号最新值
    在每个 interval 入口处记录所有信号的当前值
    统计每个 interval 内有翻转的信号集合
```

**Pass 2 — 写出压缩 VCD**

```
写出 VCD header（与原始相同）

For each merged interval:
    写 $dumpvars（仅包含该 interval 内有翻转的信号）
    写该 interval 内的所有 #timestamp + 信号变化

写 $end
```

**关键实现细节**:
- **Hold-last-value 语义**: 每个 interval 入口恢复信号边界状态，避免无状态初始化的伪翻转
- **信号过滤**: 仅 dump 在该 interval 内有 ≥1 次变化的信号，减少大电路（42K+ 信号）的 dumpvars 开销
- **强制 LF 换行**: `open(path, 'w', newline='\n')`，防止 Windows CRLF 导致 Voltus `VOLTUS_POWR-1735` 语法错误

### 3.4 输出

| 输出 | 说明 |
|------|------|
| `worst_k_{kernel}.json` | 选窗报告：热点窗口列表、阈值参数、top-k 统计 |
| `worst_k_{kernel}.vcd` | 压缩 VCD 文件（仅包含选中时间窗口） |

**典型压缩效果**:

| threshold_ratio | 保留窗口比例 | VCD 压缩率 |
|----------------|-------------|-----------|
| 0.5 | ~60% | ~40% |
| 0.7 | ~30% | ~70% |
| 0.95 | ~5% | ~95% |

### 3.5 关键脚本

| 脚本 | 功能 |
|------|------|
| `select_worst_k.py` | 核心算法：选窗 + 区间合并 + 两遍 VCD 拼接 |
| `sweep_dma.sh` | DMA_slow 多阈值 × 多核函数参数扫描 |
| `sweep_des_perf.sh` | des_perf_slow 参数扫描 |
| `batch_run.sh` | 多电路批量执行 |
| `regen_t08_all.sh` | 4 电路 t=0.8 基线重生成 |

---

## Module 4: Coverage Analysis（覆盖率分析）

> 代码路径：`coverage_analysis/code/`

### 4.1 目标

对比原始 VCD 和压缩 VCD 在 Voltus 仿真下的 IR-drop 结果，验证压缩是否保留了 worst-case 特征。

### 4.2 输入

| 输入 | 说明 |
|------|------|
| `orig.iv` | 原始 VCD 的 Voltus 实例电压文件 |
| `comp.iv` | 压缩 VCD 的 Voltus 实例电压文件 |
| DEF 文件（可选） | 用于物理位置可视化 |

### 4.3 评价指标

#### 指标 1: 强度覆盖率 $C_{\text{int}}$

$$C_{\text{int}} = \frac{\max_{i}\, \text{IRdrop}^{\text{comp}}(i)}{\max_{i}\, \text{IRdrop}^{\text{orig}}(i)} \times 100\%$$

- $C_{\text{int}} = 100\%$: 无损
- $C_{\text{int}} < 100\%$: 欠估计（**危险**，可能漏掉违例）
- $C_{\text{int}} > 100\%$: 过估计（保守，可接受）
- **目标**: $C_{\text{int}} \geq 95\%$（对齐 Hu et al. ACM TODAES 2025）

#### 指标 2: 位置覆盖率 $C_k$

$$C_k = \frac{1}{N} \sum_{n=1}^{N} \mathbb{1}\left[ \text{top-}k^{\text{comp}}_n \supseteq \text{top-}k^{\text{orig}}_n \right]$$

- 严格全命中：top-k 热点实例名精确匹配（零容差）
- $k \in \{1, 3, 5, 10\}$ 四级评估
- **目标**: $C_1 \geq 90\%$（对齐 Wen et al. ICCAD 2023）

#### 综合判定

| $C_{\text{int}} \geq 95\%$ | $C_1 \geq 90\%$ | 判定结果 |
|:---:|:---:|:---:|
| ✓ | ✓ | **PASS** |
| 部分满足 | 部分满足 | **MARGINAL** |
| ✗ | ✗ | **FAIL** |

### 4.4 算法流程

```
Step 1: 解析 .iv 文件
    For each instance line:
        IRdrop_mV = (V_nom - WIN_EIV) × 1000
    → {instance_name: ir_drop_mV}

Step 2: 计算 C_int
    C_int = max(comp) / max(orig) × 100%

Step 3: 计算 C_k
    For k in {1, 3, 5, 10}:
        top_k_orig = k 个 orig IR drop 最高的 instance
        top_k_comp = k 个 comp IR drop 最高的 instance
        hit[k] = 1 if top_k_orig ⊆ top_k_comp else 0

Step 4: 多组聚合（可选）
    C_int_mean = mean(C_int[n])
    C_int_min  = min(C_int[n])
    C_k[k]     = mean(hit[k][n]) × 100%

Step 5: 判定 Verdict
```

### 4.5 扩展分析

- **物理位置映射** (`extract_results.py`): 结合 DEF 坐标，生成 instance 级 IR-drop 空间分布 CSV
- **热点排名对比**: orig top-20 vs comp top-20，追踪排名漂移
- **交互式可视化** (`visualize_hotspot.py`): Plotly 仪表盘，含 4 张图表：
  1. Top-20 热点 IR-drop 对比柱状图
  2. 排名漂移散点图 (orig rank → comp rank)
  3. 热点空间分布散点图
  4. 详细数据表

### 4.6 输出

| 输出 | 说明 |
|------|------|
| `coverage_*.json` | C_int / C_k 指标 + 判定结果 |
| `summary.json` | 详细统计：均值/最小/最大 IR drop |
| `ir_drop_map.csv` | 全 instance IR-drop + 坐标 |
| `hotspot_top20.csv` | 热点排名对比表 |
| `hotspot_visualization.html` | 交互式分析仪表盘 |

### 4.7 关键脚本

| 脚本 | 功能 |
|------|------|
| `parse_iv.py` | 解析 Voltus `.iv` 文件 → `{instance: ir_drop_mV}` |
| `evaluate.py` | 主入口：C_int + C_k 计算、聚合、判定 |
| `extract_results.py` | 扩展分析：DEF 物理坐标 + CSV + summary.json |
| `visualize_hotspot.py` | Plotly 交互式仪表盘生成 |

---

## 端到端执行示例

```bash
# ═══ Module 1: Traditional Vector Profiling ═══

# 1a. VCD → Toggle JSONL
python Traditional_Vector_Profiling/code/vcd_to_jsonl.py input.vcd \
    --output-dir sim_result/intermediate/
python Traditional_Vector_Profiling/code/jsonl_toggle_mark.py \
    sim_result/intermediate/input.jsonl

# 1b. 解析功率参数
python Traditional_Vector_Profiling/code/parse_lib_power.py \
    --lib-dir mmmc/ --out sim_result/report/lib_power.json
python Traditional_Vector_Profiling/code/parse_spef.py \
    --spef design.spef --out sim_result/report/net_cap.json

# 1c. 生成功率矩阵
python Traditional_Vector_Profiling/code/traditional_select.py \
    --toggles sim_result/intermediate/input_toggles.jsonl \
    --vcd input.vcd --lib-power sim_result/report/lib_power.json \
    --net-cap sim_result/report/net_cap.json --def design.def \
    --window-ns 20 --mx 50 --ny 50 \
    --json-out sim_result/report/report.json

# ═══ Module 2: Risk Propagation Profiling ═══

python risk_propagation_profiling/code/risk_propagation.py \
    --report sim_result/report/report.json \
    --kernel all --alpha 5 \
    --output-dir risk_propagation_profiling/sim_result/

# ═══ Module 3: Worst-K Window Selection ═══

python worst_k_windows/code/select_worst_k.py \
    --risk-report risk_propagation_profiling/sim_result/report/risk_euclidean.json \
    --vcd input.vcd \
    --threshold-ratio 0.7 \
    --output-dir worst_k_windows/sim_result/

# ═══ Voltus 仿真（EDA 服务器） ═══
# 分别用 orig VCD 和 compressed VCD 跑 Voltus Rail Analysis
# 得到 orig.iv 和 comp.iv

# ═══ Module 4: Coverage Analysis ═══

python coverage_analysis/code/evaluate.py \
    --orig orig.iv --comp comp.iv --ks 1 3 5 10

python coverage_analysis/code/extract_results.py \
    --orig orig.iv --comp comp.iv --def design.def --out result/

python coverage_analysis/code/visualize_hotspot.py
```

---

## 关键参数汇总

| 参数 | 模块 | 默认值 | 说明 |
|------|------|--------|------|
| `window_ns` | M1 | 20 | 时间窗口宽度 (ns) |
| `mx`, `ny` | M1 | 50 | Tile 网格尺寸 |
| `vdd` | M1 | 0.7 | 供电电压 (V) |
| `slew_ps` | M1 | 40 | LUT 查表用输入 slew (ps) |
| `alpha` | M2 | 5.0 | 自影响因子（tile 自身权重） |
| `kernel` | M2/M3 | all | 传播核：euclidean / exponential / logarithmic |
| `threshold_ratio` | M3 | 0.6 | 选窗阈值 = ratio × max(worst_score) |
| `warmup_ticks` | M3 | 0 | 每个窗口前的预热时钟周期 |
| `ks` | M4 | 1,3,5,10 | top-k 位置覆盖率评估级别 |

---

## 实验观察与关键结论

1. **Toggle count 无法精确定位 worst-case IR Drop**: 排名第 45 的周期才是实际 worst-case（退耦电容累积耗尽效应）
2. **空间传播核差异显著**:
   - DMA_slow: traditional ≈ exponential（指数核自权重=1，等效 toggle 排序）
   - des_perf_slow: traditional ≠ exponential（大电路稀疏功率矩阵下两核差异明显）
   - euclidean ≈ logarithmic（在小 K 场景下相对排序一致）
3. **Pareto 最优组合**:
   - 高压缩率优先: `traditional t=0.95`（压缩率 65-73%, C_int ≥ 93%）
   - Jaccard 热点匹配优先: `logarithmic t=0.5`（压缩率 ~10%, J@10 最高 0.54）
   - 综合推荐: `traditional t=0.7`（压缩率 ~77%, C_int ≥ 100%, 精度与压缩双优）
4. **C_int 全面 ≥ 93%**: 所有核函数 × 阈值组合均满足工程可接受范围
