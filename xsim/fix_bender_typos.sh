#!/usr/bin/env bash
# Va lai 2 typo upstream trong manifest cua IP (bender >= 0.29 bao [E31]).
# Chay tu thu muc goc repo pulp, sau khi './bender checkout' da xong.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

fix() {  # $1 = duong dan sai, $2 = ten file that
  local bad="$1" good="$2"
  [ -e "$bad" ] && { echo "  da co: $bad"; return; }
  [ -f "$(dirname "$bad")/$good" ] || { echo "  bo qua (khong thay $good): $bad"; return; }
  ln -sf "$good" "$bad"
  echo "  fix: $bad -> $good"
}

echo "common_cells (typo: clk_div.s)"
for d in .bender/git/checkouts/common_cells-*/src/deprecated; do
  [ -d "$d" ] && fix "$d/clk_div.s" clk_div.sv
done

echo "adv_dbg_if (typo: adbg_axi_biu.sv,)"
for d in .bender/git/checkouts/adv_dbg_if-*/rtl; do
  [ -d "$d" ] && fix "$d/adbg_axi_biu.sv," adbg_axi_biu.sv
done

echo "Xong. Chay lai: ./bender script flist -t rtl -t test >/dev/null && echo OK"