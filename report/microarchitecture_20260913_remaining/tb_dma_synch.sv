`timescale 1ns/1ps
module tb_dma_synch;
  logic clk=0,rst=0,req=0,gnt=0,ext_done=0,tcdm_done=0,registered,busy,done;
  logic [3:0] sid=3,ext_sid=3,tcdm_sid=3;
  logic [7:0] count=0;
  int checks=0;
  always #5 clk=~clk;
  synch_unit #(.TRANS_SID(3),.TRANS_SID_WIDTH(4),.MCHAN_CMD_WIDTH(8),.MCHAN_BURST_LENGTH(256)) dut (
    .clk_i(clk),.rst_ni(rst),.mchan_tx_req_i(req),.mchan_tx_gnt_i(gnt),.mchan_tx_sid_i(sid),.mchan_tx_cmd_nb_i(count),
    .mchan_rx_req_i(1'b0),.mchan_rx_gnt_i(1'b0),.mchan_rx_sid_i(4'b0),.mchan_rx_cmd_nb_i(8'b0),
    .ext_tx_synch_req_i(ext_done),.ext_tx_synch_sid_i(ext_sid),.ext_rx_synch_req_i(1'b0),.ext_rx_synch_sid_i(4'b0),
    .tcdm_tx_synch_req_i(tcdm_done),.tcdm_tx_synch_sid_i(tcdm_sid),.tcdm_rx_synch_req_i(1'b0),.tcdm_rx_synch_sid_i(4'b0),
    .trans_registered_o(registered),.trans_status_o(busy),.term_sig_o(done));
  task automatic tick; @(posedge clk); #1; @(negedge clk); #1; endtask
  task automatic check(input bit ok,input string msg);
    if(!ok) $fatal(1,"DMA synch: %s",msg);
    checks++; $display("CHECK DMA %0d: %s",checks,msg);
  endtask
  initial begin
    $dumpfile("dma_synch.vcd"); $dumpvars(0,tb_dma_synch);
    tick(); tick(); rst=1;
    req=1; count=2; tick(); check(!busy,"ungranted command does not start transfer");
    gnt=1; #1; check(registered,"matching accepted command registers transfer"); tick(); req=0; gnt=0;
    check(busy && !done,"two commands pending at both interfaces");
    tcdm_done=1; repeat(2) tick(); tcdm_done=0;
    check(busy && !done,"all TCDM completions alone do not finish DMA");
    ext_done=1; ext_sid=4; tick(); check(busy && !done,"different SID does not retire this transfer");
    ext_sid=3; tick(); check(busy && !done,"one external completion still leaves work");
    tick(); ext_done=0; check(done && busy,"final external completion produces event; busy has delayed tail");
    tick(); check(!done && !busy,"completion pulse and delayed busy drain");
    req=1; gnt=1; count=1; tick(); req=0; gnt=0;
    // Retire old work while accepting one new command: must remain pending.
    req=1; gnt=1; ext_done=1; tcdm_done=1; tick(); req=0; gnt=0; ext_done=0; tcdm_done=0;
    check(busy && !done,"simultaneous enqueue and retire preserves new work");
    ext_done=1; tick(); ext_done=0; check(busy && !done,"external complete still waits for TCDM");
    tcdm_done=1; tick(); tcdm_done=0; check(done,"last TCDM completion also closes transfer");
    tick(); check(!busy && !done,"both directions drained");
    $display("PASS DMA synch: %0d checks",checks); $finish;
  end
  initial begin #10000; $fatal(1,"DMA synch timeout"); end
endmodule
