#!/usr/bin/env python3
"""Tong hop cycle theo ham tu trace lenh cua gvsoc (--trace=<core>/insn).

Moi dong trace co dang:
  <thoi gian ps>: <cycle>: [<duong dan>] <ham>:<dong> <mode> <pc> <lenh> ...
Cycle cua mot lenh = cycle cua dong ke tiep tru cycle cua no (gom ca stall).
Dong cuoi cung khong co dong ke tiep nen bi bo qua.

Dung: func_profile.py pe0.log [--top 20]
"""
import argparse
import collections
import re

LINE = re.compile(r'^\s*\d+:\s*(\d+):\s*\[[^\]]*\]\s*(\S+?):\d+\s')
ANSI = re.compile(r'\x1b\[[0-9;]*m')


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('trace')
    ap.add_argument('--top', type=int, default=20)
    args = ap.parse_args()

    cycles = collections.Counter()
    insns = collections.Counter()
    prev = None  # (cycle, ham)
    with open(args.trace, errors='replace') as fd:
        for raw in fd:
            m = LINE.match(ANSI.sub('', raw))
            if not m:
                continue
            cyc, func = int(m.group(1)), m.group(2)
            if prev is not None:
                cycles[prev[1]] += cyc - prev[0]
                insns[prev[1]] += 1
            prev = (cyc, func)

    total = sum(cycles.values()) or 1
    print(f'{"ham":40s} {"cycle":>10s} {"%":>6s} {"lenh":>9s} {"CPI":>6s}')
    for func, c in cycles.most_common(args.top):
        n = insns[func]
        print(f'{func[:40]:40s} {c:10d} {100 * c / total:6.1f} {n:9d} {c / n:6.2f}')
    print(f'{"TONG":40s} {total:10d} {100.0:6.1f} {sum(insns.values()):9d}')


if __name__ == '__main__':
    main()
