# 05 — Điều khiển và state

| Chặng | State quan trọng | Quy tắc cập nhật và hệ quả |
|---|---|---|
| FC TCDM demux | `active_slave_q`, FSM IDLE/PENDING | Nhớ đích response cũ; cho request mới cùng chu kỳ response nếu grant ([phân tích](../master_analysis/soc_rtl/soc_01_fc_memory_rtl.md#4-fsm-demux-nhớ-nhánh-response-không-giữ-toàn-payload)) |
| L2 crossbar | bank/owner select, valid | Arbiter chọn master; select response lấy từ grant trước, không lấy address hiện tại ([phân tích](../master_analysis/soc_rtl/soc_01_fc_memory_rtl.md#5-crossbar-arbitration-và-response-tracking)) |
| AXI→AXI-Lite→APB | AW/W association, outstanding | Instance giới hạn 1 read + 1 write ở bridge; APB chờ `PREADY` ([source](../../../.bender/git/checkouts/pulp_soc-c519334bd3ac5582/rtl/pulp_soc/soc_interconnect_wrap.sv#L226)) |
| Timer | `count`, `target_reached`, CFG | `target_reached` so `next_count`; IRQ có thể tái assert nếu nguồn vẫn high ([phân tích](../master_analysis/soc_rtl/soc_02_timer_irq_rtl.md#5-timer-register-lần-từ-address-tới-next-state)) |
| FC ITC | `r_int`, `r_mask`, `r_ack`, event FIFO | `r_int & r_mask` phát IRQ; ID lớn hơn thắng; ack xóa pending nhưng không xóa timer source ([phân tích](../master_analysis/soc_rtl/soc_02_timer_irq_rtl.md#6-interrupt-controller-pending-mask-priority-và-ack)) |
| Debug arbiter | IDLE/WAIT_GNT/WAIT_VALID | PULP TAP ưu tiên cố định trước DM ở IDLE; giữ owner tới response ([phân tích](../master_analysis/soc_rtl/soc_03_udma_debug_cluster_rtl.md#7-debug-là-master-thực-sự-của-soc)) |
| Cluster gate | lịch sử idle 4 bit, busy/event | Có thể đóng sau 4 mẫu đủ điều kiện; HWPE hiện bật giữ busy theo wrapper, nên không suy gate thực tế từ bench module ([phân tích](../master_analysis/microarchitecture/micro_07_cdc_clock_reset.md#5-cluster-gating-điều-kiện-đóng-và-đường-mở-lại)) |

**Bất biến cần kiểm:** một response về đúng owner đã được grant; không ghi register APB trước `PSEL && PENABLE && PREADY`; không pop event ID hai lần; count outstanding không âm; reset hai đầu CDC không để request cũ xuất hiện như mới. Những bất biến này là mục tiêu kiểm chứng, không phải assertion đã chạy.
