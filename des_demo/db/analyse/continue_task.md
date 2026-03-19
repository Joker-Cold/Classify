# Continue Task: Phase 1 覆盖率 + 远程 Rail Analysis 补跑

## 已完成

### 1. coverage_tier1.py — 已完成并验证通过
- 路径: `db/analyse/coverage_tier1.py`
- 功能: 解析 Voltus Rail Analysis 报告，自动计算覆盖率指标
- 输出: `db/analyse/results/` 下的 CSV + Markdown 报告
- 验证: win1 C₁=81.8%, win2 C₁=100% 与手动计算一致

### 2. 远程服务器 Innovus 环境 — 已配置
- 服务器: `ssh -p 2223 myzhu@10.98.193.24` (SSH key 免密)
- Innovus **v20.10** (非 v15)
- 共享 tmux 会话: `tmux attach -t shared`
- 项目路径: `/home/myzhu/data/des_demo/`
- Power 数据 (win1~5 的 ptiavg) 已存在于 `db/power/avg_v15_winX/avg_v15_winX/`

### 3. v20 Rail Analysis 首次尝试 — 失败，需修复
- 脚本: `/home/myzhu/data/des_demo/script/innovus/rerun_rail_v20.tcl`
- 输出目录: `rail_power_v20_win{3,4,5}` 已创建但报告不完整（无 Reports/VDD/*.rpt）
- 错误: **Rail Analysis is unsuccessful due to errors**

## 待修复问题

### 问题 1: VCD 未拆分（用户指出的根本原因）
- v15 脚本 `full_irdrop_v15.tcl` 在**功耗分析阶段**用 `read_activity_file -start/-end` 指定时间窗口
- 当前 `rerun_rail_v20.tcl` **跳过了功耗分析**，直接用已有的 ptiavg 做 rail analysis
- 但已有的 ptiavg 是 v15 用同一个 VCD 的不同时间段生成的，应该没问题
- **用户怀疑**: 可能需要将 VCD 拆分为独立文件，而不是用 `-start/-end` 参数
- 需要确认: v20 的 `read_activity_file` 是否支持 `-start/-end`？还是需要预先拆分 VCD？

### 问题 2: Rail Analysis 失败的具体原因
从 `innovus.log7` 看到的历史错误 (供参考):
- `VOLTUS-1185`: Specify power grid libraries with `-power_grid_library`
- `VOLTUS-1129`: Rail analysis mode should be set properly
- `IMPTCM-48`: `set_pg_nets` 语法错误 (两条命令写在同一行)

但我们的 v20 脚本已修正了这些。tmux 中看到的实际错误是:
```
Rail Analysis is unsuccessful due to errors.
**ERROR: (PRL-387): "Rail Analysis" failed to finish successfully.
**ERROR: (VOLTUS-1055): Rail analysis failed to finish successfully
```
需要查看 voltus 子进程的详细日志来定位。

### 问题 3: 需要清理旧的失败输出
```bash
ssh -p 2223 myzhu@10.98.193.24 'rm -rf ~/data/des_demo/db/rail_power_v20_win{3,4,5}'
```

## 下一步计划

### 方案 A: 重新跑完整流程 (功耗 + Rail)
如果需要用 v20 重新做功耗分析:
1. 在 Innovus v20 中加载设计
2. 用 `read_activity_file` 读 VCD 的各时间窗口，生成新的 power 数据
3. 用新 power 数据做 rail analysis

### 方案 B: 拆分 VCD 后重跑
1. 用 Python 脚本将 `test.vcd` 按时间窗口拆成 5 个独立 VCD
2. 每个窗口用独立 VCD 做功耗分析
3. 再做 rail analysis

### 方案 C: 修复现有脚本只跑 Rail
如果已有的 ptiavg 数据兼容 v20:
1. 排查 voltus 子进程的具体错误
2. 修复脚本后重跑

## 关键路径和文件

| 项目 | 路径 |
|------|------|
| VCD 源文件 | `/home/myzhu/data/des_demo/vcd/test.vcd` |
| Power 数据 | `db/power/avg_v15_winX/avg_v15_winX/dynamic_{VDD,VSS}.ptiavg` |
| v20 脚本 | `script/innovus/rerun_rail_v20.tcl` |
| v15 全流程脚本 | `script/innovus/full_irdrop_v15.tcl` |
| PPL 文件 | `script/innovus/ring_pads_vdd.ppl`, `ring_pads_vss.ppl` |
| PG Library | `script/innovus/des3_pg_v20/techonly.cl` (已生成) |
| 覆盖率脚本 | `db/analyse/coverage_tier1.py` |

## 时间窗口定义
```
win1: 0ns     ~ 2370ns
win2: 2370ns  ~ 4740ns
win3: 4740ns  ~ 7110ns
win4: 7110ns  ~ 9480ns
win5: 9480ns  ~ 11850ns
```
VCD timescale: 10ps, 最后时间戳 #1185000
