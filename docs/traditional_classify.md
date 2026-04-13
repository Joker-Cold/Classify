# 传统向量分析(Vector Profiling)算法

> 来源：*Risk Propagation Based Vector Profiling for High Coverage Dynamic IR-Drop Analysis* (Wen et al.)

## 输入

| 输入              | 说明                                               |
| ----------------- | -------------------------------------------------- |
| VCD波形文件       | 记录电路所有信号随时间的翻转活动                   |
| Cell库文件(.lib)  | 提供每种cell的翻转功耗和漏电功耗参数               |
| 物理设计文件(DEF) | 提供instance的物理位置和tile网格划分               |
| 窗口长度          | 将波形分割为等长窗口的参数（几个到数百个时钟周期） |
| 选择数量 k        | 需要选出的top-k个高风险窗口数                      |

## 输出

| 输出              | 说明                            |
| ----------------- | ------------------------------- |
| 窗口索引列表 τ    | 包含 k 个最高风险窗口的编号     |
| 对应窗口的VCD片段 | 用于驱动后续动态IR-drop精确仿真 |

## 算法流程

### Step 1：波形分割

将完整波形按固定长度分割为 T 个窗口：t = 1, 2, ..., T

### Step 2：活动统计与事件功率计算

对每个窗口 t，功率引擎统计所有instance的上升/下降翻转活动，计算每个instance的功率：

```
P_instance,t = 翻转活动功耗(动态) + 漏电功耗(静态)
```

### Step 3：IR-drop风险评分

两种模式二选一：

**模式A：峰值总功率 (Peak Total Power)**

```
Score_t = Σ_{所有instance} P_instance,t
```

将整个芯片所有instance功率求和作为该窗口评分。

**模式B：峰值功率密度 (Peak Power Density)**

将芯片划分为 m×n 物理tile网格，计算每个tile的功率密度，取最大值：

```
Score_t = max_{tile r ∈ R} ( Σ_{instance ∈ tile r} P_instance,t / Area_r )
```

### Step 4：窗口选择

按 Score_t 降序排序，选前 k 个窗口存入 τ，输出对应的VCD片段用于精确仿真。


