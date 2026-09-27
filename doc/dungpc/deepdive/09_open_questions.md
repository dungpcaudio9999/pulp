# 09 — Câu hỏi mở và điều kiện đóng

| Ưu tiên | Câu hỏi | Bằng chứng cần để đóng |
|---|---|---|
| P0 | Cấu hình runner này đã compile/elaborate đúng từ checkout hiện tại chưa? | command, log compile/vopt, hierarchy, HEAD/hash dependency |
| P0 | APB hole và HWPE SoC tắt có timeout/recovery ở tầng nào? | đường `PREADY`, timeout counter hoặc test watchdog; nếu không có, ghi contract software tránh vùng đó |
| P0 | FC RI5CY xử lý lỗi bus/unmapped thế nào so với PMP fault? | waveform `r_opc`, core error input, `mcause`, PC; không suy từ Ibex branch |
| P0 | Reset một phía CDC lúc còn outstanding có chính sách abort/drain không? | spec, RTL reset-sequence controller hoặc test/formal RDC theo từng channel |
| P1 | Clock gate cluster có wake đáng tin cậy với incoming AXI và HWPE bật không? | elaboration driver `incoming_req`, busy, event, gate output; waveform integration |
| P1 | UART event multicast khi một destination backpressure có giao đúng một lần không? | ready/valid từng destination, ID scoreboard, overflow |
| P1 | Địa chỉ ROM alias và vùng APB invalid là hành vi được kiến trúc cho phép? | spec/register map được phê duyệt, test boundary |
| P1 | Buffer L2/L1 chia sẻ giữa FC, DMA và PE cần fence/maintenance nào? | runtime sequence, cache policy và test visibility |
| P2 | Có contract secure boot, debug auth, lifecycle, QoS, power isolation/retention không? | tài liệu sản phẩm và điểm enforcement thực tế; hiện không thể khẳng định từ source đã xem |

Thứ tự ngắn nhất để tiến tiếp: **elaboration cấu hình → một load FC/L2 có waveform → một store APB + IRQ → một DMA C→S có B/R → ca reset/error âm**. Mỗi mục chỉ đóng khi có kết quả checker và đường dẫn bằng chứng, không đóng bằng mô tả module.
