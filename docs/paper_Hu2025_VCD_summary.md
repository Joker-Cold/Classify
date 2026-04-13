# 论文解读：Machine Learning-Assisted VCD Processing for Accelerated Dynamic Voltage Drop Analysis

> **出处**：ACM Transactions on Design Automation of Electronic Systems (TODAES), 2025
> **作者**：Jingchao Hu, Yufei Chen, Songyu Sun, Jianfei Song, Li Zhang, Xunzhao Yin, Zhou Jin, Cheng Zhuo（浙江大学 / 湖北工业大学）
> **DOI**：https://doi.org/10.1145/3736579

---

## 1. 研究背景与动机

随着工艺节点不断缩小，电源完整性（Power Integrity, PI）挑战日益严峻。电源噪声（PSN）主要来源于两类：

- **IR drop**：由 PDN 电阻引起；
- **Ldi/dt 噪声**：由封装与片上寄生电感引起。

**动态压降（Dynamic Voltage Drop, DVD）分析**是工业电源签核（power sign-off）的核心流程，需要基于 VCD（Value Change Dump）文件驱动晶体管级瞬态仿真，以刻画真实切换活动带来的 PSN 波动。然而：

1. **计算昂贵**：几百纳秒的 DVD 分析可能需要数小时到数天。Intel 曾报告在 32nm 商用 DDR 上 20ns 轨迹的 PSN 签核耗时 16 小时。
2. **存储庞大**：现代设计节点数以亿计，VCD 文件体量巨大，解析和查询开销极高。

现有工作要么聚焦 VCD **文件编码压缩**（减小存储），要么聚焦 **vector profiling**（筛选关键时间窗），两者长期割裂。作者观察到：两类任务都依赖于**翻转率（toggle rate）信息**。若能统一处理，可同时消除时域与空间域的冗余。

---

## 2. 核心贡献

1. **Physical Design-Aware Circuit Hierarchy Tree (CHT)**：把 VCD 数据映射到物理设计上的层次树，在一次解析中同时提取功耗相关特征（供 profiling）与翻转率特征（供压缩）。
2. **基于 XGBoost 的 ML Vector Profiling**：以 CHT 抽取的特征预测每个 VTW 的最大压降，保留关键时间窗，显著缩短瞬态仿真输入轨迹。
3. **Profiling 与压缩一体化框架**：使用 94 叉 Huffman 编码压缩网络名，保持 ASCII 兼容，并与下游低级编码方法无缝衔接。

**实验效果**：在 ISPD2012 五个设计（25K~1M cells）上，相较商业工具 RedHawk，DVD 分析获得约 **3.53× 加速，误差仅 3.89%**；Huffman 压缩平均达 89.7×，最高 126.4×。

---

## 3. 背景概念

### 3.1 VCD 文件结构

VCD 有两大部分：

- **Header & Encoding Section**：元数据 + 用户实例名到短编码的映射；
- **Signal Transition Section**：各信号初值（#0）及后续状态变化。

状态取值：`0 / 1 / Z / X`。

### 3.2 关键定义

- **Transition**：某个网络在某时刻的一次切换事件 $tr_n(t)=state$；
- **Transition Block (TrB)**：同一时刻所有 transitions 的集合 $TrB(t)=\{tr_n(t), \forall n \in N\}$；
- **Vector Time Window (VTW)**：连续多个 TrB 聚合成的时间窗 $VTW(t)=\{TrB(t'), t'\in[t, t+L)\}$，是 profiling 的基本单元。

### 3.3 VCD 驱动的 DVD 分析流程

输入：门级 netlist + GDSII/DEF + SPEF + SDF/SDC/Liberty + testbench  →  VCS 仿真得 VCD → Profiling → RedHawk 等签核工具进行 DVD 分析。

商业工具（如 RedHawk）内建 vector profiling：将波形切成定长窗口，计算各窗口功耗并删除对压降无显著影响的非关键窗口。缺点是**每一时刻都算功耗特征**，开销巨大。

---

## 4. Physical Design-Aware CHT

CHT 是一棵异构层次树：

- **内部节点** = 实例/子模块
- **叶节点** = pin
- **节点属性**：逻辑信息 + 物理坐标 + 翻转率 + 负载阻抗 + 功耗特征

### 4.1 构建流程

1. **Establishment**：递归解析 VCD 的 Header 生成 Structure Dictionary (SD)，构建层次树。
2. **Annotation**：post-order DFS 遍历，利用 **镜像栈（mirror stack）** 跟踪层次路径，查询 SPEF/GDSII/DEF 等物理文件。对层次化设计通过累加相对坐标得到绝对位置（示例：$c_1+c_2+c_3=(1000,1000)$）。
3. **Initialize & Update**：
   - **Global Update**（初始化或高翻转率）：遍历全部节点，复杂度 $O(N_{node})$；
   - **Partial Update**（低翻转率）：仅更新 TrB 涉及的节点，复杂度 $O(n \cdot \log N_{node})$；
   - 算法 1 给出 Global Update 的伪代码。
4. **Summarize & Output**：在每个 VTW 结束时对 CHT 做 BFS 聚合特征：
$$ F = \sum_{i=1}^{L} f_{def}(TrB(t_i), S(t_i)) $$

### 4.2 Huffman 文本压缩

- 利用 CHT 已存的翻转频率直接构建 Huffman 树；
- 可打印 ASCII 字符 94 个（去掉空格），采用 **94 叉 Huffman**；
- 步骤：Padding（补足 $pad = 93-((n-1)\bmod 93)$ 个 dummy 叶子）→ 按 toggle rate 建 min-heap → 构建 Huffman 树 → 生成 net name → 编码映射表。

压缩结果（表 1）：

| 方法 | DMA | DES_PERF | B19 | VGA_LCD | NETCARD |
|---|---|---|---|---|---|
| Huf | 1.2 | 1.3 | 1.4 | 1.3 | 1.6 |
| Huf+Sel | 5.9 | 6.2 | 6.7 | 6.4 | 8.0 |
| Bzip2 | 9.2 | 14.3 | 13.6 | 13.9 | 17.8 |
| Huf+Bzip2 | 11.4 | 18.1 | 18.9 | 17.8 | 26.9 |
| **Huf+Sel+Bzip2** | **55.3** | **89.1** | **91.6** | **86.2** | **126.4** |

与 [Gao 2023] 等低级编码（402× 平均）相比，本文方法略逊，但**仍是 ASCII 文件**，可与商用解析流程无缝衔接，并可作为下游低级压缩的前处理步骤。

---

## 5. ML-Assisted Vector Profiling

### 5.1 时-空分解

- **Temporal**：波形均匀切成定长 VTW（论文实验取 5ns）；
- **Spatial**：芯片平面划成 20×20 的 tiles，降低 ML 模型复杂度。

### 5.2 快速功耗估计

在 CHT 上直接计算，避免调用精确签核工具：

- **Switching Power**：
$$ P_{s,i}=\sum_{n=1}^{N}\frac{C_{load,n}\cdot V_{dd}^2 \cdot f \cdot \mathbb{1}(n, VTW(t))}{2} $$
- **Internal Power**：用 LUT 平均值（跳过插值）计算
$$ P_{i,i}=\sum_{n=1}^{N} P(s_n^t, s_n^{t'},\dots)\cdot \mathbb{1}(n, VTW(t)) $$
- **Leakage Power**：按状态查表，而非用平均漏电
$$ P_{l,i}=\sum_{n=1}^{N}\ell(s_n^t, s_n^{t'},\dots) $$

### 5.3 XGBoost 预测器

**特征集合（见论文表 2）**：

- **Tile 级特征**：$T_i$（tile 翻转率）、$P_{t,i}$、$P_{i,i}$、$P_{s,i}$、$R_i$（有效电阻，来自商业工具）；
- **VTW 级特征**：$T_{total}$、$T_{max}$、$T_{top3}$、$T_{change}$（两个 VTW 的翻转率差）、$T_v$（方差）、$P_t$、$P_{i,max}$、$P_{s,max}$、$P_{t,max}$（按电阻归一化的最大总功耗）、$P_{t,top3}$。

**设计思路**：
- $T_{change}$ 反映 $Ldi/dt$ 噪声（翻转越剧烈瞬态电流越大）；
- $P_{t,max}, P_{t,top3}$ 用有效电阻归一化，因 $V=IR$，低电阻可抵消高电流影响；
- $T_{top3}$ 防止个别极端翻转 tile 主导特征。

**目标与损失**：采用回归形式预测每个 tile 的最大压降 $\hat{V}^{(t_0)}_i$，阈值 $T$ 控制保留率：
$$ \max_{i\in M}(\hat{V}^{(t_0)}_i) > T \Rightarrow \text{保留该 VTW} $$

损失函数：
$$ obj = \sum_{i=1}^{n}(y^{(i)}-\hat{y}^{(i)})^2 + \sum_{k=1}^{K} \Omega(f_k),\quad \Omega(f)=\gamma T + \tfrac{1}{2}\lambda \|w\|^2 $$

数据集 80/20 划分训练/测试。

---

## 6. 实验结果

### 6.1 平台与基准

- ISPD 2012 基准 5 个设计：DMA (25K)、DES_PERF (111K)、B19 (219K)、VGA_LCD (165K)、NETCARD (959K)；
- 40nm 工艺，i9-9980XE CPU，128GB RAM；
- VTW=5ns，20×20 tiles；
- 每个设计生成两个 VCD：短文件用于训练/测试 XGBoost；长文件用于验证 DVD 分析精度；
- 对 leon32mp 类处理器额外用 CoreMark 等真实 workload 来保证 toggle 覆盖率。

### 6.2 Profiling 预测精度（Kendall's tau）

以 **MAVIREC**（DNN 版）为基线，分 A（商业工具精确特征）与 E（本文估计特征）两档。结果：
- XGBoost（估计特征） ≈ MAVIREC-A（精确特征），并**全面优于 MAVIREC-E**；
- 证明 XGBoost 对简化/噪声特征更鲁棒。

### 6.3 Profiled VCD 的 DVD 精度（表 3）

| SR | 平均 ER | 备注 |
|---|---|---|
| 0.5 | ~0% | 完全精确 |
| 0.4 | 0.4% | |
| 0.3 | 1.4% | |
| **0.2** | **≈3.8%** | 论文采用 |
| 0.1 | 16.5% | 精度恶化 |

### 6.4 与 RedHawk profiling 的对比（表 4，ER=0）

要求零误差时各方法的最大保留率（越小越好）：

| | DMA | DES_PERF | B19 | VGA_LCD | NETCARD |
|---|---|---|---|---|---|
| RedHawk | 0.59 | 0.63 | 0.71 | 0.66 | 0.63 |
| **Ours** | **0.38** | **0.41** | **0.51** | **0.47** | **0.52** |
| 提升 | 35.6% | 34.9% | 28.2% | 28.8% | 17.5% |

平均在 0 误差条件下额外减少 **≈29%** 的向量。

### 6.5 整体效率（表 5）

分两阶段：$t_1$ = vector profiling / 特征提取；$t_2$ = 瞬态仿真。以 NETCARD 为例：

| 方法 | $t_1$(s) | $t_2$(s) | 总计 |
|---|---|---|---|
| Ori | 2848.8 | 22138.2 | ≈24987 |
| VS-RH | 2839.1 | 15318.0 | ≈18157 |
| **Ours (SR=0.2)** | **2011.7** | **4513.3** | **≈6525** |

- 特征抽取阶段比 RedHawk 快 **1.64×**（得益于 CHT 结构 + 简化功耗模型）；
- 瞬态仿真阶段约 5× 加速（只处理 20% VTW）；
- **整体 DVD 分析 ≈3.53× 加速**；
- XGBoost 训练仅需 **145 秒 CPU**，而 MAVIREC 需 **~5 小时 GPU**。

---

## 7. 方法亮点与启发

1. **一次解析，双向收益**：CHT 让 profiling 和压缩共享同一份 toggle 数据，避免重复解析。
2. **物理感知**：把 VCD 与 GDSII/DEF/SPEF 的物理坐标、负载信息同时挂在树上，为 ML 特征奠基。
3. **轻量模型 + 简化特征即可击败 DNN**：XGBoost 配合手工特征（电阻归一化、Top-3 等）取得优于 MAVIREC 的排序精度，说明在压降预测这类结构化问题上，**合适的特征工程比模型容量更重要**。
4. **ASCII 兼容的 Huffman 压缩**：牺牲一定压缩率换取商业流程兼容性，务实工程取向。
5. **工业现实导向**：作者明确不替代商业签核，而是**前置压缩输入 trace**，这条路线与 [Chen 2022]、[Chhabria 2021] 等互补。

---

## 8. 局限与可能改进方向

1. **依赖 CHT 构建质量**：对层次极深或大规模 flatten 设计，mirror stack 与 DFS 遍历的成本需进一步验证；
2. **特征设计偏经验**：$T_{top3}$、$P_{t,top3}$ 等阈值策略需跨工艺迁移时重新调参；
3. **训练数据跨设计迁移性有限**：论文提到「同族设计可复用」，但未详尽评估跨工艺/跨架构迁移；
4. **压缩率低于低级编码**：89.7× vs 402×（Gao 2023），说明纯 ASCII 方案的天花板；
5. **阈值 $T$ 设置仍需人工**：目前按 SR 调整，缺乏自适应策略（可结合保守 bound 或 RL）；
6. **未覆盖 Ldi/dt 噪声的精细建模**：仅以 $T_{change}$ 代理。

---

## 9. 与本毕设的关联

本文框架与本毕设（VCD 解析 → Toggle 统计 → 时-空选择 → VCD 压缩）高度契合：

| Hu 2025 | 本毕设对应模块 |
|---|---|
| Physical Design-Aware CHT | `Classify/` VCD 解析 + 层次组织 |
| Toggle 特征抽取 | Toggle 统计阶段 |
| XGBoost VTW profiling | 关键时间窗选择 / 算法 worst window |
| Huffman ASCII 编码 | VCD 压缩模块 |
| 5ns VTW + 20×20 tile | 可借鉴的实验参数 |

**可直接复用/借鉴的点**：

- **特征集合**（表 2）可作为本毕设预测器的起点；
- **镜像栈 + DFS 标注物理信息** 的做法可用于把 DEF/SPEF 数据挂到本地 CHT；
- **Global vs Partial Update** 的选择策略适合不同 toggle 密度场景；
- **ER / MAE / MAX / Kendall's tau** 四项指标可作为本毕设的评估口径；
- **训练 VCD 与验证 VCD 分离** 的做法可避免过拟合评估偏差。

---

## 10. 参考文献（关键条目）

- [2] Ansys RedHawk
- [6] XGBoost (Chen & Guestrin 2016)
- [12] MAVIREC (Chhabria 2021, DATE)
- [22] Naroska 2003, ASP-DAC —— VCD 波形压缩
- [35] Wen 2023, ICCAD —— Risk Propagation Based Vector Profiling
- [38] PowerNet (Xie 2020)
- [43] GRANNITE (Zhang 2020, DAC)

完整文献列表见原文 References 章节。
