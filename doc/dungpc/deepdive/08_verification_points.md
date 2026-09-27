# 08 — Điểm kiểm chứng SoC

| Concern | Stimulus | Checker | Coverage tối thiểu | Trạng thái |
|---|---|---|---|---|
| Decode | FC/debug/uDMA tại đầu/cuối ROM, private, shared, APB, cluster, hole | đúng target, không chọn đôi, đúng response | master × region × read/write × boundary | Chưa có sweep tích hợp |
| L2 contention | FC và uDMA cùng bank, rồi khác bank | grant owner, response owner/data, no starvation theo policy thực | 2+ master × bank × stall | Bench xbar component không thay thế tích hợp |
| AXI/APB | AW trước W, W trước AW, APB stall | không side effect trước Access; B sau write; payload ổn định | ordering × PREADY delay × error | Chưa có kiểm tra đầu-cuối |
| Timer/ITC | compare, mask, ack đồng thời source high | pending/priority/clear, handler marker | timer low/high × mask × priority × sleep | Demo hiện chỉ đọc counter |
| uDMA/event | burst TX/RX, FIFO full, ready thấp | byte tại pad, event ID một lần, overflow status | source × mask × backpressure | Cần tích hợp |
| CDC/RDC | AW/W/B và AR/R qua hai clock, reset/gate idle và busy | accepted=completed+aborted, không lặp/mất | channel × reset side × occupancy | Component CDC đã test; reset busy chưa |
| Security/error | PMP deny, unmapped AXI, APB hole | target không side effect, phản hồi/trap đúng theo contract | initiator × privilege × region | Contract sản phẩm chưa có |
| Boot | POR→ROM→debug load→L2 fetch | PC, instruction, entry, `main`, exit | boot source × reset mode | Log cũ có; cần capture checkout hiện tại |

Nguồn kế hoạch từ [guide](../../../../uni/SoC_RTL_Analysis_Guide.md), điều chỉnh theo [phân tích RTL SoC](../master_analysis/soc_rtl/soc_00_phuong_phap_phan_tich_rtl.md) và [ma trận M8](../master_analysis/microarchitecture/micro_08_validation.md#5-ma-trận-nghiệm-thu-tích-hợp-tiếp-theo). Mỗi test mới cần lưu command, defines/parameters, HEAD dependency, ELF hash, timeout, log và waveform; một test component không chứng minh kết nối cấp chip.
