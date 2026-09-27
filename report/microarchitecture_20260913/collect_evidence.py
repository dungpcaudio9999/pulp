#!/usr/bin/env python3
"""Read-only deterministic inventory, not an RTL parser or simulation runner."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "report/microarchitecture_20260913"


def git(path, *args):
    return subprocess.check_output(["git", "-C", str(path), *args], text=True).strip()


def main():
    docs = sorted((ROOT / "doc/dungpc/master_analysis/microarchitecture").glob("micro_*.md"))
    inputs = set(docs)
    for doc in docs:
        for url in re.findall(r'\]\(([^)]+)\)', doc.read_text()):
            if "://" in url:
                continue
            path = (doc.parent / url.split("#", 1)[0]).resolve()
            if path.suffix in {".sv", ".svh", ".v", ".tcl", ".sh"}:
                inputs.add(path)
    for relative in [
        "sim/compile.tcl", "rtl/tb/tb_pulp.sv", "rtl/pulp/pulp.sv",
        "rtl/pulp/soc_domain.sv", "sw/full_system/run_sim.sh",
        ".bender/git/checkouts/pulp_soc-c519334bd3ac5582/rtl/pulp_soc/pulp_soc.sv",
        ".bender/git/checkouts/pulp_soc-c519334bd3ac5582/rtl/pulp_soc/tcdm_demux.sv",
        ".bender/git/checkouts/pulp_soc-c519334bd3ac5582/rtl/pulp_soc/l2_ram_multi_bank.sv",
        ".bender/git/checkouts/pulp_soc-c519334bd3ac5582/rtl/pulp_soc/interleaved_crossbar.sv",
        ".bender/git/checkouts/cluster_interconnect-abcda71a83f4333c/rtl/tcdm_interconnect/addr_dec_resp_mux.sv",
        ".bender/git/checkouts/cluster_interconnect-abcda71a83f4333c/rtl/tcdm_interconnect/xbar.sv",
        ".bender/git/checkouts/common_cells-f18d75f6d6d026a5/src/rr_arb_tree.sv",
    ]:
        inputs.add(ROOT / relative)
    inputs.update(REPORT / name for name in [
        "tb_fc_lsu.sv", "run_lsu.sh", "run.log", "compile.log", "lsu.vcd",
        "collect_evidence.py", "README.md",
    ])
    compile_text = (ROOT / "sim/compile.tcl").read_text()
    entries = []
    deps = {}
    for path in sorted(inputs):
        relative = path.relative_to(ROOT)
        data = path.read_bytes()
        entries.append({
            "path": str(relative), "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data), "lines": len(data.splitlines()),
            "explicit_compile_tcl_entry": f'"$ROOT/{relative}"' in compile_text,
        })
        if relative.parts[:3] == (".bender", "git", "checkouts"):
            dep = relative.parts[3]
            if dep not in deps:
                base = ROOT.joinpath(*relative.parts[:4])
                deps[dep] = {"head": git(base, "rev-parse", "HEAD"),
                             "tracked_status": git(base, "status", "--short", "--untracked-files=no").splitlines()}
    print(json.dumps({
        "scope": "2026-09-13: FC pipeline/LSU to SoC, static analysis plus isolated LSU simulation",
        "root_head": git(ROOT, "rev-parse", "HEAD"),
        "limitations": "Direct evidence only; no transitive elaboration proof or integrated CPU/SoC simulation.",
        "dependencies": deps, "files": entries,
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
