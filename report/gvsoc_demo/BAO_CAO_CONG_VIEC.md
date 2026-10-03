# Báo cáo công việc: PULP GVSoC/RTL execution-flow demo

## 1. Thông tin chung

- Ngày thực hiện và nghiệm thu: 2026-10-03, múi giờ Asia/Bangkok.
- Repository: `/home/dungpc/ndmoney4porche/projects/pulp`.
- Mục tiêu: tạo workload C vừa đủ để quan sát luồng FC -> cluster -> DMA -> FC,
  build thành một ELF và so sánh việc thực thi trên GVSoC với RTL/Questa.
- Trạng thái: **hoàn thành, hai backend đều PASS**.

## 2. Phạm vi đã thống nhất

Workload cần thể hiện được nhiều khối của PULP nhưng vẫn đủ nhỏ để RTL chạy và
trace trong thời gian hợp lý. Phạm vi được chọn gồm:

- Fabric Controller và L2;
- APB timer và một kernel ALU;
- cluster launch/wait;
- tám processing element;
- L1/TCDM và truy cập xen kẽ;
- event-unit barrier/mutex;
- MCHAN DMA L2 -> L1 -> L2;
- instruction trace, waveform và viewer so sánh.

Không đưa HWPE, flash, GPIO hoặc floating point vào lượt này vì chưa cần thiết
cho câu chuyện luồng chính và có thể làm mất tính tương đương giữa hai backend.

## 3. Công việc đã thực hiện

### 3.1. Khảo sát flow và lựa chọn kiến trúc demo

- Xác định target GVSoC phù hợp là `pulp-open`.
- Xác định flow RTL sử dụng `pulp-runtime` và testbench Questa `tb_pulp`.
- Xác định format instruction trace khác nhau giữa GVSoC và RTL.
- Chọn chiến lược phase marker và symbol `noinline` để đồng bộ log, trace và
  waveform.
- Chọn một ELF dùng chung làm điều kiện bắt buộc của phép so sánh.

### 3.2. Xây dựng workload C

Đã tạo:

```text
sw/flow_demo/flow_demo.c
sw/flow_demo/Makefile
```

Workload gồm bảy phase:

1. FC khởi tạo và checksum 64 word ở L2.
2. FC đọc timer và thực hiện 128 vòng ALU.
3. FC bật cluster và chờ hoàn tất.
4. Tám PE ghi 16 word/core theo dạng xen kẽ vào TCDM.
5. Tám PE barrier và đọc chéo dữ liệu.
6. PE0 chạy hai chiều MCHAN DMA với 256 byte.
7. FC nhận kết quả, in PASS/FAIL và thoát.

Các cơ chế phòng lỗi đã thêm:

- `CLUSTER_STACK_SIZE=0x1000`, tránh cả tràn stack và chiếm hết L1;
- sentinel `flow_cluster_ran` để phát hiện cluster không thực sự khởi động;
- gom lỗi đa core dưới mutex;
- polling DMA có giới hạn;
- so cả checksum và từng word sau DMA;
- dữ liệu xác định, không phụ thuộc random;
- `-O2 -g` và `noinline` để giữ trace thực tế nhưng vẫn ánh xạ source.

### 3.3. Build và khóa danh tính ELF

ELF đầu ra:

```text
sw/flow_demo/build/flow_demo/flow_demo
```

Thuộc tính đã kiểm tra:

- ELF32 little-endian;
- machine RISC-V;
- RVC, soft-float ABI;
- entry point `0x1c008080`;
- statically linked;
- có debug information.

SHA-256:

```text
7fff5157f6c4739a53511d85478b6c8951c068487aa24f32fb7e1272ff89c39a
```

Hash được lưu ở `report/gvsoc_demo/elf.sha256` và chính ELF này được đưa cho cả
GVSoC lẫn RTL.

### 3.4. Chạy GVSoC

Đã chạy target `pulp-open`, thu:

- stdout/phase log ở `report/gvsoc_demo/gvsoc.log`;
- FC instruction trace ở `report/gvsoc_demo/gvsoc/fc.log`;
- PE0 instruction trace ở `report/gvsoc_demo/gvsoc/pe0.log`;
- config và artifact working directory ở `report/gvsoc_demo/gvsoc/`.

Kết quả:

- 86.850 instruction FC;
- 12.950 instruction PE0;
- đủ marker PE0...PE7;
- mọi phase PASS;
- `FLOW|6|RESULT|PASS|errors=0`.

### 3.5. Chạy RTL/Questa

Đã chạy cùng ELF bằng `sw/full_system/run_sim.sh`, với watchdog mô phỏng và
wall-clock. Thời gian thực của lượt đo khoảng 86 giây.

Artifact đã lưu:

- transcript: `report/gvsoc_demo/rtl/transcript.log`;
- FC trace: `rtl/raw/trace_core_1f_0.log`;
- tám PE trace: `rtl/raw/trace_core_00_0.log` đến `_7.log`.

Kết quả:

- FC: 81.814 instruction;
- PE0: 12.950 instruction;
- PE1...PE7: 1.841 instruction/core;
- đủ marker của tám PE;
- testbench nhận `0x00000000`;
- runner kết thúc exit code 0;
- `FLOW|6|RESULT|PASS|errors=0`.

### 3.6. Thu waveform RTL

Đã tạo `sw/flow_demo/flow_wave_capture.do` và chạy một lượt RTL riêng để thu
waveform chọn lọc.

Kết quả:

- 24 nhóm/đối tượng tín hiệu;
- VCD nén khoảng 3 MiB;
- file: `report/gvsoc_demo/rtl/wave/flow_demo.vcd.gz`;
- cấu hình GTKWave: `report/gvsoc_demo/rtl/wave/flow_demo.gtkw`;
- `gzip -t` PASS;
- exit status của lượt waveform bằng 0.

Đã xác nhận có transition thực trên:

- `core_busy`, `fetch_en_int`, `core_clock_en_o`;
- `s_dmac_busy`, `s_dma_cl_event`;
- MCHAN TCDM request/grant;
- AXI read/write valid-ready.

### 3.7. Chuẩn hóa trace và tạo viewer

Đã tạo `sw/flow_demo/flow_visualize.py` với các chức năng:

- parse format instruction trace của GVSoC;
- parse format trace của RTL;
- dùng DWARF và `riscv32-unknown-elf-addr2line` ánh xạ PC RTL về hàm/source;
- phân loại instruction và vùng nhớ L1/L2/peripheral;
- tính span cycle của từng phase;
- nhúng toàn bộ dữ liệu cần thiết vào HTML độc lập;
- cung cấp timeline, bộ lọc backend/core, search, step/play và register access.

Đầu ra:

```text
report/gvsoc_demo/flow_viewer.html
```

Viewer đã parse 207.451 instruction thô và giữ 7.344 instruction tập trung vào
workload. Phần lớn polling `cluster_wait` được lọc khỏi UI nhưng raw trace vẫn
được bảo toàn.

### 3.8. Viết tài liệu

Các tài liệu đã tạo:

- `PLAN.md`: kế hoạch ban đầu;
- `RESULTS.md`: kết quả ngắn gọn;
- `HUONG_DAN_TUNG_BUOC.md`: runbook tái lập đầy đủ;
- `BAO_CAO_CONG_VIEC.md`: báo cáo công việc này;
- `report/gvsoc_demo/README.md`: báo cáo kỹ thuật cạnh artifact;
- `sw/flow_demo/README.md`: lệnh vận hành ngắn cạnh source.

## 4. Kết quả chức năng

Hai backend cho cùng kết quả dữ liệu:

| Kiểm tra | GVSoC | RTL |
|---|---|---|
| L2 checksum | `0x9c7e7a4a` | `0x9c7e7a4a` |
| ALU result | `0x41eb8881` | `0x41eb8881` |
| PE0...PE7 xuất hiện | PASS | PASS |
| Barrier/cross-read | `errors=0` | `errors=0` |
| DMA source checksum | `0x9c7e7a4a` | `0x9c7e7a4a` |
| DMA destination checksum | `0x9c7e7a4a` | `0x9c7e7a4a` |
| DMA byte count | 256 | 256 |
| Kết quả cuối | PASS | PASS |

Luồng quan sát được:

```text
FC boot/L2/timer
       |
       v
FC cluster launch ---- FC chờ
       |
       v
PE0...PE7 ghi L1/TCDM
       |
       v
event-unit barrier + cross-read
       |
       v
PE0 cấu hình MCHAN --> DMA trao đổi L1/L2 qua TCDM/AXI
       |
       v
cluster hoàn tất --> FC summary --> exit status 0
```

## 5. Kết quả cycle

Cycle được tính theo instruction đầu/cuối của hàm phase:

| Phase | Core | GVSoC | RTL | GVSoC/RTL |
|---:|---|---:|---:|---:|
| 0 — FC + L2 | FC | 12.224 | 5.761 | 2,122 |
| 1 — FC timer + ALU | FC | 15.598 | 7.143 | 2,183 |
| 2 — launch/wait cluster | FC | 191.663 | 175.519 | 1,092 |
| 3 — 8 PE ghi L1 | PE0 | 44.674 | 43.317 | 1,031 |
| 4 — barrier + đọc chéo | PE0 | 11.397 | 10.991 | 1,037 |
| 5 — DMA L2-L1-L2 | PE0 | 20.025 | 19.493 | 1,027 |
| 6 — summary | FC | 11.989 | 5.559 | 2,157 |

Nhận xét:

- Ba phase cluster chính lệch 2,7–3,7% trong demo này.
- Phase launch/wait lệch khoảng 9,2%.
- Các phase FC có nhiều `printf` lệch khoảng 2,1 lần.
- Số liệu bao gồm marker và I/O, nên dùng để minh họa luồng chứ không dùng làm
  kết luận sign-off timing hay accuracy tổng quát của GVSoC.

## 6. Kiểm chứng đã thực hiện

Checklist cuối đã PASS:

- Python syntax của parser;
- hash ELF khớp file `elf.sha256`;
- marker PASS có ở GVSoC và RTL;
- RTL testbench status bằng 0;
- trace FC và đủ tám PE đều tồn tại, không rỗng;
- VCD nén hợp lệ;
- VCD có transition ở core/event/DMA/TCDM/AXI;
- payload JSON trong HTML đọc được;
- tổng raw count là 207.451;
- focused count là 7.344;
- phase 0...6 có mặt ở cả hai backend;
- các link artifact tương đối của viewer tồn tại;
- `git diff --check` không báo lỗi.

## 7. Các quyết định kỹ thuật đáng chú ý

### Một ELF duy nhất

Đây là điều kiện quan trọng nhất để phép so sánh có nghĩa. Build khác nhau có
thể thay đổi layout, instruction count và timing dù source giống nhau.

### Tách source-level log khỏi RTL-level waveform

`FLOW` marker giải thích ý nghĩa chương trình; instruction trace giải thích CPU;
waveform giải thích các khối tự trị. Không loại dữ liệu nào thay thế hoàn toàn
hai loại còn lại.

### Không dump toàn bộ RTL

Waveform chọn lọc giúp file chỉ khoảng 3 MiB, mở nhanh và tập trung vào đường
điều khiển/transaction liên quan tới demo.

### Giữ raw trace, lọc riêng ở viewer

Viewer bỏ polling lặp để dễ đọc, nhưng không xóa raw trace. Khi cần điều tra stall
hoặc sai parser vẫn có dữ liệu gốc để đối chiếu.

### Dùng DWARF cho RTL trace

Trace RTL không tự cung cấp tên hàm/dòng C. Ánh xạ bằng ELF cho phép đặt opcode
RTL cạnh source, nhưng vẫn giữ PC/opcode làm bằng chứng gốc.

## 8. Vấn đề gặp phải và cách xử lý

| Vấn đề | Cách xử lý |
|---|---|
| Format GVSoC và RTL khác nhau | Hai parser frontend đưa về cùng schema |
| Polling `cluster_wait` làm viewer quá lớn | Lọc khỏi UI, giữ span cycle và raw log |
| DMA không hiện toàn bộ trong CPU trace | Thu thêm TCDM/AXI waveform |
| Lỗi ở core 1...7 có thể bị runtime bỏ qua | Gom lỗi dưới event-unit mutex về core 0 |
| Cluster có thể không chạy do thiếu L1 stack | Dùng stack 4 KiB/core và sentinel L2 |
| DMA có thể treo vô hạn | Poll có giới hạn và báo status khi timeout |
| Questa có bốn `vsim-191` đã biết | Nghiệm thu bằng status/marker/exit code |
| PC RTL khó đọc | Ánh xạ source bằng DWARF/addr2line |

## 9. Giới hạn hiện tại

- GVSoC không phải RTL và kết quả cycle không dùng làm sign-off.
- Viewer chỉ thu PE0 bên GVSoC; hoạt động của PE1...PE7 được chứng minh qua marker.
- `-O2` có thể ánh xạ nhiều instruction về cùng một dòng source.
- Waveform là tập tín hiệu chọn lọc, không chứa mọi internal net.
- Chưa bao phủ HWPE, flash, GPIO hoặc floating point.
- Chưa có phép fault injection riêng cho demo này.
- Kết quả phụ thuộc phiên bản model, runtime, compiler và cấu hình target đã nêu.

## 10. Bàn giao

Điểm vào dành cho người sử dụng:

1. Đọc `HUONG_DAN_TUNG_BUOC.md` để tái lập.
2. Mở `report/gvsoc_demo/flow_viewer.html` để xem luồng instruction.
3. Mở `report/gvsoc_demo/rtl/wave/flow_demo.gtkw` để xem RTL waveform.
4. Khi nghi ngờ parser/UI, đối chiếu raw trace trong `gvsoc/` và `rtl/raw/`.

Các artifact hiện tại là một baseline có hash rõ ràng. Bất kỳ thay đổi source,
compiler flag hoặc runtime nào cũng cần build hash mới và chạy lại cả hai backend
trước khi so sánh.

## 11. Hướng phát triển đề xuất

1. Thêm fault injection để chứng minh đường FAIL của multi-core và DMA.
2. Thu instruction trace GVSoC cho đủ tám PE khi cần phân tích arbitration.
3. Thêm marker RTL trực tiếp từ địa chỉ `flow_phase_marker` vào waveform.
4. Thêm thống kê stall/load-store theo phase.
5. Tách vùng đo không chứa `printf` nếu muốn đánh giá timing nghiêm túc hơn.
6. Chỉ mở rộng HWPE/GPIO/flash sau khi xác nhận model tương ứng ở cả hai backend.

