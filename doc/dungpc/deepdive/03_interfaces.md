# 03 — Giao diện và contract

| Ranh giới | Protocol/chiều | Chấp nhận | Hoàn tất | Bằng chứng |
|---|---|---|---|---|
| FC → SoC | TCDM `req/gnt`, 32-bit data/BE | `req && gnt` | `r_valid`, `r_rdata`, `r_opc` | [FC port](../master_analysis/soc_rtl/soc_01_fc_memory_rtl.md#2-contract-của-cổng-fc-đọc-assignment-thay-vì-comment) |
| SoC → ROM/L2 | TCDM demux/crossbar | grant theo target/arbiter | owner/bank state route response | [interconnect](../../../.bender/git/checkouts/pulp_soc-c519334bd3ac5582/rtl/pulp_soc/soc_interconnect_wrap.sv#L148) |
| SoC → APB | TCDM→AXI→AXI-Lite→APB | AW và W độc lập; APB Setup/Access | B/R qua bridge | [bridge](../../../.bender/git/checkouts/pulp_soc-c519334bd3ac5582/rtl/pulp_soc/soc_interconnect_wrap.sv#L216) |
| SoC ↔ cluster | AXI 32-bit S→C; AXI 64-bit C→S | AW/W/AR từng channel | B/R về master | [giao dịch domain](../master_analysis/architecture/deep_dive_05_domain_transactions.md#1-hai-giao-diện-axi-rtl) |
| SoC → cluster event | ID qua Gray FIFO | FIFO ready/valid | event được nhận phía cluster | [CDC](../master_analysis/microarchitecture/micro_07_cdc_clock_reset.md#4-event-pulse-và-event-id-là-hai-protocol-khác-nhau) |
| Timer/uDMA → FC | direct bits 10/11; event FIFO IRQ 26 | ITC pending/mask | core ack và source clear | [IRQ](soc_04_interrupt_map.md) |

**Quy tắc:** grant của TCDM không đồng nghĩa CPU retire; AXI AW không đồng nghĩa write hoàn tất; APB `PREADY=0` có thể giữ upstream vĩnh viễn nếu không có timeout. Width/ID/buffering cụ thể của từng bridge cần lấy từ parameter tại instance, không suy từ tên protocol. [SoC interconnect wrapper](../../../.bender/git/checkouts/pulp_soc-c519334bd3ac5582/rtl/pulp_soc/soc_interconnect_wrap.sv#L182) cho `AXI_MAX_WRITE_TXNS=1`, `AXI_MAX_READ_TXNS=1` riêng ở AXI→AXI-Lite; không áp giới hạn đó cho mọi đoạn AXI khác.
