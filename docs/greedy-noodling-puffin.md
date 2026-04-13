# MAVIREC v2 升级计划：融合 Hu2025 论文的 VCD+DEF 多特征方案

## Context（背景）

当前 MAVIREC 算法（[algorithm_worst_window.md](Classify/docs/algorithm_worst_window.md)）已经能用 9.3% 仿真时长达到 100% Worst-Case IR Drop 覆盖率，核心机制是：
1. **时间维度**：Phase-Aware 退耦耗尽模型 ($\rho = 0.7$)
2. **空间维度**：单一标量 $\sigma = \max(g_k)/\text{total}$

这套方案在 DES3（加密核，toggle 分布均匀）上验证有效，但存在五个隐患：
- **空间特征过于单薄**：只用"最大组占比"，无法区分"前 3 个热点"和"全局均匀+1 个极端值"两种情况
- **缺少 di/dt 信息**：当前完全依赖累积 toggle 量，未刻画相邻周期间的剧变（Ldi/dt 噪声主因）
- **DEF 利用不充分**：[vcd_def_mapper.py](Classify/vcd_power_toolkit/code/vcd_def_mapper.py) 已提取 `cell_type` 与 `(x, y)`，但 cell 面积/驱动强度未参与权重
- **只算电流不算电阻**：根据欧姆定律 $V_{\text{drop}} = I \times R$，**高电阻区域的中等电流也可能产生大压降**。v1 完全等同 $V_{\text{drop}} \propto I$，忽略 PDN/路由电阻的空间不均匀性。例如：电源 strap 稀疏的角落区域、长走线驱动的远端 cell——即使 toggle 数中等，实际 IR drop 也可能超过中心高 toggle 区。**SPEF 文件**（[des3.spef](Classify/des_demo/db/des3.spef)，已就绪）正好提供 per-net 的 R 和 C，可以作为 PDN 电阻分布的代理
- **β 是人为输入而非算法产物**：v1 强制用户先指定 $\beta$（如 10×），再按比例切窗。这违反了"让物理结构自己决定窗口位置和长度"的初衷——理想算法应该是 phase 检测出来后，每个 phase 自然给出一个窗口，**总压缩率作为输出报告，而非输入约束**

参考 ACM TODAES 2025 Hu Jingchao 等人的论文（[paper_Hu2025_VCD_summary.md](Classify/docs/paper_Hu2025_VCD_summary.md)），其 CHT + ML profiling 方案给出了 4 个对本毕设可直接借用的工程经验：

| Hu2025 概念                                                          | 价值                                        |
| -------------------------------------------------------------------- | ------------------------------------------- |
| **VTW / TrB / Transition** 三层定义                                  | 把模糊的"窗口/周期"概念形式化               |
| **$T_{\text{top3}}$, $T_{\text{change}}$** 多特征 | 替代单一 $\sigma$，刻画空间分布形态 + di/dt（本计划只取这两项，舍弃论文中冗余的 $T_{\max}$ 与 $T_v$） |
| **20×20 Tile 物理分块**                                              | 比当前 8×8 grid 粒度更细，且与商用工具兼容  |
| **负载电容加权 $C_{\text{load}}$**                                   | 提供物理一致的电流密度估计                  |
| **Tile 级有效电阻 $R_i$**（论文表 2 特征）                          | 由商用工具或 SPEF 提供，使 $V = I \times R$ 在评分中有体现 |

本计划的目标是：**保留 MAVIREC 现有 Phase-Aware 时间模型（这是论文没有的、本毕设独有的贡献），把空间维度从"单一 $\sigma$"升级到 Hu2025 风格的"多特征向量 + 物理感知权重"，并形式化 VTW 概念。**

最终成果：
1. 升级版 [algorithm_worst_window.md](Classify/docs/algorithm_worst_window.md)（v2.0）
2. 一份对应代码修改地图（不在本计划阶段执行）

---

## 升级总览

```
v1 (现状)                       v2 (本计划)
─────────                       ──────────
单一 σ = max/total       →     精简特征 (σ_top3, δ)，仅 2 个超参 α_top3, α_δ
T_clk 周期为基本单元      →     形式化 VTW 概念，周期=VTW 的特例
8×8 grid 或 scope        →     自适应 Tile（按信号密度定 L_tile，详见 §A.4）
toggle 计数等权           →     C_load 加权（SPEF）/ cell_area 加权（DEF fallback）
g_k = Σ toggle (纯电流)   →     P_k = I_k × R_k (V_drop 风险，引入 SPEF 电阻)
仅 VCD + DEF 输入         →     VCD + DEF + SPEF 三级渐进输入
β 输入 → 按比例切窗       →     无 β，每 phase 自适应出窗，压缩率作为输出
Phase-Aware ρ=0.7        →     保留（论文没有，是本毕设贡献）
```

### 输入分级（Progressive Input Strategy）

| Level | 输入                | 信号权重 $w_s$           | tile 电阻 $R_k$ | 物理保真度  |
| ----- | ------------------- | ------------------------ | --------------- | ----------- |
| L0    | VCD only            | 1.0                      | 1.0             | 最低（v1）  |
| L1    | VCD + DEF           | $\text{Area}(\text{cell}_s)$ | 1.0          | 中          |
| **L2** | **VCD + DEF + SPEF** | $C_{\text{load},s}$    | $R_{\text{tile}, k}$ | **最高（v2 默认）** |

L2 是 v2 的目标配置；L0/L1 作为退化兼容。

---

## 修改方案

### Part A：算法文档升级（[algorithm_worst_window.md](Classify/docs/algorithm_worst_window.md)）

#### A.1 §3 符号定义新增条目

| 新符号              | 含义                                                                                |
| ------------------- | ----------------------------------------------------------------------------------- |
| $\text{VTW}_t$      | 第 $t$ 个 Vector Time Window，$\text{VTW}_t = \{\text{TrB}(t') : t' \in [t, t+L)\}$ |
| $\text{TrB}(t)$     | Transition Block，时刻 $t$ 所有信号翻转的集合                                       |
| $L$                 | VTW 长度（默认 $L = T_{\text{clk}}$，与现有周期对齐）                               |
| $T_{\text{top3},t}$ | VTW $t$ 内压降风险最大的 3 个 tile 之和（取代 v1 的 max 单点，对长尾分布抗噪）       |
| $T_{\Delta,t}$      | $\lvert c_t - c_{t-1}\rvert$，相邻 VTW 总 toggle 差（di/dt 绝对幅度）              |
| $w_s$               | 信号 $s$ 的物理权重 $= C_{\text{load},s}$ 或 $\text{Area}_{\text{cell}(s)}$         |
| $L_{\text{tile}}$   | Tile 边长（自适应，目标每 tile ~500 信号，详见 §A.4）                              |

#### A.2 §3 之后插入新章节"§3.5 概念形式化（参考 Hu2025）"

引入论文三层定义：
- **Transition**：$\text{tr}_n(t) = \text{state}$
- **Transition Block (TrB)**：$\text{TrB}(t) = \{\text{tr}_n(t), \forall n \in N\}$
- **Vector Time Window (VTW)**：$\text{VTW}(t) = \{\text{TrB}(t'), t' \in [t, t+L)\}$

并明确说明：在 MAVIREC v1 中"时钟周期"= VTW($L = T_{\text{clk}}$) 的特例。v2 解耦 VTW 长度和时钟周期，允许 sub-cycle 分析。

#### A.3 改写 §4.3（Stage 3：空间集中度）→ "§4.3 空间多特征 Fingerprint（电压降风险版）"

**v1 单一公式**（仅电流）：
$$\sigma_t = \frac{\max_k g_{t,k}}{c_t},\quad e_t = c_t (1 + \alpha \sigma_t)$$

**v2 关键改动**：把"电流集中度"升级为"**电压降风险集中度**"。引入 per-tile 电阻 $R_k$ 后，每个 tile 的危险度不是 $g_k$（电流代理），而是：

$$P_{t,k} = I_{t,k} \times R_k = \left(\sum_{s \in \text{tile } k} n_{s,t} \cdot C_{\text{load},s}\right) \times R_k$$

这里 $I_{t,k}$ 用 $\sum n_s C_s$ 近似（开关电流 $\propto C \cdot V_{dd} \cdot f \cdot \alpha$，省略常数项）。$P_{t,k}$ 物理意义为该 tile 的"局部 IR drop 风险"。

**v2 精简特征公式**（仅 2 个超参，避免 v1 → 多维向量后的过参数化）：

$$\boxed{e_t = P_t^{\text{total}} \cdot \left(1 + \alpha_{\text{top3}} \cdot \sigma_{\text{top3},t}\right) + \alpha_\delta \cdot \Delta_t}$$

其中所有量都基于 $P_{t,k}$（而非 v1 的 $g_{t,k}$）：
- $P_t^{\text{total}} = \sum_k P_{t,k}$（全局 V_drop 风险，幅度量）
- $\sigma_{\text{top3},t} = \sum_{k \in \text{top3}} P_{t,k} / P_t^{\text{total}} \in (0, 1]$（**风险**集中度。$k=1$ 即退化为 v1 的 σ；取 top-3 是对长尾分布抗噪。**舍弃单独的 σ**：$\sigma_{\text{top3}}$ 与 σ 的相关系数在 DES3 上 > 0.9，保留两者是冗余）
- $\Delta_t = |P_t^{\text{total}} - P_{t-1}^{\text{total}}|$（**di/dt 绝对幅度**，单位与 $P^{\text{total}}$ 一致，详见 §A.3.2）

**舍弃的特征及理由**：
| 舍弃项 | 理由 |
|---|---|
| $\sigma_t = \max P/P^{\text{total}}$ | 与 $\sigma_{\text{top3}}$ 信息冗余（top-3 含 max） |
| $\text{CV}_t$ | "全局变异系数"与 $\sigma_{\text{top3}}$ 描述同一件事（分布形状），且 CV 对空 tile 极敏感 |
| 相对 $\delta$ | 见 §A.3.2，被绝对量 $\Delta$ 取代 |

**为什么这样能捕获"高 R 中 I"场景**：
假设两个 tile：
- Tile A：$I_A = 100$（高），$R_A = 1$（低，PDN strap 密集）→ $P_A = 100$
- Tile B：$I_B = 40$（中），$R_B = 4$（高，远离 strap）→ $P_B = 160$

v1 看 $g$ 会判定 A 危险（max=100），v2 看 $P$ 正确判定 B 危险（max=160）。这正是用户提到的物理场景。

**默认权重**：$\alpha_{\text{top3}} = 1.0$, $\alpha_\delta = 0.5$（数值依据见 §A.3.2 末尾的量纲分析；总放大上限 ≈ 2× $P^{\text{total}}$，与 v1 的 $1+\alpha\sigma \le 2$ 同量级，确保 v2 在 DES3 上至少与 v1 持平）

#### A.3.2 di/dt 项 $\Delta_t$ 的物理建模与定义

v2 评分公式中的第二项 $\alpha_\delta \cdot \Delta_t$ 用来捕获 **Ldi/dt 噪声**——电源网络的寄生电感 $L_{\text{pkg}} + L_{\text{grid}}$ 在电流剧变瞬间产生的电压扰动 $V_L = L \cdot di/dt$。该项与 IR 压降（$V_R = IR$）在物理上**正交**：前者由瞬时变化率决定，后者由稳态电流决定。v1 完全忽略了这一维度。

**为什么必须用绝对量而非相对量**：

最初草案使用相对变化率 $\delta_t = |P_t - P_{t-1}| / \max(P_t, P_{t-1})$。这个定义在物理上是错的：

| 场景 | $P_t$ | $P_{t-1}$ | 相对 $\delta$ | 绝对 $\Delta$ | 实际 $L\,di/dt$ 危险 |
|---|---|---|---|---|---|
| 微弱抖动 | 100 | 50 | 0.5 | 50 | 可忽略 |
| 大负载切换 | 10000 | 5000 | 0.5 | 5000 | 严重 |

相对 $\delta$ 把两种相差 100× 的危险等同处理。物理上 $V_L \propto \Delta I / \Delta t$，**正比于绝对变化量**，所以必须采用：

$$\Delta_t = |P_t^{\text{total}} - P_{t-1}^{\text{total}}|$$

**为什么作为加法项而非乘法项**：

v1 的 σ 与 v2 的 $\sigma_{\text{top3}}$ 都是 0~1 的**无量纲集中度**，写成 $(1+\alpha\sigma)$ 的乘法形式合理。但 $\Delta_t$ 是与 $P^{\text{total}}$ 同量纲的**幅度量**，若塞进乘法括号会破坏量纲一致性。改写为加法：

$$e_t = \underbrace{P_t^{\text{total}} (1 + \alpha_{\text{top3}} \sigma_{\text{top3},t})}_{\text{IR drop 风险（稳态电流）}} + \underbrace{\alpha_\delta \cdot \Delta_t}_{\text{Ldi/dt 风险（瞬态）}}$$

两项物理意义清晰可分：第一项对应 $V_R = IR$，第二项对应 $V_L = L\, di/dt$，毕设论文里可作为"显式分解电源噪声两大来源"的一节。

**$\alpha_\delta$ 的量纲与默认值**：

由于 $\Delta_t$ 与 $P_t^{\text{total}}$ 同量纲，$\alpha_\delta$ 是无量纲系数，反映"瞬态项相对稳态项的相对重要度"。

考虑边界情形：若每个周期 $P_t^{\text{total}}$ 完全独立波动（最坏 di/dt），则 $\Delta_t \approx P_t^{\text{total}}$；此时 $e_t \approx P^{\text{total}}(1 + \alpha_{\text{top3}} \sigma_{\text{top3}} + \alpha_\delta)$。为保持总放大与 v1 同量级（$1+\alpha\sigma \le 2$），令 $\alpha_{\text{top3}} + \alpha_\delta \approx 1.5$，取：

$$\alpha_{\text{top3}} = 1.0,\quad \alpha_\delta = 0.5$$

**边界处理**：$t = 0$ 时定义 $\Delta_0 = 0$；跨 phase 边界（中间夹静默周期）时，$\Delta$ 仍按相邻 VTW 计算，因为 phase 间的"冷启动尖峰"恰恰是 Ldi/dt 噪声最严重的场景，**不应**被屏蔽。

**与 phase detection 的关系**：$\Delta_t$ 仅参与 Stage 3 的 fingerprint 评分，不影响 Stage 2 的 phase 切分（与 §A.6 一致：phase 切分仍用原始 $c_i$）。

#### A.3.1 SPEF → tile 电阻 $R_k$ 的计算

SPEF 文件给出的是**信号网**的 RC，并非 PDN 电源网的电阻。但可以用三种代理策略，按精度递减排序：

| 策略 | 数据来源 | $R_k$ 定义 | 物理直觉 |
|---|---|---|---|
| **S1** | SPEF `*RES` 段（每条 net 的 lumped R） | $R_k = \text{mean}(R_{\text{net}})_{s \in k}$ | 信号布线密集 → 同区电源走线稀疏 → PDN R 高 |
| **S2** | SPEF `*CAP` 总电容密度 | $R_k \propto 1 / \text{cap\_density}_k$ | 间接但实现简单 |
| **S3** | DEF METAL 层 wirelength 密度 | $R_k \propto \text{wire\_density}_k$ | 不需要 SPEF |

**默认采用 S1**。归一化到无量纲：

$$\hat{R}_k = R_k / \text{median}(R_k)$$

最终 $\hat{R}_k$ 范围典型为 $[0.3, 3.0]$，clip 到 $[0.5, 2.5]$ 防止极端值主导。

> **诚实声明**：信号网 R 不是 PDN R，本质是统计相关而非物理等价。本毕设可在论文中这样表述：*"我们以信号网 RC 密度作为 PDN 电阻的代理，因为商业 P&R 工具的布线拥塞与电源网走线密度呈强负相关"*。要做到完全精确，需要 Voltus 的 PDN extraction，但那需要额外一次 Voltus run，与"加速 vector profiling"的初衷相悖。SPEF 代理方案是**精度/复杂度的合理折衷**。

新增子节 §4.3.4 给出案例对比：
- 单一 hot tile vs Top-3 hot tile 的两种危险场景（用论文场景 A、B 数据）- 一个 toggle 总量低但 $\delta_t$ 极大的"突发负载"周期，演示 $\delta_t$ 项如何捕获

#### A.4 改写 §4.3.1 空间分组模式（自适应 Tile 尺寸）

| v1 模式                                | v2 模式                                                                      |
| -------------------------------------- | ---------------------------------------------------------------------------- |
| Grid: $N \times N$ 均匀网格 (默认 8×8) | **Adaptive Tile**: 按信号密度自动选边长 $L_{\text{tile}}$（详见下文）        |
| Scope: VCD 层次分组                    | 保留作为 L0 fallback                                                          |
| —                                      | **RC-Weighted Tile**: 每信号 $w_s$ 加权 + 每 tile $R_k$ 加权（L2 默认）       |

**为什么不直接照搬 Hu2025 的 20×20**：

Hu2025 在工业级 SoC（百万信号量级）上验证 20×20=400 tile。DES3 仅 42K 信号，若硬套 20×20 平均每 tile ~100 信号，加上 DEF 映射不均匀，会出现大量空 tile，使 $\sigma_{\text{top3}}$ 退化为常数（因为非空 tile 总数 ≈ 3）。需要按设计规模自适应。

**自适应规则**：

设设计中已映射到坐标的信号总数为 $N_{\text{sig}}^{\text{mapped}}$，目标每 tile 平均信号数为 $N_{\text{tile}}^{\text{target}}$（默认 500，经验值：足以让 $\sigma_{\text{top3}}$ 有区分度，又不至于淹没局部热点）。则边长：

$$N_{\text{grid}} = \max\left(4,\; \min\left(20,\; \left\lceil \sqrt{N_{\text{sig}}^{\text{mapped}} / N_{\text{tile}}^{\text{target}}}\,\right\rceil\right)\right)$$

$$L_{\text{tile}} = \max(x_{\text{span}}, y_{\text{span}}) / N_{\text{grid}}$$

**clip 到 $[4, 20]$ 的理由**：
- 下限 4：低于 4×4=16 tile 时 top-3 占比天然 ≥ 18%，特征失去意义
- 上限 20：与 Hu2025 对齐，超过 20 时单 tile 过细，且 SPEF 聚合代价上升

**典型规模查表**：

| 设计规模 ($N_{\text{sig}}^{\text{mapped}}$) | $N_{\text{grid}}$ | tile 数 | 平均/tile |
|---|---|---|---|
| 5K (小测试用例)        | 4    | 16   | ~313 |
| 42K (DES3, 本毕设)    | **10** | **100** | **~420** |
| 200K (中型 SoC)       | 20   | 400  | ~500 |
| 1M+ (大型工业 SoC)    | 20 (上限) | 400 | ~2500 |

DES3 实际取 $N_{\text{grid}} = 10$，对应 100 个 tile，比 v1 的 8×8=64 略细，且符合 Hu2025 "tile 数 100~400" 的精神。

**空 tile 处理**：
- 计算 $\sigma_{\text{top3}}$ 时，分母为非空 tile 的 $P^{\text{total}}$，分子的 top-3 也只在非空 tile 中取
- 若非空 tile 数 < 3，退化为 $\sigma_{\text{top3}} = 1$（全在前 3 个里），评分公式仍可用

**信号权重 $w_s$**（按输入分级）：
- L2 (SPEF 可用)：$w_s = C_{\text{load},s}$，从 SPEF `*D_NET` 段读取 lumped 电容
- L1 (仅 DEF)：$w_s = \text{Area}(\text{cell\_type}(s))$，cell_type 已被 [vcd_def_mapper.py](Classify/vcd_power_toolkit/code/vcd_def_mapper.py) 提取，只需新增 cell_type→area LUT
- L0 (仅 VCD)：$w_s = 1$

**Tile 电阻 $R_k$**（详见 §A.3.1）：从 SPEF 提取信号网 R 密度并归一化。

#### A.5 §4.3 新增 Algorithm 3' "RCWeightedSpatialFingerprint"

```
Input:
  - per-VTW 信号→toggle map {(s, n_s,t)}
  - tile 映射 φ:s→tile（tile 数 = N_grid² 由 §A.4 自适应规则确定）
  - 信号权重 w_s (来自 SPEF C_load 或 DEF cell_area)
  - tile 电阻 R_hat[k] (来自 SPEF *RES 密度，已归一化)
  - 超参 α_top3, α_δ
Output: 精简 fingerprint (e_t, σ_top3, Δ) per VTW

1. P_total_prev ← 0
2. for each VTW t:
3.    I[k] ← 0 for all tile k                  // 电流代理
4.    for each signal s with toggle bits b_s,t:
5.        I[φ(s)] += popcount(b_s,t) × w_s
6.    P[k] ← I[k] × R_hat[k]                   // V_drop 风险 = I × R
7.    nonempty ← {k : P[k] > 0}
8.    P_total ← Σ_{k ∈ nonempty} P[k]
9.    if |nonempty| ≥ 3:
10.       sorted ← sort P[nonempty] descending
11.       σ_top3,t ← (sorted[0] + sorted[1] + sorted[2]) / P_total
12.   else:
13.       σ_top3,t ← 1.0                       // 退化保护
14.   Δ_t ← |P_total - P_total_prev|           // 绝对量，di/dt 代理
15.   e_t ← P_total × (1 + α_top3 · σ_top3,t) + α_δ · Δ_t
16.   P_total_prev ← P_total
17. return {(t, e_t, σ_top3, Δ)}
```

**关键点**：
1. 用 $P_{t,k} = I_{t,k} \times R_k$ 替代 v1 的 $g_{t,k}$，所有下游统计量自动具备 V_drop 物理意义
2. 超参从 v1 草案的 4 个（$\alpha_{1\sim 4}$）精简到 2 个（$\alpha_{\text{top3}}$, $\alpha_\delta$），降低过拟合风险
3. di/dt 项采用绝对量 $\Delta$ 而非相对量，物理上对应 $V_L = L \cdot di/dt$（详见 §A.3.2）

#### A.6 §5 参数表更新

**移除参数**：
- ❌ $\beta$ —— 不再作为输入；总压缩率改为算法**输出**（在结果报告中给出 $\beta_{\text{out}} = \sum_j |W_j| / T_{\text{sim}}$）

**新增参数**：

| 新参数                    | 默认             | 依据                                             |
| ------------------------- | ---------------- | ------------------------------------------------ |
| $L$ (VTW 长度)            | $T_{\text{clk}}$ | 与 v1 兼容；可选 $T_{\text{clk}}/4$ 做 sub-cycle |
| $N_{\text{tile}}^{\text{target}}$ | 500     | 自适应 tile 目标信号数/tile（详见 §A.4）          |
| $N_{\text{grid}}$         | **自适应**       | 由 $\sqrt{N_{\text{sig}}/N_{\text{tile}}^{\text{target}}}$ clip 到 $[4, 20]$；DES3 上为 10 |
| $\alpha_{\text{top3}}$    | 1.0              | Top-3 风险集中度乘法系数；与 v1 的 $\alpha=1$ 同量级，保证降级兼容 |
| $\alpha_\delta$           | 0.5              | di/dt 加法系数；量纲分析见 §A.3.2                 |
| $\eta$ (窗口半宽比)       | 0.15             | 窗口 = $[\rho - \eta,\,\rho + \eta] \cdot D$，相对 phase 长度的半宽 |
| $K_{\min}$                | 2                | 最小窗口周期数（防止极短 phase 退化为 0 周期）   |

#### A.6.1 改写 §4.4 Stage 4：无预算 Phase-Driven 窗口生成

**v1 做法（被替换）**：先输入 $\beta \cdot T_{\text{sim}}$ 总预算 → 按 phase 长度比例瓜分 → 每 phase 分到固定长度窗口。

**v2 做法**：每个 phase **独立**产生一个窗口，长度由 phase 自身的持续时间 $D_j$ 决定（**完全由物理结构驱动，无人为预算**）：

$$W_j.\text{start} = t_s^{(j)} + (\rho - \eta) \cdot D_j \cdot T_{\text{clk}}$$
$$W_j.\text{end}\;\;\, = t_s^{(j)} + (\rho + \eta) \cdot D_j \cdot T_{\text{clk}}$$

对齐到时钟周期边界，并保证至少 $K_{\min}$ 个周期：

$$n_j = \max\left(K_{\min},\; \lceil 2\eta \cdot D_j \rceil\right)$$

**关键性质**：
- **窗口长度自适应 phase 规模**：长 phase 给宽窗口（捕获更长退耦累积区间），短 phase 给窄窗口（避免浪费）
- **总压缩率自然产生**：$\beta_{\text{out}} = \sum_j n_j \cdot T_{\text{clk}} / T_{\text{sim}}$ 作为算法**输出报告**而非输入约束
- **算法只回答"哪些时刻最危险"**，不被迫在某个预算内做妥协
- **可选硬上限（post-processing）**：若运行环境对窗口数量有硬约束，可在输出端按 $e_t$ 排序保留 Top-N，但这是 post-processing，不污染算法本体

**新增 Algorithm 4'：PhaseDrivenWindowGeneration**

```
Input: phases {P_j}, ρ, η, K_min, T_clk
Output: 窗口列表 {W_j}, 实际压缩率 β_out

1. for each phase P_j with [t_s, t_e], D_j = (t_e - t_s) / T_clk:
2.    n_j ← max(K_min, ceil(2η · D_j))
3.    t_center ← t_s + ρ · D_j · T_clk
4.    W_j.start ← align_to_clock(t_center - n_j · T_clk / 2)
5.    W_j.end   ← W_j.start + n_j · T_clk
6.    Clip W_j to [t_s - T_clk, t_e + T_clk] ∩ [0, T_sim]
7. β_out ← Σ_j |W_j| / T_sim          // 报告值
8. return {W_j}, β_out
```

#### A.6.2 案例演示更新（替换 §4.4.2）

延续两个 phase（$D_1 = 7$, $D_2 = 6$, $T_{\text{clk}} = 50$ ns，$T_{\text{sim}} = 1000$ ns，$\eta = 0.15$）：

|                   | Phase 1                                          | Phase 2                                       |
| ----------------- | ------------------------------------------------ | --------------------------------------------- |
| $D_j$             | 7 cycles                                         | 6 cycles                                      |
| $\lceil 2\eta D_j \rceil$ | $\lceil 2.1 \rceil = 3$                  | $\lceil 1.8 \rceil = 2$                       |
| $n_j$             | $\max(2, 3) = 3$                                 | $\max(2, 2) = 2$                              |
| $t_{\text{center}}$ | $150 + 0.7 \cdot 7 \cdot 50 = 395$ ns          | $600 + 0.7 \cdot 6 \cdot 50 = 810$ ns        |
| 窗口（对齐前）    | $[395 - 75,\, 395 + 75] = [320,\, 470]$           | $[810 - 50,\, 810 + 50] = [760,\, 860]$      |
| 窗口（对齐后）    | $[300,\, 450]$                                    | $[750,\, 850]$                               |
| 长度              | 150 ns (3 cycles)                                | 100 ns (2 cycles)                             |

**算法输出报告**：
- $W_1 = [300,\, 450]$ ns
- $W_2 = [750,\, 850]$ ns
- $\beta_{\text{out}} = (150 + 100) / 1000 = \mathbf{25\%}$

对比 v1 强制 $\beta = 20\%$（200 ns）：v2 自适应到 250 ns，多覆盖 1 个高活跃周期；如果某仿真只有 1 个非常短的 phase，v2 也可能输出 $\beta_{\text{out}} = 2\%$，避免无意义浪费。

#### A.7 §6.6 之后新增 §6.7 "v2 升级的预期收益"

提出 4 个验证假设（待后续实验填表）：
1. **场景 B 改进**：对 toggle 长尾分布的设计（如带 DMA 的 SoC），$\sigma_{\text{top3}}$ 比 v1 的 $\sigma$ 更稳定
2. **Ldi/dt 命中**：$\Delta_t$ 项（绝对量）能否捕获 v1 漏掉的瞬态电流剧变窗口；预期表现为"$P^{\text{total}}$ 不算最高但 $\Delta$ 极大"的窗口被抬升
3. **自适应 Tile 粒度**：DES3 上 $N_{\text{grid}} = 10$ vs v1 的 8 是否提升空间分辨率；空 tile 比例应 < 30%
4. **权重物理意义**：$C_{\text{load}}$ / cell_area 加权是否使 worst-case window 更接近 Voltus 的真实热点

#### A.8 §8 算法实现表新增 4 行

| 文件                       | 功能                                                                            |
| -------------------------- | ------------------------------------------------------------------------------- |
| `spef_parser.py`           | 轻量 SPEF parser：提取 NAME_MAP / D_NET (C_load) / `*RES` (lumped R) (新增)    |
| `cell_area_lut.py`         | ASAP7 .lib → cell_type→area_µm² 字典 (L1 fallback, 新增)                       |
| `multi_feature_spatial.py` | Algorithm 3' 实现：$P_k = I_k \times R_k$ + $\sigma_{\text{top3}}$ + $\Delta$ 单遍计算 (新增) |

---

### Part B：代码修改地图（仅说明，不在本计划执行）

| 文件                                                                                                                | 修改类型 | 修改要点                                                                                  |
| ------------------------------------------------------------------------------------------------------------------- | -------- | ----------------------------------------------------------------------------------------- |
| 新文件 `spef_parser.py`                                                                                             | 新建     | 流式扫 SPEF：NAME_MAP（编号→net 名）/ `*D_NET <id> <C>` / `*RES` 段；输出 `{net: (C, R)}` |
| [vcd_def_mapper.py](Classify/vcd_power_toolkit/code/vcd_def_mapper.py)                                              | 增量     | CSV 新增 `cell_area`、`c_load`、`r_net` 三列；调用 spef_parser 与 cell_area_lut         |
| [spatial_temporal_select.py](Classify/vcd_power_toolkit/code/spatial_temporal_select.py) `build_spatial_grid()`     | 替换     | 固定 8×8 → 自适应 $N_{\text{grid}}$（§A.4）；累加时改为 $I_k = \sum n_s w_s$；新增 $R_k$ 聚合 |
| [spatial_temporal_select.py](Classify/vcd_power_toolkit/code/spatial_temporal_select.py) `build_toggle_matrix()` 后 | 新增     | 增加 $P_k = I_k \times R_k$ 矩阵；计算 $\sigma_{\text{top3}}$ 与 $\Delta$ 两项特征          |
| [find_worst_window.py](Classify/vcd_power_toolkit/code/find_worst_window.py) `load_toggles_with_spatial()`          | 替换公式 | $e_t = c_t(1+\alpha\sigma)$ → $e_t = P_t(1+\alpha_{\text{top3}}\sigma_{\text{top3}}) + \alpha_\delta \Delta_t$ |
| [find_worst_window.py](Classify/vcd_power_toolkit/code/find_worst_window.py) `select_windows()` 调用处              | 替换     | 删除 `--budget`/`--beta` 参数，改为输出 $\beta_{\text{out}}$                              |
| 新文件 `cell_area_lut.py`                                                                                           | 新建     | 解析 ASAP7 .lib，输出 JSON LUT (L1 fallback)                                              |
| 新文件 `multi_feature_spatial.py`                                                                                   | 新建     | Algorithm 3' 的纯函数实现，便于单元测试                                                   |

**关键复用**：
- JSONL 格式 (`{"time": t, "signals": {s: bits}}`) **已经保存了 per-signal toggle 位串**，足以支持 Top-3 / CV / 加权聚合，**无需重新生成 toggle 数据**
- DEF parser 已提取 `cell_type` 字符串，添加 area 字段只需一次 LUT 查表
- SPEF 文件 [des3.spef](Classify/des_demo/db/des3.spef) (1.4M 行, 54063 nets) 已就绪，无需额外 EDA 跑流程
- Phase Detection (Stage 2) **完全不动**，因为 H/M/L 阈值是针对原始 toggle 标定的，加权后会失效（v1 的设计决策保持不变）

---

### Part C：未涉及的改动（明确说"不做"）

为避免 over-engineering，本计划**不**包含：
- ❌ 引入 XGBoost 等 ML 模型（论文方案，但与本毕设"轻量启发式"定位冲突）
- ❌ 实现 Huffman 压缩（与 worst-case window 选取无关）
- ❌ 构建完整 CHT 数据结构（当前 dict-based 信号→tile 映射已够用，建树是 over-design）
- ❌ 调整 Phase-Aware ρ=0.7（这是本毕设核心贡献，论文无对应概念）

---

## 验证计划

1. **文档自洽性**：v2 文档完成后，重跑 §6 实验表的"案例演示"段，确保新公式在原 DES3 数据上仍给出与 v1 一致或更优的结果（$C_1 = 100\%$）
2. **代码层验证**（后续阶段）：
   - 在 grj-dev 容器内执行 `docker exec grj-dev python /app/Classify/vcd_power_toolkit/code/find_worst_window.py --jsonl ... --def ... --version v2`
   - 对比 v1 vs v2 的 win1/win2 范围与 $C_1$ / $C_{\text{layer,min}}$
3. **场景压力测试**：构造一个"长尾 toggle 分布"的合成 testbench（如 DES3 + DMA burst 模拟），验证 $\sigma_{\text{top3}}$ 与 $T_{\Delta}$ 是否捕获 v1 漏掉的窗口

---

## 与论文的对齐与差异（毕设论述要点）

| 维度     | Hu2025                                       | MAVIREC v2                                                | 差异理由              |
| -------- | -------------------------------------------- | --------------------------------------------------------- | --------------------- |
| 时间维度 | 等长 VTW + ML 排序                           | Phase-Aware + ρ=0.7 退耦模型                              | 物理可解释 vs ML 黑盒 |
| 空间维度 | 20×20 tile + 9 维特征 + XGBoost              | 20×20 tile + 4 维特征加权和                               | 轻量启发式            |
| 物理感知 | 完整 CHT + SPEF/GDSII + 商用工具 $R_{\text{eff}}$ | SPEF $C_{\text{load}}$ + SPEF 信号网 R 密度作为 PDN R 代理   | 不依赖额外 Voltus run |
| $V = IR$ 建模 | 商用 R + ML 隐式拟合                    | 显式 $P_k = I_k \times R_k$                              | 物理透明              |
| 目标     | 加速签核 (3.53×)                             | 替代签核前 vector 选取                                    | 流程定位不同          |

毕设论文中可强调："本工作以 Hu2025 的多特征空间表征为启发，但在时间维度引入了基于退耦电容耗尽物理模型的 Phase-Aware 选取，以**纯启发式方法**达到与论文 ML 方案可比的覆盖率，避免了模型训练数据与跨工艺迁移的成本。"
