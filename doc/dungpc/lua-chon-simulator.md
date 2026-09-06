# Vì sao dùng QuestaSim để mô phỏng, và Vivado chỉ để sinh bitstream

Ngày: `2026-09-07`

Tài liệu này giải trình một quyết định công cụ: **mô phỏng RTL bằng QuestaSim, dùng Vivado
cho synthesis và bitstream**. Lý do được nêu kèm bằng chứng kiểm chứng được, gồm cả những
lỗi đã thực sự gặp trong quá trình thử Vivado XSim từ `2026-09-03` đến `2026-09-06`.

---

## 1. Câu hỏi đặt ra

Hai câu hỏi thực tế:

1. Các board đã hỗ trợ sẵn (ZCU102, VCU118) có dùng Vivado để **mô phỏng** không, hay chỉ
   nạp bitstream?
2. Vì sao Questa mô phỏng được mà Vivado XSim thì không?

---

## 2. Trả lời câu 1: các board trước chỉ dùng Vivado để sinh bitstream

Ba bằng chứng độc lập trong repository.

### 2.1 Flow FPGA không chứa lệnh mô phỏng nào

`fpga/pulp/tcl/run.tcl` — toàn bộ luồng FPGA:

```
synth_design -rtl ...        (dòng 50)
launch_runs synth_1          (dòng 55)
impl_1: opt/place/route/phys_opt   (dòng 70-76)
launch_runs impl_1 -to_step write_bitstream   (dòng 82)
```

Không có `launch_simulation`.

### 2.2 Makefile FPGA không có target mô phỏng

`fpga/Makefile` chỉ có `all`, `zcu102`, `vcu118`, `clean_ips`, `clean_zcu102`,
`clean_vcu118`, `help`.

### 2.3 CI tách bạch hai vai trò

`.gitlab-ci.yml` khai báo hai stage riêng biệt:

| Stage | Nội dung | Công cụ |
|---|---|---|
| `build_fpga` (dòng 176) | `make -C fpga zcu102 VIVADO='vivado-2019.1.1 vivado'` | Vivado — **chỉ bitstream** |
| `sim_questa_multivers` (dòng 189) | chạy trên `questa-2019.3`, `questa-2020.1`, `questa-2021.3` | Questa — **mô phỏng** |

### 2.4 Không tồn tại testbench cho FPGA top

Chỉ ba file tham chiếu `xilinx_pulp`: hai board top
(`fpga/pulp-zcu102/rtl/xilinx_pulp.v`, `fpga/pulp-vcu118/rtl/xilinx_pulp.v`) và
`rtl/pulpemu/pulpemu.sv` — file cuối là **wrapper cho Xilinx IP Integrator**, không phải
testbench (không có `initial`, `$finish` hay `$stop`).

**Kết luận:** với ZCU102 và VCU118, Vivado chưa bao giờ mô phỏng gì. Vai trò của nó luôn
chỉ là synthesis và bitstream.

---

## 3. Trả lời câu 2: năm lý do không dùng XSim cho mô phỏng này

### 3.1 Upstream tuyên bố thẳng

`README.md` dòng 261:

> Simulation flows different from ModelSim/QuestaSim have only have limited testing.

Dòng 208 gọi `sim/` là *"the ModelSim/QuestaSim simulation platform"*. Mục Requirements
(dòng 217) nêu yêu cầu là *"ModelSim in reasonably recent version"*.

Toàn bộ hạ tầng mô phỏng đều là Questa: `sim/Makefile`, `sim/tcl_files/`, `modelsim.ini`,
20 file wave `sim/waves/*.tcl`. Flow XSim trong repository này do dự án tự dựng — chính
tên file patch đầu tiên đã tự nhận là thử nghiệm:
`xsim/0001AddexperimentalVivadoXSimflowfortb_pulp.patch`.

### 3.2 XSim không phân giải được SystemVerilog mà PULP dùng

Không phải suy đoán. Hai lỗi đã gặp trực tiếp, log tại `sim/xsim/` và mô tả trong
[PROJECT_STATUS.md](PROJECT_STATUS.md) mục 7:

| Mã lỗi | Vị trí | Cấu trúc gây lỗi | Questa | XSim 2019.1 |
|---|---|---|---|---|
| `XSIM 43-3254` | `fpnew_pkg.sv:302` | `FP_ENCODINGS[fmt].exp_bits` — lấy trường của phần tử mảng hằng, trong hàm `automatic` chạy lúc elaborate | chạy | `Could not find hier sig handle` |
| `XSIM 43-3209` | `fpnew_opgroup_multifmt_slice.sv:301` | `... ? op_result : '{default: lane_ext_bit[0]}` — assignment pattern trong toán tử ba ngôi | chạy | `Unsupported construct`, sau đó **`43-3316 SIGSEGV` — `xelab` tự sập** |

Lỗi thứ hai đáng lưu ý: **công cụ tự crash**, không phải thiết kế sai.

Quan trọng hơn, **không thể né bằng tham số**. `cv32e40p/rtl/include/riscv_defines.sv:392-394`
tham chiếu `fpnew_pkg::OP_BITS`, `FP_FORMAT_BITS`, `INT_FORMAT_BITS` **vô điều kiện ở mức
parameter**, mà file này được include bởi toàn bộ core CV32E40P. Package luôn phải compile
bất kể FPU bật hay tắt. Đã kiểm chứng: tắt FPU vẫn cho đúng lỗi `43-3254`, và `elaborate.log`
cho thấy `xelab` chết ngay ở dòng `Compiling package xil_defaultlib.fpnew_pkg`.

Nghĩa là muốn XSim chạy thì **bắt buộc phải sửa mã dependency**.

### 3.3 Mất lớp kiểm tra giao thức

Log XSim chứa hàng trăm cảnh báo `43-4127` và `43-4455`: SystemVerilog Assertion,
`$past`, multiclocked sequence, deferred assertion — tất cả bị bỏ qua. Script còn phải
truyền thêm `-ignore_assertions` mới chạy được.

Các dependency `common_cells` và `axi` chứa nhiều assertion kiểm tra giao thức. Mất chúng
có hậu quả cụ thể: trên Questa, một giao dịch AXI/HCI sai sẽ nổ ra thành assertion kèm tên
file và số dòng; trên XSim nó biểu hiện thành **dữ liệu sai âm thầm**, phải tự truy ngược
từ kết quả so sánh. Đúng hai phase khó nhất của
[sw/full_system](../../sw/full_system/README.md) — phase 6 (MCHAN DMA) và phase 7 (HWPE
datamover) — lại là nơi mất mát này nặng nhất.

Kinh nghiệm thực tế trong dự án: phase 7 đã phải sửa **bốn vòng** mới chạy đúng, và mỗi
vòng đều dựa vào việc đọc chính xác dữ liệu sai lệch. Không có assertion thì quá trình đó
còn dài hơn.

### 3.4 Cái giá phải trả

Kể cả khi vượt qua rào cản bộ nhớ còn lại, bản XSim sẽ:

- **không có FPU** — bắt buộc tắt để né lỗi `43-3209`/SIGSEGV;
- **không chạy assertion**;
- chậm hơn Questa;
- cần **hai patch trên mã dependency**, phải áp lại sau mỗi `bender checkout`
  (`xsim/patches/apply_xsim_patches.sh`).

Tức là một cấu hình phần cứng **khác** với bản đang dùng, và yếu hơn về khả năng phát hiện
lỗi. Mọi so sánh kết quả giữa hai simulator đều phải kèm cảnh báo này.

### 3.5 Không đóng góp gì cho mục tiêu ZCU104

Mô phỏng `tb_pulp` trên XSim chạy **đúng RTL** mà Questa đang chạy. Nó không chạm tới
`xilinx_pulp.v`, không chạm MMCM `fpga_clk_gen`, không chạm BRAM/XPM, không chạm ràng buộc
chân.

Thứ chuẩn bị cho board là **synthesis** — dùng engine hoàn toàn khác `xelab` và xử lý
được đám SystemVerilog nói trên bình thường. Bằng chứng: CI của upstream vẫn sinh bitstream
ZCU102 đều đặn bằng đúng Vivado 2019.1.

---

## 4. Khi nào XSim mới là lựa chọn đúng

Để công bằng, có một trường hợp XSim thực sự thuận hơn Questa: **mô phỏng chính FPGA top**
(`xilinx_pulp.v`) cùng MMCM, XPM memory và IP Xilinx thật. Questa muốn làm việc đó phải
chạy `compile_simlib` để biên dịch thư viện Xilinx trước; XSim có sẵn các thư viện đó.

Nhưng đó là việc **sau khi** đã có target ZCU104, và nhắm đối tượng khác: kiểm tra tầng bọc
FPGA, không phải kiểm tra logic PULP.

XSim cũng hoàn toàn phù hợp cho: testbench mức IP hoặc module, kiểm tra IP Xilinx và block
design, thiết kế FPGA cỡ vừa dùng SystemVerilog ở mức phổ thông. Vấn đề ở đây là **lệch
mục đích** — PULP là platform nghiên cứu hướng ASIC dùng SystemVerilog ở mức mà hiện chỉ
simulator thương mại theo kịp — chứ không phải Vivado kém.

---

## 5. Trạng thái nhánh XSim trong dự án này

Không xoá bỏ, chỉ dừng lại. Mọi thứ đã dựng sẵn nếu cần dùng lại:

| Thành phần | Vị trí |
|---|---|
| Patch `fpnew_pkg` | `xsim/patches/0002-fpnew_pkg-xsim-const-array-field-access.patch` |
| Script áp lại patch | `xsim/patches/apply_xsim_patches.sh` |
| Bật/tắt FPU cluster | `xsim/patches/toggle_fpu.sh on\|off` |
| Chạy `hello` | `sim/xsim/run_hello_xsim.tcl`, `run_hello_xsim_nofpu.tcl` |
| Chạy `full_system` | `sim/xsim/run_full_system_xsim.tcl` |

Rào cản còn lại duy nhất là `XSIM 43-4177` (hết bộ nhớ), **chưa bao giờ được thử trong điều
kiện đủ RAM** — cả năm lần chạy đều có `free physical` quanh 1 GB vì máy đang chạy Vivado
GUI, Firefox và nhiều cửa sổ VS Code. `ulimit -v` và `-m` đều `unlimited` nên đã loại trừ
giới hạn shell.

---

## 6. Kết luận

| | Mô phỏng RTL | Synthesis / bitstream |
|---|---|---|
| **Công cụ** | QuestaSim 10.7c | Vivado 2019.1 |
| **Lý do** | upstream hỗ trợ chính thức; hỗ trợ SystemVerilog đầy đủ; chạy assertion; giữ nguyên FPU | vai trò duy nhất của Vivado trong CI upstream; xử lý được RTL mà `xelab` không phân giải nổi |
| **Bằng chứng** | 9/9 phase pass, [report/full_system_20260906/](../../report/full_system_20260906/) | bitstream ZCU102 trong CI upstream |

Quyết định này **không chặn** mục tiêu ZCU104. Hai việc độc lập nhau, và việc dùng Vivado
cho synthesis vẫn diễn ra đúng như thiết kế của upstream.
