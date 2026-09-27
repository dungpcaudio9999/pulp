#!/usr/bin/env python3
"""So sanh ket qua ubench_rt giua GVSoC va RTL (Questa).

Doc cac dong 'CSV,<test>,<tham so>,<core>,<k>=<v>,...' tu hai log. Log RTL co
tien to '# [STDOUT-CLxx_PEy] ' truoc moi dong printf; tien to nay duoc bo di.
In bang Markdown: cycle hai ben, ti le GVSoC/RTL, va cac counter chi RTL co
(ld_ext_cyc, tcdm_cont) de thay cho GVSoC bo sot.

Dung: compare_ubench.py gvsoc.log rtl.log
"""
import argparse
import re

PREFIX = re.compile(r'^#?\s*(\[STDOUT-[^\]]*\]\s*)?')


def load(path):
    rows = {}
    with open(path, errors='replace') as fd:
        for raw in fd:
            line = PREFIX.sub('', raw.strip())
            if not line.startswith('CSV,'):
                continue
            f = line.split(',')
            key = (f[1], int(f[2]), int(f[3]))
            rows[key] = {k: int(v) for k, v in (x.split('=') for x in f[4:])}
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('gvsoc')
    ap.add_argument('rtl')
    ap.add_argument('--all-cores', action='store_true',
                    help='in moi core cua phep thu nhieu core (mac dinh chi core 0)')
    args = ap.parse_args()

    gv, rtl = load(args.gvsoc), load(args.rtl)
    keys = [k for k in gv if k in rtl and (args.all_cores or k[2] == 0)]
    only = sorted(set(gv) ^ set(rtl))

    print('| Test | Tham so | Core | Cycle GVSoC | Cycle RTL | GVSoC/RTL | Lenh GVSoC / RTL '
          '| ld_stall GVSoC / RTL | imiss GVSoC / RTL | ld_ext_cyc RTL | tcdm_cont RTL |')
    print('|---|---|---|---|---|---|---|---|---|---|---|')
    for k in keys:
        g, r = gv[k], rtl[k]
        # barrier_8core co them 'timer' (tong thoi gian); dung no neu co
        cg, cr = g.get('timer', g['cycles']), r.get('timer', r['cycles'])
        ratio = f'{cg / cr:.2f}' if cr else '-'
        print(f'| {k[0]} | {k[1]} | {k[2]} | {cg} | {cr} | {ratio} '
              f'| {g["instr"]} / {r["instr"]} | {g["ld_stall"]} / {r["ld_stall"]} '
              f'| {g["imiss"]} / {r["imiss"]} | {r["ld_ext_cyc"]} | {r["tcdm_cont"]} |')
    if only:
        print('\nChi co o mot ben:', ', '.join(f'{t}/{p}/{c}' for t, p, c in only))


if __name__ == '__main__':
    main()
