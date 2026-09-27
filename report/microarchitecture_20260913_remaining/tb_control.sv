`timescale 1ns/1ps
module tb_control;
  logic clk=0, rst=0;
  always #5 clk=~clk;
  int checks=0;
  task automatic check(input bit ok, input string msg);
    if (!ok) $fatal(1,"FAIL: %s",msg);
    checks++; $display("CHECK %0d: %s",checks,msg);
  endtask
  task automatic tick;
    @(posedge clk); #1;
    @(negedge clk); #1;
  endtask
  logic tx_req, tx_gnt=0, tx_valid, tx_ready=0, tx_in_valid=0, tx_in_ready;
  logic [7:0] tx_in=0, tx_out;
  io_tx_fifo #(.DATA_WIDTH(8),.BUFFER_DEPTH(2)) tx (
    .clk_i(clk),.rstn_i(rst),.clr_i(1'b0),.req_o(tx_req),.gnt_i(tx_gnt),
    .data_o(tx_out),.valid_o(tx_valid),.ready_i(tx_ready),
    .valid_i(tx_in_valid),.data_i(tx_in),.ready_o(tx_in_ready));
  logic event_in=0, event_ack=0, event_out, event_err;
  soc_event_queue eq (.clk_i(clk),.rstn_i(rst),.event_i(event_in),
    .event_ack_i(event_ack),.event_o(event_out),.err_o(event_err));
  logic apu_en=0, apu_gnt=0, apu_resp=0, apu_req, apu_ready, active, stall, rd_dep, wr_dep;
  logic [1:0] lat=2;
  logic [5:0] wa=0, wo;
  logic [2:0][5:0] rr='0;
  logic [2:0] rv='0;
  riscv_apu_disp apu (.clk_i(clk),.rst_ni(rst),.enable_i(apu_en),.apu_lat_i(lat),
    .apu_waddr_i(wa),.apu_waddr_o(wo),.apu_multicycle_o(),.apu_singlecycle_o(),
    .active_o(active),.stall_o(stall),.read_regs_i(rr),.read_regs_valid_i(rv),
    .read_dep_o(rd_dep),.write_regs_i('0),.write_regs_valid_i('0),.write_dep_o(wr_dep),
    .perf_type_o(),.perf_cont_o(),.apu_master_req_o(apu_req),.apu_master_ready_o(apu_ready),
    .apu_master_gnt_i(apu_gnt),.apu_master_valid_i(apu_resp));
  XBAR_PERIPH_BUS db();
  XBAR_PERIPH_BUS pb();
  logic [3:0] trigger=0, status, events;
  hw_barrier_unit #(.NB_CORES(4)) barrier (.clk_i(clk),.rst_ni(rst),
    .barrier_trigger_core_i(trigger),.barrier_status_o(status),.barrier_events_o(events),
    .demux_bus_slave(db),.periph_bus_slave(pb));
  logic cg_en=0, int_busy=0, incoming=0, gate_event=0, gated_clk, isolate;
  cluster_clock_gate #(.NB_CORES(4)) cg (.clk_i(clk),.rstn_i(rst),.test_mode_i(1'b0),
    .cluster_cg_en_i(cg_en),.cluster_int_busy_i(int_busy),.cores_busy_i(4'b0),
    .events_i(gate_event),.incoming_req_i(incoming),.isolate_cluster_o(isolate),.cluster_clk_o(gated_clk));
  int gated_edges=0, saved_edges;
  always @(posedge gated_clk) if(rst) gated_edges++;
  initial begin
    $dumpfile("control.vcd"); $dumpvars(0,tb_control);
    db.req=0; db.wen=0; db.add=0; db.wdata=0; db.be='1; db.id=0;
    pb.req=0; pb.wen=0; pb.add=0; pb.wdata=0; pb.be='1; pb.id=0;
    tick(); tick(); rst=1; #1;
    check(tx_req && !tx_valid,"TX empty permits reservation");
    tx_gnt=1; tick(); check(tx_req,"TX second credit available");
    tick(); tx_gnt=0; #1; check(!tx_req && tx_in_ready,"TX two inflight reserve both empty slots");
    tick(); check(!tx_req,"TX delayed responses cannot cause third request");
    tx_in_valid=1; tx_in=8'h41; tick();
    check(tx_valid && tx_out==8'h41 && !tx_req,"TX first return held under consumer stall");
    tx_in=8'h42; tick(); tx_in_valid=0; #1;
    check(!tx_in_ready && !tx_req && tx_out==8'h41,"TX full after second reserved response");
    repeat(3) tick(); check(tx_out==8'h41,"TX stable output during extended stall");
    tx_ready=1; tick(); check(tx_valid && tx_out==8'h42,"TX ordered second byte");
    tick(); check(!tx_valid && tx_req,"TX drain restores credits"); tx_ready=0;
    event_in=1; repeat(3) tick(); check(event_out && event_err,"event counter saturates at three");
    event_ack=1; #1; check(event_err,"full plus simultaneous ack still reports error");
    tick(); event_in=0; tick(); check(event_out,"event count two after ack");
    tick(); check(event_out,"event count one after ack");
    tick(); check(!event_out,"event queue empty after third ack"); event_ack=0;
    apu_en=1; wa=5; #1; check(apu_req && stall,"APU no grant causes nack stall");
    apu_gnt=1; tick(); wa=6; #1; check(active && apu_req && !stall,"APU accepts second latency-two request");
    tick(); wa=7; #1; check(stall && !apu_req,"APU full blocks third outstanding request");
    apu_en=0; apu_gnt=0; rr[0]=5; rv=1; #1; check(rd_dep,"APU RAW dependency on oldest result");
    apu_resp=1; #1; check(wo==5 && !rd_dep,"APU oldest response selects rd5 and clears its dependency");
    tick(); check(wo==6 && active,"APU next response selects rd6");
    tick(); apu_resp=0; #1; check(!active,"APU both responses drained");
    rv=0; apu_en=1; apu_gnt=1; lat=3; wa=8; tick(); lat=2; #1;
    check(stall && !apu_req,"APU latency-two blocked behind multicycle operation");
    apu_en=0; apu_gnt=0; apu_resp=1; tick(); apu_resp=0;
    db.req=1; db.add=0; db.wdata=15; tick();
    db.add=12; db.wdata=10; tick(); db.req=0;
    trigger=7; tick(); trigger=0; check(status==7 && events==0,"barrier waits for missing fourth participant");
    trigger=1; tick(); trigger=0; check(status==7 && events==0,"barrier duplicate arrival does not increment count");
    trigger=8; tick(); trigger=0; check(events==10,"barrier releases configured target mask");
    tick(); check(status==0 && events==0,"barrier clears after match");
    db.req=1; db.add=0; db.wdata=3; tick(); db.req=0;
    trigger=7; tick(); trigger=0; check(events==0 && status==7,"barrier exact equality rejects extra participant bit");
    cg_en=1; repeat(3) tick(); check(cg.s_clockenable,"clock gate stays enabled for first three idle samples");
    tick(); check(!cg.s_clockenable,"clock gate disables after four idle samples");
    saved_edges=gated_edges; repeat(3) tick(); check(gated_edges==saved_edges,"gated clock produces no edges while idle");
    incoming=1; tick(); incoming=0; tick(); check(gated_edges>saved_edges,"incoming request reopens clock gate");
    $display("PASS control: %0d checks",checks); $finish;
  end
  initial begin #10000; $fatal(1,"control timeout"); end
endmodule
