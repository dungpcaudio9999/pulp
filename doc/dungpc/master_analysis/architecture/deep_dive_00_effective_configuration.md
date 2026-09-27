# Chuyên sâu 00 — Cấu hình hiệu lực của checkout

Đối chiếu ngày **2026-09-10**, root commit `ce0628648cb0b7d2d29ed348a235b6b12442034a`.
Đối tượng chính là **RTL simulation Questa, `sw/full_system/run_sim.sh`**. Đây là
phân tích source; chưa compile/elaborate hoặc chạy lại simulator trong đợt này.

## 1. Quy ước bằng chứng

- **[RTL]**: đã lần theo wiring, nhánh generate và implementation trong checkout.
- **[SW]**: đã đối chiếu C, HAL, startup, linker hoặc script chạy; chưa chứng minh giao dịch đã xảy ra.
- **[SIM cũ: ngày/lượt]**: log lưu từ lần chạy được chỉ rõ; không phải kết quả tái lập hiện tại.
- **[CẦN ĐO]**: phép thử hoặc giả thuyết chưa có bằng chứng động đủ mạnh.

Mỗi chương domain dùng sáu mục: vai trò/ranh giới, cấu trúc hiệu lực, hoạt động,
góc nhìn phần mềm, thời gian/hiệu năng, bằng chứng và tiêu chí kiểm chứng.

## 2. Cấu hình từ cha xuống con [RTL, SW]

Nguồn: [testbench](../../../../rtl/tb/tb_pulp.sv#L32),
[top](../../../../rtl/pulp/pulp.sv#L1156), [defines](../../../../rtl/includes/pulp_soc_defines.sv),
[runner](../../../../sw/full_system/run_sim.sh),
[FPGA ZCU104](../../../../fpga/pulp-zcu104/rtl/xilinx_pulp.v#L50).

| Hạng mục | TB mặc định | Demo qua `run_sim.sh` | FPGA wrapper ZCU104 |
|---|---|---|---|
| Top | `tb_pulp → i_dut:pulp` | như TB | `xilinx_pulp → pulp` |
| Core FC / cluster | `CORE_TYPE_FC/CL=0/0` | `0/0`, nhánh `riscv_core` | `0/0` |
| FPU FC | `RISCY_FPU=1 → USE_FPU=1` | bật; FC `SHARED_FP=0`, `Zfinx=1` mặc định dependency | `USE_FPU=1` |
| FPU cluster | macro `CLUST_FPU=1` | bật; `SHARED_FPU_CLUSTER`, 4 FPNEW và 1 APU được cấu hình | cần giữ cùng defines trong compile FPGA |
| HWPE SoC / cluster | `0/0` | **`0/1`** do `-gUSE_HWPE_CL=1` | `0/0` |
| Số PE / L1 | top đặt 8 / 64 KiB | 16 bank × 4 KiB | cùng tham số top |
| `NB_HWPE_PORTS` cluster | wrapper mặc định 9, **top truyền 4** | **4** | 4 nhưng HWPE tắt |
| I-cache | `PRIVATE_ICACHE` | `icache_hier_top`: private 512 B/core, shared size parameter 4 KiB | phụ thuộc defines FPGA |
| Boot | `LOAD_L2=JTAG`, `STIM_FROM=JTAG` | JTAG, `ENTRY_POINT=0x1C008080` | boot/debug của board, không có loader TB |
| Clock reference | chu kỳ `30517 ns` | như TB, xấp xỉ 32.768 kHz | clock board và `fpga_clk_gen` |
| UART monitor | baud 625000 | **115200** | cấu hình UART phần mềm/board |

`RISCY_FPU=0` ở TB chỉ truyền tới FPU **FC**; cluster lấy macro riêng ở
`pulp.sv`. `VIVADO` được define trong header không đồng nghĩa đang chạy FPGA:
nhánh đổi clock/reset/pad được chọn bằng **`PULP_FPGA_EMUL`**.

Đường tham số HWPE giải thích được payload 12 byte:

```text
pulp.NB_HWPE_PORTS truyền 4
→ cluster_domain → pulp_cluster → hwpe_subsystem.N_MASTER_PORT=4
→ datamover_top.BW=4*32=128
→ BW_ALIGNED=BW-32=96 bit=12 byte
```

Nguồn cuối: [datamover_top](../../../../.bender/git/checkouts/hwpe-datamover-example-a9b2d6689c13b9f9/rtl/datamover_top.sv#L22).
Word 32 bit trừ đi dành cho hỗ trợ căn chỉnh dữ liệu theo byte (comment ngay
trước `BW_ALIGNED` trong datamover). Đây là **payload mỗi beat được chấp nhận**,
chưa phải throughput 12 byte mỗi
clock khi có stall, arbitration hoặc đổi chiều load/store.

## 3. Implementation nào nằm trong compile list? [RTL]

[`source_audit.json`](../../../../report/domain_analysis_20260910/source_audit.json)
ghi HEAD dependency, thay đổi local và SHA-256 của các đầu vào chính.
Đã kiểm tra **811 đường dẫn source RTL duy nhất** được liệt kê trực tiếp trong
[`sim/compile.tcl`](../../../../sim/compile.tcl); không có đường dẫn bị thiếu.
Các target define là `TARGET_RTL`, `TARGET_SIMULATION`, `TARGET_TEST`, `TARGET_VSIM`.
Con số này không bao gồm toàn bộ header include, không phải báo cáo compile thành công.

| Dependency | HEAD thực tế, rút gọn | Implementation dùng để lần theo |
|---|---|---|
| `pulp_soc` | `d878151e0e40` | `rtl/pulp_soc`, `rtl/fc`, `rtl/components/apb_soc_ctrl.sv` |
| `pulp_cluster` | `040fc3e3b2db` | `rtl/pulp_cluster.sv`, core/HCI/DMA/cache wrappers |
| `cv32e40p` | `8d58109ab61e` | tên module vẫn là `riscv_core`, không suy theo tên repo |
| `common_cells` | `b5ec8905ed78` | `rstgen_bypass`, `cdc_fifo_gray` |
| `tech_cells_generic` | `e6226a6f374e` | pad, SRAM, `generic_rom` |
| `hwpe-datamover-example` | `47e7fe8a3833` | datamover control/streamer/engine |

`Bender.yml` khai báo revision cluster `db2e173…`, còn **lock và checkout hiện tại
là `040fc3e…`**. Vì vậy không gọi đây là checkout sạch chỉ dựa vào manifest.
Một số dependency còn có patch local cho XSim; compile list Questa vẫn trỏ vào
các file đó. File `*.before_xsim_*` là bản sao, không nằm trong compile list.
Không tự checkout/update dependency để làm mất trạng thái đang được khảo sát.

## 4. Hierarchy chức năng [RTL]

```text
tb_pulp.i_dut : pulp
├─ pad_frame_i
├─ safe_domain_i
│  ├─ pad_control_i
│  └─ i_rstgen (output sync không nối ra rst_no)
├─ soc_domain_i.pulp_soc_i
│  ├─ i_clk_rst_gen
│  ├─ fc_subsystem_i.FC_CORE.lFC_CORE : riscv_core
│  ├─ i_soc_interconnect_wrap
│  ├─ boot_rom_i / l2_ram_i
│  └─ soc_peripherals_i (SoC control, GPIO, timer, uDMA, event generator)
└─ cluster_domain_i.cluster_i
   ├─ core_region_i trong vòng generate PE
   ├─ icache_top_i : icache_hier_top
   ├─ cluster_interconnect_wrap_i / tcdm_banks_i
   ├─ cluster_peripherals_i / dmac_wrap_i
   ├─ i_shared_fpu_cluster / HWPE generate
   └─ AXI CDC, event FIFO, u_clustercg
```

Đây là cây chức năng từ source, không phải dump hierarchy sau optimization.
Core Ibex và nhiều biến thể cache cũng được compile nhưng không vì thế mà được
instantiate trong cấu hình này. `safe_domain_reg_if` không được instantiate;
có file RTC không chứng minh có RTC/PMU đang hoạt động.

## 5. Clock/reset hiệu lực [RTL]

`pad_xtal_in → pad_frame.ref_clk_o → s_ref_clk → soc_clk_rst_gen`.
Non-FPGA instantiate ba mô hình FLL; clock mux chọn FLL khi `sel_fll_clk_i=0`,
chọn reference khi bằng 1. Tần số SoC/cluster thay đổi theo cấu hình FLL runtime,
không được lấy 32.768 kHz làm tần số core.

**Reset safe domain đi thẳng:** `rst_no=s_rstn=rst_ni`, dù `i_rstgen` tạo
`s_rstn_sync`. Trong SoC, `i_soc_rstgen` mới đồng bộ nhả reset theo `clk_soc_o`;
`i_cluster_rstgen` đồng bộ theo clock cluster. `cluster_rstn_o` còn AND với reset
điều khiển từ SoC control; bên trong cluster có reset generator và clock gate riêng.
Xem [bài reset → lệnh đầu tiên](deep_dive_04_boot_debug_testbench.md).

## 6. Điều kiện để gắn nhãn SIM mới

Ghi lại lệnh chạy, target/defines, tham số elaboration, HEAD và patch dependency,
hash ELF/stimuli/ROM, simulator/version, log, waveform/trace, timeout và exit code.
Thư viện `vopt_tb` có sẵn chưa chứng minh được build từ source hiện tại;
`-floatparameters+tb_pulp` trong [sim/Makefile](../../../../sim/Makefile#L45) cho phép ghi đè
generic nhưng không thay thế việc compile lại khi source/defines thay đổi.
