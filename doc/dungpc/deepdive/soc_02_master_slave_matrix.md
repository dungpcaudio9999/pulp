# SoC 02 — Ma trận master–slave

**Kết nối vật lý khác quyền truy cập.** Bảng ghi đường RTL có thể đi tới target; policy privilege/security cần [bản đồ riêng](soc_07_security_boundaries.md). `R/W` ở đây là khả năng giao dịch bus, không xác nhận software có quyền hoặc target hỗ trợ mọi offset.

| Initiator | ROM | Private/shared L2 | APB SoC | Cluster | Đường và giới hạn |
|---|---|---|---|---|---|
| FC instruction | decode R | decode R | qua nhánh AXI default nhưng không coi là fetch hợp lệ | qua AXI/CDC | TCDM master 1, response `r_valid` |
| FC data | decode tới ROM; write semantics riêng | R/W | R/W qua AXI-Lite/APB | R/W qua AXI/CDC | Master 0, prefix `0x000` remap `0x1C0` |
| uDMA TX | không có prefix ROM trong generator | R khi destination=0 | destination=1 tạo prefix `0x1A1`, target policy chưa xác nhận | destination=2 tạo prefix `0x10`, chưa nghiệm thu | Master 2, đọc payload |
| uDMA RX | không có prefix ROM trong generator | W khi destination=0 | destination=1 tạo prefix `0x1A1`, target policy chưa xác nhận | destination=2 tạo prefix `0x10`, chưa nghiệm thu | Master 3, ghi payload |
| PULP TAP / RISC-V DM | decode, target semantics riêng | R/W | route default, target policy chưa xác nhận | route default, target policy chưa xác nhận | Arbiter 2→1, master 4; TAP ưu tiên IDLE |
| Cluster AXI masters | decode qua bridge, target semantics riêng | R/W qua bốn cổng TCDM 32 | route default, target policy chưa xác nhận | local path riêng | AXI 64 C→S, CDC, ports 5–8 |
| SoC HWPE | — | interleaved shared L2 | — | — | Cổng riêng, **không instantiate** với `USE_HWPE=0` |

Nguồn wiring: [port assignment](../../../.bender/git/checkouts/pulp_soc-c519334bd3ac5582/rtl/pulp_soc/soc_interconnect_wrap.sv#L152), [demux/AXI slaves](../../../.bender/git/checkouts/pulp_soc-c519334bd3ac5582/rtl/pulp_soc/soc_interconnect_wrap.sv#L182), [TX destination decode](../../../.bender/git/checkouts/udma_core-25b62500cd51a5c6/rtl/core/udma_tx_channels.sv#L164), [RX destination decode](../../../.bender/git/checkouts/udma_core-25b62500cd51a5c6/rtl/core/udma_rx_channels.sv#L237), [debug arbitration](../master_analysis/soc_rtl/soc_03_udma_debug_cluster_rtl.md#7-debug-là-master-thực-sự-của-soc). UART TX trong cấu hình hiện tại dùng destination 0 cho L2; các nhánh khác của generic uDMA chưa được kiểm chứng tích hợp. Cột quyền R/W/X/atomic theo initiator chưa có đặc tả SoC được phê duyệt; không biến khả năng route thành lời hứa quyền. Kiểm integration phải bao gồm deny/no-side-effect và unmapped/error riêng.
