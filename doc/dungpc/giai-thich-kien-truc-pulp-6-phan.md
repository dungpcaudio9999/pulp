# Giải thích kiến trúc PULP theo 6 nhóm thành phần

Tài liệu giải thích các khái niệm phần cứng và phần mềm, đồng thời đối chiếu với hệ thống PULP trong repository này. Đối tượng mô tả là **PULP RISC-V gồm Fabric Controller và cluster xử lý song song**, không phải các nhân Arm của chip Zynq trên board FPGA.

Ngày đối chiếu: **09/09/2026**. Commit repository: `cb191f69b9c1210834fe4642993af55a56cbce09`. Các nhận xét về implementation dựa trên mã RTL và runtime đang có tại máy, bao gồm dependency trong `.bender/git/checkouts`. Tham số của testbench hoặc target FPGA có thể thay đổi cấu hình được tạo ra.

NVIC, CMSIS, MPU, ADC và DAC vẫn được giải thích theo đề cương, nhưng không được mặc nhiên coi là các khối đã tích hợp trong PULP. Những khác biệt giữa khái niệm chung, khả năng cấu hình của IP và cấu hình thực tế được nêu tại từng mục.

## 1. Kiến trúc nhân xử lý và Mô hình người lập trình (Processor Core & Programmer's Model)

### 1.1. Tập lệnh (ISA) & Cấu trúc nhân

**ISA — Instruction Set Architecture** là giao ước giữa chương trình và bộ xử lý: các lệnh được phép thực hiện, kiểu dữ liệu, thanh ghi, cách truy cập bộ nhớ và cách xử lý ngoại lệ. **Vi kiến trúc** là cách phần cứng thực hiện ISA, chẳng hạn số tầng pipeline, bộ nhân và bộ đệm lệnh. Hai nhân cùng ISA có thể chạy cùng chương trình nhưng có tốc độ và điện năng khác nhau.

PULP trong cấu hình testbench mặc định có:

- **Một Fabric Controller (FC):** thực hiện khởi động, cấu hình ngoại vi, quản lý dữ liệu và giao việc cho cluster.
- **Một cluster gồm 8 processing element (PE):** chia nhau thực hiện các tác vụ tính toán. Mỗi PE có trạng thái thực thi, PC và thanh ghi riêng, đồng thời cùng truy cập bộ nhớ dữ liệu L1.
- `CORE_TYPE_FC = 0`, `CORE_TYPE_CL = 0`: chọn nhánh RI5CY/RISCY. Dependency chứa implementation tên module `riscv_core` trong package `cv32e40p`; cần đọc revision này, không áp toàn bộ đặc tính của CV32E40P mới nhất lên thiết kế cũ.

RI5CY là nhân **32 bit, in-order, single-issue, pipeline 4 tầng**: lấy lệnh (IF), giải mã/đọc thanh ghi (ID), thực thi (EX), ghi kết quả (WB). In-order nghĩa là xử lý theo thứ tự chương trình; single-issue nghĩa là tối đa phát một lệnh mỗi chu kỳ. Lệnh nhân/chia, chờ bộ nhớ, xung đột tài nguyên hoặc nhánh có thể gây dừng pipeline, nên không thể hiểu mọi lệnh đều hoàn thành trong một chu kỳ.

Các thành phần ISA chính:

- **RV32I:** số nguyên 32 bit, tính toán, logic, nhánh, load/store. Các phép toán chủ yếu tác động lên thanh ghi; muốn xử lý dữ liệu trong RAM phải nạp dữ liệu rồi ghi kết quả trở lại.
- **M:** nhân và chia số nguyên.
- **C:** lệnh nén 16 bit để giảm kích thước chương trình; độ rộng thanh ghi vẫn là 32 bit.
- **Dấu phẩy động đơn chính xác khi bật FPU:** testbench đặt `RISCY_FPU = 1` cho FC; cluster có các tham số FPU riêng. Cần phân biệt cấu hình dùng thanh ghi FP của phần mở rộng F với tùy chọn `Zfinx` dùng thanh ghi số nguyên, như mục 1.2 giải thích.
- **Mở rộng PULP:** vòng lặp phần cứng, load/store tự tăng địa chỉ, MAC, thao tác bit, packed SIMD và dot product phục vụ xử lý tín hiệu.

Packed SIMD của PULP xử lý nhiều phần tử nhỏ nằm trong một thanh ghi. Đây không phải bằng chứng rằng hệ thống hỗ trợ phần mở rộng vector chuẩn RISC-V `V`. Tương tự, không nên suy ra có phần mở rộng atomic `A` chỉ vì phần cứng có mutex hoặc vùng test-and-set.

Các giá trị `CORE_TYPE = 1/2` chọn các nhánh Ibex với cấu hình khác. Tài liệu này tập trung vào nhánh `0`; khi đổi nhân cần kiểm tra lại lệnh mở rộng, ngắt, FPU và cờ biên dịch.

Nguồn: [README của PULP](../../README.md), [testbench](../../rtl/tb/tb_pulp.sv), [tham số hệ thống](../../rtl/includes/pulp_soc_defines.sv), [wrapper cluster](../../rtl/pulp/cluster_domain.sv).

### 1.2. Tập thanh ghi (Register Set)

**Thanh ghi số nguyên:** RV32I có `x0`–`x31`, mỗi thanh ghi rộng 32 bit. `x0` luôn đọc ra 0; việc ghi vào nó không lưu kết quả. Các tên sau là quy ước ABI để compiler và hàm assembly phối hợp:

- `x1/ra`: địa chỉ quay về sau lời gọi hàm.
- `x2/sp`: con trỏ stack; mỗi core cần stack riêng.
- `x3/gp`, `x4/tp`: con trỏ phục vụ dữ liệu global/thread theo runtime và ABI.
- `x10`–`x17`, tức `a0`–`a7`: tham số hàm; `a0` và `a1` cũng dùng cho kết quả trả về.
- `t0`–`t6`: thanh ghi tạm do phía gọi hàm bảo toàn nếu cần giữ giá trị.
- `s0`–`s11`: phía được gọi phải bảo toàn nếu sử dụng; `s0` cũng có thể làm frame pointer.

**PC — Program Counter** giữ địa chỉ lệnh đang thực thi hoặc được lấy tiếp theo. PC không phải một thanh ghi `xN` để tùy ý đọc/ghi bằng phép toán thông thường; nhánh, jump và cơ chế trap thay đổi luồng thực thi.

**CSR — Control and Status Registers** là nhóm thanh ghi đặc biệt, truy cập bằng lệnh CSR thay vì load/store thông thường. Các CSR có trong implementation đang khảo sát gồm:

- `mstatus`: trạng thái thực thi, trong đó có điều khiển cho phép ngắt.
- `misa`: mô tả một số phần mở rộng ISA của cấu hình nhân.
- `mtvec`: cơ sở vector/trap handler theo định dạng của revision nhân này.
- `mepc`: PC được lưu khi xảy ra trap; `mcause`: nguyên nhân trap.
- `mscratch`: vùng thanh ghi tạm dành cho phần mềm xử lý trap.
- `mhartid`: nhận dạng hart, ghép từ cluster ID và core ID trong RTL.
- `dcsr`, `dpc`, `dscratch0/1`: trạng thái và điểm thực thi phục vụ debug.
- CSR cho hai hardware loop, mỗi loop có địa chỉ đầu, địa chỉ cuối và bộ đếm.
- Các thanh ghi đếm hiệu năng riêng của PULP; dùng HAL tương ứng thay vì giả định mọi địa chỉ counter đều giống một bản đặc tả mới.

Khi bật FPU, các CSR như `fflags`, `frm`, `fcsr` quản lý trạng thái dấu phẩy động. Register file có hai cách cấu hình: `Zfinx = 0` dùng thêm tập thanh ghi FP `f0`–`f31`, còn `Zfinx = 1` dùng tập thanh ghi số nguyên cho toán hạng/kết quả FP. SoC/FC hiện đặt mặc định `USE_ZFINX = 1`; vì vậy không được khẳng định FC có thêm một tập 32 thanh ghi FP riêng chỉ dựa vào `RISCY_FPU = 1`. Tùy chọn mang tên `Zfinx` trong IP cũ cũng cần được đối chiếu theo revision, không mặc nhiên chứng minh tuân thủ mọi chi tiết của đặc tả Zfinx mới.

Nhánh RI5CY của cluster không ghi đè `Zfinx`, nên dùng mặc định `0` của `riscv_core`: khi FPU bật, nhánh này có tập thanh ghi FP riêng. Compiler phải tạo lệnh và dùng ABI phù hợp với cách cấu hình thanh ghi của từng phía; bật FPU trong RTL không tự động làm mọi biểu thức C dùng lệnh FP phần cứng.

**Thanh ghi ngoại vi khác CSR:** địa chỉ GPIO, timer, DMA là MMIO, được truy cập bằng load/store qua interconnect. Biến con trỏ `volatile` giúp compiler giữ các lần truy cập MMIO, nhưng không thay thế khóa, barrier hay cơ chế đồng bộ dữ liệu giữa nhiều core.

Nguồn: [CSR của nhân](../../.bender/git/checkouts/cv32e40p-0a3884e05ea5a482/rtl/riscv_cs_registers.sv), [register file](../../.bender/git/checkouts/cv32e40p-0a3884e05ea5a482/rtl/riscv_register_file.sv), [HAL RISC-V](../../pulp-runtime/include/hal/riscv/riscv_v5.h).

### 1.3. Các khối xử lý mở rộng

**DSP trong nhân:** MAC thực hiện nhân–cộng dồn, dot product phù hợp tích vô hướng, packed SIMD giúp xử lý nhiều mẫu nhỏ. Hardware loop giảm lệnh cập nhật bộ đếm và nhảy ở vòng lặp; post-increment load/store giảm lệnh tính địa chỉ. Hiệu quả thực tế phụ thuộc compiler hoặc intrinsic có sử dụng các lệnh đó hay không.

**FPU:** hỗ trợ tính toán số thực. Cluster có tùy chọn chia sẻ tài nguyên FP giữa các core; các macro `CLUST_FPU`, `CLUST_SHARED_FP`, `CLUST_FP_DIVSQRT` và `CLUST_SHARED_FP_DIVSQRT` điều khiển cấu hình. Việc chia sẻ tiết kiệm phần cứng nhưng có thể gây tranh chấp khi nhiều core yêu cầu cùng lúc.

**HWPE — Hardware Processing Engine:** bộ tăng tốc độc lập với pipeline CPU. CPU ghi các thanh ghi cấu hình, cung cấp địa chỉ buffer và khởi chạy; HWPE tự đọc/ghi bộ nhớ rồi báo hoàn thành. HWPE hiện diện không có nghĩa CPU được thêm một lệnh ISA tương ứng.

Testbench mặc định đặt `USE_HWPE = 0` và `USE_HWPE_CL = 0`. Script demo `full_system` bật riêng `-gUSE_HWPE_CL=1`. Implementation cluster có nhánh datamover, được demo dùng để di chuyển dữ liệu. Không nên dựa vào mô tả MAC accelerator trong README để kết luận mọi bản build đều có accelerator MAC đó.

Nguồn: [HWPE subsystem](../../.bender/git/checkouts/pulp_cluster-48721e3ce381c984/rtl/hwpe_subsystem.sv), [script chạy demo](../../sw/full_system/run_sim.sh), [giải thích demo](../../sw/full_system/README.md).

## 2. Cấu trúc bộ nhớ và Sơ đồ địa chỉ (Memory System & Memory Map)

### 2.1. Phân loại và dung lượng bộ nhớ

**Boot ROM:** chứa mã khởi động, không phải RAM để chương trình lưu biến. `ROM_ADDR_WIDTH = 13` và interface truy cập word 32 bit cho dung lượng địa chỉ hóa thực là `2^13 = 8192 byte`, tức **8 KiB** trong implementation đang xét. Cửa sổ decode ROM rộng 256 KiB không làm ROM vật lý tăng thành 256 KiB.

**L2 SRAM phía SoC:** lưu mã, dữ liệu FC, buffer ngoại vi và dữ liệu trao đổi với cluster. Với `USE_L2_MULTIBANK` hiện bật:

- Hai private bank, mỗi bank `8192 × 4 = 32768 byte` = **32 KiB**.
- Bốn shared/interleaved bank, mỗi bank `32768 × 4 = 131072 byte` = **128 KiB**.
- Tổng SRAM L2 của cấu hình RTL này là `2 × 32 + 4 × 128 = 576 KiB`.

Tên private bank phản ánh cách tổ chức đường truy cập và mục đích giảm tranh chấp; không tự nó chứng minh có hàng rào bảo mật ngăn mọi master khác truy cập.

**L1 TCDM của cluster:** TCDM là *Tightly Coupled Data Memory*, bộ nhớ dữ liệu dùng chung có độ trễ thấp. Wrapper đặt **64 KiB**, chia **16 bank**, mỗi bank **4 KiB**. Các core, DMA và HWPE có thể truy cập các bank khác nhau song song; truy cập cùng bank cần phân xử và có thể phải chờ. Đây là scratchpad do phần mềm bố trí dữ liệu, không phải data cache tự động thay thế dữ liệu từ L2.

**Instruction cache:** cluster có hệ thống cache lệnh để giảm số lần phải lấy lệnh qua SoC. Wrapper có `CACHE_SIZE = 4096`, cùng các tùy chọn private/hierarchy/shared cache. Giá trị tham số này không nên được diễn giải thành tổng dung lượng mọi tầng cache khi chưa xét nhánh generate. FC trong đường thực thi mà linker hiện nhắm tới không dùng instruction cache, nên linker cố tách mã và dữ liệu FC sang các bank khác nhau.

**Bộ nhớ ngoài:** giao diện SPI và HyperBus cho phép làm việc với flash/RAM ngoài tùy cấu hình và phần cứng kết nối. Dung lượng chip ngoài hoặc VIP không phải dung lượng SRAM nội chip; cũng không được tự động cộng DDR của board FPGA vào RAM mà PULP truy cập được.

**Khác biệt RTL và runtime:** [memory map của runtime](../../pulp-runtime/include/archi/chips/pulp/memory_map.h) khai báo 32 KiB private 0, 32 KiB private 1 và **448 KiB shared**, tổng **512 KiB**. [Linker script](../../pulp-runtime/kernel/chips/pulp/link.ld) chỉ dành `0x7FFFC` byte từ `0x1C000004`, tức vùng 512 KiB trừ 4 byte đầu. Vì vậy, còn 64 KiB ở cuối vùng L2 RTL chưa được linker hiện tại đưa vào ngân sách cấp phát. Tham số `L2_SIZE = 512*1024` ở wrapper cluster cũng không thay thế phép tính dung lượng SRAM từ implementation SoC.

Nguồn dung lượng RTL: [pulp_soc](../../.bender/git/checkouts/pulp_soc-c519334bd3ac5582/rtl/pulp_soc/pulp_soc.sv), [L2 multi-bank](../../.bender/git/checkouts/pulp_soc-c519334bd3ac5582/rtl/pulp_soc/l2_ram_multi_bank.sv), [boot ROM](../../.bender/git/checkouts/pulp_soc-c519334bd3ac5582/rtl/pulp_soc/boot_rom.sv), [wrapper cluster](../../rtl/pulp/cluster_domain.sv).

### 2.2. Sơ đồ địa chỉ bộ nhớ (Memory Map)

Memory map quy định một địa chỉ load/store được chuyển tới RAM, ROM hay thanh ghi nào. **Các khoảng dưới đây dùng quy ước `[đầu, cuối)`: địa chỉ cuối không thuộc vùng.**

- **`[0x1C000000, 0x1C008000)` — L2 private bank 0:** 32 KiB, linker ưu tiên dữ liệu FC.
- **`[0x1C008000, 0x1C010000)` — L2 private bank 1:** 32 KiB, linker ưu tiên vector ngắt và mã FC.
- **`[0x1C010000, 0x1C090000)` — L2 shared của RTL:** 512 KiB, chia xen kẽ qua bốn bank. Runtime hiện chỉ khai báo shared đến `0x1C080000`.
- **`[0x1A000000, 0x1A040000)` — cửa sổ Boot ROM:** decode rộng 256 KiB; ROM có 8 KiB như đã giải thích.
- **`[0x10000000, 0x10400000)` — cửa sổ AXI sang cluster 0:** rộng 4 MiB, bao gồm không gian bộ nhớ và điều khiển cluster; không phải 4 MiB RAM.
- **`[0x10000000, 0x10010000)` — vùng L1 TCDM 64 KiB của cluster 0:** địa chỉ global dùng khi FC/SoC truy cập cluster. Linker bắt đầu dữ liệu L1 tại `0x10000004`.
- **`[0x1A100000, 0x1A400000)` — cửa sổ ngoại vi SoC:** bao trùm các vùng MMIO; không phải mọi địa chỉ bên trong đều có thiết bị phản hồi.
- **`[0x00000000, 0x00100000)` — cửa sổ alias khai báo ở SoC:** cách dịch/định tuyến phụ thuộc master và cấu hình. Macro cluster cũng cho phép nhìn không gian local qua alias thấp; không coi cùng địa chỉ thấp ở FC và PE là cùng một RAM nếu chưa xét đường truy cập.

Các địa chỉ thanh ghi quan trọng theo header runtime PULP:

- `0x1A100000`: vùng FLL.
- `0x1A101000`: GPIO.
- `0x1A102000`: cơ sở uDMA; mỗi ngoại vi/kênh có offset riêng.
- `0x1A104000`: APB SoC control.
- `0x1A106000`: SoC event unit/generator.
- `0x1A109800`: FC interrupt controller.
- `0x1A10B000`: FC timer.
- `0x1A10F000`: stdout mô phỏng; không đồng nghĩa UART vật lý.

Không gian thanh ghi **global của cluster 0** được tạo từ `0x10000000 + offset`:

- `0x10200000`: cluster control.
- `0x10200400`: cluster timer.
- `0x10200800`: event unit.
- `0x10201000`: cửa sổ accelerator, được header cũ đặt tên `HWCE`; chức năng thực tế phụ thuộc IP được instantiate.
- `0x10201400`: instruction-cache control.
- `0x10201800`: MCHAN qua cổng external.
- `0x10204000`: event unit qua đường demux.
- `0x10204400`: MCHAN qua đường demux.

Header HAL có thể dùng địa chỉ local như `0x00204400` khi code đang chạy trong cluster. Để điều khiển từ FC phải dùng địa chỉ global hoặc hàm remote phù hợp.

Ví dụ cách tra một thanh ghi: bắt đầu từ base GPIO `0x1A101000`, cộng offset thanh ghi trong header GPIO đúng phiên bản, rồi kiểm tra APB decode và RTL GPIO. Không lấy offset của một dòng MCU khác chỉ vì cùng tên `GPIO`.

Nguồn: [memory map RTL](../../rtl/includes/soc_mem_map.svh), [memory map runtime](../../pulp-runtime/include/archi/chips/pulp/memory_map.h). Khi có khác biệt, RTL quyết định phần cứng được decode, còn linker quyết định phần nào chương trình thực sự sử dụng.

### 2.3. Quản lý và bảo vệ bộ nhớ (MPU)

**MPU — Memory Protection Unit** kiểm tra quyền đọc, ghi, thực thi theo vùng địa chỉ. **MMU — Memory Management Unit** có thêm vai trò dịch địa chỉ, thường dùng cho bộ nhớ ảo. Chia section trong linker chỉ tổ chức dữ liệu, không tự tạo ra bảo vệ phần cứng.

Trong RISC-V, cơ chế cần xem xét ở đây là **PMP — Physical Memory Protection**. Cấu hình hiện tại khác nhau giữa FC và cluster:

- Nhánh RI5CY của **FC** instantiate `riscv_core` với `PULP_SECURE = 1`. Core mặc định `USE_PMP = 1`, `N_PMP_ENTRIES = 16`; nhánh bảo vệ được tạo khi `PULP_SECURE && USE_PMP`. Như vậy có cơ sở RTL để xác nhận **FC có phần cứng PMP 16 entry trong nhánh này**.
- Nhánh RI5CY trong **cluster** đặt `PULP_SECURE = 0`, nên không tạo cùng nhánh PMP. Không được khái quát PMP của FC thành bảo vệ cho mọi PE.
- Nhánh **Ibex FC** đang đặt `PMPEnable = 0`; đổi loại core có thể đổi luôn khả năng bảo vệ.
- `MMU_IMPLEMENTED` trong header top bị comment. Hệ thống được runtime sử dụng với địa chỉ vật lý; không có cơ sở để mô tả một cơ chế bộ nhớ ảo kiểu hệ điều hành Linux trong cấu hình đang xét.

Sự có mặt của PMP không chứng minh runtime đã cấu hình vùng và chạy ứng dụng ở mức đặc quyền hạn chế. Chính sách quyền truy cập còn phụ thuộc CSR, chế độ thực thi và implementation của revision này. PMP nằm trên đường truy cập CPU cũng không tự động kiểm soát uDMA, MCHAN hoặc HWPE; từng master cần được xét riêng.

Về lập trình, vẫn phải quản lý giới hạn buffer, stack, heap và đồng bộ truy cập. Ví dụ 8 stack × 4 KiB đã chiếm 32 KiB trong tổng L1 64 KiB; tăng mỗi stack lên 8 KiB sẽ không còn chỗ cho dữ liệu hoặc allocator.

Nguồn: [FC subsystem](../../.bender/git/checkouts/pulp_soc-c519334bd3ac5582/rtl/fc/fc_subsystem.sv), [riscv_core](../../.bender/git/checkouts/cv32e40p-0a3884e05ea5a482/rtl/riscv_core.sv), [core region của cluster](../../.bender/git/checkouts/pulp_cluster-48721e3ce381c984/rtl/core_region.sv).

## 3. Hạ tầng kết nối nội bộ và Bus (Interconnects / On-chip Buses)

### 3.1. Chuẩn giao tiếp bus nội chip (AMBA: AHB, APB, AXI)

Bus/interconnect chuyển yêu cầu của **master** như CPU, DMA đến **slave** như RAM và thanh ghi. Khi nhiều master cùng yêu cầu một tài nguyên, interconnect phân xử; khi slave chưa xử lý kịp, giao thức cho phép trì hoãn giao dịch.

AMBA là họ giao thức của Arm và có thể sử dụng trong SoC RISC-V. Ba tên trong đề cương có vai trò khác nhau:

- **AHB — Advanced High-performance Bus:** giao thức bus hệ thống với các pha địa chỉ và dữ liệu được pipeline. Đây là khái niệm đối chiếu; các đường kết nối chính được khảo sát của PULP không tổ chức quanh một bus AHB trung tâm.
- **APB — Advanced Peripheral Bus:** giao tiếp đơn giản cho thanh ghi điều khiển ngoại vi. Phù hợp truy cập cấu hình, không tối ưu cho khối dữ liệu lớn.
- **AXI — Advanced eXtensible Interface:** các kênh địa chỉ/dữ liệu/phản hồi riêng, hỗ trợ các giao dịch cần băng thông cao và burst tùy phiên bản/cấu hình.

Nguồn khái niệm: [tổng quan AMBA của Arm](https://www.arm.com/architecture/system-architectures/amba), [giới thiệu kênh AXI](https://developer.arm.com/documentation/102202/0300/Channel-).

**AXI trong PULP:** SoC và cluster liên kết qua AXI bất đồng bộ. Năm kênh gồm `AW` — địa chỉ ghi, `W` — dữ liệu ghi, `B` — phản hồi ghi, `AR` — địa chỉ đọc, `R` — dữ liệu/phản hồi đọc. Wrapper cluster đặt dữ liệu hướng cluster→SoC rộng 64 bit và SoC→cluster rộng 32 bit. Độ rộng này không biến CPU thành nhân 64 bit; bus có thể đóng gói hoặc chuyển đổi nhiều word.

Hai domain có thể chạy khác tần số. Các FIFO/adapter CDC dùng dữ liệu cùng read/write pointer để qua biên clock; việc đồng bộ chỉ một tín hiệu điều khiển không đủ cho cả giao dịch nhiều bit.

**APB trong PULP:** đường này cấu hình GPIO, timer, FLL, SoC control, uDMA và các khối tương ứng. Một lượt truy cập có pha setup, tiếp đến access với `PSEL/PENABLE`; slave trả `PREADY`, dữ liệu đọc `PRDATA` và tín hiệu lỗi khi có. Nếu một khối bị tắt clock hoặc không được instantiate, phần mềm không nên giả định cứ đọc thanh ghi là chắc chắn nhận được phản hồi hữu ích.

**TCDM/interconnect riêng của PULP:** đường CPU/DMA tới bank SRAM không phải mọi nơi đều là AXI hoặc APB. Interface như `XBAR_TCDM_BUS` có `req`, `gnt`, `add`, `wen`, `be`, `wdata`, `r_valid`, `r_rdata`. Cluster còn có HCI phục vụ kết nối tài nguyên không đồng nhất, gồm đường truy cập HWPE.

Ba ví dụ đường đi giúp phân biệt:

1. FC ghi cấu hình GPIO: FC → SoC interconnect → APB → GPIO → pad mux/pad.
2. PE đọc buffer L1: PE → interconnect TCDM → bank L1; có thể phải chờ nếu tranh chấp bank.
3. DMA nạp tile từ L2: MCHAN → AXI qua biên clock → SoC/L2; dữ liệu nhận được đưa vào L1 qua các cổng TCDM của DMA.

Nguồn: [top-level wiring](../../rtl/pulp/pulp.sv), [SoC interconnect](../../.bender/git/checkouts/pulp_soc-c519334bd3ac5582/rtl/pulp_soc/soc_interconnect.sv), [cluster implementation](../../.bender/git/checkouts/pulp_cluster-48721e3ce381c984/rtl/pulp_cluster.sv).

## 4. Cơ chế ngắt và Quản lý ngoại vi (Interrupts & Peripherals)

### 4.1. Bộ điều khiển ngắt (Interrupt Controller / NVIC)

Ngắt cho phép CPU phản ứng với timer, ngoại vi hoặc DMA mà không liên tục đọc trạng thái. Bộ điều khiển tiếp nhận nguồn ngắt, lưu trạng thái chờ, áp dụng mask và chọn yêu cầu gửi tới CPU. CPU chuyển đến handler, phần mềm xử lý và xác nhận/xóa nguyên nhân theo quy tắc của thiết bị.

**NVIC — Nested Vectored Interrupt Controller** là khối ngắt của Arm Cortex-M. Các cơ chế và API NVIC của CMSIS-Core không áp trực tiếp lên PULP RISC-V. Nguồn đối chiếu: [CMSIS-Core: NVIC](https://arm-software.github.io/CMSIS_6/latest/Core/group__NVIC__gr.html).

Trong PULP, ba lớp cần phân biệt:

- **FC interrupt controller:** `apb_interrupt_cntrl` trong `fc_subsystem`, nhận bus 32 nguồn `events_i`, tạo yêu cầu ngắt và ID 5 bit tới core; nhận acknowledge từ core. Khối này còn tham gia điều khiển clock/fetch của FC.
- **SoC event generator/unit:** thu nhận nhiều nguồn sự kiện từ uDMA, GPIO, timer… rồi định tuyến sự kiện tới FC, cluster hoặc phía ngoại vi qua mask/FIFO tương ứng. Một event ID không nhất thiết bằng số IRQ mà CPU nhìn thấy.
- **Cluster event unit:** hỗ trợ mỗi PE chờ sự kiện, đồng bộ barrier, mutex và dispatch. Nhờ đó các PE có thể dừng chờ công việc mà không quay vòng polling liên tục.

Ví dụ RTL `soc_peripherals.sv` nối timer thấp/cao tới FC IRQ 10/11, GPIO tới IRQ 15, advanced timer tới IRQ 17–20. Các số này thuộc cấu hình đang khảo sát, không phải số NVIC hay một bảng PLIC chuẩn.

**Event và interrupt không hoàn toàn giống nhau.** Event có thể đánh thức một core đang chờ để tiếp tục tại điểm hiện tại; interrupt đưa core vào trình phục vụ ngắt. HAL event unit cung cấp thao tác đặt mask, chờ và xóa sự kiện. Cần bật đúng mask trước khi chờ DMA/HWPE; nếu không, phần cứng đã xong mà chương trình vẫn ngủ.

Luồng xử lý điển hình: cấu hình thiết bị và handler → xóa trạng thái cũ theo đặc tả → bật đường định tuyến/mask và cho phép ngắt ở CPU → khởi chạy → handler xử lý/xác nhận nguồn → trở lại chương trình. Trình tự cụ thể phải tránh mất sự kiện giữa lần kiểm tra và lúc ngủ.

Nguồn: [FC interrupt controller](../../.bender/git/checkouts/apb_interrupt_cntrl-dd2e5ce27b208df0/apb_interrupt_cntrl.sv), [SoC peripherals](../../.bender/git/checkouts/pulp_soc-c519334bd3ac5582/rtl/pulp_soc/soc_peripherals.sv), [cluster runtime](../../pulp-runtime/kernel/cluster.c).

### 4.2. Giao diện ngoại vi (GPIO, UART, SPI, I2C, Timers, ADC, DAC)

**GPIO:** chân vào/ra số dùng đọc nút nhấn, cảm biến số hoặc điều khiển tín hiệu. Cần cấu hình hướng, chức năng pad và trạng thái xuất; đọc/ghi thanh ghi đúng nhưng pad mux sai thì chân ngoài vẫn không hoạt động như mong muốn. Wrapper SoC có đường GPIO 32 bit; macro `GPIO_NUM = 64` và số pad không phải bằng chứng có 64 GPIO sử dụng được ở giao diện này.

**UART:** truyền nối tiếp bất đồng bộ qua TX/RX, hai bên phải thống nhất baud rate và định dạng khung. SoC wrapper mặc định `N_UART = 1`; đường dữ liệu UART được tích hợp với uDMA. `printf` của bài mô phỏng có thể đi qua stdout MMIO thay vì chân UART, nên thấy log không đủ để kết luận TX/RX đã được kiểm thử.

**SPI:** giao tiếp đồng bộ với clock, chip select và các đường dữ liệu; thích hợp flash và ngoại vi tốc độ cao. Thiết kế có SPI master, wrapper mặc định `N_SPI = 1`, cùng đường dữ liệu nhiều bit cho các chế độ được controller hỗ trợ. Số controller, số chip-select và số dây dữ liệu là các đại lượng khác nhau.

**I2C:** bus hai dây SDA/SCL, dùng địa chỉ để chọn thiết bị. Đường dây cần được thiết kế với khả năng nhả mức và pull-up phù hợp. Wrapper đặt `N_I2C = 2`; controller kết nối uDMA, còn pad mux quyết định đường nào được đưa ra ngoài.

**Timers:** đếm xung để đo khoảng thời gian, phát ngắt định kỳ hoặc tạo tín hiệu. PULP có FC timer, timer phía cluster và advanced timer với các nhóm kênh output. Muốn đổi giá trị đếm thành thời gian phải biết nguồn clock, prescaler và chế độ đếm thực tế, không dùng mặc định tần số của CPU cho mọi timer.

**ADC — Analog-to-Digital Converter:** biến điện áp/tín hiệu tương tự thành số; các thông số thường gặp là độ phân giải, tốc độ lấy mẫu và điện áp tham chiếu. **DAC — Digital-to-Analog Converter:** biến mã số thành mức/tín hiệu tương tự. Trong top-level và SoC peripherals đã khảo sát **không thấy khối ADC hoặc DAC tích hợp với register map riêng**. Nếu bài toán cần thu/phát analog, phải dùng thiết bị ngoài hoặc bổ sung khối tích hợp thích hợp; SPI/I2C/I2S có thể làm đường nối tùy loại converter.

Các giao diện khác có trong wrapper gồm I2S, camera/CPI, SDIO và HyperBus. Có cổng RTL không đồng nghĩa thiết bị ngoài, pin FPGA, model mô phỏng và driver đều đã được cấu hình hoàn chỉnh.

Nguồn: [SoC wrapper và các cổng I/O](../../rtl/pulp/soc_domain.sv), [pad control](../../rtl/pulp/pad_control.sv), [SoC peripherals](../../.bender/git/checkouts/pulp_soc-c519334bd3ac5582/rtl/pulp_soc/soc_peripherals.sv).

### 4.3. Bộ điều khiển DMA (Direct Memory Access)

DMA chuyển dữ liệu sau khi CPU cấu hình, giúp CPU không phải thực hiện một cặp load/store cho từng word. CPU vẫn chịu trách nhiệm chọn địa chỉ, kích thước, hướng truyền, bảo đảm buffer hợp lệ và chờ hoàn thành trước khi dùng dữ liệu.

PULP có hai cơ chế chính:

- **uDMA phía SoC:** phục vụ truyền giữa ngoại vi và L2. Ví dụ UART RX ghi buffer trong L2, hoặc SPI TX lấy dữ liệu từ buffer L2. CPU cấu hình kênh và thiết bị; uDMA thực hiện truyền rồi phát sự kiện.
- **MCHAN/DMA phía cluster:** chuyển dữ liệu giữa L2 và L1 để nuôi các kernel tính toán. Wrapper có `NB_DMAS = 4`, tương ứng các cổng DMA hướng TCDM; không nên đọc thành đúng bốn bộ điều khiển DMA độc lập hay bốn kênh phần mềm.

Một luồng sử dụng điển hình là nạp một tile L2→L1, cho các PE xử lý, rồi chép kết quả L1→L2. **Double buffering** dùng hai buffer luân phiên để DMA nạp tile tiếp theo trong lúc CPU xử lý tile hiện tại; hiệu quả phụ thuộc tránh tranh chấp bank và không ghi đè buffer còn đang dùng.

Đợi cờ hoàn thành chỉ chứng minh transfer đã kết thúc theo controller, không chứng minh ứng dụng đã truyền đúng kích thước. Demo `full_system` kiểm tra dữ liệu sau lượt L2→L1→L2; phép thử ngược cắt ngắn lượt truyền để kiểm tra chương trình có phát hiện thiếu dữ liệu.

DMA cũng không thay thế đồng bộ nhiều core: trước khi tiêu thụ dữ liệu cần chờ transfer, đặt barrier khi cần và đảm bảo chỉ các core có trách nhiệm mới cập nhật descriptor/trạng thái chung.

Nguồn: [cluster wrapper](../../rtl/pulp/cluster_domain.sv), [demo full_system](../../sw/full_system/README.md), [mã demo](../../sw/full_system/full_system.c).

## 5. Hệ thống xung nhịp, Reset và Quản lý năng lượng (Clock, Reset & Power Management)

### 5.1. Nguồn xung nhịp và mạch Reset

Clock quy định thời điểm các phần tử tuần tự cập nhật trạng thái. Reset đưa logic điều khiển về trạng thái khởi tạo xác định; reset CPU không đồng nghĩa tự xóa mọi byte SRAM. Phần mềm startup vẫn cần thiết lập stack và khởi tạo dữ liệu theo cách nạp chương trình.

Thiết kế top chia ba domain:

- **Safe domain:** nhận reference clock/reset ngoài, xử lý các đường slow clock/reset và pad control cần cho hệ thống.
- **SoC domain:** FC, L2, ngoại vi và logic tạo/phân phối clock.
- **Cluster domain:** PE, L1, DMA, cache và event unit; có clock/reset riêng từ SoC.

Trong nhánh không phải FPGA, `soc_clk_rst_gen` instantiate ba **FLL — Frequency-Locked Loop** cho SoC, peripheral và cluster. FLL dùng clock tham chiếu và cấu hình để tạo tần số hoạt động, kèm trạng thái lock. Clock mux cho phép chọn các nguồn theo thiết kế; phần mềm phải phối hợp thay đổi tần số với các ngoại vi phụ thuộc clock.

Testbench đặt `REF_CLK_PERIOD = 30517 ns`, tương đương khoảng **32,77 kHz**. Đây là tần số tham chiếu mô phỏng, không phải tốc độ chạy lệnh của FC hay cluster.

Nhánh FPGA dùng khối tạo clock dành cho FPGA; mã nguồn ghi rõ FLL không được hỗ trợ theo cùng cách trong FPGA emulation. Vì vậy không thể coi thao tác ghi thanh ghi FLL trong mô phỏng ASIC là bằng chứng FPGA đã đổi tần số tương ứng.

Reset có các bước đồng bộ cho từng clock domain. Sau reset, core còn cần địa chỉ boot, clock hợp lệ và cho phép fetch. Runtime khởi động cluster bằng cách cấu hình boot address từng core qua cluster-control MMIO rồi bật mask fetch; chỉ quan sát một tín hiệu tên `cluster_fetch_enable` ở top-level là chưa đủ để khẳng định PE đã chạy.

Nguồn: [safe domain](../../rtl/pulp/safe_domain.sv), [clock/reset generator](../../.bender/git/checkouts/pulp_soc-c519334bd3ac5582/rtl/pulp_soc/soc_clk_rst_gen.sv), [testbench](../../rtl/tb/tb_pulp.sv), [cluster_start](../../pulp-runtime/kernel/cluster.c).

### 5.2. Các chế độ quản lý năng lượng và đánh thức

Ba cơ chế thường gặp là giảm tần số, **clock gating** — ngừng cấp xung cho khối chưa cần chạy, và **power gating** — ngắt nguồn của một miền. Clock gating giảm hoạt động chuyển mạch nhưng thường giữ trạng thái; power gating có thể làm mất trạng thái nếu không có retention. Đây là các cơ chế khác nhau.

Trong thiết kế đang xét:

- FC interrupt controller có điều khiển clock/fetch; cluster event unit hỗ trợ chờ sự kiện và điều khiển hoạt động core.
- DMA/uDMA có thể tiếp tục xử lý khi CPU không thực thi lệnh, nếu clock, bộ nhớ và đường interconnect cần thiết vẫn hoạt động.
- HWPE có điều khiển clock; demo cần bật clock HWPE trước khi truy cập/chờ kết quả.
- Clock SoC, peripheral và cluster có thể được quản lý riêng theo nhánh tạo clock được build.
- Wrapper cluster buộc `pmu_mem_pwdn_i = 0`. Một số tín hiệu power/control được xuất từ SoC không nối thành một đường điều khiển nguồn vật lý đầy đủ ở top. Vì vậy tài liệu này **không khẳng định có chế độ deep sleep cắt nguồn/retention hoàn chỉnh đã được kiểm chứng**.

Các tên Sleep, Stop, Standby quen thuộc ở MCU thương mại không phải bộ tên chế độ mặc định của repository này. Muốn mô tả một chế độ phải chỉ rõ core nào dừng, clock nào còn chạy, bộ nhớ nào giữ dữ liệu và sự kiện nào còn có thể đến được.

Đánh thức có thể dựa vào timer, sự kiện ngoại vi/uDMA, sự kiện phần mềm, barrier hoặc DMA hoàn thành tùy đường định tuyến. Quy trình thực tế là cấu hình nguồn sự kiện → mở mask đúng nơi → đưa core vào chờ bằng HAL → nguồn sự kiện phát → core được đánh thức hoặc vào handler. Nếu tắt luôn domain phát sự kiện hoặc domain vận chuyển sự kiện thì nguồn đó không còn hữu ích để đánh thức.

Ví dụ trong `cluster.c`, runtime mở mặc định các event dispatch, mutex và hardware barrier. Một accelerator cần event riêng phải được cấu hình thêm; không thể chỉ gọi hàm wait cho event chưa được mở mask.

Nguồn: [cluster runtime](../../pulp-runtime/kernel/cluster.c), [cluster wrapper](../../rtl/pulp/cluster_domain.sv), [ghi chú HWPE của demo](../../sw/full_system/README.md).

## 6. Môi trường phát triển phần mềm và Chuỗi công cụ (Software, Toolchain & HAL)

### 6.1. Chuỗi công cụ biên dịch (Toolchain & Linker Script)

Luồng biên dịch thông thường gồm tiền xử lý C/C++ → compiler → assembler tạo object → linker ghép object/runtime theo linker script → ELF để nạp/chạy/debug. `objdump` giúp xem disassembly, còn thông tin symbol/debug trong ELF liên kết địa chỉ máy với hàm và dòng nguồn.

Rule của target PULP hiện dùng `riscv32-unknown-elf-gcc`, `riscv32-unknown-elf-ar` và `riscv32-unknown-elf-objdump`. Nhánh mặc định đặt **`-march=rv32imcxgap9`**; nhánh `USE_CV32E40P` thêm `-mnohwloop`, nhánh `USE_IBEX` dùng `rv32imc`. Đây là cờ của toolchain/runtime đang có, không nên tự thay bằng một chuỗi ISA hiện đại mà chưa kiểm tra khả năng compiler và opcode RTL.

Linker dùng `-nostartfiles`, `-nostdlib`, `--gc-sections` và script riêng. Điều đó nghĩa là startup/runtime của PULP đảm nhiệm những phần mà môi trường chương trình desktop thường cung cấp sẵn.

Script `kernel/chips/pulp/link.ld` quyết định:

- Entry là `_start`.
- `L2`: origin `0x1C000004`, length `0x7FFFC`.
- `L1`: origin `0x10000004`, length `0xFFFC`.
- Vector ngắt được đặt từ ít nhất `0x1C008000`, có căn chỉnh.
- `.text`, `.data`, `.bss` chứa mã/dữ liệu theo rule; `.bss` cần được khởi tạo về 0 bởi startup.
- `.l2_data` đặt mã/dữ liệu dùng chung phía cluster ở vùng shared L2 từ ít nhất `0x1C010000`.
- `.l1cluster_g`, `.bss_l1` chứa dữ liệu L1; phần còn lại dùng làm heap, gồm cấp stack cluster.

Macro `L1_DATA` và `L2_DATA` giúp đưa biến vào section tương ứng. Chọn vị trí dữ liệu ảnh hưởng cả khả năng truy cập lẫn hiệu năng: dữ liệu cần PE truy cập dày đặc thường được đưa vào L1, còn buffer lớn và dữ liệu giao tiếp ngoại vi ở L2.

Nguồn: [rule target PULP](../../pulp-runtime/rules/pulpos/targets/pulp.mk), [linker script](../../pulp-runtime/kernel/chips/pulp/link.ld), [startup assembly](../../pulp-runtime/kernel/crt0.S).

### 6.2. Mô hình lập trình (Bare-metal & RTOS)

**Bare-metal** là ứng dụng chạy trực tiếp trên phần cứng với startup, driver và runtime cần thiết, không đòi hỏi một hệ điều hành quản lý tiến trình. Có runtime hoặc hỗ trợ đa nhân không đồng nghĩa đang chạy RTOS.

Luồng trong repository phù hợp mô hình **FC điều phối, cluster tính toán**:

1. FC khởi tạo runtime, buffer và ngoại vi.
2. Runtime cấu hình cluster, allocator L1, instruction cache và stack từng PE.
3. Ghi boot address và bật fetch cho các PE.
4. Các PE phân chia công việc theo core ID, dùng barrier/mutex/event khi cần.
5. DMA đưa dữ liệu giữa L2 và L1; FC thu nhận kết quả để tiếp tục xử lý hoặc xuất ra ngoại vi.

Trong `cluster_start()`, runtime cấp `ARCHI_CLUSTER_NB_PE × CLUSTER_STACK_SIZE`. Nếu cấp phát thất bại, hàm có đường trả về sớm; ứng dụng cần kiểm tra bằng chứng cluster thực sự đã chạy. Demo dùng sentinel và gom lỗi của mọi core, vì đường kết quả runtime chỉ lấy giá trị trả về của core 0.

**RTOS — Real-Time Operating System** bổ sung task, scheduler, cơ chế chờ/đánh thức, timer và đồng bộ để đáp ứng yêu cầu thời gian. Muốn chạy một RTOS trên hệ thống này cần port chuyển ngữ cảnh RISC-V, ngắt/tick, quản lý stack và chính sách FC/cluster. Không có cơ sở từ demo hiện tại để khẳng định FreeRTOS hoặc một RTOS cụ thể đã được tích hợp và kiểm chứng.

Không được suy ra ngữ nghĩa bộ nhớ kiểu máy tính SMP có cache coherent chỉ vì có tám core. Phần mềm PULP quản lý vùng nhớ và đồng bộ rõ ràng; `volatile` không biến phép cộng vào biến chung thành atomic.

Nguồn: [cluster.c](../../pulp-runtime/kernel/cluster.c), [full_system README](../../sw/full_system/README.md), [Makefile demo](../../sw/full_system/Makefile).

### 6.3. Lớp trừu tượng phần cứng (HAL & CMSIS)

**HAL — Hardware Abstraction Layer** gói thao tác CSR/MMIO thành các hàm có tên theo chức năng, giúp ứng dụng bớt phụ thuộc vào offset và bitfield. Trong runtime này:

- `include/archi`: định nghĩa kiến trúc, địa chỉ và bitfield theo chip/IP.
- `include/hal`: thao tác thanh ghi, event unit, DMA, cache, timer và các phần khác.
- `drivers` và `kernel`: ghép các thao tác thấp thành driver, khởi tạo, cấp phát và điều phối cluster.

Ví dụ API đang có gồm `hal_core_id()`, `hal_cluster_id()`, `eu_evt_maskSet()`, `eu_bar_trig_wait_clr()`, `cluster_start()` và `cluster_wait()`. Cần phân biệt hàm HAL thao tác trực tiếp phần cứng với hàm runtime quản lý một quy trình nhiều bước.

**CMSIS — Common Microcontroller Software Interface Standard** là họ giao diện/phần mềm của Arm. Phần CMSIS-Core với header Cortex-M, NVIC và SysTick phục vụ kiến trúc Arm; các lời gọi như `NVIC_EnableIRQ()` không phải API native của PULP. Với repository này, vai trò tương ứng ở mức truy cập phần cứng do header `archi`, HAL RISC-V/PULP và runtime đảm nhiệm. Nguồn đối chiếu: [CMSIS-Core API](https://arm-software.github.io/CMSIS_6/latest/Core/modules.html).

HAL vẫn phải đúng phiên bản IP. Một tên hàm có thể tồn tại trong source nhưng bị loại khỏi build: demo hiện ghi GPIO trực tiếp vì HAL GPIO liên quan nằm trong `#if 0`. Khi thiếu API, phải dựa vào register map đã kiểm chứng để viết wrapper nhỏ, không mượn thanh ghi từ MCU khác.

Nguồn: [HAL RISC-V](../../pulp-runtime/include/hal/riscv/riscv_v5.h), [memory map runtime](../../pulp-runtime/include/archi/chips/pulp/memory_map.h), [ghi chú HAL GPIO](../../sw/full_system/README.md).

### 6.4. Công cụ gỡ lỗi (Debugging & Trace)

**Debug phần mềm** dùng ELF, symbol và debugger để đặt breakpoint, xem thanh ghi, bộ nhớ, stack và thực thi từng bước. Thiết kế có JTAG DTM cho RISC-V debug và PULP TAP phục vụ truy cập bus. Testbench hỗ trợ nạp chương trình qua JTAG, boot từ flash ở chế độ standalone hoặc chờ OpenOCD kết nối.

Luồng tương tác là GDB → OpenOCD → JTAG/remote bitbang → debug module → hart và bộ nhớ. Với nhiều core phải chọn đúng hart; dừng một PE ở giữa barrier có thể khiến các PE khác chờ, nên trạng thái treo quan sát được cần được hiểu trong bối cảnh debug.

**Debug RTL** dùng QuestaSim/ModelSim, waveform và các signal nội bộ. Một thứ tự kiểm tra hữu ích:

1. Clock và reset của domain cần chạy.
2. Boot address, fetch enable, PC của FC/PE.
3. Request/grant và response trên interconnect.
4. Địa chỉ, kích thước và trạng thái DMA.
5. Event mask, event pending và đường acknowledge.
6. Dữ liệu bộ nhớ, stack và kết quả tính toán.

**Trace** ghi lại diễn biến theo thời gian thay vì chỉ xem một trạng thái khi dừng. Repository có hook `TRACE_EXECUTION` ở một số nhánh FPGA và có thể quan sát PC/lệnh trong mô phỏng. Hook có điều kiện không có nghĩa mọi bản build đều cung cấp một trace port ngoài chip; cũng không phải Arm ETM/CoreSight.

**Bộ đếm hiệu năng** giúp xem số chu kỳ và các sự kiện liên quan đến thực thi/bộ nhớ. Khi so sánh kernel cần giữ cùng cấu hình clock, số core, vị trí dữ liệu và phạm vi đo; thời gian mô phỏng trên máy chủ không phải thời gian xử lý của phần cứng.

Để tham khảo cách build/chạy bài demo hiện có, từ thư mục gốc repository:

```bash
cd sw/full_system
./run_sim.sh all   # Chỉ build phần mềm bằng môi trường do script chuẩn bị
./run_sim.sh       # Build và chạy theo luồng mô phỏng của demo
```

Các lệnh này cần toolchain, thư viện mô phỏng và Questa được chuẩn bị như README của demo; đây là hướng dẫn sử dụng, không phải kết quả một lần chạy mới trong quá trình viết tài liệu này. Kiểm tra thành công nên gồm dữ liệu đúng, bằng chứng đủ 8 PE hoạt động và exit status của testbench, thay vì chỉ tìm một dòng `SUCCESS`.

Nguồn: [testbench README](../../rtl/tb/README.md), [testbench thực tế](../../rtl/tb/tb_pulp.sv), [script demo](../../sw/full_system/run_sim.sh), [tiêu chí PASS của demo](../../sw/full_system/README.md).

## Nguồn và cách đối chiếu tiếp

Ưu tiên đọc theo thứ tự: **tham số testbench/target → top-level wiring → dependency RTL được compile → header runtime → linker → chương trình kiểm thử**. README tổng quát có thể mô tả một cấu hình khác với nhánh build đang chạy.

- [Bender.yml](../../Bender.yml) và [Bender.lock](../../Bender.lock): khai báo/khóa dependency; đường dẫn cache trong tài liệu là đường dẫn đang tồn tại tại thời điểm viết và có thể đổi ở checkout khác.
- [pulp.sv](../../rtl/pulp/pulp.sv), [soc_domain.sv](../../rtl/pulp/soc_domain.sv), [cluster_domain.sv](../../rtl/pulp/cluster_domain.sv): ranh giới và kết nối hệ thống.
- [soc_mem_map.svh](../../rtl/includes/soc_mem_map.svh): các cửa sổ địa chỉ SoC.
- [memory_map.h](../../pulp-runtime/include/archi/chips/pulp/memory_map.h), [link.ld](../../pulp-runtime/kernel/chips/pulp/link.ld): góc nhìn phần mềm và ngân sách bộ nhớ được sử dụng.
- [full_system](../../sw/full_system/README.md): ví dụ kết nối các chủ đề bằng chương trình có FC, 8 PE, L1/L2, DMA, HWPE, GPIO và timer.

Phạm vi xác minh của tài liệu là đọc và đối chiếu mã nguồn/cấu hình hiện có. Các ví dụ dựa trên báo cáo cũ được dẫn nguồn ở đúng mục; tài liệu không thay thế kết quả synthesis, đo điện năng hay kiểm thử toàn bộ chế độ trên FPGA.
