# Chuyên sâu 04 — Boot, JTAG và testbench

## 1. Thành phần testbench

[`rtl/tb/tb_pulp.sv`](../../rtl/tb/tb_pulp.sv) instantiate `pulp` thành `i_dut`, tạo reference clock bằng `tb_clk_gen`, và bao quanh DUT bằng model UART, camera, SPI/flash, I2C EEPROM, HyperRAM/HyperFlash hoặc PSRAM tùy define/parameter.

Ba chế độ điều khiển chính:

- OpenOCD qua remote bitbang;
- external DPI driver;
- driver SystemVerilog nội bộ, gồm JTAG boot hoặc standalone flash boot.

## 2. JTAG chain

[`rtl/pulp/jtag_tap_top.sv`](../../rtl/pulp/jtag_tap_top.sv) ghép TAP PULP và debug transport. Configuration register xuất:

- `soc_jtag_reg_o = confreg[7:0]`;
- `sel_fll_clk_o = confreg[8]`.

Testbench dùng ba lớp package:

- `jtag_pkg`: thao tác TAP và debug module/DMI;
- `pulp_tap_pkg`: truy cập bus/L2 qua PULP TAP;
- `riscv_pkg`: mã CSR và cấu trúc debug RISC-V.

## 3. Trình tự JTAG boot chính xác

1. Đọc `+ENTRY_POINT`; mặc định `0x1C00_8080`.
2. Assert hard reset và đặt `bootsel=01` cho JTAG.
3. Đọc file stimuli (`+stimuli=...`, mặc định `vectors/stim.txt`).
4. Reset/soft-reset JTAG; chạy bypass và IDCODE test.
5. Ghi JTAG confreg để boot ROM biết nguồn image/debug.
6. Nhả hard reset; FC bắt đầu chạy boot ROM vì fetch-enable ở top luôn bật.
7. Dùng PULP TAP ghi/đọc mẫu `0xABBAABBA` tại entry point để kiểm tra đường tới L2.
8. Khởi tạo DMI, bật debug module, chọn FC hart `{31,0}`.
9. Halt FC, ghi CSR `DPC = entry_point`.
10. Nạp stimuli vào L2 bằng PULP bus access hoặc system bus của debug module.
11. Resume FC từ DPC.
12. Poll `0x1A10_40A0` tới khi bit 31 bằng 1; bits 30:0 bằng 0 là pass.

Điểm quan trọng: FC có thể đã thực thi boot ROM một khoảng trước khi halt request tới core. Đây là hành vi dự kiến, không nhất thiết là lỗi race.

## 4. Standalone boot

Với `LOAD_L2="STANDALONE"`, testbench đặt:

- `bootsel=00` cho SPI flash;
- `bootsel=10` cho HyperFlash.

Sau reset, boot ROM và peripheral/uDMA chịu trách nhiệm đưa image vào memory và chuyển điều khiển. Không có bước nạp L2 trực tiếp như JTAG mode.

## 5. Completion và stdout

Testbench không chờ một chân EOC riêng. Nó đọc polling register `0x1A10_40A0` qua debug system bus. Bit 31 là valid/done, payload 31 bit là exit code.

Khi không dùng netlist, `tb_fs_handler` được gắn bằng hierarchical reference vào `soc_peripherals_i.s_stdout_bus`. Đây là simulation-only backdoor/APB model cho stdout và file I/O; nó không phải phần cứng synthesizable của PULP top. Vì phụ thuộc hierarchy, thay đổi tên instance trong `pulp_soc` có thể làm testbench hỏng dù interface top vẫn đúng.

## 6. Clock/reset trong testbench

Reference clock đi vào `pad_xtal_in`, reset đi vào `pad_reset_n`, rồi phải qua `pad_frame` và `safe_domain` trước khi tới SoC. Vì vậy khi debug reset cần quan sát ít nhất:

```text
s_rst_n (TB) -> pad_reset_n -> pulp.s_rstn -> s_rstn_por -> pulp_soc reset
```

Ở FPGA build, slow clock có divider board-specific; simulation/non-emulation thường dùng reference clock trực tiếp làm slow clock.

## 7. Failure taxonomy

| Triệu chứng | Điểm kiểm tra đầu tiên |
|---|---|
| TAP không trả IDCODE | JTAG mux, TCK/TMS/TRST, pad routing |
| L2 pattern test fail | PULP TAP/bus path, reset/clock SoC, address |
| Halt timeout | DMI init, hartsel FC, debug IRQ |
| Image đã nạp nhưng PC sai | DPC, entry point, resume acknowledgement |
| UART im lặng | software UART config, `uart_tx`, pad_control OE, UART monitor selection |
| Poll EOC không bao giờ xong | software crash, peripheral register path, Cluster completion/event |
| stdout model compile/elaborate fail | hierarchy của `soc_peripherals_i.s_stdout_bus` khác revision |

## 8. Tín hiệu nên lưu waveform

Cho FC smoke test: reset chain, SoC clock, FC PC/fetch, JTAG DMI request/response, L2 access, stdout APB, EOC polling. Cho offload: bổ sung toàn bộ checklist trong tài liệu Cluster và event/AXI boundary.

