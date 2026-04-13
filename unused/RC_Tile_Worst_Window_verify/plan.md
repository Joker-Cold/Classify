# RC-Tile 最坏窗口算法验证计划

> 目标：用 Innovus v20.10（myserver）对 `find_worst_window.py` 输出的压缩 VCD 做 IR Drop 分析，验证算法有效性。
> 设计：`des3`（ASAP7，VDD=0.7V）
> 上次更新：2026-04-09

---

## 1. 实验结果汇总

### 1.1 test.vcd（N_c=238，t_sim=11850ns）

| 版本 | 核心改动 | β | peak drop | ratio vs full(26mV) |
|------|---------|---|-----------|---------------------|
| m0/m1 | sum/peak-tile score，ρ=0.7 大窗 | 29.83% | 25mV | 0.962 |
| m1b | self-tune ρ = argmax/D | 29.83% | 25mV | 0.962 |
| m2 | small-window L=5，单 argmax | 2.1% | 21mV | 0.808 |
| **m3** | **top-K=2，双 argmax** | **4.2%** | **26mV** | **1.000** ✅ |
| m4/m5a | budget=10%，peak/neighbor | 4.2% | 26mV | 1.000 ✅ |
| full（基线） | — | 100% | 26mV | 1.000 |

### 1.2 test_2x.vcd（N_c=478，t_sim=23850ns，spatial 基线=34mV）

| 版本 | 窗口数 | β | peak drop | ratio vs spatial |
|------|--------|---|-----------|-----------------|
| m3 (top-K=2) | 2 | 2.09% | 30mV | 0.882 |
| m4 (budget=10%, peak) | 9 | 9.41% | 30mV | 0.882 |
| **m5a** (budget=10%, α=0.5) | **9** | **9.41%** | **30mV** | **0.882** |
| spatial_temporal | 20 | 30.9% | **34mV** | **1.000** |

**m5a 关键窗口（夹住真实 worst 区域）**：
- win06：orig 14550~14800ns → 29mV（真 worst 左侧）
- win07：orig 15250~15500ns → 29mV（真 worst 右侧）
- 真 worst：14895~15264ns（34mV）落在 win06/07 中间 **450ns 空隙**，未被命中

**根因**：`max_k P_t,k` 模型对 PG 弱区的空间邻接效应有系统偏差，cycle 298~305 在 Python 排名 >13，budget 再大也选不到。m5a（邻接加权）把该区域提升到 rank~13，接近但未进 top-9。

---

## 2. 算法代码状态

**文件**：`F:\GraduatePrj\Classify\RC_Tile_Worst_Window\code\find_worst_window.py`

当前已实现的 CLI 参数（累积，向后兼容）：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--small-window` | 关 | 启用 L=5 小窗模式 |
| `--top-k` | 0 | per-phase 最多取 K 个 argmax（0=由 budget 控制）|
| `--min-gap-cycles` | 10 | 两个 argmax 中心最小间距（cycles）|
| `--beta-budget` | 0.0 | β 预算，达到后停止选窗（0=关闭）|
| `--score-mode` | peak | peak / neighbor / cluster |
| `--neighbor-alpha` | 1.0 | 邻接加权系数（0~1，1=退化为 peak）|
| `--cluster-k` | 1 | cluster 模式取 top-K tile 均值 |

**中间产物（可直接复用，无需重跑 Step A）**：
```
intermediate/test_toggles.jsonl        ← test.vcd
intermediate/test_2x_toggles.jsonl    ← test_2x.vcd
intermediate/signal_location_rc.csv   ← 两者共用（同设计）
```

---

## 3. 下一步：m6（零代码改动）

**目标**：让贪心算法在 14895~15264ns 区域插入一个窗口。

| 方案 | 参数变化 | 预期 β | 预期命中 | 推荐顺序 |
|------|---------|--------|---------|---------|
| **M6-A** | `--min-gap-cycles 5` | ~10.5% | ✓（cycle 298 可被选中）| **先跑** |
| M6-B | `--beta-budget 0.15` | ~15.7% | ✓（target_K=15）| 次选 |
| M6-C | `--k-min 4`（L=9，宽窗） | ~17% | ✓（单窗覆盖 450ns）| 备选 |

**通过标准**：combined peak drop ≥ 33mV（ratio ≥ 0.97）。

**m6 基础命令（test_2x，在 m5a 命令上修改参数即可）**：
```bash
MSYS_NO_PATHCONV=1 docker exec grj-dev python \
    /app/Classify/RC_Tile_Worst_Window/code/find_worst_window.py \
    --location /app/Classify/RC_Tile_Worst_Window_verify/intermediate/signal_location_rc.csv \
    --toggles  /app/Classify/RC_Tile_Worst_Window_verify/intermediate/test_2x_toggles.jsonl \
    --vcd      /app/Classify/des_demo/vcd/test_2x.vcd \
    --n-grid 8 --k-theta 1.0 --rho 0.7 --eta 0.15 \
    --k-min 2 --gap 1 --n-min 3 \
    --clock-ns 50 --timescale-ps 10 \
    --small-window --top-k 0 --beta-budget 0.10 \
    --score-mode neighbor --neighbor-alpha 0.5 \
    --min-gap-cycles 5 \          # M6-A: 改这里
    --output   /app/.../vcd/test_2x_rctile_m6a.vcd \
    --json-out /app/.../report/report_2x_m6a.json
```

---

## 4. Agent Team 运作

### 角色

| Agent | 模型 | 职责 |
|-------|------|------|
| algo-analyst | Opus | 诊断、spec、更新 results.md/plan.md |
| coder | Sonnet | 代码实现、sanity check |
| exp-runner | Sonnet | 辅助（**不稳定，team-lead 通常直接执行**）|

### 循环

```
TeamCreate → algo-analyst spec
           → coder 实现
           → team-lead 执行 Docker + SSH（比 exp-runner 可靠）
           → CronCreate(*/2) 轮询 Innovus
           → 结果下载 → algo-analyst 更新文档
           → shutdown + TeamDelete
```

### Innovus 启动（已验证）

```bash
ssh myserver bash << 'REMOTE_EOF'
source /etc/profile 2>/dev/null
export CDS_BASE=/data/Installed_tools/cadence
export INNOVUS201_HOME=$CDS_BASE/INNOVUS201
export CDS_LIC_FILE=$CDS_BASE/license/license.dat:$CDS_BASE/license/cadence.dat:$CDS_BASE/license/cadence2.dat
export PATH=$INNOVUS201_HOME/tools/bin:$PATH
cd ~/data/des_demo/script/innovus
nohup innovus -no_gui -log ./<name>.log -files ./<name>.tcl > ./<name>.stdout 2>&1 &
echo PID=$! && disown
REMOTE_EOF
```

---

## 5. 关键路径

| 类别 | 路径 |
|------|------|
| 算法主文件 | `F:\GraduatePrj\Classify\RC_Tile_Worst_Window\code\find_worst_window.py` |
| 算法文档 | `F:\GraduatePrj\Classify\docs\algorithm_worst_window_lite.md` |
| 验证结果 | `results/rctile_m3/`、`results/rctile_2x_m4/`、`results/rctile_2x_m5a/` |
| 远程 Rail 结果 | `myserver:~/data/des_demo/db/rail_power_v20_rctile_*/` |

---

## 6. 新会话快速启动

```bash
# 1. 启动容器
docker start grj-dev && docker ps | grep grj-dev

# 2. 验证 m5a 功能
MSYS_NO_PATHCONV=1 docker exec grj-dev python \
    /app/Classify/RC_Tile_Worst_Window/code/find_worst_window.py --help 2>&1 \
    | grep -E "score-mode|neighbor-alpha|beta-budget"

# 3. SSH 连通性
ssh myserver "echo ok"

# 4. 直接跑 M6-A（改 --min-gap-cycles 5，其余参数同 m5a）
```
