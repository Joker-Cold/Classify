# PI 仿真覆盖率量化框架

> 基于 IR drop 仿真结果的子集覆盖率评估方法
> 适用场景：拥有全集 VCD 和子集 VCD 的完整 PI 仿真结果

---

## 一、问题定义

### 背景
- 传统 PI 仿真需对大规模 VCD 中的每个时钟窗口运行完整 IR drop 仿真，计算代价极高
- 工程实践中通过 **Vector Profiling** 筛选少数关键窗口，但"筛选的好不好"无法被量化
- **覆盖率**的本质问题：

> 给定一个 VCD 子集及其 PI 仿真结果，相比于全集 VCD 的仿真结果，该子集在多大程度上捕获了真实的最坏噪声场景？

### 数据结构

```
全集 VCD (S_full)  ──→ PI 仿真 ──→ IRdrop_full
                                     ├── 每个节点 v 的电压降
                                     ├── 每个时间窗口 w 的 peak IR drop
                                     └── 全局 worst-case 值

子集 VCD (S_sub)   ──→ PI 仿真 ──→ IRdrop_sub
                                     ├── 每个节点 v 的电压降
                                     ├── 每个时间窗口 w 的 peak IR drop
                                     └── 全局 worst-case 值
```

以 `IRdrop_full` 为 **Ground Truth**，评估 `IRdrop_sub` 的覆盖率。

---

## 二、覆盖率量化指标体系

### 指标一：全局最坏值捕获率 C₁

**定义**

$$C_1 = \frac{\max(\text{IRdrop}_{sub})}{\max(\text{IRdrop}_{full})}$$

**含义**
- 子集能否捕获整个芯片上、所有时间窗口中最严重的电压降
- $C_1 = 1.0$：完全捕获；$C_1 = 0.95$：遗漏了 5% 的最坏噪声

**优点**：物理意义清晰，是工业界 sign-off 最常用的判据

**局限**：只看单一最大值，若最坏点恰好命中但其他严重区域全部遗漏，指标会虚高

---

### 指标二：Hotspot 检出率 C₂

**定义**

首先定义 hotspot 节点集合（以阈值 θ 为判定标准，典型值为 5% × VDD）：

$$\mathcal{H}_{full} = \{v \mid \text{IRdrop}_{full}(v) > \theta\}$$
$$\mathcal{H}_{sub}  = \{v \mid \text{IRdrop}_{sub}(v)  > \theta\}$$

**Hotspot 检出率（Recall）**：

$$C_2 = \frac{|\mathcal{H}_{sub} \cap \mathcal{H}_{full}|}{|\mathcal{H}_{full}|}$$

**补充：精确率（Precision）**（避免假阳性）：

$$P = \frac{|\mathcal{H}_{sub} \cap \mathcal{H}_{full}|}{|\mathcal{H}_{sub}|}$$

**综合指标 F1-score**：

$$F_1 = \frac{2 \cdot C_2 \cdot P}{C_2 + P}$$

**含义**
- 直接回答"PI 仿真是否可信"：覆盖率高 → hotspot 不遗漏 → 仿真结果可用于 sign-off
- Recall 高：不漏报危险区域（工程安全性保证）
- Precision 高：不误报，不引入不必要的悲观余量

---

### 指标三：分位数捕获率 C₃

**定义**

$$C_3 = \frac{Q_{p}(\text{IRdrop}_{sub})}{Q_{p}(\text{IRdrop}_{full})}$$

推荐取 $p = 99\%$ 或 $p = 99.9\%$。

**含义**
- 比单看最大值更鲁棒，不受偶然极端值的噪声干扰
- 反映子集在"严重程度排名靠前"的区域上的整体代表性

---

### 三个指标的对比与定位

| 指标 | 公式核心 | 回答的核心问题 | 适用场景 |
|------|---------|--------------|---------|
| **C₁** 全局最坏捕获率 | max 之比 | 最极端噪声有没有被找到？ | sign-off 判据、单一热点验证 |
| **C₂** Hotspot 检出率 | 集合 Recall | 所有危险区域有没有全部覆盖？ | 全芯片可靠性验证 |
| **C₃** 分位数捕获率 | 高分位数之比 | 整体严重程度的代表性如何？ | 统计完整性、分布偏差检测 |

> **三者同时高才是真正高覆盖率的子集。**
> 单看 C₁ 不够：可能漏掉大量次严重 hotspot。
> 单看 C₂ 不够：可能 hotspot 都找到了，但最坏值有偏差。

---

## 三、完整评估流程

```
Step 1：读取全集仿真结果
         └── 逐节点 IR drop 值 → 建立 IRdrop_full 矩阵

Step 2：读取子集仿真结果
         └── 逐节点 IR drop 值 → 建立 IRdrop_sub 矩阵

Step 3：计算 C₁
         └── max(IRdrop_sub) / max(IRdrop_full)

Step 4：计算 C₂
         ├── 设定阈值 θ（如 0.05 × VDD）
         ├── 提取 H_full 和 H_sub
         └── 计算 Recall / Precision / F1

Step 5：计算 C₃
         └── 99th percentile 之比

Step 6：综合输出覆盖率报告
         └── 判断子集是否达到可接受的覆盖率标准
```

---

## 四、给 Claude Code 的数据分析任务说明

> 以下是针对已有仿真结果文件夹的处理指引，供 Claude Code 执行。

### 4.1 文件夹结构探索（第一步）

```bash
# 首先探索结果文件夹的结构
ls -lh <结果文件夹路径>
find <结果文件夹路径> -type f | head -50
```

需要确认的信息：
- 文件格式（`.rpt`、`.txt`、`.csv`、`.iv` 等）
- 是否有全集和子集的分目录
- IR drop 数据的存储方式（per-node / global peak / per-window）

### 4.2 数据解析目标

从仿真结果文件中提取：

| 字段 | 说明 |
|------|------|
| `node_id` 或坐标 `(x, y)` | PDN 节点标识 |
| `irdrop_value` | 该节点的电压降值（单位：V 或 mV）|
| `window_id` 或时间戳 | 对应的仿真时间窗口（可选）|
| `net_name` | 所属电源网络（VDD / VSS 等）|

### 4.3 分析脚本的核心逻辑（Python 伪代码）

```python
import numpy as np
import pandas as pd

# 读取全集和子集结果
df_full = parse_irdrop_report("results/full/")
df_sub  = parse_irdrop_report("results/subset/")

VDD = 1.0   # 标称电压，根据实际设计修改
theta = 0.05 * VDD  # hotspot 阈值

# C1：全局最坏值捕获率
C1 = df_sub["irdrop"].max() / df_full["irdrop"].max()

# C2：Hotspot 检出率
H_full = set(df_full[df_full["irdrop"] > theta]["node_id"])
H_sub  = set(df_sub [df_sub ["irdrop"] > theta]["node_id"])

recall    = len(H_sub & H_full) / len(H_full)
precision = len(H_sub & H_full) / len(H_sub)
F1        = 2 * recall * precision / (recall + precision)

# C3：分位数捕获率
C3 = np.percentile(df_sub["irdrop"], 99) / np.percentile(df_full["irdrop"], 99)

print(f"C1 (Worst-case Capture Rate): {C1:.4f}")
print(f"C2 (Hotspot Recall):          {recall:.4f}")
print(f"   (Hotspot Precision):        {precision:.4f}")
print(f"   (F1-score):                 {F1:.4f}")
print(f"C3 (99th Percentile Ratio):   {C3:.4f}")
```

### 4.4 给 Claude Code 的具体请求模板

当你有了文件夹路径后，可以这样请求 Claude Code：

```
我有两个 PI 仿真结果文件夹：
- 全集结果：<路径>
- 子集结果：<路径>

请你：
1. 先探索文件夹结构，告诉我文件格式和内容
2. 解析 IR drop 数据，提取每个节点的电压降值
3. 计算三个覆盖率指标 C1、C2（阈值=5% VDD=1.0V）、C3（99分位数）
4. 输出覆盖率分析报告，并画出全集 vs 子集的 IR drop 分布对比图
```

---

## 五、参考文献

1. **Voltus IC Power Integrity Solution User Guide**, Cadence, 2015. — Vector Profiling, Hotspot Debugger, Dynamic IR Drop Analysis 方法论
2. **Hu et al.**, "Machine Learning-Assisted VCD Processing for Accelerated Dynamic Voltage Drop Analysis," *ACM TODAES*, 2024/2025. — CHT 特征提取 + XGBoost 预测关键窗口
3. **Wen et al.**, "Risk Propagation Based Vector Profiling for High Coverage Dynamic IR-Drop Analysis," *ICCAD*, 2023. — 覆盖率 + Risk Propagation Score 框架

---

*文档版本：v1.0 | 作者：PI 仿真覆盖率优化研究课题组*
