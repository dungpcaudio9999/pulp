# SoC 09 — Kịch bản hệ thống và tiêu chí nghiệm thu

| Kịch bản | Đường đầu-cuối | Checker cần có | Trạng thái |
|---|---|---|---|
| Boot FC | POR→ROM→JTAG load→DPC/resume→L2 fetch→`main` | PC/instruction/exit đúng | Đã có phân tích source, cần waveform build hiện tại |
| FC load L2 | FC data→demux→bank arbiter→SRAM→response | bank/row và owner/data đúng khi tranh chấp | [Trace tĩnh](04_dominant_flow.md) |
| FC timer IRQ | APB store compare→timer target→ITC 11→handler→source clear | một IRQ/handler, không repend sau clear | Demo hiện chưa thử handler |
| UART DMA TX | FC descriptor→uDMA TX đọc L2→FIFO→UART pad→event FIFO→IRQ26 | byte/pad/event ID đúng, không mất dưới backpressure | Chưa có checker tích hợp |
| Cluster offload/DMA | FC ghi boot/fetch→PE start→MCHAN L2↔L1→PE→L2→FC verify | AW/W/B/AR/R, buffer golden, guard, timeout | Demo cũ có 9 phase; chuỗi compute xuyên suốt chưa có |
| Debug contention | TAP và DM cùng request L2 | TAP priority, DM progress dưới pattern hữu hạn | Phân tích arbiter tĩnh |
| Error AXI vs APB | `0x20000000` và `0x1A107000` | lỗi hữu hạn hoặc timeout được phân loại đúng | Chưa tiêm lỗi; APB hole có thể treo |
| RDC/wake | request CDC khi cluster gate/reset | không mất/lặp transaction; abort có contract | Chưa nghiệm thu |

Nguồn chi tiết: [boot](soc_08_boot_flow.md), [address](soc_03_address_map.md), [interrupt](soc_04_interrupt_map.md), [domain transactions](../master_analysis/architecture/deep_dive_05_domain_transactions.md#3-lần-theo-demo-đang-có-rtl-sw). Với mỗi ca mới, lưu command, source/ELF hash, timeout, log, waveform và checker. [M8](../master_analysis/microarchitecture/micro_08_validation.md#5-ma-trận-nghiệm-thu-tích-hợp-tiếp-theo) nêu ranh giới giữa test component và tích hợp; không nâng nhãn PASS của component thành PASS toàn SoC.
