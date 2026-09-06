#!/usr/bin/env bash
# Chay full_system tren QuestaSim voi day du moi truong.
#
# Ton tai vi flow chuan can nhieu bien moi truong hon la 'source setup/vsim.sh',
# va vi phase 7 can generic -gUSE_HWPE_CL=1 ma tb_pulp mac dinh dat = 0.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Roi conda: chi /usr/bin/python3 co pyelftools, conda base thi khong
export PATH="$(echo "$PATH" | tr ':' '\n' | grep -v miniforge3 | paste -sd:)"
hash -r

export PULP_PROJECT_HOME="$ROOT"
export QUESTA_HOME="$HOME/questasim"
export PULP_RISCV_GCC_TOOLCHAIN="$HOME/ndmoney4porche/tools/v1.0.16-pulp-riscv-gcc-ubuntu-16"
export PULP_SDK_HOME="$ROOT/pulp-runtime"
export PULP_RUNTIME_HOME="$ROOT/pulp-runtime"
export CROSS_COMPILE="$PULP_RISCV_GCC_TOOLCHAIN/bin/riscv32-unknown-elf-"
export PATH="$PULP_RISCV_GCC_TOOLCHAIN/bin:$QUESTA_HOME/bin:$PATH"
# GCC build cho Ubuntu 16 can libmpfr.so.4 / libisl.so.15
export LD_LIBRARY_PATH="$PULP_RISCV_GCC_TOOLCHAIN/compat-libs/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"

# License server phai dang chay
if ! pgrep -x lmgrd >/dev/null; then
    "$QUESTA_HOME/linux_x86_64/lmgrd" -c "$QUESTA_HOME/LICENSE.dat" \
        -l "$QUESTA_HOME/license_server.log"
fi
export LM_LICENSE_FILE=27001@localhost
export MGLS_LICENSE_FILE=27001@localhost

ulimit -n 4096 2>/dev/null || true

cd "$ROOT"
source setup/vsim.sh
# BAT BUOC: dat PULPRT_HOME/PULPRT_TARGET. Thieu no thi rules/pulp.mk dung
# '-include' nen im lang khong nap target nao -> "No rule to make target 'clean'"
source pulp-runtime/configs/pulp.sh
export PULP_SDK_HOME="$ROOT/pulp-runtime"
export PULP_RUNTIME_HOME="$ROOT/pulp-runtime"

# Phase 7: tb_pulp.sv:48 dat USE_HWPE_CL=0 nen HWPE khong duoc instantiate.
# Phai dat qua BIEN MOI TRUONG, khong phai 'make run vsim_flags=...':
# vsim_flags dung '?=' roi '+=', bien tren dong lenh make se ghi de ca cac
# '+=' va lam MAT -gLOAD_L2=JTAG, chuong trinh se khong duoc nap.
export vsim_flags="+ENTRY_POINT=0x1c008080 -permit_unmatched_virtual_intf -gBAUDRATE=115200 -gUSE_HWPE_CL=1"

cd "$ROOT/sw/full_system"
exec make "${@:-clean all run}"
