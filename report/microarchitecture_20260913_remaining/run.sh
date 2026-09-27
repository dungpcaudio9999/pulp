#!/usr/bin/env bash
set -euo pipefail
report_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_dir=$(cd -- "$report_dir/../.." && pwd)
dep_dir="$repo_dir/.bender/git/checkouts"
common_dir="$dep_dir/common_cells-f18d75f6d6d026a5"
soc_dir="$dep_dir/pulp_soc-c519334bd3ac5582"
build_dir=$(mktemp -d /tmp/pulp-micro-remaining.XXXXXX)
printf '%s\n' "$build_dir" > "$report_dir/build_directory.txt"
verilator --version > "$report_dir/tool_version.txt"
cd "$report_dir"
verilator --binary --timing --trace --assert -Wno-fatal -j 2 --top-module tb_control --Mdir "$build_dir/control" \
  -I"$repo_dir/rtl/includes" -I"$soc_dir/rtl/includes" \
  -I"$dep_dir/cv32e40p-0a3884e05ea5a482/rtl/include" \
  "$soc_dir/rtl/components/pulp_interfaces.sv" \
  "$dep_dir/cv32e40p-0a3884e05ea5a482/rtl/include/apu_core_package.sv" \
  "$dep_dir/udma_core-25b62500cd51a5c6/rtl/common/io_generic_fifo.sv" \
  "$dep_dir/udma_core-25b62500cd51a5c6/rtl/common/io_tx_fifo.sv" \
  "$soc_dir/rtl/pulp_soc/soc_event_queue.sv" \
  "$dep_dir/cv32e40p-0a3884e05ea5a482/rtl/riscv_apu_disp.sv" \
  "$dep_dir/event_unit_flex-385402acb0ace331/rtl/hw_barrier_unit.sv" \
  "$dep_dir/tech_cells_generic-6a4b27e0e56cbcda/src/rtl/tc_clk.sv" \
  "$dep_dir/pulp_cluster-48721e3ce381c984/rtl/cluster_clock_gate.sv" \
  "$report_dir/tb_control.sv" > control_compile.log 2>&1
"$build_dir/control/Vtb_control" > control_run.log 2>&1
verilator --binary --timing --trace --assert -Wno-fatal -j 2 --top-module tb_cdc --Mdir "$build_dir/cdc" \
  -I"$common_dir/include" "$common_dir/src/cf_math_pkg.sv" \
  "$common_dir/src/sync.sv" "$common_dir/src/gray_to_binary.sv" "$common_dir/src/binary_to_gray.sv" \
  "$common_dir/src/spill_register_flushable.sv" "$common_dir/src/spill_register.sv" \
  "$common_dir/src/cdc_fifo_gray.sv" "$report_dir/tb_cdc.sv" > cdc_compile.log 2>&1
"$build_dir/cdc/Vtb_cdc" > cdc_run.log 2>&1
cat control_run.log cdc_run.log
interco_dir="$dep_dir/cluster_interconnect-abcda71a83f4333c/rtl/tcdm_interconnect"
verilator --binary --timing --trace --assert -Wno-fatal -j 2 --top-module tb_xbar --Mdir "$build_dir/xbar" \
  -I"$common_dir/include" "$common_dir/src/cf_math_pkg.sv" "$common_dir/src/lzc.sv" \
  "$common_dir/src/rr_arb_tree.sv" "$interco_dir/addr_dec_resp_mux.sv" "$interco_dir/xbar.sv" \
  "$report_dir/tb_xbar.sv" > xbar_compile.log 2>&1
"$build_dir/xbar/Vtb_xbar" > xbar_run.log 2>&1
cat xbar_run.log
mchan_dir="$dep_dir/mchan-1903412f92cb4b0c"
verilator --binary --timing --trace --assert -Wno-fatal -j 2 --top-module tb_dma_synch --Mdir "$build_dir/dma_synch" \
  -I"$mchan_dir/rtl/include" "$mchan_dir/rtl/ctrl_unit/synch_unit.sv" \
  "$report_dir/tb_dma_synch.sv" > dma_synch_compile.log 2>&1
"$build_dir/dma_synch/Vtb_dma_synch" > dma_synch_run.log 2>&1
cat dma_synch_run.log
