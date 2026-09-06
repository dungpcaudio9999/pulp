# Chuyên sâu 03 — Cluster domain và interconnect SoC–Cluster

## 1. Cấu hình Cluster

[`rtl/pulp/cluster_domain.sv`](../../rtl/pulp/cluster_domain.sv) truyền các tham số sau vào `pulp_cluster`:

| Thành phần | Giá trị top hiện tại | Ý nghĩa |
|---|---:|---|
| Core | 8 | `NB_CORES` |
| TCDM | 64 KiB | scratchpad L1 chia bank |
| TCDM banks | 16 | mỗi bank 4 KiB, word 32 bit |
| DMA | 4 | số DMA ports/channels cấu hình ở wrapper |
| HWPE ports | 4 ở `pulp.sv` | mặc định wrapper là 9 nhưng bị override |
| I-cache | private mode, 8 banks | do `PRIVATE_ICACHE` |
| Cache size | 4096 | tham số truyền xuống; phạm vi per-bank/toàn cụm phải kiểm chứng dependency |
| Set associative | 4 | cấu hình cache |
| AXI C→S | 64 bit | Cluster master tới SoC |
| AXI S→C | 32 bit | SoC master tới Cluster |

TCDM bank interleaving cho phép nhiều core/DMA truy cập song song khi địa chỉ rơi vào bank khác nhau. Với word 32 bit và 16 bank, các bit địa chỉ word thấp thường tham gia chọn bank; phép ánh xạ chính xác nằm trong dependency.

## 2. Các khối con chức năng kỳ vọng

Từ tham số/cổng của wrapper, `pulp_cluster` bao gồm các lớp logic: nhiều core, instruction cache, TCDM interconnect + banks, peripheral/event unit, DMA/mchan, debug fanout và AXI CDC slices. Đây là mô hình chức năng từ contract; tên instance và cấu trúc RTL chính xác cần dependency checkout để xác nhận.

## 3. Hai hướng AXI

### Cluster → SoC

Cluster là AXI master, thường dùng khi core/DMA đọc ghi L2 hoặc SoC peripheral. Data width là 64 bit. Ở SoC, cùng bus được nhận tại `async_data_slave_*`.

### SoC → Cluster

SoC là AXI master, dùng khi FC/debug truy cập address space Cluster. Data width là 32 bit. Ở Cluster, bus được nhận tại `async_data_slave_*`.

Mỗi hướng có đủ năm channel AXI: AW, W, B, AR, R. Request channels mang pointer/data theo chiều master→slave; response channels đổi chiều. Với `LOG_DEPTH=3`, mỗi mảng data có 8 entry và pointer có 4 bit; bit mở rộng giúp phân biệt full/empty sau vòng quay.

Payload không phải struct AXI ở top mà là vector đã pack. `pulp.sv` tính width từ ID, address, user, len, size, burst, cache, protection, QoS, region, `atop`, last và response. Điều này làm top độc lập với implementation FIFO nhưng khiến hai đầu bắt buộc dùng cùng công thức width.

## 4. Event và handshake ngoài AXI

Event FIFO có 8 entry, mỗi event 8 bit. Nó phù hợp cho notification nhỏ, không thay thế data movement. Data lớn đi qua DMA/AXI; event báo “có việc” hoặc “đã xong”.

Các handshake riêng:

- `dma_pe_evt_valid/ack`: đang nối hai chiều;
- `dma_pe_irq_valid/ack`: output Cluster tồn tại nhưng valid bị bỏ ở phía SoC top;
- `pf_evt_valid/ack`: output Cluster tồn tại nhưng valid bị bỏ ở phía SoC top;
- `dbg_irq_valid[7:0]`: SoC/debug phát tới từng core;
- `busy`: Cluster trả trạng thái tổng hợp.

## 5. Boot/fetch: hành vi thực tế của wrapper

`pulp_cluster` được instantiate với:

```systemverilog
.base_addr_i  ('0),
.en_sa_boot_i (1'b0),
.test_mode_i  (1'b0),
.fetch_en_i   (1'b0),
.cluster_id_i (6'b0)
```

Trong khi đó `pulp_soc` xuất `cluster_fetch_enable_o` và `cluster_boot_addr_o`, nhưng `cluster_domain` không khai báo input tương ứng. Vì vậy mô tả “SoC kéo fetch-enable trực tiếp để khởi động Cluster” không đúng với wiring của revision này.

Khả năng Cluster được điều khiển qua register/event/AXI bên trong dependency là hợp lý, nhưng chỉ là giả thuyết cho tới khi đọc đúng revision `pulp_cluster`. Khi mô phỏng, bằng chứng đáng tin cậy là PC/fetch nội bộ, giao dịch instruction/L2, `busy` và event—not output điều khiển đang dangling ở top.

## 6. Luồng offload có thể kiểm chứng ở boundary

```text
FC ghi code/data vào L2
  -> SoC gửi event hoặc ghi register qua AXI S→C
  -> Cluster phát sinh activity/busy
  -> Cluster DMA/core truy cập L2 qua AXI C→S
  -> Cluster trả event/handshake
  -> FC đọc kết quả
```

Phần “event/register nào bật core” phải được bổ sung sau dependency checkout. Boundary hiện tại đủ để thiết kế waveform checklist nhưng chưa đủ để kết luận state machine boot nội bộ.

## 7. Checklist waveform

- `s_cluster_clk`, `s_cluster_rstn`, `s_cluster_busy`;
- event `wptr/rptr/data`;
- C→S AW/W/B và AR/R pointers;
- S→C AW/W/B và AR/R pointers;
- `dma_pe_evt_valid/ack`;
- PC/fetch của từng core sau khi xác nhận hierarchy dependency.

