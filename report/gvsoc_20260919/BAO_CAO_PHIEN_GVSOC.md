# Báo cáo phiên làm việc GVSoC — 2026-09-19

Phiên này dựng môi trường GVSoC cho PULP, khảo sát GVSoC đo được gì, và kiểm tra
số đo của GVSoC có tin được không. **Không sửa RTL.** Mọi thay đổi nằm ở phần mềm
và script. Questa chỉ được chạy để đối chiếu số đo của GVSoC với RTL.

Kết luận kỹ thuật chi tiết: [doc/dungpc/master_analysis/gvsoc/gvsoc_00_plan_do_dac.md](../../doc/dungpc/master_analysis/gvsoc/gvsoc_00_plan_do_dac.md).
Danh mục file kết quả: [00_README.md](00_README.md).

## 1. Tóm tắt

| Câu hỏi | Kết quả |
|---|---|
| GVSoC chạy được PULP không? | Được. 12/14 test SDK PASS. `sw/full_system` chạy SUCCESS khi bỏ qua phase 7 (HWPE) |
| GVSoC đo được gì? | Trace lệnh, trace component, VCD (2555 tín hiệu), 22 perf counter, công suất (chỉ L1), profile theo lệnh và theo hàm |
| Số đo có tin được không? | Cùng một ELF chạy trên GVSoC và RTL Questa, 29 phép đo. Code một core trên cluster khớp ±2%. Code nhiều core, DMA và barrier: GVSoC nhanh hơn 8–27%. Vòng lặp trên FC: GVSoC chậm hơn tới 1.83 lần |
| Counter nào vô dụng trên GVSoC? | `TCDM_CONT`, `LD_EXT`, `ST_EXT`, `LD_EXT_CYC`, `ST_EXT_CYC`, `JR_STALL` luôn bằng 0 |
| Đã đo `full_system` theo phase chưa? | **Chưa.** Mới chạy PASS, chưa lấy số theo phase |

## 2. Môi trường

| Thành phần | Vị trí / phiên bản |
|---|---|
| GVSoC | `~/gvsoc` @ `3b4c489`, đã build sẵn trong `~/gvsoc/install` |
| PULP SDK (PMSIS/PulpOS) | `~/pulp-sdk` @ `d4b5bcd` |
| Toolchain | `/opt/pulp-toolchain`, `riscv32-unknown-elf-gcc` 7.1.1 |
| Runtime của repo | `pulp-runtime/` (dùng cho `sw/full_system` và các chương trình chạy trên RTL) |
| RTL simulator | Questa 10.7c ở `~/questasim`, license server cục bộ cổng 27001 |

Ba trở ngại môi trường, và cách xử lý:

| Trở ngại | Triệu chứng | Cách xử lý |
|---|---|---|
| `python3` trỏ vào miniforge | `ModuleNotFoundError: No module named 'prettytable'` khi chạy `gvsoc` | Đưa `/usr/bin` lên đầu PATH (`sw/gvsoc/env.sh` làm việc này) |
| `cmake` trỏ vào Xilinx SDK 3.3.2 | `libidn.so.11: cannot open shared object file` | Cùng cách trên; `/usr/bin/cmake` là 3.28 |
| License Questa | `Unable to checkout a license` | Khởi động `lmgrd` như `run_sim.sh` vẫn làm (xem §6.5) |

## 3. Các việc đã làm, theo thứ tự

| # | Việc | Kết quả |
|---|---|---|
| 1 | Chạy thử `hello` và `cluster/fork` của SDK trên `pulp-open` | Chạy được; có trace lệnh, VCD 4.5 MB, script GTKWave |
| 2 | Build `sw/full_system` bằng `pulp-runtime`, chạy trên GVSoC | Treo ở `phase7_hwpe`: `pulp-open` không có model HWPE datamover. Bỏ phase 7 (thử trên bản copy) thì SUCCESS |
| 3 | Bước 1: chạy 14 test SDK | 12 PASS; `flash/with_ram` FAIL (model flash không hỗ trợ erase); `cluster/fork_power` bị dừng tay (VCD 22 GB) |
| 4 | Bước 2: lập danh mục trace, VCD, công suất; `target_properties`; `diagram` | 1475 đường trace, 2555 tín hiệu VCD / 112 nhóm, công suất chỉ có ở 16 bank L1; chỉ 4 tham số chỉnh được lúc chạy |
| 5 | Bước 3: microbenchmark `sw/gvsoc/ubench` (PMSIS), 6 phép thử | Hai lần chạy giống hệt nhau (tất định). Phát hiện FC fetch chậm, không có xung đột bank, 6 counter luôn 0 |
| 6 | Đọc source GVSoC để xác nhận | `l1_interleaver_impl.cpp` không có arbitration; ISS không cộng vào 6 counter trên |
| 7 | Viết lại microbenchmark bằng `pulp-runtime` (`sw/gvsoc/ubench_rt`) | Cùng một ELF chạy được trên GVSoC và RTL |
| 8 | Thêm `APP_DIR` vào `sw/full_system/run_sim.sh` | Chạy ứng dụng khác trên RTL mà không chép lại runner |
| 9 | Bước 4: chạy `ubench_rt` trên RTL Questa | `PASS (exit 0)`, 11 phút 4 giây. Bảng so sánh 29 phép đo |
| 10 | Bước 5: target biến thể `pulp-open-icache8k` và phép quét `icache_sweep` | Chạy trên 2 target GVSoC và RTL (6 phút 43 giây). Điểm gãy khi code vượt 4 KiB khớp RTL |
| 11 | Bước 2 (tiếp): `gvsoc_analyze_insn`, viết `func_profile.py` | ~90% thời gian của pe0 nằm trong `printf` |
| 12 | Thêm cờ `SKIP_HWPE` vào `sw/full_system` | `full_system` chạy SUCCESS trên GVSoC, phase 7 báo SKIP; build mặc định không đổi |
| 13 | Viết tài liệu, kết quả và báo cáo này | `doc/dungpc/master_analysis/gvsoc/gvsoc_00_plan_do_dac.md`, `report/gvsoc_20260919/` |

## 4. File đã tạo và sửa

Không file nào dưới `rtl/`, `.bender/`, `sim/` hay `~/gvsoc` bị sửa. Chưa commit.

### 4.1 File sửa (3 file, +17 / −1 dòng)

| File | Thay đổi | Ảnh hưởng tới flow cũ |
|---|---|---|
| [`sw/full_system/run_sim.sh`](../../sw/full_system/run_sim.sh) | `cd "${APP_DIR:-$ROOT/sw/full_system}"` và thêm dòng mô tả biến `APP_DIR` ở đầu file | Không. Mặc định vẫn là `sw/full_system` |
| [`sw/full_system/full_system.c`](../../sw/full_system/full_system.c) | `#ifdef DEMO_SKIP_HWPE` quanh lời gọi `phase7_hwpe()`; khi bật thì in `[PHASE 7] ... SKIP` | Không. Chỉ có tác dụng khi define |
| [`sw/full_system/Makefile`](../../sw/full_system/Makefile) | `ifdef SKIP_HWPE` → `PULP_CFLAGS += -DDEMO_SKIP_HWPE` | Không. Chỉ khi `make ... SKIP_HWPE=1` |

### 4.2 File mới trong `sw/gvsoc/`

| File | Việc |
|---|---|
| [`env.sh`](../../sw/gvsoc/env.sh) | Môi trường GVSoC + PULP SDK, sửa PATH |
| [`step1_sdk_tests.sh`](../../sw/gvsoc/step1_sdk_tests.sh) | Chạy 13 test SDK (bỏ `fork_power`), ghi `summary.txt` |
| [`step2_inventory.sh`](../../sw/gvsoc/step2_inventory.sh) | Chạy một ELF với mọi trace / VCD / `--power`, rút ra danh mục, xoá file lớn |
| [`ubench/`](../../sw/gvsoc/ubench/test.c) | Microbenchmark bằng PMSIS, chỉ chạy trên GVSoC |
| [`ubench_rt/`](../../sw/gvsoc/ubench_rt/test.c) | Cùng các phép thử viết bằng `pulp-runtime`, thêm phép 8 core đọc L2; chạy được trên GVSoC và RTL |
| [`icache_sweep/`](../../sw/gvsoc/icache_sweep/test.c) | Vòng lặp có code dài 256 B → 6 KiB, 1 core và 8 core |
| [`targets/pulp-open-icache8k.py`](../../sw/gvsoc/targets/pulp-open-icache8k.py) + `targets/pulp_open_icache8k/cluster.json` | Target biến thể: shared I-cache 8 KiB, không sửa `~/gvsoc` |
| [`analyze/func_profile.py`](../../sw/gvsoc/analyze/func_profile.py) | Cycle, số lệnh, CPI theo hàm từ trace `insn` |
| [`analyze/compare_ubench.py`](../../sw/gvsoc/analyze/compare_ubench.py) | Bảng Markdown so sánh GVSoC với RTL từ hai log |
| [`analyze/csv_table.py`](../../sw/gvsoc/analyze/csv_table.py) | In dòng `CSV` của một log (GVSoC hoặc RTL) thành bảng thẳng cột, kèm CPI |
| `*/.gitignore` | Bỏ qua thư mục build và `__pycache__` |

### 4.3 Tài liệu và kết quả

| File | Nội dung |
|---|---|
| [`doc/dungpc/master_analysis/gvsoc/gvsoc_00_plan_do_dac.md`](../../doc/dungpc/master_analysis/gvsoc/gvsoc_00_plan_do_dac.md) | Kết luận: danh mục đo, so sánh RTL, bảng mức tin cậy |
| [`report/gvsoc_20260919/`](00_README.md) | Log và dữ liệu thô của từng bước (4.8 MB) |

## 5. Kết quả chính

### 5.1 Test SDK (`step1/summary.txt`)

| Test | Kết quả | Test | Kết quả |
|---|---|---|---|
| `hello` FC / cluster | PASS / PASS | `flash/simple` | PASS |
| `cluster/call`, `cluster/fork` | PASS | `flash/with_ram` | FAIL (erase không được hỗ trợ) |
| `cluster/fork_power` | dừng tay (VCD 22 GB) | `fs/read` FC / cluster | PASS / PASS |
| `dma/1d` | PASS | `ram/simple` | PASS |
| `perf/double_buffering`, `perf/matmult` | PASS | `uart/loopback` | PASS |

### 5.2 GVSoC so với RTL, cùng ELF (`step4/compare.md`)

| Phép thử | GVSoC | RTL | GVSoC/RTL |
|---|---|---|---|
| FC: vòng ALU 1000 lần | 22003 | 12007 | **1.83** |
| FC: load-use | 7019 | 7005 | 1.00 |
| Cluster: vòng ALU | 12039 | 12092 | 1.00 |
| Cluster: load-use | 7042 | 7047 | 1.00 |
| Cluster: 256 load L2 phụ thuộc nhau | 4504 | 4516 | 1.00 (RTL ~15.0 cycle/load) |
| 8 core, khác bank TCDM | 810 | 931 | 0.87 |
| 8 core, cùng bank TCDM | 778 | 1032 | **0.75** (RTL `tcdm_cont` = 127, GVSoC = 0) |
| 8 core cùng đọc L2 | 2570 | 2686 | 0.96 |
| DMA L2→L1, 256 B / 8 KiB | 81 / 1071 | 111 / 1177 | 0.73 / 0.91 |
| 100 barrier, 8 core | 2596 | 2864 | 0.91 |

### 5.3 I-cache (`step5/`), CPI của core 0 khi 8 core cùng chạy

| Code | GVSoC 4 KiB | GVSoC 8 KiB | RTL |
|---|---|---|---|
| 256 B | 1.02 | 1.02 | 1.03 |
| 1–3 KiB | 1.22–1.26 | 1.22–1.25 | 1.01–1.02 |
| 4 KiB | 1.31 | 1.25 | 1.09 |
| 6 KiB | **2.50** | 1.26 | **2.37** |

### 5.4 Mức tin cậy

| Mức | Thông số |
|---|---|
| Khớp RTL ±2% | Số lệnh, `LD`, `ST`, `BRANCH`, `JUMP`, `RVC`, `LD_STALL`; cycle của code một core trên cluster (vòng lặp vừa 512 B); latency L2 từ cluster |
| Lệch có hệ thống | Code nhiều core (GVSoC nhanh hơn 13–25%); DMA (8–27%); barrier (~9%); code cluster 0.5–4 KiB (GVSoC chậm hơn ~20%); vòng lặp trên FC (chậm hơn tới 1.83 lần) |
| Không dùng được | `TCDM_CONT`, `LD_EXT*`, `ST_EXT*`, `JR_STALL`, `APU_CONT`; công suất ngoài L1; HWPE |

## 6. Câu lệnh để chạy lại

Tất cả lệnh chạy từ gốc repo `~/ndmoney4porche/projects/pulp`. **GVSoC/SDK và
`pulp-runtime` dùng hai môi trường khác nhau**: `env.sh` đặt `PULP_SDK_HOME` trỏ vào
`~/pulp-sdk`, còn build bằng `pulp-runtime` cần `PULP_SDK_HOME` trỏ vào
`pulp-runtime`. Nên dùng hai terminal riêng, hoặc chạy mỗi phần trong một subshell
`( ... )`.

### 6.1 Môi trường

```bash
# Terminal A: GVSoC + PULP SDK
source sw/gvsoc/env.sh

# Terminal B: build bằng pulp-runtime (cho ubench_rt, icache_sweep, full_system)
export PATH=$(echo "$PATH" | tr ':' '\n' | grep -v miniforge3 | paste -sd:)
export PULP_RISCV_GCC_TOOLCHAIN=/opt/pulp-toolchain
source pulp-runtime/configs/pulp.sh
export PULP_PROJECT_HOME=$PWD PULP_SDK_HOME=$PWD/pulp-runtime
```

### 6.2 Bước 1 và bước 2 (terminal A)

```bash
sw/gvsoc/step1_sdk_tests.sh report/gvsoc_20260919/step1      # ~1 phút
sw/gvsoc/step2_inventory.sh report/gvsoc_20260919/step2      # cần build hello trước (bước 1)

gvsoc --target=pulp-open target_properties                   # tham số chỉnh được lúc chạy
gvsoc --target=pulp-open diagram                             # sinh architecture.dot
dot -Tsvg architecture.dot -o architecture.svg

# Một test SDK kèm trace lệnh và VCD
cd ~/pulp-sdk/tests/cluster/fork
make clean all run runner_args="--trace=insn:insn.log --vcd --event=.*@all.vcd"
gtkwave BUILD/PULP/GCC_RISCV/view.gtkw
```

Không chạy `cluster/fork_power`: Makefile của test này ép `--event=.*` và sinh VCD
hàng chục GB.

### 6.3 Bước 3: microbenchmark PMSIS (terminal A)

```bash
cd sw/gvsoc/ubench && make clean all run | grep -E '^(CSV|INFO)'
```

### 6.4 Build các chương trình `pulp-runtime` (terminal B)

```bash
(cd sw/gvsoc/ubench_rt    && make clean all)
(cd sw/gvsoc/icache_sweep && make clean all)
(cd sw/full_system        && make clean all SKIP_HWPE=1)   # bản chạy được trên GVSoC
```

### 6.5 Chạy trên GVSoC (terminal A)

```bash
gvsoc --target=pulp-open --binary sw/gvsoc/ubench_rt/build/test/test run
gvsoc --target=pulp-open --binary sw/full_system/build/test/test run

# Target biến thể (shared I-cache 8 KiB)
gvsoc --target-dir=sw/gvsoc/targets --target=pulp-open-icache8k \
      --binary sw/gvsoc/icache_sweep/build/test/test run
```

Thêm `--work-dir=<thư mục>` để file sinh ra (`gvsoc_config.json`, `hyperflash.bin`
64 MB, VCD) không rơi vào thư mục hiện tại. Khi có `--work-dir`, `--binary` phải là
đường dẫn tuyệt đối (`$PWD/sw/...`); đường dẫn tương đối được tính từ thư mục làm
việc và gây lỗi `Unable to open binary`.

Hướng dẫn chạy từng bước kèm danh sách ảnh cần chụp:
[doc/dungpc/master_analysis/gvsoc/gvsoc_01_huong_dan_chay.md](../../doc/dungpc/master_analysis/gvsoc/gvsoc_01_huong_dan_chay.md).

### 6.6 Profile theo lệnh và theo hàm (terminal A)

```bash
gvsoc --target=pulp-open --binary sw/gvsoc/ubench_rt/build/test/test \
      --trace=cluster/pe0/insn:pe0.log run
sed -i 's/\x1b\[[0-9;]*m//g' pe0.log                       # bỏ mã màu
python3 -W ignore $(which gvsoc_analyze_insn) --trace pe0.log
sw/gvsoc/analyze/func_profile.py pe0.log --top 15
```

### 6.7 Chạy cùng ELF trên RTL Questa (đối chiếu)

```bash
# License server (runner cũng tự làm nếu lmgrd chưa chạy)
pgrep -x lmgrd || ~/questasim/linux_x86_64/lmgrd -c ~/questasim/LICENSE.dat \
                    -l ~/questasim/license_server.log

APP_DIR=$PWD/sw/gvsoc/ubench_rt SIM_TIMEOUT="200 ms" WALL_TIMEOUT=7200 \
    sw/full_system/run_sim.sh all run > report/gvsoc_20260919/step4/rtl.log 2>&1

# So sánh
sw/gvsoc/analyze/compare_ubench.py report/gvsoc_20260919/step4/gvsoc.log \
                                   report/gvsoc_20260919/step4/rtl.log
```

`all run` dùng ELF đã build ở §6.4. Bỏ tham số thì runner chạy `clean all run` và
build lại. Thời gian thực: `ubench_rt` 11 phút, `icache_sweep` 7 phút. Nếu phiên
terminal có thể bị đóng, chạy qua `setsid nohup ... &` để vsim không bị giết giữa
chừng.

## 7. Sự cố trong phiên

| Sự cố | Nguyên nhân | Xử lý |
|---|---|---|
| `full_system` treo, không in gì | Treo ở phase 7; stdout của GVSoC bị buffer nên mất hết khi bị kill do timeout | Dùng `--trace=.../insn` để tìm chỗ treo; thêm cờ `SKIP_HWPE` |
| `cluster/fork_power` sinh VCD 22 GB trong 4 phút | Makefile của test ép `--event=.*` | Dừng tiến trình, xoá VCD, loại test khỏi script |
| `step1_sdk_tests.sh` thoát ngay | `set -u` gặp biến chưa đặt trong `~/gvsoc/sourceme.sh` | Chỉ bật `set -u` sau khi `source` môi trường |
| Thư mục kết quả chứa `hyperflash.bin` 64 MB | GVSoC tạo file này ở mỗi work dir | Xoá sau mỗi lần chạy; `step2_inventory.sh` tự xoá |
| Lần chạy RTL đầu bị ngắt | Phiên làm việc kết thúc giữa chừng, vsim nhận SIGTERM, `lmgrd` cũng bị dừng | Khởi động lại `lmgrd`, chạy lại bằng `setsid nohup` |
| 4 lỗi `vsim-191` lúc nạp thiết kế | Có sẵn cả trong log PASS của `report/full_system_20260906/` | Vô hại, không ảnh hưởng kết quả |
| Kết luận sai về I-cache | Ban đầu tính shared I-cache của GVSoC là 2 KiB, bỏ sót `nb_l1_banks = 2` | Phép quét `icache_sweep` cho thấy dung lượng thật là 4 KiB, bằng RTL. Đã sửa tài liệu; target thử đổi tên từ `rtlcfg` thành `icache8k` |

## 8. Chưa làm

| Việc | Ghi chú |
|---|---|
| Đo `full_system` theo từng phase | Cycle, lệnh, stall theo phase; thời gian ngủ ở barrier, thời gian DMA bận. Làm được từ trace và VCD mà không sửa code |
| Đo ngoại vi (UART, SPI, flash qua uDMA), latency ngắt, timer | Cần viết thêm chương trình thử nhỏ |
| Latency các lệnh FPU | GVSoC không có FPU dùng chung, nhưng vẫn đo được latency từng lệnh |
| `--gui` | `gvsoc-gui` chưa được cài; cần `make gui` trong `~/gvsoc` (clone qua SSH) |
| Model HWPE datamover cho GVSoC | Chỉ cần nếu muốn chạy phase 7 trên GVSoC |
