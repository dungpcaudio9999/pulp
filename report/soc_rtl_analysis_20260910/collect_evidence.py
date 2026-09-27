#!/usr/bin/env python3
"""Read-only source inventory for the SoC walkthrough; JSON goes to stdout.

This locates text and hashes files. It does not parse/elaborate SystemVerilog,
prove a claim, compile software, or run a simulator. Run again after RTL changes.
"""

import hashlib
import json
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[2]
CHECKOUTS = ROOT / ".bender/git/checkouts"

# A dependency prefix is resolved to exactly one checkout, never silently picked.
# Each entry: dependency (None = workspace), relative file, literal search anchors.
SOURCES = [
    (None, "sim/compile.tcl", ["timer_unit-", "lint_2_axi.sv"]),
    (None, "rtl/tb/tb_pulp.sv", ["CORE_TYPE_FC", "USE_HWPE"]),
    (None, "rtl/pulp/pulp.sv", ["soc_domain", "NB_HWPE_PORTS"]),
    (None, "rtl/includes/periph_bus_defines.sv", ["TIMER_START_ADDR", "EU_START_ADDR"]),
    (None, "sw/full_system/full_system.c", ["timer_base_fc"]),
    (None, "sw/full_system/run_sim.sh", ["USE_HWPE_CL"]),
    ("pulp_soc", "rtl/pulp_soc/pulp_soc.sv", ["i_dm_top", "jtag_lint_arbiter_i", "axi_cdc_src"]),
    ("pulp_soc", "rtl/fc/fc_subsystem.sv", ["core_data_we", "core_data_err"]),
    ("pulp_soc", "rtl/pulp_soc/soc_interconnect_wrap.sv", ["tcdm_fc_data_addr_remapped", "axi_lite_to_apb_intf"]),
    ("pulp_soc", "rtl/pulp_soc/tcdm_demux.sv", ["PENDING", "active_slave_q"]),
    ("pulp_soc", "rtl/pulp_soc/contiguous_crossbar.sv", ["WriteRespOn", "RespLat"]),
    ("pulp_soc", "rtl/pulp_soc/interleaved_crossbar.sv", ["PORT_SEL_WIDTH", "RespLat"]),
    ("pulp_soc", "rtl/pulp_soc/l2_ram_multi_bank.sv", ["tc_sram"]),
    ("pulp_soc", "rtl/pulp_soc/boot_rom.sv", ["generic_rom", "ADDR_WIDTH"]),
    ("pulp_soc", "rtl/include/tcdm_macros.svh", ["TCDM_EXPLODE_ARRAY_DECLARE", "[3:0]"]),
    ("tech_cells_generic", "src/rtl/tc_sram.sv", ["Latency", "sram[addr_i[i]][j]"]),
    ("tech_cells_generic", "src/deprecated/generic_rom.sv", ["$readmemb", "A_Q <= A"]),
    ("pulp_soc", "rtl/pulp_soc/lint_2_axi_wrap.sv", ["REGISTERED_GRANT", "data_we_i"]),
    ("pulp_soc", "rtl/pulp_soc/periph_bus_wrap.sv", ["timer_master", "apb_node"]),
    ("pulp_soc", "rtl/pulp_soc/soc_peripherals.sv", ["i_apb_timer_unit", "s_timer_hi_event"]),
    ("pulp_soc", "rtl/pulp_soc/soc_event_generator.sv", ["s_valid_fc", "s_event_ready", "r_fc_mask"]),
    ("pulp_soc", "rtl/pulp_soc/soc_event_queue.sv", ["r_event_count", "err_o"]),
    ("pulp_soc", "rtl/components/tcdm_arbiter_2x1.sv", ["RR_FLAG", "WAIT_VALID_0"]),
    ("pulp_soc", "rtl/components/apb_timer_unit.sv", ["module apb_timer_unit"]),
    ("pulp_soc", "rtl/udma_subsystem/udma_subsystem.sv", ["i_uart_gen", "CH_ID_TX_UART"]),
    ("common_cells", "src/addr_decode.sv", ["start_addr", "end_addr"]),
    ("common_cells", "src/rr_arb_tree.sv", ["ExtPrio", "FairArb", "LockIn"]),
    ("cluster_interconnect", "rtl/tcdm_interconnect/xbar.sv", ["rr_arb_tree", "addr_dec_resp_mux"]),
    ("cluster_interconnect", "rtl/tcdm_interconnect/addr_dec_resp_mux.sv", ["WriteRespOn", "bank_sel_q", "vld_q"]),
    ("l2_tcdm_hybrid_interco", "RTL/lint_2_axi.sv", ["WRITE_DATA", "WRITE_ADDR", "WRITE_WAIT"]),
    ("axi", "src/axi_lite_to_apb.sv", ["fall_through_register", "Setup:", "Access:"]),
    ("apb_node", "src/apb_node.sv", ["match_address", "pready_o"]),
    ("timer_unit", "rtl/apb_timer_unit.sv", ["IEM_BIT", "PADDR[5:0]", "irq_hi_o"]),
    ("timer_unit", "rtl/timer_unit_counter.sv", ["s_count == compare_value_i", "reset_count_i"]),
    ("apb_interrupt_cntrl", "apb_interrupt_cntrl.sv", ["s_event_fifo_ready", "proc_id", "proc_int"]),
    ("cv32e40p", "rtl/riscv_controller.sv", ["SLEEP:", "IRQ_TAKEN_ID:", "IRQ_TAKEN_IF:"]),
    ("cv32e40p", "rtl/riscv_if_stage.sv", ["EXC_PC_IRQ"]),
    ("udma_core", "rtl/core/udma_core.sv", ["periph_valid_o"]),
    ("udma_core", "rtl/common/udma_apb_if.sv", ["PADDR[11:7]", "PADDR[6:2]"]),
    ("udma_core", "rtl/common/udma_ctrl.sv", ["r_cg", "cg_core_o"]),
    ("udma_core", "rtl/core/udma_ch_addrgen.sv", ["s_compare", "int_ch_events_o", "int_not_stall_i"]),
    ("udma_core", "rtl/core/udma_tx_channels.sv", ["s_fifoin", "s_stall", "l2_addr_o"]),
    ("udma_uart", "rtl/udma_uart_reg_if.sv", ["REG_TX_CFG", "cfg_data_i[6]", "cfg_data_i[31:16]"]),
    ("udma_uart", "rtl/udma_uart_top.sv", ["io_tx_fifo", "udma_dc_fifo #(8,4)", "s_uart_tx_sample"]),
    ("udma_uart", "rtl/udma_uart_tx.sv", ["STOP_BIT_FIRST:", "busy_o", "cfg_div_i"]),
    (None, "pulp-runtime/drivers/uart.c", ["uart_wait_tx_done", "plp_udma_enqueue"]),
    (None, "pulp-runtime/kernel/irq.c", ["rt_irq_set_handler", "pos_irq_init"]),
    (None, "pulp-runtime/kernel/soc_event.c", ["pos_irq_set_handler"]),
    (None, "pulp-runtime/include/archi/chips/pulp/memory_map.h", ["ARCHI_FC_ITC_OFFSET"]),
    (None, "pulp-runtime/include/archi/udma/udma_v3.h", ["UDMA_CHANNEL_CFG_CLEAR_BIT"]),
]


def git(directory, *args):
    return subprocess.check_output(
        ["git", "-C", str(directory), *args], text=True
    ).strip()


def checkout(name):
    matches = sorted(p for p in CHECKOUTS.glob(name + "-*") if p.is_dir())
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one {name} checkout; got {matches}")
    return matches[0]


def main():
    compile_path = ROOT / "sim/compile.tcl"
    compile_text = compile_path.read_text()
    explicit = sorted(set(re.findall(
        r'\$ROOT/([^"\n]+\.(?:sv|v|vhd|vhdl))"', compile_text
    )))
    dependencies = {}
    files = []
    for dep, relative, needles in SOURCES:
        base = checkout(dep) if dep else ROOT
        if dep and dep not in dependencies:
            dependencies[dep] = {
                "path": str(base.relative_to(ROOT)),
                "head": git(base, "rev-parse", "HEAD"),
                "tracked_status": git(base, "status", "--short", "--untracked-files=no").splitlines(),
            }
        path = base / relative
        content = path.read_bytes()
        lines = content.decode("utf-8").splitlines()
        anchors = {}
        for needle in needles:
            hits = [i for i, line in enumerate(lines, 1) if needle in line]
            if not hits:
                raise RuntimeError(f"Anchor not found: {path}: {needle!r}")
            anchors[needle] = hits
        repo_path = str(path.relative_to(ROOT))
        files.append({
            "path": repo_path,
            "sha256": hashlib.sha256(content).hexdigest(),
            "line_count": len(lines),
            "explicitly_listed_rtl_in_compile_tcl": repo_path in explicit,
            "literal_anchors": anchors,
        })

    output = {
        "scope": "Static source inventory for SoC walkthrough, 2026-09-10",
        "limitations": [
            "Literal text locations are navigation aids, not proof of RTL behavior.",
            "Compile membership is a textual filelist check, not elaboration or active-branch proof.",
            "Files may be included indirectly; false explicit membership does not prove unused.",
            "No RTL compile, simulation, waveform measurement or formal verification was run.",
            "Per-file hashes cover listed evidence only, not every transitive input.",
        ],
        "root_head": git(ROOT, "rev-parse", "HEAD"),
        "compile_inventory": {
            "unique_explicit_rtl_files": len(explicit),
            "missing_files": [p for p in explicit if not (ROOT / p).is_file()],
        },
        "dependencies": dependencies,
        "sources": files,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
