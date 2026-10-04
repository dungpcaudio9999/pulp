# Focused waveform for the prebuilt zcu104_uart_direct ELF.
# This application runs only on the FC and sends one 23-byte UDMA UART buffer.

set TB /tb_pulp
set CL /tb_pulp/i_dut/cluster_domain_i/cluster_i
set FC /tb_pulp/i_dut/soc_domain_i/pulp_soc_i/fc_subsystem_i

vcd file -compress zcu104_uart_direct.vcd.gz

set patterns [list \
  "$TB/s_clk_ref" \
  "$TB/s_rst_n" \
  "$TB/exit_status" \
  "$TB/w_uart_rx" \
  "$TB/w_uart_tx" \
  "$TB/uart_tb_rx_en" \
  "$FC/fetch_en_i" \
  "$FC/boot_addr_i" \
  "$CL/clk_cluster" \
  "$CL/s_rst_n" \
  "$CL/fetch_en_int" \
  "$CL/core_busy" \
  "$CL/busy_o"]

set added 0
foreach pattern $patterns {
  set matches [find signals -nodu $pattern]
  foreach signal $matches {
    vcd add $signal
    incr added
  }
}
echo "UART-DIRECT-VCD|signals=$added"

if {[info exists ::env(SIM_TIMEOUT)]} {
  eval run $::env(SIM_TIMEOUT)
} else {
  run 30 ms
}

set status [examine -radix decimal $TB/exit_status]
echo "UART-DIRECT-VCD|exit_status=$status"
vcd flush
if {$status == -1} {
  quit -f -code 124
}
quit -f -code $status
