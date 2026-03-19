# MAVIREC: ML-Aided Vectored IR-Drop Estimation and Classification

> Chhabria et al., 2021 (Univ. of Minnesota + NVIDIA)
> 论文总结

---

## 1. 解决的问题

工业 signoff 需要对大量测试向量做 **dynamic IR drop 分析**，但：
- 一个向量有 ~100K 个时钟周期（~5000 个 slice，每 slice 20 cycles）
- 工业工具跑一个 slice 的 Rail Analysis 需要 **3 小时**（30GB 存储）
- 传统 vector profiling 只能选出 **3~5 个** worst-case slice → 覆盖率不足
- 用平均功耗排序不准：**高功耗区域不一定对应高 IR drop**（Fig.2 的核心观察）

## 2. MAVIREC 整体流程

```
┌─────────────────────────────────────────────────────┐
│ 输入: VCD (100K cycles) + DEF + LEF + LIB + SPEF    │
│                                                      │
│ ① Candidate Generation (筛选 slice)                  │
│    Stage 1: 按 slice 平均功耗排序 → 保留 top Na=200  │
│    Stage 2: 按 region 功耗密度排序 → 每 region top 5  │
│    → ~100 个 unique candidate slices                  │
│                                                      │
│ ② Scoring (ML 快速推理)                              │
│    对每个 candidate slice:                            │
│    - 提取特征 (instance-level + tile-based 2D/3D)     │
│    - MAVIREC 模型推理 → 全芯片 instance-level IR drop │
│    - 每个 region 取 worst-case IR 作为 score          │
│                                                      │
│ ③ Ranking (区域覆盖最大化)                            │
│    - 按 IR score 降序选 slice                         │
│    - 跳过已覆盖 region 的重复 slice                   │
│    → 输出 No 个 slice + 对应 IR drop map              │
└─────────────────────────────────────────────────────┘
```

## 3. 特征工程

### 3.1 Instance-level 特征（7 个）

| 特征 | 含义 |
|------|------|
| `pi` | Internal power |
| `ps` | Switching power |
| `pl` | Leakage power |
| `pr` | Toggle-rate-scaled power = `pl + τ(ps + pi)` |
| `ptot` | Total power = `pl + ps + pi` |
| `pol` | Overlap power（共享 timing window 的邻居 pr 之和） |
| `r` | Effective distance to via stack（5μm 邻域内 V 个 via: `r⁻¹ = Σ dᵢ⁻¹`） |

### 3.2 Tile-level 2D 空间特征（7 个）

将芯片划分为 **2.5μm × 2.5μm** 的 tile 网格，每个 tile 聚合其中所有 instance 的特征：
- 功率类取 **求和**，effective distance 取 **最大值**
- 生成 7 张 2D feature map: `Pi, Ps, Pl, Pr, Ptot, Pol, R`

### 3.3 Temporal 3D 特征（n×t 张 power map）

- 将 20-cycle slice 细分为 `n×t = 20×5 = 100` 个 time step
- 每个 time step 生成一张 tile-level power map `Pt(j)`
- 公式: `pt(j) = pl + bj × (pi + ps)`，其中 `bj = 1` 当 instance 在 step j 翻转

**总输入通道数**: `n×t + 7 = 107` 张 tile-based feature map

## 4. ML 模型架构（核心创新）

基于 **U-Net** (encoder-decoder with skip connections)，两个关键改进：

### 4.1 3D 卷积 Encoder

```
输入: 107 通道 feature map (H × W × 107)

Encoder (下采样):
  4 × [3D Conv(3×3×3) + ReLU + 3D MaxPool]
  ↓ 捕获时空局部 switching activity（解决 temporal power map 极度稀疏问题）

Bridge (3D → 2D):
  沿 temporal 维度求和 + concatenate (skip connection)

Decoder (上采样):
  4 × [2D Conv(3×3) + ReLU + 2D Upsample]
  ↓ 输出: 7 张 β coefficient map (与 7 个 instance 特征对应)
```

**为什么用 3D 卷积而非 2D?**
- 真实工作负载中，cell 只在极少数时空位置翻转 → temporal power map 极度稀疏（zero-dominant）
- 2D 卷积把所有时间步当 channel 一起处理，非零信号被淹没
- 3D 卷积在 3×3×3 局部窗口内操作，能捕捉 **同时开关活动 (simultaneous switching)**

### 4.2 Regression-like 输出层

U-Net 不直接输出 IR drop 值，而是输出 **7 个系数 β₁~β₇ 的空间 map**：

```
IRᵢ = β₁·pᵢ + β₂·ps + β₃·pl + β₄·pr + β₅·ptot + β₆·pol + β₇·r
```

**优势**:
1. **可迁移性**: 学的是特征与 IR drop 的关系（β），而非 IR drop 值本身 → 跨设计通用
2. **细粒度**: 预测到 per-instance level（不是 per-tile）
3. **可解释性**: β 系数 = 每个特征对 IR drop 的敏感度，帮助定位 root cause

## 5. Vector Profiling 算法（Algorithm 1）

```python
# Stage 1: 粗筛 — 按 slice 平均功耗
for slice c in all_slices:  # ~5000 个
    P_slice[c] = Σ [pl + (Tc[c]/20) × (ps + pi)]  # 所有 instance 求和
C_Na = top_Na(P_slice)  # 保留 top 200

# Stage 2: 细筛 — 按 region 功耗密度
for region r in W_r × L_r:  # region = 15μm × 15μm = 6×6 tiles
    for slice c in C_Na:
        P_R[r][c] = Σ [pl + (Tc[c]/20) × (ps + pi)]  # 仅 region 内 instance
    C_Nr[r] = top_Nr(P_R[r])  # 每 region 保留 top 5
C_Nc = unique(C_Nr)  # ~100 个 unique candidates

# Scoring: ML 快速推理
for slice c in C_Nc:
    features = extract_features(c)  # 17 min (one-time) + 4 min (per-slice)
    IR_chip = MAVIREC_inference(features)  # <3s per slice
    for region r:
        IR_score[r][c] = max(IR_chip[c] in r)

# Ranking: 区域覆盖最大化
covered = set()
for n = 1 to N_o:
    (r, c) = argmax IR_score[r][c] where r not in covered
    output[n] = c
    covered.add(r)
```

## 6. 实验结果

### 6.1 IR drop 预测精度

| 指标 | 数值 |
|------|------|
| RMSE | < 4 mV (instance-level) |
| 分类准确率 (2.5μm tile) | 93.12% |
| 分类准确率 (15μm region) | 91.22% |
| F1 Score (6×6 region) | 0.78 |

### 6.2 速度

| 步骤 | 工业流程 | MAVIREC |
|------|---------|---------|
| 特征提取 | 3 hours | 17 min |
| 推理 | 5 min | **< 3s** |
| 总计 (per slice) | 3 hours | 18 min (**10× 加速**) |
| Vector profiling (100K cycles) | 2 hours | **30 min (4× 加速)** |

### 6.3 覆盖率

| 指标 | 工业流程 | MAVIREC |
|------|---------|---------|
| 推荐 slice 数 | 3 | 70~170 |
| 工业流程遗漏的 IR-critical regions | 5~11% | — |
| MAVIREC 遗漏率 | — | < 1.7% |

## 7. 与我们项目的关联

| MAVIREC 概念 | 我们的对应实现 |
|-------------|--------------|
| Slice (20-cycle window) | `select_worst_window.py` 的时间窗口 |
| Tile-based power map | `toggle_heatmap.py` 的 grid-based toggle 聚合 |
| Instance physical location from DEF | `vcd_def_mapper.py` 的信号→坐标映射 |
| Toggle count per slice | `jsonl_toggle_mark.py` 的 XOR toggle 计算 |
| Regional power density ranking | `find_worst_window.py` 的空间集中度 σ |
| Average power ≠ worst IR drop | 我们的核心发现（排名 #45 周期才是实际 worst） |

### 关键差异
- MAVIREC 用 **ML (3D U-Net)** 替代 Rail Analysis → 我们没有训练数据，用启发式
- MAVIREC 的 region-based ranking 思想与我们的 **spatial concentration** 方法一致
- MAVIREC 的 overlap power `pol` 概念 ≈ 我们的空间集中度公式 `effective = total × (1+α×σ)`
- **共同核心观察**: 仅靠 toggle/power 排序无法准确定位 worst IR drop，需要空间信息
