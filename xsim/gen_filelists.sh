#!/usr/bin/env bash
# Sinh file list cho Vivado XSim tu Bender.
# Chay tu thu muc goc cua repo pulp:   ./xsim/gen_filelists.sh
#
# Bien moi truong:
#   BENDER=<path>   dung bender khac (mac dinh ./bender)
#   WITH_TRACE=1    giu +define+TRACE_EXECUTION va RVFI (mac dinh: bo)
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/xsim"
BENDER="${BENDER:-$ROOT/bender}"
TARGETS=(-t rtl -t test)

[ -x "$BENDER" ] || { echo "Khong tim thay $BENDER - chay 'make checkout' truoc"; exit 1; }
echo "bender: $("$BENDER" --version)"

# ---------------------------------------------------------------------------
# Chon subcommand.
#   bender <  0.30 : 'flist' co ca +incdir+ / +define+
#   bender >= 0.30 : 'flist' chi con duong dan; phai dung 'flist-plus'
# ---------------------------------------------------------------------------
if "$BENDER" script --help 2>&1 | grep -q 'flist-plus'; then
  FMT=flist-plus
else
  FMT=flist
fi
echo "format: $FMT"

# ---------------------------------------------------------------------------
# Doan duong dan that tu duong dan sai trong manifest.
# ---------------------------------------------------------------------------
resolve_typo() {
  local p="$1" c
  [ -f "$p" ] && { printf '%s' "$p"; return; }
  for c in "${p}v" "${p%,}" "${p%.*}.sv" "${p%.*}.v" "${p%.*}.vhd" "${p%.*}.svh"; do
    [ -f "$c" ] && { printf '%s' "$c"; return; }
  done
  printf ''
}

# ---------------------------------------------------------------------------
# bender >= 0.29 kiem tra su ton tai cua moi file trong manifest va bao [E31].
# Vai IP upstream co typo (common_cells: clk_div.s ; adv_dbg_if: adbg_axi_biu.sv,).
# Vong lap nay tu tao symlink cho tung file thieu roi thu lai.
# ---------------------------------------------------------------------------
heal_missing_files() {
  local tries=0 err missing cand
  while [ $tries -lt 20 ]; do
    if err=$("$BENDER" script "$FMT" "${TARGETS[@]}" 2>&1 >/dev/null); then
      return 0
    fi
    missing=$(printf '%s' "$err" | sed 's/\x1b\[[0-9;]*m//g' \
              | sed -n 's/.*\[E31\] File \(.*\) doesn.t exist.*/\1/p' | head -1)
    if [ -z "$missing" ]; then
      echo "bender loi (khong phai E31):" >&2
      printf '%s\n' "$err" | tail -20 >&2
      return 1
    fi
    cand="$(resolve_typo "$missing")"
    if [ -z "$cand" ]; then
      echo "Khong tim duoc file thay the cho: $missing" >&2; return 1
    fi
    echo "  [fix] $(basename "$missing") -> $(basename "$cand")"
    ln -sf "$(basename "$cand")" "$missing"
    tries=$((tries+1))
  done
  echo "Qua nhieu file thieu, dung lai." >&2; return 1
}

echo "=== kiem tra manifest ==="
heal_missing_files || exit 1

# ---------------------------------------------------------------------------
RAW="$OUT/all.flist"
"$BENDER" script "$FMT" "${TARGETS[@]}" > "$RAW" || exit 1

# incdir (co the rong voi bender cu -> khong phai loi)
grep '^+incdir+' "$RAW" | sed 's/^+incdir+//' > "$OUT/incdirs.txt" || true

# define: bo TRACE_EXECUTION / RVFI o lan build dau (keo theo class + mailbox
# trong riscv_tracer / ibex, XSim 2019.1 rat de vo o day)
if [ "${WITH_TRACE:-0}" = "1" ]; then
  grep '^+define+' "$RAW" | sed 's/^+define+//' > "$OUT/defines.txt" || true
else
  grep '^+define+' "$RAW" | sed 's/^+define+//' \
    | grep -vE '^(TRACE_EXECUTION|RVFI)' > "$OUT/defines.txt" || true
fi
# luon co, khong phu thuoc bender
for d in TARGET_RTL TARGET_TEST TARGET_SIMULATION; do
  grep -qx "$d" "$OUT/defines.txt" 2>/dev/null || echo "$d" >> "$OUT/defines.txt"
done

# ---------------------------------------------------------------------------
# Cac file DPI-only: bo ra khoi lan build dau (khong duoc instantiate khi
# ENABLE_DPI / ENABLE_EXTERNAL_DRIVER / TARGET_RT_DPI = 0)
#   - DPI-only (khong duoc instantiate khi cac ENABLE_* = 0)
#   - testbench rieng cua tung IP phu thuoc (.bender/.../<ip>/test/...):
#     khong lien quan toi tb_pulp, va la noi tap trung class/randomize ma
#     XSim 2019.1 hay vo. Giu nguyen rtl/tb/ cua chinh repo pulp.
EXCLUDE_RE='dpi_models/dpi_models\.sv|tb_driver/tb_driver\.sv|rtl/tb/SimDTM\.sv|/checkouts/[^/]+/test/'

: > "$OUT/vhdl.f"
: > "$OUT/sv.f"

{
  while read -r d; do [ -n "$d" ] && echo "-d $d"; done < "$OUT/defines.txt"
  while read -r d; do [ -n "$d" ] && echo "-i $d"; done < "$OUT/incdirs.txt"
} >> "$OUT/sv.f"

skipped=0
while IFS= read -r f; do
  [ -z "$f" ] && continue
  case "$f" in +*|-*) continue ;; esac
  echo "$f" | grep -Eq "$EXCLUDE_RE" && continue
  if [ ! -f "$f" ]; then
    r="$(resolve_typo "$f")"
    if [ -z "$r" ]; then
      echo "  [bo qua] khong tim thay: $f" >&2; skipped=$((skipped+1)); continue
    fi
    f="$r"
  fi
  case "$f" in
    *.vhd|*.vhdl) echo "$f" >> "$OUT/vhdl.f" ;;
    *)            echo "$f" >> "$OUT/sv.f"   ;;
  esac
done < "$RAW"

if [ -f "$OUT/patch_sources.py" ] && command -v python3 >/dev/null; then
  echo "=== va nguon cho XSim ==="
  python3 "$OUT/patch_sources.py" "$OUT/sv.f"
fi

echo "=== ket qua ==="
echo "sv.f    : $(grep -c '^/' "$OUT/sv.f")  file"
echo "vhdl.f  : $(wc -l < "$OUT/vhdl.f")  file"
echo "incdir  : $(wc -l < "$OUT/incdirs.txt")"
echo "define  : $(tr '\n' ' ' < "$OUT/defines.txt")"
[ "$skipped" -gt 0 ] && echo "CANH BAO: bo qua $skipped file khong ton tai"
exit 0
