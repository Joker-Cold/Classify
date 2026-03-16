// =============================================================================
// File    : spi_master.v
// Module  : spi_master
// Purpose : SPI master controller, mode 0 (CPOL=0 CPHA=0), 8-bit transfers.
//           Writing to the TX data register triggers a transfer.
//           SCLK = clk / (2 × (spi_div + 1))  — default div=3 → clk/8.
//           Three-segment FSM.
//
// Register Map (byte offset, word access):
//   0x00 : SPI_DATA   — write=load TX and start; read=last RX byte [7:0]
//   0x04 : SPI_CTRL   — bits[7:0]=spi_div (clock divider - 1), default 3
//   0x08 : SPI_STATUS — bit0=busy
//
// Trigger: ahb_write to offset 0x00 (i.e. paddr[3:2]==2'b00) while not busy.
// In testbench, this maps to: ahb_write(32'h0000_0F00, data, ...).
//
// Author  : Generated for VCD power analysis project
// Date    : 2026-03-12
// Version : 1.0
// =============================================================================

`timescale 1ns / 1ps

module spi_master (
    input  wire        clk,
    input  wire        rst_n,

    // Internal peripheral bus
    input  wire        pvalid_i,
    input  wire        pwrite_i,
    input  wire [7:0]  paddr_i,
    input  wire [31:0] pwdata_i,
    output wire [31:0] prdata_o,

    // Physical SPI
    input  wire        spi_miso_i,
    output wire        spi_mosi_o,
    output wire        spi_sclk_o,
    output wire        spi_cs_n_o
);

    // =========================================================================
    // Configurable clock divider register
    // =========================================================================
    reg [7:0]  spi_div_r;    // SCLK = clk / (2 × (spi_div_r + 1))

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            spi_div_r <= 8'd3;   // default: clk/8
        else if (pvalid_i && pwrite_i && (paddr_i[3:2] == 2'b01))
            spi_div_r <= pwdata_i[7:0];
    end

    // =========================================================================
    // State machine — SPI_IDLE / SPI_CS_SETUP / SPI_SHIFT / SPI_CS_HOLD
    // =========================================================================
    localparam SPI_IDLE     = 2'd0;
    localparam SPI_CS_SETUP = 2'd1;   // CS asserted, wait 1 half-period
    localparam SPI_SHIFT    = 2'd2;   // shift 8 bits
    localparam SPI_CS_HOLD  = 2'd3;   // CS holds low 1 half-period after last bit

    reg [1:0]  spi_state_r, spi_state_nxt;
    reg [7:0]  spi_div_cnt_r;    // counts 0..(spi_div_r)
    reg [7:0]  tx_shift_r;       // TX shift register
    reg [7:0]  rx_shift_r;       // RX shift register
    reg [7:0]  rx_data_r;        // captured RX byte
    reg [3:0]  bit_cnt_r;        // counts bit pairs: 0..15 (2 per bit: lo+hi sclk)
    reg        sclk_r;
    reg        cs_n_r;

    // Trigger: write to SPI_DATA while IDLE
    wire spi_start_w = pvalid_i && pwrite_i && (paddr_i[3:2] == 2'b00) &&
                       (spi_state_r == SPI_IDLE);
    // Half-period done (SCLK toggle point)
    wire half_done_w = (spi_div_cnt_r == spi_div_r);
    // All 16 half-periods completed (8 bits × 2 edges)
    wire shift_done_w = half_done_w && (bit_cnt_r == 4'd15);

    // ----- Segment 1: state register ----------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) spi_state_r <= SPI_IDLE;
        else        spi_state_r <= spi_state_nxt;
    end

    // ----- Segment 2: next-state logic (combinatorial) ----------------------
    always @(*) begin
        spi_state_nxt = spi_state_r;
        case (spi_state_r)
            SPI_IDLE:     if (spi_start_w)   spi_state_nxt = SPI_CS_SETUP;
            SPI_CS_SETUP: if (half_done_w)   spi_state_nxt = SPI_SHIFT;
            SPI_SHIFT:    if (shift_done_w)  spi_state_nxt = SPI_CS_HOLD;
            SPI_CS_HOLD:  if (half_done_w)   spi_state_nxt = SPI_IDLE;
            default:                         spi_state_nxt = SPI_IDLE;
        endcase
    end

    // ----- Segment 3: datapath registers (sequential) -----------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            spi_div_cnt_r <= 8'h0;
            tx_shift_r    <= 8'h0;
            rx_shift_r    <= 8'h0;
            rx_data_r     <= 8'h0;
            bit_cnt_r     <= 4'd0;
            sclk_r        <= 1'b0;
            cs_n_r        <= 1'b1;
        end else begin
            case (spi_state_r)
                SPI_IDLE: begin
                    sclk_r        <= 1'b0;
                    cs_n_r        <= 1'b1;
                    spi_div_cnt_r <= 8'h0;
                    bit_cnt_r     <= 4'd0;
                    if (spi_start_w)
                        tx_shift_r <= pwdata_i[7:0];
                end

                SPI_CS_SETUP: begin
                    cs_n_r <= 1'b0;   // assert CS
                    if (half_done_w)
                        spi_div_cnt_r <= 8'h0;
                    else
                        spi_div_cnt_r <= spi_div_cnt_r + 8'h1;
                end

                SPI_SHIFT: begin
                    if (half_done_w) begin
                        spi_div_cnt_r <= 8'h0;
                        bit_cnt_r     <= bit_cnt_r + 4'd1;
                        sclk_r        <= ~sclk_r;
                        if (!sclk_r) begin
                            // Rising edge: sample MISO into RX shift register
                            rx_shift_r <= {rx_shift_r[6:0], spi_miso_i};
                        end else begin
                            // Falling edge: shift TX to present next MOSI bit
                            tx_shift_r <= {tx_shift_r[6:0], 1'b0};
                        end
                        if (shift_done_w) begin
                            rx_data_r <= rx_shift_r;   // capture complete byte
                            sclk_r    <= 1'b0;
                        end
                    end else begin
                        spi_div_cnt_r <= spi_div_cnt_r + 8'h1;
                    end
                end

                SPI_CS_HOLD: begin
                    if (half_done_w) begin
                        cs_n_r        <= 1'b1;
                        spi_div_cnt_r <= 8'h0;
                    end else begin
                        spi_div_cnt_r <= spi_div_cnt_r + 8'h1;
                    end
                end

                default: begin
                    sclk_r <= 1'b0;
                    cs_n_r <= 1'b1;
                end
            endcase
        end
    end

    // =========================================================================
    // Output assignments
    // =========================================================================
    assign spi_mosi_o = tx_shift_r[7];   // MSB first
    assign spi_sclk_o = sclk_r;
    assign spi_cs_n_o = cs_n_r;

    // =========================================================================
    // Register read (combinatorial mux)
    // =========================================================================
    reg [31:0] prdata_w;

    always @(*) begin
        prdata_w = 32'h0;
        case (paddr_i[3:2])
            2'b00:   prdata_w = {24'h0, rx_data_r};            // RX data
            2'b01:   prdata_w = {24'h0, spi_div_r};            // clock div
            2'b10:   prdata_w = {31'h0, (spi_state_r != SPI_IDLE)}; // busy
            default: prdata_w = 32'h0;
        endcase
    end

    assign prdata_o = prdata_w;

endmodule
