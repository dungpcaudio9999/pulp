#!/usr/bin/env python3
"""Snapshot direct analysis/bench inputs and validate Markdown file/line links.
Not an RTL elaborator, source-closure proof, or simulator.
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
REPORT = Path(__file__).resolve().parent
DEPS = ROOT / '.bender/git/checkouts'


def git(where, *args):
    return subprocess.check_output(['git', '-C', str(where), *args], text=True).strip()


def main():
    docs = sorted((ROOT / 'doc/dungpc/master_analysis/microarchitecture').glob('micro_*.md'))
    docs += [ROOT / 'doc/dungpc/master_analysis/architecture/DEEP_DIVE_INDEX.md',
             ROOT / 'doc/dungpc/master_analysis/soc_rtl/soc_03_udma_debug_cluster_rtl.md', REPORT / 'README.md']
    inputs = set(docs)
    checked = 0
    for doc in docs:
        for url in re.findall(r'\]\(([^)]+)\)', doc.read_text()):
            if '://' in url or url.startswith('#'):
                continue
            target, _, anchor = url.partition('#')
            path = (doc.parent / target).resolve()
            if not path.exists():
                raise RuntimeError(f'Broken link: {doc.relative_to(ROOT)} -> {url}')
            if re.fullmatch(r'L\d+', anchor):
                line = int(anchor[1:])
                if not (0 < line <= len(path.read_text().splitlines())):
                    raise RuntimeError(f'Invalid line anchor: {url}')
            checked += 1
            if path.suffix in {'.sv', '.svh', '.v', '.tcl', '.sh', '.h', '.c'}:
                inputs.add(path)
    # Additional explicit compilation sources/headers used by component benches.
    extra = {
        'common_cells-f18d75f6d6d026a5': [
            'src/cf_math_pkg.sv', 'src/lzc.sv', 'src/rr_arb_tree.sv',
            'src/gray_to_binary.sv', 'src/binary_to_gray.sv',
            'include/common_cells/registers.svh', 'include/common_cells/assertions.svh'],
        'cv32e40p-0a3884e05ea5a482': [
            'rtl/include/apu_core_package.sv', 'rtl/include/apu_macros.sv'],
        'pulp_soc-c519334bd3ac5582': ['rtl/components/pulp_interfaces.sv'],
        'mchan-1903412f92cb4b0c': ['rtl/include/mchan_defines.sv'],
        'cluster_interconnect-abcda71a83f4333c': [
            'rtl/tcdm_interconnect/xbar.sv', 'rtl/tcdm_interconnect/addr_dec_resp_mux.sv'],
    }
    for package, paths in extra.items():
        inputs.update(DEPS / package / path for path in paths)
    inputs.update(ROOT / p for p in ['rtl/includes/pulp_soc_defines.sv',
                                    'sim/compile.tcl', 'rtl/tb/tb_pulp.sv',
                                    'sw/full_system/run_sim.sh'])
    inputs.update(p for p in REPORT.iterdir() if p.is_file()
                  and p.name not in {'evidence.json', 'build_directory.txt'})
    entries, deps = [], {}
    for p in sorted(inputs):
        data = p.read_bytes()
        rel = p.relative_to(ROOT)
        entries.append({'path': str(rel), 'sha256': hashlib.sha256(data).hexdigest(),
                        'bytes': len(data), 'lines': len(data.splitlines())})
        if rel.parts[:3] == ('.bender', 'git', 'checkouts'):
            package = rel.parts[3]
            if package not in deps:
                base = DEPS / package
                deps[package] = {'head': git(base, 'rev-parse', 'HEAD'),
                                 'tracked_status': git(base, 'status', '--short', '--untracked-files=no').splitlines()}
    results = {}
    for bench, marker in [('control', 'PASS control: 31 checks'),
                          ('cdc', 'PASS CDC: sent=64 received=64'),
                          ('xbar', 'PASS xbar: 16 accepted requests'),
                          ('dma_synch', 'PASS DMA synch: 12 checks')]:
        log = (REPORT / f'{bench}_run.log').read_text()
        if marker not in log or 'FAIL' in log or 'Assertion failed' in log:
            raise RuntimeError(f'Missing clean PASS marker: {bench}')
        results[bench] = [s for s in log.splitlines() if s.startswith('PASS')]
    print(json.dumps({'scope': '2026-09-13 continuation M4-M7 static + M8 component simulation',
                      'limitations': 'No new full-system elaboration/simulation; no physical CDC or numerical FP sign-off.',
                      'root_head': git(ROOT, 'rev-parse', 'HEAD'),
                      'tool': (REPORT / 'tool_version.txt').read_text().strip(),
                      'markdown_links_checked': checked, 'results': results,
                      'dependencies': deps, 'files': entries}, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
