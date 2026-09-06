#!/usr/bin/env bash
# Compile + elaborate + run tb_pulp bang Vivado XSim.
# Dung tu thu muc goc repo:   ./xsim/run.sh [compile|elab|sim|all] [gui]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKDIR="$ROOT/xsim/work"        # noi chua xsim.dir
STIM="${STIM:-$ROOT/xsim/vectors/stim.txt}"
SNAP=tb_pulp_snap
STEP="${1:-all}"
GUI="${2:-}"

command -v xvlog >/dev/null || { echo "Chua source settings64.sh cua Vivado"; exit 1; }

mkdir -p "$WORKDIR"
cd "$WORKDIR"

# xvlog/xvhdl tu ghi log cua chung (xvlog.log, xvhdl.log) trong thu muc
# hien tai. KHONG dung `| tee xvlog.log` - se co hai tien trinh cung ghi
# vao mot file. stdbuf ep xuat theo dong de theo doi tien do truc tiep.
BUF=""
command -v stdbuf >/dev/null && BUF="stdbuf -oL -eL"

clean() {
  echo "=== xoa thu vien cu ==="
  rm -rf "$WORKDIR/xsim.dir" "$WORKDIR"/*.log "$WORKDIR"/*.pb "$WORKDIR"/*.jou
}

compile() {
  echo "=== xvhdl (16 file FLL) ==="
  $BUF xvhdl --work work --relax -f "$ROOT/xsim/vhdl.f"

  echo "=== xvlog (SystemVerilog) ==="
  # --relax noi long mot so kiem tra LRM ma XSim von rat kho tinh
  $BUF xvlog --sv --work work --relax -f "$ROOT/xsim/sv.f"
}

elab() {
  echo "=== xelab ==="
  xelab work.tb_pulp \
    -s $SNAP \
    --relax --debug typical --mt 8 \
    --timescale 1ps/1ps \
    -generic_top "BAUDRATE=115200" \
    -generic_top "USE_SDVT_CPI=0" \
    -generic_top "ENABLE_DEV_DPI=0" \
    -L work
}

sim() {
  echo "=== xsim ==="
  mkdir -p vectors
  [ -f "$STIM" ] && cp -f "$STIM" vectors/stim.txt || true
  [ -f vectors/stim.txt ] || echo "CANH BAO: chua co vectors/stim.txt"
  if [ "$GUI" = "gui" ]; then
    xsim $SNAP -gui -testplusarg "stimuli=./vectors/stim.txt"
  else
    xsim $SNAP -testplusarg "stimuli=./vectors/stim.txt" -R -log xsim.log
  fi
}

case "$STEP" in
  clean)   clean ;;
  compile) compile ;;
  elab)    elab ;;
  sim)     sim ;;
  all)     clean; compile; elab; sim ;;
  *) echo "usage: $0 [clean|compile|elab|sim|all] [gui]"; exit 1 ;;
esac
