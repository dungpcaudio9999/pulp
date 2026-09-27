`timescale 1ns/1ps
module tb_cdc;
  logic sc=0, dc=0, sr=0, dr=0, sv=0, ready, dv, consume=0;
  logic [15:0] data_in=0, data_out;
  always #3.5 sc=~sc;
  always #5.5 dc=~dc;
  int sent=0, received=0, dst_cycles=0, stalled=0, max_pending=0;
  time first_send, first_receive;
  int src_reset_count=0, dst_reset_count=0;
  always @(posedge sc) if(!sr) begin
    src_reset_count <= src_reset_count+1;
    if(src_reset_count==2) sr <= 1;
  end
  always @(posedge dc) if(!dr) begin
    dst_reset_count <= dst_reset_count+1;
    if(dst_reset_count==2) dr <= 1;
  end
  cdc_fifo_gray #(.WIDTH(16),.LOG_DEPTH(2)) dut (
    .src_rst_ni(sr),.src_clk_i(sc),.src_data_i(data_in),.src_valid_i(sv),.src_ready_o(ready),
    .dst_rst_ni(dr),.dst_clk_i(dc),.dst_data_o(data_out),.dst_valid_o(dv),.dst_ready_i(consume));
  always @(posedge sc) if(sr && sv) begin
    if(ready) begin
      if(sent==0) first_send=$time;
      sent++;
      if(sent-received>max_pending) max_pending=sent-received;
    end else stalled++;
  end
  always @(negedge sc) if(sr) begin sv=(sent<64); data_in=16'h9000+16'(sent); end
  always @(negedge dc) if(dr) begin
    dst_cycles++;
    consume=(dst_cycles>24) && ((dst_cycles%5)!=0) && ((dst_cycles%7)!=0);
  end
  always @(posedge dc) if(dr && dv && consume) begin
    if(data_out !== (16'h9000+16'(received))) $fatal(1,"CDC order/data: index %0d got %h",received,data_out);
    if(received==0) first_receive=$time;
    received++;
  end
  initial begin
    $dumpfile("cdc.vcd"); $dumpvars(0,tb_cdc);
    // POR asserted together; deassert at each domain's clock edge after reset cycles.
    wait(sr && dr);
    wait(dst_cycles==23); #1;
    if(sent!=6 || received!=0 || ready) $fatal(1,"CDC capacity expected four FIFO + two spill entries, got %0d/%0d ready=%b",sent,received,ready);
    $display("CHECK CDC blocked consumer: accepted=%0d (4 FIFO + 2 spill), received=%0d",sent,received);
    wait(received==64); repeat(6) @(posedge dc); #1;
    if(sent!=64 || dv || stalled==0 || max_pending>6) $fatal(1,"CDC drain/credit failure");
    $display("PASS CDC: sent=%0d received=%0d max_pending=%0d src_stall_cycles=%0d first_delivery_elapsed_ns=%0d (includes deliberate consumer stall)",sent,received,max_pending,stalled,first_receive-first_send);
    $finish;
  end
  initial begin #20000; $fatal(1,"CDC timeout"); end
endmodule
