# Chuyên sâu 03 — Cluster: PE, cache, TCDM, event và DMA

Đối chiếu 2026-09-10 theo [cấu hình hiệu lực](deep_dive_00_effective_configuration.md).
Dependency đã được đọc trực tiếp. Mặc định các kết luận cấu trúc là **[RTL]**;
trình tự runtime là **[SW]**; kết quả chạy cũ và phép đo mới được ghi riêng.

## 1. Vai trò và ranh giới

[cluster_domain](../../../../rtl/pulp/cluster_domain.sv) bọc
[pulp_cluster](../../../../.bender/git/checkouts/pulp_cluster-48721e3ce381c984/rtl/pulp_cluster.sv).
Cluster nhận clock/reset, giao dịch AXI và event từ SoC; thực thi 8 PE với L1
TCDM dùng chung; truy cập L2 bằng core/cache refill/DMA qua AXI master 64 bit.
FC cấu hình cluster qua AXI master SoC→cluster 32 bit. Hai chiều đặt tên theo
**bên phát request**, không theo chiều byte dữ liệu.

## 2. Cấu trúc thực sự tồn tại

| Khối | Implementation trong `pulp_cluster` | Cấu hình đáng chú ý |
|---|---|---|
| PE | vòng generate `core_region_i` | 8 core loại 0, boot/fetch riêng |
| Instruction | `icache_top_i:icache_hier_top` | `PRIVATE_ICACHE`; private 512 B/core; shared size parameter 4 KiB |
| Data | `cluster_interconnect_wrap_i`, `tcdm_banks_i` | 16 bank × 4 KiB, HCI nối PE/DMA/external/HWPE |
| Control/EU | `cluster_peripherals_i` | cluster control, event unit, timer, cache control |
| DMA | `dmac_wrap_i` | MCHAN, cổng L1 và AXI external |
| FPU | `i_shared_fpu_cluster` | `NB_FPNEW=4`, `NB_APUS=1`; tài nguyên chia sẻ |
| HWPE | `hwpe_subsystem`, nhánh datamover | demo bật; `N_MASTER_PORT=4` do top override |
| Biên domain | AXI CDC, event FIFO, edge propagator | clock input và clock sau gate có vai trò khác nhau |

Có nhiều implementation interconnect/cache trong compile list; ở đây lần theo
nhánh generate thực tế, không suy tên instance từ module cũ.

## 3. Hoạt động: boot PE, instruction/data và đồng bộ

### Boot/fetch không phụ thuộc dây fetch bị buộc 0

Top buộc `fetch_en_i=0`, `en_sa_boot_i=0`, `base_addr_i=0`, `cluster_id_i=0`.
Nhưng `pulp_cluster` dùng **`fetch_en_int=fetch_enable_reg_int`**. Register được
[cluster_control_unit](../../../../.bender/git/checkouts/cluster_peripherals-cc771700129bb934/cluster_control_unit/cluster_control_unit.sv#L267)
ghi qua peripheral bus; output tới từng `core_region_i` cùng `boot_addr[i]`.
Đường standalone FSM `RESET→BOOT→WAIT_FETCH→LIMBO` là một cơ chế khác; dây ngoài
bằng 0 không chặn ghi register từ FC.

### Instruction cache và refill

PE phát instruction req/address, cache trả grant/valid/data. Miss ở các tầng
cache cần refill qua `s_core_instr_bus` tới AXI Cluster→SoC và L2. Refill dùng
chung tài nguyên AXI với DMA và core external data; dữ liệu ở L1 không có nghĩa
mã lệnh cũng lấy từ L1. `CACHE_SIZE` của wrapper không đủ mô tả private/shared
cache: nhánh `PRIVATE_ICACHE` đặt các tham số riêng trong instance.

### Ánh xạ TCDM và arbitration

[HCI wrapper](../../../../.bender/git/checkouts/pulp_cluster-48721e3ce381c984/rtl/cluster_interconnect_wrap.sv#L65)
nối 8 core, 4 DMA port, 4 external port và HWPE tới 16 bank.
Đường core/DMA/external qua `hci_log_interconnect → tcdm_interconnect`; module
cuối tách bank bằng `add_i[ByteOffWidth+NumOutLog2-1:ByteOffWidth]`.
Với word 32 bit và 16 bank, `ByteOffWidth=2`, `NumOutLog2=4`:

```text
bank = (A >> 2) & 15          // A[5:2]
row  = offset_trong_L1 >> 6
```

Nguồn: [tcdm_interconnect](../../../../.bender/git/checkouts/cluster_interconnect-abcda71a83f4333c/rtl/tcdm_interconnect/tcdm_interconnect.sv#L71).
Với base căn 64 B, PE `p` truy cập `base+4*p` thì khác bank; `base+64*p` thì
cùng bank, khác row. HWPE có đường rộng và arbitration HCI riêng; không biến
công thức core bank thành công thức throughput HWPE.

### Event unit

Runtime mở các mask dispatch/mutex/barrier, cấu hình barrier 0 với mask `0xFF`,
rồi `synch_barrier()` gọi `eu_bar_trig_wait_clr()`. Các PE phải cùng tham gia
trước khi barrier cho đi tiếp. Mask nhận sự kiện, mask PE tham gia và fetch mask
là những cấu hình khác nhau cần thống nhất khi đổi số PE.

Mutex dùng cho `cl_report()` gom lỗi của các PE; dispatch là khả năng EU nhưng
`full_system` không có bài kiểm chứng riêng cho dispatch. Chờ bằng event có
thể ngủ; polling status DMA của demo vẫn khiến core hoạt động.

## 4. Góc nhìn phần mềm và luồng DMA [SW]

[cluster_start()](../../../../pulp-runtime/kernel/cluster.c#L62) lưu function entry,
khởi tạo FLL/L1 allocator, bật I-cache, cấp stack rồi ghi:

| Tác động | Địa chỉ cho cluster 0 | Hàm |
|---|---|---|
| boot mỗi PE | `0x10200040 + 4*core` | `plp_ctrl_core_bootaddr_set_remote()` |
| bật fetch PE | `0x10200008`, giá trị `0xFF` | `eoc_fetch_enable_remote()` |
| stack riêng | L1 base cấp phát + `(core_id+1)*CLUSTER_STACK_SIZE` | `crt0.S:pe_start` |
| chạy entry | `cluster_entry_stub()` gọi `cluster_entry` | `bench_cluster_forward()` đưa tới `main` |

[Register map](../../../../pulp-runtime/include/archi/cluster_ctrl/cluster_ctrl_v2.h).
Stack demo là 4 KiB/core, tổng 32 KiB trong L1 64 KiB. Khi malloc thất bại,
`cluster_start()` return sớm; cần sentinel `demo_cl_ran` để phân biệt với chạy
thành công. Runtime chỉ ghi retval core 0, nên demo gom lỗi qua biến chung/mutex.
`cluster_wait()` **poll biến `cluster_running` trong memory**; không chờ event
completion phần cứng như một số mô tả kiến trúc tổng quát.

[Phase 6](../../../../sw/full_system/full_system.c#L226) thực hiện:

```text
PE0: plp_dma_extToL1(L1_scratch, L2_src, nbytes)
→ MCHAN command/địa chỉ → AXI AR/R đọc L2 → HCI ghi L1
→ poll status counter về 0, free counter
PE0: plp_dma_l1ToExt(L2_dst, L1_scratch, nbytes)
→ HCI đọc L1 → AXI AW/W/B ghi L2
→ poll status, free counter → so sánh từng word L2_dst với L2_src
```

Cả hai transfer dùng **AXI Cluster→SoC**; không dùng giao diện AXI SoC→Cluster
cho lượt L2→L1 do MCHAN chủ động đọc. Phase 6 chưa có bước các PE biến đổi buffer
sau DMA; luồng tính toán đó được thiết kế riêng ở bài 05.

HWPE dùng register cấu hình và enable clock, acquire job, địa chỉ/length/stride,
trigger rồi kiểm tra completion và nội dung. Payload 12 B/beat được giải thích
bởi `4*32-32=96 bit`; xem bài cấu hình. `hwpe_subsystem.busy_o=1` bị buộc hằng,
vì vậy `cluster busy` không phải dấu hiệu đủ để kết luận PE đang chạy hay HWPE
đang tính. Cần quan sát event/status và dữ liệu thực.

## 5. Thời gian và hiệu năng [CẦN ĐO]

Để đo tranh chấp bank: dùng vùng L1 đã cấp phát riêng, cùng số truy cập, phép toán
và clock; warm-up instruction cache; barrier trước đo; không `printf` trong vùng
đo. So sánh hai mẫu trên, đồng thời thu req/gnt từng PE và bank. Một sample
cycle count dài hơn chưa chứng minh nguyên nhân là bank conflict nếu không
loại refill, DMA hoặc tranh chấp HWPE.

Thử 1/2/4/8 PE đòi hỏi đổi fetch mask, barrier mask, cách chia việc và aggregation;
không chỉ đổi mask fetch rồi giữ barrier `0xFF`. Với FPU, cần instruction float
thật và request/grant/response ở APU; chương trình số nguyên không kiểm chứng
4 FPNEW chia sẻ ra sao. Với HWPE, đo accepted beats và stall để suy throughput,
không gọi 12 B payload là 12 B/clock đạt được.

## 6. Bằng chứng và tiêu chí đúng/sai

**[SIM cũ: 2026-09-06, lượt 06/08]**
[PASS](../../../../report/full_system_20260906/06_PASS_toan_bo_9_phase.log),
[tiêm lỗi core 3](../../../../report/full_system_20260906/08_phep_thu_nguoc_core3_FAIL.log).
Các log chứng minh chương trình của lượt đó đã chạy cluster và truyền lỗi về FC;
không phải benchmark bank/FPU/CDC hiện tại.

| Phép kiểm chứng | Điều kiện PASS | Phép thử âm/giới hạn |
|---|---|---|
| multicore/barrier | đủ core ID, tất cả qua barrier, kết quả chung đúng | PE thiếu không được PASS; watchdog báo timeout |
| DMA round-trip | status xong và từng word đúng | `INJECT_FAULT_DMA=1` phải fail; cần chạy lại mới có SIM mới |
| HWPE | clock/job/status và output buffer đúng | tắt generic HWPE phải không cho bài test thành công giả |
| bank contention | đúng dữ liệu, khác biệt stall được giải thích bằng grant | chưa có phép đo mới |
| FPU/dispatch | test riêng cho chức năng và mức chia sẻ | chưa được demo kiểm chứng |
