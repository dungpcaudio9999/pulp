#!/usr/bin/env bash
# Bật/tắt FPU cluster. XSim 2019.1 cần TẮT (xem PROJECT_STATUS mục 7); Questa dùng BẬT.
#   ./toggle_fpu.sh off   -> cho XSim
#   ./toggle_fpu.sh on    -> cho Questa (mặc định của repo)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
F="$ROOT/rtl/includes/pulp_soc_defines.sv"
case "${1:-}" in
  off) sed -i 's/^`define CLUST_FPU 1$/`define CLUST_FPU 0/; s/^`define CLUST_FP_DIVSQRT 1$/`define CLUST_FP_DIVSQRT 0/' "$F" ;;
  on)  sed -i 's/^`define CLUST_FPU 0$/`define CLUST_FPU 1/; s/^`define CLUST_FP_DIVSQRT 0$/`define CLUST_FP_DIVSQRT 1/' "$F" ;;
  *)   echo "dùng: $0 on|off"; exit 1 ;;
esac
grep -n '^`define CLUST_FPU\|^`define CLUST_FP_DIVSQRT' "$F"
echo "LƯU Ý: đổi giá trị này thì phải chạy lại 'make build' cho Questa."
