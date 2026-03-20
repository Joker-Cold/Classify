# PI 仿真覆盖率评估方法论 — 伪代码与科学性分析

> 核心问题：**给定一组从完整 VCD 中筛选出的时间窗口子集，如何科学地量化该子集对 worst-case IR Drop 场景的覆盖程度？**

---

## 一、问题形式化

### 1.1 符号定义

```
S_full          完整 VCD 仿真激励（N 个时钟周期）
S_sub           子集 VCD 激励（k 个窗口，每窗 w 个周期，k·w << N）
Φ(S)            对激励 S 执行 Voltus Dynamic IR Drop 仿真的结果集
V_nom           标称电源电压（如 0.7V）
V_min(S)        仿真结果中的全局最低电压
ΔV(S)           全局最大 IR Drop = V_nom − V_min(S)
ΔV_l(S)         金属层 l 的最大 IR Drop
I_peak(S)       峰值动态电流
N_viol(S)       违反电压阈值的节点数
```

### 1.2 覆盖率的本质

```
Coverage(S_sub) = "S_sub 的仿真结果在多大程度上逼近 S_full 的仿真结果"

理想覆盖：Φ(S_sub) ≈ Φ(S_full)  在所有关键指标上
```

**前提假设**：Φ(S_full) 是 Ground Truth。

---

## 二、三级覆盖率指标伪代码

### 第一级：全局指标（已实现，基于 Voltus 文本报告）

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
算法 1: Tier-1 全局覆盖率计算
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

输入:
    R_full  ← 全集 Voltus 报告 {main.rpt, layerbased_ir.rpt, dynpwr.rpt}
    R_sub   ← 子集 Voltus 报告（同结构）

输出:
    CoverageResult {C₁, C_peak, C_layer[], C_layer_avg, C_layer_min, C_violation}

────────────────────────────────────────────────────────

FUNCTION ComputeTier1(R_full, R_sub):

    // ── 指标 1: 全局最坏 IR Drop 捕获率 ──
    //
    //         V_nom − V_min(sub)     ΔV(sub)
    //  C₁ = ─────────────────── = ──────────
    //         V_nom − V_min(full)    ΔV(full)
    //

    ΔV_full ← R_full.vnom − R_full.vmin
    ΔV_sub  ← R_full.vnom − R_sub.vmin      // 注意: 使用 full 的 vnom

    IF ΔV_full > 0:
        C₁ ← ΔV_sub / ΔV_full
    ELSE:
        C₁ ← 1.0                             // 无 IR Drop 则视为完美覆盖

    // ── 指标 2: 峰值电流捕获率 ──
    //
    //  C_peak = I_peak(sub) / I_peak(full)
    //

    C_peak ← R_sub.ipeak / R_full.ipeak

    // ── 指标 3: 逐金属层 IR Drop 捕获率 ──
    //
    //  C_layer(l) = ΔV_l(sub) / ΔV_l(full),  l ∈ {M1, M2, ..., M7, LISD}
    //

    FOR EACH layer l IN R_full.layers:
        IF ΔV_l(full) > 0:
            C_layer[l] ← ΔV_l(sub) / ΔV_l(full)

    C_layer_avg ← MEAN(C_layer.values)
    C_layer_min ← MIN(C_layer.values)

    // ── 指标 4: 违规一致性 ──

    IF (N_viol(full) = 0 AND N_viol(sub) = 0) OR
       (N_viol(full) > 0 AND N_viol(sub) > 0):
        C_violation ← PASS
    ELSE:
        C_violation ← FAIL

    RETURN {C₁, C_peak, C_layer, C_layer_avg, C_layer_min, C_violation}
```

### 多窗口组合覆盖率

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
算法 2: 多窗口组合（包络取最坏值）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

输入:
    R_full         ← 全集报告
    {R_w1, ..., R_wk}  ← k 个窗口的报告

输出:
    CoverageResult（取包络后的覆盖率）

────────────────────────────────────────────────────────

FUNCTION ComputeCombination(R_full, windows[]):

    // 核心思想: 多窗口 "联合" = 各窗口中取最极端值
    //   - 电压:  取最低 V_min（对应最大 IR Drop）
    //   - 电流:  取最大 I_peak
    //   - 逐层:  取每层最大 IR Drop
    //   - 违规:  取并集（任一窗口检出即算检出）

    V_min_combined  ← MIN(w.vmin FOR w IN windows)
    I_peak_combined ← MAX(w.ipeak FOR w IN windows)

    FOR EACH layer l:
        ΔV_l_combined ← MAX(w.layers[l].ir_drop FOR w IN windows)

    // 用组合后的极端值计算 Tier-1 指标
    C₁     ← (V_nom − V_min_combined) / (V_nom − R_full.vmin)
    C_peak ← I_peak_combined / R_full.ipeak

    // 违规: 全集有 → 子集任一窗口有 → PASS
    IF N_viol(full) = 0 AND ALL(N_viol(w) = 0):
        C_violation ← PASS
    ELIF N_viol(full) > 0 AND ANY(N_viol(w) > 0):
        C_violation ← PASS
    ELSE:
        C_violation ← FAIL

    RETURN {C₁, C_peak, C_layer_avg, C_layer_min, C_violation}
```

### 第二级：空间分布指标（设计方案，尚未实现）

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
算法 3: Tier-2 Hotspot 覆盖率
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

输入:
    V_full[inst]  ← 全集仿真中每个 instance 的最坏电压
    V_sub[inst]   ← 子集仿真中每个 instance 的最坏电压
    θ             ← Hotspot IR Drop 阈值 (如 7% × V_nom)

输出:
    C₂ (Recall), Precision, F1

────────────────────────────────────────────────────────

FUNCTION ComputeHotspot(V_full, V_sub, θ):

    // 定义 hotspot 集合: IR Drop 超过阈值的 instance
    H_full ← {inst | V_nom − V_full[inst] > θ}
    H_sub  ← {inst | V_nom − V_sub[inst]  > θ}

    //          |H_sub ∩ H_full|
    //  C₂  = ─────────────────    (Recall: 全集 hotspot 被子集检出的比例)
    //            |H_full|

    C₂        ← |H_sub ∩ H_full| / |H_full|
    Precision ← |H_sub ∩ H_full| / |H_sub|
    F1        ← 2 · C₂ · Precision / (C₂ + Precision)

    RETURN {C₂, Precision, F1}
```

### 第三级：统计分布指标（设计方案，尚未实现）

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
算法 4: Tier-3 分位数捕获率
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

输入:
    ΔV_full[inst]  ← 全集中每个 instance 的 IR Drop
    ΔV_sub[inst]   ← 子集中每个 instance 的 IR Drop
    p              ← 分位数 (如 0.99, 0.999)

输出:
    C₃

────────────────────────────────────────────────────────

FUNCTION ComputePercentile(ΔV_full, ΔV_sub, p):

    //           Q_p(ΔV_sub)
    //  C₃  = ───────────────
    //           Q_p(ΔV_full)

    C₃ ← PERCENTILE(ΔV_sub, p) / PERCENTILE(ΔV_full, p)

    RETURN C₃
```

---

## 三、完整评估流程

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
算法 5: 完整覆盖率评估管线
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

输入:
    VCD_full          ← 完整仿真 VCD
    VCD_sub[1..k]     ← k 个选窗切片 VCD
    design_db         ← 物理设计数据库（DEF/SPEF/Netlist）

输出:
    CoverageReport    ← 三级覆盖率报告

────────────────────────────────────────────────────────

// Phase A: EDA 仿真（Voltus 执行，非脚本自动化）

FOR EACH vcd IN {VCD_full, VCD_sub[1..k]}:
    Φ(vcd) ← Voltus_DynamicIRDrop(vcd, design_db)
    //  → 生成 main.rpt, layerbased_ir.rpt, dynpwr.rpt
    //  → (可选) 导出 instance-level 电压 CSV

// Phase B: Tier-1 覆盖率（自动，纯文本解析）

R_full ← ParseReports(Φ(VCD_full))

FOR EACH i IN 1..k:
    R_sub[i]   ← ParseReports(Φ(VCD_sub[i]))
    Tier1[i]   ← ComputeTier1(R_full, R_sub[i])              // 算法 1

FOR EACH combo IN MeaningfulCombinations({1..k}):
    TierCombo  ← ComputeCombination(R_full, combo)            // 算法 2

// Phase C: Tier-2/3（需 instance-level 数据）

IF instance_voltage_data_available:
    FOR EACH i IN 1..k:
        Tier2[i] ← ComputeHotspot(V_full, V_sub[i], θ)      // 算法 3
        Tier3[i] ← ComputePercentile(ΔV_full, ΔV_sub[i], p)  // 算法 4

// Phase D: 综合判定

FUNCTION Judge(tier1, tier2, tier3):
    PASS IF:
        tier1.C₁         ≥ 0.95   AND      // 最坏值偏差 < 5%
        tier1.C_layer_min ≥ 0.80   AND      // 每层覆盖不低于 80%
        tier1.C_violation = PASS   AND      // 违规一致
        tier2.C₂          ≥ 0.90   AND      // Hotspot 检出 ≥ 90%
        tier3.C₃          ≥ 0.90            // 统计分布偏差 < 10%
    MARGINAL IF:
        tier1.C₁ ≥ 0.90
    FAIL OTHERWISE
```

---

## 四、科学性审查

### 4.1 逻辑合理性评估

| 方面 | 评估 | 说明 |
|------|------|------|
| C₁ 定义 | **合理** | IR Drop 比值直接反映 sign-off 关键指标，物理意义清晰 |
| C_peak 定义 | **合理** | 峰值电流是 IR Drop 的直接驱动因素 |
| C_layer 定义 | **合理** | 不同金属层的 IR Drop 机制不同（上层 lateral, 下层 via），逐层检验有价值 |
| C_violation | **过于粗糙** | 仅判断有无违规，未区分违规数量和严重程度（见 4.2.1） |
| 多窗口包络 | **逻辑正确** | worst-case 取各窗口最极端值的定义合理 |
| Tier-2 Hotspot | **核心正确** | Recall/F1 是信息检索标准框架，适用于 hotspot 检出问题 |
| Tier-3 分位数 | **合理** | 比 max 更鲁棒，补偿 C₁ 的单点敏感问题 |

### 4.2 发现的问题与改进建议

#### 问题 1: C_violation 信息量不足

**现状**：仅做二值判定（PASS/FAIL），且当前设计全部 0 violation，该指标无区分力。

**问题**：
- 全集 0 违规 + 子集 0 违规 → PASS。但这只说明"都没违规"，不说明覆盖好。
- 如果全集有 100 个违规节点，子集检出了 1 个，也判为 PASS。

**建议改进**：

```
// 改进版: 违规覆盖率（当存在违规时）
IF N_viol(full) > 0:
    C_violation ← N_viol(sub) / N_viol(full)    // 改为比值
ELSE IF N_viol(sub) = 0:
    C_violation ← 1.0    // 全集无违规，子集也无 → 完美
ELSE:
    C_violation ← "FALSE_POSITIVE"  // 子集出现了全集没有的违规（假阳性）
```

#### 问题 2: C > 100% 的物理解释

**现象**：algo_win1 的 C_layer_avg = 103.5%，意味着子集 IR Drop > 全集。

**原因分析**：
- 全集仿真覆盖完整时间跨度，peak IR Drop 取全局最大值
- 子集窗口截取了最活跃的时段，Voltus 仿真的初始条件不同
- 子集窗口的退耦电容初始状态可能是"满充"（从 t=0 开始仿真），而在全集仿真中该时刻退耦电容可能已部分耗尽

**这是一个关键物理问题**：

```
全集仿真:  ───────[前段活动]───[目标窗口]───[后段活动]───
                                ↑
                    退耦电容已被前段活动部分耗尽
                    实际 IR Drop 更大

子集仿真:  [目标窗口从 t=0 开始]
                ↑
            退耦电容从满充开始
            前几个周期 IR Drop 被低估，后段才正常
```

**建议处理**：
1. **不要截断到 1.0**——C > 1.0 本身是重要信息
2. 报告中标注 C > 1.0 的物理原因
3. 如果条件允许，仿真时添加 **warm-up period**（在目标窗口前加入少量活跃周期）

#### 问题 3: 初始条件偏差（最根本的科学性问题）

**问题**：子集 VCD 切片仿真和全集仿真在同一时间段的结果**不完全相同**，因为：

```
Voltus 动态仿真的 IR Drop 依赖:
  1. 当前周期的瞬态电流    ← 由 VCD 激励决定 ✓ 子集和全集一致
  2. 退耦电容的剩余电荷    ← 由前序活动历史决定 ✗ 子集丢失了前序信息
  3. 电源网络的暂态响应    ← 取决于前序状态 ✗
```

**影响**：
- C₁ 可能**高估**覆盖率：子集从满充电容开始，前几个周期 IR Drop 偏低
- 也可能**低估**：如果窗口包含了 toggle 渐强的序列，全集中该窗口前已有持续活动导致电容已充分耗尽

**当前方案的缓解措施**（已内嵌于选窗算法）：
- `depletion_ratio = 0.7` 参数将窗口定位在活跃相位的 70% 位置，而非开头
- 窗口起始点前已有足够的活跃周期，Voltus 仿真前段可作为 warm-up

**建议改进**：
```
// 切片时在窗口前添加 warm-up 余量
FUNCTION SliceWithWarmup(VCD, t_start, t_end, warmup_cycles):
    t_warmup ← t_start − warmup_cycles × T_clk
    t_warmup ← MAX(t_warmup, 0)
    sliced_vcd ← VCD[t_warmup : t_end]
    RETURN sliced_vcd
    // Voltus 仿真时只关注 [t_start, t_end] 的结果，前段为 warm-up
```

#### 问题 4: 单一设计验证的统计置信度

**现状**：仅在 DES3（3DES 加密核）一个设计上验证。

**问题**：
- DES3 是组合逻辑为主的对称设计，toggle 分布相对均匀
- 无法保证方法在以下场景同样有效：
  - 高度非对称设计（CPU/GPU 的不同功能模块）
  - 大量时钟门控的设计（toggle 分布极度不均）
  - 多电压域设计

**建议**：
- 在论文中明确标注验证范围和适用条件
- 如有条件，增加 1-2 个不同类型的设计做交叉验证

#### 问题 5: 阈值选择缺乏灵敏度分析

**现状**：
- C₂ 的 hotspot 阈值 θ = 7% × V_nom 为固定值
- C₃ 的分位数 p = 99% 为固定值
- 判定阈值（C₁ ≥ 95%, C₂ ≥ 90%）无理论依据

**建议**：

```
// 灵敏度分析: 多阈值扫描
FUNCTION SensitivityAnalysis(V_full, V_sub):
    FOR θ IN {3%, 5%, 7%, 10%} × V_nom:
        C₂(θ) ← ComputeHotspot(V_full, V_sub, θ)
    FOR p IN {95%, 99%, 99.5%, 99.9%}:
        C₃(p) ← ComputePercentile(ΔV_full, ΔV_sub, p)
    PLOT C₂ vs θ  // 应呈单调递减（阈值越宽松，recall 越高）
    PLOT C₃ vs p  // 越接近 100%，C₃ 越接近 C₁
```

### 4.3 工程可行性评估

| 指标 | 数据获取难度 | 自动化程度 | 当前状态 |
|------|-------------|-----------|---------|
| **C₁** | 低（文本报告解析） | 全自动 | **已实现** ✅ |
| **C_peak** | 低 | 全自动 | **已实现** ✅ |
| **C_layer** | 低 | 全自动 | **已实现** ✅ |
| **C_violation** | 低 | 全自动 | **已实现** ✅ |
| **C₂ Hotspot** | **高**（需 Innovus Tcl 导出逐 instance 电压） | 半自动 | 待实现 |
| **C₃ 分位数** | **高**（同 C₂） | 半自动 | 待实现 |
| **灵敏度分析** | 依赖 C₂/C₃ | 自动 | 待实现 |

**工程瓶颈**：C₂/C₃ 需要从 Voltus 导出逐 instance 的电压数据，这需要：
1. 活跃的 Innovus/Voltus license
2. 加载完整 rail 分析数据库
3. 编写 Tcl 导出脚本
4. 对全集和每个子集分别执行

---

## 五、推荐的最终指标体系

综合以上分析，推荐以下分级评估方案：

```
                    PI 仿真覆盖率评估指标体系
 ═══════════════════════════════════════════════════

 ┌─────────────────────────────────────────────────┐
 │  Tier-1: 全局指标 (必须)                         │
 │                                                 │
 │  C₁ = ΔV(sub) / ΔV(full)     ← worst IR Drop   │
 │  C_peak = Ipeak(sub)/Ipeak(full) ← peak current │
 │  C_layer_min                  ← 最弱金属层       │
 │  C_viol = N_viol(sub)/N_viol(full)  ← 违规比值  │
 │                                                 │
 │  判据: C₁ ≥ 95%, C_layer_min ≥ 80%              │
 ├─────────────────────────────────────────────────┤
 │  Tier-2: 空间指标 (推荐)                         │
 │                                                 │
 │  C₂ = Hotspot Recall (F1)    ← 危险区域检出     │
 │  多阈值灵敏度: θ ∈ {5%, 7%, 10%} × V_nom       │
 │                                                 │
 │  判据: C₂ ≥ 90% (at θ = 7%)                    │
 ├─────────────────────────────────────────────────┤
 │  Tier-3: 统计指标 (增强)                         │
 │                                                 │
 │  C₃ = Q_99%(ΔV_sub) / Q_99%(ΔV_full)           │
 │  分布相似度: Wasserstein / KL 散度               │
 │                                                 │
 │  判据: C₃ ≥ 90%                                 │
 └─────────────────────────────────────────────────┘
```

### 判定矩阵

```
 ┌──────────────┬──────────┬──────────┬──────────┐
 │              │ C₁ ≥ 95% │ C₂ ≥ 90% │ C₃ ≥ 90% │
 ├──────────────┼──────────┼──────────┼──────────┤
 │ PASS         │    ✓     │    ✓     │    ✓     │
 │ CONDITIONAL  │    ✓     │   N/A    │   N/A    │
 │ MARGINAL     │  90-95%  │    -     │    -     │
 │ FAIL         │  < 90%   │    -     │    -     │
 └──────────────┴──────────┴──────────┴──────────┘

 CONDITIONAL: 仅 Tier-1 数据可用时的有条件通过
              需在报告中注明缺少空间覆盖率验证
```

---

## 六、开放疑问

### Q1: "全集仿真 = Ground Truth" 是否成立？

当前方案将全集 VCD 的仿真结果作为绝对参考。但：
- 全集 VCD 本身只是一组**特定测试向量**的仿真，不等于芯片在实际工作负载下的真实 worst-case
- 如果测试向量不够充分，全集的 worst-case 本身就可能偏乐观
- **影响**：C₁ = 100% 只能说明"子集和全集一样好"，不能说明"足够安全"

### Q2: 时间窗口的独立性假设

多窗口组合取包络值（max/min）隐含假设各窗口的仿真结果相互独立。但：
- 如果两个窗口在时间上相邻，它们的 IR Drop 可能存在**时间相关性**（退耦电容的持续耗尽效应跨越窗口边界）
- 对于非相邻窗口，独立性假设基本成立

### Q3: C_layer 的权重问题

当前 C_layer_avg 对所有金属层等权平均，但实际上：
- 底层金属（M1/M2）的 IR Drop 对标准单元性能影响最大
- 顶层金属（M6/M7）的 IR Drop 主要影响全局电源分配
- 是否应按物理重要性加权？

```
// 可选: 加权 C_layer
weights = {M1: 0.25, M2: 0.20, M3: 0.15, M4: 0.12, M5: 0.10, M6: 0.10, M7: 0.08}
C_layer_weighted = Σ(w_l × C_layer(l)) / Σ(w_l)
```

### Q4: 覆盖率 vs 压缩率的 trade-off 曲线

当前只回答"子集够不够好"，但工程上更关心的是：
- 不同压缩率（保留 10%, 20%, 50% 的 VCD）下覆盖率如何变化？
- 是否存在一个**拐点**：压缩到某个比例以下覆盖率急剧下降？

```
// 建议补充: 覆盖率-压缩率曲线
FOR ratio IN {5%, 10%, 20%, 30%, 50%, 80%, 100%}:
    windows ← SelectWindows(VCD, budget=ratio)
    coverage[ratio] ← EvaluateCoverage(windows)

PLOT coverage vs ratio  // 预期: 单调递增, 存在拐点
```

---

## 七、与现有代码的对应关系

| 伪代码 | 实现文件 | 状态 |
|--------|---------|------|
| 算法 1 ComputeTier1 | `coverage_tier1.py::compute_coverage()` | ✅ 已实现 |
| 算法 2 ComputeCombination | `coverage_tier1.py::compute_combination()` | ✅ 已实现 |
| 算法 3 ComputeHotspot | `irdrop_coverage_framework.md` 设计方案 | ❌ 待实现 |
| 算法 4 ComputePercentile | `coverage_calculation_plan.md` Phase 3 | ❌ 待实现 |
| 算法 5 完整管线 | 跨多工具链协作 | 部分完成 |
| 灵敏度分析 | — | ❌ 待实现 |
| 压缩率-覆盖率曲线 | — | ❌ 待实现 |

---

*文档版本: v1.0 | 日期: 2026-03-19*
