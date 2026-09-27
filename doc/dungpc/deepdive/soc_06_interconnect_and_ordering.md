# SoC 06 — Interconnect, bridge và ordering

## Request/response

1. FC/uDMA/debug TCDM vào `soc_interconnect`: demux L2 contiguous, interleaved hoặc AXI default; wrapper gán chính xác ports 0–8 ([source](../../../.bender/git/checkouts/pulp_soc-c519334bd3ac5582/rtl/pulp_soc/soc_interconnect_wrap.sv#L148)).
2. L2 path giữ `active_slave_q` và bank/owner response state; grant chấp nhận request, `r_valid` mới hoàn tất ([trace](../master_analysis/soc_rtl/soc_01_fc_memory_rtl.md#4-fsm-demux-nhớ-nhánh-response-không-giữ-toàn-payload)). Bank arbiter khác debug arbiter: debug TAP ưu tiên cố định ở IDLE, nên không khẳng định toàn hệ round-robin ([debug](../master_analysis/soc_rtl/soc_03_udma_debug_cluster_rtl.md#7-debug-là-master-thực-sự-của-soc)).
3. AXI default tới cluster hoặc APB; APB qua AXI→AXI-Lite (`AXI_MAX_WRITE_TXNS=1`, `AXI_MAX_READ_TXNS=1`) rồi AXI-Lite→APB ([bridge instance](../../../.bender/git/checkouts/pulp_soc-c519334bd3ac5582/rtl/pulp_soc/soc_interconnect_wrap.sv#L216)). AW và W độc lập; B response hoàn tất write. APB Access chờ `PREADY`; node không chọn slave có thể đứng mãi.
4. Cluster→SoC 64-bit AXI qua CDC rồi bốn cổng TCDM 32-bit. DMA L2→L1 dùng AR/R; DMA L1→L2 dùng AW/W/B trên **cùng master C→S** ([domain trace](../master_analysis/architecture/deep_dive_05_domain_transactions.md#1-hai-giao-diện-axi-rtl)).

| Kênh AXI | Payload/state cần xem | Điều kiện hoàn tất |
|---|---|---|
| AW | address, ID, len/size, owner/route | `AWVALID && AWREADY`, chưa phải memory write |
| W | data, strobe, last, association với AW | `WVALID && WREADY`, có thể khác chu kỳ AW |
| B | ID, response | `BVALID && BREADY`, write response |
| AR | address, ID, len/size | `ARVALID && ARREADY` |
| R | ID, data, resp, last | từng `RVALID && RREADY`; completion ở beat cuối |

**Ordering giới hạn:** source đọc được bridge capacity và state, nhưng chưa có spec toàn hệ về ordering giữa ID, atomic/exclusive, barrier, QoS hoặc coherency. Không suy độ trễ tối đa từ đường không stall. Trace concurrency cần FC+uDMA chung bank, AW/W lệch nhau, APB stall, một CDC queue đầy và reset khi request đã qua một phía; xem [verification](08_verification_points.md).
