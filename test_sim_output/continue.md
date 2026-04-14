# ISPD2012 Benchmark Voltus Simulation — Continuation Guide

## 总体目标
5个电路的 VCD 压缩 → Voltus IR Drop 仿真 → 覆盖率对比评估

## 当前进度 (2026-04-14)

| 电路 | P&R | Voltus Full VCD | VCD压缩 | Voltus Compressed |
|------|-----|-----------------|---------|-------------------|
| **DMA_slow** (22K cells) | ✅ 完成 | ✅ 完成 | ❌ 待做 | ❌ 待做 |
| **des_perf_slow** (111K cells) | ✅ 完成 | ✅ 完成 | ❌ 待做 | ❌ 待做 |
| **vga_lcd_slow** (165K cells) | ⏳ 运行中 (placement阶段) | ❌ 待P&R后 | ❌ 待做 | ❌ 待做 |
| **leon3mp_slow** (649K cells) | ❌ 等vga完成后 | ❌ | ❌ 待做 | ❌ 待做 |
| **des_demo** (参考) | ✅ 已有 | ✅ 已有 | ✅ 已有 | 部分 |

## 远程服务器信息
- **SSH**: `ssh -p 2223 myzhu@10.98.193.24`
- **Innovus路径**: `/data/Installed_tools/cadence/INNOVUS201`
- **项目目录**: `~/data/test_sim_output/`
- **License**: 由 `/etc/profile` 配置（本地 .dat 文件，不要用 port@hostname）

## 已解决的关键问题

### 1. contest_cells.lef 生成
- ISPD2012 无物理 LEF，用 Python 生成: `scripts/gen_contest_lef.py`
- 匹配 ASAP7 tech LEF: SITE=asap7sc7p5t, DATABASE MICRONS 4000
- **关键修复**: 所有坐标必须 snap 到 MANUFACTURINGGRID=0.004um

### 2. Innovus v20 locale crash
- 错误: `locale::facet::_S_create_c_locale name not valid`
- 原因: Innovus v20 与 Ubuntu 22/24 glibc 不兼容
- **解决**: `LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libstdc++.so.6` + `LC_ALL=C`
- **但 optDesign 仍会 crash**（即使 catch 也无法拦截 ABORT signal）

### 3. 脚本错误处理 (IMPSYT-6692)
- Innovus 的 `-init` 脚本执行器会因任何未捕获错误停止后续命令
- **解决**: 使用 `wrapper.tcl` 模式，`catch {source pr_flow.tcl}` 后手动 defOut/saveNetlist
- 即使 P&R 在 routeDesign 后报错，wrapper 仍能保存 DEF 和网表

### 4. ccopt_design 失败
- 原因: contest.lib 无 buffer/clock gate 单元
- 已用 `suppressMessage` + `catch` 处理
- 对 IR Drop 分析无影响（CTS 不是必须的）

### 5. Voltus 相关
- VCD 需要指定 `-start`/`-end` 时间
- pad 文件格式: 4列 `name x y layer`（不是简单的 `x y`）
- pad 坐标必须在实际 power ring 金属上（从 DEF SPECIALNETS 解析）

## 启动运行的标准命令

### 环境设置脚本（所有电路通用）
```bash
# /tmp/run_pr_circuit.sh (已在服务器上)
#!/bin/bash
CIRCUIT=$1
source /etc/profile
export LC_ALL=C LANG=C
export INNOVUS201_HOME=/data/Installed_tools/cadence/INNOVUS201
export PATH=$INNOVUS201_HOME/tools/bin:$PATH
export LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libstdc++.so.6
cd ~/data/test_sim_output/$CIRCUIT/script
rm -f pr_flow.log pr_flow.stdout
innovus -nowin -init wrapper.tcl -log pr_flow.log > pr_flow.stdout 2>&1
echo "EXIT_CODE=$?" >> pr_flow.stdout
```

### 运行 P&R
```bash
nohup /tmp/run_pr_circuit.sh <circuit_name> > /dev/null 2>&1 &
```

### P&R 完成后生成 pad 文件
在服务器上运行 Python 脚本解析 DEF 中的 ring 坐标，生成 `ring_pads_{vdd,vss}.ppl`。
参考 `/tmp/gen_pads2.py` 或从 DEF 的 SPECIALNETS 中提取 M6/M7 ring 坐标。

### 运行 Voltus
```bash
# /tmp/run_voltus_circuit.sh (已在服务器上)
nohup /tmp/run_voltus_circuit.sh <circuit_name> > /dev/null 2>&1 &
```

### 监控进度
```bash
# P&R 进度
tail -f ~/data/test_sim_output/<circuit>/script/pr_flow.stdout

# Voltus 进度
tail -f ~/data/test_sim_output/<circuit>/script/voltus_full.stdout

# 检查输出文件
ls -la ~/data/test_sim_output/<circuit>/src/<circuit>.def
ls -la ~/data/test_sim_output/<circuit>/sim_data/full/rail/
```

## 未完成的工作

### 1. vga_lcd_slow P&R + Voltus
- P&R 正在运行（placement 阶段），预计 5-10 分钟完成
- 完成后需: 生成 pad 文件 → 运行 Voltus

### 2. leon3mp_slow P&R + Voltus
- 649K cells，最大的电路
- 等 vga_lcd_slow 完成后运行（共享 Innovus license）
- 预计 P&R 15-30 分钟

### 3. 本地 VCD 压缩 (Phase 4)
- 对每个电路运行 `code/find_worst_window.py` 生成压缩 VCD
- 两种方法: traditional (toggle-based) 和 risk_propagation
- 输出: `{circuit}/vcd/{circuit}_compressed_{method}.vcd`

### 4. 压缩 VCD 上传 + Voltus 对比 (Phase 5)
- 上传压缩 VCD 到服务器
- 运行 `voltus_compressed.tcl`（脚本已就绪，需设置 METHOD 环境变量）

### 5. 覆盖率评估 (Phase 6)
- 对比 full vs compressed 的 IR Drop 结果
- 使用 `db/analyse/coverage_tier1.py` 框架

## 已完成的 Voltus 结果

### DMA_slow
- VDD: Min=0.651V, Avg=0.666V, Max=0.700V (0 violations)
- VSS: Max bounce=56.3mV (0 violations)
- Rail reports: `sim_data/full/rail/rail_full/PD_25C_dynamic_3/`

### des_perf_slow
- VDD: Min=0.479V, Avg=0.533V, Max=0.700V (73345 violations)
- VSS: Max bounce=231mV (70608 violations)
- 显著 IR Drop，是好的测试用例
- Rail reports: `sim_data/full/rail/rail_full/PD_25C_dynamic_1/`

## 文件结构
```
test_sim_output/
├── scripts/
│   ├── gen_contest_lef.py      # 生成 contest LEF（已修复 grid snap）
│   └── contest_cells.lef       # 已生成
├── lib/
│   └── contest.lib             # ISPD2012 时序库
├── DMA_slow/
│   ├── src/
│   │   ├── DMA_slow.v          # 网表（原始 + P&R后的）
│   │   ├── DMA_slow.sdc        # 约束
│   │   └── DMA_slow.def        # P&R 输出 (3MB)
│   ├── vcd/
│   │   └── sim.vcd             # 完整 VCD (6MB, 192600ps)
│   ├── script/
│   │   ├── pr_flow.tcl         # P&R 脚本
│   │   ├── wrapper.tcl         # P&R 错误恢复包装器
│   │   ├── voltus_full.tcl     # 全 VCD Voltus
│   │   ├── voltus_compressed.tcl # 压缩 VCD Voltus
│   │   ├── wrapper_voltus_full.tcl
│   │   ├── contest.mmmc        # MMMC 视图（硬编码路径）
│   │   ├── ring_pads_vdd.ppl   # 电源 pad 坐标
│   │   └── ring_pads_vss.ppl
│   └── sim_data/full/          # Voltus 输出
├── des_perf_slow/              # 同上结构
├── vga_lcd_slow/               # 同上结构
└── leon3mp_slow/               # 同上结构
```

## VCD 时间范围
| 电路 | Timescale | End Time | Scope |
|------|-----------|----------|-------|
| DMA_slow | 1ps | 192600ps | tb/u0 |
| des_perf_slow | 1ps | 192600ps | tb/u0 |
| vga_lcd_slow | 1ps | 149800ps | tb/u0 |
| leon3mp_slow | 1ps | 385200ps | tb/u0 |

## Team 建立要求

下次继续时，需要建立多 Agent 协作 Team 来高效推进。

### Team 结构

| 成员 | 模型 | 职责 | 权限模式 |
|------|------|------|----------|
| **team-lead** (主 agent) | **opus** | 总体协调、审查产出质量、Phase 4/6 本地 Python 分析 | 默认 |
| **remote-ops** | **sonnet** | SSH 远程操作：P&R执行、Voltus执行、文件传输、进度监控 | bypassPermissions |
| **script-gen** | **sonnet** | 生成/修复 TCL/Shell 脚本（按需，当前脚本已基本就绪可省略） | bypassPermissions |

### 建立步骤

1. **创建 Team**:
   ```
   TeamCreate: team_name="ispd-voltus", description="ISPD2012 Benchmark P&R + Voltus IR Drop pipeline"
   ```

2. **创建任务** (TaskCreate):
   - 按 Phase 分解为粒度合适的任务
   - 当前剩余任务列表见下方「未完成的工作」
   - 设置 blockedBy 依赖关系（如 Voltus 任务依赖于 P&R 完成）

3. **启动 Teammate** (Agent tool):
   ```
   Agent: name="remote-ops", subagent_type="general-purpose", team_name="ispd-voltus",
          mode="bypassPermissions", model="sonnet"
   prompt: "你是远程服务器操作员。通过 SSH 执行 EDA 工具命令。
            SSH: ssh -p 2223 myzhu@10.98.193.24
            Innovus 环境: source /etc/profile && export LC_ALL=C LANG=C &&
            export INNOVUS201_HOME=/data/Installed_tools/cadence/INNOVUS201 &&
            export PATH=$INNOVUS201_HOME/tools/bin:$PATH &&
            export LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libstdc++.so.6
            项目目录: ~/data/test_sim_output/
            查看 TaskList 领取任务并执行。"
   ```

4. **任务分配**: 通过 TaskUpdate 的 owner 参数分配任务给 teammate

### 关键经验教训（从本次 session 总结）

- **remote-ops 需要完整的环境变量说明**: 必须包含 `LC_ALL=C`、`LD_PRELOAD` 和正确的 license 配置（`/etc/profile` 提供，不要覆盖 `CDS_LIC_FILE`）
- **script-gen 容易引入回退**: 上次 session 中 script-gen 多次将已修复的路径改回错误版本。建议在任务描述中明确「不要修改 XXX 路径」或者改用 team-lead 直接修改
- **wrapper.tcl 模式是必须的**: 所有 Innovus `-init` 脚本必须通过 wrapper.tcl 执行，否则 IMPSYT-6692 会阻止后续命令（包括 defOut）
- **P&R 后必须手动生成 pad 文件**: wrapper.tcl 的 catch 块里 `dbget top.fplan.corebox` 可能失败，需要从 DEF 的 DIEAREA/SPECIALNETS 解析 ring 坐标来生成
- **Innovus license 单次一个**: 只能串行运行 P&R 和 Voltus（共享 license），不能并行

### 并行化策略

```
Phase 3 (远程 P&R/Voltus)              Phase 4 (本地 VCD 压缩)
│                                       │
├─ vga_lcd_slow P&R ─── Voltus         ├─ DMA_slow VCD 压缩
├─ leon3mp_slow P&R ─── Voltus         ├─ des_perf_slow VCD 压缩
│                                       ├─ vga_lcd_slow VCD 压缩
│                                       └─ leon3mp_slow VCD 压缩
│
└─── Phase 5: 上传压缩 VCD → Voltus compressed 对比
     └─── Phase 6: 覆盖率评估
```

- remote-ops 在远程**串行**执行 P&R + Voltus（license 限制）
- team-lead 在本地**并行**执行 VCD 压缩分析（不依赖远程）
- Phase 5 需要 Phase 3 + Phase 4 都完成后才能开始

## 注意事项
- `/tmp/run_pr_circuit.sh` 和 `/tmp/run_voltus_circuit.sh` 在 /tmp 中，服务器重启后会丢失，需要重建（内容见上方「启动运行的标准命令」）
- MMMC 文件使用硬编码路径（因为 `[info script]` 在 init_mmmc_file 中返回空）
- contest.lib 路径: `/home/myzhu/data/test_sim_output/lib/contest.lib`
- ASAP7 tech LEF: `/home/myzhu/data/des_demo/db/des3.enc.dat/libs/lef/asap7_tech_4x_201209.lef`
- QRC: `/home/myzhu/data/des_demo/db/des3.enc.dat/libs/mmmc/rc_typ_25/qrcTechFile_typ03_scaled4xV06`
