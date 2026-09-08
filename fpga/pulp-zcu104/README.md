# PULP trên ZCU104

Target này được dựng từ [gap analysis](../../doc/dungpc/zcu102-to-zcu104-gap.md).
Nó **chưa từng chạy trên board thật** — mới chỉ qua synthesis.

## Chạy

```bash
source /tools/Xilinx/Vivado/2019.1/settings64.sh
# BẮT BUỘC trên Ubuntu mới: Vivado 2019.1 cần libtinfo.so.5 mà hệ thống không
# còn; Vivado tự mang theo một bản trong lib/lnx64.o/SuSE.
export LD_LIBRARY_PATH="/tools/Xilinx/Vivado/2019.1/lib/lnx64.o/SuSE:$LD_LIBRARY_PATH"

make -C fpga zcu104-synth   # chỉ synthesis, dừng lại, báo cáo ở fpga/pulp/reports/
make -C fpga zcu104         # đầy đủ: synth + impl + bitstream
```

Điều kiện trước: `./bender checkout && ./patch-deps && make scripts` ở gốc repo,
vì `fpga/pulp/tcl/add_sources.tcl` source `tcl/generated/compile.tcl` do bender sinh.

## Khác gì so với ZCU102

| Hạng mục | ZCU102 | ZCU104 |
|---|---|---|
| Part | `xczu9eg-ffvb1156-2-e` | `xczu7ev-ffvc1156-2-e` |
| Ref clock | `G21`/`F21` `LVDS_25` | `H11`/`G11` `LVDS` — vẫn 125 MHz |
| Reset | `AM13` | `M11` |
| UART | `E13`/`F13` `LVCMOS33` | `A20`/`C19` **`LVCMOS18`** (bank 28 là 1.8V) |
| JTAG | `A20 B20 A22 A21 B21` | `G8 H8 G7 H7 G6` — sang PMOD0 |
| Số cổng của top | 54 | **14** |
| LED | comment hết | `D5 D6 A5 B5`, nối vào 4 pad dự phòng |

Reference clock cùng 125 MHz nên `fpga/pulp/ips/xilinx_clk_mngr/tcl/run.tcl` —
file dùng chung cho mọi board — **không phải sửa**.

## Ba điểm phải kiểm khi lên board

1. **JTAG cần adapter rời.** Kênh PL của FT4232HL trên ZCU104 đã bị chiếm, nên JTAG
   phải ra PMOD0 (J55). Không cắm USB thẳng được. Dùng Digilent HS2 hoặc Olimex
   ARM-USB-OCD-H như hai file cfg của ZCU102.
2. **LED chưa chắc bật được từ phần mềm.** Bốn pad LED mới chỉ được nối ra chân FPGA.
   Muốn phần mềm điều khiển thì padmux trong `safe_domain` phải chọn đúng hàm thay thế
   để pad sang chế độ GPIO. Chưa kiểm chứng.
3. **Điện áp bank hỗn hợp.** JTAG/reset/LED ở bank 87/88 (3.3V), UART ở bank 28 (1.8V).
   Đã tách chuẩn IO trong XDC, nhưng nên soi lại `report_drc` trước khi nạp board.

## Vì sao top chỉ còn 14 cổng

Bản ZCU102 có 54 cổng, 44 trong đó là ngoại vi trên card FMC (HyperBus, camera, SDIO,
QSPI, I2C, I2S). ZCU104 chỉ có **FMC LPC**, ít chân hơn FMC HPC của ZCU102, nên không
ánh xạ nguyên vẹn được. Cổng không được ràng buộc chân sẽ làm implementation báo lỗi,
nên chúng bị bỏ hẳn. `sw/full_system` chỉ cần UART, JTAG và GPIO nên tập này là đủ.

Muốn dùng lại các ngoại vi đó thì phải kiểm từng nhóm xem FMC LPC còn đủ chân không —
xem gap analysis mục 4 hướng B.
