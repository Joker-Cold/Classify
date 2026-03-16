// =============================================================================
// File    : soc_top.v
// Module  : soc_top
// Purpose : SoC top-level integration.  Instantiates all sub-IPs and wires
//           them together via an internal peripheral bus.
//           Port list EXACTLY matches gen_VCD.v testbench (tb_top).
//           Replaces the behavioural stub at the bottom of gen_VCD.v.
//
// Sub-modules (one file each):
//   ahb_slave.v  — AHB-Lite protocol handler + address decoder
//   sram_ctrl.v  — Synchronous SRAM controller with byte enables
//   gpio_ctrl.v  — 16-bit GPIO with direction control + input sync
//   uart_ctrl.v  — UART 8N1 TX/RX with parameterisable baud rate
//   spi_master.v — SPI mode-0 8-bit master with configurable clock div
//   irq_ctrl.v   — 8-channel sticky interrupt controller (W1C)
//   pwr_ctrl.v   — Power mode tracker + sleep-time counter
//
// Internal address map (haddr[11:8]):
//   4'h0 → reg_file  (16 × 32-bit config registers, inline below)
//   4'h1 → gpio_ctrl
//   4'h2 → uart_ctrl
//   4'h4 → irq_ctrl
//   4'h5 → pwr_ctrl
//   4'hF → spi_master  (0x0000_0F00 matches testbench Phase-2 SPI write)
//
// Author  : Generated for VCD power analysis project
// Date    : 2026-03-12
// Version : 1.0
// =============================================================================

`timescale 1ns / 1ps

module soc_top #(
    parameter CLK_FREQ  = 100_000_000,   // system clock frequency (Hz)
    parameter BAUD_RATE = 115_200,       // UART baud rate
    parameter SRAM_DEPTH = 1024          // SRAM words (4 KB default)
)(
    input  wire        clk,
    input  wire        rst_n,

    // AHB-Lite slave interface (CPU transactions driven by testbench)
    input  wire [31:0] haddr,
    input  wire [1:0]  htrans,
    input  wire        hwrite,
    input  wire [2:0]  hsize,
    input  wire [31:0] hwdata,
    output wire [31:0] hrdata,
    output wire        hready,
    output wire        hresp,

    // Dedicated SRAM port (DMA / CPU direct — driven by testbench)
    input  wire [17:0] sram_addr,
    input  wire [31:0] sram_wdata,
    output wire [31:0] sram_rdata,
    input  wire        sram_wen,
    input  wire        sram_ren,
    input  wire [3:0]  sram_ben,

    // GPIO
    input  wire [15:0] gpio_in,
    output wire [15:0] gpio_out,

    // UART
    input  wire        uart_rx,
    output wire        uart_tx,

    // SPI master
    input  wire        spi_miso,
    output wire        spi_mosi,
    output wire        spi_sclk,
    output wire        spi_cs_n,

    // External interrupts
    input  wire [7:0]  irq,

    // Power mode control (driven by testbench)
    input  wire [1:0]  pwr_mode
);

    // =========================================================================
    // Internal peripheral bus wires
    // =========================================================================
    wire [7:0]  paddr_w;
    wire [31:0] pwdata_w;
    wire        pwrite_w;
    wire        pvalid_w;
    wire        sel_reg_w, sel_gpio_w, sel_uart_w, sel_spi_w, sel_irq_w, sel_pwr_w;

    wire [31:0] prdata_reg_w;
    wire [31:0] prdata_gpio_w;
    wire [31:0] prdata_uart_w;
    wire [31:0] prdata_spi_w;
    wire [31:0] prdata_irq_w;
    wire [31:0] prdata_pwr_w;

    // =========================================================================
    // AHB Slave + Address Decoder
    // =========================================================================
    ahb_slave u_ahb_slave (
        .clk           (clk),
        .rst_n         (rst_n),
        .haddr_i       (haddr),
        .htrans_i      (htrans),
        .hwrite_i      (hwrite),
        .hsize_i       (hsize),
        .hwdata_i      (hwdata),
        .hrdata_o      (hrdata),
        .hready_o      (hready),
        .hresp_o       (hresp),
        .paddr_o       (paddr_w),
        .pwdata_o      (pwdata_w),
        .pwrite_o      (pwrite_w),
        .pvalid_o      (pvalid_w),
        .sel_reg_o     (sel_reg_w),
        .sel_gpio_o    (sel_gpio_w),
        .sel_uart_o    (sel_uart_w),
        .sel_spi_o     (sel_spi_w),
        .sel_irq_o     (sel_irq_w),
        .sel_pwr_o     (sel_pwr_w),
        .prdata_reg_i  (prdata_reg_w),
        .prdata_gpio_i (prdata_gpio_w),
        .prdata_uart_i (prdata_uart_w),
        .prdata_spi_i  (prdata_spi_w),
        .prdata_irq_i  (prdata_irq_w),
        .prdata_pwr_i  (prdata_pwr_w)
    );

    // =========================================================================
    // Config Register File (16 × 32-bit, inline in soc_top)
    // AHB address 0x000 – 0x03F (haddr[11:8] == 4'h0)
    // =========================================================================
    reg [31:0] reg_r [0:15];
    integer    ri;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            for (ri = 0; ri < 16; ri = ri + 1)
                reg_r[ri] <= 32'h0;
        end else begin
            if (pvalid_w && pwrite_w && sel_reg_w)
                reg_r[paddr_w[5:2]] <= pwdata_w;
        end
    end

    // Combinatorial read (valid in same clock as pvalid)
    assign prdata_reg_w = reg_r[paddr_w[5:2]];

    // =========================================================================
    // SRAM Controller
    // =========================================================================
    sram_ctrl #(
        .DEPTH (SRAM_DEPTH)
    ) u_sram_ctrl (
        .clk          (clk),
        .rst_n        (rst_n),
        .sram_addr_i  (sram_addr),
        .sram_wdata_i (sram_wdata),
        .sram_rdata_o (sram_rdata),
        .sram_wen_i   (sram_wen),
        .sram_ren_i   (sram_ren),
        .sram_ben_i   (sram_ben)
    );

    // =========================================================================
    // GPIO Controller
    // =========================================================================
    gpio_ctrl u_gpio_ctrl (
        .clk        (clk),
        .rst_n      (rst_n),
        .pvalid_i   (pvalid_w & sel_gpio_w),
        .pwrite_i   (pwrite_w),
        .paddr_i    (paddr_w),
        .pwdata_i   (pwdata_w),
        .prdata_o   (prdata_gpio_w),
        .gpio_in_i  (gpio_in),
        .gpio_out_o (gpio_out)
    );

    // =========================================================================
    // UART Controller
    // =========================================================================
    uart_ctrl #(
        .CLK_FREQ  (CLK_FREQ),
        .BAUD_RATE (BAUD_RATE)
    ) u_uart_ctrl (
        .clk       (clk),
        .rst_n     (rst_n),
        .pvalid_i  (pvalid_w & sel_uart_w),
        .pwrite_i  (pwrite_w),
        .paddr_i   (paddr_w),
        .pwdata_i  (pwdata_w),
        .prdata_o  (prdata_uart_w),
        .uart_rx_i (uart_rx),
        .uart_tx_o (uart_tx)
    );

    // =========================================================================
    // SPI Master
    // =========================================================================
    spi_master u_spi_master (
        .clk        (clk),
        .rst_n      (rst_n),
        .pvalid_i   (pvalid_w & sel_spi_w),
        .pwrite_i   (pwrite_w),
        .paddr_i    (paddr_w),
        .pwdata_i   (pwdata_w),
        .prdata_o   (prdata_spi_w),
        .spi_miso_i (spi_miso),
        .spi_mosi_o (spi_mosi),
        .spi_sclk_o (spi_sclk),
        .spi_cs_n_o (spi_cs_n)
    );

    // =========================================================================
    // IRQ Controller
    // =========================================================================
    irq_ctrl u_irq_ctrl (
        .clk      (clk),
        .rst_n    (rst_n),
        .pvalid_i (pvalid_w & sel_irq_w),
        .pwrite_i (pwrite_w),
        .paddr_i  (paddr_w),
        .pwdata_i (pwdata_w),
        .prdata_o (prdata_irq_w),
        .irq_i    (irq)
    );

    // =========================================================================
    // Power Controller
    // =========================================================================
    pwr_ctrl u_pwr_ctrl (
        .clk        (clk),
        .rst_n      (rst_n),
        .pvalid_i   (pvalid_w & sel_pwr_w),
        .pwrite_i   (pwrite_w),
        .paddr_i    (paddr_w),
        .pwdata_i   (pwdata_w),
        .prdata_o   (prdata_pwr_w),
        .pwr_mode_i (pwr_mode)
    );

endmodule
