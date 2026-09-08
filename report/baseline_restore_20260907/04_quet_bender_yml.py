#!/usr/bin/env python3
"""Quet moi Bender.yml trong .bender/git/checkouts/ tim duong dan file khong ton tai.

Ly do ton tai: bender 0.31.0 dung ngay khi gap duong dan hong va chi bao MOT loi
mot lan, nen sua theo kieu chay-loi-sua rat cham. Script nay liet ke het mot luot.

Chay: /usr/bin/python3 report/baseline_restore_20260907/04_quet_bender_yml.py
"""
import glob
import os
import re
import sys

EXT = re.compile(r"\.(sv|svh|v|vhd|vhdl)\b")


def main() -> int:
    bad = []
    for d in sorted(glob.glob(".bender/git/checkouts/*")):
        y = os.path.join(d, "Bender.yml")
        if not os.path.exists(y):
            continue
        for i, line in enumerate(open(y, errors="replace"), 1):
            s = line.strip()
            if not s.startswith("- "):
                continue
            # bo comment cuoi dong va dau nhay; bo qua dong co bien/wildcard
            p = s[2:].split(" #")[0].strip().strip('"').strip("'")
            if not EXT.search(p) or "$" in p or "*" in p:
                continue
            if not os.path.exists(os.path.join(d, p)):
                bad.append((os.path.basename(d), i, p))

    for name, line_no, path in bad:
        print(f"{name:42s} line {line_no:<5d} {path!r}")
    print(f"\nTONG: {len(bad)} duong dan hong")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
