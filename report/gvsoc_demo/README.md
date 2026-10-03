# Kết quả PULP execution-flow demo

Ngày chạy: 2026-10-03 (Asia/Bangkok).

Tài liệu liên quan:

- `HUONG_DAN_TUNG_BUOC.md`: hướng dẫn tái lập toàn bộ quy trình từ C/ELF tới
  GVSoC, RTL, trace, waveform và viewer.
- `BAO_CAO_CONG_VIEC.md`: báo cáo phạm vi, công việc đã làm, kết quả và bàn giao.

## Kết luận

Một ELF duy nhất build từ `sw/flow_demo/flow_demo.c` đã chạy thành công trên cả:

- GVSoC target `pulp-open`;
- RTL PULP bằng Questa 10.7c.

SHA-256 của ELF:

```text
7fff5157f6c4739a53511d85478b6c8951c068487aa24f32fb7e1272ff89c39a
```

Cả hai backend đều cho:

- cùng checksum L2 `0x9c7e7a4a`;
- cùng kết quả ALU `0x41eb8881`;
- đủ PE0 đến PE7;
- barrier/cross-read không lỗi;
- DMA L2 -> L1 -> L2 khôi phục đúng 256 byte;
- `FLOW|6|RESULT|PASS|errors=0`;
- RTL testbench nhận exit status `0x00000000`.

## Xem kết quả

- `flow_viewer.html`: viewer độc lập, có timeline, so sánh cycle và replay
  instruction GVSoC/RTL.
- `gvsoc.log`: stdout GVSoC.
- `gvsoc/fc.log`, `gvsoc/pe0.log`: instruction trace GVSoC thô.
- `rtl/transcript.log`: transcript RTL/Questa.
- `rtl/raw/trace_core_1f_0.log`: instruction trace FC từ RTL.
- `rtl/raw/trace_core_00_0.log` ... `trace_core_00_7.log`: trace tám PE RTL.
- `rtl/wave/flow_demo.vcd.gz`: waveform RTL chọn lọc.
- `rtl/wave/flow_demo.gtkw`: danh sách tín hiệu mặc định cho GTKWave.

Mở viewer:

```bash
firefox report/gvsoc_demo/flow_viewer.html
```

Mở waveform:

```bash
cd report/gvsoc_demo/rtl/wave
gtkwave flow_demo.gtkw
```

## Cycle theo biên hàm phase

Các số dưới đây lấy từ first/last instruction của hàm phase. Chúng bao gồm
marker/`printf`, vì vậy dùng để hình dung luồng, không thay cho microbenchmark.

| Phase | Core | GVSoC | RTL | GVSoC/RTL |
|---:|---|---:|---:|---:|
| 0 — FC + L2 | FC | 12.224 | 5.761 | 2,122 |
| 1 — FC timer + ALU | FC | 15.598 | 7.143 | 2,183 |
| 2 — launch/wait cluster | FC | 191.663 | 175.519 | 1,092 |
| 3 — 8 PE ghi L1 | PE0 | 44.674 | 43.317 | 1,031 |
| 4 — barrier + đọc chéo | PE0 | 11.397 | 10.991 | 1,037 |
| 5 — DMA L2-L1-L2 | PE0 | 20.025 | 19.493 | 1,027 |
| 6 — summary | FC | 11.989 | 5.559 | 2,157 |

Kết quả thể hiện đúng đặc tính đã thấy ở các benchmark trước: phần cluster của
GVSoC gần RTL trong demo này, còn phase nhiều `printf` trên FC lệch khoảng 2,1x.

## Trace và waveform

Viewer đã parse 207.451 instruction thô:

| Backend/core | Instruction thô |
|---|---:|
| GVSoC FC | 86.850 |
| GVSoC PE0 | 12.950 |
| RTL FC | 81.814 |
| RTL PE0 | 12.950 |
| RTL PE1 ... PE7 | 1.841 mỗi core |

Sau khi bỏ boot/runtime không liên quan và vòng polling `cluster_wait` lặp lại,
viewer giữ 7.344 instruction tập trung vào `flow_demo`, cluster hand-off,
barrier và DMA. Raw trace không bị xóa.

Waveform nén có kích thước khoảng 3 MiB và chứa 24 đối tượng được chọn. Đã xác
nhận có chuyển trạng thái thực trên:

- `core_busy`, `core_clock_en_o` và `fetch_en_int`;
- `s_dmac_busy`, `s_dma_cl_event`;
- MCHAN TCDM request;
- AXI read/write valid-ready của DMA.

## Cách diễn giải

Instruction trace cho thấy FC hoặc PE đang thực thi opcode nào, PC, register và
địa chỉ vật lý. Nó không thể tự mô tả toàn bộ hoạt động của DMA: CPU chỉ ghi cấu
hình và chờ, còn DMA chạy tự trị. Vì vậy phase 5 phải đọc cùng lúc:

1. instruction trace PE0 để thấy các lệnh cấu hình/poll;
2. waveform `s_dmac_busy`, TCDM request và AXI handshake để thấy transfer RTL.

Tương tự, phase 3-4 ghép instruction của tám PE với `core_busy`, clock enable và
event-unit signals để thấy barrier/sleep/wakeup.

## Giới hạn

- Đây là demo giải thích luồng, không phải phép đo sign-off timing.
- Viewer dùng source/DWARF để ánh xạ PC RTL; code tối ưu có thể gộp nhiều
  instruction vào cùng một dòng C.
- GVSoC target có model PE8 nhưng phần mềm và RTL demo chỉ dùng tám PE0...PE7.
- HWPE, flash, GPIO và floating point chưa nằm trong workload này.
- Bốn `vsim-191` của Questa 10.7c là lỗi khởi động đã biết trong môi trường này;
  runner vẫn kết thúc PASS và testbench trả status 0.
