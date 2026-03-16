// =============================================================================
// File    : uart_ctrl.v
// Module  : uart_ctrl
// Purpose : UART controller — 8N1 format, parameterised baud rate.
//           Includes TX shift register and RX deserialiser with
//           2-stage input synchroniser.  Three-segment FSM for each path.
//
// Register Map (byte offset, word access):
//   0x00 : UART_TXDATA — write byte to transmit (triggers TX if not busy)
//   0x04 : UART_RXDATA — read last received byte [7:0]
//   0x08 : UART_STATUS — bit0=tx_busy, bit1=rx_valid (cleared on read), bit2=rx_err
//
// TX baud timing: 10 bits (1 start + 8 data + 1 stop), LSB first.
// RX sampling   : mid-bit sampling (sample at half-baud after start edge).
//
// Author  : Generated for VCD power analysis project
// Date    : 2026-03-12
// Version : 1.0
// =============================================================================

`timescale 1ns / 1ps

module uart_ctrl #(
    parameter CLK_FREQ  = 100_000_000,   // system clock, Hz
    parameter BAUD_RATE = 115_200        // desired baud rate
)(
    input  wire        clk,
    input  wire        rst_n,

    // Internal peripheral bus
    input  wire        pvalid_i,
    input  wire        pwrite_i,
    input  wire [7:0]  paddr_i,
    input  wire [31:0] pwdata_i,
    output wire [31:0] prdata_o,

    // Physical UART
    input  wire        uart_rx_i,
    output wire        uart_tx_o
);

    // =========================================================================
    // Baud rate constants
    // =========================================================================
    localparam BAUD_DIV  = CLK_FREQ / BAUD_RATE;      // cycles per bit (e.g. 868)
    localparam BAUD_HALF = BAUD_DIV / 2;               // half-bit offset for RX
    localparam CNT_W     = $clog2(BAUD_DIV + 1);       // counter width (e.g. 10)

    // Verilog-2001 compatible baud constants (replaces SystemVerilog CNT_W'(...) casts)
    localparam [CNT_W-1:0] BAUD_DIV_M1  = BAUD_DIV  - 1;
    localparam [CNT_W-1:0] BAUD_HALF_M1 = BAUD_HALF - 1;

    // =========================================================================
    // TX — state definitions
    // =========================================================================
    localparam TX_IDLE  = 1'b0;
    localparam TX_SHIFT = 1'b1;

    reg        tx_state_r, tx_state_nxt;
    reg [9:0]  tx_frame_r;     // 10-bit frame: {stop, data[7:0], start}
    reg [3:0]  tx_bit_r;       // counts 0..9  (10 bits total)
    reg [CNT_W-1:0] tx_baud_r; // baud period counter
    reg        tx_out_r;
    reg        tx_busy_r;

    // Combinatorial helper signals
    wire tx_start_w   = pvalid_i && pwrite_i && (paddr_i[3:2] == 2'b00) &&
                        (tx_state_r == TX_IDLE);
    wire tx_baud_done = (tx_baud_r == BAUD_DIV_M1);
    wire tx_last_bit  = (tx_bit_r  == 4'd9);

    // ----- Segment 1: TX state register -------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) tx_state_r <= TX_IDLE;
        else        tx_state_r <= tx_state_nxt;
    end

    // ----- Segment 2: TX next-state logic (combinatorial) -------------------
    always @(*) begin
        tx_state_nxt = tx_state_r;   // default: hold current state
        case (tx_state_r)
            TX_IDLE:  if (tx_start_w)                    tx_state_nxt = TX_SHIFT;
            TX_SHIFT: if (tx_baud_done && tx_last_bit)   tx_state_nxt = TX_IDLE;
            default:                                      tx_state_nxt = TX_IDLE;
        endcase
    end

    // ----- Segment 3: TX datapath registers (sequential) -------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            tx_frame_r <= 10'h3FF;
            tx_bit_r   <= 4'd0;
            tx_baud_r  <= {CNT_W{1'b0}};
            tx_out_r   <= 1'b1;
            tx_busy_r  <= 1'b0;
        end else begin
            case (tx_state_r)
                TX_IDLE: begin
                    tx_out_r  <= 1'b1;
                    tx_busy_r <= 1'b0;
                    if (tx_start_w) begin
                        // Build 10-bit frame: start=0, data LSB-first, stop=1
                        tx_frame_r <= {1'b1, pwdata_i[7:0], 1'b0};
                        tx_baud_r  <= {CNT_W{1'b0}};
                        tx_bit_r   <= 4'd0;
                        tx_busy_r  <= 1'b1;
                    end
                end
                TX_SHIFT: begin
                    tx_out_r <= tx_frame_r[tx_bit_r];   // drive current bit
                    if (tx_baud_done) begin
                        tx_baud_r <= {CNT_W{1'b0}};
                        tx_bit_r  <= tx_bit_r + 4'd1;
                    end else begin
                        tx_baud_r <= tx_baud_r + {{(CNT_W-1){1'b0}}, 1'b1};
                    end
                    if (tx_baud_done && tx_last_bit)
                        tx_busy_r <= 1'b0;
                end
                default: begin
                    tx_out_r  <= 1'b1;
                    tx_busy_r <= 1'b0;
                end
            endcase
        end
    end

    assign uart_tx_o = tx_out_r;

    // =========================================================================
    // RX — state definitions
    // =========================================================================
    localparam RX_IDLE  = 2'd0;
    localparam RX_START = 2'd1;
    localparam RX_DATA  = 2'd2;
    localparam RX_STOP  = 2'd3;

    reg [1:0]        rx_state_r, rx_state_nxt;
    reg [CNT_W-1:0]  rx_baud_r;
    reg [7:0]        rx_shift_r;
    reg [2:0]        rx_bit_r;
    reg [7:0]        rx_data_r;
    reg              rx_valid_r;
    reg              rx_err_r;

    // 2-stage input synchroniser (CDC for async UART input)
    reg              rx_sync1_r, rx_sync2_r;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            rx_sync1_r <= 1'b1;
            rx_sync2_r <= 1'b1;
        end else begin
            rx_sync1_r <= uart_rx_i;
            rx_sync2_r <= rx_sync1_r;
        end
    end

    wire rx_baud_done = (rx_baud_r == BAUD_DIV_M1);
    wire rx_half_done = (rx_baud_r == BAUD_HALF_M1);
    wire rx_last_bit  = (rx_bit_r  == 3'd7);

    // ----- Segment 1: RX state register -------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) rx_state_r <= RX_IDLE;
        else        rx_state_r <= rx_state_nxt;
    end

    // ----- Segment 2: RX next-state logic (combinatorial) -------------------
    always @(*) begin
        rx_state_nxt = rx_state_r;
        case (rx_state_r)
            RX_IDLE:  if (!rx_sync2_r)                   rx_state_nxt = RX_START;
            RX_START: if (rx_half_done)                  rx_state_nxt = RX_DATA;
            RX_DATA:  if (rx_baud_done && rx_last_bit)   rx_state_nxt = RX_STOP;
            RX_STOP:  if (rx_baud_done)                  rx_state_nxt = RX_IDLE;
            default:                                     rx_state_nxt = RX_IDLE;
        endcase
    end

    // ----- Segment 3: RX datapath registers (sequential) -------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            rx_baud_r  <= {CNT_W{1'b0}};
            rx_shift_r <= 8'h0;
            rx_bit_r   <= 3'd0;
            rx_data_r  <= 8'h0;
            rx_valid_r <= 1'b0;
            rx_err_r   <= 1'b0;
        end else begin
            rx_valid_r <= 1'b0;   // pulse: cleared every cycle by default
            case (rx_state_r)
                RX_IDLE: begin
                    rx_baud_r <= {CNT_W{1'b0}};
                    rx_bit_r  <= 3'd0;
                end
                RX_START: begin
                    // Count to half-baud to hit the middle of the start bit
                    rx_baud_r <= rx_half_done ? {CNT_W{1'b0}} :
                                 rx_baud_r + {{(CNT_W-1){1'b0}}, 1'b1};
                end
                RX_DATA: begin
                    if (rx_baud_done) begin
                        // Sample at mid-bit, shift in LSB first
                        rx_shift_r <= {rx_sync2_r, rx_shift_r[7:1]};
                        rx_baud_r  <= {CNT_W{1'b0}};
                        rx_bit_r   <= rx_bit_r + 3'd1;
                    end else begin
                        rx_baud_r  <= rx_baud_r + {{(CNT_W-1){1'b0}}, 1'b1};
                    end
                end
                RX_STOP: begin
                    if (rx_baud_done) begin
                        rx_data_r  <= rx_shift_r;
                        rx_valid_r <= 1'b1;
                        rx_err_r   <= ~rx_sync2_r;   // framing error: stop bit ≠ 1
                        rx_baud_r  <= {CNT_W{1'b0}};
                    end else begin
                        rx_baud_r  <= rx_baud_r + {{(CNT_W-1){1'b0}}, 1'b1};
                    end
                end
                default: ;
            endcase
        end
    end

    // =========================================================================
    // Register read (combinatorial mux)
    // =========================================================================
    reg [31:0] prdata_w;

    always @(*) begin
        prdata_w = 32'h0;
        case (paddr_i[3:2])
            2'b00:   prdata_w = {31'h0, tx_busy_r};              // TX status
            2'b01:   prdata_w = {24'h0, rx_data_r};              // RX data
            2'b10:   prdata_w = {29'h0, rx_err_r,
                                         rx_valid_r, tx_busy_r}; // combined status
            default: prdata_w = 32'h0;
        endcase
    end

    assign prdata_o = prdata_w;

endmodule
