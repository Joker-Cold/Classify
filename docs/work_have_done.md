# 毕业设计工作总结

## 1. 课题目标与任务

### 1.1 研究背景

随着半导体工艺技术的不断进步，集成电路（IC）的规模和复杂度急剧增加，从传统的2D平面设计向2.5D/3D堆叠结构演进，同时工作频率已达GHz级别。这导致电源分配网络（Power Delivery Network, PDN）在供电稳定性方面面临巨大挑战。电源完整性（Power Integrity, PI）问题已成为制约IC设计可靠性的关键瓶颈，包括IR Drop、同步开关噪声（SSN）和电磁干扰等[3]。

在工业实践中，PI仿真已成为签核（sign-off）验证的核心环节，但传统方法依赖海量测试矢量，计算资源消耗巨大，并且覆盖率难以量化，亟需优化以提升验证效率。

### 1.2 课题目标

本课题的目标是开发一种PI仿真覆盖率优化方法，在保持最坏噪声场景准确捕获能力的前提下，显著减少所需仿真矢量数量。

核心研究问题为：在不影响功耗验证覆盖率有效性的前提下，提出 VCD 激励向量规模压缩的优化算法。

### 1.3 具体任务

1. 调研并了解电源完整性分析（PI）的研究目标和基本方法，包括传统PI仿真在不同规模下的电源分配网络的仿真数量和时间消耗。
2. 调研并选择一种量化标准，用以科学评估PI仿真的覆盖率，该标准需满足统计学上的科学性和工业工程中的可靠性与适用性。
3. 建立一种优化方法，能够智能筛选出最能代表最坏噪声场景的关键测试矢量集，针对传统PI仿真测试矢量过多、计算量巨大的问题进行改进。
4. 使用Cadence Voltus对所提出的优化方法进行验证，评估覆盖率精度、矢量数量减少比例及仿真时间节省等指标，并在不同规模的电源分配网络上开展对比实验。
5. 完成毕业论文的总结工作和撰写（不少于11000字）。

### 1.4 复杂工程问题

本课题需解决的相关复杂工程问题主要为电源完整性仿真中测试矢量覆盖率量化与优化的工业问题。具体拆解如下：

1. **量化覆盖率的标准缺失**：传统PI仿真缺乏统一的统计指标，无法客观评估测试矢量是否全面覆盖噪声场景。需要提出一种满足统计学上的科学性与工程实践上的可靠性的覆盖率量化标准。
2. **关键测试矢量的筛选算法**：传统PI仿真计算量巨大，且存在大量冗余测试矢量。需要在海量矢量中高效智能识别能够激发最坏电源噪声的关键矢量集。

---

## 2. 实施方案与可行性研究

### 2.1 实施方案

本课题的实施方案从概率论与数理统计、集成电子电路网络与系统理论出发，采取数理推导、建立算法模型与仿真验证的技术路线。具体步骤如下：

1. **文献调研与基础方法建立**：调研PI分析的基本方法，包括静态IR Drop分析和动态噪声仿真。传统动态仿真使用大规模测试矢量模拟电路切换活动，以捕获同步开关噪声（SSN）和电源波动。
2. **覆盖率量化标准选择**：选择基于统计学的覆盖率指标，同时需要有物理意义，如热点比例（Hotspot Ratio）来检测PI验证后的结果是否覆盖最坏噪声情况[2]。
3. **优化方法构建**：建立智能筛选算法，从海量矢量中提取关键矢量集，并能够捕获最坏电源噪声场景。
4. **验证与迭代**：在不同规模PDN上进行传统与优化仿真对比，评估精度、矢量减少比例和时间节省。工具链包括Cadence Voltus用于PI仿真，Python用于数据处理和算法实现。

### 2.2 可行性研究

- **技术可行性**：采用成熟工具 Python 和 Cadence Voltus，类似算法框架（如当前矢量的时间压缩法[2]）已在学术论文中验证，易于复现和拓展。
- **实验条件可行性**：小规模PDN测试可在个人电脑上完成，中大规模实验可利用实验室资源补充。文献资源通过学校数据库和在线平台（如IEEE Xplore）可免费获取。
- **时间可行性**：课题分为调研、算法构建、验证和论文撰写四个阶段，总时长约6个月。算法设计和验证允许并行推进，缓冲时间充足。

---

## 3. 已完成工作

### 3.1 量化评估标准的建立

> 代码实现：`coverage_analysis/`

由于传统验证覆盖率（功能覆盖率、代码覆盖率）不适用于功耗热点场景，本课题建立了面向 IR Drop 的**双维度热点覆盖率（Hotspot Coverage）指标体系**，通过解析 Voltus 仿真输出的 `.iv`（instance voltage）文件自动计算：

**C_int（强度覆盖率）**：

$$C_{int} = \frac{V_{comp\_max}}{V_{orig\_max}} \times 100\%$$

衡量压缩 VCD 仿真是否保留了最坏 IR Drop 强度。C_int ≥ 100% 表示保守估计（安全），C_int < 95% 表示显著低估（危险）。

**C_k（位置覆盖率）**：

$$C_k = P_{top\text{-}k} = \frac{|S_{orig}^{(k)} \cap S_{comp}^{(k)}|}{k}$$

衡量压缩 VCD 仿真是否保留了 top-k 热点的空间位置。对 k ∈ {1, 3, 5, 10} 分别评估，采用严格全命中判定。

**判定准则**：C_int_min ≥ 95% 且 C_k(1) ≥ 90% 为 **PASS**；其中一个满足为 **MARGINAL**；两者均不满足为 **FAIL**。

**工具链**：`evaluate.py` 接收原始与压缩两组 `.iv` 文件，自动计算 C_int、C_k 并输出 JSON 报告；`extract_results.py` 结合 DEF 物理坐标生成逐 instance 的 IR Drop 对照表（`ir_drop_map.csv`）和 top-20 热点排名变化表；`visualize_hotspot.py` 生成交互式 Plotly 可视化面板（柱状图、排名散点图、空间分布图、数据表）。

### 3.2 传统向量分析——功耗矩阵生成

> 代码实现：`Traditional_Vector_Profiling/`

基于 Wen et al. ICCAD 2023 的功率模型，实现了从原始 VCD 到空间-时间功耗矩阵的完整生成流水线。

**功率模型**：对每个 instance 在每个时间窗口内计算三分量功耗：

$$P_{inst,t} = P_{sw} + P_{int} + P_{leak}$$

其中 $P_{sw} = \Sigma_{toggles} \times 0.5 \times C_{net} \times V_{DD}^2 / T_{win}$，$P_{int}$ 通过 Liberty LUT 查表插值获取，$P_{leak}$ 为静态漏电。按物理坐标将 instance 映射到 M×N tile 网格后汇总，输出功耗矩阵 `power_matrix_mW[T][ny][mx]`。

**数据流水线**：

```
VCD → vcd_to_jsonl.py → JSONL → jsonl_toggle_mark.py → Toggle JSONL
Liberty .lib → parse_lib_power.py → lib_power.json（cell功率LUT）
SPEF → parse_spef.py → net_cap.json（net电容）
DEF → traditional_select.py（instance坐标+cell类型）
                    ↓
    traditional_select.py → report.json [T][ny][mx] 功耗矩阵
```

在 DES3 设计上生成了 593×50×50 的功耗矩阵（593 个 20ns 窗口，50×50 tile 网格）。

### 3.3 热点传播风险评估

> 代码实现：`risk_propagation_profiling/`

将论文中的 Green 函数推广为**可插拔的热点传播核函数**，实现了基于空间传播模型的 IR-drop 风险评分算法。核心思想：某 tile 的 IR-drop 风险不仅取决于自身功耗，还受周围 tile 功耗经 PDN 传播的影响。

**风险评分公式**：

$$S_{r,t} = \frac{\sum_{r' \in R} P_{r',t} \cdot G(r, r')}{\sum_{r' \in R} G(r, r')}$$

分子为所有 tile 功耗以传播核为权重的加权和，分母为归一化因子（消除边界效应）。

**三种传播核函数**（$d = \sqrt{dx^2 + dy^2}$，$\alpha$ 为自影响因子）：

| 核函数 | $G(r, r')$ 当 $r \neq r'$ | 物理含义 |
|--------|---------------------------|----------|
| 欧氏距离（论文原始） | $1 / d$ | 自由空间 Green 函数，IR-drop 随距离线性衰减 |
| 指数衰减 | $\exp(-d)$ | 近场主导，远程影响迅速消失 |
| 对数衰减 | $1 / \ln(1+d)$ | 衰减较缓，远程 tile 仍有显著影响 |

当 $r = r'$ 时，$G = \alpha$（实验中 $\alpha = 5$），控制自身功耗对 IR-drop 的权重。

**实现优化**：由于网格规则，G 仅取决于偏移量 $(di, dj)$，预计算为 $[2N-1] \times [2M-1]$ 的相对核矩阵，所有窗口复用。归一化矩阵也仅计算一次。

**实验结果**：三种核函数对 DES3 的 593 个窗口产生了不同的风险排名（top-10 窗口交集为 0），其中指数核的最大风险分为 0.0004（最差窗口 422），欧氏核和对数核约为 0.0001（最差窗口 342/352），表明核函数的选择对热点定位有显著影响。

### 3.4 最差窗口选取与 VCD 裁剪

> 代码实现：`worst_k_windows/`

实现了通用的 top-k 最差窗口选取与 VCD 时间区间裁剪工具，作为独立模块可与任意上游评分算法对接。

**选取算法**：从风险评分向量 `worst_per_window[T]` 中取 top-k 最大值对应的窗口索引，转换为 VCD 时钟区间后进行区间合并（支持预热 warmup 扩展）。

**VCD 裁剪算法**（两遍扫描）：
1. 第一遍：流式扫描 VCD，在每个区间边界处快照信号状态（hold-last-value）
2. 第二遍：在每个区间入口写 `$dumpvars`（从快照恢复完整信号状态），然后写区间内的 value changes，时间戳连续重映射

**数据流**：

```
risk_propagation_profiling/sim_result/report/risk_<kernel>.json
        ↓  （worst_per_window + parameters）
worst_k_windows/code/select_worst_k.py
        ↓  --top-k 10  --vcd traditional.vcd
worst_k_windows/sim_result/report/worst_k_<kernel>.json  （top-k 索引+评分）
worst_k_windows/sim_result/vcd/worst_k_<kernel>.vcd      （压缩 VCD）
```

该模块可独立于 risk_propagation_profiling 使用——只要输入 JSON 包含 `worst_per_window` 数组和 `parameters.T`、`parameters.t_max_ticks` 即可。

### 3.5 VCD 信号到物理位置的映射

开发了 VCD 信号到 DEF 物理坐标的自动映射工具，通过解析 DEF 文件的 COMPONENTS/PINS/NETS 段，将 VCD scope 层次路径转换为 DEF instance 路径。在 DES3 设计上映射成功率达 **99.8%**（42,340/42,410 信号）。该映射为空间集中度评分和功耗矩阵的 tile 划分提供了坐标基础。

### 3.6 端到端工具链

完成了从原始 VCD 到覆盖率报告的完整自动化工具链，各模块通过 JSON 文件解耦、独立运行：

```
原始 VCD + DEF + SPEF + Liberty
        ↓
Traditional_Vector_Profiling → report.json [T][ny][mx] 功耗矩阵
        ↓
risk_propagation_profiling → risk_<kernel>.json [T][ny][mx] 风险矩阵
        ↓
worst_k_windows → worst_k_<kernel>.vcd 压缩 VCD
        ↓
Voltus 仿真（原始 vs 压缩）→ .iv 文件
        ↓
coverage_analysis → 覆盖率报告 (C_int, C_k) + 可视化
```

### 3.7 实验验证

**测试电路**：选择 DES3（组合逻辑密集、翻转活跃、流水线结构使不同时钟周期的功耗有明显差异，适合验证选窗算法）。

**实验结果**：算法选窗在仅 **9.3%** 的仿真时长内达到了与全集完全一致的 Tier-1 覆盖率，验证了 Phase-Aware + 空间集中度选窗方法的有效性。同时发现，等分方案中 5 个窗口的覆盖率差异显著（C₁ 从 84.6% 到 100%），其中 eq_win3 判定为 FAIL（C_layer_min = 79.9%），说明盲目选窗无法保证验证质量。

**热力图对比**（来自 Voltus 仿真输出，左侧为 IR Drop 线性分布图，右侧为最坏电压分布图）：
- (a) 全集 full — 基线参考
- (b) 算法选窗 algo_win (5.1%) — 实验组
- (c) 等分窗口 eq_win2 (20%) — 最优等分对照
- (d) 等分窗口 eq_win1 (20%) — 非最优对照

---

## 4. 知识技能学习情况

- **EDA 工具操作**：学习了 Cadence Innovus v20.10 的 Dynamic IR Drop 仿真流程，包括电源网格建模、Voltus 引擎配置、Rail Analysis 参数设置与报告解析，能独立完成从 VCD 加载到 IR Drop 报告生成的完整流程。
- **电源完整性理论**：深入理解了 PDN 的基本分析方法，包括退耦电容的充放电模型、IR Drop 的时空分布特性等。阅读了经典专著《Power Integrity Modeling and Design for Semiconductors and Systems》[4]。
- **编程与自动化**：使用 Python 开发了模块化的分析工具链（6 个独立模块），涉及 VCD 格式解析、DEF/SPEF/Liberty 物理设计文件解析、大规模信号处理、Plotly 数据可视化、Voltus 报告自动解析等。
- **算法设计**：设计并实现了多种选窗算法，包括 Phase-Aware 选窗、基于传统功率模型的功耗矩阵生成、基于可插拔核函数的热点传播风险评分、top-k 窗口选取与 VCD 裁剪等，涉及信号处理、空间卷积、二维核函数设计等算法概念。

---

## 5. 职业素养培养

- **工程规范意识**：严格遵循 sign-off 标准（IR Drop 阈值 7% × Vnom），所提出的覆盖率评估方法遵循保守原则。
- **科学严谨性**：系统分析了指标体系的科学性，包括 C > 100% 的物理解释（初始条件偏差）、单一设计验证的统计局限性等问题，并如实记录。
- **团队协作与资源管理**：在远程 EDA 服务器上进行仿真时，合理使用共享计算资源（8 核并行）。
- **知识产权意识**：测试电路 DES3 来源于开源社区（OpenCores），工艺 PDK 使用学术开放的 ASAP7，注意了知识产权的合规使用。

---

## 6. 存在问题与解决方案

### 6.1 存在的主要问题

1. **核函数选择缺乏理论指导**：三种传播核函数（欧氏/指数/对数）产生了差异显著的风险排名（top-10 交集为 0），目前缺乏选择最优核函数的理论依据，需要通过 Voltus 仿真闭环验证确定哪种核函数的覆盖率最优。
2. **压缩率-覆盖率 Trade-off 曲线数据不足**：仅有 5.1%、9.3%、20% 等有限数据点，尚未建立完整的关系曲线。
3. **单一设计验证的泛化性有限**：目前仅在 DES3 一个电路上完成验证，无法保证方法在高度非对称设计中同样有效。
4. **初始条件偏差的影响**：子集 VCD 切片从 t=0 重新仿真，退耦电容从满充状态开始，与全集仿真中同一时段的初始条件不同。

### 6.2 解决方案

1. **核函数闭环验证**：对三种核函数各自选出的 top-k 窗口分别生成压缩 VCD，送入 Voltus 仿真后用 coverage_analysis 模块评估 C_int 和 C_k，以仿真结果确定最优核函数。
2. **构建多点 Trade-off 曲线**：通过调整 top-k 和 alpha 参数，在 5%~50% 压缩率范围内生成更多数据点，绘制覆盖率 vs 压缩率曲线，分析拐点位置。
3. **增加验证设计规模**：在现有 DES3 基础上，增加 1~2 个不同类型的设计进行交叉验证，在论文中明确标注验证范围和适用条件。
4. **Warm-up 机制**：worst_k_windows 模块已支持 `--warmup-ticks` 参数，在 VCD 切片时于目标窗口前添加预热余量周期，使 Voltus 仿真前段作为退耦电容预热期。

---

## 7. 后续实施计划

| 时间 | 计划内容 |
|------|----------|
| 2026年1月-2月 | 完善优化算法模型，使用Python编写优化代码并实现智能筛选；利用Cadence Voltus进行仿真验证 |
| 2026年3月-4月 | 进行大规模实验对比，分析仿真数量与时间优化效果；从理论和实验层面论证覆盖率量化的科学性 |
| 2026年5月-6月 | 撰写毕业论文，总结成果；进行答辩准备 |

各阶段预留1-2周缓冲时间应对潜在的算法迭代或仿真收敛问题。

---

## 参考文献

[1] Xu, Jun, "System level power integrity transient analysis using a physics-based approach" (2018). Masters Theses. 7842.

[2] Xiao Dong, Yufei Chen, Jun Chen, Yucheng Wang, Ji Li, Tianming Ni, Zhiguo Shi, Xunzhao Yin, and Cheng Zhuo. 2023. Worst-case Power Integrity Prediction Using Convolutional Neural Network. ACM Trans. Des. Autom. Electron. Syst. 28, 4, Article 54 (July 2023), 19 pages.

[3] 张木水. 高速电路电源分配网络设计与电源完整性分析 [D]. 西安 : 西安电子科技大学, 2009

[4] SWAMINATHAN M, ENGIN A E, 2007. Power integrity modeling and design for semiconductors and systems[M]. Upper Saddle River: Prentice Hall.

[5] V. A. Chhabria, Y. Zhang, H. Ren, B. Keller, B. Khailany and S. S. Sapatnekar, "MAVIREC: ML-Aided Vectored IR-Drop Estimation and Classification," 2021 DATE, Grenoble, France, 2021, pp. 1825-1828.

[6] Y. -F. Wen, S. -J. Chen, Z. -W. Li and S. S. Sapatnekar, "Risk Propagation Based Vector Profiling for High Coverage Dynamic IR-Drop Analysis," 2023 IEEE/ACM International Conference on Computer Aided Design (ICCAD), San Francisco, CA, USA, 2023.
