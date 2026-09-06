# Môi trường theo doc/dungpc/nhat-ky-mo-phong-pulp-questasim.md, Phụ lục B
# Rời conda (script không interactive nên không có hàm 'conda deactivate')
export PATH="$(echo "$PATH" | tr ':' '\n' | grep -v miniforge3 | paste -sd:)"
hash -r

export PULP_PROJECT_HOME="$HOME/ndmoney4porche/projects/pulp"
export QUESTA_HOME="$HOME/questasim"
export PULP_RISCV_GCC_TOOLCHAIN="$HOME/ndmoney4porche/tools/v1.0.16-pulp-riscv-gcc-ubuntu-16"

export PULP_SDK_HOME="$PULP_PROJECT_HOME/pulp-runtime"
export PULP_RUNTIME_HOME="$PULP_PROJECT_HOME/pulp-runtime"
export PULP_RISCV_GCC_TOOLCHAIN_CI="$PULP_RISCV_GCC_TOOLCHAIN"
export CROSS_COMPILE="$PULP_RISCV_GCC_TOOLCHAIN/bin/riscv32-unknown-elf-"
export PATH="$PULP_RISCV_GCC_TOOLCHAIN/bin:$QUESTA_HOME/bin:$PATH"
export LD_LIBRARY_PATH="$PULP_RISCV_GCC_TOOLCHAIN/compat-libs/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"

export LM_LICENSE_FILE=27001@localhost
export MGLS_LICENSE_FILE=27001@localhost

ulimit -n 4096 2>/dev/null || true

cd "$PULP_PROJECT_HOME"
source setup/vsim.sh
# BẮT BUỘC: đặt PULPRT_HOME/PULPRT_TARGET. Thiếu nó thì rules/pulp.mk dùng
# '-include' nên im lặng không nạp target nào -> "No rule to make target 'clean'"
source pulp-runtime/configs/pulp.sh
# phải export lại: setup/vsim.sh không giữ hai biến này
export PULP_SDK_HOME="$PULP_PROJECT_HOME/pulp-runtime"
export PULP_RUNTIME_HOME="$PULP_PROJECT_HOME/pulp-runtime"
