# Hướng phân tích trực quan ELF trên GVSoC và RTL PULP

Ngày tạo: 2026-10-03 (Asia/Bangkok).

## 1. Mục tiêu

Xây dựng một câu chuyện kỹ thuật có thể trình bày trên slide, nối được ba lớp:

```text
Software / instruction
        ↓
Giao dịch kiến trúc: memory, MMIO, event
        ↓
Hoạt động phần cứng quan sát trên RTL waveform
```

Mục tiêu không phải đưa toàn bộ log hoặc toàn bộ waveform lên slide. Mỗi slide
chỉ giữ một checkpoint quan trọng và trả lời bốn câu hỏi:

1. Software đang thực hiện thao tác gì?
2. Instruction hoặc MMIO nào kích hoạt thao tác đó?
3. Khối PULP nào tham gia?
4. Tín hiệu RTL nào chứng minh hoạt động đã xảy ra?

## 2. Cách diễn đạt đúng về luồng thực thi

Không nên nói rằng mọi instruction đều "chạy qua" UDMA, interconnect và UART.
Instruction được thực thi trong core, ví dụ Fabric Controller (FC). Một số
instruction load/store sau đó tạo giao dịch memory hoặc MMIO để cấu hình phần
cứng. Sau khi được cấu hình, UDMA hoặc peripheral có thể hoạt động tự trị trong
khi core polling, sleep hoặc làm việc khác.

Luồng đúng nên được mô tả như sau:

```text
CPU instruction
      ↓
MMIO write / memory transaction
      ↓
Peripheral được cấu hình
      ↓
Phần cứng hoạt động tự trị
      ↓
Status/event/interrupt
      ↓
CPU tiếp tục
```

## 3. Vai trò của GVSoC

GVSoC là virtual platform mô hình hóa kiến trúc PULP ở mức chức năng và timing
sự kiện. Nó chạy trực tiếp ELF RISC-V mà không cần mô phỏng toàn bộ netlist RTL.

Trong flow này, GVSoC có các vai trò chính:

### 3.1. Chạy software nhanh

GVSoC dùng để kiểm tra sớm rằng ELF:

- boot được;
- đi vào `main`;
- gọi đúng runtime/driver;
- truy cập đúng địa chỉ peripheral;
- hoàn thành và gọi `exit(0)`.

Điều này thuận tiện cho phát triển software khi chưa cần hoặc chưa muốn chạy
Questa/RTL vốn chậm hơn nhiều.

### 3.2. Sinh reference trace ở mức kiến trúc

Instruction trace GVSoC cho biết:

- PC, opcode và function;
- register đọc/ghi;
- địa chỉ vật lý của load/store;
- thứ tự các checkpoint phần mềm;
- modeled cycle/time của virtual platform.

Trace này có thể dùng làm reference về **thứ tự và ý nghĩa sự kiện**, nhưng
không phải golden reference cho từng cycle RTL.

### 3.3. Phát hiện lỗi software hoặc cấu hình sớm

Ví dụ, với `zcu104_uart_direct`, GVSoC xác nhận:

```text
UART setup  0x1a1020a4 ← 0x00560306
TX address  0x1a102090 ← 0x1c000820
TX size     0x1a102094 ← 0x00000017
exit status 0x1a1040a0 ← 0x80000000
```

Nếu các giao dịch này sai ngay trên GVSoC thì thường nên sửa ELF, runtime hoặc
cấu hình trước khi debug tín hiệu RTL.

### 3.4. Làm mốc đối chiếu với RTL

GVSoC và RTL chạy cùng ELF một cách độc lập:

```text
                    ┌─> GVSoC ─> instruction/architecture trace
C source ─> ELF ────┤
                    └─> RTL    ─> instruction trace + waveform
```

Hai kết quả nên được căn chỉnh bằng event có ý nghĩa, không căn chỉnh bằng số
cycle tuyệt đối:

| Event | GVSoC | RTL |
|---|---|---|
| E0 | `_start` | `_start` |
| E1 | UART setup write | UART setup write |
| E2 | TX address write | TX address write |
| E3 | TX size/enable | TX size/enable |
| E4 | UART hoàn thành | UART hoàn thành |
| E5 | `exit(0)` | `exit(0)` |

### 3.5. Những gì GVSoC không thay thế

GVSoC không thay thế RTL khi cần chứng minh:

- tín hiệu request/grant cụ thể;
- protocol handshake từng cycle;
- arbitration và backpressure thực tế;
- reset/clock crossing;
- FIFO, serializer và pin UART;
- bug do implementation RTL;
- timing chính xác theo clock của RTL platform.

Trong hai demo hiện tại, UART hiệu dụng trên GVSoC khoảng `825000 baud`, còn
RTL khoảng `202250 baud`. Vì vậy modeled time khác nhau dù ELF và thứ tự sự kiện
giống nhau. Đây là lý do không được xem GVSoC và RTL là lockstep cycle.

## 4. Vai trò của RTL và waveform

RTL là bằng chứng ở mức implementation. Instruction trace RTL cho biết core đã
retire instruction nào, còn waveform cho biết phần cứng phản ứng ra sao.

Waveform nên được dùng để xác nhận:

- MMIO request xuất hiện đúng thời điểm;
- address và write data đúng;
- UDMA nhận cấu hình và chuyển sang busy;
- UDMA phát request đọc L2;
- interconnect grant/response đúng;
- UART nhận dữ liệu và serialize ra TX;
- status/done quay trở lại software;
- testbench nhận đúng chuỗi và exit status.

## 5. Vai trò của HTML viewer

HTML viewer là lớp điều hướng giữa raw trace và waveform. Nó không chạy lại ELF
và không thay thế GTKWave.

HTML dùng để:

- replay instruction trace đã ghi;
- tìm PC, opcode, function và source;
- tìm địa chỉ MMIO hoặc physical address;
- xem register access;
- so sánh checkpoint GVSoC/RTL;
- xác định vùng thời gian cần mở trong waveform;
- lưu một report độc lập có thể mở lại khi thuyết trình.

Mối quan hệ giữa các artifact:

| Artifact | Trả lời câu hỏi |
|---|---|
| C/ELF | Chương trình muốn làm gì? |
| GVSoC trace | Software/kiến trúc dự kiến làm gì và theo thứ tự nào? |
| RTL trace | Core RTL thực sự retire instruction nào? |
| VCD/GTKWave | Tín hiệu phần cứng thực sự thay đổi thế nào? |
| HTML | Tìm và liên kết các bằng chứng trên như thế nào? |

## 6. Template cho một slide phân tích

Mỗi slide checkpoint nên có bố cục:

```text
┌────────────────────────────┬──────────────────────────┐
│ Kiến trúc PULP             │ Trace CPU                │
│                            │ PC / function / opcode   │
│ FC → ICN → UDMA → UART     │ MMIO address + value     │
│ Khối hoạt động được tô màu │                          │
├────────────────────────────┴──────────────────────────┤
│ Waveform RTL tại cùng checkpoint                      │
│ PC | bus request | address | UDMA busy | UART TX      │
└───────────────────────────────────────────────────────┘
```

Quy tắc trình bày:

- chỉ giữ 3–6 instruction liên quan;
- waveform chỉ cắt quanh checkpoint;
- dùng một vạch thời gian dọc chung;
- tô màu nhất quán giữa kiến trúc và waveform;
- ghi rõ đâu là evidence từ GVSoC và đâu là evidence từ RTL;
- không dùng modeled time GVSoC như cycle-accurate prediction cho RTL.

Màu đề xuất:

- xanh dương: FC;
- xanh lá: L2;
- vàng: interconnect;
- tím: UDMA;
- đỏ: UART/TX.

## 7. Storyboard cho `zcu104_uart_direct`

### Slide 1 — Mục tiêu và workload

```c
uart_write(0, message, 23);
```

Thông điệp: một buffer 23 byte từ L2 được gửi qua UDMA UART.

### Slide 2 — Runtime và mở UART

Trace:

```text
_start → pos_init_start → uart_open
```

Kiến trúc:

```text
FC ──MMIO──> SoC interconnect ──> UDMA UART
```

Checkpoint chính:

```text
0x1a1020a4 ← 0x00560306
```

### Slide 3 — `main` chuẩn bị transfer

Các tham số:

```text
channel = 0
buffer  = 0x1c000820
size    = 23
```

Tô sáng FC và vùng buffer trong L2.

### Slide 4 — FC cấu hình UDMA TX

Checkpoint:

```text
0x1a102090 ← 0x1c000820
0x1a102094 ← 0x00000017
TX enable
```

Trace cung cấp PC/instruction/MMIO. Waveform cung cấp bus request, address,
write data và enable.

### Slide 5 — UDMA tự đọc L2

```text
L2 ──23 byte──> interconnect ──> UDMA UART TX
```

CPU có thể đang polling. Waveform cần cho thấy UDMA request/grant, L2 address,
read response và UART channel busy.

### Slide 6 — UART serialize

```text
UDMA UART FIFO → serializer → TX pad
```

Phóng to một byte để chỉ start bit, 8 data bit và stop bit; không cần đưa toàn
bộ 23 byte lên slide.

### Slide 7 — Hoàn thành và exit

```text
UART done → FC thoát polling → uart_close → exit(0)
```

Bằng chứng:

```text
RTL RX string: Hello PULP from ZCU104
RTL status:    0x00000000
exit write:    0x1a1040a0 ← 0x80000000
```

### Slide 8 — GVSoC so với RTL

So sánh theo semantic event:

- cùng function path hay không;
- cùng MMIO address/value hay không;
- cùng output và exit status hay không;
- modeled time/cycle khác nhau ở đâu;
- khác biệt nào do clock/model, khác biệt nào có thể là bug.

## 8. Chọn workload để trình bày

`zcu104_uart_direct` phù hợp làm luồng chính vì chỉ có một transfer UDMA 23 byte,
dễ nối trace với waveform.

`zcu104_uart_smoke` phù hợp làm case so sánh software abstraction:

```text
printf → formatting → nhiều uart_write → nhiều instruction/giao dịch hơn
```

Hai ELF này chỉ bao phủ:

```text
FC + L2 + SoC interconnect + UDMA UART
```

Chúng không bao phủ cluster, 8 PE, TCDM, barrier, MCHAN DMA hoặc HWPE. Nếu mục
tiêu là giới thiệu kiến trúc PULP rộng hơn, cần thêm workload có cluster/DMA và
phase marker riêng.

## 9. Danh sách tín hiệu RTL cần bổ sung

Tên hierarchy cụ thể cần được xác nhận trong RTL, nhưng nhóm tín hiệu nên gồm:

### FC

- instruction valid/retire;
- PC;
- data request/grant;
- address, write-enable và write data.

### Peripheral/interconnect

- request/grant;
- address;
- write/read data;
- response valid/error.

### UDMA UART TX

- channel enable;
- start address;
- transfer size;
- busy/done;
- L2 request/grant;
- data valid/ready.

### UART/pad

- UART clock/reset;
- TX busy;
- serializer state nếu cần;
- TX pad;
- testbench UART receiver output.

### Kết thúc chương trình

- exit/status register;
- testbench status;
- simulation done.

## 10. Kết luận phương pháp

Vai trò hợp lý của hai simulator là bổ sung cho nhau:

```text
GVSoC: nhanh, software-centric, architectural reference
RTL:   chậm hơn, implementation-centric, signal-level proof
```

Phương pháp trình bày tốt nhất là dùng GVSoC để thiết lập expected semantic
flow, dùng RTL trace để xác nhận core thực thi, và dùng waveform để chứng minh
các khối phần cứng thực sự hoạt động. HTML đóng vai trò index/replay giúp đi từ
instruction đến đúng checkpoint waveform; slide kể lại các checkpoint đó bằng
hình kiến trúc được tô sáng và bằng chứng tối thiểu cần thiết.
