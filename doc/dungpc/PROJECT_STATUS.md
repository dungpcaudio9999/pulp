# Trạng thái project PULP

## 1. Thông tin snapshot

- Ngày cập nhật: `2026-09-07` (cập nhật lần 5: giải trình lựa chọn simulator)
- Repository: `pulp` (fork `dungpcaudio9999/pulp`)
- Branch: `feature/dungpc-work`
- HEAD: `b6ae547` — bằng `origin/feature/dungpc-work`, không ahead/behind
- Baseline ban đầu: `b6ae547` (HEAD hiện tại **chính là** baseline)
- Máy làm việc: Linux (`dungpc-ThinkPad-P1-Gen-4i`), không còn là Windows/MSYS2
- Giai đoạn hiện tại: Milestone 5 hoàn thành; còn lại Milestone 6 (ZCU104) và 7 (báo cáo)
- Trạng thái tổng thể: **đang thực hiện**

> **Đính chính so với snapshot `2026-09-01`.** Bản trước ghi HEAD là `ad0c389` với các
> file tài liệu đã được commit. Commit đó **không tồn tại** trong working copy hiện tại
> (`git cat-file -t ad0c389` → *not a valid object name*). Reflog chỉ có hai entry:
> `clone` rồi `checkout` sang `feature/dungpc-work`. Đây là một bản clone mới trên máy
> Linux; toàn bộ `doc/dungpc/` hiện là **untracked**, chưa có commit nào của mình.

## 2. Tổng quan milestone

| Milestone | Nội dung | Trạng thái | Ghi chú |
|---|---|---|---|
| 0 | Baseline và branch | Hoàn thành | Branch `feature/dungpc-work` tại `b6ae547` |
| 1 | Kiến trúc và source map | Gần hoàn thành | 4 chương deep-dive + source map đã viết; chưa commit, chưa review, sơ đồ Draw.io vẫn ngoài repo |
| 2 | Dependency, toolchain và RTL build | **Hoàn thành** | Bender 0.31.0, dependency đã checkout, `vopt_tb` build sạch 0 error |
| 3 | Software toolchain và FC smoke test | **Hoàn thành** | Toolchain RISC-V có sẵn; `hello` chạy pass trên Questa |
| 4 | Cluster/offload simulation | **Hoàn thành** | `sw/full_system` 9/9 phase pass, gồm cả HWPE datamover; phép thử ngược xác nhận bắt được lỗi |
| 5 | Waveform analysis | **Hoàn thành** | VCD 4.6 MB của `full_system`; phát hiện 70% thời gian mô phỏng là nạp JTAG |
| 6 | Đánh giá/port ZCU104 | Chưa bắt đầu | Vivado đã có; XSim thất bại (mục 7), repo chỉ có `fpga/pulp-zcu102` |
| 7 | Báo cáo và bàn giao | Chưa bắt đầu | Đã có log evidence để dựng báo cáo |

## 3. Công việc đã hoàn thành

### Baseline và tài liệu

- Branch `feature/dungpc-work` tại `b6ae547`.
- Đã đọc `README.md`, `Bender.yml`, `Bender.lock`, xác định platform top `rtl/pulp/pulp.sv`,
  ba domain (`safe_domain`, `soc_domain`, `cluster_domain`), simulation top `rtl/tb/tb_pulp.sv`.
- Artifact Milestone 1 (tất cả **chưa commit**):
  - [Kiến trúc và bản đồ mã nguồn PULP](pulp_architecture_and_source_map.md)
  - [Mục lục phân tích chuyên sâu](DEEP_DIVE_INDEX.md)
  - [Platform top, pad frame và safe domain](deep_dive_01_platform_safe_domain.md)
  - [SoC domain và Fabric Controller](deep_dive_02_soc_domain.md)
  - [Cluster domain và interconnect SoC–Cluster](deep_dive_03_cluster_and_interconnect.md)
  - [Boot, JTAG và testbench](deep_dive_04_boot_debug_testbench.md)
  - [PLAN.md](PLAN.md), [plan_demo.md](plan_demo.md)
- Sơ đồ Draw.io: `/home/dungpc9/ndmoney4porche/uni/diagram/pulp_domains.drawio` — đường dẫn này
  thuộc user `dungpc9`, không phải `dungpc`; cần xác minh lại trên máy hiện tại.

### Milestone 2 — RTL build (hoàn thành `2026-09-04`)

Toàn bộ log tại [report/questa_hello_demo/20260904_010100/](../../report/questa_hello_demo/20260904_010100/).

| Bước | Log | Kết quả |
|---|---|---|
| License Questa | `01_license_status.log` | server UP (MASTER) v11.14.1, daemon `mgcld` UP |
| `make checkout` | `06_make_checkout.log` | Bender 0.31.0, dependency checkout xong |
| `make scripts` | `07_make_scripts.log`, `08_compile_script.log` | sinh `sim/compile.tcl` |
| `vlog` compile | `12_rtl_compile.log` | xong |
| `vopt` optimize | `13_rtl_optimize.log`, `15_rtl_build_result.log` | `vopt_tb`, **0 error**, 23 warning, 508 suppressed |

### Milestone 3 — FC smoke test (hoàn thành `2026-09-04`)

| Hạng mục | Giá trị |
|---|---|
| Toolchain | `riscv32-unknown-elf-gcc` 7.1.1 tại `~/ndmoney4porche/tools/v1.0.16-pulp-riscv-gcc-ubuntu-16` |
| ELF | `regression_tests/hello/build/test/test` — ELF32 RISC-V, text 1668 / data 28 / bss 2116 |
| Entry point | `0x1c008080` |
| Nạp chương trình | JTAG (`-gLOAD_L2=JTAG`), stimuli sinh bởi `stim_utils.py` |
| Kết quả | `[STDOUT-CL31_PE0] Hello !` tại 5387801 ns |
| Exit status | `Received status core: 0x00000000`, `make run exit status: 0` |
| Thời gian chạy | 22 giây wall-clock cho 5.39 ms sim-time |

Kết luận trong `21_final_result.log`: **PULP hello test passed functionally.**

### Phát hiện từ phân tích RTL (đã đối chiếu lại với dependency thật)

- `safe_domain` chủ yếu chứa `pad_control` và reset/slow-clock adaptation.
- `soc_domain.sv` / `cluster_domain.sv` là wrapper mỏng quanh `pulp_soc` / `pulp_cluster`.
- `rtl/pulp/pulp.sv` buộc `cluster_domain` với `.base_addr_i('0)` và `.fetch_en_i(1'b0)`.
  **Đây không phải bug chặn offload:** trong `pulp_cluster.sv`, `fetch_en_i` chỉ đi vào
  `cluster_peripherals_i` (dòng 762), còn fetch enable thật của core là
  `fetch_en_int = fetch_enable_reg_int` (dòng 550) — do FC ghi qua thanh ghi cluster control.
  Runtime dùng đúng đường này: `cluster_start()` gọi `plp_ctrl_core_bootaddr_set_remote()`
  rồi `eoc_fetch_enable_remote()` (`pulp-runtime/kernel/cluster.c:62-95`).
- Hai return path `dma_pe_irq_valid` và `pf_evt_valid` từ Cluster vẫn bị bỏ ở SoC integration top.
- HWPE được instantiate trong cluster là **datamover** (`USE_RBE = 0` →
  `hwpe_subsystem.sv` chọn `datamover_top`), không phải MAC engine.

## 4. Trạng thái working tree

Đã có **7 commit** trên `feature/dungpc-work` (kèm merge `ad0c389` từ máy cũ):

```
97132c6 test: add cluster bring-up and HWPE probe evidence
a8d3271 docs: record cluster bring-up evidence and resolve HWPE blocker
48b11a2 merge: hợp nhất commit ad0c389 từ máy cũ
54aa56a test: add Questa hello simulation logs as milestone evidence
5ebb58d sim: add experimental Vivado XSim flow for tb_pulp
25fa939 docs: add PULP architecture analysis, project status and demo plan
27e764e chore: ignore simulator and Vivado build artifacts
```

Đang chờ commit (kết quả Milestone 4 và 5):

| Mục | Nội dung |
|---|---|
| `sw/` | `sw/full_system/` — chương trình 9 phase, Makefile, `run_sim.sh`, `wave_capture.do`, README |
| `report/full_system_20260906/` | chuỗi chẩn đoán phase 7 và hai log kết quả |
| `report/waveform_20260906/` | dòng thời gian và phân bổ thời gian mô phỏng |
| `doc/dungpc/PROJECT_STATUS.md` | file này |
| `.gitignore` | bỏ qua `*.vcd`, `*.vcd.gz`, `*.wlf` |

Patch `const ref` trên `rtl/tb/{dbg,jtag,pulp_tap}_pkg.sv` đã được commit tại `5ebb58d`,
kèm bằng chứng nó vô hại với Questa. Các file rác ở thư mục gốc đã dọn tại `27e764e`.

## 5. Trạng thái dependency

Đã checkout tại `.bender/git/checkouts/`. Các dependency liên quan trực tiếp tới Milestone 4:

| Dependency | Checkout |
|---|---|
| `pulp_cluster` | `pulp_cluster-48721e3ce381c984` |
| `hwpe-datamover-example` | `hwpe-datamover-example-a9b2d6689c13b9f9` |
| `hwpe-ctrl` | `hwpe-ctrl-aaea72c1bd54a7f4` |
| `hwpe-mac-engine` | `hwpe-mac-engine-51b68cfc401cd47c` (có mặt nhưng **không** được instantiate) |
| `cv32e40p` | `cv32e40p-0a3884e05ea5a482` |

Ghi chú cũ về việc `Bender.yml` và `Bender.lock` lệch revision `pulp_cluster` không còn là
blocker: `make checkout` đã chạy được và `vopt_tb` build sạch.

## 6. Trạng thái toolchain

| Tool | Trạng thái |
|---|---|
| `vsim`/`vlog`/`vopt` | Questa **10.7c**, license server UP |
| `riscv32-unknown-elf-gcc` | 7.1.1 (PULP GCC v1.0.16, Ubuntu 16 build) |
| `bender` | 0.31.0 (`./bender` trong repo) |
| `make`, `python3` | Có |
| `vivado` | Có — nhưng XSim không dùng được, xem mục 7 |

## 7. Build và simulation status

| Hạng mục | Trạng thái |
|---|---|
| Dependency checkout | **Xong** |
| `make scripts` / `sim/compile.tcl` | **Xong** |
| RTL compile + `vopt_tb` | **Xong**, 0 error |
| FC software build (`hello`) | **Xong** |
| FC simulation trên Questa | **Pass** |
| Cluster simulation | **Pass** — `mchan` status `0x00000000`; 8 core in ra `CL0_PE0..PE7` |
| Waveform | **Có** — 16 tín hiệu, 18.27 ms, kèm dòng thời gian sự kiện |
| Vivado XSim | **Thất bại** |
| ZCU104 synthesis | Chưa chạy |

### Milestone 4 — `sw/full_system` `2026-09-06`

Nguồn tại [sw/full_system/](../../sw/full_system/), log tại
[report/full_system_20260906/](../../report/full_system_20260906/).

Chương trình C duy nhất chạy hai lần: trên FC rồi trên cả 8 core cluster.

| Lượt | Kết quả |
|---|---|
| Sạch | **SUCCESS**, 9/9 phase OK, status `0x00000000`, log đủ `CL0_PE0`..`CL0_PE7` |
| `INJECT_FAULT=1` | **FAIL** đúng như mong đợi, status `0x00000001` |

Cả 9 khối đều được đánh thức và tự kiểm chứng: FC/L2/SoC interconnect, APB timer,
PMU và cluster clock/reset, 8 core cluster với event unit và barrier, TCDM, MCHAN DMA,
**HWPE datamover**, GPIO và safe domain padmux.

#### Phát hiện kỹ thuật: băng thông HWPE thật là 12 byte

Cả hai nguồn "chính thống" đều cho số **sai**: `test_datamover.c` của dependency hardcode
`DATAMOVER_BW = 256/8 = 32`, còn suy từ RTL (`N_MASTER_PORT = NB_HWPE_PORTS = 9` →
`BW = 9*32` bit = 36 byte) cũng sai. Thực đo là **12 byte = 96 bit** mỗi nhịp.

Cách đo: đặt `D0_STRIDE` khác nhau rồi nhìn mẫu word bị bỏ sót. Stride 32 byte cho word
đúng ở 0,1,2 / 8,9,10; stride 36 byte cho 0,1,2 / 9,10,11. Chu kỳ đi theo stride nhưng số
word đúng mỗi chu kỳ luôn là 3 — tách bạch được stride (phần mềm đặt) khỏi payload
(phần cứng cố định).

#### Hai lỗi im lặng đã bị bắt

1. **Cluster không chạy mà vẫn báo SUCCESS.** `cluster_start()` return im lặng khi
   `pi_l1_malloc` cấp stack thất bại, `cluster_wait()` trả về 0 — không phân biệt được với
   thành công. Xảy ra thật vì `CLUSTER_STACK_SIZE=0x2000` khiến 8 × 8 KB = đúng 64 KB,
   vượt L1. Đã thêm sentinel `demo_cl_ran` để phase 3 kiểm chứng thay vì tin giá trị trả về.
2. **Lỗi ở core khác 0 bị nuốt mất.** Runtime chỉ giữ giá trị trả về của core 0. Phép thử
   ngược tiêm lỗi vào core 3 xác nhận cơ chế gom lỗi qua mutex hoạt động: core **2** phát
   hiện và lỗi tới được exit status.

### Bước 0 cluster — `2026-09-06`

Log đầy đủ tại [report/cluster_buoc0_20260906/](../../report/cluster_buoc0_20260906/).

| Bài test | Kết quả | Status core |
|---|---|---|
| `mchan_tests/testMCHAN_TCDM2TCDM_tx_rx` | **PASS** | `0x00000000` |
| `parallel_bare_tests/multicore` | FAIL (lỗi của test, không phải cluster) | `0x00000025` |

**Kết luận: cluster hoạt động.** Bằng chứng quyết định là dải `[STDOUT-CL0_PE0]` đến
`[STDOUT-CL0_PE7]` — bài `hello` trước đó chỉ có `CL31`, tức FC. Được chứng minh: PMU và
cluster clock/reset, AXI SoC↔Cluster, 8 core cùng chạy, event unit và barrier, TCDM,
MCHAN DMA ổn định qua mọi kích thước truyền.

`multicore` FAIL vì `nbPe` và `stackSize` trong Makefile của nó là biến SDK cũ mà
pulp-runtime bỏ qua; runtime hardcode 8 core và stack 2 KB, nên bài sudoku đệ quy tràn
stack sang vùng L1 kề bên.

### Phase 7 / HWPE — đã gỡ được

`tb_pulp.sv:48` đặt `USE_HWPE_CL = 0` nên mặc định HWPE không được instantiate. Đã kiểm
chứng rằng **truyền `-gUSE_HWPE_CL=1` lúc `vsim` là đủ**, không cần sửa testbench cũng
không cần `make build` lại — bước vopt dùng `-floatparameters+tb_pulp` nên tham số vẫn
override được lúc runtime. Engine sinh ra là `datamover_top`, khớp `hal_datamover.h`.
Chi tiết ở [report/cluster_buoc0_20260906/07_hwpe_conclusion.md](../../report/cluster_buoc0_20260906/07_hwpe_conclusion.md).

### Milestone 5 — waveform `2026-09-06`

Thu bằng [sw/full_system/wave_capture.do](../../sw/full_system/wave_capture.do), phân tích
tại [report/waveform_20260906/](../../report/waveform_20260906/).

| Giai đoạn | Dài (ms) | % |
|---|---:|---:|
| Reset và khởi tạo | 0.052 | 0.3% |
| **Nạp chương trình qua JTAG** | **12.792** | **70.0%** |
| FC thực thi (phase 0–2 + khởi động cluster) | 4.100 | 22.4% |
| Cluster thực thi (phase 4–7) | 1.326 | 7.3% |

**Phát hiện chính: 70% thời gian mô phỏng là nạp chương trình, không phải chạy nó.**
Đổi sang `-gLOAD_L2=STANDALONE` sẽ cắt phần lớn 12.8 ms này — đáng làm cho vòng lặp
debug, nhưng nên giữ ít nhất một lần chạy `LOAD_L2=JTAG` để bảo chứng đường nạp.

VCD 4.6 MB không commit (tái tạo được, đã thêm vào `.gitignore`).

### Bốn cạm bẫy môi trường đã vấp phải và cách xử lý

| Thiếu gì | Triệu chứng | Xử lý |
|---|---|---|
| `lmgrd` chưa chạy | `Fatal: Invalid license environment` | Giai đoạn 1 nhật ký |
| `LD_LIBRARY_PATH` | `cc1: libmpfr.so.4 not found` | trỏ vào `compat-libs` của toolchain |
| Conda che python hệ thống | `ModuleNotFoundError: elftools` | rời conda; chỉ `/usr/bin/python3` có `pyelftools` |
| Chưa `source configs/pulp.sh` | `No rule to make target 'clean'` | **thiếu trong Phụ lục B nhật ký**, đã bổ sung |

Cái cuối nguy hiểm nhất: `rules/pulp.mk` dùng `-include` nên make **im lặng** không nạp
target nào, thông báo lỗi không gợi ý gì về biến môi trường.

### Vivado XSim — thất bại (`2026-09-03`, chạy lại `2026-09-06`)

> Lý do đầy đủ của quyết định "Questa để mô phỏng, Vivado để sinh bitstream" nằm ở
> [lua-chon-simulator.md](lua-chon-simulator.md), kèm bằng chứng rằng ZCU102 và VCU118
> cũng **chưa bao giờ** dùng Vivado để mô phỏng.

Flow thử nghiệm nằm ở [sim/xsim/](../../sim/xsim/) và [xsim/](../../xsim/) (filelist, patch
`const ref`, `dpi_stub.c` cho `jtag_tick`, script `run_hello_xsim.tcl`). Vivado **v2019.1**.

Hai lần chạy cho **hai lỗi khác nhau**:

| Lần | Lỗi | Ghi chú |
|---|---|---|
| `2026-09-03` | `[XSIM 43-4177] This design requires more memory than the host operating system can support` | dừng sau `Completed simulation data flow analysis`; `free physical = 1130 MB` |
| `2026-09-06` | `[XSIM 43-3254] ... fpnew_pkg.sv, line 302. Could not find hier sig handle for expression : FP_ENCODINGS[fmt].exp_bits` + `[XSIM 43-3915] fatal error` | elaborate dừng sau 10 s; `free physical = 951 MB` — **không** còn lỗi 43-4177 |

Kết luận: **lỗi bộ nhớ không phải nguyên nhân gốc.** Lần chạy lại có ít RAM trống hơn
(951 MB so với 1130 MB) nhưng lại không gặp 43-4177 nữa, mà lộ ra một giới hạn ngôn ngữ thật sự:

```systemverilog
// fpnew_pkg.sv:302 — XSim 2019.1 không phân giải được
function automatic int unsigned fp_width(fp_format_e fmt);
  return FP_ENCODINGS[fmt].exp_bits + FP_ENCODINGS[fmt].man_bits + 1;
endfunction
```

Truy cập trường của struct trong mảng hằng, bên trong hàm được gọi lúc elaborate để tính tham số —
`xelab` của Vivado 2019.1 không xử lý được. Đây là lỗi **fatal**, không bỏ qua được bằng switch.

Ghi chú thêm: `ulimit -v` và `ulimit -m` đều `unlimited`, nên giới hạn tài nguyên shell đã bị loại
trừ. Log còn có `WARNING: [filemgmt 56-315] Source scanning failed during design analysis`, nghĩa
là Vivado không tự xác định được compile order — có thể là lý do hai lần chạy hỏng ở hai chỗ khác nhau.

### Chuỗi thí nghiệm `2026-09-06` — đã bóc được ba lớp lỗi

| Lần | Cấu hình | Kết quả | Elaborate |
|---|---|---|---|
| 1 | nguyên trạng | `43-4177` hết bộ nhớ | 8 s |
| 2 | nguyên trạng (chạy lại) | `43-3254` `fpnew_pkg.sv:302` | 10 s |
| 3 | tắt FPU (`RISCY_FPU=0`, `CLUST_FPU 0`) | `43-3254` **y nguyên** | 9 s |
| 4 | patch `fpnew_pkg` | `43-3209` + `43-3316 SIGSEGV` tại `fpnew_opgroup_multifmt_slice.sv:301` | **1437 s** |
| 5 | patch + tắt FPU | **`43-4177` hết bộ nhớ** | 8 s |

Ba lớp lỗi đã được xác định và xử lý xong hai:

1. **`43-3254` — package `fpnew_pkg`.** `xelab` không phân giải được truy cập trường trên
   phần tử mảng hằng (`FP_ENCODINGS[fmt].exp_bits`). Không tắt được bằng tham số vì
   `cv32e40p/rtl/include/riscv_defines.sv:392-394` tham chiếu `fpnew_pkg::` **vô điều kiện**
   ở mức parameter, nên package luôn phải compile. ✅ **Đã xử lý** bằng
   `xsim/patches/0002-fpnew_pkg-xsim-const-array-field-access.patch` (4 chỗ, gán struct ra
   biến trung gian). Tái áp dụng bằng `xsim/patches/apply_xsim_patches.sh` sau mỗi `bender checkout`.
2. **`43-3209` + SIGSEGV — module `fpnew_opgroup_multifmt_slice.sv:301.`** Assignment pattern
   trong toán tử ba ngôi (`... ? op_result : '{default: lane_ext_bit[0]}`); XSim 2019.1 từ chối
   rồi crash chính `xelab`. ✅ **Đã né** bằng cách tắt FPU — module chỉ elaborate khi được
   instantiate, khác với package. Đánh đổi: **bản XSim không có FPU**, là cấu hình khác bản Questa.
3. **`43-4177` — hết bộ nhớ.** ⬅ **Rào cản còn lại duy nhất.** Chưa từng được kiểm chứng
   trong điều kiện đủ RAM: cả năm lần chạy đều có `free physical` quanh 1 GB (951 / 989 /
   1130 / 1169 / 1255 MB) vì máy đang chạy Vivado GUI, Firefox và nhiều cửa sổ VS Code.
   `ulimit -v` và `-m` đều `unlimited` nên đã loại trừ giới hạn shell.

Phép thử quyết định còn lại — cần thao tác của người dùng vì `sudo` đòi mật khẩu:

```bash
# đóng Vivado GUI, Firefox, bớt cửa sổ VS Code
sync && sudo sysctl -w vm.drop_caches=3
free -h        # cần thấy cột "free" > 20 GB, không phải "available"
vivado -mode batch -source sim/xsim/run_hello_xsim_nofpu.tcl
```

Nếu vẫn `43-4177` với 20+ GB trống thật thì đó là giới hạn thật của XSim 2019.1 với thiết kế
cỡ này, và Questa là lựa chọn duy nhất.

**Trạng thái file đang để dở:** `rtl/includes/pulp_soc_defines.sv` hiện đang bị sửa
(`CLUST_FPU 0`, `CLUST_FP_DIVSQRT 0`) để phục vụ phép thử trên; bản gốc ở
`pulp_soc_defines.sv.before_nofpu_experiment`. Khôi phục khi quay lại dùng Questa.

**Lỗi này không chặn hạng mục A.** Synthesis dùng engine khác `xelab`; flow
`fpga/pulp-zcu102` là flow chính thức upstream và vẫn tạo được bitstream. Mô phỏng hành vi
`tb_pulp` trên XSim không nằm trên đường tới ZCU104.

## 8. Vấn đề còn tồn

### Chặn Milestone 4

Không có blocker về hạ tầng. Việc còn lại là viết chương trình test — đã có kế hoạch tại
[plan_demo.md](plan_demo.md).

### Chặn Milestone 5

`sim/waves/wave_hello.vcd` chỉ 118 byte. Cần bật dump waveform đúng cách trong `run.tcl`
trước khi có gì để phân tích.

### Chặn Milestone 6

- Repo chỉ có `fpga/pulp-zcu102`, chưa có target ZCU104.
- Bản FPGA đặt `USE_HWPE = 0` và `USE_HWPE_CL = 0` (`xilinx_pulp.v:93,127-128`) — HWPE
  không tồn tại trên board.
- Toàn bộ LED trong `zcu102.xdc` đang bị comment.

### Nhiễu chưa lý giải (không chặn)

- 4 lỗi `** Error: (vsim-191) Questa has encountered an unexpected internal error:
  ../../src/vsim/vsimfunc.c(1989)` — internal error của Questa 10.7c, test vẫn pass.
- `** Warning: (vsim-3770) Failed to find user specified function 'jtag_tick' in DPI
  C/C++ source files` — remote-bitbang DPI chưa build; không cần cho luồng LOAD_L2=JTAG.
- `vsim-3040`: generic `USE_SDVT_I2S` / `USE_SDVT_SPI` truyền vào nhưng không có trong design.

## 9. Next actions theo thứ tự

Milestone 0–5 đã xong. Còn lại:

1. **Commit kết quả Milestone 4 và 5** (danh sách ở mục 4).
2. **Đóng Milestone 1** — việc duy nhất còn thiếu là review tài liệu và quyết định số phận
   sơ đồ `pulp_domains.drawio`; xem mục 11.
3. **Dọn đĩa trước khi bắt đầu Milestone 6.** Còn 36 GB trên `/home` (đã dùng 89%). Một
   lượt synthesis + implementation cho ZU7EV thường ngốn 20–40 GB thư mục `.runs`; thiếu
   chỗ sẽ hỏng sau vài giờ chạy.
4. **Milestone 6 — dựng target ZCU104.** Vivado 2019.1 đã có sẵn part `xczu7ev*` (27 part)
   và board file ZCU104 (2 mục), nên không vướng công cụ. Việc thật:
   - tạo `fpga/pulp-zcu104/fpga-settings.mk` (đổi `XILINX_PART`, `XILINX_BOARD`);
   - viết lại `constraints/zcu104.xdc` — pinout ZCU104 khác ZCU102 hoàn toàn;
   - dùng lại `rtl/xilinx_pulp.v` gần như nguyên vẹn;
   - thêm target `zcu104` vào `fpga/Makefile` song song với `zcu102` và `vcu118`.

   Lưu ý repo **chưa từng chạy synthesis lần nào** — toàn bộ lịch sử Vivado ở đây là mô
   phỏng XSim (xem mục 7).
5. **Milestone 7 — báo cáo và bàn giao.** Đã có đủ evidence trong `report/`.

### Việc tùy chọn, chi phí thấp

- Đổi sang `-gLOAD_L2=STANDALONE` cho vòng lặp debug: cắt được ~70% thời gian mô phỏng
  (xem Milestone 5). Giữ ít nhất một lần chạy `LOAD_L2=JTAG` để bảo chứng đường nạp.
- Mở rộng `wave_capture.do` thu thêm nhóm `pad_*` để xác minh tín hiệu GPIO ra chân thật —
  hiện phase 8 mới chỉ chứng minh ghi/đọc lại được thanh ghi `PADOUT`.
- Nhánh Vivado XSim đang dừng ở lỗi bộ nhớ `43-4177` chưa được kiểm chứng trong điều kiện
  đủ RAM (xem mục 7). Không chặn gì, chỉ là câu hỏi bỏ ngỏ.

## 10. Ranh giới build và mô phỏng

- **Milestone 2** — hạ tầng mô phỏng: checkout, sinh compile script, compile và elaborate
  `tb_pulp` thành `vopt_tb`. ✅
- **Milestone 3** — mô phỏng chức năng đầu tiên: build ELF cho FC, nạp qua JTAG, kiểm tra
  stdout và exit status. ✅
- **Milestone 4** — mô phỏng Cluster và luồng FC→Cluster.
- **Milestone 5** — thu và phân tích waveform.

## 11. Tiêu chí đóng Milestone 1

Ba trong bốn điều kiện đã đạt: file SoC/Cluster thật đã được xác minh sau dependency
checkout, tài liệu đã được commit (`25fa939`, `a8d3271`), và snapshot này được cập nhật
liên tục. Còn thiếu:

- tài liệu được **review**;
- quyết định có đưa sơ đồ `pulp_domains.drawio` vào Git hay không — đường dẫn ghi trong
  mục 3 thuộc user `dungpc9`, không phải `dungpc`, nên cần xác minh lại trên máy hiện tại.

## 12. Cách cập nhật file status

Mỗi lần cập nhật cần thay đổi tối thiểu: ngày snapshot; trạng thái milestone; artifact hoặc
kết quả mới; blocker phát sinh/đã giải quyết; next actions; commit/HEAD mới nếu đã commit.
