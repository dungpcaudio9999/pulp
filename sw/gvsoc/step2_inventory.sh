#!/usr/bin/env bash
# Buoc 2: lap danh muc nhung gi gvsoc do duoc tren pulp-open.
# Chay mot ELF nho voi tung co che do, roi rut ra:
#   traces.txt   component nao sinh trace text (--trace=.*)
#   vcd_signals.txt  cay tin hieu VCD (--vcd --event=.*)
#   power.csv    component nao co model cong suat (--power)
# Dung: sw/gvsoc/step2_inventory.sh [thu_muc_ket_qua] [elf]
set -o pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="${1:-$HERE/../../report/gvsoc_$(date +%Y%m%d)/step2}"
mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"
source "$HERE/env.sh"
set -u

# Mac dinh: hello chay tren cluster (FC + 8 PE, co offload), du nho de trace .*
ELF="${2:-$PULP_SDK_HOME_GV/tests/hello/BUILD/PULP/GCC_RISCV/cl/test/test}"
[[ -f "$ELF" ]] || { echo "Khong thay ELF: $ELF (chay step1 truoc)" >&2; exit 1; }

strip_ansi() { sed 's/\x1b\[[0-9;]*m//g'; }
run() {  # run <ten> <tham so gvsoc...>
  local name=$1; shift
  local wd="$OUT/run_$name"
  mkdir -p "$wd"
  ( cd "$wd" && timeout 600 gvsoc --target=pulp-open --work-dir="$wd" --binary "$ELF" "$@" run ) \
    > "$wd/stdout.log" 2>&1
  echo "$name: exit=$?" | tee -a "$OUT/runs.txt"
}

: > "$OUT/runs.txt"
echo "ELF=$ELF sha256=$(sha256sum "$ELF" | cut -c1-16)" >> "$OUT/runs.txt"

# 1. Tat ca trace text
run trace_all --trace=.*:trace_all.log --trace-level=trace
strip_ansi < "$OUT/run_trace_all/trace_all.log" \
  | grep -oE '\[/[^ ]+' | tr -d '[' | sort | uniq -c | sort -k2 > "$OUT/traces.txt"

# 2. Tat ca event VCD
run vcd_all --vcd --event=.*@all.vcd
awk '$1=="$scope"{s[++d]=$3} $1=="$upscope"{d--}
     $1=="$var"{p=""; for(i=1;i<=d;i++) p=p"/"s[i]; print p"/"$5}' \
  "$OUT/run_vcd_all/all.vcd" | sort -u > "$OUT/vcd_signals.txt"

# 3. Cong suat
run power --power
cp "$OUT/run_power/power_report.csv" "$OUT/power.csv" 2>/dev/null

# Tom tat
{
  echo "trace paths:  $(wc -l < "$OUT/traces.txt")"
  echo "vcd signals:  $(wc -l < "$OUT/vcd_signals.txt")"
  echo "power rows:   $(grep -c power_trace "$OUT/power.csv" 2>/dev/null)"
} | tee -a "$OUT/runs.txt"

# Xoa file lon, giu ket qua da rut gon
rm -f "$OUT/run_vcd_all/all.vcd" "$OUT"/run_*/hyperflash.bin
gzip -f "$OUT/run_trace_all/trace_all.log"
