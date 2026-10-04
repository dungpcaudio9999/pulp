# Kết quả chạy `zcu104_uart_smoke` trên GVSoC và RTL

Ngày chạy: 2026-10-03 (Asia/Bangkok).

## Kết luận

ELF do người dùng cung cấp đã chạy đến `exit(0)` trên cả GVSoC `pulp-open` và
RTL/Questa. RTL testbench nhận status `0x00000000`. Waveform UART giải mã thành:

```text
Hello PULP from ZCU104
```

Đây là workload FC + UDMA UART rất ngắn. Nó không khởi động cluster, không chạy
PE0...PE7, không dùng TCDM cluster hoặc MCHAN DMA. Vì vậy artifact này chủ yếu
cho thấy boot/runtime, `main`, `printf`, driver UDMA UART và `exit`.

## ELF

Nguồn ELF:

```text
/home/dungpc/ndmoney4porche/projects/doc/gvsoc_demo/zcu104_uart_smoke
```

Bản snapshot dùng cho hai backend:

```text
report/zcu104_uart_smoke/elf/zcu104_uart_smoke
```

SHA-256:

```text
40d9d50a0a0ec783d7d8df38708aee23ea75e0ed0ed50a3778fdfab5dba1e6da
```

ELF là RISC-V 32-bit little-endian, RVC, soft-float ABI, statically linked,
entry point `0x1c008080`, có DWARF và không bị strip.

## Kết quả GVSoC

- Target: `pulp-open`.
- Exit code của `gvsoc`: 0.
- FC trace: 5.397 instruction.
- PE0 trace: 0 instruction, đúng vì ứng dụng không bật cluster.
- Trace đi qua `main`, `printf`, `uart_open`, `uart_write`, `uart_close` và
  cuối cùng ghi status thành công tại `exit`.

UART checker của GVSoC được đặt `825000 baud` và console giải mã đúng đủ 23 byte:

```text
Hello PULP from ZCU104\n
```

Giá trị này khác baud monitor RTL vì clock hiệu dụng của peripheral trong model
GVSoC `pulp-open` khác clock của RTL testbench. Nếu giữ mặc định `115200`, console
GVSoC sẽ ra byte nhiễu dù instruction trace vẫn chạy hết và gọi `exit(0)`.

Artifact:

- `gvsoc.log`: chuỗi UART đã giải mã đúng;
- `gvsoc/fc.log`: instruction trace FC;
- `gvsoc/pe0.log`: rỗng có chủ đích;
- `gvsoc/gvsoc_config.json`: cấu hình model thực tế.

## Kết quả RTL/Questa

- RTL testbench status: `0x00000000`.
- FC trace: 35.405 instruction, không tính dòng header.
- Trace PE0...PE7 chỉ có header, đúng vì cluster không chạy.
- Lượt mô phỏng kết thúc ở 7.888.701 ns; phần lớn thời gian là JTAG load.
- Bốn `vsim-191` là nhiễu Questa 10.7c đã biết; status và exit code vẫn PASS.

ELF ghi UART setup `0x00560306`; divider là `0x56`. Waveform cho thấy bit UART
dài `4.944.384 ps`, tương ứng khoảng `202.250 baud`. Lượt RTL cuối đặt monitor
ở đúng `202250 baud`; testbench trực tiếp in:

```text
Hello PULP from ZCU104\n
```

Artifact:

- `rtl/transcript.log`: transcript của lượt PASS có waveform;
- `rtl/raw/trace_core_1f_0.log`: FC instruction trace;
- `rtl/raw/trace_core_00_0.log` ... `_7.log`: header-only cluster trace;
- `rtl/uart_decoded.txt`: đúng 23 byte do monitor UART RTL nhận được;
- `rtl/wave/zcu104_uart_smoke.vcd.gz`: waveform chọn lọc;
- `rtl/wave/zcu104_uart_smoke.gtkw`: cấu hình GTKWave.

## HTML viewer

`flow_viewer.html` chứa toàn bộ 40.802 instruction đã parse:

| Backend | Core | Instruction |
|---|---|---:|
| GVSoC | FC | 5.397 |
| RTL | FC | 35.405 |
| GVSoC/RTL | Cluster | 0 |

Hai ô log mặc định chỉ hiện kết quả quan trọng. Với RTL, đó là `RX string`,
status core, `exit_status` và thời gian kết thúc. Bấm **Xem transcript RTL đầy
đủ** nếu cần xem warning khởi tạo Questa; các warning này không phải log lệnh.

Mở viewer:

```bash
firefox report/zcu104_uart_smoke/flow_viewer.html
```

ELF không có symbol `phaseN_*` theo convention của `flow_demo`, nên viewer tự
suy luận timeline từ các mốc runtime `_start`, `main`, `pos_init_stop` và
`exit`. Timeline có bốn giai đoạn: runtime init, `main + UART/application`,
runtime shutdown và exit. Chiều rộng block dùng đúng tỷ lệ simulation time;
legend bên dưới ghi duration, phần trăm và cycle, kể cả với block quá nhỏ để
hiện nhãn. Hai lane GVSoC và RTL luôn hiện đồng thời trên cùng thang thời gian
tính từ `_start`. Khi bấm Play, playhead trắng đi theo backend/core đang chọn;
playhead xanh của backend kia được đồng bộ theo cùng giai đoạn để đối chiếu,
không được hiểu là lockstep cycle. Play chỉ cuộn bên trong khung instruction,
không kéo vị trí trang khỏi timeline. Phần instruction replay vẫn đầy đủ. Cách
xem đề xuất:

1. Chọn `GVSoC / FC`, tìm `main`.
2. Chọn tốc độ rồi bấm `Play` để xem instruction và hai playhead; hoặc bấm
   `Tiếp` để đi từng lệnh từ `main` vào `printf` và driver UART.
3. Tìm `uart_open` để xem ghi clock-gate/config UART.
4. Tìm `uart_write` để xem UDMA TX được cấu hình nhiều lần.
5. Chọn `RTL / FC` và lặp lại; source được ánh xạ về `hello.c` và
   `udma_uart.c` bằng DWARF của ELF.
6. Tìm địa chỉ vật lý `0x1a1020a4` để thấy UART setup register.

HTML là instruction viewer, không phải waveform. Mở tín hiệu UART RTL bằng:

```bash
cd report/zcu104_uart_smoke/rtl/wave
gtkwave zcu104_uart_smoke.gtkw
```

Trong GTKWave, `w_uart_rx` là đường TX từ DUT đi vào UART receiver của testbench
(tên tín hiệu theo góc nhìn pad/testbench). Cluster busy/fetch giữ inactive và
làm bằng chứng workload không sử dụng cluster.

## Lệnh GVSoC đã dùng

```bash
source sw/gvsoc/env.sh
gvsoc --target=pulp-open \
  --work-dir="$PWD/report/zcu104_uart_smoke/gvsoc" \
  --binary="/home/dungpc/ndmoney4porche/projects/doc/gvsoc_demo/zcu104_uart_smoke" \
  --config-opt=uart_checker/uart_checker/baudrate=825000 \
  --trace=chip/soc/fc/insn:fc.log \
  --trace=chip/cluster/pe0/insn:pe0.log run
```

## Lệnh RTL cơ bản đã dùng

Không build lại ELF. Biến `TARGETS` trỏ thẳng đến binary đã cung cấp, còn
`TARGET_BUILD_DIR` tạo working directory riêng:

```bash
APP_DIR="$PWD/sw/flow_demo" \
DO_FILES="-do $PWD/report/zcu104_uart_smoke/uart_wave_capture.do" \
SIM_TIMEOUT="80 ms" WALL_TIMEOUT=3600 \
PULP_RISCV_GCC_TOOLCHAIN=/opt/pulp-toolchain \
sw/full_system/run_sim.sh run \
  TARGETS=/home/dungpc/ndmoney4porche/projects/doc/gvsoc_demo/zcu104_uart_smoke \
  TARGET_BUILD_DIR="$PWD/report/zcu104_uart_smoke/rtl/work" \
  "vsim_flags=+ENTRY_POINT=0x1c008080 -permit_unmatched_virtual_intf -gBAUDRATE=202250 -gUSE_HWPE_CL=1 -gLOAD_L2=JTAG"
```

Waveform dùng `uart_wave_capture.do`; đây là do-file riêng của report này.

## Giới hạn khi so sánh

- GVSoC và RTL có boot/runtime path khác nhau nên tổng instruction count không
  được hiểu là hai backend thực thi sai khác chương trình C.
- Timeline là giai đoạn suy luận từ symbol runtime, không phải marker do source C
  chủ động phát ra như `flow_demo`.
- UART baud phụ thuộc clock runtime của platform. Với ELF này, decoder là
  `825000` trên GVSoC và `202250` trên RTL; đây là cấu hình decoder, không phải
  thay đổi binary hay luồng lệnh CPU.
- Với workload ngắn này, không thể đánh giá cluster, barrier, TCDM hoặc DMA.
