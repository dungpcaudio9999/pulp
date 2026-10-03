# Focused RTL waveform for flow_demo.  This intentionally records control and
# transaction handshakes instead of recursively dumping the complete design.

set TB /tb_pulp
set CL /tb_pulp/i_dut/cluster_domain_i/cluster_i
set FC /tb_pulp/i_dut/soc_domain_i/pulp_soc_i/fc_subsystem_i

vcd file -compress flow_demo.vcd.gz

set patterns [list \
  "$TB/s_clk_ref" \
  "$TB/s_rst_n" \
  "$TB/exit_status" \
  "$FC/fetch_en_i" \
  "$FC/boot_addr_i" \
  "$CL/clk_cluster" \
  "$CL/s_rst_n" \
  "$CL/fetch_en_int" \
  "$CL/core_busy" \
  "$CL/busy_o" \
  "$CL/s_dmac_busy" \
  "$CL/s_dma_cl_event" \
  "$CL/dmac_wrap_i/mchan_i/ctrl_targ_req_i" \
  "$CL/dmac_wrap_i/mchan_i/ctrl_targ_gnt_o" \
  "$CL/dmac_wrap_i/mchan_i/tcdm_init_req_o" \
  "$CL/dmac_wrap_i/mchan_i/tcdm_init_gnt_i" \
  "$CL/dmac_wrap_i/mchan_i/axi_master_aw_valid_o" \
  "$CL/dmac_wrap_i/mchan_i/axi_master_aw_ready_i" \
  "$CL/dmac_wrap_i/mchan_i/axi_master_ar_valid_o" \
  "$CL/dmac_wrap_i/mchan_i/axi_master_ar_ready_i" \
  "$CL/dmac_wrap_i/mchan_i/axi_master_r_valid_i" \
  "$CL/dmac_wrap_i/mchan_i/axi_master_r_ready_o" \
  "$CL/cluster_peripherals_i/event_unit_flex_i/core_busy_i" \
  "$CL/cluster_peripherals_i/event_unit_flex_i/core_clock_en_o"]

set added 0
foreach pattern $patterns {
  set matches [find signals -nodu $pattern]
  foreach signal $matches {
    vcd add $signal
    incr added
  }
}
echo "FLOW-VCD|signals=$added"

if {[info exists ::env(SIM_TIMEOUT)]} {
  eval run $::env(SIM_TIMEOUT)
} else {
  run 30 ms
}

set status [examine -radix decimal $TB/exit_status]
echo "FLOW-VCD|exit_status=$status"
vcd flush
if {$status == -1} {
  quit -f -code 124
}
quit -f -code $status
