#!/usr/bin/env bash
# Tái áp dụng các patch cần thiết cho Vivado XSim sau mỗi lần `bender checkout`.
# Idempotent: chạy lại nhiều lần không hỏng gì.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

FPNEW="$(ls -d .bender/git/checkouts/fpnew-* 2>/dev/null | head -1)"
if [[ -z "$FPNEW" ]]; then
    echo "SKIP: chưa có checkout fpnew (chạy 'make checkout' trước)"
    exit 0
fi

F="$FPNEW/src/fpnew_pkg.sv"
if grep -q "XSim: no field access on const-array element" "$F"; then
    echo "OK: fpnew_pkg.sv đã được patch, bỏ qua"
else
    cp "$F" "$F.before_xsim_fpencodings_patch"
    patch -p1 -d "$FPNEW" < xsim/patches/0002-fpnew_pkg-xsim-const-array-field-access.patch
    echo "OK: đã patch $F"
fi

# rtl/tb/*.sv cần `const ref` cho XSim — các file này do repo quản lý nên chỉ cảnh báo.
for TB in rtl/tb/jtag_pkg.sv rtl/tb/dbg_pkg.sv rtl/tb/pulp_tap_pkg.sv; do
    if ! grep -q "const ref logic s_tdo" "$TB" 2>/dev/null; then
        echo "CẢNH BÁO: $TB thiếu patch 'const ref' — XSim sẽ báo lỗi ref argument"
    fi
done
