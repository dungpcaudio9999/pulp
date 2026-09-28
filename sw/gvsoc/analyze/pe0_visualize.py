#!/usr/bin/env python3
"""Generate a dependency-free interactive HTML viewer for a GVSoC ISS trace."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
TRACE_RE = re.compile(
    r"^(\d+):\s*(\d+):\s*\[([^\]]+)\]\s+"
    r"(\S+?):(\d+)\s+([A-Z])\s+([0-9a-fA-F]+)\s+(\S+)\s*(.*)$"
)
WRITE_RE = re.compile(r"\b([a-z][a-z0-9]*)=([0-9a-f]{8})\b", re.I)
READ_RE = re.compile(r"\b([a-z][a-z0-9]*):([0-9a-f]{8})\b", re.I)
PA_RE = re.compile(r"\bPA:([0-9a-f]{8})\b", re.I)


def instruction_category(op: str) -> str:
    op = op.lower()
    if op in {"jal", "jalr", "c.j", "c.jal", "c.jr", "c.jalr"} or op.startswith(
        ("b", "c.b", "p.b")
    ):
        return "Control flow"
    if op == "p.elw" or op.startswith(("lw", "lh", "lb", "lbu", "p.l", "c.l")):
        return "Load / event"
    if op.startswith(("sw", "sh", "sb", "p.s", "c.s")):
        return "Store"
    if op.startswith(("mul", "div", "rem", "p.mul")):
        return "Multiply / divide"
    if op.startswith(("csr", "ecall", "mret", "wfi")):
        return "System / CSR"
    return "ALU / other"


def memory_region(address: int | None) -> str:
    if address is None:
        return ""
    if 0x10000000 <= address < 0x10010000:
        return "Cluster L1 / TCDM"
    if 0x1C000000 <= address < 0x1D000000:
        return "L2"
    if 0x1A000000 <= address < 0x1B000000:
        return "SoC / peripheral"
    if address < 0x01000000:
        return "Low-address peripheral"
    return "Other"


def parse_trace(path: Path) -> list[dict]:
    rows: list[dict] = []
    for source in path.read_text(errors="replace").splitlines():
        clean = ANSI_RE.sub("", source)
        match = TRACE_RE.match(clean)
        if not match:
            continue
        time_ps, cycle, component, function, line, mode, pc, op, tail = match.groups()
        writes = [[name, value.lower()] for name, value in WRITE_RE.findall(tail)]
        reads = [[name, value.lower()] for name, value in READ_RE.findall(tail)]
        pa_match = PA_RE.search(tail)
        pa = int(pa_match.group(1), 16) if pa_match else None
        args = WRITE_RE.sub("", tail)
        args = READ_RE.sub("", args)
        args = PA_RE.sub("", args)
        args = " ".join(args.split())
        rows.append(
            {
                "t": int(time_ps),
                "c": int(cycle),
                "d": 0,
                "k": component.strip(),
                "f": function,
                "l": int(line),
                "q": mode,
                "p": "0x" + pc.lower(),
                "o": op,
                "a": args,
                "w": writes,
                "r": reads,
                "m": f"0x{pa:08x}" if pa is not None else "",
                "mr": memory_region(pa),
                "g": instruction_category(op),
            }
        )
    for index in range(1, len(rows)):
        rows[index]["d"] = rows[index]["c"] - rows[index - 1]["c"]
    return rows


def aggregate(rows: list[dict]) -> dict:
    by_function: dict[str, dict] = defaultdict(lambda: {"count": 0, "cycles": 0})
    by_op: dict[str, dict] = defaultdict(lambda: {"count": 0, "cycles": 0, "max": 0})
    by_category: dict[str, dict] = defaultdict(lambda: {"count": 0, "cycles": 0})
    by_memory = Counter()
    register_writes = Counter()
    for row in rows:
        by_function[row["f"]]["count"] += 1
        by_function[row["f"]]["cycles"] += row["d"]
        by_op[row["o"]]["count"] += 1
        by_op[row["o"]]["cycles"] += row["d"]
        by_op[row["o"]]["max"] = max(by_op[row["o"]]["max"], row["d"])
        by_category[row["g"]]["count"] += 1
        by_category[row["g"]]["cycles"] += row["d"]
        if row["mr"]:
            by_memory[row["mr"]] += 1
        for register, _ in row["w"]:
            register_writes[register] += 1

    def ranked(mapping: dict[str, dict], limit: int, key: str) -> list[dict]:
        return [
            {"name": name, **values}
            for name, values in sorted(mapping.items(), key=lambda item: item[1][key], reverse=True)[:limit]
        ]

    phase_functions = sorted(
        (name for name in by_function if name.startswith("phase")),
        key=lambda name: next(i for i, row in enumerate(rows) if row["f"] == name),
    )
    bookmarks = [{"name": "Boot PE0", "index": 0}]
    for name in phase_functions:
        bookmarks.append(
            {
                "name": name,
                "index": next(i for i, row in enumerate(rows) if row["f"] == name),
            }
        )
    longest_wait = max(range(len(rows)), key=lambda i: rows[i]["d"])
    bookmarks.append({"name": "Longest wait", "index": longest_wait})
    bookmarks.sort(key=lambda item: item["index"])

    total_cycles = rows[-1]["c"] - rows[0]["c"]
    return {
        "summary": {
            "instructions": len(rows),
            "spanCycles": total_cycles,
            "firstCycle": rows[0]["c"],
            "lastCycle": rows[-1]["c"],
            "spanPs": rows[-1]["t"] - rows[0]["t"],
            "uniquePc": len({row["p"] for row in rows}),
            "functions": len(by_function),
            "operations": len(by_op),
            "memoryOps": sum(1 for row in rows if row["m"]),
        },
        "functions": ranked(by_function, 20, "cycles"),
        "operations": ranked(by_op, 20, "count"),
        "categories": ranked(by_category, len(by_category), "count"),
        "memory": [{"name": name, "count": count} for name, count in by_memory.most_common()],
        "registerWrites": [{"name": name, "count": count} for name, count in register_writes.most_common()],
        "bookmarks": bookmarks,
        "longestWait": longest_wait,
    }


HTML_TEMPLATE = r'''<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>GVSoC PE0 Instruction Analyzer</title>
<style>
:root{color-scheme:dark;--bg:#101217;--panel:#181b22;--panel2:#20242d;--line:#343a46;--text:#eef1f6;--muted:#9aa4b3;--accent:#69a7ff;--ok:#69c38f;--warn:#e5b567;--bad:#ef7d7d;--mono:ui-monospace,SFMono-Regular,Consolas,monospace}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px/1.45 system-ui,sans-serif}main{max-width:1500px;margin:auto;padding:24px}h1{font-size:24px;margin:0}h2{font-size:18px;margin:0 0 10px}h3{font-size:15px;margin:0 0 8px}.muted{color:var(--muted)}.mono,code{font-family:var(--mono)}code{background:var(--panel2);padding:2px 5px;border-radius:4px}.header,.row,.toolbar{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.header{justify-content:space-between;margin-bottom:18px}.pill{border:1px solid var(--line);border-radius:999px;padding:3px 8px;font-size:12px}.ok{color:var(--ok)}.warn{color:var(--warn)}.stats{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:9px;margin:15px 0 20px}.stat,.card{border:1px solid var(--line);background:var(--panel);border-radius:7px}.stat{padding:10px}.stat b{display:block;font-size:19px;margin:2px 0}.layout{display:grid;grid-template-columns:minmax(0,1.45fr) minmax(360px,.8fr);gap:14px}.card-head{display:flex;justify-content:space-between;gap:8px;align-items:center;padding:10px 12px;border-bottom:1px solid var(--line)}.card-body{padding:12px}.analysis{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:18px}.bar-row{display:grid;grid-template-columns:minmax(105px,1fr) 2fr 72px;gap:8px;align-items:center;margin:6px 0}.bar-track{height:7px;background:var(--panel2);border-radius:999px;overflow:hidden}.bar-fill{height:100%;background:var(--accent)}.stack{display:flex;height:14px;border-radius:3px;overflow:hidden;background:var(--panel2)}.stack span{display:block;height:100%;border-right:1px solid var(--bg)}.category-list{display:flex;gap:10px;flex-wrap:wrap;margin-top:8px}.category-list small:before{content:'';display:inline-block;width:8px;height:8px;background:var(--accent);margin-right:5px}.callout{border-left:3px solid var(--warn);background:var(--panel);padding:10px 12px;margin:14px 0}.controls{display:grid;grid-template-columns:auto auto 1fr auto;gap:7px;align-items:center}.controls input[type=range]{width:100%}button,input,select{font:inherit;color:var(--text);background:var(--panel2);border:1px solid var(--line);border-radius:5px;padding:6px 9px}button{cursor:pointer}button.primary{background:var(--accent);border-color:var(--accent);color:#0c1727;font-weight:650}button:disabled{opacity:.4;cursor:not-allowed}.bookmarks{display:flex;gap:6px;flex-wrap:wrap;margin:10px 0}.instruction{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;font-size:17px;margin:4px 0 12px}.instruction strong{font-size:23px;color:var(--accent)}.details{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}.detail{padding:8px;background:var(--panel2);border-radius:5px}.detail small{display:block;color:var(--muted)}.values{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px}.value-box{background:var(--panel2);padding:9px;border-radius:5px}.chips{display:flex;flex-wrap:wrap;gap:5px;margin-top:5px}.registers{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px}.reg{background:var(--panel2);padding:5px 7px;border-radius:4px;font-family:var(--mono);font-size:12px}.reg.changed{outline:1px solid var(--accent)}.gaps{height:90px;display:flex;align-items:end;gap:2px;border-bottom:1px solid var(--line);padding-top:8px}.gap{min-width:3px;flex:1;background:var(--accent);cursor:pointer}.gap.current{background:var(--warn)}.trace-list{margin-top:12px;border-top:1px solid var(--line);max-height:510px;overflow:auto}.trace-row{display:grid;grid-template-columns:72px 88px 105px minmax(160px,1fr) 150px;gap:7px;padding:6px 8px;border-bottom:1px solid var(--line);cursor:pointer}.trace-row:hover,.trace-row.active{background:var(--panel2)}.trace-row.active{border-left:3px solid var(--accent);padding-left:5px}.search-row{display:grid;grid-template-columns:1fr auto auto;gap:7px;margin-top:9px}.phase-line{position:relative;height:42px;background:var(--panel2);border-radius:5px;overflow:hidden;margin:8px 0}.phase-block{position:absolute;top:0;height:100%;border-right:1px solid var(--line);background:color-mix(in srgb,var(--accent) 22%,transparent);padding:4px;overflow:hidden;font-size:11px}.footer{margin-top:20px;color:var(--muted);font-size:12px}@media(max-width:1050px){.layout,.analysis{grid-template-columns:1fr}.stats{grid-template-columns:repeat(3,1fr)}}@media(max-width:700px){main{padding:14px}.stats{grid-template-columns:repeat(2,1fr)}.details,.values{grid-template-columns:1fr 1fr}.trace-row{grid-template-columns:68px 90px 1fr}.trace-row span:nth-child(2),.trace-row span:last-child{display:none}.controls{grid-template-columns:auto auto 1fr}.controls span{display:none}}@media(max-width:480px){.stats,.details,.values{grid-template-columns:1fr}.registers{grid-template-columns:repeat(2,1fr)}}
</style></head><body><main>
<div class="header"><div><h1>GVSoC PE0 instruction analyzer</h1><div class="muted" id="source"></div></div><div class="row"><span class="pill ok">parsed successfully</span><span class="pill">PE0 · full trace</span></div></div>
<section class="stats" id="stats"></section>
<div class="callout"><b>Cách đọc Δ cycle:</b> đây là khoảng cách giữa cycle retire của lệnh hiện tại và lệnh trước. Một giá trị lớn có thể là latency, stall, sleep hoặc chờ event; không nên coi trực tiếp là latency độc lập của opcode.</div>
<section class="analysis"><div><h2>Hotspot theo hàm — tổng Δ cycle</h2><div id="function-bars"></div><div class="muted" style="font-size:12px">Nguồn: pe0.log · toàn bộ khoảng cycle của trace.</div></div><div><h2>Cơ cấu instruction</h2><div class="stack" id="category-stack"></div><div class="category-list" id="category-list"></div><h3 style="margin-top:18px">Memory access theo vùng</h3><div id="memory-bars"></div></div></section>
<section><h2>Timeline phase theo cycle</h2><div class="phase-line" id="phase-line"></div><div class="muted" style="font-size:12px">Vị trí block tính theo first/last cycle xuất hiện của các hàm phase.</div></section>
<section style="margin-top:20px"><div class="header"><h2>Replay từng instruction</h2><div class="toolbar"><button id="play">Play</button><button id="prev">Lùi</button><button class="primary" id="next">Lệnh tiếp</button></div></div><div class="controls"><span>Index</span><input id="index" type="number" min="0"><input id="slider" type="range" min="0"><span id="counter"></span></div><div class="bookmarks" id="bookmarks"></div><div class="search-row"><input id="search" placeholder="Tìm function, opcode, PC, argument…"><button id="find-prev">Kết quả trước</button><button id="find-next">Kết quả tiếp</button></div>
<div class="layout" style="margin-top:12px"><div><div class="card"><div class="card-head"><b id="core-cycle"></b><span class="pill" id="category"></span></div><div class="card-body"><div class="instruction"><code id="pc"></code><strong id="op"></strong><code id="args"></code></div><div class="details"><div class="detail"><small>Simulation time</small><b id="time"></b></div><div class="detail"><small>Function/source</small><b id="func"></b></div><div class="detail"><small>Δ cycle</small><b id="delta"></b></div><div class="detail"><small>Memory</small><b id="memory"></b></div></div><div class="values"><div class="value-box"><span class="muted">Register write</span><div class="chips" id="writes"></div></div><div class="value-box"><span class="muted">Register read</span><div class="chips" id="reads"></div></div></div><h3 style="margin-top:14px">Cycle gap quanh instruction đang chọn</h3><div class="gaps" id="gaps"></div></div></div><div class="trace-list" id="trace-list"></div></div><div><div class="card"><div class="card-head"><b>Register state dựng lại</b><span class="pill">last write ≤ index</span></div><div class="card-body"><div class="registers" id="registers"></div></div></div><div class="card" style="margin-top:12px"><div class="card-head"><b>Diễn giải nhanh</b></div><div class="card-body" id="explain"></div></div></div></div></section>
<div class="footer">Generated locally from GVSoC textual instruction trace. Không dùng network hoặc thư viện JavaScript ngoài.</div>
</main><script>
const payload=__TRACE_DATA__;
const rows=payload.rows,meta=payload.meta,s=meta.summary,$=id=>document.getElementById(id);let index=0,timer=null,matches=[];
const esc=v=>String(v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=n=>Number(n).toLocaleString('en-US');
function init(){ $('source').textContent=`${payload.source} · ${fmt(s.instructions)} parsed instructions`;const cards=[['Instructions',fmt(s.instructions),`${fmt(s.uniquePc)} unique PC`],['Cycle span',fmt(s.spanCycles),`${fmt(s.firstCycle)} → ${fmt(s.lastCycle)}`],['Functions',fmt(s.functions),`${fmt(s.operations)} opcodes`],['Memory ops',fmt(s.memoryOps),`${(100*s.memoryOps/s.instructions).toFixed(1)}% instructions`],['Simulated time',(s.spanPs/1e6).toFixed(2)+' µs','trace timestamp span']];$('stats').innerHTML=cards.map(x=>`<div class="stat"><span class="muted">${x[0]}</span><b>${x[1]}</b><small>${x[2]}</small></div>`).join('');renderBars();renderTimeline();$('slider').max=rows.length-1;$('index').max=rows.length-1;$('bookmarks').innerHTML=meta.bookmarks.map(b=>`<button data-index="${b.index}">${esc(b.name)}</button>`).join('');$('bookmarks').querySelectorAll('button').forEach(b=>b.onclick=()=>go(+b.dataset.index));bind();go(0)}
function renderBars(){const maxF=meta.functions[0].cycles;$('function-bars').innerHTML=meta.functions.slice(0,10).map(x=>`<div class="bar-row"><span title="${esc(x.name)}">${esc(x.name)}</span><div class="bar-track"><div class="bar-fill" style="width:${100*x.cycles/maxF}%"></div></div><span class="mono">${fmt(x.cycles)}</span></div>`).join('');const total=meta.categories.reduce((a,x)=>a+x.count,0);$('category-stack').innerHTML=meta.categories.map((x,i)=>`<span title="${esc(x.name)}: ${fmt(x.count)}" style="width:${100*x.count/total}%;opacity:${1-i*.1}"></span>`).join('');$('category-list').innerHTML=meta.categories.map(x=>`<small>${esc(x.name)} · ${fmt(x.count)} (${(100*x.count/total).toFixed(1)}%)</small>`).join('');const maxM=meta.memory[0].count;$('memory-bars').innerHTML=meta.memory.map(x=>`<div class="bar-row"><span>${esc(x.name)}</span><div class="bar-track"><div class="bar-fill" style="width:${100*x.count/maxM}%"></div></div><span class="mono">${fmt(x.count)}</span></div>`).join('')}
function renderTimeline(){const phaseNames=meta.bookmarks.filter(b=>b.name.startsWith('phase'));const blocks=phaseNames.map((b,i)=>{const next=phaseNames[i+1]?.index??rows.length-1,start=100*(rows[b.index].c-s.firstCycle)/s.spanCycles,end=100*(rows[next].c-s.firstCycle)/s.spanCycles;return`<button class="phase-block" data-index="${b.index}" style="left:${start}%;width:${Math.max(2,end-start)}%">${esc(b.name)}</button>`}).join('');$('phase-line').innerHTML=blocks;$('phase-line').querySelectorAll('button').forEach(b=>b.onclick=()=>go(+b.dataset.index))}
function bind(){ $('prev').onclick=()=>go(index-1);$('next').onclick=()=>go(index+1);$('slider').oninput=e=>go(+e.target.value);$('index').onchange=e=>go(+e.target.value);$('play').onclick=togglePlay;$('search').oninput=updateMatches;$('find-next').onclick=()=>find(1);$('find-prev').onclick=()=>find(-1)}
function togglePlay(){if(timer){clearInterval(timer);timer=null;$('play').textContent='Play';return}$('play').textContent='Dừng';timer=setInterval(()=>{if(index>=rows.length-1){togglePlay();return}go(index+1)},120)}
function updateMatches(){const q=$('search').value.trim().toLowerCase();matches=q?rows.map((r,i)=>({r,i})).filter(x=>`${x.r.f} ${x.r.o} ${x.r.p} ${x.r.a}`.toLowerCase().includes(q)).map(x=>x.i):[];$('find-next').textContent=matches.length?`Kết quả tiếp (${fmt(matches.length)})`:'Kết quả tiếp'}
function find(dir){if(!matches.length)return;const ordered=dir>0?matches:[...matches].reverse();const target=ordered.find(i=>dir>0?i>index:i<index);go(target??ordered[0])}
function chips(values,kind){return values.length?values.map(v=>`<code>${esc(v[0])} ${kind} 0x${esc(v[1])}</code>`).join(''):'<span class="muted">Không có</span>'}
function registersAt(at){const state={};for(let i=0;i<=at;i++)for(const [reg,val] of rows[i].w)state[reg]=val;const order=['ra','sp','gp','tp','t0','t1','t2','s0','s1','a0','a1','a2','a3','a4','a5','a6','a7','s2','s3','s4','s5','s6','s7','s8','s9','s10','s11','t3','t4','t5','t6'];const changed=new Set(rows[at].w.map(x=>x[0]));return order.filter(r=>state[r]).map(r=>`<div class="reg ${changed.has(r)?'changed':''}">${r}<br><b>0x${state[r]}</b></div>`).join('')}
function explanation(r){let text=`PE0 retire lệnh ${r.o} tại ${r.p}. `;if(r.g==='Load / event')text+=r.o==='p.elw'?'Đây là event-load; Δ cycle lớn thường biểu thị core đang chờ event. ':'Đây là thao tác đọc dữ liệu. ';else if(r.g==='Store')text+='Đây là thao tác ghi dữ liệu. ';else if(r.g==='Control flow')text+='Lệnh này thay đổi hoặc kiểm tra luồng điều khiển. ';if(r.m)text+=`Địa chỉ vật lý ${r.m} thuộc vùng ${r.mr}. `;if(r.d>100)text+=`Khoảng chờ ${fmt(r.d)} cycle là bất thường lớn và đáng kiểm tra.`;else if(r.d>10)text+=`Khoảng ${fmt(r.d)} cycle cao hơn luồng retire thông thường.`;return text}
function renderGaps(){const from=Math.max(0,index-20),to=Math.min(rows.length,index+21),slice=rows.slice(from,to),max=Math.max(...slice.map(r=>r.d),1);$('gaps').innerHTML=slice.map((r,j)=>{const i=from+j,h=Math.max(2,80*Math.log1p(r.d)/Math.log1p(max));return`<div class="gap ${i===index?'current':''}" data-index="${i}" title="index ${i} · Δ ${r.d} cycle" style="height:${h}px"></div>`}).join('');$('gaps').querySelectorAll('.gap').forEach(b=>b.onclick=()=>go(+b.dataset.index))}
function renderContext(){const from=Math.max(0,index-10),to=Math.min(rows.length,index+11);$('trace-list').innerHTML=rows.slice(from,to).map((r,j)=>{const i=from+j;return`<div class="trace-row ${i===index?'active':''}" data-index="${i}"><span class="muted">#${i}</span><span class="muted">cy ${r.c}</span><code>${r.p}</code><span><b>${esc(r.o)}</b> ${esc(r.a)}</span><span class="muted">${esc(r.f)}:${r.l}</span></div>`}).join('');$('trace-list').querySelectorAll('.trace-row').forEach(el=>el.onclick=()=>go(+el.dataset.index));$('trace-list').querySelector('.active')?.scrollIntoView({block:'center'})}
function go(next){index=Math.max(0,Math.min(rows.length-1,next));const r=rows[index];$('index').value=index;$('slider').value=index;$('counter').textContent=`${fmt(index+1)} / ${fmt(rows.length)}`;$('core-cycle').textContent=`${r.k.trim()} · cycle ${fmt(r.c)}`;$('category').textContent=r.g;$('pc').textContent=r.p;$('op').textContent=r.o;$('args').textContent=r.a||'—';$('time').textContent=fmt(r.t)+' ps';$('func').textContent=`${r.f}:${r.l}`;$('delta').textContent=fmt(r.d);$('memory').textContent=r.m?`${r.m} · ${r.mr}`:'Không có';$('writes').innerHTML=chips(r.w,'=');$('reads').innerHTML=chips(r.r,':');$('registers').innerHTML=registersAt(index);$('explain').textContent=explanation(r);$('prev').disabled=index===0;$('next').disabled=index===rows.length-1;renderGaps();renderContext()}
init();
</script></body></html>'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path, help="GVSoC instruction trace, for example pe0.log")
    parser.add_argument("output", type=Path, help="HTML output path")
    args = parser.parse_args()
    rows = parse_trace(args.trace)
    if not rows:
        parser.error(f"no instruction rows parsed from {args.trace}")
    payload = {
        "source": str(args.trace),
        "meta": aggregate(rows),
        "rows": rows,
    }
    document = HTML_TEMPLATE.replace(
        "__TRACE_DATA__", json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(document, encoding="utf-8")
    print(f"Wrote {args.output} ({len(rows)} instructions, {args.output.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
