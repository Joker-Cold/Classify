// =============================================================================
// File    : pwr_ctrl.v
// Module  : pwr_ctrl
// Purpose : Power management controller.
//           Tracks the externally supplied pwr_mode signal, maintains a
//           sleep-time counter (counts cycles spent outside Normal mode),
//           and exposes wake-up event logic.
//
// Register Map (byte offset, word access):
//   0x00 : PWR_MODE    — latched pwr_mode from pin [1:0]  (read-only)
//                        2'b00=Normal, 2'b01=Sleep, 2'b10=DeepSleep
//   0x04 : PWR_SLPTIME — cumulative cycles in non-Normal mode [31:0] (R/W)
//   0x08 : PWR_CTRL    — software control bits [1:0]  (R/W)
//                        bit0 = force_wakeup  (write 1 to assert wake event)
//                        bit1 = clkgate_en    (enable downstream clock gating)
//
// Author  : Generated for VCD power analysis project
// Date    : 2026-03-12
// Version : 1.0
// =============================================================================

`timescale 1ns / 1ps

module pwr_ctrl (
    input  wire        clk,
    input  wire        rst_n,

    // Internal peripheral bus
    input  wire        pvalid_i,
    input  wire        pwrite_i,
    input  wire [7:0]  paddr_i,
    input  wire [31:0] pwdata_i,
    output wire [31:0] prdata_o,

    // External power mode control (driven by testbench)
    input  wire [1:0]  pwr_mode_i
);

    // =========================================================================
    // Registers
    // =========================================================================
    reg [1:0]  pwr_mode_r;      // latched mode
    reg [31:0] slp_time_r;      // sleep-time accumulator
    reg [1:0]  sw_ctrl_r;       // software control (bit0=force_wakeup, bit1=clkgate)

    // =========================================================================
    // Latch pwr_mode_i and accumulate sleep time
    // =========================================================================
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            pwr_mode_r <= 2'b00;
            slp_time_r <= 32'h0;
        end else begin
            pwr_mode_r <= pwr_mode_i;
            // Increment counter whenever not in Normal mode
            if (pwr_mode_i != 2'b00)
                slp_time_r <= slp_time_r + 32'h1;
            // AHB write to sleep-time counter resets or sets it
            if (pvalid_i && pwrite_i && (paddr_i[3:2] == 2'b01))
                slp_time_r <= pwdata_i;
        end
    end

    // =========================================================================
    // Software control register
    // =========================================================================
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            sw_ctrl_r <= 2'b00;
        else if (pvalid_i && pwrite_i && (paddr_i[3:2] == 2'b10))
            sw_ctrl_r <= pwdata_i[1:0];
    end

    // =========================================================================
    // Register read (combinatorial mux)
    // =========================================================================
    reg [31:0] prdata_w;

    always @(*) begin
        prdata_w = 32'h0;
        case (paddr_i[3:2])
            2'b00:   prdata_w = {30'h0, pwr_mode_r};   // PWR_MODE
            2'b01:   prdata_w = slp_time_r;             // PWR_SLPTIME
            2'b10:   prdata_w = {30'h0, sw_ctrl_r};    // PWR_CTRL
            default: prdata_w = 32'h0;
        endcase
    end

    assign prdata_o = prdata_w;

endmodule
