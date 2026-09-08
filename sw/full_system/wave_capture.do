set TB  /tb_pulp
set CL  /tb_pulp/i_dut/cluster_domain_i/cluster_i
set FC  /tb_pulp/i_dut/soc_domain_i/pulp_soc_i/fc_subsystem_i

vcd file -compress full_system.vcd.gz
foreach s "$TB/s_clk_ref $TB/s_rst_n $TB/s_tck $TB/s_tms $TB/s_tdi $TB/s_tdo \
           $TB/s_trstn $TB/exit_status $TB/jtag_mux \
           $CL/clk_cluster $CL/s_rst_n $CL/fetch_en_int $CL/core_busy $CL/busy_o \
           $FC/fetch_en_i $FC/boot_addr_i" {
  if {[find signals -nodu $s] ne ""} { vcd add $s }
}

proc mark {lbl} { echo "EVT|[format %12.1f [expr {$::now/1000.0}]]|$lbl" }

# 'when' chi nhan bieu thuc tren tin hieu, KHONG nhan bien Tcl:
# viet "$::now > N" trong dieu kien se bi thay bang 0 luc dinh nghia va
# vsim bao 'No objects found matching 0' roi treo o prompt.
when -label e1 "$TB/s_rst_n == 1'b1"     { mark "reset he thong nha";         nowhen e1 }
when -label e2 "$TB/s_trstn == 1'b1"     { mark "JTAG trstn nha";             nowhen e2 }
when -label e3 "$FC/fetch_en_i == 1'b1"  { mark "FC fetch enable bat";        nowhen e3 }
when -label e4 "$CL/s_rst_n == 1'b1"     { mark "cluster reset nha";          nowhen e4 }
when -label e5 "$CL/fetch_en_int != 0"   { mark "cluster core bat dau fetch";  nowhen e5 }
when -label e6 "$CL/busy_o == 1'b1"      { mark "cluster bao busy lan dau";   nowhen e6 }

# Watchdog: SIM_TIMEOUT gioi han thoi gian mo phong (vd "30 ms").
# 'run -all' tran khong co gioi han: neu tb khong toi $stop thi vsim treo im
# o prompt, khong PASS khong FAIL. tb_pulp.sv:156 khoi tao exit_status =
# `EXIT_ERROR(-1) va chi ghi de khi test ket thuc, nen -1 = chua chay xong.
if {[info exists ::env(SIM_TIMEOUT)] && [string trim $::env(SIM_TIMEOUT)] ne ""} {
  set timeout [string trim $::env(SIM_TIMEOUT)]
  echo "WATCHDOG|bat, gioi han thoi gian mo phong = $timeout"
  eval run $timeout
} else {
  run -all
}

mark "mo phong dung (\$stop cua tb)"
set st [examine -radix decimal $TB/exit_status]
echo "EXIT-STATUS|[examine -radix hex $TB/exit_status]"
# Luon flush VCD truoc khi thoat: waveform cua mot lan TIMEOUT chinh la thu
# can nhat de tim cho treo.
vcd flush
if {$st == -1} {
  echo "WATCHDOG|TIMEOUT - testbench chua ket thuc, exit_status van la EXIT_ERROR(-1)"
  quit -f -code 124
}
quit -f -code $st
