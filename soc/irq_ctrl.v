// =============================================================================
// File    : irq_ctrl.v
// Module  : irq_ctrl
// Purpose : 8-channel interrupt controller.
//           — Sticky-set: once an IRQ fires, the status bit stays set
//             until software clears it (write-1-to-clear, W1C).
//           — Per-channel enable mask: only enabled IRQs show in STATUS.
//           — Provides a combined IRQ output for CPU (if wired to int line).
//
// Register Map (byte offset, word access):
//   0x00 : IRQ_ENABLE  — per-channel enable mask [7:0]  (R/W, default 0xFF)
//   0x04 : IRQ_STATUS  — pending & enabled IRQs  [7:0]  (R / W1C to clear)
//   0x08 : IRQ_RAW     — raw IRQ input, no mask   [7:0]  (read-only)
//   0x0C : IRQ_PENDING — sticky pending (pre-mask)[7:0]  (R / W1C to clear)
//
// Author  : Generated for VCD power analysis project
// Date    : 2026-03-12
// Version : 1.0
// =============================================================================

`timescale 1ns / 1ps

module irq_ctrl (
    input  wire        clk,
    input  wire        rst_n,

    // Internal peripheral bus
    input  wire        pvalid_i,
    input  wire        pwrite_i,
    input  wire [7:0]  paddr_i,
    input  wire [31:0] pwdata_i,
    output wire [31:0] prdata_o,

    // External IRQ inputs
    input  wire [7:0]  irq_i
);

    // =========================================================================
    // Registers
    // =========================================================================
    reg [7:0] irq_enable_r;    // enable mask
    reg [7:0] irq_pending_r;   // sticky raw pending (set by irq_i, W1C)

    // =========================================================================
    // 2-stage input synchroniser for each IRQ line
    // =========================================================================
    reg [7:0] irq_sync1_r;
    reg [7:0] irq_sync2_r;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            irq_sync1_r <= 8'h0;
            irq_sync2_r <= 8'h0;
        end else begin
            irq_sync1_r <= irq_i;
            irq_sync2_r <= irq_sync1_r;
        end
    end

    // =========================================================================
    // IRQ enable register (R/W)
    // =========================================================================
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            irq_enable_r <= 8'hFF;   // default: all channels enabled
        else if (pvalid_i && pwrite_i && (paddr_i[3:2] == 2'b00))
            irq_enable_r <= pwdata_i[7:0];
    end

    // =========================================================================
    // Sticky pending register — set by IRQ level, cleared by W1C write
    // =========================================================================
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            irq_pending_r <= 8'h0;
        end else begin
            // Latch any newly asserted IRQs (level-triggered, sticky)
            irq_pending_r <= irq_pending_r | irq_sync2_r;
            // Write-1-to-clear: software writes 1 to bits it wants cleared
            if (pvalid_i && pwrite_i) begin
                case (paddr_i[3:2])
                    2'b01: irq_pending_r <= (irq_pending_r | irq_sync2_r)
                                           & ~pwdata_i[7:0];   // W1C STATUS
                    2'b11: irq_pending_r <= (irq_pending_r | irq_sync2_r)
                                           & ~pwdata_i[7:0];   // W1C PENDING
                    default: ;
                endcase
            end
        end
    end

    // =========================================================================
    // Masked status = pending AND enabled
    // =========================================================================
    wire [7:0] irq_status_w = irq_pending_r & irq_enable_r;

    // =========================================================================
    // Register read (combinatorial mux)
    // =========================================================================
    reg [31:0] prdata_w;

    always @(*) begin
        prdata_w = 32'h0;
        case (paddr_i[3:2])
            2'b00:   prdata_w = {24'h0, irq_enable_r};    // IRQ_ENABLE
            2'b01:   prdata_w = {24'h0, irq_status_w};    // IRQ_STATUS (masked)
            2'b10:   prdata_w = {24'h0, irq_sync2_r};     // IRQ_RAW
            2'b11:   prdata_w = {24'h0, irq_pending_r};   // IRQ_PENDING (raw sticky)
            default: prdata_w = 32'h0;
        endcase
    end

    assign prdata_o = prdata_w;

endmodule
