# Kiểm tra lại hai flow ZCU104 UART

Ngày kiểm tra: 2026-10-03 (Asia/Bangkok).

## Kết luận

Cả hai ELF `zcu104_uart_smoke` và `zcu104_uart_direct` đều PASS trên hai backend:

| ELF | GVSoC UART | GVSoC FC | RTL UART | RTL FC | RTL status |
|---|---|---:|---|---:|---|
| `zcu104_uart_smoke` | `Hello PULP from ZCU104\n` | 5.397 | đúng 23 byte | 35.405 | `0x00000000` |
| `zcu104_uart_direct` | `Hello PULP from ZCU104\n` | 4.634 | đúng 23 byte | 22.957 | `0x00000000` |

Hai chương trình chỉ chạy trên Fabric Controller (FC). Trace PE0 của GVSoC rỗng
và trace PE0...PE7 của RTL chỉ có header; điều này phù hợp vì ELF không bật
cluster.

## Vấn đề UART và cách xử lý

Các log GVSoC trước đó bị nhiễu vì UART checker dùng baud mặc định `115200`.
Lượt chạy cuối dùng đúng đường dẫn cấu hình:

```text
--config-opt=uart_checker/uart_checker/baudrate=825000
```

Cả hai `gvsoc_config.json` xác nhận giá trị `825000`, và hai `gvsoc.log` hiện
đều chứa đúng 23 byte. RTL dùng monitor `202250 baud`, lấy từ bit period đo trên
waveform là khoảng `4.944384 us`.

Hai baud decoder khác nhau không có nghĩa hai ELF hay luồng CPU khác nhau. Cùng
UART setup value `0x00560306` được thực thi, nhưng clock peripheral hiệu dụng
của model GVSoC `pulp-open` khác clock trong RTL testbench.

## Bằng chứng kết thúc thành công

Ở cuối cả hai GVSoC FC trace:

- `a0` ban đầu là `0`, tức giá trị trả về của `main`;
- lệnh `p.bseti` tạo protocol value `0x80000000`;
- lệnh cuối ghi `0x80000000` vào `PA:0x1a1040a0` tại hàm `exit`.

Ở RTL, cả hai transcript đều có:

```text
RX string: Hello PULP from ZCU104
Received status core: 0x00000000
exit_status=0
```

`uart_smoke` kết thúc tại `7.888.701 ns`; `uart_direct` kết thúc tại
`4.979.801 ns`. Các warning `vsim-191` là warning khởi động của Questa 10.7c;
chúng không thay đổi status, chuỗi UART hoặc exit code.

## Tính toàn vẹn artifact

- Snapshot `zcu104_uart_smoke` giống binary nguồn, SHA-256:
  `40d9d50a0a0ec783d7d8df38708aee23ea75e0ed0ed50a3778fdfab5dba1e6da`.
- Snapshot `zcu104_uart_direct` giống binary nguồn, SHA-256:
  `13f7b41018b8d83688d789c614cba6d25d3e4b958f27882840cf655560a02ed3`.
- Hai file VCD gzip đều qua `gzip -t`.
- HTML `uart_smoke` chứa 40.802 instruction đã parse.
- HTML `uart_direct` chứa 27.591 instruction đã parse.
- Source mapping DWARF trong HTML tìm được `hello.c` và `direct_uart.c`.

## Artifact nên mở

### `zcu104_uart_smoke`

- Hướng dẫn/kết quả: `report/zcu104_uart_smoke/README.md`
- UART GVSoC: `report/zcu104_uart_smoke/gvsoc.log`
- UART RTL: `report/zcu104_uart_smoke/rtl/uart_decoded.txt`
- Transcript RTL: `report/zcu104_uart_smoke/rtl/transcript.log`
- Instruction viewer: `report/zcu104_uart_smoke/flow_viewer.html`
- Waveform: `report/zcu104_uart_smoke/rtl/wave/zcu104_uart_smoke.vcd.gz`

### `zcu104_uart_direct`

- Hướng dẫn/kết quả: `report/zcu104_uart_direct/README.md`
- UART GVSoC: `report/zcu104_uart_direct/gvsoc.log`
- UART RTL: `report/zcu104_uart_direct/rtl/uart_decoded.txt`
- Transcript RTL: `report/zcu104_uart_direct/rtl/transcript.log`
- Instruction viewer: `report/zcu104_uart_direct/flow_viewer.html`
- Waveform: `report/zcu104_uart_direct/rtl/wave/zcu104_uart_direct.vcd.gz`

HTML dùng để replay/search từng instruction và đối chiếu GVSoC với RTL. VCD mở
bằng GTKWave để quan sát tín hiệu theo thời gian; HTML không thay thế waveform.

Trong HTML, `Log — RTL (kết quả)` chỉ hiện các dòng nghiệm thu để warning khởi
tạo Questa không che mất kết quả. Transcript không bị xóa: mở mục **Xem
transcript RTL đầy đủ** hoặc liên kết `RTL raw transcript` ngay bên dưới.

Vì hai ELF không có symbol `phaseN_*`, timeline được tự động dựng từ bốn mốc
PULP runtime: `_start`, `main`, `pos_init_stop` và `exit`. Viewer hiển thị bốn
giai đoạn tương ứng cho cả GVSoC và RTL, đồng thời tính cycle từng giai đoạn.
Chiều rộng block là tỷ lệ simulation time chính xác, không áp dụng minimum
width; phase quá nhỏ được đọc qua legend duration/phần trăm/cycle bên dưới.
Hai backend được đặt trên hai lane cùng một thang thời gian tuyệt đối. Playhead
trắng bám instruction của backend/core đang chọn; playhead xanh ánh xạ cùng
phase sang backend kia để so sánh trực quan, không đại diện cho lockstep cycle.
Auto-scroll khi Play chỉ tác động khung instruction, không cuộn toàn bộ trang.
