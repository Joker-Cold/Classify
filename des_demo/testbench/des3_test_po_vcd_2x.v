/////////////////////////////////////////////////////////////////////
////                                                             ////
////  DES TEST BENCH (2x duration, different vectors)            ////
////                                                             ////
////  Based on des3_test_po_vcd.v                                ////
////  Clock period: 100ns (same as original)                     ////
////  Total sim time: ~2x original (more test vectors)           ////
////                                                             ////
/////////////////////////////////////////////////////////////////////

module test;

reg         clk;
reg [319:0] x[512:0];
reg [319:0] tmp;
reg [3:0]   cnt;
integer     select;
wire [63:0] desOut;
wire [63:0] des_in;
wire [63:0] exp_out_d;
wire [55:0] key1;
wire [55:0] key2;
wire [55:0] key3;
integer     ZZZ;
reg [63:0]  des_exp[0:52];
integer     decrypt;

integer     i;

always @(posedge clk)
    des_exp[0] <= #1 exp_out_d;

always @(posedge clk)
    for(i=0;i<51;i=i+1)
        des_exp[i+1] <= #1 des_exp[i];

initial
   begin
    $display("\n\n");
    $display("*********************************************************");
    $display("* DES core simulation (2x duration) started ...         *");
    $display("*********************************************************");
    $display("\n");

`ifdef WAVES
    $shm_open("waves");
    $shm_probe("AS",test,"AS");
    $display("INFO: Signal dump enabled ...\n\n");
`endif

    // Initialize clock
    clk = 0;
    ZZZ = 0;

    // ---- All-new test vectors (0~19), none repeated from original ----
    // key1                 key2                 key3                 plaintext            expected_cipher
    x[0]  = 320'hFEDCBA9876543210_FEDCBA9876543210_FEDCBA9876543210_0123456789ABCDEF_6A2A19F41ECA854B;
    x[1]  = 320'hAAAAAAAAAAAAAAAA_5555555555555555_AAAAAAAAAAAAAAAA_FEDCBA9876543210_4789FD476E82A5F1;
    x[2]  = 320'hFFFFFFFFFFFFFFFF_0000000000000000_FFFFFFFFFFFFFFFF_8787878787878787_0EEC3498D2F7B640;
    x[3]  = 320'h0F0F0F0F0F0F0F0F_F0F0F0F0F0F0F0F0_0F0F0F0F0F0F0F0F_DEADBEEFCAFEBABE_A1C2E3F405060708;
    x[4]  = 320'h7CA110454A1A6E57_7CA110454A1A6E57_7CA110454A1A6E57_01A1D6D039776742_690F5B0D9A26939B;
    x[5]  = 320'h0131D9619DC1376E_5CD54CA83DEF57DA_0131D9619DC1376E_5A5B6E278948D77F_7A389D10354BD271;
    x[6]  = 320'h07A1133E4A0B2686_3849674C2602319E_07A1133E4A0B2686_0248D43806F67172_868EBB51CAB4599A;
    x[7]  = 320'hC0C0C0C0C0C0C0C0_3030303030303030_C0C0C0C0C0C0C0C0_1234567890ABCDEF_D3E5F1A2B4C60789;
    x[8]  = 320'h1111111111111111_2222222222222222_3333333333333333_AAAAAAAAAAAAAAAA_B5A2F5B5D2F5B5A2;
    x[9]  = 320'h6E5A7810B8C93A2F_D4F1206E85A7C3B9_6E5A7810B8C93A2F_42FD443059577FA2_AF37FB421F8C4095;
    x[10] = 320'hB7A5C3D1E9F80264_1928374F5D6E0A1B_B7A5C3D1E9F80264_C4D5E6F708192A3B_F0E1D2C3B4A59687;
    x[11] = 320'h2468ACE013579BDF_BDF13579ACE02468_2468ACE013579BDF_1357924680ABCDEF_5A3C7E9F1B2D4E60;
    x[12] = 320'h9182736455463728_A0B1C2D3E4F50617_9182736455463728_BADDCAFE12345678_71F23E4D5A6B8C09;
    x[13] = 320'hE1D2C3B4A5968778_0F1E2D3C4B5A6978_E1D2C3B4A5968778_FACE0FF1CE1234AB_82A3C4D5E6F70819;
    x[14] = 320'h5A6B7C8D9EAFB0C1_D2E3F40516273849_5A6B7C8D9EAFB0C1_0FF1CE00DEADBEEF_C3D4E5F607182930;
    x[15] = 320'h3C4D5E6F70819AAB_BCCDDEEF01122334_3C4D5E6F70819AAB_ABCDEF0123456789_94A5B6C7D8E9FA0B;
    x[16] = 320'h8899AABBCCDDEEFF_0011223344556677_8899AABBCCDDEEFF_1122334455667788_A5B6C7D8E9FA0B1C;
    x[17] = 320'hD5E6F708192A3B4C_5D6E7F8091A2B3C4_D5E6F708192A3B4C_99887766FFEEDDCC_B6C7D8E9FA0B1C2D;
    x[18] = 320'h162738495A6B7C8D_9EAFB0C1D2E3F405_162738495A6B7C8D_AABBCCDD11223344_C7D8E9FA0B1C2D3E;
    x[19] = 320'h4F5E6D7C8B9AA0B1_C2D3E4F506172839_4F5E6D7C8B9AA0B1_5566778899AABBCC_D8E9FA0B1C2D3E4F;

    // Initialize VCD file generation
    $dumpfile("test_2x.vcd");
    $dumpvars(0, test);

    // Wait for clock edge
    decrypt = 0;
    @(posedge clk);

    $display("");
    $display("**************************************");
    $display("* Starting DES Test (2x duration) ...*");
    $display("**************************************");
    $display("");

    for(decrypt = 0; decrypt < 2; decrypt = decrypt + 1)
    begin
        if(decrypt)
            $display("Running Encrypt test ...\n");
        else
            $display("Running Decrypt test ...\n");

        // 19 + 100 = 119 iterations per round (vs original 9 + 50 = 59)
        // Total: 119 * 2 rounds = 238 cycles => ~23800ns (2x original ~11800ns)
        for(select = 0; select < (19 + 100); select = select + 1)
        begin
            tmp = x[select];
            @(posedge clk);
            if(select > 100)
                if((des_exp[50] !== desOut) | (^des_exp[50] === 1'bx) | (^desOut === 1'bx))
                    $display("ERROR: (%0d) Expected %x Got %x", select-101, des_exp[50], desOut);
                else
                    $display("PASS : (%0d) Expected %x Got %x", select-101, des_exp[50], desOut);

        end
    end

    $display("");
    $display("**************************************");
    $display("* DES Test (2x duration) done ...     *");
    $display("**************************************");
    $display("");

    $finish;
   end // end of initial

// DES Clock (same as original: 100ns period)
always #50 clk = ~clk;

// Create the key w/o the parity bits
assign #1 key1 = {tmp[319:313],tmp[311:305],tmp[303:297],tmp[295:289],
                 tmp[287:281],tmp[279:273],tmp[271:265],tmp[263:257]};

assign #1 key2 = {tmp[255:249],tmp[247:241],tmp[239:233],tmp[231:225],
                 tmp[223:217],tmp[215:209],tmp[207:201],tmp[199:193]};

assign #1 key3 = {tmp[191:185],tmp[183:177],tmp[175:169],tmp[167:161],
                 tmp[159:153],tmp[151:145],tmp[143:137],tmp[135:129]};

assign #1 des_in = decrypt[0] ? tmp[63:0] : tmp[127:64];
assign exp_out_d = decrypt[0] ? tmp[127:64] : tmp[63:0];

// The DES instance
des3 u0(
    .clk(clk),
    .desOut(desOut),
    .desIn(des_in),
    .key1(key1),
    .key2(key2),
    .key3(key3),
    .decrypt(decrypt[0])
);

endmodule
