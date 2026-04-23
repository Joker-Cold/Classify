# test_sim_output_v2 — ISPD2012 长仿真 Voltus 验证

> v1 仿真时长仅 ~200ns (200 vectors × 0.9ns clock), 窗口切分无意义。
> v2 对齐 des_demo 体量: **~12,000ns**, timescale 10ps。

## 电路参数

| 电路 | 时钟周期 | 向量数 | 仿真时长 | instances |
|------|---------|--------|---------|-----------|
| DMA_slow | 900ps | 13,333 | 12,000ns | 2,903 |
| des_perf_slow | 900ps | 13,333 | 12,000ns | 49,323 |
| vga_lcd_slow | 700ps | 17,142 | 12,000ns | 38,641 |
| leon3mp_slow | 1,800ps | 6,666 | 12,000ns | ~650K |

对比 des_demo: 50ns clock × 237 vectors = 11,850ns。

---

## 目录结构

```
test_sim_output_v2/
├── README.md
├── scripts/                      ← 共享工具脚本
│   ├── gen_testbench.py          生成 testbench (支持 --timescale-ps)
│   ├── gen_cell_models.py        .lib → Verilog 行为模型
│   ├── gen_contest_lef.py        生成 contest cell LEF
│   ├── gen_all.sh                一键生成全部 testbench + cell 模型
│   ├── run_vcs.sh                VCS 门级仿真 (timescale=10ps)
│   ├── contest.lef               ASAP7 tech LEF (预生成)
│   └── contest_cells.lef         Contest cell LEF (预生成)
├── lib/                          ← cell 行为模型 (需在远程服务器生成)
│   └── contest_cells.v           gen_cell_models.py 输出
├── {circuit}/
│   ├── testbench/tb_{circuit}.v  已生成 (v2 long-sim)
│   ├── src/                      网表+DEF+SDC (从 test_circuit 上传)
│   ├── vcd/                      VCS 仿真输出
│   │   └── sim.vcd               完整 VCD (~12000ns)
│   ├── script/innovus/           Innovus/Voltus TCL 脚本
│   │   ├── pr_flow.tcl           P&R 流程
│   │   ├── voltus_full.tcl       Full VCD → IR drop
│   │   ├── voltus_compressed.tcl 压缩 VCD → IR drop
│   │   ├── voltus_hotspot.tcl    参数化 hotspot sweep
│   │   ├── contest.mmmc          MMMC 配置
│   │   └── ring_pads_*.ppl       Pad 文件
│   ├── sim_data/                 Voltus 输出 (远程生成)
│   └── analysis/                 本地分析结果
```

---

## 操作流程

### Phase 0: 准备 (本地, 已完成)

```bash
# Testbench 已预生成在 {circuit}/testbench/tb_{circuit}.v
# 如需重新生成:
./scripts/gen_all.sh
```

### Phase 1: 上传到 EDA 服务器

```bash
# SSH: ssh -p 2223 myzhu@10.98.193.24
REMOTE="myzhu@10.98.193.24"
REMOTE_DIR="/home/myzhu/data/test_sim_output_v2"

# 上传整个目录
scp -P 2223 -r test_sim_output_v2/ $REMOTE:~/data/

# 或增量上传 testbench
for c in DMA_slow des_perf_slow vga_lcd_slow leon3mp_slow; do
  scp -P 2223 $c/testbench/tb_${c}.v $REMOTE:$REMOTE_DIR/$c/testbench/
done
```

### Phase 2: 上传源文件 (仅首次)

远程服务器上 ISPD 源文件放在 `{circuit}/src/`:

```bash
# 在远程服务器执行
ISPD_LOCAL=~/data/test_circuit/ispd2012  # 如果已有
for c in DMA_slow des_perf_slow vga_lcd_slow leon3mp_slow; do
  cp $ISPD_LOCAL/$c/$c.v    ~/data/test_sim_output_v2/$c/src/
  cp $ISPD_LOCAL/$c/$c.def  ~/data/test_sim_output_v2/$c/src/
  cp $ISPD_LOCAL/$c/$c.sdc  ~/data/test_sim_output_v2/$c/src/
  cp $ISPD_LOCAL/$c/$c.spef ~/data/test_sim_output_v2/$c/src/
done
```

### Phase 3: 生成 cell 模型 + VCS 仿真 (远程)

```bash
# 在远程服务器:
cd ~/data/test_sim_output_v2

# Step 1: 生成 cell 行为模型 (只需一次)
python3 scripts/gen_cell_models.py \
    --lib ~/data/test_circuit/ispd2012/lib/contest.lib \
    --output lib/contest_cells.v

# Step 2: VCS 仿真
set +u; source /etc/profile; set -u   # ← 重要: 防 XDG_DATA_DIRS 未绑定
export PATH=/data/Installed_tools/cadence/VCS/bin:$PATH  # 确保 vcs 可用

for c in DMA_slow des_perf_slow vga_lcd_slow leon3mp_slow; do
  echo "=== $c ==="
  bash scripts/run_vcs.sh $c
done
```

**预期 VCD 大小**:
- v1 (200 vectors): DMA_slow 5.8M, des_perf_slow ~62M
- v2 (13K+ vectors): 预计 **50-60× 倍** (DMA ~350M, des_perf ~3.7G)
- 若 VCD 过大, 考虑降低向量数或只 dump 部分层次

### Phase 4: 更新 Voltus 脚本中的 VCD 时间范围

**关键**: `voltus_full.tcl` 中 `read_activity_file -end` 必须匹配实际 VCD 时长!

```bash
# 获取实际 VCD 最大时间戳 (在远程服务器)
for c in DMA_slow des_perf_slow vga_lcd_slow leon3mp_slow; do
  END=$(grep '^#' ~/data/test_sim_output_v2/$c/vcd/sim.vcd | tail -1 | tr -d '#')
  echo "$c: end = ${END} ticks (timescale=10ps → $(echo "$END * 10" | bc)ps)"
done
```

然后修改各电路的 `voltus_full.tcl`:
```tcl
# 替换 -end 值 (单位: ps = ticks × 10)
read_activity_file -format VCD $VCD_FILE \
    -scope $VCD_SCOPE \
    -start 0ps -end ${END_PS}ps    ;# ← 改为实际值
```

### Phase 5: Innovus P&R + Voltus (远程)

```bash
# 环境变量 (非交互 shell 必须)
set +u; source /etc/profile; set -u
export CDS_BASE=/data/Installed_tools/cadence
export INNOVUS201_HOME=$CDS_BASE/INNOVUS201
export CDS_LIC_FILE="20030@hzhb-Super-Server:$CDS_BASE/license/cadence.dat:$CDS_BASE/license/cadence2.dat:$CDS_BASE/license/cadence23.lic:$CDS_BASE/license/licence.dat"
export PATH=$INNOVUS201_HOME/tools/bin:$PATH
export LD_PRELOAD=$INNOVUS201_HOME/tools.lnx86/lib/64bit/libstdc++.so.6

CIRCUIT=DMA_slow
cd ~/data/test_sim_output_v2/$CIRCUIT

# P&R (如果之前没跑过; v1 的 pg_lib_full 不能复用, 因为设计相同但输出路径不同)
$INNOVUS201_HOME/tools/bin/innovus -no_gui -log pr_flow \
    -execute "source script/innovus/pr_flow.tcl; exit"

# Full VCD Voltus
$INNOVUS201_HOME/tools/bin/innovus -no_gui -log voltus_full \
    -execute "source script/innovus/voltus_full.tcl; exit"
```

### Phase 6: 下载结果到本地

```bash
# 关键: tar 加 -h 解引用 Reports/ 软链接
ssh -p 2223 $REMOTE "cd ~/data/test_sim_output_v2/$CIRCUIT && tar chf - sim_data/" \
    | tar xf - -C test_sim_output_v2/$CIRCUIT/

# 注意: scp 不展开远程 brace {a,b}, 用 tar 或逐个 scp
```

---

## v1 踩坑经验汇总

### VCD 相关

| 坑 | 症状 | 解决 |
|----|------|------|
| **Windows CRLF** | Voltus `VOLTUS_POWR-1735 line 3 col 6 syntax error` | Python `open(path,'w',newline='\n')`; 应急 `sed -i 's/\r$//' <vcd>` |
| **VCD 时间范围** | `VOLTUS_POWR-2149` | `read_activity_file` 必须带 `-start 0ps -end ${END}ps` |
| **VCD 过大** | 磁盘 100% `ENOSPC (errno 28)` | 及时清理 `sim_data/t*/power/`, 完成后保留 `rail/.../Reports/` |

### Innovus/Voltus 相关

| 坑 | 症状 | 解决 |
|----|------|------|
| **locale crash** | optDesign 崩溃 | `wrapper.tcl` + `LD_PRELOAD` 绕过 |
| **ccopt 无 buffer** | ccopt 报错退出 | `suppressMessage` + `catch` |
| **IMPSYT-6692** | init 卡住 | `wrapper.tcl catch` 后手动 `defOut` |
| **ring_pads 生成失败** | gen_ring_pads 报错 | 手写 8-pad ppl 文件 (4角 M6 + 4边中点 M7, margin 6.24um) |
| **pg_lib_full 路径** | hotspot.tcl 找不到 | 检测 `script/` vs `script/innovus/` 两种布局 |

### 远程执行相关

| 坑 | 症状 | 解决 |
|----|------|------|
| **set -u + /etc/profile** | `XDG_DATA_DIRS: 未绑定的变量` | `set +u; source /etc/profile; set -u` |
| **scp brace 不展开** | `scp remote:{a,b}` 报错 | 用 `tar chf - \| tar xf -` 管道 |
| **innovus alias 覆盖 -log** | log 文件名不对 | 用全路径 `$INNOVUS201_HOME/tools/bin/innovus` |
| **nohup 进程随 ssh 断开** | 后台任务被杀 | `nohup ... & disown`; 或 `setsid` |

### 分析相关

| 坑 | 症状 | 解决 |
|----|------|------|
| **exponential ≠ traditional** | DMA 上两者重合, des_perf 上差 8.5pp | 不要基于单电路推广结论 |
| **logarithmic t≥0.8 崩溃** | J@10=0, 仅保留极少 instances | 该核在高阈值下过度裁剪 |
| **C_int > 100%** | 压缩 VCD IR drop 比 full 大 | 正常 (保守过估计), 不是 bug |

---

## 与 v1 的关键差异

| 维度 | v1 | v2 |
|------|----|----|
| timescale | 1ps | **10ps** |
| 向量数 | 200 | **6,666~17,142** |
| 仿真时长 | 140~360ns | **~12,000ns** |
| VCD 时间点 | ~429 | 预计 **~数万** |
| 选窗意义 | 窗口太少无法形成 phase | 有完整活跃相位 |
| 磁盘占用 | ~3.5G (4 电路) | 预计 **~50G+** (VCD 显著增大) |

---

## 复用文件来源

| 文件 | 来源 | 是否修改 |
|------|------|----------|
| `scripts/gen_testbench.py` | v1, 加了 `--timescale-ps` | 修改 |
| `scripts/gen_cell_models.py` | v1 原样 | 无 |
| `scripts/gen_contest_lef.py` | v1 原样 | 无 |
| `scripts/contest*.lef` | v1 原样 | 无 |
| `scripts/run_vcs.sh` | v1, `-timescale=10ps/10ps` | 修改 |
| `scripts/gen_all.sh` | 新写, 含各电路向量数 | 新 |
| `{circuit}/testbench/` | v1 `tb_*_long.v` 改名 | 新生成 |
| `{circuit}/script/innovus/*.tcl` | v1 原样复制 | **需改 -end 时间** |
| `{circuit}/script/innovus/*.mmmc` | v1 原样 | **需改远程路径** |
| `{circuit}/script/innovus/*.ppl` | v1 原样 | 无 |

---

## 远程服务器路径规划

```
~/data/test_sim_output_v2/
├── scripts/           ← 本地 scp 上传
├── lib/
│   └── contest_cells.v  ← 远程 gen_cell_models.py 生成
├── DMA_slow/
│   ├── src/{DMA_slow.v, .def, .sdc, .spef}  ← 从 test_circuit 复制
│   ├── testbench/tb_DMA_slow.v               ← 本地 scp 上传
│   ├── vcd/sim.vcd                           ← VCS 生成
│   └── script/innovus/                       ← 本地 scp 上传
│       └── contest.mmmc                      ← 需改 lib/sdc 路径为远程绝对路径
├── des_perf_slow/
│   └── (同上)
├── vga_lcd_slow/
│   └── (同上)
└── leon3mp_slow/
    └── (同上)
```

### contest.mmmc 远程路径模板

```tcl
# 需替换为实际远程路径:
create_library_set -name contest_libs \
    -timing [list /home/myzhu/data/test_sim_output_v2/lib/contest.lib]

create_rc_corner -name rc_typical \
    -T 25 \
    -qx_tech_file /home/myzhu/data/des_demo/db/des3.enc.dat/libs/mmmc/rc_typ_25/qrcTechFile_typ03_scaled4xV06

create_constraint_mode -name cm_func \
    -sdc_files [list /home/myzhu/data/test_sim_output_v2/{CIRCUIT}/src/{CIRCUIT}.sdc]
```
