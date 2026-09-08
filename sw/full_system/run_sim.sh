#!/usr/bin/env bash
# Chay full_system tren QuestaSim voi day du moi truong.
#
# Ton tai vi flow chuan can nhieu bien moi truong hon la 'source setup/vsim.sh',
# va vi phase 7 can generic -gUSE_HWPE_CL=1 ma tb_pulp mac dinh dat = 0.
#
# Bien moi truong ghi de duoc:
#   QUESTA_HOME              thu muc cai Questa            (mac dinh: $HOME/questasim)
#   PULP_RISCV_GCC_TOOLCHAIN toolchain RISC-V              (mac dinh: do tu tim)
#   SIM_TIMEOUT              watchdog thoi gian MO PHONG   (mac dinh: "40 ms")
#   WALL_TIMEOUT             watchdog thoi gian THUC, giay (mac dinh: 1800)
#
# Vi du:
#   ./run_sim.sh                       # clean all run
#   ./run_sim.sh clean all run INJECT_FAULT=1
#   SIM_TIMEOUT="5 ms" ./run_sim.sh    # ep watchdog no som de thu duong TIMEOUT
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Roi conda: chi /usr/bin/python3 co pyelftools, conda base thi khong
export PATH="$(echo "$PATH" | tr ':' '\n' | grep -v miniforge3 | paste -sd:)"
hash -r

# --- Dinh vi toolchain -----------------------------------------------------
# Truoc day hai duong dan nay bi hardcode vao mot may cu. Tren may khac chung
# tro vao hu vo, va loi chi lo ra rat muon duoi dang 'No rule to make target'.
export QUESTA_HOME="${QUESTA_HOME:-$HOME/questasim}"

if [[ -z "${PULP_RISCV_GCC_TOOLCHAIN:-}" ]]; then
    for c in "$HOME/ndmoney4porche/tools/v1.0.16-pulp-riscv-gcc-ubuntu-16" \
             "$HOME/tools/v1.0.16-pulp-riscv-gcc-ubuntu-16" \
             /opt/riscv /opt/pulp-riscv-gcc; do
        if [[ -x "$c/bin/riscv32-unknown-elf-gcc" ]]; then
            PULP_RISCV_GCC_TOOLCHAIN="$c"; break
        fi
    done
fi
export PULP_RISCV_GCC_TOOLCHAIN="${PULP_RISCV_GCC_TOOLCHAIN:-}"

# --- Preflight -------------------------------------------------------------
# Bao het cac thu thieu MOT LAN, thay vi chet giua chung o cho kho doan.
missing=()
[[ -x "$QUESTA_HOME/bin/vsim" ]] || missing+=("Questa: khong thay \$QUESTA_HOME/bin/vsim (QUESTA_HOME=$QUESTA_HOME)")
[[ -n "$PULP_RISCV_GCC_TOOLCHAIN" && -x "$PULP_RISCV_GCC_TOOLCHAIN/bin/riscv32-unknown-elf-gcc" ]] \
    || missing+=("Toolchain RISC-V: dat PULP_RISCV_GCC_TOOLCHAIN tro toi thu muc chua bin/riscv32-unknown-elf-gcc")
[[ -f "$ROOT/pulp-runtime/configs/pulp.sh" ]] || missing+=("pulp-runtime: chay 'make pulp-runtime' o goc repo")
[[ -f "$ROOT/sim/compile.tcl" ]] || missing+=("sim/compile.tcl: chay './bender checkout && ./patch-deps && make scripts'")
/usr/bin/python3 -c "import elftools" 2>/dev/null || missing+=("pyelftools cho /usr/bin/python3: 'pip3 install pyelftools' (stim_utils.py can)")

if (( ${#missing[@]} )); then
    echo "THIEU DIEU KIEN DE CHAY:" >&2
    printf '  - %s\n' "${missing[@]}" >&2
    exit 1
fi

export PULP_PROJECT_HOME="$ROOT"
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

# --- Watchdog tang 1: thoi gian mo phong -----------------------------------
# Doc boi proc run_and_exit (sim/tcl_files/config/vsim.tcl) va boi
# wave_capture.do. Lan chay sach do duoc 18.27 ms, nen 40 ms la ~2.2x du phong.
export SIM_TIMEOUT="${SIM_TIMEOUT:-40 ms}"

# BUG CU: 'make "${@:-clean all run}"' -- trong dau nhay, gia tri mac dinh nay
# no ra MOT tu duy nhat, nen make di tim target ten 'clean all run' va bao
# 'No rule to make target'. Chay khong tham so la duong dung nhat, va no hong.
if (( $# == 0 )); then
    set -- clean all run
fi

cd "$ROOT/sw/full_system"

# --- Watchdog tang 2: thoi gian thuc ---------------------------------------
# Tang 1 khong cuu duoc truong hop vsim treo TRUOC khi nap do-file (cho
# license, ket noi mang hong...). setsid dat make vao process group rieng de
# khi het gio giet duoc ca vsim con, khong chi mot minh make.
WALL_TIMEOUT="${WALL_TIMEOUT:-1800}"
echo "RUNNER|make $* | SIM_TIMEOUT='$SIM_TIMEOUT' | WALL_TIMEOUT=${WALL_TIMEOUT}s"

setsid make "$@" &
sim_pid=$!
sim_pgid="$(ps -o pgid= -p "$sim_pid" 2>/dev/null | tr -d ' ' || true)"

(
    for ((i = 0; i < WALL_TIMEOUT; i++)); do
        kill -0 "$sim_pid" 2>/dev/null || exit 0
        sleep 1
    done
    echo "RUNNER|WALL TIMEOUT sau ${WALL_TIMEOUT}s - giet process group $sim_pgid" >&2
    [[ -n "$sim_pgid" ]] && kill -TERM -"$sim_pgid" 2>/dev/null || true
    sleep 10
    [[ -n "$sim_pgid" ]] && kill -KILL -"$sim_pgid" 2>/dev/null || true
) &
watchdog_pid=$!

rc=0
wait "$sim_pid" || rc=$?
kill "$watchdog_pid" 2>/dev/null || true
wait "$watchdog_pid" 2>/dev/null || true

case $rc in
    0)   echo "RUNNER|PASS (exit 0)" ;;
    124) echo "RUNNER|TIMEOUT mo phong - testbench khong ket thuc trong '$SIM_TIMEOUT'" >&2 ;;
    143|137) echo "RUNNER|BI GIET boi watchdog wall-clock (${WALL_TIMEOUT}s)" >&2; rc=124 ;;
    *)   echo "RUNNER|FAIL (exit $rc)" >&2 ;;
esac
exit $rc
