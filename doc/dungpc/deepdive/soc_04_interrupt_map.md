# SoC 04 — Interrupt và event

| Nguồn | Tín hiệu/ID | Đường đến FC | Mask/clear | Bằng chứng |
|---|---|---|---|---|
| Timer low | ITC bit 10 | `fc_events_o[10]` trực tiếp | ITC mask 1=mở; clear timer source và pending | [timer](../master_analysis/soc_rtl/soc_02_timer_irq_rtl.md#6-interrupt-controller-pending-mask-priority-và-ack) |
| Timer high | ITC bit 11 | `fc_events_o[11]` trực tiếp | như low; nguồn high có thể repend | [timer](../master_analysis/soc_rtl/soc_02_timer_irq_rtl.md#5-timer-register-lần-từ-address-tới-next-state) |
| SoC event/uDMA UART | IRQ 26, FIFO giữ event ID 8 bit | source queue→arbiter→FC FIFO→ITC | event mask 1=chặn; core ack 26 pop ID | [uDMA/event](../master_analysis/soc_rtl/soc_03_udma_debug_cluster_rtl.md#6-event-uart-trở-lại-fc-qua-queue-arbiter-và-fifo) |
| Cluster event/wake | event ID qua CDC | SoC→cluster event FIFO | ready/valid, gate wake | [CDC](../master_analysis/microarchitecture/micro_07_cdc_clock_reset.md#4-event-pulse-và-event-id-là-hai-protocol-khác-nhau) |

ITC giữ sticky `r_int`, mask `r_mask`, ack lịch sử `r_ack`; `core_irq_req_o=|(r_int&r_mask)`. Encoder vòng tăng dần ghi đè ID nên **ID lớn nhất có priority cao nhất** trong các bit đang enabled. Core ack đúng ID thắng set cùng chu kỳ; nếu nguồn timer vẫn assert, pending có thể lập lại sau đó ([ITC analysis](../master_analysis/soc_rtl/soc_02_timer_irq_rtl.md#6-interrupt-controller-pending-mask-priority-và-ack)). FIFO event không pop bởi APB read; core ack IRQ 26 hoặc thao tác clear phù hợp mới pop, và ID đã pop được latch để handler đọc.

**Trace cần nghiệm thu:** đặt compare timer high, mở mask 11, thấy target_reached→pending→IRQ→core handler→clear source→ack→không repend. Kịch bản khác phải test hai timer cùng lúc, IRQ 26 cùng timer, mask thay đổi khi pending, WFI và reset. `full_system` hiện đọc counter timer; chưa chứng minh handler đã chạy ([giới hạn demo](../master_analysis/soc_rtl/soc_02_timer_irq_rtl.md#8-đối-chiếu-demo-và-cách-kiểm-chứng-tiếp)).
