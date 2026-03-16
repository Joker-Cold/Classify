// =============================================================================
// File    : gpio_ctrl.v
// Module  : gpio_ctrl
// Purpose : 16-bit GPIO controller with direction control and input
//           synchroniser (2-stage FF).  AHB-mapped via internal peripheral bus.
//
// Register Map (byte offset, word access):
//   0x00 : GPIO_OUT  — output data register [15:0]   (R/W)
//   0x04 : GPIO_IN   — input  data register [15:0]   (R, reflects gpio_in_i)
//   0x08 : GPIO_DIR  — direction register   [15:0]   (R/W)
//                      bit=1 → output, bit=0 → input (default all input)
//
// gpio_out_o is driven by GPIO_OUT masked by GPIO_DIR.
// gpio_in_i  is double-synchronised before being latched into GPIO_IN.
//
// Author  : Generated for VCD power analysis project
// Date    : 2026-03-12
// Version : 1.0
// =============================================================================

`timescale 1ns / 1ps

module gpio_ctrl (
    input  wire        clk,
    input  wire        rst_n,

    // Internal peripheral bus
    input  wire        pvalid_i,
    input  wire        pwrite_i,
    input  wire [7:0]  paddr_i,
    input  wire [31:0] pwdata_i,
    output wire [31:0] prdata_o,

    // Physical GPIO
    input  wire [15:0] gpio_in_i,
    output wire [15:0] gpio_out_o
);

    // =========================================================================
    // Registers
    // =========================================================================
    reg [15:0] gpio_out_r;   // output data register
    reg [15:0] gpio_dir_r;   // direction: 1=output, 0=input

    // =========================================================================
    // Segment 1: Input synchroniser (2-stage FF, prevents metastability)
    // =========================================================================
    reg [15:0] gpio_sync1_r;
    reg [15:0] gpio_sync2_r;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            gpio_sync1_r <= 16'h0;
            gpio_sync2_r <= 16'h0;
        end else begin
            gpio_sync1_r <= gpio_in_i;
            gpio_sync2_r <= gpio_sync1_r;
        end
    end

    // =========================================================================
    // Segment 2: Register writes (sequential)
    // =========================================================================
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            gpio_out_r <= 16'h0;
            gpio_dir_r <= 16'h0;
        end else if (pvalid_i && pwrite_i) begin
            case (paddr_i[3:2])
                2'b00: gpio_out_r <= pwdata_i[15:0];   // GPIO_OUT
                2'b10: gpio_dir_r <= pwdata_i[15:0];   // GPIO_DIR
                default: ;  // 0x04 is read-only; other offsets ignored
            endcase
        end
    end

    // =========================================================================
    // Output: drive only direction=output pins
    // =========================================================================
    assign gpio_out_o = gpio_out_r & gpio_dir_r;

    // =========================================================================
    // Read data mux (combinatorial)
    // =========================================================================
    reg [31:0] prdata_w;

    always @(*) begin
        prdata_w = 32'h0;   // default prevents latch
        case (paddr_i[3:2])
            2'b00:   prdata_w = {16'h0, gpio_out_r};
            2'b01:   prdata_w = {16'h0, gpio_sync2_r};
            2'b10:   prdata_w = {16'h0, gpio_dir_r};
            default: prdata_w = 32'h0;
        endcase
    end

    assign prdata_o = prdata_w;

endmodule
