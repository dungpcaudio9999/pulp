#!/usr/bin/env python3
"""Tao ban sao da va cua nhung file ma XSim 2019.1 khong nuot duoc.

Khong sua file goc trong .bender/ (bender co the ghi de) hay trong rtl/.
Ban va nam o xsim/patched/, va duong dan trong xsim/sv.f duoc tro sang do.

Chay: ./xsim/patch_sources.py [duong/dan/sv.f]

Them luat moi:
  - loi mang tinh he thong  -> viet mot ham va them vao RULES
  - loi o dung mot cho      -> them mot dong vao REPLACEMENTS
"""
import hashlib
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FLIST = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "xsim", "sv.f")
PATCHDIR = os.path.join(ROOT, "xsim", "patched")

UNIT_OPEN = re.compile(r"^\s*(module|interface|package|program|primitive|checker)\b")
UNIT_CLOSE = re.compile(r"^\s*end(module|interface|package|program|primitive|checker)\b")
TIMEUNIT = re.compile(r"^\s*(timeunit|timeprecision)\b")


# --------------------------------------------------------------------------
# Luat theo cau truc
# --------------------------------------------------------------------------
def fix_compilation_unit_timeunit(lines):
    """[VRFC 10-1488] unexpected timeunit

    `timeunit` / `timeprecision` o pham vi compilation unit (ngoai moi
    module/interface) khong duoc XSim 2019.1 ho tro. Ben trong module thi
    binh thuong, nen chi comment nhung cai o ngoai. Timescale that su do
    xelab --timescale quyet dinh.
    """
    depth = 0
    changed = False
    out = []
    for ln in lines:
        if UNIT_CLOSE.match(ln):
            depth = max(0, depth - 1)
        elif UNIT_OPEN.match(ln):
            depth += 1
        elif depth == 0 and TIMEUNIT.match(ln):
            out.append("// [xsim-patch] " + ln.rstrip("\n") + "\n")
            changed = True
            continue
        out.append(ln)
    return out, changed


RULES = [fix_compilation_unit_timeunit]


# --------------------------------------------------------------------------
# Thay the tai cho: (duoi duong dan, chuoi cu, chuoi moi, ly do)
# Moi muc phai khop dung 1 lan, neu khong script se bao loi.
# --------------------------------------------------------------------------
REPLACEMENTS = [
    (
        "pulp_soc/soc_interconnect.sv",
        "LatencyMode: axi_pkg::CUT_MST_AX | axi_pkg::MuxW,",
        "LatencyMode: axi_pkg::xbar_latency_e'(axi_pkg::CUT_MST_AX | axi_pkg::MuxW),",
        "[VRFC 10-2649] OR hai gia tri enum ra mot gia tri khong co ten; "
        "XSim doi ep kieu tuong minh. xbar_latency_e la enum logic[9:0] va "
        "axi_xbar chi doc tung bit LatencyMode[n], nen ep kieu khong doi hanh vi.",
    ),
    (
        "src/axi_xbar.sv",
        "  parameter type rule_t                 = axi_pkg::xbar_rule_64_t\n"
        ") (",
        "  parameter type rule_t                 = axi_pkg::xbar_rule_64_t,\n"
        "  // [xsim-patch] xem ly do o duoi\n"
        "  parameter int unsigned XSIM_NO_SLV    = Cfg.NoSlvPorts,\n"
        "  parameter int unsigned XSIM_NO_MST    = Cfg.NoMstPorts\n"
        ") (",
        "[VRFC 10-3352] XSim 2019.1 khong nhan mang interface lam actual khi "
        "bien cua port lay tu mot truong cua struct parameter (Cfg.NoSlvPorts). "
        "Dua bien ra thanh parameter don. Gia tri khong doi.",
    ),
    (
        "src/axi_xbar.sv",
        "  AXI_BUS.Slave                                                   slv_ports [Cfg.NoSlvPorts-1:0],\n"
        "  AXI_BUS.Master                                                  mst_ports [Cfg.NoMstPorts-1:0],",
        "  AXI_BUS.Slave                                                   slv_ports [XSIM_NO_SLV-1:0],\n"
        "  AXI_BUS.Master                                                  mst_ports [XSIM_NO_MST-1:0],",
        "Dung parameter don lam bien cho mang interface.",
    ),
    (
        "rtl/hwpe_ctrl_interfaces.sv",
        "  parameter int unsigned ID_WIDTH = -1;",
        "  parameter int unsigned ID_WIDTH = 1;  // [xsim-patch] khong dung -1",
        "Mac dinh -1 gan vao 'int unsigned' thanh 4294967295, nen "
        "logic [ID_WIDTH-1:0] tro thanh vector 4 ty bit va xvlog treo khi "
        "phan tich interface o che do standalone. Moi cho instantiate deu "
        "truyen ID_WIDTH that (hwpe_subsystem, mac_top_wrap), nen gia tri "
        "mac dinh khong bao gio duoc dung -> doi thanh 1 la vo hai.",
    ),
    (
        "rtl/tb/SimJTAG.sv",
        'import "DPI-C" function int jtag_tick\n'
        "(\n"
        " output bit jtag_TCK,\n"
        " output bit jtag_TMS,\n"
        " output bit jtag_TDI,\n"
        " output bit jtag_TRSTn,\n"
        "\n"
        " input bit  jtag_TDO\n"
        ");\n",
        "// [xsim-patch] bo DPI import - xem ham jtag_tick noi bo ben duoi\n",
        "[XSIM 43-4452] xsc khong link duoc thu vien DPI. SimJTAG duoc "
        "instantiate vo dieu kien trong tb_pulp nhung enable=0 khi "
        "ENABLE_OPENOCD=0, nen jtag_tick khong bao gio duoc goi. Thay bang "
        "ham SV noi bo de bo han DPI. Muon dung OpenOCD that thi phai go "
        "luat nay va build librbs.so.",
    ),
    (
        "rtl/tb/SimJTAG.sv",
        "   reg          init_done_sticky;\n",
        "   reg          init_done_sticky;\n"
        "\n"
        "   // [xsim-patch] thay cho DPI jtag_tick\n"
        "   function automatic int jtag_tick(output bit o_tck,\n"
        "                                    output bit o_tms,\n"
        "                                    output bit o_tdi,\n"
        "                                    output bit o_trstn,\n"
        "                                    input  bit i_tdo);\n"
        "      o_tck   = 1'b0;\n"
        "      o_tms   = 1'b0;\n"
        "      o_tdi   = 1'b0;\n"
        "      o_trstn = 1'b1;\n"
        "      return 0;\n"
        "   endfunction\n",
        "Dinh nghia jtag_tick ngay trong module SimJTAG.",
    ),
]


USED = set()


def apply_replacements(path, text):
    changed = False
    for idx, (suffix, old, new, why) in enumerate(REPLACEMENTS):
        if not path.endswith(suffix):
            continue
        n = text.count(old)
        if n == 0:
            continue
        if n > 1:
            sys.exit("Luat khop %d lan (mong doi 1) trong %s:\n  %s" % (n, path, old))
        text = text.replace(old, new, 1)
        USED.add(idx)
        changed = True
    return text, changed


def main():
    if not os.path.isfile(FLIST):
        sys.exit("Khong thay %s - chay ./xsim/gen_filelists.sh truoc." % FLIST)
    os.makedirs(PATCHDIR, exist_ok=True)

    out_lines = []
    patched = []
    for raw in open(FLIST):
        p = raw.strip()
        if not p or p.startswith(("-", "+")) or p.startswith(PATCHDIR):
            out_lines.append(raw)
            continue
        try:
            lines = open(p, errors="replace").readlines()
        except OSError:
            out_lines.append(raw)
            continue

        changed_any = False
        for rule in RULES:
            lines, changed = rule(lines)
            changed_any = changed_any or changed

        text, changed = apply_replacements(p, "".join(lines))
        changed_any = changed_any or changed

        if not changed_any:
            out_lines.append(raw)
            continue

        tag = hashlib.sha1(p.encode()).hexdigest()[:8]
        dst = os.path.join(PATCHDIR, "%s_%s" % (tag, os.path.basename(p)))
        with open(dst, "w") as f:
            f.write(text)
        patched.append((p, dst))
        out_lines.append(dst + "\n")

    with open(FLIST, "w") as f:
        f.writelines(out_lines)

    if patched:
        print("Da va %d file (ban goc khong bi dong):" % len(patched))
        for src, dst in patched:
            print("  %s\n    -> %s" % (src.replace(ROOT + "/", ""),
                                       dst.replace(ROOT + "/", "")))
    else:
        print("Khong co file nao can va.")

    # Chi canh bao khi thuc su vua va (chay lai lan 2 thi sv.f da tro sang
    # ban va, khong con file goc de khop -> khong phai loi).
    unused = [i for i in range(len(REPLACEMENTS)) if i not in USED] if patched else []
    if unused:
        print()
        print("CANH BAO: %d luat REPLACEMENTS khong khop file nao:" % len(unused))
        for i in unused:
            print("  - %s : %s" % (REPLACEMENTS[i][0],
                                   REPLACEMENTS[i][1].splitlines()[0][:60]))


if __name__ == "__main__":
    main()
