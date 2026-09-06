# Nhật ký xây dựng và mô phỏng PULP bằng QuestaSim

## 1. Mục tiêu và kết quả cuối cùng

Mục tiêu của quá trình này là chạy một mô phỏng RTL hoàn chỉnh của hệ thống PULP bằng QuestaSim, sử dụng chương trình phần mềm `hello` làm smoke test.

Kết quả cuối cùng đã quan sát được:

```text
[TB] 4729101ns - Waiting for end of computation
[STDOUT-CL31_PE0] Hello !
[TB] 5387801ns - Received status core: 0x00000000
```

Điều này chứng minh chương trình đã được nạp vào mô hình RTL, CPU bắt đầu thực thi, xuất được chuỗi `Hello !` và trả về mã trạng thái thành công.

Tuy nhiên, một số lần chạy QuestaSim 10.7c vẫn xuất hiện bốn lỗi nội bộ `vsim-191`. Vì vậy kết luận chính xác là:

> Test `hello` đã pass về mặt chức năng, nhưng phiên mô phỏng chưa hoàn toàn sạch do lỗi nội bộ của simulator cũ trên môi trường Linux hiện tại.

---

## 2. Mô phỏng này đang mô phỏng cái gì?

### Đối tượng được mô phỏng

Đây không phải là mô phỏng riêng một CPU hoặc một module nhỏ. Top-level testbench là:

```text
rtl/tb/tb_pulp.sv
```

Testbench instantiate DUT PULP và các thành phần phục vụ mô phỏng. Ở mức chức năng, phiên mô phỏng bao gồm:

- PULP SoC RTL.
- Fabric/interconnect và các interface nội bộ.
- Bộ xử lý điều khiển của hệ thống.
- Cluster và các core được cấu hình trong PULP checkout.
- L2 memory và các memory model cần cho testbench.
- Debug/JTAG infrastructure dùng để nạp chương trình và đọc trạng thái.
- Testbench output/status mechanism.
- Các model ngoại vi phục vụ simulation.

Snapshot đã optimize và thực sự được QuestaSim chạy là:

```text
sim/work/vopt_tb
```

Top-level trong snapshot là `tb_pulp`.

### Test đang kiểm tra điều gì?

Test phần mềm được sử dụng là:

```text
regression_tests/hello
```

Source chính của ứng dụng:

```text
regression_tests/hello/test.c
```

Đây là một smoke test end-to-end. Nó kiểm tra cả chuỗi hoạt động:

1. PULP GCC compile được ứng dụng cho đúng ISA PULP.
2. Runtime và linker tạo được ELF chạy trên PULP.
3. Công cụ stimulus đọc được ELF và tạo vector memory.
4. Testbench nạp chương trình vào mô hình PULP bằng debug/JTAG.
5. Core thoát reset và bắt đầu fetch từ entry point.
6. Instruction và data interface hoạt động đủ để chương trình chạy.
7. Chương trình xuất được `Hello !` qua cơ chế stdout của testbench.
8. Chương trình báo hoàn thành với status bằng 0.

Test này không chứng minh rằng:

- Toàn bộ peripheral của PULP đều đúng.
- Tất cả core trong cluster đều đã được kiểm thử.
- Các protocol corner case đã được cover.
- RTL đạt timing trên FPGA hoặc ASIC.
- UART vật lý đã truyền `Hello !` trên pin.

Dòng `[STDOUT-CL31_PE0] Hello !` là output do môi trường mô phỏng thu nhận. Không nên tự động coi nó là một bài kiểm tra UART pin-level nếu chưa xác nhận đường UART trong testbench.

### Luồng dữ liệu của test

```text
test.c
  -> PULP GCC + pulp-runtime
  -> build/test/test             (ELF)
  -> stim_utils.py
  -> build/vectors/stim.txt      (memory stimulus)
  -> tb_pulp + LOAD_L2=JTAG
  -> PULP RTL executes at 0x1c008080
  -> Hello !
  -> completion status = 0
```

### Những file chính tham gia flow

| Vai trò | File/thư mục |
|---|---|
| Source ứng dụng | `regression_tests/hello/test.c` |
| Makefile ứng dụng | `regression_tests/hello/Makefile` |
| Build rule của runtime | `pulp-runtime/install/rules/pulp_rt.mk` |
| ELF được tạo | `regression_tests/hello/build/test/test` |
| Tool đọc ELF | `pulp-runtime/bin/stim_utils.py` |
| Memory stimulus | `regression_tests/hello/build/vectors/stim.txt` |
| SPI flash stimulus | `regression_tests/hello/build/vectors/qspi_stim.slm` |
| HyperBus stimulus | `regression_tests/hello/build/vectors/hyper_stim.slm` |
| Top-level testbench | `rtl/tb/tb_pulp.sv` |
| JTAG simulation module | `rtl/tb/SimJTAG.sv` |
| JTAG packages | `rtl/tb/jtag_pkg.sv`, `rtl/tb/pulp_tap_pkg.sv`, `rtl/tb/dbg_pkg.sv` |
| Remote-bitbang DPI source | `rtl/tb/remote_bitbang/remote_bitbang.c`, `sim_jtag.c` |
| Remote-bitbang library | `rtl/tb/remote_bitbang/librbs.so` |
| Bender-generated source list | `sim/compile.tcl` |
| Questa library configuration | `sim/modelsim.ini` |
| Compiled/optimized design | `sim/work/vopt_tb` |
| Tcl cấu hình simulator | `sim/tcl_files/config/vsim.tcl` |
| Tcl điều khiển run | `sim/tcl_files/run.tcl`, `sim/tcl_files/config/run_and_exit.tcl` |

---

# Giai đoạn 1 — Xác định simulator, license và repository

## Mục tiêu

Trước khi build, cần xác minh ba yếu tố độc lập:

- QuestaSim đã được cài.
- QuestaSim thực sự checkout được license.
- Đang làm việc trên đúng repository PULP top-level.

## Kiểm tra simulator

```bash
# Locate the installed QuestaSim executables.
type -a vsim
type -a vlog

# Display the installed simulator versions.
vsim -version 2>&1 | head -n 10
vlog -version 2>&1 | head -n 10

# Perform a real license checkout and exit immediately.
vsim -c -do 'quit -f' </dev/null
```

Đã xác nhận QuestaSim 10.7c tại `/home/dungpc/questasim`. `vsim -version` chỉ xác nhận executable tồn tại; lệnh console cuối mới thực sự kiểm tra license.

## Khôi phục license

License chứa:

```text
SERVER dungpc-ThinkPad-P1-Gen-4i f4a475365100 27001
VENDOR mgcld
```

Host ID và hostname đều khớp. Nguyên nhân lỗi ban đầu là `lmgrd`/`mgcld` chưa chạy và không có process lắng nghe cổng 27001.

```bash
# Define the QuestaSim installation and license locations.
export QUESTA_HOME="$HOME/questasim"
export QUESTA_LICENSE_FILE="$QUESTA_HOME/LICENSE.dat"
export QUESTA_LICENSE_LOG="$QUESTA_HOME/license_server.log"

# Start the FlexNet server when it is not already running.
if ! pgrep -x lmgrd >/dev/null; then
    "$QUESTA_HOME/linux_x86_64/lmgrd" \
        -c "$QUESTA_LICENSE_FILE" \
        -l "$QUESTA_LICENSE_LOG"
fi

# Point QuestaSim to the running local license server.
export LM_LICENSE_FILE=27001@localhost
export MGLS_LICENSE_FILE=27001@localhost

# Verify the server and perform a simulator checkout.
"$QUESTA_HOME/linux_x86_64/lmutil" lmstat -a -c 27001@localhost
vsim -c -do 'quit -f' </dev/null
```

## Xác định repository

Repository top-level đúng là:

```text
/home/dungpc/ndmoney4porche/projects/pulp
```

Thiết lập biến dùng xuyên suốt:

```bash
# Define the top-level PULP repository.
export PULP_PROJECT_HOME="$HOME/ndmoney4porche/projects/pulp"
```

Repository được nhận diện bằng Git remote thay vì đoán đường dẫn. Cần giữ nguyên các file untracked hoặc thay đổi cục bộ không liên quan.

---

# Giai đoạn 2 — Chuẩn bị và compile RTL PULP

## Nạp môi trường và dependency

```bash
# Leave Conda to reduce host-library conflicts with EDA tools.
conda deactivate 2>/dev/null || true
hash -r

# Enter the PULP repository and select the license server.
cd "$PULP_PROJECT_HOME"
export LM_LICENSE_FILE=27001@localhost
export MGLS_LICENSE_FILE=27001@localhost

# Load the repository's QuestaSim environment.
source setup/vsim.sh

# Increase the open-file limit for dependency generation and compilation.
ulimit -n 4096

# Download pinned dependencies and regenerate simulation scripts.
make checkout
make scripts
```

File quan trọng được sinh cho QuestaSim là `sim/compile.tcl`. Nó chứa danh sách và thứ tự compile các package, interface, RTL module và testbench mà Bender chọn từ dependency lock của repository.

## Tạo library configuration

Build ban đầu thất bại vì target clean xóa `modelsim.ini`. Thứ tự đúng đã dùng:

```bash
# Enter the simulator build directory and clean first.
cd "$PULP_PROJECT_HOME/sim"
make clean

# Create the local QuestaSim configuration after cleaning.
vmap -c

# Create and map the work library.
make lib
```

Không chạy `make clean` sau `vmap -c`, nếu không `modelsim.ini` vừa tạo sẽ bị xóa.

## Build remote-bitbang DPI library

QuestaSim cần `librbs.so` để cung cấp `jtag_tick`, `rbs_init` và `rbs_done`. GCC mới báo `multiple definition` do mã C cũ định nghĩa global variables trong header.

```bash
# Clean the failed remote-bitbang library build.
make -C "$PULP_PROJECT_HOME/rtl/tb/remote_bitbang" clean

# Build the legacy C sources with common-symbol compatibility.
make -C "$PULP_PROJECT_HOME/rtl/tb/remote_bitbang" all \
    CFLAGS="-Wall -Wextra \
    -Wno-missing-field-initializers \
    -Wno-unused-function \
    -Wno-missing-braces \
    -O2 -g -march=native \
    -DENABLE_LOGGING -DNDEBUG \
    -fcommon"

# Verify the generated DPI library and exported functions.
file "$PULP_PROJECT_HOME/rtl/tb/remote_bitbang/librbs.so"
nm -D --defined-only "$PULP_PROJECT_HOME/rtl/tb/remote_bitbang/librbs.so" |
    grep -E ' (jtag_tick|rbs_init|rbs_done)$'
```

Workaround bền vững là thêm `-fcommon` vào CFLAGS trong `rtl/tb/remote_bitbang/Makefile`. Cách sửa C đúng hơn là dùng `extern` trong header và chỉ định nghĩa mỗi global một lần trong file `.c`.

## Compile và optimize testbench

```bash
# Compile all PULP RTL and testbench sources.
cd "$PULP_PROJECT_HOME/sim"
make build

# Optimize the compiled tb_pulp design.
make opt
```

Kết quả:

```text
Optimized design name is vopt_tb
Errors: 0, Warnings: 23, Suppressed Warnings: 508
```

Các artifact chính sau giai đoạn này:

```text
sim/modelsim.ini
sim/work/
sim/work/vopt_tb/
rtl/tb/remote_bitbang/librbs.so
```

---

# Giai đoạn 3 — Chuẩn bị PULP GCC và build chương trình `hello`

## Chọn đúng compiler

Các RISC-V GCC generic trên máy chấp nhận một số ISA option nhưng không hỗ trợ builtin `__builtin_pulp_OffsetedRead`. Toolchain được chọn là:

```text
/home/dungpc/ndmoney4porche/tools/v1.0.16-pulp-riscv-gcc-ubuntu-16
```

```bash
# Select the PULP-specific RISC-V GCC toolchain.
export PULP_RISCV_GCC_TOOLCHAIN="$HOME/ndmoney4porche/tools/v1.0.16-pulp-riscv-gcc-ubuntu-16"
export PULP_RISCV_GCC_TOOLCHAIN_CI="$PULP_RISCV_GCC_TOOLCHAIN"
export CROSS_COMPILE="$PULP_RISCV_GCC_TOOLCHAIN/bin/riscv32-unknown-elf-"
export PATH="$PULP_RISCV_GCC_TOOLCHAIN/bin:$PATH"

# Add private compatibility libraries required by the old GCC binary.
export LD_LIBRARY_PATH="$PULP_RISCV_GCC_TOOLCHAIN/compat-libs/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"

# Verify the selected compiler.
riscv32-unknown-elf-gcc --version
```

Toolchain Ubuntu 16 cần `libmpfr.so.4` và `libisl.so.15`, đã được giải nén cục bộ dưới `compat-libs` thay vì cài đè thư viện hệ thống.

## Runtime và Makefile của test

`regression_tests/hello/Makefile` khai báo ứng dụng `test`, source `test.c` và include:

```make
include $(PULP_SDK_HOME)/install/rules/pulp_rt.mk
```

Do đó phải đặt:

```bash
# Point legacy build rules to the checked-out PULP runtime.
export PULP_SDK_HOME="$PULP_PROJECT_HOME/pulp-runtime"
export PULP_RUNTIME_HOME="$PULP_PROJECT_HOME/pulp-runtime"
```

Nếu `PULP_SDK_HOME` rỗng, Make sẽ tìm sai `/install/rules/pulp_rt.mk`.

## Sửa compatibility của Python tools

`stim_utils.py` cần `pyelftools`:

```bash
# Install and verify pyelftools for the system Python interpreter.
sudo apt install -y python3-pyelftools
/usr/bin/python3 -c \
    'from elftools.elf.elffile import ELFFile; print("RESULT: system pyelftools works.")'
```

`pulp-runtime/bin/slm_hyper.py` dùng mode `rU` đã bị loại bỏ khỏi Python mới. Thay bằng:

```python
# Open the SLM input using modern Python text mode.
with open(args.input_file, "r") as fi:
```

Sau khi build/test preparation thành công, các file được tạo:

```text
regression_tests/hello/build/test/test
regression_tests/hello/build/vectors/stim.txt
regression_tests/hello/build/vectors/qspi_stim.slm
regression_tests/hello/build/vectors/hyper_stim.slm
```

Hai file trực tiếp quan trọng cho flow hiện tại:

- `build/test/test`: ELF chứa code, data, symbol và entry point.
- `build/vectors/stim.txt`: nội dung ELF đã được chuyển thành stimulus để nạp memory của mô hình.

---

# Giai đoạn 4 — Chạy mô phỏng PULP `hello`

Đây là giai đoạn trung tâm của workflow.

## Chuẩn bị đầy đủ môi trường

Mỗi terminal mới cần khôi phục simulator, license, runtime và compiler. Chỉ `source setup/vsim.sh` là chưa đủ.

```bash
# Leave Conda to avoid mixing EDA tools with Conda libraries.
conda deactivate 2>/dev/null || true
hash -r

# Define project, simulator and compiler locations.
export PULP_PROJECT_HOME="$HOME/ndmoney4porche/projects/pulp"
export QUESTA_HOME="$HOME/questasim"
export PULP_RISCV_GCC_TOOLCHAIN="$HOME/ndmoney4porche/tools/v1.0.16-pulp-riscv-gcc-ubuntu-16"

# Configure the PULP runtime and cross compiler.
export PULP_SDK_HOME="$PULP_PROJECT_HOME/pulp-runtime"
export PULP_RUNTIME_HOME="$PULP_PROJECT_HOME/pulp-runtime"
export PULP_RISCV_GCC_TOOLCHAIN_CI="$PULP_RISCV_GCC_TOOLCHAIN"
export CROSS_COMPILE="$PULP_RISCV_GCC_TOOLCHAIN/bin/riscv32-unknown-elf-"
export PATH="$PULP_RISCV_GCC_TOOLCHAIN/bin:$QUESTA_HOME/bin:$PATH"
export LD_LIBRARY_PATH="$PULP_RISCV_GCC_TOOLCHAIN/compat-libs/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"

# Select the running local license server.
export LM_LICENSE_FILE=27001@localhost
export MGLS_LICENSE_FILE=27001@localhost

# Load repository-specific simulator settings.
cd "$PULP_PROJECT_HOME"
source setup/vsim.sh

# Set PULPRT_HOME and PULPRT_TARGET, required by rules/pulp.mk.
source pulp-runtime/configs/pulp.sh

# Restore variables referenced directly by legacy Makefiles.
export PULP_SDK_HOME="$PULP_PROJECT_HOME/pulp-runtime"
export PULP_RUNTIME_HOME="$PULP_PROJECT_HOME/pulp-runtime"

# Verify the three critical runtime dependencies.
vsim -c -do 'quit -f' </dev/null
riscv32-unknown-elf-gcc --version
/usr/bin/python3 -c 'from elftools.elf.elffile import ELFFile'
```

## Chạy bằng Makefile

```bash
# Enter the hello regression directory.
cd "$PULP_PROJECT_HOME/regression_tests/hello"

# Build software artifacts and run the RTL simulation.
make run
```

Flow bên trong gồm:

1. Compile `test.c` cùng PULP runtime.
2. Tạo ELF `build/test/test`.
3. Chạy `stim_utils.py` để tạo `build/vectors/stim.txt`.
4. Tạo QSPI/Hyper stimulus theo rule của runtime.
5. Chuyển working directory sang `regression_tests/hello/build`.
6. Khởi động QuestaSim với snapshot `vopt_tb`.
7. Truyền `ENTRY_POINT=0x1c008080`.
8. Chọn `LOAD_L2=JTAG`.
9. Nạp chương trình vào mô hình PULP.
10. Chạy RTL tới khi testbench nhận completion status.

## Ý nghĩa của `LOAD_L2=JTAG`

Generic `LOAD_L2=JTAG` cho biết testbench dùng đường JTAG/debug để chuẩn bị L2 memory và điều khiển boot/run.

Các dòng `retrying debug reg access` chưa phải failure nếu testbench vẫn tiến tới:

```text
Waiting for end of computation
```

Chúng chỉ trở thành vấn đề nếu lặp vô hạn.

## Entry point và thực thi

Entry point của chương trình là:

```text
0x1c008080
```

Sau khi nạp chương trình, cần có:

- Core reset được deassert.
- Fetch enable được bật.
- PC tới `0x1c008080`.
- Instruction request nhận grant và response.
- `instr_rdata` xác định khi `instr_rvalid=1`.
- PC tiếp tục thay đổi.
- Data interface có các giao dịch cần thiết cho chương trình.

## Cách testbench quyết định pass/fail

Completion logic nằm trong `rtl/tb/tb_pulp.sv`. Testbench poll debug address:

```text
0x1A1040A0
```

Sau đó:

- Bit 31 bằng 1 báo computation đã kết thúc.
- Bits `[30:0]` bằng 0 báo success.
- Bits `[30:0]` khác 0 báo failure.
- Testbench in status và gọi `$stop` tại dòng 1008.

Giá trị raw hợp lệ nhiều khả năng là `0x80000000`; log chỉ in 31 bit thấp nên hiển thị `0x00000000`.

## Tiêu chí pass

Không nên chỉ nhìn exit status của Make. Functional pass cần đồng thời có:

```text
[STDOUT-CL31_PE0] Hello !
[TB] ... Received status core: 0x00000000
```

và không có `$fatal` hay testbench failure trước completion. `$stop` ở cuối là hành vi chủ động của testbench.

```bash
# Check functional markers and simulator errors together.
grep -nE \
    'Hello !|Waiting for end of computation|Received status core|Fatal:|Error:|Errors:' \
    pulp_hello_run.log
```

Kết quả đã chứng minh đường build firmware → tạo stimulus → nạp L2 → CPU thực thi → stdout → completion status hoạt động.

---

# Giai đoạn 5 — Mở GUI, xem waveform và đánh giá kết quả

## Mở QuestaSim GUI

`make run gui=1` không hoạt động ổn định với Makefile/runtime cũ. Ngoài ra, command Tcl từng thiếu `-sv_lib`, dẫn đến cảnh báo không tìm thấy `jtag_tick`. Vì vậy sử dụng lệnh trực tiếp:

```bash
# Enter the directory containing the generated memory stimuli.
cd "$PULP_PROJECT_HOME/regression_tests/hello/build"

# Start the optimized PULP testbench in QuestaSim GUI mode.
vsim -64 -gui \
    -modelsimini "$PULP_PROJECT_HOME/sim/modelsim.ini" \
    vopt_tb \
    -L models_lib \
    -L vip_lib \
    -t ps \
    -sv_lib "$PULP_PROJECT_HOME/rtl/tb/remote_bitbang/librbs" \
    -permit_unmatched_virtual_intf \
    +ENTRY_POINT=0x1c008080 \
    +VSIM_PATH="$PULP_PROJECT_HOME/sim" \
    -gBAUDRATE=115200 \
    -gLOAD_L2=JTAG \
    -gENABLE_DEV_DPI=0
```

Working directory là `hello/build` vì tại đây có `vectors/stim.txt`. `modelsim.ini` được chỉ rõ để Questa tìm đúng work library và `vopt_tb`.

Trong transcript nên có:

```text
Loading .../rtl/tb/remote_bitbang/librbs.so
```

và không nên còn cảnh báo `vsim-3770` về `jtag_tick`.

## Thời điểm xem waveform

Khoảng quan trọng nhất của lần chạy hiện tại là:

```text
4.65 ms đến 5.39 ms
```

| Giai đoạn | Khoảng thời gian | Nội dung cần kiểm tra |
|---|---:|---|
| Reset/khởi tạo | Từ 0 đến khi reset nhả | Clock hoạt động, reset nhả sạch |
| Nạp/debug JTAG | Trước khoảng 4.729 ms | TCK/TMS/TDI/TDO hoạt động, debug access tiến triển |
| Bắt đầu thực thi | Khoảng 4.729 ms | Fetch enable bật, PC tới `0x1c008080` |
| Chạy ứng dụng | 4.729–5.388 ms | Instruction/data handshake, PC tiến triển |
| Completion | Khoảng 5.387801 ms | Done bit, status 0 và `$stop` |

```tcl
# Run to just before firmware execution begins.
run 4.65 ms

# Run across the transition from JTAG loading to execution.
run 200 us

# Continue until the testbench stops at completion.
run -all
```

## Nhóm tín hiệu cần xem

- Clock/reset: reference clock, SoC/core clock, reset, fetch enable, core busy.
- JTAG: `s_tck`, `s_tms`, `s_tdi`, `s_tdo`, `s_trstn`, `jtag_data`.
- Instruction: PC, `instr_req`, `instr_gnt`, `instr_rvalid`, `instr_addr`, `instr_rdata`.
- Data: `data_req`, `data_gnt`, `data_rvalid`, `data_addr`, `data_we`, `data_be`, `data_wdata`, `data_rdata`.
- Completion: `exit_status`, EOC/status và debug access tới `0x1A1040A0`.

Điều kiện bus tối thiểu:

- Request nhận được grant.
- Read nhận được response valid.
- Read data xác định khi valid.
- PC có tiến triển.
- Không có request treo vô hạn.

## Trạng thái chưa sạch

Một số run vẫn có:

```text
Error: (vsim-191) Questa has encountered an unexpected internal error
```

Vì vậy phải ghi kết quả theo hai lớp:

- **Functional result:** pass.
- **Simulator transcript cleanliness:** chưa pass.

Hướng điều tra tiếp là chạy QuestaSim mới hơn, chạy 10.7c trên hệ điều hành tương thích hơn, hoặc so sánh run có/không có remote-bitbang DPI.

---

# Phụ lục A — Các file được tạo hoặc sửa

## File được sinh tự động

| File | Nguồn tạo | Mục đích |
|---|---|---|
| `sim/compile.tcl` | `make scripts`/Bender | Danh sách và thứ tự compile Questa |
| `sim/modelsim.ini` | `vmap -c` | Ánh xạ library Questa |
| `sim/work/` | `make build` | Compiled design units |
| `sim/work/vopt_tb/` | `make opt` | Optimized simulation snapshot |
| `rtl/tb/remote_bitbang/librbs.so` | Remote-bitbang Makefile | DPI implementation cho JTAG |
| `regression_tests/hello/build/test/test` | PULP GCC/runtime | Firmware ELF |
| `regression_tests/hello/build/vectors/stim.txt` | `stim_utils.py` | L2 memory stimulus |
| `regression_tests/hello/build/vectors/qspi_stim.slm` | `plp_mkflash` | QSPI stimulus |
| `regression_tests/hello/build/vectors/hyper_stim.slm` | `slm_hyper.py` | HyperBus stimulus |

## File đã cần patch hoặc cấu hình

| File/khu vực | Thay đổi | Lý do |
|---|---|---|
| `rtl/tb/remote_bitbang/Makefile` hoặc command CFLAGS | Thêm `-fcommon` | Tương thích GCC mới |
| `pulp-runtime/bin/slm_hyper.py` | Đổi `rU` thành `r` | Tương thích Python mới |
| Shell environment | License, PULP GCC, runtime, `LD_LIBRARY_PATH` | Khôi phục đầy đủ môi trường |

Không nên commit bừa các file build/generated. Trước khi commit patch source hoặc Makefile, cần kiểm tra `git diff` và xác nhận đây là thay đổi có chủ đích.

---

# Phụ lục B — Checklist chạy lại nhanh

```bash
# Leave Conda to avoid host-library conflicts.
conda deactivate 2>/dev/null || true
hash -r

# Define project and tool locations.
export PULP_PROJECT_HOME="$HOME/ndmoney4porche/projects/pulp"
export QUESTA_HOME="$HOME/questasim"
export PULP_RISCV_GCC_TOOLCHAIN="$HOME/ndmoney4porche/tools/v1.0.16-pulp-riscv-gcc-ubuntu-16"

# Configure the runtime and PULP cross compiler.
export PULP_SDK_HOME="$PULP_PROJECT_HOME/pulp-runtime"
export PULP_RUNTIME_HOME="$PULP_PROJECT_HOME/pulp-runtime"
export PULP_RISCV_GCC_TOOLCHAIN_CI="$PULP_RISCV_GCC_TOOLCHAIN"
export CROSS_COMPILE="$PULP_RISCV_GCC_TOOLCHAIN/bin/riscv32-unknown-elf-"
export PATH="$PULP_RISCV_GCC_TOOLCHAIN/bin:$QUESTA_HOME/bin:$PATH"
export LD_LIBRARY_PATH="$PULP_RISCV_GCC_TOOLCHAIN/compat-libs/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"

# Start and select the local license server.
if ! pgrep -x lmgrd >/dev/null; then
    "$QUESTA_HOME/linux_x86_64/lmgrd" \
        -c "$QUESTA_HOME/LICENSE.dat" \
        -l "$QUESTA_HOME/license_server.log"
fi
export LM_LICENSE_FILE=27001@localhost
export MGLS_LICENSE_FILE=27001@localhost

# Load PULP's simulator environment.
cd "$PULP_PROJECT_HOME"
source setup/vsim.sh

# Set PULPRT_HOME and PULPRT_TARGET, required by rules/pulp.mk.
source pulp-runtime/configs/pulp.sh

export PULP_SDK_HOME="$PULP_PROJECT_HOME/pulp-runtime"
export PULP_RUNTIME_HOME="$PULP_PROJECT_HOME/pulp-runtime"

# Verify critical dependencies before running.
vsim -c -do 'quit -f' </dev/null
riscv32-unknown-elf-gcc --version
/usr/bin/python3 -c 'from elftools.elf.elffile import ELFFile'
test -f "$PULP_PROJECT_HOME/sim/modelsim.ini"
test -d "$PULP_PROJECT_HOME/sim/work/vopt_tb"
test -f "$PULP_PROJECT_HOME/rtl/tb/remote_bitbang/librbs.so"

# Run the hello smoke test.
cd "$PULP_PROJECT_HOME/regression_tests/hello"
make run
```

Kết quả cần tìm:

```text
Hello !
Received status core: 0x00000000
```

---

# Phụ lục C — Bài học chính

1. `vsim -version` không thay thế phép thử checkout license.
2. License file đúng vẫn cần `lmgrd` và `mgcld` đang chạy.
3. Phải dùng đúng PULP GCC; RISC-V GCC generic không đủ.
4. `test.c`, ELF và `stim.txt` là ba lớp khác nhau của cùng một test.
5. `sim/compile.tcl` mô tả platform RTL; `hello/Makefile` mô tả ứng dụng phần mềm.
6. `tb_pulp.sv` điều phối nạp chương trình, chạy DUT và quyết định pass/fail.
7. `LOAD_L2=JTAG` quyết định đường nạp chương trình trong flow hiện tại.
8. `Hello !` chứng minh software chạy tới output call, không tự động chứng minh UART pin-level.
9. Status 0 là điều kiện hoàn thành chính của testbench.
10. Functional pass không đồng nghĩa transcript không có lỗi simulator.
11. `source setup/vsim.sh` là chưa đủ để build ứng dụng. Phải thêm
    `source pulp-runtime/configs/pulp.sh` để có `PULPRT_HOME` và `PULPRT_TARGET`.
    Thiếu chúng, `pulp-runtime/rules/pulp.mk` dùng `-include` nên **im lặng** không
    nạp target nào, và make chỉ báo `No rule to make target 'clean'` — thông báo này
    không hề gợi ý nguyên nhân là biến môi trường.
12. `nbPe` và `stackSize` trong Makefile của các regression test cũ là biến của SDK
    cũ và **pulp-runtime bỏ qua hoàn toàn**. Runtime hardcode `ARCHI_CLUSTER_NB_PE 8`
    và `CLUSTER_STACK_SIZE 0x800` (2 KB). Test nào cần stack lớn phải tự đặt
    `-DCLUSTER_STACK_SIZE=...` trong `PULP_CFLAGS`.

