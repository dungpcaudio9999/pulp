#!/usr/bin/env python3
"""In cac dong 'CSV,...' cua ubench / ubench_rt / icache_sweep thanh bang de doc.

Doc duoc log GVSoC va log RTL (bo tien to '# [STDOUT-CLxx_PEy] ').
Cot CPI = cycles / instr.

Dung:
  csv_table.py <log>                  # chi core 0
  csv_table.py <log> --all-cores
  csv_table.py <log> --cols cycles,instr,imiss
"""
import argparse
import re

PREFIX = re.compile(r'^#?\s*(\[STDOUT-[^\]]*\]\s*)?')
DEFAULT_COLS = 'cycles,instr,ld_stall,imiss,ld_ext_cyc,tcdm_cont'


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('log')
    ap.add_argument('--all-cores', action='store_true')
    ap.add_argument('--cols', default=DEFAULT_COLS)
    args = ap.parse_args()
    cols = args.cols.split(',')

    rows = []
    with open(args.log, errors='replace') as fd:
        for raw in fd:
            line = PREFIX.sub('', raw.strip())
            if not line.startswith('CSV,'):
                continue
            f = line.split(',')
            if not args.all_cores and f[3] != '0':
                continue
            kv = dict(x.split('=') for x in f[4:])
            cyc = int(kv.get('timer', kv.get('cycles', 0)))
            ins = int(kv.get('instr', 0))
            rows.append([f[1], f[2], f[3]] + [kv.get(c, '-') for c in cols]
                        + [f'{cyc / ins:.2f}' if ins else '-'])

    head = ['test', 'param', 'core'] + cols + ['CPI']
    width = [max(len(str(r[i])) for r in rows + [head]) for i in range(len(head))]
    fmt = '  '.join('{:<%d}' % width[0] if i == 0 else '{:>%d}' % w
                    for i, w in enumerate(width))
    print(fmt.format(*head))
    for r in rows:
        print(fmt.format(*r))


if __name__ == '__main__':
    main()
