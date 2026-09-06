# Gap analysis: chuyển FPGA target từ ZCU102 sang ZCU104

Ngày: `2026-09-07` — Milestone 6

Nguồn dữ liệu, xếp theo độ tin cậy:

1. **UG1267** — *ZCU104 Evaluation Board User Guide*, `doc/dungpc/ug1267-zcu104-eval-bd.pdf`
   (v1.1, 09/10/2018, 92 trang). Nguồn có thẩm quyền cao nhất.
2. **Board file Vivado 2019.1** — `Vivado/2019.1/data/boards/board_files/zcu104/1.1/`.
   Chỉ phơi ra tập con các chân gắn với giao diện có tên; **không** đủ để port.
3. **Target tham chiếu** — `~/ndmoney4porche/fpt/pulpissimo/target/fpga/pulpissimo-zcu104/`,
   một target ZCU104 cho PULPissimo có sẵn trên máy. Hữu ích nhưng **có một lỗi**, xem mục 3.

---

## 1. Bảng khác biệt

| Hạng mục | ZCU102 (hiện có) | ZCU104 (đích) | Mức độ |
|---|---|---|---|
| FPGA part | `xczu9eg-ffvb1156-2-e` | `xczu7ev-ffvc1156-2-e` | đổi 1 dòng |
| Board part | — | `xilinx.com:zcu104:part0:1.1` | đổi 1 dòng |
| Reference clock | `G21`/`F21`, `LVDS_25`, 125 MHz | **`H11`/`G11`**, `LVDS`, **125 MHz** | đổi chân, **cùng tần số** |
| Reset | `AM13`, `LVCMOS33` | `M11`, `LVCMOS33` | đổi chân |
| UART | `E13`/`F13`, `LVCMOS33` | `A20`/`C19`, **`LVCMOS18`** | đổi chân **và chuẩn I/O** |
| JTAG | `A20` `B20` `A22` `A21` `B21`, `LVCMOS33` | `G8` `H8` `G7` `H7` `G6`, `LVCMOS33` | đổi chân, sang PMOD0 |
| Ngoại vi FMC | ~44 cổng đang ràng buộc | **cần quyết định** | xem mục 4 |
| LED | có chân nhưng comment hết | `D5` `D6` `A5` `B5` khả dụng | tùy chọn |
| Clocking Wizard | `PRIM_IN_FREQ {125.000}` | **giữ nguyên** | không đổi |

Điểm quan trọng: **tần số reference clock giống nhau (125 MHz)**, nên
`fpga/pulp/ips/xilinx_clk_mngr/tcl/run.tcl` — file **dùng chung cho mọi board** — không
phải sửa. Tránh được một thay đổi có nguy cơ làm hỏng zcu102 và vcu118.

---

## 2. Bảng chân ZCU104 đầy đủ

Mọi chân đã kiểm chứng tồn tại trên package `xczu7ev-ffvc1156` (1156 chân) bằng
`get_package_pins`, và đối chiếu với UG1267.

| Tín hiệu PULP | Chân | Chuẩn I/O | Bank | Căn cứ |
|---|---|---|---|---|
| `ref_clk_p` | `H11` | `LVDS` | 68 | UG1267 Bảng 3-13, net `CLK_125_P` |
| `ref_clk_n` | `G11` | `LVDS` | 68 | UG1267 Bảng 3-13, net `CLK_125_N` |
| `pad_reset` | `M11` | `LVCMOS33` | 87 | nút CPU_RESET (SW20) |
| `pad_uart_rx` | `A20` | `LVCMOS18` | 28 | UART2, kênh D của FT4232HL |
| `pad_uart_tx` | `C19` | `LVCMOS18` | 28 | UART2, kênh D của FT4232HL |
| `pad_jtag_tms` | `G8` | `LVCMOS33` | 87 | UG1267 Bảng 3-23, PMOD0_0 = J55.1 |
| `pad_jtag_tdi` | `H8` | `LVCMOS33` | 87 | PMOD0_1 = J55.3 |
| `pad_jtag_tdo` | `G7` | `LVCMOS33` | 87 | PMOD0_2 = J55.5 |
| `pad_jtag_tck` | `H7` | `LVCMOS33` | 87 | PMOD0_3 = J55.7 |
| `pad_jtag_trst` | `G6` | `LVCMOS33` | 87 | PMOD0_4 = J55.2 |
| LED 0..3 *(tùy chọn)* | `D5` `D6` `A5` `B5` | `LVCMOS33` | 88 | board file + UG1267 |

`H11`/`G11` là cặp clock-capable (`IO_L13P/N_T2L_N0_GC_QBC_68`), đúng loại chân cho clock
đầu vào. Nguồn cấp là bộ tạo clock IDT8T49N287 (U182), ngõ ra Q6.

### Đấu nối JTAG vật lý

UG1267 nêu rõ: chỉ **một** kênh của chip FT4232HL nối tới miền PL, và kênh đó đã dành cho
UART. Vì vậy **không dùng được cổng micro-USB J164 cho JTAG** — bắt buộc cắm adapter rời
vào PMOD0 (J55):

| Tín hiệu | J55 |
|---|---|
| tms / tdi / tdo / tck | 1 / 3 / 5 / 7 |
| trst | 2 |
| GND | 9 |
| 3V3 | 11 |

Target tham chiếu có sẵn cấu hình OpenOCD cho Digilent JTAG-HS1 và Olimex ARM-USB-OCD-H,
dùng lại được.

---

## 3. Lỗi trong target tham chiếu — không được sao chép

`pulpissimo-zcu104/constraints/zcu104.xdc` đặt reference clock ở **`F23`/`E23`**. Đây là
**sai** và sai theo kiểu nguy hiểm:

- `F23`/`E23` **không xuất hiện ở bất kỳ đâu trong UG1267**;
- chúng nằm ở **bank 28**, mà UG1267 (mục Bank Voltage) ghi:
  `PL Bank 28 — VCC1V8 — 1.8V — UART2 only (mostly NC pins)`;
- **NC = Not Connected.** Ngoài UART2, các chân bank 28 không nối tới đâu trên board.

Chúng vẫn là chân hợp lệ của package, nên Vivado sẽ synthesize và implement **trót lọt,
không cảnh báo gì** — nhưng trên phần cứng sẽ **không bao giờ có clock**. Thiết kế chết câm.

Bốn chân JTAG của target đó (`G8` `H8` `G7` `H7`) thì **đúng**, đã đối chiếu Bảng 3-23.

> Bài học: board file của Vivado và target của người khác đều không thay thế được tài liệu
> board. Board file chỉ phơi ra tập con chân (`F23`, `H11`, `G8` đều **không** có trong đó),
> nên khảo sát chỉ dựa vào nó sẽ bỏ sót và dễ dẫn tới kết luận sai.

---

## 4. Hạng mục lớn nhất: ~44 cổng ngoại vi FMC

`fpga/pulp-zcu102/rtl/xilinx_pulp.v` có **54 cổng**, trong đó chỉ 10 là tín hiệu lõi. Số
còn lại là ngoại vi nằm trên card FMC: HyperBus (`FMC_hyper_dqio*`, 8 bit), camera
(`FMC_cam_data*`, 8 bit), SDIO, QSPI, I2C, I2S. XDC của ZCU102 đang bật 65 ràng buộc
`set_property`, phần lớn cho nhóm này.

Cổng không được ràng buộc sẽ khiến implementation báo lỗi, nên **bắt buộc phải xử lý**.
Hai hướng:

| Hướng | Nội dung | Đánh giá |
|---|---|---|
| **A. Top rút gọn cho ZCU104** | Tạo `fpga/pulp-zcu104/rtl/xilinx_pulp.v` chỉ giữ 10 cổng lõi, bỏ toàn bộ ngoại vi FMC | **Khuyến nghị.** Đúng cách PULPissimo làm cho ZCU104 (top của nó chỉ 39 cổng). Đưa được bitstream lên board nhanh nhất |
| **B. Map sang FMC LPC của ZCU104** | Giữ nguyên 54 cổng, ánh xạ sang connector J5 | ZCU104 chỉ có **FMC LPC**, ít chân hơn **FMC HPC** của ZCU102; cần kiểm tra từng nhóm có đủ chỗ. Chỉ nên làm khi thực sự cần các ngoại vi đó |

Với mục tiêu chạy `sw/full_system` trên board thì hướng A là đủ: chương trình chỉ dùng
UART (stdout), JTAG (nạp) và GPIO/LED.

---

## 5. Danh sách file phải tạo hoặc sửa

```text
fpga/pulp-zcu104/
├── fpga-settings.mk          TẠO MỚI
├── constraints/zcu104.xdc    TẠO MỚI  — theo bảng chân mục 2
└── rtl/xilinx_pulp.v         TẠO MỚI  — bản rút gọn, xem mục 4 hướng A

fpga/Makefile                 SỬA      — thêm target zcu104 song song zcu102/vcu118
fpga/pulp/ips/.../run.tcl     KHÔNG SỬA — 125 MHz giống nhau
```

### Nội dung `fpga-settings.mk` đề xuất

```makefile
export BOARD=zcu104
export XILINX_PART=xczu7ev-ffvc1156-2-e
export XILINX_BOARD=xilinx.com:zcu104:part0:1.1
export FC_CLK_PERIOD_NS=100
export CL_CLK_PERIOD_NS=100
export PER_CLK_PERIOD_NS=100
export SLOW_CLK_PERIOD_NS=30517
```

Giữ nguyên chu kỳ của ZCU102 (10 MHz) cho lần chạy đầu thay vì lấy 62.5 ns của
PULPissimo: ZU7EV nhỏ hơn ZU9EG, nên nên để timing dễ thở ở lần bring-up đầu, siết sau.

---

## 6. Điểm cần xác minh khi triển khai

1. **Điện áp bank hỗn hợp.** JTAG và reset ở bank 87 (3.3V), UART ở bank 28 (1.8V). Cần
   xác nhận `xilinx_pulp.v` không gộp chúng vào cùng nhóm ràng buộc điện áp.
2. **`pad_jtag_trst` tham gia logic reset.** `xilinx_pulp.v:99`:
   `assign reset_n = ~pad_reset & pad_jtag_trst;` — nếu bỏ chân này thì phải buộc mức cao,
   không được để thả nổi.
3. **LED cần thêm cổng.** `xilinx_pulp.v` không có cổng LED nào. Muốn nhìn thấy GPIO chạy
   thì phải thêm, ánh xạ vào pad dự phòng — PULPissimo làm vậy với `spim_csn1`, `cam_pclk`,
   `cam_hsync`, `cam_data0`.
4. **Dung lượng đĩa.** Một lượt synthesis + implementation cho ZU7EV thường chiếm 20–40 GB.
   `/home` hiện còn 36 GB (đã dùng 89%) — nên dọn trước.
5. **Repo chưa từng chạy synthesis.** Toàn bộ lịch sử Vivado ở đây là mô phỏng XSim
   (xem [lua-chon-simulator.md](lua-chon-simulator.md)). Lần chạy đầu nên dừng ở
   `synth_design` để bắt lỗi sớm, trước khi bỏ vài giờ cho P&R.

---

## 7. Definition of Done — đối chiếu

| Tiêu chí trong [PLAN.md](PLAN.md) | Trạng thái |
|---|---|
| Có bảng khác biệt ZCU102–ZCU104 | ✅ mục 1 và 2 |
| Xác định đầy đủ file phải tạo hoặc sửa | ✅ mục 5 |
| Không dùng nguyên trạng pin constraint của ZCU102 | ✅ đã chứng minh không thể — `A20` của ZCU102 là chân UART trên ZCU104 |
| Elaboration, synthesis, DRC, timing đạt | chỉ áp dụng **nếu triển khai** port thật |

Ba tiêu chí đầu đã đạt. Tiêu chí thứ tư phụ thuộc quyết định scope: `PLAN.md` ghi rõ
*"Phần `fpga:` chỉ thực hiện nếu scope yêu cầu port thật."*
