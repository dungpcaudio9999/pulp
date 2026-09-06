# Chuyên sâu 01 — Platform top, pad frame và safe domain

## 1. Vai trò của `pulp`

[`rtl/pulp/pulp.sv`](../../rtl/pulp/pulp.sv) là integration top dùng chung cho simulation và FPGA wrapper. Module nhận toàn bộ chân ngoài ở dạng `inout wire`, sau đó phân rã mỗi pad hai chiều thành ba nhóm tín hiệu nội bộ:

- `s_in_*`: giá trị đọc từ chân;
- `s_out_*`: giá trị logic muốn phát ra chân;
- `s_oe_*`: cho phép output của pad.

`pulp` không triển khai FC, DMA, memory hay core. Công việc chính của nó là instantiate `pad_frame`, `safe_domain`, `soc_domain`, `cluster_domain`, rồi nối các interface. Các localparam ở dòng 90–117 tính kích thước payload đã pack của năm kênh AXI.

## 2. `pad_frame`: biên điện của thiết kế

[`rtl/pulp/pad_frame.sv`](../../rtl/pulp/pad_frame.sv) chuyển giữa pad vật lý và bộ ba `in/out/oe`. Mẫu chung là:

```text
logic out_i ----> I    pad cell    PAD <----> pin ngoài
logic oe_i  ----> OEN             O ----> in_o
```

Pad cell dùng `OEN` active-low, do đó code truyền `~oe_*_i`. Các pad SPI/SDIO/camera chủ yếu dùng pull-down; UART, I2C, GPIO và HyperBus dùng pull-up. `pad_cfg_i[index][0]` điều khiển pull-enable cho phần lớn pad peripheral. HyperBus, boot select, clock, reset và JTAG dùng cấu hình pull cố định.

Ánh xạ index đáng chú ý:

| Dải `pad_cfg` | Nhóm pad |
|---|---|
| 0–6 | SPI master |
| 7–8 | I2C0 |
| 9–19 | camera |
| 20–25 | SDIO |
| 26–27 | I2C1 |
| 33–34 | UART |
| 35–38 | I2S |
| 41 trở đi | GPIO |

`bootsel[1:0]`, reference clock, reset và JTAG là input-only; JTAG TDO là output-only. Điều này giải thích vì sao chúng không đi qua mux peripheral thông thường.

## 3. `safe_domain` thực sự chứa gì

[`rtl/pulp/safe_domain.sv`](../../rtl/pulp/safe_domain.sv) instantiate đúng một khối chức năng local là `pad_control_i`. Ngoài ra nó xử lý reset và slow clock theo target:

```text
ref_clk_i ──┬──────────────> logic SoC/FLL reference
            └─ safe_domain ─> slow_clk_o
rst_ni ─────── safe_domain ─> rst_no
```

- Không định nghĩa `PULP_FPGA_EMUL`: `rstgen` đồng bộ nhả reset theo `ref_clk_i`; `slow_clk_o = ref_clk_i`.
- Có `PULP_FPGA_EMUL`: reset sync bị bypass và `fpga_slow_clk_gen` chia clock theo board.
- `test_clk_o`, `dft_cg_enable_o`, `test_mode_o`, `mode_select_o` đều bị buộc `0` trong revision hiện tại.

Tên “safe domain” gợi một always-on/power-management island đầy đủ, nhưng implementation local hiện tại không instantiate PMU/RTC register block. Hai signal nội bộ `s_rtc_int` và `s_gpio_wake` chỉ được khai báo, không tạo datapath hoạt động.

## 4. `pad_control`: routing cố định thay vì pad mux động

[`rtl/pulp/pad_control.sv`](../../rtl/pulp/pad_control.sv) nối peripheral phía SoC với các tín hiệu pad. Bốn biến alternative function đều bằng `0`; input `pad_cfg_i` được chuyển tiếp sang `pad_cfg_o`, còn pad-mux động không được thực hiện trong khối này.

Các quy tắc output-enable chính:

- SPI DQ: đảo `spi_oen_i`; SCK và CS luôn output.
- UART RX luôn input, TX luôn output.
- Camera luôn input.
- SDIO CMD/DATA theo các tín hiệu `oen`; clock luôn output.
- I2C dùng trực tiếp `*_oe_i`, phù hợp kiểu open-drain do controller điều khiển.
- GPIO[31:0] dùng `gpio_dir_i`; top chỉ sử dụng 32 GPIO dù define toàn cục là 64.
- HyperBus clock, CS, reset luôn output; DQ/RWDS đổi chiều theo controller.

`gpio_cfg_i` phẳng 192 bit được `safe_domain` pack thành `32 x 6 bit`; khi đi ra pad frame, `pad_control` chỉ giữ bốn bit thấp và thêm hai bit `0` cho mỗi GPIO. Đây là một chỗ nên kiểm tra kỹ nếu software mong cả sáu bit cấu hình GPIO có hiệu lực ở pad.

## 5. Luồng một giao dịch peripheral

Ví dụ UART TX:

```text
pulp_soc.uDMA/UART
  -> soc_domain.uart_tx_o
  -> safe_domain.pad_control (out_uart_tx=uart_tx, oe=1)
  -> pad_frame UART TX cell
  -> pad_uart_tx
```

Ví dụ camera RX đi ngược lại:

```text
pad_cam_data[7:0]
  -> pad_frame in_cam_data
  -> pad_control cam_data_o
  -> soc_domain.cam_data_i
  -> pulp_soc camera/uDMA logic
```

## 6. Điểm quan sát khi mô phỏng

Để phân biệt lỗi peripheral controller và lỗi pad routing, quan sát theo ba tầng: `soc_domain_i` peripheral signal, `safe_domain_i.pad_control_i` signal, rồi `pad_*`. Nếu tầng đầu thay đổi nhưng chân không đổi, lỗi nằm ở direction/OE hoặc pad mapping; nếu tầng đầu không đổi, cần đi sâu vào `pulp_soc`.

