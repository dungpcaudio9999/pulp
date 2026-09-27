# 04 — Giao dịch chủ đạo: FC đọc shared L2

## Intent và điều kiện

**[RTL, SUY RA]** FC load word aligned ở `0x1C010014`, sau reset, L2 clock chạy; không có master khác cùng bank. Đây là ví dụ decode, không phải buffer an toàn để ghi khi chạy software. FC giữ `req` cho tới grant ([contract](../master_analysis/soc_rtl/soc_01_fc_memory_rtl.md#2-contract-của-cổng-fc-đọc-assignment-thay-vì-comment)).

## Đường đi và state

1. FC data master vào `soc_interconnect_wrap` port 0; remap chỉ đổi prefix `0x000` thành `0x1C0`, nên địa chỉ này giữ nguyên ([wiring](../../../.bender/git/checkouts/pulp_soc-c519334bd3ac5582/rtl/pulp_soc/soc_interconnect_wrap.sv#L119), [ports](../../../.bender/git/checkouts/pulp_soc-c519334bd3ac5582/rtl/pulp_soc/soc_interconnect_wrap.sv#L152)).
2. Demux chọn vùng shared `0x1C010000 ≤ A < 0x1C090000`; offset `0x14`, bank `(offset>>2)&3 = 1`, row `offset>>4 = 1` ([decode chứng minh](../master_analysis/soc_rtl/soc_01_fc_memory_rtl.md#3-decode-gồm-hai-cấp-và-một-remap-riêng)).
3. Crossbar arbiter cấp grant. Demux lưu nhánh `active_slave_q`, crossbar lưu `bank_sel_q` và valid tương ứng; response SRAM đi ngược về FC với `r_valid/r_rdata/r_opc` ([response state](../master_analysis/soc_rtl/soc_01_fc_memory_rtl.md#4-fsm-demux-nhớ-nhánh-response-không-giữ-toàn-payload)).
4. FC chỉ coi load hoàn tất khi nhận response; không lấy thời điểm grant làm dữ liệu hợp lệ.

## Stall, lỗi và hệ quả kiểm chứng

Nếu bank đang bận, grant phải chờ và request/payload phải ổn định. `0x1C010024` vẫn bank 1 nhưng row 2; `0x1C010018` bank 2 row 1; `0x1C090000` ra khỏi shared L2 và đi nhánh AXI default ([địa chỉ biên](soc_03_address_map.md)). Kiểm scoreboard theo `(master, address, data)` và xác nhận response thuộc request cũ khi có request mới cùng chu kỳ. Bảng chu kỳ trước đây giả định không stall và memory latency 1; **chưa có waveform mới** xác nhận latency dưới tranh chấp ([phân tích chi tiết](../master_analysis/soc_rtl/soc_01_fc_memory_rtl.md#6-ba-giao-dịch-được-lần-hoàn-chỉnh)).

## Trace thứ hai: FC store tới timer rồi IRQ

**Intent/preconditions [SW, RTL]:** phase 2 gọi timer high START; `timer_base_fc(0,1)=0x1A10B004`, cộng offset START_LO `0x18` thành địa chỉ **`0x1A10B01C`**. Store word aligned đưa `req=1`, `wen=0`, `be=1111` trên FC data port ([source/đối chiếu](../master_analysis/soc_rtl/soc_02_timer_irq_rtl.md#2-theo-một-store-cụ-thể-qua-bridge-tcdm--axi)).

1. Địa chỉ ngoài L2/ROM chọn default TCDM→AXI. `lint_2_axi` phát AW và W độc lập. Nếu chỉ AW được accept, FSM chờ W ở `WRITE_DATA`; nếu chỉ W được accept, chờ AW ở `WRITE_ADDR`. FC chỉ nhận grant sau khi cả hai phía cần thiết được accept; `WRITE_WAIT` chờ B để trả `r_valid` ([FSM](../master_analysis/soc_rtl/soc_02_timer_irq_rtl.md#2-theo-một-store-cụ-thể-qua-bridge-tcdm--axi)).
2. AXI xbar chọn peripheral window. AXI→AXI-Lite giới hạn một read và một write; AXI-Lite→APB đưa `PSEL=1,PENABLE=0` ở Setup, rồi `PSEL=1,PENABLE=1` ở Access. Chỉ `PREADY=1` kết thúc Access và tạo B/R response; `PSLVERR` đổi thành error response ([bridge](../master_analysis/soc_rtl/soc_02_timer_irq_rtl.md#3-axi--axi-lite--apb-nơi-giao-dịch-thực-sự-ghi-timer)).
3. APB node chọn timer ở `0x1A10B000–0x1A10BFFF`. Timer decode low bits thành START_HI, set enable; counter và `target_reached` cập nhật theo clock. Khi compare/IRQ-enable được cấu hình, timer high tới ITC bit 11. ITC lưu pending/mask, core ack xóa pending; software vẫn phải xử lý nguồn để tránh repend ([timer](../master_analysis/soc_rtl/soc_02_timer_irq_rtl.md#5-timer-register-lần-từ-address-tới-next-state), [ITC](../master_analysis/soc_rtl/soc_02_timer_irq_rtl.md#6-interrupt-controller-pending-mask-priority-và-ack)).

**Completion/failure:** B/r_valid xác nhận APB write hoàn tất, không xác nhận timer đã đạt compare hoặc ISR đã chạy. Nếu APB node không chọn slave (`0x1A107000`), `PREADY=0` có thể chặn B vô hạn; test cần watchdog. **Verification:** quan sát AW/W riêng, Setup/Access, register enable, count/target, pending 11, core PC/handler và source clear. Demo hiện chỉ kiểm count tăng, nên IRQ trace là kế hoạch kiểm chứng chứ chưa là kết quả SIM.

## Trace thứ ba: UART TX descriptor tới pad và event

**Intent/preconditions:** driver ghi start address/size rồi enable uDMA UART TX; UART destination được buộc về L2. Address generator giữ `current address/bytes left`; khi grant và `not_stall`, nó tiến địa chỉ và giảm bytes left. Event ở request cuối **chưa phải** stop bit cuối trên pad ([uDMA source trace](../master_analysis/soc_rtl/soc_03_udma_debug_cluster_rtl.md#3-từ-enqueue-tới-request-l2-và-response-byte)).

1. TX channels giữ metadata address/size/destination/ID trong request FIFO, tạo prefix `0x1C`, đưa master 2 tới L2. Với byte tại `0x1C010015`, request word aligned `0x1C010014`, bank 1 row 1; response lane `[15:8]` vào UART ([TX RTL](../../../.bender/git/checkouts/udma_core-25b62500cd51a5c6/rtl/core/udma_tx_channels.sv#L164)).
2. Byte đi qua system-clock FIFO rồi dual-clock FIFO tới serializer peripheral clock. UART phát START, data LSB-first, parity nếu bật, STOP; `uart_tx_o` còn phải qua safe-domain mux/OE mới ra pad ([UART trace](../master_analysis/soc_rtl/soc_03_udma_debug_cluster_rtl.md#4-qua-hai-clock-data-fifo-và-configuration-không-cùng-cơ-chế)).
3. Event uDMA qua source queue/arbiter tới FC FIFO, IRQ 26; core ack pop event ID và handler đọc latch. Event generator mask `1=chặn`, khác ITC mask `1=mở` ([event trace](../master_analysis/soc_rtl/soc_03_udma_debug_cluster_rtl.md#6-event-uart-trở-lại-fc-qua-queue-arbiter-và-fifo)).

**Stall/state/failure:** FIFO credit và `r_valid` TX phải được kiểm cùng nhau; chưa có bằng chứng integration rằng mọi backpressure giữ dữ liệu. Config UART được sample khi enable edge qua đồng bộ clock, nên thay divider khi enable còn 1 không tự cập nhật serializer. **Verification:** monitor giải mã byte/stop bit ở pad, scoreboard L2 response→FIFO→UART, event ID đúng một lần, full/backpressure và overflow. Phân biệt `descriptor done`, `DMA read response`, `UART busy=0` và `pad stop bit` bằng timestamp riêng.
