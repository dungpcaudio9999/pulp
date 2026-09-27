`timescale 1ns/1ps
// Standalone test of the repository LSU. The EX and memory interfaces are driven
// explicitly; this is not a CPU/interconnect simulation or an instruction test.
module tb_fc_lsu;
  logic clk = 0, rst_n = 1;
  logic data_req_o, data_gnt_i = 0, data_rvalid_i = 0, data_err_i = 0;
  logic [31:0] data_addr_o, data_wdata_o, data_rdata_i = 0;
  logic data_we_o;
  logic [3:0] data_be_o;
  logic data_we_ex_i = 0, data_req_ex_i = 0;
  logic [1:0] data_type_ex_i = 0, data_reg_offset_ex_i = 0, data_sign_ext_ex_i = 0;
  logic [31:0] data_wdata_ex_i = 0, operand_a_ex_i = 0, operand_b_ex_i = 0;
  logic addr_useincr_ex_i = 1, data_misaligned_ex_i = 0, data_misaligned_o;
  logic [31:0] data_rdata_ex_o;
  logic lsu_ready_ex_o, lsu_ready_wb_o, ex_valid_i = 1, busy_o;
  integer checks = 0;

  riscv_load_store_unit dut (.*);

  task automatic check(input logic condition, input string message);
    if (condition !== 1'b1) $fatal(1, "FAIL: %s", message);
    checks++;
  endtask

  task automatic tick;
    #2; clk = 1; #2; clk = 0; #1;
  endtask

  initial begin
    $dumpfile("lsu.vcd");
    $dumpvars(0, tb_fc_lsu);
    #1; rst_n = 0; tick(); rst_n = 1; #1;
    check(!busy_o && lsu_ready_ex_o && lsu_ready_wb_o, "reset idle");

    // A signed byte load: delayed grant, then delayed response.
    data_req_ex_i = 1; data_type_ex_i = 2'b10; data_sign_ext_ex_i = 1;
    operand_a_ex_i = 32'h1c010015;
    #1;
    check(data_req_o && !lsu_ready_ex_o && data_be_o == 4'b0010, "byte request waits for grant");
    tick(); tick();
    check(data_req_o && data_addr_o == 32'h1c010015, "held request before grant");
    data_gnt_i = 1; #1;
    check(lsu_ready_ex_o, "grant releases EX side");
    tick(); data_gnt_i = 0; data_req_ex_i = 0; #1;
    check(!lsu_ready_wb_o && !data_req_o, "response wait blocks WB");
    tick();

    // Load response and next store acceptance on the same edge: old metadata
    // must sign-extend the byte even though the new request is a word store.
    data_rvalid_i = 1; data_rdata_i = 32'h00008000;
    data_req_ex_i = 1; data_we_ex_i = 1; data_type_ex_i = 0;
    operand_a_ex_i = 32'h1c010018; data_wdata_ex_i = 32'h11223344;
    data_gnt_i = 1; #1;
    check(data_rdata_ex_o == 32'hffffff80, "old response uses old byte/sign metadata");
    check(data_req_o && lsu_ready_ex_o && lsu_ready_wb_o, "response plus next grant");
    check(data_we_o && data_be_o == 4'b1111 && data_wdata_o == 32'h11223344, "full-word store payload");
    tick(); data_gnt_i = 0; data_rvalid_i = 0; data_req_ex_i = 0; #1;
    check(!lsu_ready_wb_o && busy_o, "store waits for completion response");
    tick(); data_rvalid_i = 1; #1;
    check(lsu_ready_wb_o, "store response releases WB");
    tick(); data_rvalid_i = 0;

    // A request is accepted while EX cannot advance for another reason.
    data_req_ex_i = 1; data_we_ex_i = 0; data_gnt_i = 1; ex_valid_i = 0;
    operand_a_ex_i = 32'h1c010020; #1; tick(); data_gnt_i = 0; #1;
    check(!data_req_o, "accepted transaction not reissued while EX stalled");
    data_rvalid_i = 1; data_rdata_i = 32'hcafef00d; #1; tick();
    data_rvalid_i = 0; #1;
    check(!data_req_o && data_rdata_ex_o == 32'hcafef00d, "response retained through EX stall");
    tick(); check(!data_req_o, "no duplicate in IDLE_EX_STALL");
    ex_valid_i = 1; data_req_ex_i = 0; tick();

    // Split word load. The test drives the second-beat operands/flag that the
    // real ID/EX logic must generate; this does not test that pipeline logic.
    data_req_ex_i = 1; data_gnt_i = 1; operand_a_ex_i = 32'h1c010015;
    data_type_ex_i = 0; #1;
    check(data_misaligned_o && data_be_o == 4'b1110, "split word first beat");
    tick(); data_misaligned_ex_i = 1; operand_a_ex_i = 32'h1c010019;
    data_rvalid_i = 1; data_rdata_i = 32'h44332211; #1;
    check(data_req_o && data_be_o == 4'b0001 && !data_misaligned_o, "split word second beat");
    tick(); data_gnt_i = 0; data_req_ex_i = 0; data_misaligned_ex_i = 0;
    data_rdata_i = 32'h88776655; #1;
    check(data_rdata_ex_o == 32'h55443322, "split word little-endian assembly");
    tick(); data_rvalid_i = 0; #1;
    check(data_rdata_ex_o == 32'h55443322 && !busy_o, "assembled result retained");

    // Split-store payload rotation and byte enables, no memory model used.
    data_req_ex_i = 1; data_we_ex_i = 1; data_gnt_i = 1;
    operand_a_ex_i = 32'h1c010015; data_wdata_ex_i = 32'h11223344; #1;
    check(data_be_o == 4'b1110 && data_wdata_o == 32'h22334411, "split store first payload");
    tick(); data_misaligned_ex_i = 1; operand_a_ex_i = 32'h1c010019;
    data_rvalid_i = 1; #1;
    check(data_req_o && data_be_o == 4'b0001 && data_wdata_o == 32'h22334411, "split store second payload");
    tick(); data_gnt_i = 0; data_req_ex_i = 0; data_misaligned_ex_i = 0;
    tick(); data_rvalid_i = 0; #1;
    check(!busy_o, "split store completed");
    $display("PASS: %0d checks, standalone LSU only", checks);
    $finish;
  end
  initial begin #10000; $fatal(1, "watchdog"); end
endmodule
