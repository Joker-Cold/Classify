// =============================================================================
// File    : sram_ctrl.v
// Module  : sram_ctrl
// Purpose : Internal SRAM controller with byte-lane enables.
//           Models a synchronous SRAM: write is same-cycle, read has
//           1-clock latency (data valid the cycle after ren assertion).
//           Exposes an 18-bit address port so it can be driven directly
//           by the testbench (simulating CPU/DMA SRAM access).
//
// Memory : DEPTH x 32-bit words (default 1024 = 4 KB)
//
// Author  : Generated for VCD power analysis project
// Date    : 2026-03-12
// Version : 1.0
// =============================================================================

`timescale 1ns / 1ps

module sram_ctrl #(
    parameter DEPTH = 1024                        // number of 32-bit words
)(
    input  wire        clk,
    input  wire        rst_n,

    // External SRAM port (driven by testbench / CPU / DMA)
    input  wire [17:0] sram_addr_i,
    input  wire [31:0] sram_wdata_i,
    output reg  [31:0] sram_rdata_o,
    input  wire        sram_wen_i,               // write enable (active high)
    input  wire        sram_ren_i,               // read  enable (active high)
    input  wire [3:0]  sram_ben_i                // byte enables [3]=MSB, [0]=LSB
);

    localparam ADDR_W = $clog2(DEPTH);           // address bits needed

    // =========================================================================
    // Internal memory array
    // =========================================================================
    reg [31:0] mem_r [0:DEPTH-1];

    // =========================================================================
    // Write port — byte-lane enabled, synchronous
    // =========================================================================
    always @(posedge clk) begin
        if (sram_wen_i) begin
            if (sram_ben_i[0]) mem_r[sram_addr_i[ADDR_W-1:0]][7:0]   <= sram_wdata_i[7:0];
            if (sram_ben_i[1]) mem_r[sram_addr_i[ADDR_W-1:0]][15:8]  <= sram_wdata_i[15:8];
            if (sram_ben_i[2]) mem_r[sram_addr_i[ADDR_W-1:0]][23:16] <= sram_wdata_i[23:16];
            if (sram_ben_i[3]) mem_r[sram_addr_i[ADDR_W-1:0]][31:24] <= sram_wdata_i[31:24];
        end
    end

    // =========================================================================
    // Read port — registered output (1-cycle latency), reset to 0
    // =========================================================================
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            sram_rdata_o <= 32'h0;
        end else begin
            if (sram_ren_i)
                sram_rdata_o <= mem_r[sram_addr_i[ADDR_W-1:0]];
        end
    end

endmodule
