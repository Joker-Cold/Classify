# 毕业设计（论文）中期报告

**课题名称**：基于 VCD 波形分析的芯片最差功耗场景自动选取方法研究

**专业**：微电子科学与工程

---

## 目录

1. [毕业设计的进展情况](#1-毕业设计的进展情况)
   - 1.1 [课题工作完成情况](#11-课题工作完成情况)
   - 1.2 [知识技能学习情况](#12-知识技能学习情况)
   - 1.3 [职业素养学习培养](#13-职业素养学习培养)
2. [存在的问题及解决方案](#2-存在的问题及解决方案)
   - 2.1 [存在的主要问题](#21-存在的主要问题)
   - 2.2 [解决方案与可行性研究](#22-解决方案与可行性研究)
3. [前期工作完成度与后续实施计划](#3-前期工作完成度与后续实施计划)
4. [参考文献](#参考文献)

---

## 1. 毕业设计的进展情况

### 1.1 课题工作完成情况

#### （1）研究背景与问题定义

本课题针对芯片电源完整性（PI）验证中仿真时间过长的工程痛点，研究如何从完整的 VCD 仿真波形中自动选取最差功耗（worst-case power）时间窗口，在大幅压缩仿真向量规模的同时，保持对 IR Drop 热点的有效覆盖。核心研究问题为：在不影响功耗验证有效性的前提下，将 VCD 激励压缩至原始规模的 10% 以内。

#### （2）量化评估标准的建立

由于传统验证覆盖率（功能覆盖率、代码覆盖率）不适用于功耗热点场景，本课题提出了面向 IR Drop 的**三级渐进式热点覆盖率（Hotspot Coverage）指标体系**：

- **Tier-1 全局指标**（已实现）：通过自动解析 Voltus 仿真报告（main.rpt, layerbased_ir.rpt, dynpwr.rpt），计算以下覆盖率指标：

  - **C₁（全局最坏 IR Drop 捕获率）**：C₁ = ΔV(sub)/ΔV(full)，其中 ΔV = V_nom − V_min。该指标直接反映子集能否捕获全集的最坏电压跌落，是 sign-off 最核心的判据。
  - **C_peak（峰值电流捕获率）**：C_peak = I_peak(sub)/I_peak(full)，峰值电流是 IR Drop 的直接驱动因素。
  - **C_layer(l)（逐金属层 IR Drop 覆盖率）**：C_layer(l) = ΔV_l(sub)/ΔV_l(full)，l ∈ {M1, M2, ..., M6, LISD}。不同金属层的 IR Drop 物理机制不同（上层以 lateral drop 为主，下层以 via drop 为主），逐层检验可避免局部盲区。取所有层的最小值 C_layer_min 和均值 C_layer_avg 作为汇总指标。
  - **C_violation（违规一致性）**：判断全集和子集的违规状态是否一致（全集有违规时子集也应检出）。
  - **多窗口包络组合**：当使用多个窗口时，取各窗口的最极端值——电压取 MIN(V_min)、电流取 MAX(I_peak)、逐层取 MAX(ΔV_l)——作为联合结果计算覆盖率。
  - **判定准则**：C₁ ≥ 95% 且 C_layer_min ≥ 80% 为 PASS；C₁ 在 90%~95% 为 MARGINAL；C₁ < 90% 为 FAIL。

- **Tier-2 空间指标**（已设计，待实现）：定义 Hotspot 集合 H = {inst | V_nom − V(inst) > θ}（θ 为 IR Drop 阈值，如 7%×V_nom），计算子集对全集 Hotspot 的 Recall（检出率）、Precision 和 F1 值。该指标需从 Voltus 导出逐 instance 电压数据。

- **Tier-3 统计指标**（已设计，待实现）：C₃ = Q_p(ΔV_sub)/Q_p(ΔV_full)（p=99%），用分位数比值替代单点极值，提供比 C₁ 更鲁棒的分布相似度度量。

#### （3）两种优化选窗方案的建立

**方案一：Phase-Aware + 空间集中度选窗（vcd_power_toolkit）**

该方案关注局部最坏解，不追求全局覆盖，核心思路为精确定位 IR Drop 最严重的时间段。算法包括三个关键步骤：

1. **时钟周期聚合**：按时钟边沿将信号翻转（toggle）聚合到对应周期，消除周期内时序差异
2. **Phase 检测**：基于翻转率阈值自动识别高活跃相位（如加密/解密切换），分相独立选窗
3. **退耦电容耗尽模型**：通过 depletion_ratio = 0.7 参数，将窗口定位于活跃相位的 70%~80% 位置——这是退耦电容累积耗尽、IR Drop 达到极值的物理位置，而非简单的 toggle 峰值位置
4. **空间集中度评分**（可选）：结合 DEF 物理坐标或 VCD scope 层次，计算翻转空间集中度 σ = max(group_toggle)/total，通过 effective = total × (1+α×σ) 对空间集中的窗口加权

**方案二：全局覆盖选窗（spatial_temporal）**

该方案采用常规思路，考虑全局时空覆盖，稳妥保障覆盖率。目前已完成方案设计，仿真数据待生成。

#### （4）实验验证

在 DES3（三重 DES 加密核，ASAP7 7nm 工艺，42,410 信号，64,179 标准单元）上进行了完整验证。共执行 8 次独立 Voltus Dynamic IR Drop 仿真：

| 仿真类型 | 编号 | 时间范围 | 占全 VCD 比例 |
|---------|------|---------|-------------|
| 全集基线 | full | 0~11850ns | 100% |
| 等分窗口 | eq_win1~5 | 各 2370ns | 各 20% |
| 算法选窗 | algo_win1 | 3790~4390ns | 5.1% |
| 算法选窗 | algo_win2 | 9600~10100ns | 4.2% |

**核心实验结果**：

| 方案 | VCD 占比 | C₁ (IR Drop 捕获率) | C_layer_min | Tier-1 判定 |
|------|---------|---------------------|-------------|-----------|
| 算法选窗 (win1+win2) | **9.3%** | **100.0%** | **100.0%** | **PASS** |
| 等分最优单窗 (win2) | 20% | 100.0% | 100.0% | PASS |
| 等分两窗 (win2+win4) | 40% | 100.0% | 100.0% | PASS |
| 等分全部 (win1~5) | 100% | 100.0% | 100.0% | PASS |

算法选窗在仅 9.3% 的仿真时长内达到了与全集完全一致的 Tier-1 覆盖率，验证了 Phase-Aware + 空间集中度选窗方法的有效性。同时发现，等分方案中 5 个窗口的覆盖率差异显著（C₁ 从 84.6% 到 100%），其中 eq_win3 判定为 FAIL（C_layer_min = 79.9%），说明盲目选窗无法保证验证质量。

#### （5）VCD 信号到物理位置的映射

开发了 VCD 信号到 DEF 物理坐标的自动映射工具，通过解析 DEF 文件的 COMPONENTS/PINS/NETS 段，将 VCD scope 层次路径转换为 DEF instance 路径（剥离 testbench 和顶层 instance 前缀，分隔符 '.' 转 '/'），优先使用 net driver cell 的坐标定位信号。在 DES3 设计上映射成功率达 99.8%（42,340/42,410 信号），未映射信号为 testbench 变量和 CTS 内部端口。该映射为空间集中度评分的 Grid 模式（将坐标映射到 NxN 物理网格）提供了坐标基础。

#### （6）工具链开发

完成了完整的 JSONL-based 分析工具链：VCD 解析 → 信号翻转标记 → 热力图可视化 → 选窗算法 → 覆盖率自动评估，实现了从原始 VCD 到覆盖率报告的端到端自动化流程。

### 1.2 知识技能学习情况

在本课题研究过程中，系统学习并掌握了以下知识和技能：

1. **EDA 工具操作**：学习了 Cadence Innovus v20.10 的 Dynamic IR Drop 仿真流程，包括电源网格建模、Voltus 引擎配置、Rail Analysis 参数设置与报告解析，能独立完成从 VCD 加载到 IR Drop 报告生成的完整流程。

2. **电源完整性理论**：深入理解了 PDN（Power Distribution Network）的基本分析方法，包括退耦电容的充放电模型、IR Drop 的时空分布特性、金属层级 IR Drop 的物理机制（上层 lateral drop vs 下层 via drop）等。

3. **编程与自动化**：使用 Python 开发了完整的分析工具链，涉及 VCD 格式解析、DEF 物理设计文件解析、大规模信号处理、Plotly 数据可视化、文本报告自动解析等。同时学习了 Python 与 EDA 工具（Innovus Tcl）的联动方法。

4. **算法设计**：设计并实现了 Phase-Aware 多窗口选取算法，涉及时间序列分析、相位检测、滑动窗口优化、空间集中度评分等算法概念。

### 1.3 职业素养学习培养

在毕业设计过程中，培养了以下职业素养：

1. **工程规范意识**：在电源完整性验证工作中，严格遵循 sign-off 标准（IR Drop 阈值 7% × Vnom），理解了芯片设计中安全裕量的工程意义。所提出的覆盖率评估方法遵循保守原则——C_layer > 100% 意味着子集比全集更悲观，从 sign-off 角度是安全的。

2. **科学严谨性**：在覆盖率方法论中，系统分析了指标体系的科学性，包括 C > 100% 的物理解释（初始条件偏差）、单一设计验证的统计局限性、阈值选择缺乏灵敏度分析等问题，并在文档中如实记录。

3. **团队协作与资源管理**：在远程 EDA 服务器上进行仿真时，合理使用共享计算资源（8 核并行），通过 tmux 会话管理长时间仿真任务，体现了对共享资源的负责任使用态度。

4. **知识产权意识**：测试电路 DES3 来源于开源社区（OpenCores, 作者 Rudolf Usselmann），工艺 PDK 使用学术开放的 ASAP7，在研究过程中注意了知识产权的合规使用。

---

## 2. 存在的问题及解决方案

### 2.1 存在的主要问题

#### 问题一：覆盖率评估体系尚不完整

目前仅实现了 Tier-1 全局覆盖率指标，Tier-2 空间 Hotspot 覆盖率和 Tier-3 统计分位数覆盖率尚未实现。Tier-1 虽然能捕获全局最坏 IR Drop，但无法回答"子集是否检出了所有危险区域"这一关键问题。此外，当前设计全部 0 violation，C_violation 指标无区分力。

#### 问题二：压缩率-覆盖率 Trade-off 曲线数据不足

当前仅有 5.1%（algo_win1）、9.3%（algo_win1+win2）、20%（等分单窗）等有限数据点，尚未建立完整的压缩率-覆盖率关系曲线，无法确定是否存在覆盖率急剧下降的"拐点"。

#### 问题三：单一设计验证的泛化性有限

目前仅在 DES3 一个电路上完成验证。DES3 是组合逻辑为主的对称设计，toggle 分布相对均匀。无法保证方法在高度非对称设计（如 CPU/GPU 不同功能模块）、大量时钟门控设计（toggle 分布极度不均）或多电压域设计中同样有效。

#### 问题四：初始条件偏差的影响

子集 VCD 切片从 t=0 重新仿真，退耦电容从满充状态开始，与全集仿真中同一时段的初始条件不同。这导致部分金属层覆盖率超过 100%（最高 LISD 层 106.5%），虽然从 sign-off 角度是保守安全的，但引入了系统性偏差。

#### 问题五：空间-时间联合优化方案（spatial_temporal）尚未验证

第二种优化方案已完成设计但尚未进行仿真验证，缺少与 Phase-Aware 方案的对比数据。

### 2.2 解决方案与可行性研究

#### 针对问题一：渐进式实现 Tier-2/3 覆盖率

- **Tier-2 Hotspot 覆盖率**：需从 Innovus/Voltus 中导出逐 instance 的最坏电压数据（通过 Tcl 脚本 `report_rail -instance` 命令），计算 Hotspot Recall 和 F1 值。技术方案已设计完毕，实现的瓶颈在于 EDA license 时间和数据导出的 Tcl 脚本开发。
- **替代方案**：可通过简化的 IR-Power 模型（基于 toggle rate 和 PDN 阻抗矩阵）快速预测空间 IR Drop 分布，避免对每个子集都执行完整 Voltus 仿真。也有文献报道使用机器学习方法（如图神经网络）从 toggle 特征快速预测 IR Drop 分布，可作为 Tier-2 的近似替代。

#### 针对问题二：构建多点 Trade-off 曲线

- 通过调整选窗算法的窗口数量和窗口长度参数，在 5%~50% 的压缩率范围内生成更多数据点
- 绘制覆盖率 vs 压缩率曲线，分析拐点位置
- 该实验的可行性较高，主要耗时在 Voltus 仿真（每次约 5~10 分钟）

#### 针对问题三：增加验证设计规模

- 在现有 DES3 基础上，计划增加 1~2 个不同类型的设计进行交叉验证
- 同时探索更大规模仿真向量（更长 VCD）下的算法表现
- 在论文中明确标注验证范围和适用条件

#### 针对问题四：Warm-up 机制

- 在 VCD 切片时，在目标窗口前添加 warm-up 余量周期，使 Voltus 仿真前段作为退耦电容预热期
- 当前算法的 depletion_ratio=0.7 已部分缓解该问题（窗口起始前有足够活跃周期）

#### 针对问题五：推进 spatial_temporal 方案仿真

- 生成 spatial_temporal 方案的选窗 VCD，提交 Voltus 仿真
- 与 Phase-Aware 方案进行相同指标下的对比分析

---

## 3. 前期工作完成度与后续实施计划

### 3.1 前期工作完成度

| 序号 | 工作内容 | 完成情况 | 备注 |
|------|---------|---------|------|
| 1 | 文献调研与方案设计 | ✅ 100% | 完成 IR Drop 理论、选窗算法文献调研 |
| 2 | VCD 解析与信号处理工具链 | ✅ 100% | 含 VCD 头解析、波形提取、JSONL 转换 |
| 3 | 翻转率分析与可视化 | ✅ 100% | 翻转热力图、差分热力图 |
| 4 | Phase-Aware 选窗算法 | ✅ 100% | 含相位检测、退耦耗尽模型、空间集中度 |
| 5 | VCD-DEF 物理坐标映射 | ✅ 100% | 映射成功率 99.8% |
| 6 | Tier-1 覆盖率自动评估 | ✅ 100% | 自动解析 Voltus 报告并计算四项指标 |
| 7 | DES3 全集 + 等分窗口仿真 | ✅ 100% | 6 次 Voltus 仿真 |
| 8 | DES3 算法选窗仿真 | ✅ 100% | algo_win1/win2, 2 次仿真 |
| 9 | Tier-2/3 覆盖率实现 | ⬜ 0% | 待 instance 级数据导出 |
| 10 | spatial_temporal 方案仿真 | ⬜ 0% | 待提交仿真 |
| 11 | 压缩率-覆盖率曲线 | 🔲 20% | 已有部分数据点 |
| 12 | 论文撰写 | 🔲 10% | 已有方法论文档和实验数据 |

**总体完成度约 65%**。

### 3.2 后续实施计划

| 阶段 | 时间安排 | 工作内容 |
|------|---------|---------|
| 第一阶段 | 3月下旬 | 完成 spatial_temporal 方案仿真验证，与 Phase-Aware 方案对比分析 |
| 第二阶段 | 4月上旬 | 实现 Tier-2 Hotspot 覆盖率（Tcl 脚本 + Python 分析）；构建完整 Trade-off 曲线 |
| 第三阶段 | 4月中旬 | （如条件允许）增加 1 个不同类型设计的交叉验证；灵敏度分析 |
| 第四阶段 | 4月下旬~5月 | 论文撰写：绪论、相关工作、方法论、实验结果与分析、结论 |
| 第五阶段 | 5月中旬 | 论文修改、查重、答辩准备 |

### 3.3 知识技能学习计划

- 继续深入学习 Voltus 高级功能（instance-level 报告导出、多电压域分析）
- 学习机器学习在 EDA 领域的应用文献，评估是否可用于 IR Drop 快速预测
- 提升学术论文写作能力，参考 IEEE/ACM 相关会议论文的写作规范

---

## 参考文献

[1] S. X. D. Tan and C. J. R. Shi, "Efficient very large scale integration power/ground network analysis via Green's function method," IEEE Journal of Solid-State Circuits, vol. 38, no. 6, pp. 949-959, Jun. 2003.

[2] T. Y. Wang and C. C. P. Chen, "Vectorless power supply noise analysis using multigrid method for large-scale on-chip power/ground networks," in Proc. DAC, 2004, pp. 830-833.

[3] N. H. Abdul Ghani and F. N. Najm, "Fast vectorless power grid verification using an approximate inverse technique," in Proc. DAC, 2009, pp. 184-189.

[4] Z. Qi, H. Meng, and J. Wang, "Machine learning-based IR drop prediction for fast power integrity analysis," in Proc. ASP-DAC, 2023, pp. 628-633.

[5] R. Usselmann, "DES/Triple DES IP Core," OpenCores. [Online]. Available: https://opencores.org/projects/des

[6] L. T. Clark et al., "ASAP7: A 7-nm FinFET predictive process design kit," Microelectronics Journal, vol. 53, pp. 105-115, Jul. 2016.
