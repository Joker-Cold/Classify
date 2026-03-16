# Verilog & SoC 设计 SKILL — 注意事项与最佳实践

> 适用场景：编写 RTL、设计 SoC 子系统、写 Testbench、做 Lint/综合前检查。  
> 使用本 SKILL 的时机：用户提到 Verilog、SystemVerilog、RTL、SoC、模块设计、仿真、综合、时序约束时。

---

## 一、Verilog 编码规范

### 1.1 文件与模块组织

- **一个文件只放一个模块**，文件名与模块名完全一致（`uart_tx.v` ↔ `module uart_tx`）
- 文件头必须包含：模块用途、作者、创建日期、最后修改日期、版本号
- 端口声明采用 **ANSI 风格**（Verilog-2001），避免旧式分离声明：

```verilog
// ✅ 推荐：ANSI 风格
module uart_tx #(
    parameter DATA_WIDTH = 8,
    parameter CLK_FREQ   = 50_000_000,
    parameter BAUD_RATE  = 115200
)(
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire [DATA_WIDTH-1:0] tx_data,
    input  wire                  tx_valid,
    output reg                   tx_ready,
    output reg                   tx_out
);
```

### 1.2 命名规范（必须严格执行）

| 类型 | 命名规则 | 示例 |
|------|----------|------|
| 模块名 | 小写+下划线 | `apb_slave`, `fifo_sync` |
| 端口/信号 | 小写+下划线 | `tx_data`, `rx_valid` |
| 低电平有效 | 后缀 `_n` | `rst_n`, `cs_n` |
| 寄存器 | 后缀 `_r` 或 `_reg` | `cnt_r`, `state_reg` |
| 组合逻辑 | 后缀 `_w` 或 `_nxt` | `sum_w`, `state_nxt` |
| Parameter | 全大写+下划线 | `DATA_WIDTH`, `FIFO_DEPTH` |
| Localparam | 全大写+下划线 | `ST_IDLE`, `ST_SEND` |
| Generate 块 | 有意义的标签 | `gen_fifo_inst` |
| 时钟 | 前缀 `clk_` | `clk_sys`, `clk_pix` |
| 复位 | 前缀 `rst_` | `rst_n`, `rst_por_n` |

### 1.3 always 块规则

- **组合逻辑**：用 `always @(*)` 或 `always_comb`，敏感列表不能手写（容易遗漏）
- **时序逻辑**：只用 **非阻塞赋值** `<=`，严禁在时序块里用 `=`
- **组合逻辑**：只用 **阻塞赋值** `=`，严禁在组合块里用 `<=`
- 同一个 `always` 块内不能混用阻塞和非阻塞赋值

```verilog
// ✅ 时序逻辑模板（同步复位）
always @(posedge clk) begin
    if (!rst_n) begin
        state_r <= ST_IDLE;
        cnt_r   <= '0;
    end else begin
        state_r <= state_nxt;
        cnt_r   <= cnt_nxt;
    end
end

// ✅ 组合逻辑模板
always @(*) begin
    state_nxt = state_r;   // 默认保持，防止 latch
    cnt_nxt   = cnt_r;
    case (state_r)
        ST_IDLE: if (start) state_nxt = ST_RUN;
        ST_RUN:  if (done)  state_nxt = ST_IDLE;
        default:             state_nxt = ST_IDLE;
    endcase
end
```

### 1.4 严禁事项（综合/仿真常见陷阱）

- ❌ **禁止** 在 `always @(*)` 中对信号有条件地赋值但不给默认值 → 产生 **Latch**
- ❌ **禁止** `initial` 块出现在综合代码中（仅 Testbench 允许）
- ❌ **禁止** 使用 `#delay` 延迟语句在 RTL 中（仅 Testbench）
- ❌ **禁止** 敏感列表写成 `always @(a or b)` 而漏掉信号
- ❌ **禁止** `case` 语句缺少 `default` 分支
- ❌ **禁止** 多驱动（同一信号被多个 `always` 或 `assign` 驱动）
- ❌ **禁止** 跨时钟域直接连线（必须加 CDC 同步器）
- ❌ **禁止** 组合逻辑回路（combinational loop）

---

## 二、SoC 设计注意事项

### 2.1 总线与接口

**AXI4 / AXI4-Lite 关键约束：**
- AWVALID / ARVALID 拉高后，主机不能在无 READY 时撤销（valid 不能提前撤）
- WDATA 和 AWADDR 可以乱序到达，从机必须能处理
- BRESP / RRESP 必须正确返回：`2'b00` = OKAY，`2'b10` = SLVERR
- 不能在 RVALID 时反压（RREADY 未知），主机必须能接收

**APB 关键约束：**
- SETUP 阶段 → ENABLE 阶段，严格两拍时序
- PSEL 和 PENABLE 不能同时在第一拍都拉高

**AHB-Lite：**
- 地址和控制信号在数据传输的上一拍给出（流水线特性）
- HRESP 需要两拍传输 ERROR 响应

### 2.2 时钟域设计（CDC）

**必须处理 CDC 的场景：**
- 任何跨时钟域的单 bit 信号 → 使用 **两级 FF 同步器**
- 跨时钟域的多 bit 数据 → 使用 **握手协议** 或 **异步 FIFO**
- 跨时钟域的脉冲信号 → 使用 **脉冲展宽 + 同步 + 脉冲再生**

```verilog
// ✅ 两级 FF 同步器模板
module cdc_sync #(parameter STAGES = 2) (
    input  wire clk_dst,
    input  wire rst_n,
    input  wire sig_src,
    output wire sig_dst
);
    reg [STAGES-1:0] sync_r;
    always @(posedge clk_dst or negedge rst_n) begin
        if (!rst_n) sync_r <= '0;
        else        sync_r <= {sync_r[STAGES-2:0], sig_src};
    end
    assign sig_dst = sync_r[STAGES-1];
endmodule
```

**CDC 常见错误：**
- ❌ 多 bit 信号直接连接到另一个时钟域（会采样到亚稳态组合）
- ❌ 用 `assign` 直接跨时钟域
- ❌ 两级同步器之间插入组合逻辑

### 2.3 复位设计

- 推荐使用 **异步复位、同步释放（async assert, sync deassert）**
- 复位释放必须与目标时钟同步，防止亚稳态

```verilog
// ✅ 同步释放复位模板
module rst_sync (
    input  wire clk,
    input  wire rst_async_n,   // 外部异步复位（低有效）
    output wire rst_sync_n     // 同步后的复位
);
    reg [1:0] sync_r;
    always @(posedge clk or negedge rst_async_n) begin
        if (!rst_async_n) sync_r <= 2'b00;
        else              sync_r <= {sync_r[0], 1'b1};
    end
    assign rst_sync_n = sync_r[1];
endmodule
```

### 2.4 FIFO 设计

| 类型 | 适用场景 | 关键注意 |
|------|----------|----------|
| 同步 FIFO | 同一时钟域 | 满/空标志需提前一拍（almost full/empty）|
| 异步 FIFO | 跨时钟域 | 读写指针必须用 **格雷码** 再同步 |

**异步 FIFO 核心要点：**
- 读写指针转换为格雷码后，再做两级 FF 同步
- 空/满判断在各自时钟域完成
- 深度必须是 2 的幂次

### 2.5 存储器接口

- SRAM 读操作有 1 拍延迟，读数据在下一拍有效（需流水线配合）
- 写使能（WEN）信号必须在地址/数据稳定后才有效
- ECC（错误纠正）：如果 SoC 对可靠性有要求，片上 SRAM 需加 SECDED ECC

---

## 三、状态机设计规范

### 推荐：三段式状态机

```verilog
// 第一段：状态寄存器
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) state_r <= ST_IDLE;
    else        state_r <= state_nxt;
end

// 第二段：次态逻辑（纯组合）
always @(*) begin
    state_nxt = state_r;  // 必须有默认值
    case (state_r)
        ST_IDLE: if (req)   state_nxt = ST_PROC;
        ST_PROC: if (done)  state_nxt = ST_DONE;
        ST_DONE:            state_nxt = ST_IDLE;
        default:            state_nxt = ST_IDLE;
    endcase
end

// 第三段：输出逻辑（可寄存或纯组合）
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        out_valid <= 1'b0;
    end else begin
        out_valid <= (state_r == ST_DONE);
    end
end
```

**为什么用三段式：**
- 次态逻辑（第二段）与输出逻辑（第三段）分离，可读性强
- 输出寄存器化，消除组合毛刺
- 综合工具更容易优化

---

## 四、参数化与可复用设计

```verilog
// ✅ 参数化模块模板
module sync_fifo #(
    parameter DATA_WIDTH = 8,
    parameter FIFO_DEPTH = 16,
    // 不要让用户手动设 ADDR_WIDTH，自动计算
    parameter ADDR_WIDTH = $clog2(FIFO_DEPTH)
)(
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire [DATA_WIDTH-1:0] wr_data,
    input  wire                  wr_en,
    input  wire                  rd_en,
    output reg  [DATA_WIDTH-1:0] rd_data,
    output wire                  full,
    output wire                  empty,
    output wire [ADDR_WIDTH:0]   data_cnt
);
```

**参数使用原则：**
- 用 `$clog2()` 自动计算位宽，不要硬编码
- 顶层用 `parameter`，内部常量用 `localparam`
- 关键参数加合法性检查（`generate if` 报错）

```verilog
// ✅ 参数合法性检查
generate
    if (FIFO_DEPTH < 2 || (FIFO_DEPTH & (FIFO_DEPTH-1)) != 0) begin
        // 深度必须是 2 的幂次且 >= 2
        $error("FIFO_DEPTH must be a power of 2 and >= 2");
    end
endgenerate
```

---

## 五、综合相关注意事项

### 5.1 综合友好编码

- **移位操作**：用 `>>` / `<<` 代替除法/乘法（综合器自动优化，但明确更好）
- **乘法**：明确标注是有符号还是无符号（`$signed(a) * $signed(b)`）
- **条件赋值**：三目运算符 `?:` 等价于 MUX，综合效果好
- **常数索引**：`wire [7:0] byte = data[8*i +: 8]` 使用 part-select，综合友好

### 5.2 容易导致综合问题的代码

```verilog
// ❌ 会产生 Latch（output_sig 在 b==0 时没有被赋值）
always @(*) begin
    if (b == 1) output_sig = a;
end

// ✅ 修正：给出默认值
always @(*) begin
    output_sig = 1'b0;    // 默认值
    if (b == 1) output_sig = a;
end
```

### 5.3 时序收敛技巧

- 关键路径上的大位宽加法/比较器考虑**流水线拆分**
- 寄存器输出直接连到下一级寄存器输入是最理想的路径
- 避免长扇出信号（一个寄存器驱动几百个门）——考虑插入 buffer 或复制寄存器
- 大型 MUX（>16 选 1）考虑用二级树形结构

---

## 六、Testbench 编写规范

### 6.1 Testbench 结构模板

```verilog
`timescale 1ns/1ps

module tb_xxx;

// =========================================
// 参数声明
// =========================================
localparam CLK_PERIOD = 10;   // 100MHz
localparam RST_CYCLES = 5;

// =========================================
// 信号声明
// =========================================
reg         clk;
reg         rst_n;
// ... 其他端口

// =========================================
// DUT 例化
// =========================================
xxx u_dut (
    .clk    (clk),
    .rst_n  (rst_n),
    // ...
);

// =========================================
// 时钟生成
// =========================================
initial clk = 0;
always #(CLK_PERIOD/2) clk = ~clk;

// =========================================
// VCD 导出（用于 Voltus 等功耗分析）
// =========================================
initial begin
    $dumpfile("sim_output.vcd");
    $dumpvars(0, tb_xxx);
end

// =========================================
// 复位序列
// =========================================
initial begin
    rst_n = 1'b0;
    // 其他信号初始化
    repeat(RST_CYCLES) @(posedge clk);
    @(negedge clk);
    rst_n = 1'b1;
end

// =========================================
// 测试激励
// =========================================
initial begin
    // 等复位完成
    @(posedge rst_n);
    @(posedge clk);

    // --- 阶段1：正常功能测试 ---
    // ...

    // --- 阶段2：边界条件测试 ---
    // ...

    // --- 阶段3：高切换活动（worst-case power）---
    // ...

    #(CLK_PERIOD * 10);
    $display("All tests passed!");
    $finish;
end

// =========================================
// 自动检查（assertions）
// =========================================
always @(posedge clk) begin
    if (rst_n) begin
        // 示例：valid 和 ready 同时有效时，数据不能为 X
        if (out_valid && out_ready)
            assert (^out_data !== 1'bx)
            else $error("Data has X when handshake occurs!");
    end
end

endmodule
```

### 6.2 Testbench 常见错误

- ❌ 信号没有初始值，导致仿真开始时全是 X
- ❌ 用 `=` 驱动时序逻辑相关信号（应配合时钟沿）
- ❌ `$finish` 放在 `always` 块里导致无法结束
- ❌ 没有超时机制（DUT 死锁时仿真跑无限长时间）

```verilog
// ✅ 超时保护
initial begin
    #(CLK_PERIOD * 100000);
    $error("TIMEOUT: Simulation exceeded max cycles");
    $finish;
end
```

---

## 七、SoC 集成检查清单

在集成多个 IP 之前，逐项确认：

### 接口连接
- [ ] 所有端口信号都已连接，无悬空（`unconnected`）端口
- [ ] 位宽匹配，无隐式截断（宽连窄会丢位）
- [ ] 时钟域映射正确，跨域信号有 CDC 处理

### 复位网络
- [ ] 所有模块的复位来源一致（统一复位树）
- [ ] 复位释放有同步处理
- [ ] 上电复位时序满足所有 IP 的要求

### 时钟网络
- [ ] 时钟分频/倍频由专用时钟模块（PLL/MMCM）产生
- [ ] 不使用组合逻辑产生时钟（门控时钟需用专用 ICG cell）
- [ ] 时钟约束（SDC/XDC）覆盖所有时钟域

### 地址映射
- [ ] 各 IP 的地址空间无重叠
- [ ] 地址解码逻辑覆盖全部地址范围，有默认响应
- [ ] 总线宽度、大小端（endianness）一致

### 中断系统
- [ ] 中断信号的极性（高/低有效）与中断控制器匹配
- [ ] 中断清除机制已实现（防止中断锁死）

### 仿真与综合
- [ ] Lint 检查无 Warning（至少无 error 级别）
- [ ] 所有 `reg` 类型端口在复位时有确定值
- [ ] 综合后门级网表已做 STA，时序收敛

---

## 八、Vivado 特定注意事项

- **IP 核时序约束**：Vivado IP 生成的 XCI 文件自带约束，不要在顶层 XDC 重复约束
- **BUFG 数量限制**：7 系列最多 32 个 BUFG，UltraScale 更多但也有限
- **Block RAM 推断**：综合器自动推断 BRAM，但需满足特定写优先/读优先模式
- **DSP 推断**：乘法器和 MAC 结构尽量让综合器自动推断 DSP48，不要手工例化（除非必要）
- **VCD 导出设置**：在 Simulation Settings → Simulation → `xsim.simulate.xsim.more_options` 中加 `-wdb` 选项；或直接在 TB 中用 `$dumpfile`/`$dumpvars`

---

## 九、给 Claude Code 的额外提示

当让 Claude Code 写或修改 Verilog 时，在提示词中附加：

```
编写规范要求：
1. 遵循三段式状态机结构
2. 所有 always 块必须有明确的默认赋值，禁止生成 Latch
3. 时序逻辑只用非阻塞赋值（<=），组合逻辑只用阻塞赋值（=）
4. 跨时钟域信号必须加两级 FF 同步器
5. case 语句必须有 default 分支
6. 参数化设计，位宽用 $clog2() 自动计算
7. 端口声明用 ANSI 风格
8. 信号命名：低电平有效后缀 _n，寄存器后缀 _r，次态信号后缀 _nxt
```
