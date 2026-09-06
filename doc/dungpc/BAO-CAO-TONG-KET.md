# Báo cáo tổng kết: mô phỏng RTL PULP và đánh giá ZCU104

Ngày: `2026-09-07` · Milestone 7 · Branch `feature/dungpc-work`

---

## 1. Tóm tắt

| Mục tiêu | Kết quả |
|---|---|
| Dựng được môi trường mô phỏng RTL PULP | ✅ QuestaSim 10.7c, `vopt_tb` build sạch 0 error |
| Chạy được phần mềm trên mô hình RTL | ✅ `hello` pass, rồi `sw/full_system` 9/9 phase pass |
| Đánh thức và kiểm chứng mọi khối chính | ✅ FC, L2, timer, PMU, 8 core cluster, TCDM, DMA, HWPE, GPIO |
| Thu và phân tích waveform | ✅ VCD 16 tín hiệu, dòng thời gian, phân bổ thời gian |
| Đánh giá khả năng chuyển sang ZCU104 | ✅ gap analysis đầy đủ, đối chiếu UG1267 |

Bằng chứng quyết định cho việc cluster thật sự hoạt động: log chứa đủ `[STDOUT-CL0_PE0]`
đến `[STDOUT-CL0_PE7]`, trong khi bài `hello` ban đầu chỉ có `CL31` — vốn là Fabric
Controller chứ không phải cluster.

---

## 2. Baseline và dependency

| Hạng mục | Giá trị |
|---|---|
| Repository | fork của `pulp-platform/pulp` |
| Baseline | `b6ae547` — *Merge pull request #72 from pulp-platform/fix_cluster_alias* |
| Nhánh làm việc | `feature/dungpc-work` |

Revision dependency, **đã đối chiếu `Bender.lock` với checkout thực tế và trùng khớp**:

| Dependency | Revision | Version |
|---|---|---|
| `pulp_soc` | `d878151e0e40` | 3.0.1 |
| `pulp_cluster` | `040fc3e3b2db` | — |
| `cv32e40p` | `8d58109ab61e` | — |
| `ibex` | `95b85ddd1c99` | — |
| `fpnew` | `8dc44406b1cc` | 0.6.6 |
| `hwpe-datamover-example` | `47e7fe8a3833` | 1.0.1 |
| `common_cells` | `b5ec8905ed78` | 1.24.0 |
| `axi` | `527cf64a95f7` | 0.29.2 |

Hai repository tách rời, clone riêng chứ không phải submodule:

| Repo | Version |
|---|---|
| `pulp-runtime` | `v0.0.15` |
| `regression_tests` | `v2.0.0-7-g7343d39` |

---

## 3. Môi trường và phiên bản công cụ

| Công cụ | Phiên bản | Vai trò |
|---|---|---|
| QuestaSim | `10.7c` (2018.08) | **mô phỏng RTL** |
| Vivado | `2019.1` | **chỉ synthesis/bitstream** — xem [lua-chon-simulator.md](lua-chon-simulator.md) |
| Bender | `0.31.0` | quản lý dependency |
| PULP RISC-V GCC | `7.1.1` (v1.0.16, bản Ubuntu 16) | biên dịch phần mềm |
| Hệ điều hành | Linux, kernel 7.0.0-30-generic | |

### Bốn thứ dễ thiếu trong môi trường

Quy trình `make run` **sẽ hỏng** nếu thiếu bất kỳ mục nào dưới đây, và ba trong bốn cho
thông báo lỗi không gợi ý nguyên nhân:

| Thiếu | Triệu chứng | Xử lý |
|---|---|---|
| `lmgrd` chưa chạy | `Fatal: Invalid license environment` | khởi động license server, xem nhật ký Giai đoạn 1 |
| `LD_LIBRARY_PATH` | `cc1: libmpfr.so.4: cannot open shared object file` | trỏ vào `compat-libs` đi kèm toolchain |
| Conda che python hệ thống | `ModuleNotFoundError: No module named 'elftools'` | rời conda; chỉ `/usr/bin/python3` có `pyelftools` |
| Chưa `source pulp-runtime/configs/pulp.sh` | `No rule to make target 'clean'` | đặt `PULPRT_HOME`/`PULPRT_TARGET` |

Mục cuối nguy hiểm nhất: `pulp-runtime/rules/pulp.mk` dùng `-include`, nên make **im lặng**
không nạp target nào và thông báo lỗi không hề nhắc tới biến môi trường.

Script `sw/full_system/run_sim.sh` đã gói sẵn cả bốn.

---

## 4. Kiến trúc và bản đồ mã nguồn

Chi tiết ở các tài liệu riêng:

| Tài liệu | Nội dung |
|---|---|
| [pulp_architecture_and_source_map.md](pulp_architecture_and_source_map.md) | bản đồ mã nguồn toàn platform |
| [DEEP_DIVE_INDEX.md](DEEP_DIVE_INDEX.md) | mục lục 4 chương phân tích RTL |
| [deep_dive_01..04](DEEP_DIVE_INDEX.md) | safe domain, SoC domain, cluster/interconnect, boot/JTAG/testbench |

Cây khối đã kiểm chứng:

```text
tb_pulp (chỉ dùng cho mô phỏng)
└── i_dut: pulp
    ├── pad_frame_i, safe_domain_i
    ├── soc_domain_i → pulp_soc          [dependency]
    └── cluster_domain_i → pulp_cluster  [dependency]
```

### Một kết luận ban đầu đã được đính chính

Bản phân tích đầu tiên nhận xét rằng `pulp.sv` buộc `.fetch_en_i(1'b0)` cho
`cluster_domain` nên "không kết luận được cluster có fetch hay không". Quan sát về wiring
là **đúng**, nhưng suy luận rút ra thì **sai**: điều đó không chặn cluster khởi chạy.

Trong `pulp_cluster.sv`, `fetch_en_i` chỉ đi vào `cluster_peripherals_i` (dòng 762); fetch
enable thật của core là `fetch_en_int = fetch_enable_reg_int` (dòng 550) — một thanh ghi
do FC ghi qua AXI. Runtime dùng đúng đường đó: `cluster_start()` gọi
`plp_ctrl_core_bootaddr_set_remote()` rồi `eoc_fetch_enable_remote()`
(`pulp-runtime/kernel/cluster.c:62-95`). Mô phỏng xác nhận: cả 8 core chạy và in ra.

---

## 5. Quy trình tái lập từ checkout sạch

```bash
# 1. Lấy mã nguồn và dependency
git clone <fork-url> pulp && cd pulp
git checkout feature/dungpc-work
make checkout                # tải bender, checkout dependency, sinh sim/compile.tcl
make pulp-runtime            # clone pulp-runtime v0.0.15
./update-regression-tests    # clone regression_tests v2.0.0

# 2. Môi trường (xem chi tiết ở nhật ký, Phụ lục B)
#    Hoặc dùng luôn sw/full_system/run_sim.sh vốn đã gói sẵn.

# 3. Build RTL
source setup/vsim.sh
ulimit -n 4096

#    KHONG chay 'make build' o goc tren checkout sach: no goi 'make -C sim all'
#    = clean + lib + build + opt, ma 'clean' xoa modelsim.ini (sim/Makefile:74)
#    con 'lib' ngay sau do lai 'chmod +w modelsim.ini' (dong 57) -> hong.
#    Trinh tu da kiem chung:
cd sim
make clean
vmap -c                      # tao modelsim.ini; PHAI dung sau 'clean'
make lib
make build                   # vlog toan bo RTL
make opt                     # vopt -> sim/work/vopt_tb
cd ..

#    Tu lan build thu hai tro di, khi modelsim.ini da ton tai:
#    'make build' o thu muc goc dung duoc binh thuong.

# 3b. Thu vien DPI cho JTAG (chi can mot lan)
make -C rtl/tb/remote_bitbang clean
make -C rtl/tb/remote_bitbang all CFLAGS="-Wall -O2 -g -fcommon"
#    '-fcommon' bat buoc voi GCC moi: ma C cu dinh nghia bien toan cuc trong header

# 4. Chạy chương trình demo
cd sw/full_system
./run_sim.sh                          # lượt sạch, kỳ vọng SUCCESS
./run_sim.sh clean all run INJECT_FAULT=1   # phép thử ngược, kỳ vọng FAIL
```

Chỉ dành cho XSim (không bắt buộc):

```bash
bash xsim/patches/apply_xsim_patches.sh   # áp lại patch fpnew sau mỗi 'make checkout'
bash xsim/patches/toggle_fpu.sh off
```

Tiêu chí pass của `full_system`:

1. đủ 9 dòng `[PHASE n] ... OK`;
2. log có `[STDOUT-CL0_PE0]` đến `CL0_PE7`;
3. `==== FULL-SYSTEM SUMMARY: SUCCESS`;
4. `[TB] ... Received status core: 0x00000000`.

---

## 6. Kết quả và bằng chứng

Toàn bộ log thô nằm trong `report/` (70 file, 4 thư mục).

| Hạng mục | Kết quả | Bằng chứng |
|---|---|---|
| RTL compile + optimize | 0 error, 23 warning | [report/questa_hello_demo/](../../report/questa_hello_demo/) |
| `hello` (chỉ FC) | pass, status `0x00000000` | cùng thư mục |
| Cluster bring-up | `mchan` pass; 8 core in ra | [report/cluster_buoc0_20260906/](../../report/cluster_buoc0_20260906/) |
| `full_system` lượt sạch | **9/9 phase**, status `0x00000000` | [report/full_system_20260906/](../../report/full_system_20260906/) |
| `full_system` tiêm lỗi | FAIL đúng, status `0x00000001` | cùng thư mục |
| Waveform | VCD 4.6 MB, 16 tín hiệu, 18.27 ms | [report/waveform_20260906/](../../report/waveform_20260906/) |

### Chín phase và khối tương ứng

| # | Khối được đánh thức | Chạy ở |
|---|---|---|
| 0 | FC, L2, đường stdout | FC |
| 1 | FC core, L2, SoC interconnect (checksum) | FC |
| 2 | APB timer, FC clock | FC |
| 3 | PMU, cluster clock/reset, AXI SoC→CL | FC |
| 4 | 8 core cluster, event unit, barrier | 8 core |
| 5 | TCDM và interconnect | 8 core |
| 6 | MCHAN DMA, AXI hai chiều | core 0 |
| 7 | HWPE datamover | core 0 |
| 8 | GPIO, safe domain padmux | FC |

### Phân tích waveform

| Giai đoạn | Dài (ms) | % |
|---|---:|---:|
| Reset và khởi tạo | 0.052 | 0.3% |
| **Nạp chương trình qua JTAG** | **12.792** | **70.0%** |
| FC thực thi | 4.100 | 22.4% |
| Cluster thực thi | 1.326 | 7.3% |

**70% thời gian mô phỏng là nạp chương trình, không phải chạy nó.** Đổi sang
`-gLOAD_L2=STANDALONE` sẽ cắt phần lớn 12.8 ms — đáng làm cho vòng lặp debug, nhưng nên
giữ ít nhất một lần chạy `LOAD_L2=JTAG` để bảo chứng đường nạp.

---

## 7. Lỗi đã gặp và cách xử lý

Phần này là giá trị lớn nhất cho người tiếp nhận. Điểm chung của hầu hết: **chúng không
báo lỗi rõ ràng** mà im lặng hoặc báo lạc hướng.

### 7.1 Lỗi im lặng — nguy hiểm nhất

| Vấn đề | Biểu hiện | Xử lý |
|---|---|---|
| **Cluster không chạy mà báo SUCCESS** | `cluster_start()` return im lặng khi `pi_l1_malloc` cấp stack thất bại; `cluster_wait()` trả về 0 — không phân biệt được với thành công. Xảy ra thật khi đặt `CLUSTER_STACK_SIZE=0x2000` (8 × 8 KB = đúng 64 KB L1) | sentinel `demo_cl_ran` ở L2; phase 3 kiểm tra thay vì tin giá trị trả về |
| **Lỗi ở core khác 0 bị nuốt** | Runtime chỉ giữ giá trị trả về của core 0 | gom lỗi vào biến L1 dùng chung, bảo vệ bằng mutex của event unit |
| **Tràn stack cluster** | Không crash, chỉ âm thầm hỏng dữ liệu L1 kề bên. Bài `parallel_bare_tests/multicore` FAIL vì lý do này | stack mặc định chỉ 2 KB; `nbPe`/`stackSize` trong Makefile test cũ **bị runtime bỏ qua hoàn toàn** |
| **HWPE không được instantiate** | `tb_pulp.sv:42,48` đặt `USE_HWPE = 0`, ghi đè mặc định `1` của `pulp.sv` | truyền `-gUSE_HWPE_CL=1` lúc `vsim`; không cần sửa testbench nhờ `-floatparameters+tb_pulp` |

### 7.2 Thông báo lỗi lạc hướng

| Thông báo | Nguyên nhân thật |
|---|---|
| `No rule to make target 'clean'` | thiếu `PULPRT_HOME`/`PULPRT_TARGET`; `rules/pulp.mk` dùng `-include` nên im lặng |
| `archi/chips/PULP_CHIP_STR/pulp.h: No such file` | ghi đè `PULP_CFLAGS` trên dòng lệnh make, xoá mất define do rule thêm bằng `+=` |
| `undefined reference to hal_gpio_paddir_set` | toàn bộ HAL GPIO nằm trong `#if 0` (`hal/gpio/gpio_v3.h:35-99`) |
| `too few arguments to function` | `L2_DATA`/`L1_DATA` của runtime là **macro đặt section**, không phải tên biến — đặt trùng tên làm hỏng mọi biểu thức chứa nó |

### 7.3 Tài liệu và tham chiếu sai

| Nguồn | Sai ở đâu | Cách phát hiện |
|---|---|---|
| `test_datamover.c` của dependency | `DATAMOVER_BW = 256/8 = 32` — sai với cấu hình này | đo thực nghiệm: **12 byte** |
| Suy từ RTL `NB_HWPE_PORTS = 9` | cho ra 36 byte — cũng sai | đổi `D0_STRIDE` và quan sát: chu kỳ đi theo stride, payload mỗi nhịp cố định 3 word |
| Target ZCU104 của PULPissimo | `ref_clk` ở `F23`/`E23` — bank 28, UG1267 ghi *"UART2 only (mostly NC pins)"* | đối chiếu UG1267; chân đúng là `H11`/`G11` |
| Board file Vivado | chỉ phơi ra tập con chân — `H11`, `G8`, `F23` đều không có | phải đọc UG1267 |

Bài học chung: **cả tài liệu của dependency lẫn target có sẵn của người khác đều không
thay thế được tài liệu board và phép đo thực tế.**

### 7.4 Nhiễu đã biết, không phải hồi quy

- 4 lỗi `vsim-191` (internal error của Questa 10.7c) xuất hiện cả ở bài `hello` vốn pass;
- warning `vsim-3770` về `jtag_tick` khi không nạp `librbs.so`;
- `vsim-3040`: generic `USE_SDVT_*` truyền vào nhưng không có trong design.

---

## 8. Kết luận về ZCU104

Chi tiết đầy đủ: [zcu102-to-zcu104-gap.md](zcu102-to-zcu104-gap.md).

### Sẵn sàng

- Vivado 2019.1 có sẵn part `xczu7ev-ffvc1156-2-e` và board file ZCU104;
- toàn bộ chân đã xác định và đối chiếu UG1267 (mục 2 của tài liệu gap);
- reference clock **cùng tần số 125 MHz** với ZCU102, nên IP Clocking Wizard dùng chung
  **không phải sửa**;
- có sẵn cấu hình OpenOCD cho ZCU104 (Digilent HS1, Olimex) dùng lại được.

### Chưa sẵn sàng

| Việc | Ghi chú |
|---|---|
| ~44 cổng ngoại vi FMC | `xilinx_pulp.v` có 54 cổng, chỉ 10 là lõi. Cổng không ràng buộc sẽ làm implementation lỗi. Khuyến nghị làm top rút gọn |
| Chưa từng chạy synthesis | Toàn bộ lịch sử Vivado của repo là mô phỏng XSim. Nên dừng ở `synth_design` ở lần đầu |
| Dung lượng đĩa | `/home` còn 36 GB (89% đã dùng); một lượt ZU7EV thường chiếm 20–40 GB |
| JTAG vật lý | Không dùng được cổng micro-USB J164 — chỉ một kênh FT4232HL nối tới PL và đã dành cho UART. Bắt buộc adapter rời cắm PMOD0 (J55) |

**Đánh giá:** không có rào cản kỹ thuật nào chưa có lời giải. Việc còn lại là công sức
triển khai, không phải nghiên cứu.

---

## 9. Giới hạn của kết quả hiện tại

Nêu rõ để người tiếp nhận không suy diễn quá phạm vi đã kiểm chứng:

1. **Phase 8 chưa chứng minh có tín hiệu ra chân.** Nó mới chứng minh ghi và đọc lại được
   thanh ghi `PADOUT`. Muốn xác minh mức logic ra pad phải thu thêm nhóm `pad_*` vào
   `wave_capture.do`.
2. **`Hello`/stdout đi qua cơ chế fake stdout của testbench**, không qua UART vật lý.
3. **Waveform mới thu 16 tín hiệu** ở mức top và biên cluster/FC; chưa có bus
   instruction/data hay giao dịch AXI chi tiết.
4. **Chưa chạy synthesis lần nào** — mọi kết luận về ZCU104 là phân tích tĩnh, chưa có
   bằng chứng từ công cụ.
5. **Nhánh Vivado XSim đang dừng** ở `XSIM 43-4177` (bộ nhớ), chưa được thử trong điều kiện
   đủ RAM. Không chặn gì vì Questa là luồng chính.
6. **Băng thông HWPE 12 byte là số đo thực nghiệm** trên đúng cấu hình này, không phải giá
   trị lấy từ tài liệu. Nếu đổi `NB_HWPE_PORTS` hoặc bump `pulp_cluster` thì phải đo lại.

---

## 10. Tài liệu liên quan

| Tài liệu | Nội dung |
|---|---|
| [PLAN.md](PLAN.md) | kế hoạch tổng thể theo milestone |
| [PROJECT_STATUS.md](PROJECT_STATUS.md) | trạng thái động, cập nhật liên tục |
| [nhat-ky-mo-phong-pulp-questasim.md](nhat-ky-mo-phong-pulp-questasim.md) | quy trình dựng môi trường, 15 bài học |
| [lua-chon-simulator.md](lua-chon-simulator.md) | vì sao Questa mô phỏng, Vivado chỉ bitstream |
| [zcu102-to-zcu104-gap.md](zcu102-to-zcu104-gap.md) | gap analysis, bảng chân đối chiếu UG1267 |
| [plan_demo.md](plan_demo.md) | thiết kế chương trình 9 phase |
| [sw/full_system/README.md](../../sw/full_system/README.md) | sáu quyết định thiết kế không hiển nhiên |
