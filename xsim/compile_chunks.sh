#!/usr/bin/env bash
# Bien dich sv.f theo tung khoi nho de khoanh vung cho treo / cho loi.
# Thu tu file duoc giu nguyen, nen ket qua giong het bien dich mot lan.
#
#   ./xsim/compile_chunks.sh [so_file_moi_khoi] [timeout_giay_moi_khoi]
# vi du:
#   ./xsim/compile_chunks.sh 25 300
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKDIR="$ROOT/xsim/work"
SVF="$ROOT/xsim/sv.f"
CHUNK="${1:-25}"
TMO="${2:-300}"

command -v xvlog >/dev/null || { echo "Chua source settings64.sh cua Vivado"; exit 1; }
[ -f "$SVF" ] || { echo "Khong thay $SVF"; exit 1; }

# stdbuf ep xvlog xuat theo dong, nho vay out.txt van co noi dung khi bi
# timeout giet -> biet duoc file cuoi cung no dang xu ly.
BUF=""
command -v stdbuf >/dev/null && BUF="stdbuf -oL -eL"

mkdir -p "$WORKDIR"; cd "$WORKDIR"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# Tach phan dau (-d / -i) va danh sach file
grep -E '^[-+]' "$SVF" > "$TMP/header.f"
grep '^/'      "$SVF" > "$TMP/files.txt"

TOTAL=$(wc -l < "$TMP/files.txt")
echo "Tong $TOTAL file, moi khoi $CHUNK file, timeout $TMO giay/khoi"
echo

i=0
n=0
while [ $i -lt "$TOTAL" ]; do
  n=$((n+1))
  first=$((i+1))
  last=$((i+CHUNK)); [ $last -gt "$TOTAL" ] && last=$TOTAL

  cp "$TMP/header.f" "$TMP/chunk.f"
  sed -n "${first},${last}p" "$TMP/files.txt" >> "$TMP/chunk.f"

  printf "[khoi %3d] file %4d-%4d ... " "$n" "$first" "$last"
  start=$SECONDS
  timeout "$TMO" $BUF xvlog --sv --work work --relax -f "$TMP/chunk.f" \
      > "$TMP/out.txt" 2>&1
  rc=$?
  dur=$((SECONDS-start))

  if [ $rc -eq 124 ]; then
    echo "TREO sau ${TMO}s"
    echo
    echo "File trong khoi nay:"
    sed -n "${first},${last}p" "$TMP/files.txt"
    echo
    echo "File cuoi cung xvlog dang xu ly:"
    grep 'Analyzing' "$TMP/out.txt" | tail -3
    echo
    echo "20 dong cuoi cua output:"
    tail -20 "$TMP/out.txt"
    exit 124
  elif [ $rc -ne 0 ]; then
    echo "LOI (${dur}s)"
    echo
    grep -i 'error' "$TMP/out.txt" | head -20
    exit $rc
  fi
  echo "ok (${dur}s)"

  i=$last
done

echo
echo "Tat ca $TOTAL file da bien dich xong."
