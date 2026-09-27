#!/usr/bin/env bash
# Moi truong GVSoC + PULP SDK. Dung: source sw/gvsoc/env.sh
#
# /usr/bin phai dung truoc miniforge va Xilinx SDK trong PATH: python3 cua
# miniforge thieu prettytable/pyelftools, cmake 3.3.2 cua Xilinx loi libidn.
export GVSOC_HOME="${GVSOC_HOME:-$HOME/gvsoc}"
export PULP_SDK_HOME_GV="${PULP_SDK_HOME_GV:-$HOME/pulp-sdk}"
export PULP_RISCV_GCC_TOOLCHAIN="${PULP_RISCV_GCC_TOOLCHAIN:-/opt/pulp-toolchain}"

PATH="$(echo "$PATH" | tr ':' '\n' | grep -vE 'miniforge3|/SDK/2019.1' | paste -sd:)"
export PATH="/usr/bin:$PATH"
hash -r

source "$GVSOC_HOME/sourceme.sh" >/dev/null
source "$PULP_SDK_HOME_GV/configs/pulp-open.sh"
