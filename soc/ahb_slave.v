// =============================================================================
// File    : ahb_slave.v
// Module  : ahb_slave
// Purpose : AHB-Lite slave protocol handler + address decoder.
//           Captures the address phase, generates internal peripheral bus
//           signals (pvalid/pwrite/paddr/pwdata/sel_xxx) in the data phase,
//           and muxes read data back onto hrdata.
//           hready is always 1 (zero-wait-state slave).
//
// Address Map (haddr[11:8]):
//   4'h0 : reg_file  (config registers, 0x000-0x0FF)
//   4'h1 : gpio_ctrl (0x100-0x1FF)
//   4'h2 : uart_ctrl (0x200-0x2FF)
//   4'h4 : irq_ctrl  (0x400-0x4FF)
//   4'h5 : pwr_ctrl  (0x500-0x5FF)
//   4'hF : spi_master(0xF00-0xFFF)  -- matches testbench write to 0x0000_0F00
//
// Author  : Generated for VCD power analysis project
// Date    : 2026-03-12
// Version : 1.0
// =============================================================================

`timescale 1ns / 1ps

module ahb_slave (
    input  wire        clk,
    input  wire        rst_n,

    // AHB-Lite slave ports
    input  wire [31:0] haddr_i,
    input  wire [1:0]  htrans_i,   // IDLE=2'b00, NONSEQ=2'b10, SEQ=2'b11
    input  wire        hwrite_i,
    input  wire [2:0]  hsize_i,
    input  wire [31:0] hwdata_i,
    output wire [31:0] hrdata_o,
    output wire        hready_o,
    output wire        hresp_o,

    // Peripheral bus outputs (data phase, 1 cycle after address phase)
    output wire [7:0]  paddr_o,    // byte offset within peripheral block
    output wire [31:0] pwdata_o,   // write data (= hwdata_i)
    output wire        pwrite_o,   // 1 = write, 0 = read
    output wire        pvalid_o,   // 1 = active transfer this cycle

    // Peripheral select strobes (combinatorial from registered address)
    output wire        sel_reg_o,
    output wire        sel_gpio_o,
    output wire        sel_uart_o,
    output wire        sel_spi_o,
    output wire        sel_irq_o,
    output wire        sel_pwr_o,

    // Read data inputs from each peripheral (combinatorial)
    input  wire [31:0] prdata_reg_i,
    input  wire [31:0] prdata_gpio_i,
    input  wire [31:0] prdata_uart_i,
    input  wire [31:0] prdata_spi_i,
    input  wire [31:0] prdata_irq_i,
    input  wire [31:0] prdata_pwr_i
);

    // =========================================================================
    // AHB always responds OKAY, no wait states
    // =========================================================================
    assign hready_o = 1'b1;
    assign hresp_o  = 1'b0;

    // =========================================================================
    // Segment 1: Address-phase capture registers
    // =========================================================================
    reg [31:0] haddr_r;
    reg        hwrite_r;
    reg        transfer_r;   // 1 when an active transfer was in progress

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            haddr_r    <= 32'h0;
            hwrite_r   <= 1'b0;
            transfer_r <= 1'b0;
        end else begin
            haddr_r    <= haddr_i;
            hwrite_r   <= hwrite_i;
            transfer_r <= htrans_i[1];   // NONSEQ or SEQ
        end
    end

    // =========================================================================
    // Peripheral bus — data phase signals (combinatorial from registered addr)
    // =========================================================================
    assign pvalid_o = transfer_r;
    assign pwrite_o = hwrite_r;
    assign paddr_o  = haddr_r[7:0];
    assign pwdata_o = hwdata_i;          // hwdata valid in data phase

    // =========================================================================
    // Address decode (using registered address → data phase)
    // =========================================================================
    assign sel_reg_o  = (haddr_r[11:8] == 4'h0) & transfer_r;
    assign sel_gpio_o = (haddr_r[11:8] == 4'h1) & transfer_r;
    assign sel_uart_o = (haddr_r[11:8] == 4'h2) & transfer_r;
    assign sel_irq_o  = (haddr_r[11:8] == 4'h4) & transfer_r;
    assign sel_pwr_o  = (haddr_r[11:8] == 4'h5) & transfer_r;
    assign sel_spi_o  = (haddr_r[11:8] == 4'hF) & transfer_r;

    // =========================================================================
    // Read data mux (combinatorial — peripherals must present data within 1 cycle)
    // =========================================================================
    reg [31:0] hrdata_w;

    always @(*) begin
        hrdata_w = 32'h0;   // default: no peripheral selected
        case (haddr_r[11:8])
            4'h0:    hrdata_w = prdata_reg_i;
            4'h1:    hrdata_w = prdata_gpio_i;
            4'h2:    hrdata_w = prdata_uart_i;
            4'h4:    hrdata_w = prdata_irq_i;
            4'h5:    hrdata_w = prdata_pwr_i;
            4'hF:    hrdata_w = prdata_spi_i;
            default: hrdata_w = 32'h0;
        endcase
    end

    assign hrdata_o = hrdata_w;

endmodule
