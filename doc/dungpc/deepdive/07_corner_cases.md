# 07 — Ca biên và đường lỗi

| Tình huống | Hệ quả từ source | Phép thử cần làm |
|---|---|---|
| Cuối shared L2 `0x1C08FFFC` rồi `0x1C090000` | Địa chỉ đầu vào bank 3; địa chỉ sau ra nhánh AXI default ([decode](../master_analysis/soc_rtl/soc_01_fc_memory_rtl.md#3-decode-gồm-hai-cấp-và-một-remap-riêng)) | Read/write hai phía biên, kiểm target và response |
| ROM window 256 KiB, storage 8 KiB | Index bị cắt; nhiều địa chỉ cửa sổ alias cùng word ROM ([ROM](../master_analysis/soc_rtl/soc_01_fc_memory_rtl.md#3-decode-gồm-hai-cấp-và-một-remap-riêng)) | Fetch hai địa chỉ cách `0x2000`, kiểm alias được chấp nhận hay là gap spec |
| Unmapped AXI `0x20000000` | Decode error downstream có response lỗi; FC loại 0 không chắc trap bus error do wiring ([FC control](../master_analysis/microarchitecture/micro_09_fc_control_plane.md#4-exception-trap-và-bus-error-boundary)) | Đọc `r_opc`, `mcause`, PC và watchdog |
| Trong peripheral lớn nhưng APB không chọn, ví dụ `0x1A107000` | APB node để `PREADY=0`, có thể treo vô hạn ([timer/APB](../master_analysis/soc_rtl/soc_02_timer_irq_rtl.md#4-hai-cấp-decode-apb-và-ba-kiểu-địa-chỉ-không-hợp-lệ)) | Timeout ngoài, không chạy trực tiếp trên hệ không có watchdog |
| Timer source high sau ITC ack | Pending có thể set lại; clear nguồn trước khi cho IRQ tiếp ([ITC](../master_analysis/soc_rtl/soc_02_timer_irq_rtl.md#6-interrupt-controller-pending-mask-priority-và-ack)) | Ack trong lúc comparator còn high |
| Debug TAP và DM cùng đòi bus | TAP ưu tiên lúc IDLE; DM có thể đói nếu TAP liên tục ([arbiter](../master_analysis/soc_rtl/soc_03_udma_debug_cluster_rtl.md#7-debug-là-master-thực-sự-của-soc)) | Concurrency bounded-latency hoặc ghi rõ không có bound |
| Reset một CDC endpoint khi có AW/W | Có thể mất association/response; chưa có recovery contract ([CDC](../master_analysis/microarchitecture/micro_07_cdc_clock_reset.md#6-reset-contract-và-reset-khi-còn-giao-dịch)) | Scoreboard accepted/completed/aborted, formal RDC |

**Không gắn nhãn bug xác nhận** cho các ca chưa có test; bảng phân biệt hành vi RTL, giới hạn spec và việc cần kiểm.
