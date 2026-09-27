#!/usr/bin/env bash
set -euo pipefail
MICRO_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
MICRO_ROOT=$(cd -- "$MICRO_DIR/../.." && pwd)
MICRO_BUILD=$(mktemp -d /tmp/pulp-micro-lsu.XXXXXX)
printf 'Build directory: %s\n' "$MICRO_BUILD"
iverilog -V 2>&1 | sed -n '1p'
# VERILATOR disables only the original LSU's SVA block, unsupported by Icarus.
# The testbench's independent procedural checks remain enabled.
iverilog -g2012 -DVERILATOR -s tb_fc_lsu -o "$MICRO_BUILD/tb" \
  "$MICRO_ROOT/.bender/git/checkouts/cv32e40p-0a3884e05ea5a482/rtl/riscv_load_store_unit.sv" \
  "$MICRO_DIR/tb_fc_lsu.sv" > "$MICRO_BUILD/compile.log" 2>&1 || {
    cat "$MICRO_BUILD/compile.log"
    exit 1
  }
cd -- "$MICRO_BUILD"
vvp ./tb
printf 'Compiler log: %s/compile.log\nWaveform: %s/lsu.vcd\n' "$MICRO_BUILD" "$MICRO_BUILD"
