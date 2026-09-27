#!/usr/bin/env bash
# Buoc 1: chay tung test cua PULP SDK tren gvsoc pulp-open, ghi PASS/FAIL.
# Dung: sw/gvsoc/step1_sdk_tests.sh [thu_muc_ket_qua]
set -o pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="${1:-$HERE/../../report/gvsoc_$(date +%Y%m%d)/step1}"
mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"
source "$HERE/env.sh"
set -u

# ten | thu muc | co make (lay tu testset.cfg) | chuoi phai co trong output
TESTS=(
  "hello_fc|hello|build_dir_ext=fc|Hello from FC"
  "hello_cl|hello|build_dir_ext=cl USE_CLUSTER=1|Hello from cluster_id: 0, core_id: 0"
  "cluster_call|cluster/call|build_dir_ext=call|"
  "cluster_fork|cluster/fork|build_dir_ext=fork|"
  # cluster/fork_power bi bo: Makefile cua no ep --event=.* va sinh VCD
  # 22 GB sau 4 phut (lan chay 2026-09-19), co nguy co lam day o dia.
  "dma_1d|dma/1d|build_dir_ext=1d|"
  "flash_simple|flash/simple|build_dir_ext=simple|"
  "flash_with_ram|flash/with_ram|build_dir_ext=with_ram|"
  "fs_read_fc|fs/read|build_dir_ext=read_fc|"
  "fs_read_cl|fs/read|build_dir_ext=read_cl USE_CLUSTER=1|"
  "perf_double_buffering|perf/double_buffering|build_dir_ext=double_buffering|"
  "perf_matmult|perf/matmult|build_dir_ext=matmult|"
  "ram_simple|ram/simple|build_dir_ext=simple|"
  "uart_loopback|uart/loopback|build_dir_ext=simple|"
)

{
  echo "# gvsoc $(git -C "$GVSOC_HOME" rev-parse --short HEAD), pulp-sdk $(git -C "$PULP_SDK_HOME_GV" rev-parse --short HEAD), $(date -Is)"
  printf "%-24s %-6s %-5s %s\n" TEST RESULT EXIT WALL_S
} > "$OUT/summary.txt"

for t in "${TESTS[@]}"; do
  IFS='|' read -r name dir flags expect <<< "$t"
  log="$OUT/$name.log"
  start=$(date +%s)
  ( cd "$PULP_SDK_HOME_GV/tests/$dir" && timeout 600 make clean all run $flags ) > "$log" 2>&1
  rc=$?
  wall=$(( $(date +%s) - start ))
  res=FAIL
  if [[ $rc -eq 0 ]]; then
    if [[ -z "$expect" ]] || grep -qF "$expect" "$log"; then res=PASS; fi
  fi
  [[ $rc -eq 124 ]] && res=TIMEOUT
  printf "%-24s %-6s %-5s %s\n" "$name" "$res" "$rc" "$wall" | tee -a "$OUT/summary.txt"
done
