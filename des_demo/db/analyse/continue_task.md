# Continue Task: Worst-Case Window Selection + 物理位置映射 + 覆盖率验证

## 当前进展总览

项目目标: 压缩 VCD 文件，只保留 worst-case power 窗口，不影响芯片功耗验证精度。

### 已完成的工具链

| 工具 | 路径 | 功能 | 状态 |
|------|------|------|------|
| VCD 解析器 | `code/parse_vcd_signal.py` | VCD header/waveform 解析，多 scope 消歧 | ✅ |
| VCD→JSONL | `code/vcd_to_jsonl.py` | VCD 转 JSONL（hold-last-value） | ✅ |
| Toggle 标记 | `code/jsonl_toggle_mark.py` | 逐 bit XOR toggle 计算 | ✅ |
| Phase-Aware 选窗 | `code/select_worst_window.py` | 核心算法库：aggregate_by_clock, detect_phases, select_windows | ✅ |
| 选窗 CLI | `code/find_worst_window.py` | Phase-Aware + 空间集中度选窗 | ✅ |
| **VCD→DEF 物理映射** | `code/vcd_def_mapper.py` | **本次新增**，VCD 信号→芯片物理坐标 | ✅ |
| 覆盖率分析 | `db/analyse/coverage_tier1.py` | Voltus Rail 报告解析 + 覆盖率计算 | ✅ (需适配 v20) |
| VCD 切片 | `code/vcd_slicer.py` | VCD 时间窗口裁剪 | ✅ |

### 已完成的验证数据

- **v20 Rail Analysis**: 5 等分窗口全部跑通，worst IR drop = win2 (26mV)
- **Phase-Aware 选窗验证**: depletion_ratio=0.7 选出 3790~4390ns 覆盖实际 worst-case 4050ns

---

## 本次完成: VCD→DEF 物理位置映射器

### `code/vcd_def_mapper.py`

**功能**: 将 VCD 仿真信号映射到 DEF 物理芯片坐标

**映射策略** (按优先级):
1. **COMPONENTS 直接匹配** — DEF path 完全一致的 cell 放置坐标
2. **PINS 匹配** — 顶层端口 (desOut, desIn 等)
3. **NETS driver 匹配** — net 的驱动 cell (pin=Q/QN/Y/Z) 的放置坐标 ← 最常用
4. **FE_PHN→FE_PHC** — Physical Net→Physical Cell 名称转换
5. **Bus 信号** — 用第一个 bit 的 net driver 坐标

**关键实现细节**:
- VCD scope→DEF path: 去掉 testbench (`test`) + 顶层实例 (`u0`)，`.`→`/`
- DEF 括号转义: `\[` → `[` (COMPONENTS/NETS 一致处理)
- 流式解析 91 万行 DEF 文件，不加载到内存
- 坐标自动除以 UNITS (4000) 转换为 um

**映射结果**:
```
Total:     42,410 VCD signals
Mapped:    42,340 (99.8%)
Unmapped:      70 (testbench 变量 / CTS clk / 子模块内部端口)

Source breakdown:
  net_driver:     42,021  ← 使用驱动 cell 放置坐标（最精确）
  bus_net_driver:    310
  pin:                 6
  bus_net_route:       3
```

**输出**:
- `output/signal_location_map.csv` — 42,410 行 (signal_name, scope, width, x_um, y_um, source_type, cell_type)
- `output/signal_location_map.html` — Plotly scatter plot

**运行命令**:
```bash
python code/vcd_def_mapper.py \
    --vcd des_demo/vcd/test.vcd \
    --def des_demo/db/des3.def \
    --output output/signal_location_map.csv \
    --html output/signal_location_map.html
```

---

## 待完成任务

### 1. 将物理坐标集成到选窗算法 (高优先)
- **目标**: 用物理坐标替代 VCD scope 层次做空间集中度分析
- `find_worst_window.py` 当前的 `build_scope_map()` 用 VCD scope 做模块级集中度
- 可用 `vcd_def_mapper.py` 的坐标做 **区域级集中度** (grid-based spatial concentration)
- 思路: 将芯片划分为 NxN 网格，计算每个窗口中 toggle 的空间分布集中度
- 公式: `σ_spatial = max(grid_toggle) / total_toggle` 或用 Gini 系数

### 2. 用 v20 数据重跑覆盖率分析
- `coverage_tier1.py` 需适配 v20 的报告路径（多一层 `PD_25C_dynamic_1/`）
- 重新计算 C₁, C_peak, C_layer, C_violation 指标

### 3. 修复 full_irdrop_v20.tcl
- 在 `set_rail_analysis_mode` 中加回 `-limit_number_of_steps false`
- 使其可以一次性跑完功耗 + Rail 全流程

### 4. 选窗验证 — 用选窗算法选出的窗口 vs 等分窗口
- 用 Phase-Aware 选出 worst window → vcd_slicer 切片 → 上传服务器 → Voltus 跑 Rail
- 与等分 5 窗口的 worst IR drop 对比，验证选窗精度

---

## 关键路径和文件

| 项目 | 路径 |
|------|------|
| VCD 源文件 | `des_demo/vcd/test.vcd` |
| DEF 文件 | `des_demo/db/des3.def` (91万行) |
| 物理映射输出 | `output/signal_location_map.csv` |
| Toggle JSONL | `output/test_toggles.jsonl` |
| Power 数据 (v20) | `db/power/avg_v20_winX/dynamic_{VDD,VSS}.ptiavg` |
| Rail 报告 (v20) | `db/rail_power_v20_winX/PD_25C_dynamic_1/Reports/` |
| v20 Rail-only 脚本 | `script/innovus/rerun_rail_v20_fix.tcl` ✅ |
| 覆盖率脚本 | `db/analyse/coverage_tier1.py` |
| 算法文档 | `docs/algorithm_worst_window.md` |

## 远程服务器
- SSH: `ssh -p 2223 myzhu@10.98.193.24` (key auth)
- Innovus v20.10, 项目路径: `/home/myzhu/data/des_demo/`
- 共享终端: `tmux attach -t shared`

## 时间窗口定义 (等分)
```
win1: 0ns     ~ 2370ns
win2: 2370ns  ~ 4740ns    ← worst IR drop (26mV)
win3: 4740ns  ~ 7110ns
win4: 7110ns  ~ 9480ns
win5: 9480ns  ~ 11850ns
```
VCD timescale: 10ps, 最后时间戳 #1185000
