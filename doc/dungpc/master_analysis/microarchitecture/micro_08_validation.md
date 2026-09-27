# M8 — Kiểm chứng microarchitecture: kết quả mới và phần chưa nghiệm thu

Ngày: 2026-09-13. [Plan](micro_00_plan_phan_tich_pulp.md) đã được tiếp tục qua
M4–M7; M8 có thêm kiểm chứng component, **chưa hoàn tất kiểm chứng tích hợp**.

## 1. Phương pháp kiểm chứng

Đổi mỗi nhận định tĩnh thành một phép thử có phản ví dụ. Ví dụ “FIFO không
tràn” cần phát request trước, trì hoãn response, khóa consumer rồi kiểm số
credit; test chỉ push/pop khi luôn ready không chạm đến vấn đề outstanding.

Bench instantiate module RTL thật từ dependency checkout, stimulus thay thế
các endpoint còn lại. Dữ liệu/response được kiểm tại handshake, có timeout
và `$fatal` khi sai. Giữ compile log, run log, VCD, tham số và hash source;
không tính việc generate tài liệu hoặc kiểm link là simulation.

[Report và lệnh chạy lại](../../../../report/microarchitecture_20260913_remaining/README.md)
chứa bốn bench mới. [Report LSU trước đó](../../../../report/microarchitecture_20260913/README.md)
được giữ riêng để không trộn phạm vi và log.

## 2. Kết quả đã chạy

| Phép thử | RTL và cấu hình | Kết quả mới | Phạm vi kết luận |
|---|---|---|---|
| TX credit | io_tx_fifo + io_generic_fifo, 8 bit, depth 2 | 9 checks PASS | Hai inflight giữ chỗ; response trễ và consumer stall không mất/đảo A/B |
| Event counter | soc_event_queue default | 5 checks PASS | Count 0..3; full+event+ack vẫn báo err; ba ack drain |
| APU dispatch | riscv_apu_disp, stimulus class 2/3 | 8 checks PASS | Nack, full, RAW, ordered destinations, class conflict |
| Barrier | hw_barrier_unit, NB_CORES=4, bus config thật | 5 checks PASS | Mask, duplicate arrival, missing/extra participant, release/clear |
| Clock gate | cluster_clock_gate + tc_clk_gating, NB_CORES=4 | 4 checks PASS | Bốn mẫu idle đóng gate; không có output edge; incoming mở lại |
| CDC FIFO | width 16, LOG_DEPTH=2, sync mặc định 2; clocks 7/11 ns | 64/64 data đúng thứ tự; max pending 6 | Flow control, pointer wrap nhiều vòng, spill capacity; không kiểm metastability |
| Xbar contention | xbar + addr_dec_resp_mux + rr_arb_tree, 4×4, RespLat=1 | 16 request / 16 response đúng | Same-bank serialization, different-bank parallelism, bank stall, owner/data |
| DMA completion | synch_unit, SID=3, SID width 4, command counter width 8, burst parameter 256 | 12 checks PASS | Hai phía cùng drain, SID filtering, simultaneous enqueue/retire |

Năm hàng đầu nằm trong một bench `tb_control.sv`, tổng **31 checks**. DMA có
**12 checks riêng**; CDC và xbar dùng scoreboard. Không cộng 64 payload hoặc
16 response thành số test case độc lập. LSU PASS 20 là kết quả của đợt đầu,
không phải số check phát sinh trong lượt tiếp tục này.

APU class 2/3 và DMA counter width 8 là cấu hình kiểm module; không phải tất
cả parameter của FPU/DMAC trong full-system. Xbar dùng load (`wen_i=0` theo
convention nội bộ xbar), target fixture trả payload XOR signature qua register
một chu kỳ; không có SRAM hoặc AXI bridge trong bench.

## 3. Các số đo được phép sử dụng

| Thử xbar | Bank bị chặn trước khi phục vụ | Chu kỳ phục vụ 4 requests sau khi mở bank | Accepted requests / service cycle |
|---|---:|---:|---:|
| 4 bank khác nhau | 0 | 1 | 4 |
| cùng một bank | 0 | 4 | 1 |
| cùng một bank | 3 | 4 | 1 |
| 4 bank khác nhau | 2 | 1 | 4 |

Đếm tại cạnh `req && gnt`; span phục vụ không gồm các chu kỳ cố ý chặn bank.
Response valid/data được kiểm sau cạnh cập nhật register của target và xbar.
Đây là throughput của primitive và fixture đã nêu, không phải IPC FC,
bandwidth HCI cluster, hay bandwidth L2 end-to-end.

CDC: source bị stall 111 chu kỳ có valid; consumer ban đầu chặn, sau đó ready
bị hạ theo modulo 5/7 của destination counter. First accept → first delivery
289 ns chứa thời gian chặn có chủ ý. Dùng số này để tái lập testcase, không
lấy làm hằng số CDC latency. Source accept 6 khi consumer chưa nhận gì xác
nhận 4 ô storage cộng 2 ô spill.

## 4. Preflight full-system và giới hạn môi trường

Đã chạy `vsim -c -do quit` với license environment `27001@localhost`; simulator
thoát mã 4, báo **Unable to checkout a license / Invalid license environment**.
[Lưu preflight](../../../../report/microarchitecture_20260913_remaining/questa_preflight.log)
ghi lỗi thực. Đây là thử khởi động simulator, chưa load tb_pulp và chưa chạy
workload full_system.

Runner hiện tự khởi động lmgrd và ghi log trong thư mục cài Questa ngoài
workspace. Lượt này không đổi cấu hình license/server để thay cho phân tích RTL.
Các phép thử mới chạy bằng Verilator không cần license. Có binary/library
trong sim directory không chứng minh simulator hiện có thể chạy hay library
khớp source; cần compile/elaborate lại khi làm nghiệm thu tích hợp.

Không dùng PASS full_system 2026-09-06 để đóng những testcase của source hiện
nay. M8 giữ trạng thái một phần vì còn thiếu tích hợp và coverage, không chỉ
vì thiếu một con số timing.

## 5. Ma trận nghiệm thu tích hợp tiếp theo

Các hàng này là công việc còn lại của M8, **chưa có PASS mới**. Chúng xác định
stimulus, điểm đo và điều kiện đạt để tiếp tục mà không phải thiết kế lại plan.

| Ưu tiên / đường | Stimulus cụ thể | Điểm đo / scoreboard | Điều kiện đạt |
|---|---|---|---|
| P0 FC→SoC | load-use; store→load; split qua bank; master uDMA giả cạnh tranh | ID/EX/WB, LSU state, req/gnt, bank owner, rvalid, RF write | Data/RF đúng; accepted/completed khớp; đo stall do grant riêng response |
| P0 uDMA TX | channel 0 và channel khác; FIFO credit cạn; response trễ; byte offsets 0..3 | metadata ID, binary r_resp, r_valid, peripheral ready, UART TX pin | Mỗi byte đúng một lần; no overwrite; xác định effect của s_stall |
| P0 DMA/compute | L2→TCDM, barrier, kernel dùng input đã DMA, TCDM→L2 | SID, AR/R/AW/W/B, TCDM data, result và term | Output so với golden; done sau completion hai phía |
| P0 reset contract | quiesce/drain hợp lệ; reset có outstanding chỉ với protocol abort được định nghĩa | ID ledger ở hai phía CDC và bridge | Mỗi accepted work completed hoặc explicitly aborted; không ghost response |
| P1 I-cache | cold/warm cùng code; stride đổi shared bank; flush; prefetch conflict | private/shared miss, refill queues/IDs, AR/R, PC trace | Instruction đúng; đo từng thành phần miss penalty |
| P1 TCDM HCI | 8 PE base+4*id so với base+64*id, thêm DMA rồi HWPE | per-bank grants, stall, owner và result | Mapping/data đúng; có thống kê fairness/starvation từng nhóm |
| P1 FPU | dependency chain và independent streams, 1/8 PE, mixed add/div/sqrt | issue/gnt/return/tag/RF/fflags | Numerical golden + ordered writeback; tách contention/dependency |
| P1 HWPE | aligned/unaligned, lengths và 2D strides, sink stall | source/sink beat counts, addresses, FIFO, done, output RAM | Copy đúng; done không sớm; đo bytes và traffic TCDM |
| P1 EU/barrier | actual PE wait/clear, 8 participants; IRQ/debug lúc sleep | event buffer/masks, core clocks, barrier status, PC | Không deadlock/lost wake; mỗi vòng barrier release đúng tập PE |
| P1 cluster gating | HWPE tắt để có idle; event wake; kiểm driver incoming trước AXI wake | ungated/gated clocks, busy OR, FIFO valid, history | Thực sự có clock-off/on và work tiếp tục đúng |
| P2 multicast events | một destination ready, một destination stall, mask/unmask | source count và accepted ID từng destination | Không mất/lặp delivery theo specification |
| P0 FC control | IRQ cùng branch/PMP/debug; WFI wake; ELW grant+IRQ; loop 16/32-bit | controller state, IF/ID/EX PC, mepc/dpc/cause, ack, loop counter | Đúng priority; không skip/duplicate; ack/event ledger cân bằng |
| P0 AXI bridges | 4 source tranh target; stall riêng AW/AR/W/R/B; access decode gap | xbar ID, bridge FSM/FIFO, internal gnt/rvalid, AXI response | Owner/data/order đúng; không deadlock; error quan sát khớp RTL/spec |
| P1 width conversion | S2C byte/half/word, burst, crossing 64-bit boundary | AW/W/AR/R trước-sau converter, address/lane/strobe | Byte lane và beat count đúng; read/write scoreboard khớp |
| P1 uDMA protocols | SPI/I2C/SDIO/I2S/camera/filter/Hyper với pad/model và stall | buffer done, protocol EOT/error, FIFO/CDC, L2 data | Phân biệt đúng completion; không mất/lặp data/event; protocol model PASS |
| P2 interrupt corner | core ack và event mới cùng IRQ bit; nhiều pending ID | r_int/r_mask, selected ID, FIFO pop, ISR count | Kết quả đúng priority đã định; software không mất source ngoài contract |

P0 reset không yêu cầu FIFO hỗ trợ warm reset ngoài contract của nó. Nếu
specification muốn reset độc lập, cần thiết kế cơ chế clear/abort trước khi
đặt kỳ vọng scoreboard. Các phát hiện s_incoming_req chưa thấy driver và
HWPE busy hằng phải được xử lý trong cấu hình/test trước khi đo clock gating
end-to-end.

Năm hàng bổ sung ngày 2026-09-19 xuất phát từ closure L3
([M9](micro_09_fc_control_plane.md), [M10](micro_10_udma_peripherals.md),
[M11](micro_11_cluster_axi_bridges.md)); chúng chưa có nhãn PASS.

## 6. Cách đọc waveform để học cách phân tích source khác

1. Đánh dấu cạnh nhận work đầu tiên, đừng bắt đầu từ một xung done cuối cùng.
2. Ghi mỗi state đang giữ work: ID/address, valid, FIFO occupancy hoặc counter.
3. Khi có stall, lần ngược readiness tới tài nguyên đầu tiên không nhận được.
4. Đối chiếu output data/owner khi completion, rồi mới tính latency.
5. Tách startup, warmup, steady-state, drain; báo mẫu số throughput cụ thể.
6. Chạy phản ví dụ làm giả thuyết thất bại: extra barrier bit, bank conflict,
   delayed response, downstream full. Không chỉ chạy đường always-ready.
7. Viết rõ phần nào instantiate RTL và phần nào là fixture. Test module qua
   không thay thế proof integration, numerical verification hay timing sign-off.
