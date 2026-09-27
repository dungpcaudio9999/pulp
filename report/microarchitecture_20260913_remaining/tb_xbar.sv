`timescale 1ns/1ps
module tb_xbar;
  logic clk=0,rst=0;
  always #5 clk=~clk;
  logic [3:0] req=0, grant, valid, bank_req, bank_grant=15;
  logic [3:0][1:0] bank='0;
  logic [3:0][31:0] payload='0, out_payload, reply='0, data;
  logic [3:0] accepted;
  logic [3:0][31:0] expected;
  int total=0;
  xbar #(.NumIn(4),.NumOut(4),.ReqDataWidth(32),.RespDataWidth(32),.RespLat(1),.WriteRespOn(1)) dut (
    .clk_i(clk),.rst_ni(rst),.rr_i('0),.req_i(req),.add_i(bank),.wen_i(4'b0),
    .wdata_i(payload),.gnt_o(grant),.vld_o(valid),.rdata_o(data),
    .gnt_i(bank_grant),.req_o(bank_req),.wdata_o(out_payload),.rdata_i(reply));
  // A one-cycle target fixture, not SRAM: encodes the routed request in its reply.
  always @(posedge clk) begin
    for(int b=0;b<4;b++) if(bank_req[b] && bank_grant[b]) reply[b]<=out_payload[b]^32'hcaf00000;
    accepted=req & grant;
    for(int m=0;m<4;m++) expected[m]=payload[m]^32'hcaf00000;
    #1;
    if(rst) begin
      if(valid !== accepted) $fatal(1,"response valid != previous edge acceptance");
      for(int m=0;m<4;m++) if(valid[m]) begin
        if(data[m]!==expected[m]) $fatal(1,"response owner/data mismatch master %0d",m);
        total++;
      end
    end
  end
  task automatic run_case(input bit conflict, input int blocked_cycles, input int tag);
    int cycles, n;
    logic [3:0] got;
    @(negedge clk); req=15;
    for(int m=0;m<4;m++) begin bank[m]=conflict ? 2'b0 : 2'(m); payload[m]=32'(tag*16+m); end
    bank_grant=blocked_cycles>0 ? 0 : 15;
    for(int c=0;c<blocked_cycles;c++) begin
      @(posedge clk); #2;
      if(grant!=0 || valid!=0) $fatal(1,"grant/response while all banks stalled");
      @(negedge clk);
    end
    bank_grant=15; cycles=0;
    while(req!=0) begin
      #1; got=grant & req; n=$countones(got);
      if(n != (conflict ? 1 : 4)) $fatal(1,"wrong parallel grant count: %0d",n);
      @(posedge clk); #2; cycles++;
      @(negedge clk); req=req & ~got;
      if(cycles>4) $fatal(1,"starvation");
    end
    if(cycles!=(conflict ? 4 : 1)) $fatal(1,"unexpected service span");
    $display("PASS xbar case: same_bank=%0d blocked_cycles=%0d four_requests_service_cycles=%0d",conflict,blocked_cycles,cycles);
    @(posedge clk); #2;
  endtask
  initial begin
    $dumpfile("xbar.vcd"); $dumpvars(0,tb_xbar);
    repeat(2) @(negedge clk); rst=1;
    run_case(0,0,1); run_case(1,0,2); run_case(1,3,3); run_case(0,2,4);
    if(total!=16) $fatal(1,"wrong response count %0d",total);
    $display("PASS xbar: 16 accepted requests, 16 checked responses; independent banks 4 requests/cycle, same bank 1 request/cycle in this fixture");
    $finish;
  end
  initial begin #10000; $fatal(1,"xbar timeout"); end
endmodule
