# Kết quả chạy `zcu104_uart_direct` trên GVSoC và RTL

Ngày chạy: 2026-10-03 (Asia/Bangkok).

## Kết luận

ELF do người dùng cung cấp đã chạy đến `exit(0)` trên cả GVSoC `pulp-open` và
RTL/Questa. RTL testbench nhận status `0x00000000` và tự giải mã đúng UART:

```text
RX string: Hello PULP from ZCU104
```

Khác với `zcu104_uart_smoke`, binary này không dùng `printf`. `main()` tail-call
thẳng:

```c
uart_write(0, message, 23);
```

Do đó toàn bộ chuỗi 23 byte được chuyển bằng một cấu hình UDMA TX, thay vì nhiều
lượt ghi nhỏ phát sinh bởi lớp formatted I/O.

Đây vẫn là workload FC + UDMA UART. Nó không khởi động cluster, không chạy
PE0...PE7, không dùng TCDM cluster hoặc MCHAN DMA.

## ELF

Nguồn ELF:

```text
/home/dungpc/ndmoney4porche/projects/doc/gvsoc_demo/zcu104_uart_direct
```

Bản snapshot thực sự dùng cho report:

```text
report/zcu104_uart_direct/elf/zcu104_uart_direct
```

SHA-256:

```text
13f7b41018b8d83688d789c614cba6d25d3e4b958f27882840cf655560a02ed3
```

Thuộc tính:

- ELF32 little-endian RISC-V;
- RVC, soft-float ABI;
- statically linked;
- entry point `0x1c008080`;
- có DWARF, không bị strip;
- kích thước file khoảng 68 KiB;
- `.text` khoảng `0x78c` byte;
- buffer 23 byte nằm tại `0x1c000820` trong L2/data.

Nội dung buffer trong ELF:

```text
48 65 6c 6c 6f 20 50 55 4c 50 20 66 72 6f 6d 20
5a 43 55 31 30 34 0a
```

## Luồng chương trình

```text
PULP runtime boot
      |
      +-- pos_init_start
      |      |
      |      +-- uart_open: bật clock + ghi UART setup 0x00560306
      |
      +-- main
      |      |
      |      +-- uart_write(channel=0, address=0x1c000820, size=23)
      |             |
      |             +-- UDMA đọc một buffer 23 byte từ L2
      |             +-- UART TX serialize 23 byte
      |             +-- CPU poll trạng thái hoàn tất
      |
      +-- pos_init_stop
      |      |
      |      +-- uart_close
      |
      +-- exit(0) --> testbench status 0x00000000
```

## Kết quả GVSoC

- Target: `pulp-open`.
- Process exit code: 0.
- FC trace: 4.634 instruction.
- PE0 trace: 0 instruction, đúng vì ứng dụng không bật cluster.
- Trace đi qua `main`, `uart_open`, `uart_write`, `uart_close`, `exit`.
- `main` nạp địa chỉ `0x1c000820`, size 23 rồi tail-call `uart_write`.
- UART setup register `0x1a1020a4` nhận `0x00560306`.
- TX start address `0x1a102090` nhận `0x1c000820`.
- TX size `0x1a102094` nhận `0x17`.

UART checker của GVSoC được đặt `825000 baud` và console giải mã đúng toàn bộ:

```text
Hello PULP from ZCU104\n
```

Ba byte nhiễu ở lần thử ban đầu là do checker mặc định dùng `115200 baud`.
Clock peripheral hiệu dụng của model GVSoC khác RTL testbench, nên baud decoder
GVSoC (`825000`) và RTL (`202250`) không cần giống nhau. Binary và UART setup
register vẫn giữ nguyên.

Artifact:

- `gvsoc.log`: chuỗi UART đã giải mã đúng;
- `gvsoc/fc.log`: instruction trace FC;
- `gvsoc/pe0.log`: rỗng có chủ đích;
- `gvsoc/gvsoc_config.json`: cấu hình target thực tế.

## Kết quả RTL/Questa

- Monitor UART được đặt `202250 baud` theo bit period đã đo.
- Testbench tự in `RX string: Hello PULP from ZCU104`.
- File `stdout/uart` chứa đúng 23 byte, đã lưu thành `rtl/uart_decoded.txt`.
- Testbench status: `0x00000000`.
- Runner: PASS, exit code 0.
- FC trace: 22.957 instruction, không tính header.
- PE0...PE7 trace chỉ có header; cluster không hoạt động.
- Kết thúc mô phỏng tại `4.979.801 ns`.
- Thời gian thực khoảng 26 giây.

Bốn `vsim-191` là nhiễu khởi động đã biết của Questa 10.7c. Các bằng chứng
nghiệm thu là chuỗi UART đúng, status 0, do-file status 0 và runner exit 0.

## Waveform

Do-file chọn 13 đối tượng/nhóm tín hiệu:

- reset và exit status;
- UART pad theo hai chiều và enable của testbench receiver;
- FC fetch và boot address;
- cluster clock/reset/fetch/busy để chứng minh cluster không được dùng.

Artifact:

- `rtl/wave/zcu104_uart_direct.vcd.gz`;
- `rtl/wave/zcu104_uart_direct.gtkw`.

Mở:

```bash
cd report/zcu104_uart_direct/rtl/wave
gtkwave zcu104_uart_direct.gtkw
```

Trong hierarchy testbench, `w_uart_rx` là tín hiệu TX từ DUT đi vào UART receiver
của testbench. Tên này được đặt theo phía nhận của testbench, không phải theo
phía phát của PULP.

Bit period trên waveform xấp xỉ `4.944384 us`, tương ứng khoảng `202250 baud`.
Ở tốc độ này, toàn bộ 23 byte được decoder của testbench nhận đúng.

## HTML instruction viewer

Viewer:

```text
report/zcu104_uart_direct/flow_viewer.html
```

Nó chứa toàn bộ 27.591 instruction đã parse:

| Backend | Core | Instruction |
|---|---|---:|
| GVSoC | FC | 4.634 |
| RTL | FC | 22.957 |
| GVSoC/RTL | Cluster | 0 |

Hai ô log mặc định chỉ hiện kết quả quan trọng. Với RTL, đó là `RX string`,
status core, `exit_status` và thời gian kết thúc. Bấm **Xem transcript RTL đầy
đủ** nếu cần xem warning khởi tạo Questa; các warning này không phải log lệnh.

Mở:

```bash
firefox report/zcu104_uart_direct/flow_viewer.html
```

Cách xem đề xuất:

1. Chọn `GVSoC / FC`, tìm `main`.
2. Chọn tốc độ và bấm `Play` để xem hai playhead, hoặc xem năm instruction của
   `main`: nạp buffer, size 23, channel 0 và jump tới `uart_write`.
3. Tìm `uart_open` hoặc địa chỉ `0x1a1020a4` để thấy setup `0x00560306`.
4. Tìm `0x1a102090` và `0x1a102094` để thấy start address/size của UDMA TX.
5. Tìm `uart_write` để thấy polling trạng thái TX.
6. Chuyển sang `RTL / FC` và đối chiếu cùng PC/opcode.
7. Tìm `direct_uart.c`; DWARF ánh xạ `main` về source gốc của ELF.

ELF không có convention `phaseN_*`, nên viewer tự suy luận timeline từ `_start`,
`main`, `pos_init_stop` và `exit`. Bốn block tương ứng runtime init,
`main + UART/application`, runtime shutdown và exit. Chiều rộng block dùng đúng
tỷ lệ simulation time; hai lane GVSoC/RTL luôn hiện đồng thời trên cùng một
thang thời gian. Khi Play, playhead trắng đi theo backend/core đang chọn và
playhead xanh của backend kia đồng bộ theo cùng giai đoạn, không phải lockstep
cycle. Play chỉ cuộn bên trong khung instruction, không kéo vị trí trang khỏi
timeline. Legend ghi duration, phần trăm và cycle. Instruction replay, search,
register access, physical address và source mapping vẫn hoạt động đầy đủ.

## So sánh với `zcu104_uart_smoke`

| Thuộc tính | `uart_smoke` | `uart_direct` |
|---|---:|---:|
| ELF size | khoảng 92 KiB | khoảng 68 KiB |
| C entry | `printf(...)` | `uart_write(..., 23)` |
| GVSoC FC instruction | 5.397 | 4.634 |
| RTL FC instruction | 35.405 | 22.957 |
| RTL simulation end | 7.888.701 ns | 4.979.801 ns |
| RTL UART decode | testbench giải mã trực tiếp | testbench giải mã trực tiếp |
| Chuỗi nhận được | đúng | đúng |

Sự giảm instruction chủ yếu do bỏ formatter `printf` và truyền cả buffer trong
một giao dịch UDMA.

Không dùng tổng thời gian mô phỏng làm cycle benchmark ứng dụng: phần lớn thời
gian đầu là testbench/JTAG nạp ELF, và hai ELF có kích thước khác nhau.

## Lệnh GVSoC

```bash
source sw/gvsoc/env.sh
gvsoc --target=pulp-open \
  --work-dir="$PWD/report/zcu104_uart_direct/gvsoc" \
  --binary="/home/dungpc/ndmoney4porche/projects/doc/gvsoc_demo/zcu104_uart_direct" \
  --config-opt=uart_checker/uart_checker/baudrate=825000 \
  --trace=chip/soc/fc/insn:fc.log \
  --trace=chip/cluster/pe0/insn:pe0.log run
```

## Lệnh RTL + waveform

```bash
DO_FILES="-do $PWD/report/zcu104_uart_direct/uart_wave_capture.do" \
APP_DIR="$PWD/sw/flow_demo" \
SIM_TIMEOUT="80 ms" WALL_TIMEOUT=3600 \
PULP_RISCV_GCC_TOOLCHAIN=/opt/pulp-toolchain \
sw/full_system/run_sim.sh run \
  TARGETS=/home/dungpc/ndmoney4porche/projects/doc/gvsoc_demo/zcu104_uart_direct \
  TARGET_BUILD_DIR="$PWD/report/zcu104_uart_direct/rtl/work" \
  "vsim_flags=+ENTRY_POINT=0x1c008080 -permit_unmatched_virtual_intf -gBAUDRATE=202250 -gUSE_HWPE_CL=1 -gLOAD_L2=JTAG"
```

## Giới hạn

- GVSoC và RTL có boot/runtime path khác nhau; raw instruction count không nên
  so trực tiếp như cycle accuracy.
- Timeline là giai đoạn suy luận từ symbol runtime; ứng dụng không có phase
  marker chủ động và không đo vùng code tách khỏi runtime.
- Không kiểm tra cluster, TCDM, barrier, MCHAN DMA hoặc HWPE.
- UART baud phụ thuộc clock platform. Hai lượt cuối dùng decoder `825000` trên
  GVSoC và `202250` trên RTL để cùng nhận đúng chuỗi 23 byte.
