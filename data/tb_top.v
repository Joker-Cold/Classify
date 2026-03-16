//=============================================================================
// File    : tb_top.v
// Purpose : Testbench for SoC â€? generates sim_output.vcd for
//           Cadence Voltus dynamic vector-based IRdrop / power analysis.
//
// DUT     : soc_top (structural RTL from soc/ directory)
//           Compile with: soc/soc_top.v soc/ahb_slave.v soc/sram_ctrl.v
//           soc/gpio_ctrl.v soc/uart_ctrl.v soc/spi_master.v
//           soc/irq_ctrl.v soc/pwr_ctrl.v
//
// Clock   : 100 MHz  (T_clk = 10 ns)
//
// Phase Timeline  (approximate, verify exact timestamps from VCD):
//   Phase 1 â€? Init & Reset       :    0 ns ~   100 ns   (10 cycles)
//   Phase 2 â€? Normal Operation   :  100 ns ~   600 ns   (~50 cycles)
//   Phase 3 â€? Worst-Case Power   :  600 ns ~  1600 ns   (100 cycles) *** Voltus window ***
//   Phase 4 â€? Idle / Low Power   : 1600 ns ~  2100 ns   (50 cycles)
//   Phase 5 â€? Burst Activity     : 2100 ns ~  ~3500 ns  (2 x burst + gaps)
//
// Voltus Usage Example:
//   read_activity_file -format VCD \
//       -scope tb_top/u_soc \
//       -start 600ns -end 1600ns \
//       sim_output.vcd
//=============================================================================

`timescale 1ns / 1ps

//=============================================================================
// Testbench: tb_top
//=============================================================================
module tb_top;

    //=========================================================================
    // 1. DUT Port Declarations
    //=========================================================================

    // Clock & Reset
    reg         clk;
    reg         rst_n;

    // AHB-Lite Master Interface (CPU -> SoC interconnect)
    reg  [31:0] haddr;
    reg  [1:0]  htrans;     // 2'b00=IDLE, 2'b10=NONSEQ, 2'b11=SEQ
    reg         hwrite;
    reg  [2:0]  hsize;      // 3'b000=Byte, 3'b001=Halfword, 3'b010=Word
    reg  [31:0] hwdata;
    wire [31:0] hrdata;
    wire        hready;
    wire        hresp;

    // SRAM Interface
    reg  [17:0] sram_addr;
    reg  [31:0] sram_wdata;
    wire [31:0] sram_rdata;
    reg         sram_wen;
    reg         sram_ren;
    reg  [3:0]  sram_ben;

    // GPIO
    reg  [15:0] gpio_in;
    wire [15:0] gpio_out;

    // UART
    reg         uart_rx;
    wire        uart_tx;

    // SPI Master
    reg         spi_miso;
    wire        spi_mosi;
    wire        spi_sclk;
    wire        spi_cs_n;

    // External Interrupts
    reg  [7:0]  irq;

    // Power Mode Control
    reg  [1:0]  pwr_mode;   // 2'b00=Normal, 2'b01=Sleep, 2'b10=DeepSleep

    //=========================================================================
    // 2. DUT Instantiation
    //=========================================================================
    soc_top u_soc (
        .clk        (clk),
        .rst_n      (rst_n),
        .haddr      (haddr),
        .htrans     (htrans),
        .hwrite     (hwrite),
        .hsize      (hsize),
        .hwdata     (hwdata),
        .hrdata     (hrdata),
        .hready     (hready),
        .hresp      (hresp),
        .sram_addr  (sram_addr),
        .sram_wdata (sram_wdata),
        .sram_rdata (sram_rdata),
        .sram_wen   (sram_wen),
        .sram_ren   (sram_ren),
        .sram_ben   (sram_ben),
        .gpio_in    (gpio_in),
        .gpio_out   (gpio_out),
        .uart_rx    (uart_rx),
        .uart_tx    (uart_tx),
        .spi_miso   (spi_miso),
        .spi_mosi   (spi_mosi),
        .spi_sclk   (spi_sclk),
        .spi_cs_n   (spi_cs_n),
        .irq        (irq),
        .pwr_mode   (pwr_mode)
    );

    //=========================================================================
    // 3. Clock Generation: 100 MHz (period = 10 ns)
    //=========================================================================
    initial clk = 1'b0;
    always #5 clk = ~clk;

    //=========================================================================
    // 4. VCD Dump Setup
    //    $dumpvars(0, tb_top) exports ALL hierarchical signals including
    //    DUT internals â€? required for Voltus dynamic power analysis.
    //=========================================================================
    initial begin
        $dumpfile("F:\GraduatePrj\Classify\data\sim_output.vcd");
        $dumpvars(0, tb_top);
    end

    //=========================================================================
    // 5. Helper Tasks
    //=========================================================================

    // AHB-Lite single-beat write (address phase + data phase = 2 clock cycles)
    task ahb_write;
        input [31:0] addr;
        input [31:0] data;
        input [2:0]  sz;
        begin
            @(posedge clk); #1;
            haddr  = addr;
            htrans = 2'b10;   // NONSEQ
            hwrite = 1'b1;
            hsize  = sz;
            @(posedge clk); #1;
            hwdata = data;
            htrans = 2'b00;   // IDLE
            hwrite = 1'b0;
        end
    endtask

    // AHB-Lite single-beat read (address phase + data phase = 2 clock cycles)
    task ahb_read;
        input [31:0] addr;
        input [2:0]  sz;
        begin
            @(posedge clk); #1;
            haddr  = addr;
            htrans = 2'b10;   // NONSEQ
            hwrite = 1'b0;
            hsize  = sz;
            @(posedge clk); #1;
            htrans = 2'b00;   // IDLE
        end
    endtask

    // SRAM burst write: count cycles of back-to-back writes + 1 termination cycle
    task sram_burst_write;
        input [17:0] base;
        input [31:0] pattern;
        input integer count;
        integer j;
        begin
            for (j = 0; j < count; j = j + 1) begin
                @(posedge clk); #1;
                sram_addr  = base + j[17:0];
                sram_wdata = pattern ^ {16'h0, j[15:0]};
                sram_wen   = 1'b1;
                sram_ren   = 1'b0;
                sram_ben   = 4'hF;
            end
            @(posedge clk); #1;
            sram_wen = 1'b0;
        end
    endtask

    //=========================================================================
    // 6. Timeout Protection
    //=========================================================================
    initial begin
        #(10 * 500000);
        $error("TIMEOUT: Simulation exceeded max cycles");
        $finish;
    end

    //=========================================================================
    // 7. Main Stimulus
    //=========================================================================
    integer k;

    initial begin

        //---------------------------------------------------------------------
        // PHASE 1 â€? Init & Reset  (0 ns ~ ~100 ns, 10 clock cycles)
        //   All inputs driven to known-good values. Active-low reset held for
        //   10 clock cycles before release.
        //---------------------------------------------------------------------
        $display("[%0t ns] PHASE 1 START: Init & Reset", $time);

        // Initialize ALL inputs to deterministic values (no X/Z)
        rst_n      = 1'b0;
        haddr      = 32'h0000_0000;
        htrans     = 2'b00;
        hwrite     = 1'b0;
        hsize      = 3'b010;
        hwdata     = 32'h0000_0000;
        sram_addr  = 18'h0_0000;
        sram_wdata = 32'h0000_0000;
        sram_wen   = 1'b0;
        sram_ren   = 1'b0;
        sram_ben   = 4'hF;
        gpio_in    = 16'h0000;
        uart_rx    = 1'b1;    // UART idle line = HIGH
        spi_miso   = 1'b0;
        irq        = 8'h00;
        pwr_mode   = 2'b00;   // Normal mode

        // Hold reset for 10 clock cycles (100 ns at 100 MHz)
        repeat (10) @(posedge clk);
        #1;
        rst_n = 1'b1;

        $display("[%0t ns] PHASE 1 END:   Reset released", $time);

        //---------------------------------------------------------------------
        // PHASE 2 â€? Normal Operation  (~100 ns ~ ~600 ns, ~50 cycles)
        //   Simulates typical SoC boot sequence:
        //     AHB register config, SRAM initialisation, GPIO sensor reads,
        //     interrupt service, SPI peripheral configuration.
        //---------------------------------------------------------------------
        $display("[%0t ns] PHASE 2 START: Normal Operation", $time);

        // AHB register writes â€? boot / peripheral init  (5 writes = 10 cycles)
        ahb_write(32'h0000_0000, 32'hDEAD_BEEF, 3'b010);  // config reg 0
        ahb_write(32'h0000_0004, 32'hCAFE_BABE, 3'b010);  // config reg 1
        ahb_write(32'h0000_0008, 32'h1234_5678, 3'b010);  // DMA base address
        ahb_write(32'h0000_000C, 32'hA5A5_A5A5, 3'b010);  // timer reload value
        ahb_write(32'h0000_0010, 32'h0000_0001, 3'b010);  // global enable

        // AHB read-back to verify registers  (5 reads = 10 cycles)
        ahb_read(32'h0000_0000, 3'b010);
        ahb_read(32'h0000_0004, 3'b010);
        ahb_read(32'h0000_0008, 3'b010);
        ahb_read(32'h0000_000C, 3'b010);
        ahb_read(32'h0000_0010, 3'b010);

        // SRAM sequential initialisation â€? 16 words  (16 + 1 = 17 cycles)
        sram_burst_write(18'h0_0000, 32'h1111_2222, 16);

        // GPIO stimulus â€? incrementing sensor input  (5 cycles)
        repeat (5) begin
            @(posedge clk); #1;
            gpio_in = gpio_in + 16'h0101;
        end

        // Interrupt service sequence â€? 2 IRQ events  (4 cycles)
        @(posedge clk); #1; irq = 8'h01;   // IRQ0 asserted
        @(posedge clk); #1; irq = 8'h00;   // handler clears
        @(posedge clk); #1; irq = 8'h42;   // IRQ1 + IRQ6 asserted
        @(posedge clk); #1; irq = 8'h00;

        // SPI peripheral config via AHB  (2 cycles)
        ahb_write(32'h0000_0F00, 32'h0000_00A5, 3'b000);  // byte write to SPI ctrl

        // Padding to complete ~50-cycle Phase 2 window  (2 cycles)
        repeat (2) @(posedge clk);

        $display("[%0t ns] PHASE 2 END:   Normal Operation", $time);

        //---------------------------------------------------------------------
        // PHASE 3 â€? Worst-Case Power  (~600 ns ~ ~1600 ns, 100 cycles)
        //
        //   ALL buses driven at maximum toggle rate simultaneously.
        //   AHB address/data, SRAM data, GPIO, IRQ, UART RX, SPI MISO
        //   all switch every clock cycle using maximum-Hamming-distance
        //   patterns (0xFFFF_FFFF <-> 0x0000_0000 and 0xAAAA_AAAA <-> 0x5555_5555).
        //
        //   *** Voltus IRdrop analysis window: -start 600ns -end 1600ns ***
        //---------------------------------------------------------------------
        $display("[%0t ns] PHASE 3 START: Worst-Case Power (Voltus window START)", $time);

        for (k = 0; k < 100; k = k + 1) begin
            @(posedge clk); #1;

            // AHB bus â€? alternating checkerboard (maximum toggle density)
            haddr  = (k % 2 == 0) ? 32'hAAAA_AAAA : 32'h5555_5555;
            htrans = 2'b10;
            hwrite = 1'b1;
            hsize  = 3'b010;
            hwdata = (k % 2 == 0) ? 32'hFFFF_FFFF : 32'h0000_0000;

            // SRAM bus â€? alternating byte-lane patterns
            sram_addr  = {1'b0, k[16:0]};
            sram_wdata = (k % 2 == 0) ? 32'hFF00_FF00 : 32'h00FF_00FF;
            sram_wen   = 1'b1;
            sram_ren   = 1'b0;
            sram_ben   = 4'hF;

            // GPIO â€? full rail-to-rail swing every cycle
            gpio_in = (k % 2 == 0) ? 16'hFFFF : 16'h0000;

            // IRQ â€? all interrupt lines toggling
            irq = (k % 2 == 0) ? 8'hFF : 8'h00;

            // UART RX â€? data stream at maximum bit rate
            uart_rx = k[0];

            // SPI MISO â€? pseudo-random bit via XOR-reduce
            spi_miso = ^k[7:0];
        end

        // Clean deassert of all bus activity
        @(posedge clk); #1;
        htrans   = 2'b00;
        hwrite   = 1'b0;
        sram_wen = 1'b0;
        sram_ren = 1'b0;
        irq      = 8'h00;
        uart_rx  = 1'b1;
        spi_miso = 1'b0;

        $display("[%0t ns] PHASE 3 END:   Worst-Case Power (Voltus window END)", $time);

        //---------------------------------------------------------------------
        // PHASE 4 â€? Idle / Low Power  (~1600 ns ~ ~2100 ns, 50 cycles)
        //   All buses held constant; only the clock is toggling.
        //   pwr_mode asserted to model standby / wait state.
        //---------------------------------------------------------------------
        $display("[%0t ns] PHASE 4 START: Idle / Low Power", $time);

        haddr    = 32'h0000_0000;
        htrans   = 2'b00;
        hwrite   = 1'b0;
        hwdata   = 32'h0000_0000;
        sram_addr  = 18'h0_0000;
        sram_wdata = 32'h0000_0000;
        sram_wen = 1'b0;
        sram_ren = 1'b0;
        gpio_in  = 16'hABCD;  // stable sensor value â€? no GPIO toggles
        irq      = 8'h00;
        uart_rx  = 1'b1;
        spi_miso = 1'b0;
        pwr_mode = 2'b01;     // Sleep mode

        repeat (50) @(posedge clk);
        #1;
        pwr_mode = 2'b00;     // Wake-up: return to Normal mode

        $display("[%0t ns] PHASE 4 END:   Idle / Low Power", $time);

        //---------------------------------------------------------------------
        // PHASE 5 â€? Burst Activity  (~2100 ns ~ ~3500 ns)
        //   Two intensive bursts separated by a 10-cycle idle gap.
        //   Models power-surge / bursty workload profile (e.g., DMA transfer,
        //   frame processing). Toggle rate is between Phase 2 and Phase 3.
        //---------------------------------------------------------------------
        $display("[%0t ns] PHASE 5 START: Burst Activity", $time);

        //-- Burst 1: AHB sequential writes + SRAM fill (~82 cycles) ----------
        $display("[%0t ns] PHASE 5: Burst 1 start", $time);

        for (k = 0; k < 20; k = k + 1) begin
            ahb_write(
                32'h0010_0000 + (k[31:0] << 2),
                32'hDEAD_0000 | k[31:0],
                3'b010
            );
        end

        sram_burst_write(18'h1_0000, 32'hBEEF_CAFE, 20);

        // Interrupt burst associated with end of DMA
        @(posedge clk); #1; irq = 8'h0F;
        @(posedge clk); #1; irq = 8'h00;

        //-- Idle gap between bursts (10 cycles) -------------------------------
        htrans   = 2'b00;
        hwrite   = 1'b0;
        sram_wen = 1'b0;
        repeat (10) @(posedge clk);

        //-- Burst 2: Interleaved AHB + SRAM + GPIO + IRQ (~21 cycles) --------
        $display("[%0t ns] PHASE 5: Burst 2 start", $time);

        for (k = 0; k < 20; k = k + 1) begin
            @(posedge clk); #1;
            // AHB write with alternating payload
            haddr  = 32'h0020_0000 + (k[31:0] << 2);
            htrans = 2'b10;
            hwrite = 1'b1;
            hsize  = 3'b010;
            hwdata = (k % 2 == 0) ? 32'hF0F0_F0F0 : 32'h0F0F_0F0F;
            // SRAM write interleaved
            sram_addr  = 18'h2_0000 + k[17:0];
            sram_wdata = (k % 2 == 0) ? 32'hAABB_CCDD : 32'h5544_3322;
            sram_wen   = 1'b1;
            sram_ben   = 4'hF;
            // GPIO and IRQ burst
            gpio_in = 16'hFF00 ^ k[15:0];
            irq     = k[7:0];
        end

        @(posedge clk); #1;
        htrans   = 2'b00;
        hwrite   = 1'b0;
        sram_wen = 1'b0;
        irq      = 8'h00;

        // Final idle settling (10 cycles)
        repeat (10) @(posedge clk);

        $display("[%0t ns] PHASE 5 END:   Burst Activity", $time);

        //---------------------------------------------------------------------
        // End of Simulation
        //---------------------------------------------------------------------
        $display("[%0t ns] All phases complete. VCD written to sim_output.vcd", $time);
        $dumpoff;
        $finish;

    end // initial

endmodule
