#!/usr/bin/env python3
"""Build a standalone side-by-side GVSoC/RTL execution-flow viewer."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path


ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
GVSOC_RE = re.compile(
    r"^(\d+):\s*(\d+):\s*\[([^\]]+)\]\s+"
    r"(\S+?):(\d+)\s+([A-Z])\s+([0-9a-fA-F]+)\s+(\S+)\s*(.*)$"
)
RTL_RE = re.compile(
    r"^\s*(\d+)ns\s+(\d+)\s+([0-9a-fA-F]{8})\s+"
    r"([0-9a-fA-F]{8})\s+(\S+)\s*(.*)$"
)
WRITE_RE = re.compile(r"\b([a-z][a-z0-9]*)=([0-9a-fx]{8})\b", re.I)
READ_RE = re.compile(r"\b([a-z][a-z0-9]*):([0-9a-fx]{8})\b", re.I)
PA_RE = re.compile(r"\bPA:([0-9a-fx]{8})\b", re.I)
PHASE_RE = re.compile(r"^phase(\d+)_")
IMPORTANT_LOG_RE = re.compile(
    r"FLOW\||RX string:|Received status core:|(?:^|[| ])exit_status="
    r"|SIMULATION (?:PASS|FAIL)|\bTIMEOUT\b|^# End time:",
    re.I,
)

PHASE_NAMES = {
    0: "FC + L2",
    1: "FC timer + ALU",
    2: "Launch/wait cluster",
    3: "8 PE write L1",
    4: "Barrier + cross-read",
    5: "DMA L2-L1-L2",
    6: "FC summary",
}


def memory_region(text: str) -> str:
    if not text or "x" in text.lower():
        return ""
    address = int(text, 16)
    if 0x10000000 <= address < 0x10010000:
        return "L1 / TCDM"
    if 0x1C000000 <= address < 0x1D000000:
        return "L2"
    if 0x1A000000 <= address < 0x1B000000:
        return "SoC peripheral"
    if address < 0x01000000:
        return "Cluster peripheral"
    return "Other"


def category(op: str) -> str:
    op = op.lower()
    if op in {"jal", "jalr", "c.j", "c.jal", "c.jr", "c.jalr"} or op.startswith(("b", "c.b", "p.b")):
        return "Control"
    if op == "p.elw" or op.startswith(("lw", "lh", "lb", "lbu", "p.l", "c.lw", "c.fl")):
        return "Load/event"
    if op.startswith(("sw", "sh", "sb", "p.s", "c.sw", "c.fsw")):
        return "Store"
    if op.startswith(("mul", "div", "rem")):
        return "Multiply/divide"
    if op.startswith(("csr", "mret", "wfi", "ecall")):
        return "System"
    return "ALU/other"


def values(tail: str) -> tuple[list[list[str]], list[list[str]], str, str]:
    writes = [[name, value.lower()] for name, value in WRITE_RE.findall(tail)]
    reads = [
        [name, value.lower()]
        for name, value in READ_RE.findall(tail)
        if name.lower() != "pa"
    ]
    match = PA_RE.search(tail)
    pa = match.group(1).lower() if match else ""
    args = WRITE_RE.sub("", tail)
    args = READ_RE.sub("", args)
    args = PA_RE.sub("", args)
    return writes, reads, pa, " ".join(args.split())


def parse_gvsoc(path: Path, backend: str, core: str) -> list[dict]:
    rows = []
    for raw in path.read_text(errors="replace").splitlines():
        match = GVSOC_RE.match(ANSI_RE.sub("", raw))
        if not match:
            continue
        time_ps, cycle, component, function, line, mode, pc, op, tail = match.groups()
        writes, reads, pa, args = values(tail)
        rows.append({
            "b": backend, "k": core, "t": int(time_ps), "c": int(cycle),
            "d": 0, "p": "0x" + pc.lower(), "i": "", "o": op,
            "a": args, "f": function, "s": "", "l": int(line),
            "w": writes, "r": reads, "m": "0x" + pa if pa else "",
            "mr": memory_region(pa), "g": category(op), "q": mode,
            "component": component.strip(),
        })
    add_deltas(rows)
    return rows


def addr2line(elf: Path, pcs: list[str], tool: str) -> dict[str, tuple[str, str, int]]:
    if not pcs:
        return {}
    result = subprocess.run(
        [tool, "-f", "-C", "-e", str(elf)],
        input="\n".join(pcs) + "\n", text=True, capture_output=True, check=True,
    )
    lines = result.stdout.splitlines()
    mapped = {}
    for index, pc in enumerate(pcs):
        function = lines[index * 2] if index * 2 < len(lines) else "??"
        location = lines[index * 2 + 1] if index * 2 + 1 < len(lines) else "??:0"
        source, _, line_text = location.rpartition(":")
        try:
            line = int(line_text)
        except ValueError:
            source, line = location, 0
        mapped[pc] = (function, source, line)
    return mapped


def parse_rtl(path: Path, backend: str, core: str, symbols: dict[str, tuple[str, str, int]]) -> list[dict]:
    rows = []
    for raw in path.read_text(errors="replace").splitlines():
        match = RTL_RE.match(raw)
        if not match:
            continue
        time_ns, cycle, pc_text, insn, op, tail = match.groups()
        pc = "0x" + pc_text.lower()
        function, source, line = symbols.get(pc, ("??", "", 0))
        writes, reads, pa, args = values(tail)
        rows.append({
            "b": backend, "k": core, "t": int(time_ns) * 1000, "c": int(cycle),
            "d": 0, "p": pc, "i": insn.lower(), "o": op, "a": args,
            "f": function, "s": source, "l": line, "w": writes, "r": reads,
            "m": "0x" + pa if pa else "", "mr": memory_region(pa),
            "g": category(op), "q": "RTL", "component": core,
        })
    add_deltas(rows)
    return rows


def add_deltas(rows: list[dict]) -> None:
    for index in range(1, len(rows)):
        rows[index]["d"] = rows[index]["c"] - rows[index - 1]["c"]


def focus(row: dict) -> bool:
    function = row["f"]
    return (
        function.startswith("phase")
        or function in {"main", "flow_mark", "flow_checksum", "flow_cluster_report", "flow_dma_wait"}
        # cluster_wait is deliberately omitted: its tight polling loop adds
        # tens of thousands of visually identical rows.  The wait is still
        # represented by the phase-2 cycle span and by the large delta at the
        # first instruction after the cluster returns.
        or function.startswith(("bench_cluster", "cluster_start", "cluster_entry", "synch_barrier"))
        or row["s"].endswith("flow_demo.c")
    )


def phase_spans(all_rows: dict[tuple[str, str], list[dict]]) -> list[dict]:
    spans = []
    for (backend, core), rows in sorted(all_rows.items()):
        grouped: dict[int, list[dict]] = defaultdict(list)
        for row in rows:
            match = PHASE_RE.match(row["f"])
            if match:
                grouped[int(match.group(1))].append(row)
        for phase, phase_rows in grouped.items():
            first, last = phase_rows[0], phase_rows[-1]
            spans.append({
                "backend": backend, "core": core, "phase": phase,
                "name": PHASE_NAMES.get(phase, f"Phase {phase}"),
                "firstCycle": first["c"], "lastCycle": last["c"],
                "cycles": last["c"] - first["c"],
                "firstTime": first["t"], "lastTime": last["t"],
            })
    return spans


def automatic_spans(all_rows: dict[tuple[str, str], list[dict]]) -> list[dict]:
    """Infer coarse execution phases for an ELF without phaseN_* symbols."""
    spans = []
    definitions = (
        (0, "Runtime init", "init"),
        (1, "main + UART/application", "application"),
        (2, "Runtime shutdown", "shutdown"),
        (3, "exit", "exit"),
    )
    for (backend, core), rows in sorted(all_rows.items()):
        if not rows:
            continue

        def first_index(functions: set[str], start: int) -> int | None:
            return next(
                (index for index in range(start, len(rows)) if rows[index]["f"] in functions),
                None,
            )

        start = first_index({"_start"}, 0)
        start = start if start is not None else 0
        main = first_index({"main"}, start)
        stop = first_index({"pos_init_stop"}, main if main is not None else start)
        exit_index = first_index({"exit"}, stop if stop is not None else start)
        markers = (start, main, stop, exit_index)
        if any(marker is None for marker in markers[1:]):
            # Without the common PULP runtime landmarks, a guessed timeline
            # would be misleading.  Instruction replay remains available.
            continue

        for item, (phase, name, kind) in enumerate(definitions):
            first = markers[item]
            last = markers[item + 1] if item + 1 < len(markers) else len(rows) - 1
            if first is None or last is None or last < first:
                continue
            spans.append({
                "backend": backend,
                "core": core,
                "phase": phase,
                "name": name,
                "kind": kind,
                "automatic": True,
                "firstCycle": rows[first]["c"],
                "lastCycle": rows[last]["c"],
                "cycles": rows[last]["c"] - rows[first]["c"],
                "firstTime": rows[first]["t"],
                "lastTime": rows[last]["t"],
            })
    return spans


def execution_spans(all_rows: dict[tuple[str, str], list[dict]]) -> list[dict]:
    explicit = phase_spans(all_rows)
    return explicit if explicit else automatic_spans(all_rows)


def read_log_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [
        ANSI_RE.sub("", line).strip()
        for line in path.read_text(errors="replace").splitlines()
        if line.strip()
    ]


def summarize_log(lines: list[str], mode: str = "flow") -> list[str]:
    if mode == "flow":
        selected = [line for line in lines if "FLOW|" in line]
    else:
        selected = [line for line in lines if IMPORTANT_LOG_RE.search(line)]
    if selected:
        return selected
    # UART-only GVSoC output normally contains just the application text and no
    # tagged status line.  Keep short logs verbatim; for a noisy transcript,
    # show only its tail and leave the complete text in the expandable panel.
    return lines if len(lines) <= 30 else lines[-30:]


def log_payload(path: Path, mode: str = "flow") -> dict[str, list[str]]:
    lines = read_log_lines(path)
    full = lines
    if len(lines) > 1000:
        full = [f"… đã lược {len(lines) - 1000} dòng đầu; mở raw transcript để xem toàn bộ …"] + lines[-1000:]
    return {"summary": summarize_log(lines, mode), "full": full}


HTML = r'''<!doctype html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PULP execution-flow viewer</title><style>
:root{color-scheme:dark;--bg:#0e1116;--panel:#171c24;--panel2:#202733;--line:#354052;--text:#edf2f8;--muted:#9ba9ba;--blue:#6aacf8;--green:#63d49a;--orange:#f0b86b;--red:#ef7777}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px/1.45 system-ui,sans-serif}main{max-width:1500px;margin:auto;padding:22px}h1{font-size:24px;margin:0}h2{font-size:17px;margin:0 0 10px}.header,.row{display:flex;align-items:center;gap:9px;flex-wrap:wrap}.header{justify-content:space-between;margin-bottom:16px}.pill{border:1px solid var(--line);border-radius:999px;padding:3px 9px}.ok{color:var(--green)}.muted{color:var(--muted)}code,.mono{font-family:ui-monospace,SFMono-Regular,Consolas,monospace}.stats{display:grid;grid-template-columns:repeat(5,1fr);gap:9px;margin:14px 0}.card,.stat{background:var(--panel);border:1px solid var(--line);border-radius:8px}.stat{padding:10px}.stat b{display:block;font-size:18px}.card{padding:12px;margin:12px 0}.lanes{display:grid;grid-template-columns:95px 1fr;gap:6px 8px}.lane{position:relative;height:28px;background:var(--panel2);border-radius:4px;overflow:hidden}.lane.active{outline:1px solid var(--blue)}.block{position:absolute;top:3px;height:22px;padding:0 4px;border:0;border-radius:2px;background:#315c88;color:white;font-size:11px;overflow:hidden;white-space:nowrap;cursor:pointer}.block.cluster{background:#795c2d}.block.dma,.block.application{background:#3c7659}.block.shutdown{background:#795c2d}.block.exit{background:#704154}.playhead{position:absolute;z-index:5;top:0;bottom:0;width:2px;margin-left:-1px;background:#f7fbff;box-shadow:0 0 6px #fff;pointer-events:none;transition:left 55ms linear}.playhead.reference{width:1px;background:#56d8ff;box-shadow:0 0 5px #56d8ff}.timeline-note{margin-top:8px}.timeline-legend{display:grid;grid-template-columns:repeat(2,minmax(300px,1fr));gap:5px 16px;margin:9px 0 0 103px}.legend-item{display:flex;align-items:center;gap:6px;color:var(--muted);font-size:12px}.swatch{width:10px;height:10px;flex:0 0 auto;border-radius:2px;background:#315c88}.swatch.application{background:#3c7659}.swatch.shutdown{background:#795c2d}.swatch.exit{background:#704154}.compare{width:100%;border-collapse:collapse}.compare th,.compare td{padding:6px 8px;border-bottom:1px solid var(--line);text-align:left}.compare td:not(:first-child){font-family:ui-monospace,monospace;text-align:right}.controls{display:grid;grid-template-columns:auto auto auto 120px 130px 130px 1fr;gap:7px;align-items:center}button,input,select{font:inherit;color:var(--text);background:var(--panel2);border:1px solid var(--line);border-radius:5px;padding:6px 8px}button{cursor:pointer}.viewer{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(350px,.8fr);gap:12px}.instruction{font-size:19px;margin:8px 0}.instruction b{font-size:23px;color:var(--blue)}.details{display:grid;grid-template-columns:repeat(3,1fr);gap:7px}.detail{background:var(--panel2);padding:8px;border-radius:5px}.detail small{display:block;color:var(--muted)}.chips{display:flex;gap:5px;flex-wrap:wrap}.chips code{background:var(--panel2);padding:3px 6px;border-radius:4px}.trace{max-height:500px;overflow:auto;border-top:1px solid var(--line)}.trace-row{display:grid;grid-template-columns:70px 90px 95px 1fr 155px;gap:7px;padding:5px;border-bottom:1px solid var(--line);cursor:pointer}.trace-row.active,.trace-row:hover{background:var(--panel2)}pre{white-space:pre-wrap;max-height:270px;overflow:auto;background:var(--panel2);padding:9px;border-radius:5px}.log-summary{border-left:3px solid var(--green)}details{margin:-3px 0 13px}summary{color:var(--blue);cursor:pointer}details pre{max-height:360px}.callout{border-left:3px solid var(--orange);padding:9px 12px;background:var(--panel);margin:12px 0}@media(max-width:900px){.stats{grid-template-columns:repeat(2,1fr)}.viewer{grid-template-columns:1fr}.controls{grid-template-columns:repeat(2,1fr)}.timeline-legend{grid-template-columns:1fr;margin-left:0}.trace-row{grid-template-columns:65px 85px 1fr}.trace-row span:nth-child(2),.trace-row span:last-child{display:none}}
</style></head><body><main>
<div class="header"><div><h1 id="title">PULP execution-flow viewer</h1><div class="muted" id="subtitle">C → cùng một ELF → GVSoC và RTL/Questa</div></div><div class="row"><span class="pill ok" id="gvstatus">GVSoC</span><span class="pill ok" id="rtlstatus">RTL</span></div></div>
<section class="stats" id="stats"></section>
<div class="callout"><b>Cách đọc:</b> instruction trace cho biết core thực thi gì. DMA và interconnect hoạt động tự trị sau khi CPU cấu hình, nên phải đối chiếu thêm waveform RTL; khoảng trống Δ cycle lớn thường là stall, sleep hoặc chờ phần cứng.</div>
<section class="card"><h2>Timeline GVSoC + RTL theo simulation time</h2><div class="muted" id="timeline-label"></div><div class="lanes" id="lanes"></div><div class="muted timeline-note" id="timeline-now">Playhead trắng là backend đang chọn; playhead xanh đồng bộ theo giai đoạn, không phải lockstep cycle.</div><div class="timeline-legend" id="timeline-legend"></div></section>
<section class="card"><h2>Cycle theo giai đoạn — cùng ELF</h2><table class="compare"><thead><tr><th>Giai đoạn / core</th><th>GVSoC</th><th>RTL</th><th>GVSoC/RTL</th></tr></thead><tbody id="comparison"></tbody></table></section>
<section class="card"><div class="controls"><button id="prev">Lùi</button><button id="next">Tiếp</button><button id="play">Play</button><select id="play-speed" title="Số instruction mỗi nhịp"><option value="1">1 lệnh/nhịp</option><option value="10">10 lệnh/nhịp</option><option value="100" selected>100 lệnh/nhịp</option><option value="1000">1000 lệnh/nhịp</option></select><select id="backend"></select><select id="core"></select><input id="search" placeholder="Tìm function, opcode, PC, source…"></div><div class="viewer"><div><div class="instruction"><code id="pc"></code> <b id="op"></b> <code id="args"></code></div><div class="details"><div class="detail"><small>Backend / core</small><b id="where"></b></div><div class="detail"><small>Cycle / Δ cycle</small><b id="cycle"></b></div><div class="detail"><small>Simulation time</small><b id="time"></b></div><div class="detail"><small>Function/source</small><b id="source"></b></div><div class="detail"><small>Memory</small><b id="memory"></b></div><div class="detail"><small>Category</small><b id="category"></b></div></div><h3>Register access</h3><div class="chips" id="registers"></div><div class="trace" id="trace"></div></div><div><h2>Log — GVSoC (kết quả)</h2><pre class="log-summary" id="gvlog"></pre><details><summary>Xem log GVSoC đầy đủ</summary><pre id="gvlogfull"></pre></details><h2>Log — RTL (kết quả)</h2><pre class="log-summary" id="rtllog"></pre><details><summary>Xem transcript RTL đầy đủ (bao gồm warning khởi tạo Questa)</summary><pre id="rtllogfull"></pre></details><p><a href="gvsoc/fc.log">GVSoC FC raw trace</a> · <a href="gvsoc/pe0.log">GVSoC PE0 raw trace</a> · <a href="gvsoc.log">GVSoC UART log</a><br><a href="rtl/raw/trace_core_1f_0.log">RTL FC raw trace</a> · <a href="rtl/raw/trace_core_00_0.log">RTL PE0 raw trace</a> · <a href="rtl/transcript.log">RTL raw transcript</a><br><a id="wave-link" href="rtl/wave/flow_demo.vcd.gz">RTL selected VCD</a></p></div></div></section>
</main><script>const D=__DATA__,$=id=>document.getElementById(id);let rows=[],index=0,timer=null,timelineState={maxDuration:1,ranges:{}};const fmt=n=>Number(n).toLocaleString('en-US'),esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function init(){$('title').textContent=D.title;$('subtitle').textContent=D.subtitle;$('gvstatus').textContent=D.status.GVSoC;$('rtlstatus').textContent=D.status.RTL;$('wave-link').href=D.waveLink;const raw=Object.values(D.rawCounts).reduce((a,b)=>a+b,0),shown=Object.values(D.rows).reduce((a,b)=>a+b.length,0);$('stats').innerHTML=[['ELF SHA-256',D.hash.slice(0,16)+'…'],['Raw instructions',fmt(raw)],['Displayed instructions',fmt(shown)],['GVSoC streams',Object.values(D.rawCounts).filter((_,i)=>Object.keys(D.rawCounts)[i].startsWith('GVSoC/')&&_>0).length],['RTL streams',Object.values(D.rawCounts).filter((_,i)=>Object.keys(D.rawCounts)[i].startsWith('RTL/')&&_>0).length]].map(x=>`<div class="stat"><span class="muted">${x[0]}</span><b class="mono">${x[1]}</b></div>`).join('');const bs=[...new Set(Object.keys(D.rows).filter(k=>D.rows[k].length).map(x=>x.split('/')[0]))];$('backend').innerHTML=bs.map(x=>`<option>${x}</option>`).join('');$('backend').onchange=loadCores;$('core').onchange=loadRows;$('prev').onclick=()=>go(index-1);$('next').onclick=()=>go(index+1);$('play').onclick=play;$('search').oninput=renderList;$('gvlog').textContent=D.logs.GVSoC.summary.join('\n')||'Không có dòng kết quả.';$('gvlogfull').textContent=D.logs.GVSoC.full.join('\n')||'Không có log.';$('rtllog').textContent=D.logs.RTL.summary.join('\n')||'Không có dòng kết quả.';$('rtllogfull').textContent=D.logs.RTL.full.join('\n')||'Không có log.';timeline();comparison();loadCores()}
function loadCores(){const b=$('backend').value,cores=Object.keys(D.rows).filter(x=>x.startsWith(b+'/')).map(x=>x.split('/')[1]);$('core').innerHTML=cores.map(x=>`<option>${x}</option>`).join('');loadRows()}
function loadRows(){stopPlayback();rows=D.rows[$('backend').value+'/'+$('core').value]||[];index=0;renderList();go(0)}
function go(n){if(!rows.length)return;index=Math.max(0,Math.min(rows.length-1,n));const r=rows[index];$('pc').textContent=r.p;$('op').textContent=r.o;$('args').textContent=r.a||'—';$('where').textContent=r.b+' / '+r.k;$('cycle').textContent=fmt(r.c)+' / +'+fmt(r.d);$('time').textContent=(r.t/1e6).toFixed(3)+' µs';$('source').textContent=r.f+(r.s?' · '+r.s.split('/').pop():'')+':'+r.l;$('memory').textContent=r.m?(r.m+' · '+r.mr):'—';$('category').textContent=r.g;const regs=[...r.w.map(x=>x[0]+' = 0x'+x[1]),...r.r.map(x=>x[0]+' : 0x'+x[1])];$('registers').innerHTML=regs.length?regs.map(x=>`<code>${esc(x)}</code>`).join(''):'<span class="muted">Không có</span>';renderList();updateTimelineCursor(r)}
function renderList(){const q=$('search').value.toLowerCase(),ids=[];for(let i=0;i<rows.length;i++){const r=rows[i];if(!q||`${r.f} ${r.o} ${r.p} ${r.a} ${r.s}`.toLowerCase().includes(q))ids.push(i)}const near=q?ids.slice(0,300):Array.from({length:Math.min(41,rows.length)},(_,j)=>Math.max(0,Math.min(rows.length-1,index-20+j))),trace=$('trace');trace.innerHTML=[...new Set(near)].map(i=>{const r=rows[i];return`<div class="trace-row ${i===index?'active':''}" data-i="${i}"><span>#${i}</span><span>cy ${fmt(r.c)}</span><code>${r.p}</code><span><b>${esc(r.o)}</b> ${esc(r.a)}</span><span>${esc(r.f)}:${r.l}</span></div>`}).join('');trace.querySelectorAll('[data-i]').forEach(e=>e.onclick=()=>go(+e.dataset.i));const active=trace.querySelector('.active');if(active){const box=trace.getBoundingClientRect(),row=active.getBoundingClientRect();trace.scrollTop+=row.top-box.top-(trace.clientHeight-active.clientHeight)/2}}
function stopPlayback(){if(timer){clearInterval(timer);timer=null}$('play').textContent='Play'}
function play(){if(timer){stopPlayback();return}const key=$('backend').value+'/'+$('core').value,phaseRows=D.spans.filter(x=>x.backend===$('backend').value&&x.core===$('core').value);if(phaseRows.length&&rows[index]?.t<phaseRows[0].firstTime){const first=rows.findIndex(x=>x.t>=phaseRows[0].firstTime);if(first>=0)go(first)}const step=Number($('play-speed').value)||1;$('play').textContent='Dừng';timer=setInterval(()=>index>=rows.length-1?stopPlayback():go(Math.min(rows.length-1,index+step)),60)}
function phaseClass(x){return x.kind?x.kind:x.phase===5?'dma':x.phase>=3&&x.phase<=4?'cluster':''}
function durationText(ps){const us=ps/1e6;return us>=1?us.toFixed(3)+' µs':(ps/1e3).toFixed(3)+' ns'}
function timeline(){const spans=D.spans;if(!spans.length){$('timeline-label').textContent='Không tìm được phase marker hoặc mốc runtime';$('lanes').innerHTML='<span class="muted">Dùng instruction replay bên dưới.</span>';$('timeline-legend').innerHTML='';return}const keys=[...new Set(spans.map(x=>x.backend+'/'+x.core))],ranges={};for(const key of keys){const[b,c]=key.split('/'),group=spans.filter(x=>x.backend===b&&x.core===c);ranges[key]={start:Math.min(...group.map(x=>x.firstTime)),end:Math.max(...group.map(x=>x.lastTime))};ranges[key].duration=ranges[key].end-ranges[key].start}const maxDuration=Math.max(...Object.values(ranges).map(x=>x.duration))||1;timelineState={maxDuration,ranges};$('timeline-label').textContent=`Cùng thang thời gian từ _start · full scale ${durationText(maxDuration)} · chiều rộng tuyệt đối so sánh trực tiếp hai backend`;$('lanes').innerHTML=keys.map(key=>{const[b,c]=key.split('/'),range=ranges[key],group=spans.filter(x=>x.backend===b&&x.core===c),blocks=group.map(x=>{const left=100*(x.firstTime-range.start)/maxDuration,width=100*(x.lastTime-x.firstTime)/maxDuration,cl=phaseClass(x),label=x.automatic?x.name:`P${x.phase} ${x.name}`,inside=width>=8?esc(label):'';return`<button class="block ${cl}" style="left:${left.toFixed(6)}%;width:${width.toFixed(6)}%" title="${esc(label)}: ${durationText(x.lastTime-x.firstTime)}, ${fmt(x.cycles)} cycles">${inside}</button>`}).join('');return`<b>${b} ${c}</b><div class="lane" data-lane="${key}">${blocks}<i class="playhead" style="left:0"></i></div>`}).join('');$('timeline-legend').innerHTML=spans.map(x=>{const range=ranges[x.backend+'/'+x.core],pct=100*(x.lastTime-x.firstTime)/(range.duration||1),label=x.automatic?x.name:`P${x.phase} ${x.name}`;return`<span class="legend-item"><i class="swatch ${phaseClass(x)}"></i><b>${x.backend} · ${esc(label)}</b> ${durationText(x.lastTime-x.firstTime)} · ${pct.toFixed(3)}% · ${fmt(x.cycles)} cy</span>`}).join('')}
function updateTimelineCursor(r){const source=D.spans.filter(x=>x.backend===r.b&&x.core===r.k).sort((a,b)=>a.firstTime-b.firstTime);if(!source.length)return;let phase=source.find(x=>r.t>=x.firstTime&&r.t<=x.lastTime),progress=0;if(!phase){phase=r.t<source[0].firstTime?source[0]:source[source.length-1];progress=r.t<source[0].firstTime?0:1}else progress=Math.max(0,Math.min(1,(r.t-phase.firstTime)/(phase.lastTime-phase.firstTime||1)));document.querySelectorAll('[data-lane]').forEach(lane=>{const key=lane.dataset.lane,[backend,core]=key.split('/'),target=D.spans.find(x=>x.backend===backend&&x.core===core&&x.phase===phase.phase),head=lane.querySelector('.playhead');lane.classList.toggle('active',backend===r.b&&core===r.k);if(!target){head.style.display='none';return}const range=timelineState.ranges[key],time=target.firstTime+progress*(target.lastTime-target.firstTime),left=100*(time-range.start)/timelineState.maxDuration;head.style.display='block';head.style.left=Math.max(0,Math.min(100,left)).toFixed(6)+'%';head.classList.toggle('reference',backend!==r.b||core!==r.k)});const label=phase.automatic?phase.name:`P${phase.phase} ${phase.name}`;$('timeline-now').textContent=`Đang phát ${r.b}/${r.k} · ${label} ${Math.round(progress*100)}% · playhead backend còn lại đồng bộ theo giai đoạn, không phải lockstep cycle.`}
function comparison(){const keys=[];for(const s of D.spans){const k=s.phase+'/'+s.core;if(!keys.includes(k)&&D.spans.some(x=>x.backend!==s.backend&&x.phase===s.phase&&x.core===s.core))keys.push(k)}$('comparison').innerHTML=keys.sort((a,b)=>+a.split('/')[0]-+b.split('/')[0]).map(k=>{const[p,c]=k.split('/'),g=D.spans.find(x=>x.backend==='GVSoC'&&x.phase==p&&x.core===c),r=D.spans.find(x=>x.backend==='RTL'&&x.phase==p&&x.core===c),ratio=r.cycles?(g.cycles/r.cycles).toFixed(3):'—',label=g.automatic?g.name:`P${p} ${g.name}`;return`<tr><td>${esc(label)} / ${c}</td><td>${fmt(g.cycles)}</td><td>${fmt(r.cycles)}</td><td>${ratio}</td></tr>`}).join('')}
init();</script></body></html>'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", required=True, type=Path)
    parser.add_argument("--gvsoc-fc", required=True, type=Path)
    parser.add_argument("--gvsoc-pe0", required=True, type=Path)
    parser.add_argument("--gvsoc-log", required=True, type=Path)
    parser.add_argument("--rtl-dir", required=True, type=Path)
    parser.add_argument("--rtl-log", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--addr2line", default="riscv32-unknown-elf-addr2line")
    parser.add_argument("--focus-mode", choices=("flow", "all"), default="flow")
    parser.add_argument("--log-mode", choices=("flow", "all"), default="flow")
    parser.add_argument("--title", default="PULP execution-flow viewer")
    parser.add_argument("--subtitle", default="C → cùng một ELF → GVSoC và RTL/Questa")
    parser.add_argument("--gvsoc-status", default="GVSoC PASS")
    parser.add_argument("--rtl-status", default="RTL PASS")
    parser.add_argument("--wave-link", default="rtl/wave/flow_demo.vcd.gz")
    args = parser.parse_args()

    raw: dict[tuple[str, str], list[dict]] = {
        ("GVSoC", "FC"): parse_gvsoc(args.gvsoc_fc, "GVSoC", "FC"),
        ("GVSoC", "PE0"): parse_gvsoc(args.gvsoc_pe0, "GVSoC", "PE0"),
    }

    rtl_files = [(args.rtl_dir / "trace_core_1f_0.log", "FC")]
    rtl_files += [(args.rtl_dir / f"trace_core_00_{core}.log", f"PE{core}") for core in range(8)]
    pc_set = set()
    for path, _ in rtl_files:
        for line in path.read_text(errors="replace").splitlines():
            match = RTL_RE.match(line)
            if match:
                pc_set.add("0x" + match.group(3).lower())
    symbols = addr2line(args.elf, sorted(pc_set), args.addr2line)
    for path, core in rtl_files:
        raw[("RTL", core)] = parse_rtl(path, "RTL", core, symbols)

    focused = {}
    raw_counts = {}
    for key, rows in raw.items():
        name = "/".join(key)
        raw_counts[name] = len(rows)
        focused[name] = rows if args.focus_mode == "all" else [row for row in rows if focus(row)]

    hash_value = subprocess.run(
        ["sha256sum", str(args.elf)], capture_output=True, text=True, check=True
    ).stdout.split()[0]
    payload = {
        "title": args.title,
        "subtitle": args.subtitle,
        "status": {"GVSoC": args.gvsoc_status, "RTL": args.rtl_status},
        "waveLink": args.wave_link,
        "hash": hash_value,
        "rawCounts": raw_counts,
        "rows": focused,
        "spans": execution_spans(raw),
        "logs": {
            "GVSoC": log_payload(args.gvsoc_log, args.log_mode),
            "RTL": log_payload(args.rtl_log, args.log_mode),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    document = HTML.replace("__DATA__", json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    args.output.write_text(document, encoding="utf-8")
    print(f"Wrote {args.output} ({args.output.stat().st_size} bytes)")
    print(f"Parsed {sum(raw_counts.values())} raw instructions, kept {sum(map(len, focused.values()))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
