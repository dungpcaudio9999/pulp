# Chuyên sâu 01 — Safe domain và đường I/O tới pad

Đối chiếu 2026-09-10 theo [cấu hình hiệu lực](deep_dive_00_effective_configuration.md).
Các kết luận wiring dưới đây là **[RTL]**, chưa phải chứng nhận I/O bằng mô phỏng.

## 1. Vai trò và ranh giới

[pulp](../../../../rtl/pulp/pulp.sv) instantiate `pad_frame`, `safe_domain`, `soc_domain`
và `cluster_domain`. `pad_frame` chuyển chân `inout` thành bộ ba giá trị input,
output và output-enable. Safe domain nối các tín hiệu peripheral/GPIO phía SoC
với bộ ba này, chuyển tiếp reset và tạo/chuyển tiếp slow clock.

Safe domain hiện không có PMU/RTC register block đang hoạt động. Các biến
`s_rtc_int`, `s_gpio_wake` chỉ được khai báo; `safe_domain_reg_if` không được
instantiate. Tên domain không chứng minh nó quản lý power như một always-on
island đầy đủ.

## 2. Cấu trúc hiệu lực

[safe_domain](../../../../rtl/pulp/safe_domain.sv) chứa `pad_control_i`, và nhánh clock/reset:

| Target | Module/assignment | Hiệu lực |
|---|---|---|
| RTL non-FPGA | `i_rstgen`, `slow_clk_o=ref_clk_i` | tạo `s_rstn_sync` nội bộ |
| FPGA | bypass sync, `fpga_slow_clk_gen` | chia reference theo board |
| cả hai | `rst_no=s_rstn=rst_ni` | **reset xuất domain là reset thô** |
| cả hai | test clock, DFT enable, test mode, mode select bằng 0 | không có điều khiển DFT động ở đây |

Đính chính tài liệu cũ: dù có `i_rstgen` đồng bộ theo reference, **output sync
không nối ra `rst_no`**. SoC reset generator mới đồng bộ reset cho FC theo clock
SoC; xem [đường reset đầy đủ](deep_dive_04_boot_debug_testbench.md).

## 3. Hoạt động: routing và cực tính OE

[pad_control](../../../../rtl/pulp/pad_control.sv) có bốn biến alternative function
bằng 0; port/kết nối `pad_mux_i` bị comment. Có register padmux phía SoC không
đồng nghĩa ghi register sẽ đổi đường peripheral tới pad. Routing hiện chủ yếu
cố định; `pad_cfg` là cấu hình pad khác với lựa chọn chức năng mux.

[pad_frame](../../../../rtl/pulp/pad_frame.sv) nối OE logic với `OEN` active-low của
[pad model](../../../../.bender/git/checkouts/tech_cells_generic-6a4b27e0e56cbcda/src/deprecated/pad_functional.sv):

| OE logic | OEN pad | Hành vi |
|---|---|---|
| 1 | 0 | pad drive giá trị `I` |
| 0 | 1 | driver nhả; chân do nguồn ngoài/pull quyết định |

Nhả driver không luôn làm giá trị đọc thành `Z`: pull-up/down có thể tạo mức
logic. Khi test contention cần phân biệt pull yếu với hai driver mạnh trái mức.

| Peripheral | Routing/OE trong pad_control |
|---|---|
| UART | TX theo `uart_tx_i`, OE=1; RX OE=0 |
| GPIO | output=`gpio_out_i`, OE=`gpio_dir_i`, input=`in_gpios_i` |
| SPI | SCK/CS output; DQ đảo `spi_oen_i` thành OE |
| Camera | các chân nhận input |
| I2C | chuyển tiếp output/input/OE controller; phải đọc controller để xác nhận trình tự open-drain |
| SDIO/HyperBus | clock/CS theo hướng cố định; data đổi chiều theo controller |

Pad config index: SPI 0–6, I2C0 7–8, camera 9–19, SDIO 20–25, I2C1 26–27,
UART 33–34, I2S 35–38, GPIO 41–72. `pad_cfg[index][0]` điều khiển pull-enable
ở nhiều pad peripheral; không phải mọi bit cấu hình đều được pad model dùng.
GPIO config phẳng 192 bit được pack 32×6; pad_control chuyển thành
`{2'b00,gpio_cfg_i[i][3:0]}`. Top có **32 GPIO pad**, không suy 64 pad từ macro
`GPIO_NUM=64` trong header.

```text
UART controller → soc_domain.uart_tx_o
→ safe_domain.pad_control.out_uart_tx_o, oe_uart_tx_o=1
→ pad_frame (~OE → OEN) → pad_uart_tx → UART monitor

GPIO output register → gpio_out/dir → pad_control → pad_frame → pad_gpios
→ pad_frame input → pad_control.gpio_in_o → SoC GPIO input sampling/register
```

Nhánh FPGA thay một số pad đặc biệt bằng assign trực tiếp theo
`PULP_FPGA_EMUL`; chân board nào thực sự được đưa ra ngoài còn do
`xilinx_pulp.v` và XDC. GPIO register hoạt động không chứng minh LED/pin của board
đã được nối.

## 4. Góc nhìn phần mềm [SW]

[Phase 8](../../../../sw/full_system/full_system.c#L85) lưu `PADDIR/PADOUT`, ghi direction
output, ghi `0xA5A5`, đọc lại **PADOUT**, rồi khôi phục. Nó chỉ chứng minh đường
register write/read; chưa đọc `PADIN`, chưa kiểm chứng vòng pad/input hay padmux.
GPIO HAL trong runtime có phần bị `#if 0`, nên demo truy cập register trực tiếp.

UART thật cần cấu hình clock peripheral, baud/frame, buffer và uDMA channel,
sau đó kiểm tra pad. Stdout APB simulation của `printf` không phải UART vật lý.

## 5. Thời gian và điều kiện hoạt động

**[RTL]** Routing pad_control chủ yếu combinational; độ trễ lấy mẫu GPIO còn nằm
ở controller/synchronizer phía SoC. Test ghi rồi đọc input ngay tức thì có thể
đọc mẫu cũ; cần chờ số clock đủ theo implementation hoặc poll có timeout.

**[CẦN ĐO]** Khi có output đúng ở controller mà pad sai, kiểm tra OE, pad config,
external driver và mapping. Khi pad đúng mà PADIN sai, kiểm tra input path,
input enable và sampling trước khi sửa controller output.

## 6. Phép kiểm chứng và bằng chứng

| Test | Cách làm | Điều kiện PASS |
|---|---|---|
| GPIO tự đọc pad | drive GPIO, đọc PADIN sau sampling; thu out/OE/pad/in | PADIN khớp pattern và waveform chứng minh đi qua pad |
| GPIO loopback hai chân | TB nối một output sang một input, đảm bảo chỉ một driver | pattern/đảo pattern khớp ở PADIN chân nhận |
| GPIO nhả chân | đổi direction input, TB drive 0 rồi 1 | input theo TB, output driver DUT đã nhả |
| UART TX | gửi chuỗi byte có `0x00`, `0xFF`, `0x55`, `0xA5` | monitor pad giải mã đúng byte/baud/frame |
| Pad mux | ghi lựa chọn mux rồi quan sát routing | với RTL hiện tại phải ghi rõ mux động chưa được triển khai |

**[SIM cũ: 2026-09-06, lượt 06]**
[Log phase 8 OK](../../../../report/full_system_20260906/06_PASS_toan_bo_9_phase.log)
chỉ là PADOUT readback. Các test loopback/UART ở bảng trên là **[CẦN ĐO]**;
không có kết quả chạy mới trong đợt cập nhật tài liệu này.
