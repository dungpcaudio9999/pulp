# Chuyên sâu 02 — SoC domain: FC, L2, ngoại vi và event

Áp dụng [cấu hình RTL Questa và quy ước bằng chứng](deep_dive_00_effective_configuration.md),
đối chiếu 2026-09-10. Dependency đã có; các kết luận dưới đây đi vào implementation.

Phần phân tích RTL chi tiết được triển khai thành bốn bài:
[phương pháp và mẫu tái sử dụng](../soc_rtl/soc_00_phuong_phap_phan_tich_rtl.md),
[FC → ROM/L2](../soc_rtl/soc_01_fc_memory_rtl.md),
[FC → APB timer → IRQ](../soc_rtl/soc_02_timer_irq_rtl.md),
[uDMA/UART, debug và cluster](../soc_rtl/soc_03_udma_debug_cluster_rtl.md).
Các bài này bổ sung port binding, FSM, phương trình next-state, bảng chu kỳ,
semantics completion và cách kiểm chứng cho phần tổng quan dưới đây.

## 1. Vai trò và ranh giới [RTL]

[soc_domain](../../../../rtl/pulp/soc_domain.sv) là wrapper quanh `pulp_soc_i`, truyền
tham số/cổng bằng `.*`, buộc `boot_l2_i=0` và đổi tên output debug IRQ.
SoC chứa FC, L2, ROM, debug, interconnect, peripheral/uDMA và event routing;
nhận reference/reset từ safe domain, cấp clock/reset và giao dịch cho cluster.

## 2. Cấu trúc hiệu lực [RTL]

Nguồn chính: [pulp_soc](../../../../.bender/git/checkouts/pulp_soc-c519334bd3ac5582/rtl/pulp_soc/pulp_soc.sv),
[soc_peripherals](../../../../.bender/git/checkouts/pulp_soc-c519334bd3ac5582/rtl/pulp_soc/soc_peripherals.sv).

| Nhóm | Instance/implementation | Điều cần phân biệt |
|---|---|---|
| FC | `fc_subsystem_i`, `FC_CORE.lFC_CORE:riscv_core` | FC instruction và data là hai master riêng |
| Memory | `boot_rom_i`, `l2_ram_i` | cửa sổ địa chỉ khác dung lượng vật lý |
| Interconnect | `i_soc_interconnect_wrap` | nhánh contiguous, interleaved, TCDM→AXI |
| Peripheral | `soc_peripherals_i` | APB control và uDMA data là hai đường |
| Clock/reset | `i_clk_rst_gen` | reset sync theo clock đích; xem bài 04 |
| Debug | TAP/DMI/debug module | có master truy cập memory riêng |

HWPE FC tắt trong demo; module FPU FC được bật nhưng smoke test số nguyên không
chứng minh FPU hoạt động. Các nguồn uDMA cũng không được coi đã chạy chỉ vì được instantiate.

## 3. Hoạt động: decode memory và sự kiện [RTL]

### L2 và instruction/data

[Map/decode](../../../../.bender/git/checkouts/pulp_soc-c519334bd3ac5582/rtl/pulp_soc/soc_interconnect_wrap.sv#L90)
và [SRAM implementation](../../../../.bender/git/checkouts/pulp_soc-c519334bd3ac5582/rtl/pulp_soc/l2_ram_multi_bank.sv):

| Vùng, end exclusive | Dung lượng vật lý/đường đi |
|---|---|
| `0x1C000000–0x1C008000` | private bank 0: 8192 word × 4 B = 32 KiB |
| `0x1C008000–0x1C010000` | private bank 1: 32 KiB; entry demo tại `0x1C008080` |
| `0x1C010000–0x1C090000` | 4 bank interleaved × 32768 word × 4 B = 512 KiB |
| `0x1A000000–0x1A040000` | cửa sổ ROM; ROM thực 8 KiB |
| `0x10000000–0x10400000` | TCDM→AXI, cửa sổ cluster |
| `0x1A100000–0x1A400000` | TCDM→AXI→AXI-Lite→APB, ngoại vi |

Tổng SRAM L2 vật lý là **576 KiB**. Linker runtime khai báo vùng L2 gần 512 KiB
(`ORIGIN=0x1C000004`, `LENGTH=0x7FFFC`), nên dung lượng linker dùng không đồng
nghĩa tổng SRAM RTL. Không đụng toàn vùng memory khi chương trình/stack đang ở đó.

Với `A` thuộc shared L2, `offset=A-0x1C010000`:

```text
bank = (offset >> 2) & 3       // A[3:2]
row  = offset >> 4            // memory cắt các bit byte/bank
```

FC instruction/data, uDMA TX/RX, debug và 4 cổng từ AXI Cluster→SoC cùng có thể
đến shared banks. Các request khác bank có khả năng phục vụ song song;
cùng bank phải qua arbitration. “Private” mô tả vùng/bank liên tục, không phải
cơ chế bảo vệ cấm mọi master khác. FC data còn remap prefix `0x000` sang `0x1C0`
trong wrapper; không tự áp dụng alias này cho mọi master.

### Timer interrupt khác SoC event FIFO

```text
APB timer compare → s_timer_lo_event/hi_event
→ fc_events_o[10]/[11] → fc_subsystem.events_i
→ apb_interrupt_cntrl: pending & mask → core_irq_req/id
→ riscv_core → irq_ack/id → controller
```

Đây là đường **direct interrupt**; không đi vòng qua FIFO sự kiện SoC.
Trong `apb_interrupt_cntrl`, `core_irq_req_o=|(r_int & r_mask)`.

Đường uDMA/peripheral event khác:

```text
s_udma_events / GPIO / advanced timer
→ soc_event_generator (mask, phân phối FC/cluster)
→ FC event FIFO (4 entry trong apb_interrupt_cntrl)
→ interrupt bit 26 → core
```

FC phải đọc mã event để biết peripheral nào báo. Không nhầm FIFO FC 4 entry
với FIFO CDC SoC→cluster 8 entry. Nguồn:
[interrupt controller](../../../../.bender/git/checkouts/apb_interrupt_cntrl-dd2e5ce27b208df0/apb_interrupt_cntrl.sv#L87).
Đọc register FIFO trả ID đã được latch ở lần pop gần nhất; thao tác đọc không
tự pop. Core ack IRQ 26 hoặc software clear tương ứng mới tạo pop. Event
generator mask bit 1 là chặn, còn FC interrupt mask bit 1 là cho phép.

### UART/uDMA: control và data

CPU cấu hình UART/descriptor qua đường data FC→interconnect→APB→`i_udma`.
Sau đó uDMA TX tự đọc buffer L2 qua master TX; uDMA RX tự ghi L2 qua master RX.
UART serializer đi qua `uart_tx_o` tới pad_control/pad_frame. `printf` qua stdout
model của TB không chứng minh đường này. Cần byte thực trên pad và buffer RX
được đối chiếu mới nghiệm thu UART/uDMA.

## 4. Góc nhìn phần mềm [SW]

[Bài 04](deep_dive_04_boot_debug_testbench.md) lần đầy đủ reset→ROM→DPC→startup.
Bài timer hiện tại dùng `timer_base_fc(0,1)`: timer high tại base `0x1A10B004`;
HAL reset/start/read tương ứng `0x1A10B024`, `0x1A10B01C`, `0x1A10B00C`.
[Phase 2](../../../../sw/full_system/full_system.c#L42) chỉ kiểm tra count tiến lên.

Để mở rộng thành timer interrupt, cần handler/vector, xóa pending cũ, cấu hình
comparator và IRQ-enable, mở mask FC cho bit 11 (hoặc bit 10 nếu chọn timer low),
mở interrupt trong core, start rồi đếm số lần handler chạy. Sau handler phải
xử lý nguồn/pending theo mode timer; chỉ thấy pending chưa chứng minh core nhận IRQ.
Nguồn register: [timer_v2](../../../../pulp-runtime/include/archi/timer/timer_v2.h),
[HAL timer](../../../../pulp-runtime/include/hal/timer/timer_v2.h).
Đây là trình tự thử **[CẦN ĐO]**, chưa có trong phase 2.
Implementation timer phải lấy từ dependency `timer_unit/rtl/apb_timer_unit.sv`
được `sim/compile.tcl` chọn, không phải file cùng tên trong `pulp_soc/rtl/components`.

Khởi động cluster dùng `cluster_start()` ghi remote boot address và fetch mask,
không dùng trực tiếp các output `cluster_boot_addr_o/cluster_fetch_enable_o`
đang không được cluster wrapper tiêu thụ; xem bài 03.

## 5. Thời gian, tranh chấp và điều kiện chờ

**[RTL]** SRAM/ROM có response đăng ký tại memory port. FC instruction thường
truy cập L2 nên tranh chấp instruction/data ảnh hưởng trực tiếp; linker cố tách
FC code/data sang private banks. Đường APB/AXI, arbitration và CDC làm latency
khác latency một chu kỳ của SRAM.
Crossbar L2 tự tạo response valid từ grant với `RespLat=1`; nó không chờ tín hiệu
r_valid của SRAM để quyết định hoàn tất. Đây là contract fixed latency cần giữ
khi thay implementation memory. APB decode miss ở peripheral node lại giữ
PREADY=0; không phải mọi địa chỉ sai đều có response lỗi hữu hạn. Bus error
cũng chưa chứng minh FC core loại 0 nhận access-fault, vì wiring không nối
core_instr_err/core_data_err vào nhánh core này.

**[CẦN ĐO]** Giữ nguyên ELF, FLL và tải DMA khi so sánh private/shared banks.
Đo req→gnt và gnt→rvalid riêng để tách arbitration khỏi response. Không lấy thời
gian nạp JTAG hay `printf` làm thời gian giao dịch memory.

## 6. Bằng chứng và phép kiểm chứng

| Phép thử | Hiện có | Tiêu chí bổ sung |
|---|---|---|
| FC/L2 | phase 1 checksum buffer; SIM cũ ở log 06 | từng vùng được cấp phát an toàn, pattern theo bank/row và ranh giới |
| Timer | phase 2 count tăng | handler đúng IRQ, đúng số lần, mask tắt thì không có handler |
| UART TX | chưa có trong demo mặc định | monitor giải mã đúng chuỗi byte, baud và stop bit tại pad |
| uDMA RX/TX | chưa có trong demo | size/status hoàn tất **và** buffer khớp, guard vùng ngoài transfer không đổi |
| FC completion | core status/EOC qua debug | phân biệt exit 0, lỗi nội dung và watchdog timeout |

**[SIM cũ: 2026-09-06, lượt 06]**
[Log PASS](../../../../report/full_system_20260906/06_PASS_toan_bo_9_phase.log) chỉ chứng
minh các phép kiểm tra có trong phiên bản chương trình lúc đó. Không gắn kết
quả này cho các hàng “chưa có” hoặc cho source đã đổi mà chưa chạy lại.
