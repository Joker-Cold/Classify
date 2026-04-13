# RC-Tile 最坏功耗窗口选择算法

> **当前版本**：m4（2026-04-08）
> **设计原则**：轻量级（纯 Python，单遍扫描，无训练）、物理可解释、以找到 worst hotspot 为第一优先级。

---

## 1. 算法定位

**目标**：从 VCD 动态仿真中自动选取一组时间窗口，拼接为压缩 VCD，送 Innovus / Voltus 做 PDN 动态仿真，以最小代价覆盖真实最坏 IR Drop 场景。

**优先级顺序**：
1. 覆盖 worst hotspot（ratio = peak_sub / peak_full ≥ 0.95）
2. 最小化压缩率 β（窗口总时长 / 仿真总时长）
3. 算法可解释（每步有明确物理意义）

**算法特点**：
- 无需训练数据或标注样本
- 单遍扫描，复杂度 O(N_cycles × N_signals)
- 纯 Python，可在任意环境运行
- 每一步可独立验证，方便调试

---

## 2. 五阶段流程

```
VCD + DEF + SPEF
      │
      ▼
Stage 1: 信号翻转统计    每个 cycle 累计 toggle 总数 c_i
      │
      ▼
Stage 2: Phase 检测      基于 median 阈值找持续活跃段
      │
      ▼
Stage 3: RC 加权打分     e_t = max_k(I_{t,k} × R̂_k)，peak-tile 危险评分
      │
      ▼
Stage 4: β-budget 窗口生成  在 phase 内贪心采样，直到预算耗尽
      │
      ▼
Stage 5: VCD 拼接输出    时间重映射，段间插 $comment，送 Innovus
```

### Stage 1：信号翻转统计

**输入**：Toggle JSONL（逐信号逐周期 toggle 数）
**输出**：`c[i]`，第 i 个 clock cycle 的 toggle 总数

**物理意义**：toggle 数正比于动态开关功耗；高 toggle 密度的 cycle 对应高功耗时刻。

```python
for (t, signal, n_toggles) in jsonl:
    i = int(t / T_clk)
    c[i] += n_toggles
```

---

### Stage 2：Phase 检测

**输入**：`c[i]`
**输出**：活跃相位列表 `[ps_j, pe_j)`

**物理意义**：worst IR drop 必然出现在设计处于"持续工作状态"的时段（phase）内，而非孤立的毛刺周期。Phase 检测过滤空闲段，将后续搜索限定在有意义的区域。

```
θ = k_θ × median({c_i | c_i > 0})   # 活跃阈值
a_i = 1 if c_i > θ else 0
合并连续 a_i=1 区间（容忍 gap 个空洞），过滤长度 < n_min 的微小 phase
```

关键参数：`--k-theta`（默认 1.0），增大使 phase 更短更精确，减小更保守。

---

### Stage 3：RC 加权 Tile 打分

**输入**：Toggle JSONL + DEF（坐标映射）+ SPEF（电阻权重）
**输出**：`e_t`，每个 cycle 的危险评分

**物理意义**：将芯片划分为 N×N 个空间 tile，计算每个 tile 的 IR drop 代理值 P_{t,k} = I_{t,k} × R̂_k，取全局最大值作为该 cycle 的危险评分。这直接对应"最弱 tile 的瞬时 PDN 压力"，比全局总功率更贴近 IR drop 的局部失效物理。

$$e_t = \max_k \left( \hat{R}_k \cdot \sum_{s \in \text{tile } k} n_{s,t} \cdot w_s \right)$$

其中：
- `w_s = C_load`（来自 SPEF，为信号的物理电容权重）
- `R̂_k = clip(R_k / median(R_k), 0.5, 2.5)`（归一化 tile 电阻）

---

### Stage 4：β-budget 自适应窗口生成（m4 核心）

**输入**：phase 列表 + `e_t` + 预算参数
**输出**：窗口列表 `{W_1, W_2, ...}`

**物理意义**：β 的物理含义是"Innovus 验证时长 / 原始仿真时长"，直接对应工程成本。在预算约束下，用贪心 argmax 逐步采样最危险位置，每次禁用采样区域周围 min_gap 个 cycle，防止窗口堆叠。

```python
L = 2 * K_min + 1                      # 窗口长度（cycles）
K_target = ceil(beta_budget * N_c / L) # 预算对应最多窗口数

mask = [True] * (pe - ps)
picks = []
accum = 0

while True:
    if top_k > 0 and len(picks) >= top_k:       # top-K 上限（兼容旧接口）
        break
    if beta_budget > 0 and len(picks) >= 1:
        if (accum + L) / N_c > beta_budget:      # β 预算耗尽
            break

    best = argmax over mask of e_t[ps:]
    if best < 0:
        break                                    # phase 内无可选 cycle

    picks.append(best)
    accum += L
    mask[best - min_gap : best + min_gap] = False  # 禁用邻近区域
```

---

### Stage 5：VCD 拼接输出

两遍扫描原始 VCD：
- **Pass 1**：采集每个窗口起始时刻的全部信号状态（边界快照，确保初始值正确）
- **Pass 2**：写 `$dumpvars` + 流式拼接，时间重映射到 0 开始，段间插 `$comment`

输出 VCD 送 Innovus 做完整 PDN 瞬态仿真，Python 不重复建模积分过程。

---

## 3. 关键参数

| 参数 | 默认值 | 含义 | 建议 |
|---|---|---|---|
| `--beta-budget` | 0.0（关闭）| **核心参数**：压缩预算（0~1） | **推荐 0.10** |
| `--top-k` | 0 | 每 phase 最多窗口数；与 beta-budget 联合使用取先满足者 | 单独使用时设 2~3 |
| `--small-window` | 关闭 | 启用 m2+ 精准小窗模式（L=5 cycles）| 推荐开启 |
| `--min-gap-cycles` | 10 | 两窗口中心最小间距（cycles）| 建议 ≥ L_w |
| `--k-min` | 2 | 窗口半宽（cycles），L_w = 2k_min+1 = 5 | 一般不改 |
| `--n-grid` | 8 | tile 边数（8×8=64 个 tile）| 小设计 6，大设计 10 |
| `--k-theta` | 1.0 | phase 阈值倍率 | 增大→phase 更精确；减小→更保守 |

---

## 4. 推荐用法

```bash
# 标准用法：找最坏热点（推荐）
python find_worst_window.py \
    --vcd test.vcd --def design.def --spef design.spef \
    --small-window --beta-budget 0.10

# 快速验证（低 β，适合已知 cluster 数目的设计）
python find_worst_window.py ... --small-window --top-k 2

# 高精度（允许更高 β，对打分偏差容忍度更高）
python find_worst_window.py ... --small-window --beta-budget 0.20
```

---

## 5. 实验验证结果

测试设计：DES3（ASAP7 工艺），VCD 时长 11850 ns / 23850 ns，T_clk=50 ns。

### 5.1 各算法版本对比

| 版本 | 核心机制 | test.vcd β | test.vcd ratio | test_2x.vcd β | test_2x.vcd ratio |
|---|---|---|---|---|---|
| m0 | sum-based score | 29.8% | 0.962 | — | — |
| m1 | peak-tile e_t = max_k P_{t,k} | — | 改善 | — | — |
| m2 | small-window + argmax center | 2.1% | 0.808 | — | — |
| m3 | top-K=2 非重叠 argmax | 4.2% | **1.000** ✅ | 2.09% | 0.882 |
| **m4** | β-budget=10% 自适应 | **4.2%** | **1.000** ✅ | **9.41%** | **0.882** |
| spatial_temporal | 空间格子局部投票 union | — | — | 30.9% | **1.000** ✅ |

### 5.2 m4 vs m3：关键观察

**在 test.vcd 上，m4（9 窗）与 m3（2 窗）结果完全相同（均 30 mV）。**

这不是偶然：m4 用 β-budget 贪心采样出了 9 个窗口，但最终 Innovus 报告的 peak drop 与 m3 的 2 窗结果一致，说明**问题根源在于打分公式的系统性偏差，而非窗口数量不足**。增加窗口数不能弥补 e_t 排序的偏差——如果真实 worst hotspot 在 Python 排名靠后，再多的窗口也只是在"次优位置"重复采样。

---

## 6. 算法局限性与下一步

### 6.1 e_t 打分公式的系统偏差

`e_t = max_k P_{t,k}` 假设"单 tile 峰值电流 ∝ IR drop"。但真实 IR drop 还受以下因素影响，Python 模型无法感知：
- **邻接 tile 电流叠加**：PG 弱区附近多个 tile 的协同效应
- **PG mesh 几何**：电阻路径长度因布线结构而异
- **decap 局部分布**：本地去耦电容对瞬态噪声的抑制作用
- **封装电感瞬态响应**：L×di/dt 分量

实测（DES3 test_2x.vcd）：
- 真实 worst 区域（Innovus 34 mV）在 Python e_t 中约为 rank#13~20
- e_t 相对 max 约 93~94%，系统低估约 6%

**直接后果**：m4 与 m3 在 test.vcd 上结果相同（均 30 mV），增加窗口数无济于事。

### 6.2 spatial_temporal 为何能找到更坏热点

spatial_temporal 为每个 tile 独立打分（100 个局部专家），取所有热点的 union，能捕捉"电流不集中但 PG 弱"的区域。代价是 β 固定约 30%（是 m4 的 3 倍）。

| 维度 | RC-Tile m4 | spatial_temporal |
|---|---|---|
| 打分策略 | 1 个全局 peak-tile 评分 | N×N 个局部评分取 union |
| β | ~10%（可配置）| ~30%（固定）|
| 偏差方向 | 可能漏 PG 弱区 hotspot | 可能过选（均匀设计上 cluster 过滤失效）|
| 可解释性 | 高（每步有物理公式）| 中（投票机制直觉合理但无物理公式）|

### 6.3 m5 方向

**触发条件**：m4（budget=10%）仍漏 hotspot，即 ratio < 0.95。

**改进方向**：在 Stage 3 打分时引入空间邻接权重，让"PG 弱区附近的 tile 簇"获得更高危险分数，而不仅依赖单 tile 最大值。这能从根本上修复打分公式偏差，而不是靠增加窗口数来覆盖偏差。

---

## 7. 版本演进记录

| 版本 | 核心改动 | 主要结论 |
|---|---|---|
| m0 | sum-based score + ρ=0.7 中心选取 | ratio=0.962，β=29.8%，ρ 机制卡在两簇中间 |
| m1 | peak-tile e_t，max S(W) | 与 m0 字节级一致（单 phase 单候选，sum/max 等价）|
| m2 | small-window L=5，argmax 为中心 | ratio=0.808，β=2.1%，Python argmax 漏 cluster① |
| m3 | top-K=2 贪心双 argmax | ratio=1.000（test.vcd ✅），test_2x 漏 34mV hotspot |
| **m4** | β-budget 自适应采样（本版本）| test.vcd 结果与 m3 相同（打分偏差是根因，非窗口数不足）|
| spatial_temporal | 空间格子局部投票 | test_2x ratio=1.000 ✅，β=30.9%（高 3× 于 m4）|
