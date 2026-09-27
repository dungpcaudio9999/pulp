# Khảo sát GVSoC cho PULP: đo được gì, chạy được tới đâu

Ngày lập: **2026-09-19**. Mục tiêu: hiểu GVSoC đo được những thông số nào trên PULP,
và số đo nào dùng được cho RTL của checkout này
([cấu hình hiệu lực](../architecture/deep_dive_00_effective_configuration.md)).
Nhãn bằng chứng: **[GVSOC]** là đã chạy trên GVSoC; **[SIM mới]** là đã chạy RTL
trên Questa trong đợt này; **[SRC]** là đọc từ source; **[CẦN ĐO]** là chưa có bằng
chứng.

Kết quả cuối cùng là ba bảng: khối nào chạy được (§3), cơ chế đo nào có (§4), và
thông số nào tin được, đã đối chiếu với RTL (§8).

## 1. Môi trường và cách chạy

| Thành phần | Phiên bản |
|---|---|
| GVSoC | `~/gvsoc` @ `3b4c489`, target `pulp-open` |
| PULP SDK (PMSIS/PulpOS) | `~/pulp-sdk` @ `d4b5bcd` |
| Toolchain | `/opt/pulp-toolchain`, gcc 7.1.1 |
| RTL simulator | Questa 10.7c; runner `sw/full_system/run_sim.sh` tự khởi động `lmgrd` |

Mã nguồn trong [`sw/gvsoc/`](../../../../sw/gvsoc/):

| Thành phần | Việc |
|---|---|
| `env.sh` | `source` trước mọi lệnh GVSoC. Đưa `/usr/bin` lên đầu PATH: python3 của miniforge thiếu `prettytable`/`pyelftools`, cmake 3.3.2 của Xilinx lỗi `libidn` |
| `step1_sdk_tests.sh` | Bước 1: chạy các test SDK, ghi PASS/FAIL |
| `step2_inventory.sh` | Bước 2: lập danh mục trace, VCD, công suất |
| `ubench/` | Bước 3: microbenchmark bằng PMSIS (chỉ chạy trên GVSoC) |
| `ubench_rt/` | Bước 4: cùng các phép thử, viết bằng `pulp-runtime`; **một ELF chạy được trên cả GVSoC và RTL** |
| `icache_sweep/` | Bước 5: quét kích thước code 256 B → 6 KiB để đo I-cache |
| `targets/pulp-open-icache8k.py` | Bước 5: target biến thể với shared I-cache 8 KiB, không sửa `~/gvsoc` |
| `analyze/func_profile.py` | Cycle theo hàm từ trace `insn` |
| `analyze/compare_ubench.py` | Bảng so sánh GVSoC với RTL từ hai log |

Chạy cùng một ELF trên RTL:
`APP_DIR=$PWD/sw/gvsoc/ubench_rt sw/full_system/run_sim.sh all run`. Biến `APP_DIR`
mới được thêm vào runner; mặc định vẫn là `sw/full_system`.

Kết quả thô nằm trong [`report/gvsoc_20260919/`](../../../../report/gvsoc_20260919/00_README.md).

## 2. Trạng thái

| Bước | Câu hỏi | Trạng thái |
|---|---|---|
| 1 | GVSoC chạy được những gì của PULP? | **Xong** (§3) |
| 2 | Mỗi cơ chế đo cho ra dữ liệu gì? | **Xong** (§4). `--gui` chưa cài (§4.2) |
| 3 | Số đo có hợp lý không? | **Xong** (§5) |
| 4 | GVSoC khác RTL ở đâu? | **Xong** cho 29 phép đo, cùng ELF trên RTL Questa (§6) |
| 5 | Mở rộng được tới đâu? | **Xong** một thí nghiệm I-cache (§7); HWPE chưa làm |

## 3. Bước 1: khối nào chạy được [GVSOC]

12 trên 14 test SDK PASS (`step1/summary.txt`).

| Test | Khối được dùng | Kết quả |
|---|---|---|
| `hello` (FC và cluster) | FC, L2, stdout, khởi động cluster | PASS |
| `cluster/call`, `cluster/fork` | 8 PE, event unit, dispatch | PASS |
| `dma/1d` | MCHAN DMA L2↔L1 | PASS |
| `perf/double_buffering`, `perf/matmult` | DMA chồng với tính toán, perf counter | PASS |
| `flash/simple`, `fs/read` (FC và cluster) | uDMA, HyperFlash, file system | PASS |
| `ram/simple` | HyperRAM | PASS |
| `uart/loopback` | uDMA UART | PASS |
| `flash/with_ram` | lệnh erase flash | FAIL: model HyperFlash không hỗ trợ erase. SDK cũng tự skip test này |
| `cluster/fork_power` | công suất với `--event=.*` | Dừng tay: sinh VCD **22 GB trong 4 phút**. Đã loại khỏi script |

Phần mềm của repo: `sw/full_system` chạy được trên GVSoC khi build với
`make all SKIP_HWPE=1`. Phase 0–6 và 8 OK, phase 7 SKIP, kết quả `SUCCESS`
(`report/gvsoc_20260919/full_system/run.log`). Build mặc định không đổi; không có
cờ này thì phase 7 treo vì `pulp-open` không có model HWPE datamover.

Không có model: HWPE datamover, FPU dùng chung của cluster [SRC].

## 4. Bước 2: danh mục cơ chế đo [GVSOC]

### 4.1 Danh mục

Chạy `hello` bản cluster với mọi trace và event (`step2/`). Kết quả gồm 1475 đường
trace, 2555 tín hiệu VCD thuộc 112 nhóm component, và 262 dòng công suất.

| Cơ chế | Cách bật | Nội dung chính |
|---|---|---|
| Trace lệnh | `--trace=<core>/insn` | Mỗi lệnh: thời điểm (ps), cycle, hàm:dòng, PC, lệnh, giá trị thanh ghi đọc/ghi, địa chỉ vật lý |
| Trace component | `--trace=<regex>` | Thông điệp của từng model; danh sách ở `step2/traces.txt` |
| VCD của core | `--vcd --event=...` | `pc`, `func`/`file`/`line`/`asm`, `busy`, `stalled`, `wfi`, `elw_stalled`, `irq_enter/exit`, `lsu/{addr,size,is_write,req_denied}` và 22 tín hiệu `pcer_*` |
| VCD bộ nhớ | như trên | Mỗi bank L1, L2 private, 48 cut L2 shared: `req_addr`, `req_size`, `req_is_write` |
| VCD interconnect | như trên | Mỗi router, theo từng đích: `addr`, `size` |
| VCD I-cache | như trên | `refill`, `refill_addr`, nội dung từng line |
| VCD DMA / event unit | như trên | `dma/channel_N`; `event_unit/core_N/active` |
| VCD clock | như trên | `cycles`, `period` của từng clock domain |
| Perf counter | `pi_perf_*` (PMSIS) hoặc `cpu_perf_*` (`pulp-runtime`) | Xem §5, §6 |
| Công suất | `--power` | `power_report.csv`, dynamic và leakage theo cây component |
| Thống kê theo lệnh | `gvsoc_analyze_insn --trace <file>` | Số lần và cycle trung bình của từng loại lệnh |
| Thống kê theo hàm | `sw/gvsoc/analyze/func_profile.py <file>` | Cycle, số lệnh, CPI của từng hàm |
| Tham số lúc chạy | `gvsoc --target=pulp-open target_properties` | Chỉ có 4: `cluster/redmule`, `soc/fic`, `soc/binary`, `uart_checker/loopback` |
| Sơ đồ kiến trúc | `gvsoc --target=pulp-open diagram` | `step2/architecture.svg` |

Danh sách đầy đủ theo component: `step2/vcd_by_component.txt`.

**Công suất chỉ có model cho 16 bank L1**. Core, L2, DMA và interconnect đều ra
0 W. Vì vậy `--power` trên `pulp-open` thực chất là công suất L1.

### 4.2 Profile theo lệnh và theo hàm

Chạy trên trace `cluster/pe0/insn` của `ubench_rt` (`step2/analyze_insn/`):

- Theo lệnh: `p.sw` trung bình 21.5 cycle (ghi ra L2 và stdout), `p.lbu` 12.2 cycle
  (đọc chuỗi định dạng của `printf` từ L2), `add` 1.2 cycle.
- Theo hàm: khoảng **90% thời gian của pe0 nằm trong `printf`** (`pos_libc_prf`
  31.7%, `strchr` 26.7%, `fputc` 19.4%…). Các kernel đo thật chỉ chiếm vài phần
  trăm. Khi đo, luôn đặt `printf` ngoài vùng đếm.

`--gui` **chưa dùng được**: trình xem `gvsoc-gui` không được cài. Muốn có thì chạy
`make gui` trong `~/gvsoc`; lệnh này clone repo `gvsoc/gui` qua SSH rồi build.

## 5. Bước 3: số đo có hợp lý không? [GVSOC]

Chương trình: [`sw/gvsoc/ubench/test.c`](../../../../sw/gvsoc/ubench/test.c). Kernel viết
bằng asm để số lệnh cố định. Hai lần chạy cho kết quả **giống hệt nhau**, nên
GVSoC là tất định. Dữ liệu: `step3/ubench_run1.csv`.

| Phép thử | Kỳ vọng | Đo được |
|---|---|---|
| ALU trên cluster, 10 lệnh/vòng | ~12 cycle/vòng (10 lệnh + 2 phạt nhánh taken) | 12.07; `instr` đúng 10010 |
| ALU trên FC | như cluster | **22.05**; `imiss` = 10025. FC đứng 5 cycle mỗi lần fetch sang dòng 16 B mới, đúng bằng `latency=5` của `fc_fetch_ico` |
| Load-use | +1 cycle/vòng; `LD_STALL` = N | 7.07 so với 6.09; `ld_stall` = 1000 |
| TCDM: 8 core cùng bank so với khác bank | cùng bank chậm hơn nhiều | 776 so với 794; `tcdm_cont` = 0. L1 interleaver chuyển request thẳng tới bank, không có arbitration [SRC] |
| DMA 64 B → 16 KiB | tuyến tính | 8 B/cycle |
| Barrier 1–8 core | gần như không đổi | 9.5–9.9 cycle/barrier |

Counter được khai báo nhưng **không bao giờ tăng** [GVSOC, SRC]: `LD_EXT`,
`ST_EXT`, `LD_EXT_CYC`, `ST_EXT_CYC`, `TCDM_CONT`, `JR_STALL`. ISS không có lệnh
`event_account` nào cho chúng.

Lưu ý khi đo bằng PMSIS: `PI_PERF_CYCLES` đọc timer **dùng chung** của cluster.
Khi nhiều core đo cùng lúc, mỗi core phải dùng `PI_PERF_ACTIVE_CYCLES`.

## 6. Bước 4: GVSoC so với RTL [GVSOC, SIM mới]

### 6.1 Cách so

[`sw/gvsoc/ubench_rt/test.c`](../../../../sw/gvsoc/ubench_rt/test.c) được build một lần
bằng `pulp-runtime`. **Cùng một ELF** (sha256 `49bd9044…`) chạy trên GVSoC và trên
RTL `tb_pulp` (Questa, JTAG load, `-gUSE_HWPE_CL=1`); RTL kết thúc `PASS (exit 0)`.
Hai bên đọc cùng các CSR `0x780+i`.

Perf counter trong RTL [SRC]: `riscv_cs_registers.sv` chỉ gộp về **một** thanh ghi
khi có `SYNTHESIS` (tổng hợp ASIC). Trong mô phỏng, mỗi event có counter riêng.
Counter 12–16 được nối trong `core_region.sv`: `perf_l2_ld/st(_cyc)` và
`tcdm_contention`. Như vậy các counter mà GVSoC luôn để 0 thì RTL có số thật.

Bảng đầy đủ: `report/gvsoc_20260919/step4/compare.md`, sinh bằng
`sw/gvsoc/analyze/compare_ubench.py`.

### 6.2 Kết quả (cycle, core 0)

| Phép thử | GVSoC | RTL | GVSoC/RTL | Ghi chú từ counter RTL |
|---|---|---|---|---|
| FC: ALU 1000 vòng | 22003 | 12007 | **1.83** | RTL `imiss` = 0: FC fetch không tốn thêm cycle |
| FC: load-use | 7019 | 7005 | 1.00 | `ld_stall` = 1000 ở cả hai |
| FC: pointer chase L2 | 910 | 901 | 1.01 | |
| Cluster: ALU | 12039 | 12092 | 1.00 | |
| Cluster: load-use | 7042 | 7047 | 1.00 | |
| Cluster: pointer chase L2 | 4504 | 4516 | 1.00 | `ld_ext_cyc`/256 = **15.0 cycle mỗi load L2**; GVSoC +14 |
| Cluster: pointer chase L1 | 904 | 927 | 0.98 | |
| 8 core, khác bank | 810 | 931 | 0.87 | RTL `imiss` 156 so với 38: 8 core tranh nhau shared I-cache |
| 8 core, cùng bank | 778 | 1032 | **0.75** | RTL `tcdm_cont` = 127/128 load; GVSoC = 0 |
| 8 core cùng đọc L2 | 2570 | 2686 | 0.96 | RTL 14.9 cycle/load, gần bằng lúc 1 core: tranh chấp AXI nhỏ |
| DMA L2→L1, 256 B | 81 | 111 | 0.73 | Sai lệch lớn nhất ở kích thước nhỏ |
| DMA L2→L1, 8 KiB | 1071 | 1177 | 0.91 | Độ dốc: GVSoC 8.0 B/cycle, RTL 7.5 B/cycle |
| DMA L1→L2, 8 KiB | 1093 | 1183 | 0.92 | |
| 100 barrier 8 core (timer) | 2596 | 2864 | 0.91 | 26.0 so với 28.6 cycle mỗi vòng |

### 6.3 Khác biệt cấu hình

| Hạng mục | RTL checkout | GVSoC `pulp-open` | Hệ quả |
|---|---|---|---|
| Số PE | 8 | `nb_pe=9`, nhưng pe8 không chạy lệnh nào (trace bước 2) | Không ảnh hưởng số đo |
| L1 | 64 KiB, 16 bank, có arbitration | 64 KiB, 16 bank, **không có xung đột** | Đa core lạc quan (§6.2) |
| L2 | 512 KiB | 2 MiB shared (48 cut) + 2 × 32 KiB private | Không ảnh hưởng nếu chương trình vừa 512 KiB |
| Interconnect | arbitration | router với latency cố định, không đặt băng thông [SRC] | Latency L2 khớp (15 so với 14 cycle); tranh chấp AXI trong RTL nhỏ với tải thử |
| I-cache cluster | private 512 B, shared 4 KiB | private 512 B, shared **2 bank × 2 KiB = 4 KiB** | Cùng dung lượng, điểm gãy khớp RTL; phạt miss L0 cao hơn RTL ~0.2 cycle/lệnh (§7.2) |
| Fetch của FC | không có phạt cho vòng lặp | 5 cycle mỗi dòng 16 B | CPI của FC bi quan tới 1.83 lần |
| FPU cluster | dùng chung, 4 FPNEW | không có model dùng chung | `APU_CONT` vô nghĩa |
| HWPE | datamover, 12 B/beat | không có | Phase 7 phải bỏ qua |
| Boot | JTAG | nạp ELF trực tiếp | Không đo được thời gian boot |

**Sửa kết luận trước**: bản đầu của tài liệu này ghi shared I-cache của GVSoC là
2 KiB. Sai: cấu hình có `nb_l1_banks = 2`, mỗi bank 2 KiB, tổng 4 KiB bằng RTL.
Thí nghiệm ở §7 xác nhận điều này.

## 7. Bước 5: mở rộng model [GVSOC]

### 7.1 Tạo target biến thể mà không sửa GVSoC

Target là một file Python trỏ vào generator. `sw/gvsoc/targets/pulp-open-icache8k.py`
dùng lại `Pulp_open_board` nhưng thay `cluster.json` bằng bản riêng
(`icache/config/l1/nb_sets_bits` 5 → 6, tức shared 8 KiB):

```bash
gvsoc --target-dir=sw/gvsoc/targets --target=pulp-open-icache8k --binary <ELF> run
```

Generator Python chạy lại mỗi lần khởi động nên **không cần build lại** GVSoC khi
chỉ đổi JSON hay generator. Chỉ khi sửa model C++ mới cần `make build` trong
`~/gvsoc`. `gvsoc_config.json` trong thư mục chạy cho thấy cấu hình đã được áp.

### 7.2 Quét kích thước code (`icache_sweep`)

Vòng lặp có thân dài K lệnh `c.add`, lặp 20 lần sau một lần làm nóng cache. CPI
của core 0 khi 8 core cùng chạy. Cột RTL là cùng ELF chạy trên Questa
[SIM mới], `PASS (exit 0)`:

| Kích thước code | `pulp-open` (4 KiB) | `pulp-open-icache8k` (8 KiB) | RTL (4 KiB) |
|---|---|---|---|
| 256 B | 1.02 | 1.02 | 1.03 |
| 1 KiB | 1.22 | 1.22 | 1.01 |
| 2 KiB | 1.25 | 1.25 | 1.01 |
| 3 KiB | 1.26 | 1.25 | 1.02 |
| 4 KiB | 1.31 | 1.25 | 1.09 |
| 6 KiB | **2.50** | 1.26 | **2.37** |

- **Điểm gãy dung lượng khớp RTL**: code vượt 4 KiB thì CPI tăng vọt, 2.50 trên
  GVSoC và 2.37 trên RTL. Với target 8 KiB thì code 6 KiB vẫn vừa cache.
- **Phạt miss L0 bị thổi phồng**: code 1–3 KiB vượt L0 private 512 B nhưng vừa
  shared. RTL gần như không mất gì (CPI 1.01–1.02), còn GVSoC tính khoảng 0.22
  cycle/lệnh (CPI 1.22–1.26), tức bi quan ~20%.

Dữ liệu: `report/gvsoc_20260919/step5/icache_sweep_{pulp-open,pulp-open-icache8k,rtl}.log`.

Thí nghiệm băng thông cho `axi_ico` không được làm: RTL cho thấy 8 core cùng đọc L2
chỉ chậm hơn 4% (§6.2), nên thêm giới hạn băng thông không làm GVSoC khớp RTL hơn.

## 8. Mức tin cậy của từng thông số (đã đối chiếu RTL)

| Mức | Thông số |
|---|---|
| **Khớp RTL trong ±2%** | Số lệnh, `LD`, `ST`, `BRANCH`, `TAKEN_BRANCH`, `JUMP`, `RVC`, `LD_STALL`; cycle của code chạy **một core trên cluster** khi vòng lặp vừa L0 512 B; latency load L2 từ cluster (~15 cycle); load-use trên FC |
| **Lệch có hệ thống, dùng để so sánh tương đối** | Code đa core trên cluster (GVSoC nhanh hơn 13–25%); DMA (nhanh hơn 8–27%, lệch nhiều nhất ở gói nhỏ); barrier (nhanh hơn ~9%); `IMISS` khi 8 core cùng fetch; công suất L1 |
| **Sai hướng** (GVSoC chậm hơn RTL) | Vòng lặp trên FC: tới 1.83 lần do mô hình fetch; code cluster 0.5–4 KiB: ~20% do phạt miss L0 |
| **Khớp về định tính** | Điểm gãy khi code vượt 4 KiB shared I-cache (CPI 2.50 so với 2.37) |
| **Không dùng được** | `TCDM_CONT`, `LD_EXT*`, `ST_EXT*`, `JR_STALL` (luôn 0; RTL có số thật); xung đột bank; `APU_CONT`; công suất ngoài L1; mọi thông số của HWPE |

Cách dùng: GVSoC để tìm chỗ chậm và so sánh các phương án phần mềm. Khi con số
tuyệt đối quan trọng, hoặc khi phần mềm có nhiều core cùng truy cập L1 hay chạy
nhiều trên FC, đo lại trên RTL bằng `APP_DIR=... run_sim.sh`.

## 9. Việc còn lại

- Model C++ cho HWPE datamover, nếu cần phase 7 trên GVSoC.
- Nếu muốn GVSoC khớp RTL hơn: giảm `latency` của `fc_fetch_ico` và
  `refill_latency` của L0 trong một target biến thể, rồi chạy lại `ubench_rt` và
  `icache_sweep` để hiệu chỉnh.
- Cài `gvsoc-gui` (`make gui` trong `~/gvsoc`) nếu cần xem timeline.
