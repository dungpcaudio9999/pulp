# Runbook từ máy mới đến GVSoC + RTL + waveform + HTML Viewer

Ngày cập nhật: **2026-10-04**.

Tài liệu này là bản thao tác đầy đủ cho demo `sw/flow_demo`. Mục tiêu là người
thực hiện đi lần lượt từ trên xuống, copy/paste từng khối lệnh, kiểm tra đúng
checkpoint rồi mới sang bước tiếp theo.

Kết quả cuối cùng gồm:

1. một ELF RISC-V duy nhất được build từ `flow_demo.c`;
2. ELF đó chạy PASS trên GVSoC `pulp-open`;
3. đúng ELF đó chạy PASS trên PULP RTL bằng QuestaSim;
4. có instruction trace của FC và cluster;
5. có waveform RTL chọn lọc;
6. có `flow_viewer.html` để xem timeline và replay instruction.

Nếu toàn bộ công cụ đã có trên máy hiện tại, đi thẳng đến [Phần A](#phần-a--đường-chạy-nhanh-trên-máy-hiện-tại).
Nếu bắt đầu từ Ubuntu mới, làm từ [Phần B](#phần-b--setup-từ-ubuntu-mới).

> **Giới hạn không thể tự động hóa:** QuestaSim là phần mềm thương mại. Người
> dùng phải có bộ cài và license hợp lệ. Runbook mô tả chính xác cấu trúc thư
> mục, biến môi trường và phép thử license sau khi cài, nhưng không cung cấp bộ
> cài hoặc license.

---

## 0. Baseline đã kiểm chứng

| Thành phần | Phiên bản/trạng thái đã chạy thành công |
|---|---|
| Host | Ubuntu 24.04.5 LTS, x86_64 |
| PULP repository | nhánh `feature/pc-work`, commit nền `37355b88c127740add0b747f2d04e5214d0dcdd6` |
| PULP GCC | `riscv32-unknown-elf-gcc 7.1.1`, `/opt/pulp-toolchain` |
| Toolchain archive | `v1.0.16-pulp-riscv-gcc-ubuntu-16.tar.bz2` |
| GVSoC | commit `3b4c489c8cccbf4e749c9e94e24d43b2c3351584` |
| PULP SDK dùng với GVSoC | commit `d4b5bcdd6e416a402a6e22a3e04f29402424cb21` |
| `pulp-runtime` dùng build demo | tag `v0.0.15`, commit `dd39b06789a8fb5a622cac2bbb074a9a18a5a4cf` |
| Bender | `0.31.0` |
| RTL simulator | QuestaSim 10.7c, 64-bit |
| Python hệ thống | `/usr/bin/python3` 3.12.3 |
| GVSoC target | `pulp-open` |

Không thay một toolchain RISC-V generic cho PULP GCC. Code runtime sử dụng các
builtin/extension riêng của PULP mà compiler generic có thể không hỗ trợ.

### 0.1. Quy tắc dùng terminal

Không chạy toàn bộ flow trong một terminal duy nhất. PULP SDK cho GVSoC và
`pulp-runtime` cho RTL cùng đặt một số biến tên giống nhau nhưng trỏ tới hai cây
khác nhau.

| Terminal | Chỉ dùng cho | Environment chính |
|---|---|---|
| Terminal BUILD | build ELF | `pulp-runtime/configs/pulp.sh` |
| Terminal GVSOC | chạy model kiến trúc | `sw/gvsoc/env.sh` |
| Terminal RTL | chạy Questa | `sw/full_system/run_sim.sh` tự dựng environment |

Nếu đã source nhầm environment, cách chắc chắn nhất là đóng terminal đó, mở
terminal mới rồi copy lại đúng block. Không source `sw/gvsoc/env.sh` trước khi
gọi `run_sim.sh`.

### 0.2. Thời gian tham khảo

| Bước | Thời gian thường gặp |
|---|---:|
| Cài package hệ thống | 5–20 phút |
| Build GVSoC `pulp-open` | 10–30 phút |
| Build RTL lần đầu | 30–60 phút |
| Build `flow_demo` | dưới 1 phút |
| Chạy GVSoC | vài giây đến dưới 1 phút |
| Chạy RTL + trace | vài phút đến hàng chục phút tùy máy |
| Chạy RTL thu VCD | tương đương hoặc chậm hơn lượt RTL thường |

---

# Phần A — Đường chạy nhanh trên máy hiện tại

Phần này giả sử source và các tool đã nằm đúng vị trí như baseline.

## A1. Mở terminal kiểm tra môi trường

Copy nguyên khối:

```bash
export PROJECT_ROOT=/home/dungpc/ndmoney4porche/projects/pulp
export TOOLCHAIN_ROOT=/opt/pulp-toolchain
export GVSOC_ROOT="$HOME/gvsoc"
export GVSOC_SDK_ROOT="$HOME/pulp-sdk"
export QUESTA_ROOT="$HOME/questasim"

cd "$PROJECT_ROOT"

test -x "$TOOLCHAIN_ROOT/bin/riscv32-unknown-elf-gcc"
test -x "$GVSOC_ROOT/install/bin/gvsoc"
test -f "$GVSOC_SDK_ROOT/configs/pulp-open.sh"
test -x "$QUESTA_ROOT/bin/vsim"
test -f pulp-runtime/configs/pulp.sh
test -f sim/compile.tcl
test -d sim/work/vopt_tb
test -f rtl/tb/remote_bitbang/librbs.so
/usr/bin/python3 -c 'from elftools.elf.elffile import ELFFile; print("pyelftools: OK")'
command -v gtkwave
```

Nếu khối trên kết thúc mà không có lỗi, tiếp tục A2. Nếu một `test` trả về lỗi,
không đoán cách sửa; tìm đúng thành phần thiếu trong Phần B.

## A2. Build một ELF duy nhất

Mở terminal sạch và copy:

```bash
export PROJECT_ROOT=/home/dungpc/ndmoney4porche/projects/pulp
export PULP_RISCV_GCC_TOOLCHAIN=/opt/pulp-toolchain

cd "$PROJECT_ROOT"

export PATH=$(printf '%s' "$PATH" | tr ':' '\n' | grep -v miniforge3 | paste -sd:)
source pulp-runtime/configs/pulp.sh
export PULP_PROJECT_HOME="$PROJECT_ROOT"
export PULP_SDK_HOME="$PROJECT_ROOT/pulp-runtime"
export PULP_RUNTIME_HOME="$PROJECT_ROOT/pulp-runtime"

make -C sw/flow_demo clean all

file sw/flow_demo/build/flow_demo/flow_demo
sha256sum sw/flow_demo/build/flow_demo/flow_demo \
  | tee report/gvsoc_demo/elf.sha256
```

Checkpoint:

```bash
test -s sw/flow_demo/build/flow_demo/flow_demo
/opt/pulp-toolchain/bin/riscv32-unknown-elf-readelf -h \
  sw/flow_demo/build/flow_demo/flow_demo | rg 'Class:|Machine:|Entry point'
/opt/pulp-toolchain/bin/riscv32-unknown-elf-nm -n \
  sw/flow_demo/build/flow_demo/flow_demo | rg 'phase[0-6]_'
```

Kỳ vọng:

- ELF 32-bit RISC-V;
- entry point `0x1c008080`;
- có symbol `phase0_*` đến `phase6_*`;
- `elf.sha256` chứa đúng một dòng hash.

Từ đây đến hết A6 **không chạy lại `make clean all`**. Hai backend phải nhận
đúng binary vừa hash.

## A3. Chạy GVSoC và thu instruction trace

Mở terminal mới dành riêng cho GVSoC:

```bash
export PROJECT_ROOT=/home/dungpc/ndmoney4porche/projects/pulp
cd "$PROJECT_ROOT"

source sw/gvsoc/env.sh

which gvsoc
which riscv32-unknown-elf-gcc
which python3
gvsoc --target=pulp-open target_properties >/tmp/pulp_open_properties.txt

mkdir -p report/gvsoc_demo/gvsoc

gvsoc --target=pulp-open \
  --work-dir="$PROJECT_ROOT/report/gvsoc_demo/gvsoc" \
  --binary="$PROJECT_ROOT/sw/flow_demo/build/flow_demo/flow_demo" \
  --trace=chip/soc/fc/insn:fc.log \
  --trace=chip/cluster/pe0/insn:pe0.log run \
  2>&1 | tee report/gvsoc_demo/gvsoc.log
```

Checkpoint GVSoC:

```bash
rg 'FLOW\|6\|RESULT\|PASS\|errors=0' report/gvsoc_demo/gvsoc.log
test -s report/gvsoc_demo/gvsoc/fc.log
test -s report/gvsoc_demo/gvsoc/pe0.log
wc -l report/gvsoc_demo/gvsoc/fc.log report/gvsoc_demo/gvsoc/pe0.log
```

Kỳ vọng có đúng dòng:

```text
FLOW|6|RESULT|PASS|errors=0
```

## A4. Chạy đúng ELF đó trên RTL/Questa

Không dùng terminal GVSoC. Mở terminal mới, copy:

```bash
export PROJECT_ROOT=/home/dungpc/ndmoney4porche/projects/pulp
cd "$PROJECT_ROOT"

APP_DIR="$PROJECT_ROOT/sw/flow_demo" \
SIM_TIMEOUT="80 ms" \
WALL_TIMEOUT=3600 \
PULP_RISCV_GCC_TOOLCHAIN=/opt/pulp-toolchain \
sw/full_system/run_sim.sh all run
```

`all run` cố ý không có `clean`: runner dùng ELF đã build ở A2. Không dùng
`clean all run` tại bước này vì sẽ build một binary mới sau khi đã chạy GVSoC.

Checkpoint RTL:

```bash
rg 'FLOW\|6\|RESULT\|PASS\|errors=0' sw/flow_demo/build/transcript
rg 'Received status core: 0x00000000' sw/flow_demo/build/transcript
test -s sw/flow_demo/build/trace_core_1f_0.log

for n in 0 1 2 3 4 5 6 7; do
  test -s "sw/flow_demo/build/trace_core_00_${n}.log"
done
```

Questa 10.7c có thể in bốn `vsim-191`. Chỉ kết luận PASS khi đồng thời có:

1. runner exit code 0;
2. marker `RESULT|PASS`;
3. testbench status `0x00000000`.

## A5. Chép artifact RTL vào report

```bash
export PROJECT_ROOT=/home/dungpc/ndmoney4porche/projects/pulp
cd "$PROJECT_ROOT"

mkdir -p report/gvsoc_demo/rtl/raw

cp sw/flow_demo/build/transcript report/gvsoc_demo/rtl/transcript.log
cp sw/flow_demo/build/trace_core_1f_0.log report/gvsoc_demo/rtl/raw/

for n in 0 1 2 3 4 5 6 7; do
  cp "sw/flow_demo/build/trace_core_00_${n}.log" report/gvsoc_demo/rtl/raw/
done
```

## A6. Chạy lại RTL để thu waveform chọn lọc

```bash
export PROJECT_ROOT=/home/dungpc/ndmoney4porche/projects/pulp
cd "$PROJECT_ROOT"

export DO_FILES="-do $PROJECT_ROOT/sw/flow_demo/flow_wave_capture.do"

APP_DIR="$PROJECT_ROOT/sw/flow_demo" \
SIM_TIMEOUT="80 ms" \
WALL_TIMEOUT=3600 \
PULP_RISCV_GCC_TOOLCHAIN=/opt/pulp-toolchain \
sw/full_system/run_sim.sh all run

unset DO_FILES
```

Checkpoint waveform:

```bash
rg 'FLOW-VCD\|signals=24' sw/flow_demo/build/transcript
rg 'FLOW-VCD\|exit_status=0' sw/flow_demo/build/transcript

mkdir -p report/gvsoc_demo/rtl/wave
cp sw/flow_demo/build/flow_demo.vcd.gz \
  report/gvsoc_demo/rtl/wave/flow_demo.vcd.gz
gzip -t report/gvsoc_demo/rtl/wave/flow_demo.vcd.gz
```

## A7. Sinh HTML Viewer

```bash
export PROJECT_ROOT=/home/dungpc/ndmoney4porche/projects/pulp
cd "$PROJECT_ROOT"

/usr/bin/python3 sw/flow_demo/flow_visualize.py \
  --elf sw/flow_demo/build/flow_demo/flow_demo \
  --gvsoc-fc report/gvsoc_demo/gvsoc/fc.log \
  --gvsoc-pe0 report/gvsoc_demo/gvsoc/pe0.log \
  --gvsoc-log report/gvsoc_demo/gvsoc.log \
  --rtl-dir report/gvsoc_demo/rtl/raw \
  --rtl-log report/gvsoc_demo/rtl/transcript.log \
  --addr2line /opt/pulp-toolchain/bin/riscv32-unknown-elf-addr2line \
  --output report/gvsoc_demo/flow_viewer.html
```

Kỳ vọng:

```text
Parsed 207451 raw instructions, kept 7344
```

Số lệnh có thể thay đổi nếu compiler hoặc source thay đổi. Điều bắt buộc là
script kết thúc không lỗi và HTML không rỗng.

## A8. Kiểm tra toàn bộ artifact

```bash
export PROJECT_ROOT=/home/dungpc/ndmoney4porche/projects/pulp
cd "$PROJECT_ROOT"

/usr/bin/python3 -m py_compile sw/flow_demo/flow_visualize.py
sha256sum -c report/gvsoc_demo/elf.sha256

rg 'FLOW\|6\|RESULT\|PASS\|errors=0' \
  report/gvsoc_demo/gvsoc.log \
  report/gvsoc_demo/rtl/transcript.log

rg 'Received status core: 0x00000000' \
  report/gvsoc_demo/rtl/transcript.log

test -s report/gvsoc_demo/gvsoc/fc.log
test -s report/gvsoc_demo/gvsoc/pe0.log
test -s report/gvsoc_demo/rtl/raw/trace_core_1f_0.log

for n in 0 1 2 3 4 5 6 7; do
  test -s "report/gvsoc_demo/rtl/raw/trace_core_00_${n}.log"
done

gzip -t report/gvsoc_demo/rtl/wave/flow_demo.vcd.gz
test -s report/gvsoc_demo/flow_viewer.html

echo 'ALL CHECKS PASSED'
```

Nếu dòng cuối xuất hiện, flow đã hoàn tất.

## A9. Mở kết quả

Viewer:

```bash
firefox /home/dungpc/ndmoney4porche/projects/pulp/report/gvsoc_demo/flow_viewer.html
```

Waveform:

```bash
cd /home/dungpc/ndmoney4porche/projects/pulp/report/gvsoc_demo/rtl/wave
gtkwave flow_demo.gtkw
```

Trong phase DMA, quan sát:

- `s_dmac_busy`;
- `s_dma_cl_event`;
- TCDM request/grant;
- AXI read `AR/R valid-ready`;
- AXI write `AW/W/B valid-ready`.

---

# Phần B — Setup từ Ubuntu mới

Phần B chỉ phải làm một lần cho mỗi máy.

## B1. Xác nhận host

```bash
cat /etc/os-release
uname -m
df -h .
free -h
```

Baseline là Ubuntu x86_64. Nên có tối thiểu:

- 30 GiB dung lượng trống cho source, dependency, GVSoC và Questa work library;
- 16 GiB RAM; 32 GiB thuận tiện hơn khi compile RTL;
- kết nối GitHub để tải dependency;
- quyền `sudo` để cài package hệ thống.

## B2. Cài package hệ thống

```bash
sudo apt-get update

sudo apt-get install -y \
  build-essential gcc g++ make cmake ninja-build \
  git curl wget ca-certificates rsync ripgrep file procps binutils \
  autoconf automake libtool pkg-config texinfo \
  python3 python3-pip python3-venv \
  python3-pyelftools python3-yaml python3-prettytable \
  python3-numpy python3-pexpect python3-sphinx \
  libftdi1-dev libusb-1.0-0-dev \
  libsdl2-dev libsdl2-ttf-dev libsndfile1-dev \
  libmpc3 libmpfr6 libgmp10 zlib1g \
  scons graphviz gtkwave doxygen ccache lz4 \
  unzip bzip2 gzip tcl
```

Kiểm tra:

```bash
git --version
gcc --version | head -1
cmake --version | head -1
/usr/bin/python3 --version
/usr/bin/python3 -c 'import elftools, yaml, prettytable, numpy; print("Python packages: OK")'
gtkwave --version | head -1
dot -V
```

## B3. Lấy đúng PULP repository

Chọn thư mục cha rồi clone:

```bash
export PROJECT_PARENT=/home/dungpc/ndmoney4porche/projects
export PROJECT_ROOT="$PROJECT_PARENT/pulp"

mkdir -p "$PROJECT_PARENT"
git clone https://github.com/dungpcaudio9999/pulp.git "$PROJECT_ROOT"
cd "$PROJECT_ROOT"
git checkout feature/pc-work
```

Kiểm tra:

```bash
git remote -v
git branch --show-current
git rev-parse HEAD
test -f sw/flow_demo/flow_demo.c
test -f sw/flow_demo/flow_visualize.py
test -f sw/full_system/run_sim.sh
```

Nếu branch đã tiến lên commit mới hơn baseline, vẫn có thể tiếp tục nhưng phải
ghi lại `git rev-parse HEAD` trong báo cáo chạy.

## B4. Cài đúng PULP RISC-V GCC

### B4.1. Trên máy hiện tại có sẵn archive đã kiểm chứng

Archive:

```text
/home/dungpc/ndmoney4porche/tools/v1.0.16-pulp-riscv-gcc-ubuntu-16.tar.bz2
```

SHA-256 đã kiểm chứng:

```text
6c73e81e9bf8479ce02209f8800b3af31e61722b617b60eddf994abd5e3cb95e
```

Nếu `/opt/pulp-toolchain` đã tồn tại và compiler chạy được, không giải nén lại:

```bash
test -x /opt/pulp-toolchain/bin/riscv32-unknown-elf-gcc
/opt/pulp-toolchain/bin/riscv32-unknown-elf-gcc --version | head -1
```

### B4.2. Trên máy mới

Tải asset `v1.0.16-pulp-riscv-gcc-ubuntu-16.tar.bz2` từ release `v1.0.16` của
`pulp-platform/pulp-riscv-gnu-toolchain`, rồi đặt tại:

```text
$HOME/Downloads/v1.0.16-pulp-riscv-gcc-ubuntu-16.tar.bz2
```

Sau khi file đã có, copy/paste:

```bash
export TOOLCHAIN_ARCHIVE="$HOME/Downloads/v1.0.16-pulp-riscv-gcc-ubuntu-16.tar.bz2"
export TOOLCHAIN_EXTRACTED=/opt/v1.0.16-pulp-riscv-gcc-ubuntu-16
export TOOLCHAIN_ROOT=/opt/pulp-toolchain

test -f "$TOOLCHAIN_ARCHIVE"
sha256sum "$TOOLCHAIN_ARCHIVE"

sudo tar -xjf "$TOOLCHAIN_ARCHIVE" -C /opt

if test ! -e "$TOOLCHAIN_ROOT"; then
  sudo ln -s "$TOOLCHAIN_EXTRACTED" "$TOOLCHAIN_ROOT"
fi

test -x "$TOOLCHAIN_ROOT/bin/riscv32-unknown-elf-gcc"
"$TOOLCHAIN_ROOT/bin/riscv32-unknown-elf-gcc" --version | head -1
```

Nếu binary prebuilt cũ báo thiếu `libmpfr.so.4` hoặc `libisl.so.15`, không tạo
symlink giả sang ABI mới. Dùng một trong hai cách an toàn:

1. dùng bản `/opt/pulp-toolchain` đã chạy được trên máy baseline;
2. giải nén đúng compatibility libraries của toolchain vào một thư mục riêng và
   thêm thư mục đó vào `LD_LIBRARY_PATH`.

Phép thử thật của compiler sẽ diễn ra ở B10 khi build `flow_demo`.

## B5. Chuẩn bị `pulp-runtime`

```bash
export PROJECT_ROOT=/home/dungpc/ndmoney4porche/projects/pulp
cd "$PROJECT_ROOT"

if test ! -d pulp-runtime/.git; then
  make pulp-runtime
fi

git -C pulp-runtime checkout v0.0.15
```

Python 3.11+ đã bỏ mode `rU`. Áp compatibility fix có điều kiện:

```bash
if rg -q '"rU"' pulp-runtime/bin/slm_hyper.py; then
  sed -i 's/"rU"/"r"/g' pulp-runtime/bin/slm_hyper.py
fi

/usr/bin/python3 -m py_compile pulp-runtime/bin/slm_hyper.py
```

Không commit `pulp-runtime/bin/slm_hyper.py` vào repository cha vì
`pulp-runtime` là checkout độc lập và bị ignore.

## B6. Cài PULP SDK dùng với GVSoC

SDK này khác `pulp-runtime` trong repository:

- `$HOME/pulp-sdk`: cung cấp config/runner cho GVSoC;
- `$PROJECT_ROOT/pulp-runtime`: build workload cho flow RTL hiện tại.

Clone đúng state đã kiểm chứng:

```bash
export GVSOC_SDK_ROOT="$HOME/pulp-sdk"

if test ! -d "$GVSOC_SDK_ROOT/.git"; then
  git clone https://github.com/pulp-platform/pulp-sdk.git "$GVSOC_SDK_ROOT"
fi

git -C "$GVSOC_SDK_ROOT" fetch --all --tags
git -C "$GVSOC_SDK_ROOT" checkout d4b5bcdd6e416a402a6e22a3e04f29402424cb21

test -f "$GVSOC_SDK_ROOT/configs/pulp-open.sh"
```

## B7. Build và cài GVSoC `pulp-open`

### B7.1. Clone đúng commit

```bash
export GVSOC_ROOT="$HOME/gvsoc"

if test ! -d "$GVSOC_ROOT/.git"; then
  git clone https://github.com/gvsoc/gvsoc.git "$GVSOC_ROOT"
fi

git -C "$GVSOC_ROOT" fetch --all --tags
git -C "$GVSOC_ROOT" checkout 3b4c489c8cccbf4e749c9e94e24d43b2c3351584
git -C "$GVSOC_ROOT" submodule update --init --recursive -j8
```

### B7.2. Cài Python requirements cho Python hệ thống

GVSoC executable được chạy bằng Python trong `PATH`. Trên Ubuntu 24.04, dùng:

```bash
/usr/bin/python3 -m pip install --user --break-system-packages \
  -r "$GVSOC_ROOT/core/requirements.txt"

/usr/bin/python3 -m pip install --user --break-system-packages \
  -r "$GVSOC_ROOT/gapy/requirements.txt"
```

Kiểm tra các module quan trọng:

```bash
/usr/bin/python3 -c 'import elftools, yaml, prettytable, pexpect; print("GVSoC Python deps: OK")'
```

### B7.3. Build target

```bash
export GVSOC_ROOT="$HOME/gvsoc"
cd "$GVSOC_ROOT"

make all TARGETS=pulp-open -j"$(nproc)"
```

Checkpoint:

```bash
test -x "$GVSOC_ROOT/install/bin/gvsoc"
source "$GVSOC_ROOT/sourceme.sh"
which gvsoc
gvsoc --target=pulp-open target_properties >/tmp/pulp_open_properties.txt
test -s /tmp/pulp_open_properties.txt
```

Nếu `gvsoc --target=pulp-open` báo không tìm thấy target, build chưa hoàn tất
hoặc terminal chưa `source "$GVSOC_ROOT/sourceme.sh"`.

## B8. Cài và kiểm tra QuestaSim

### B8.1. Cấu trúc thư mục mà flow hiện tại chờ đợi

Sau khi cài QuestaSim 10.7c bằng installer hợp lệ, cấu trúc tối thiểu phải có:

```text
$HOME/questasim/
├── bin/vsim
├── bin/vlog
├── bin/vopt
├── linux_x86_64/lmgrd
├── linux_x86_64/lmutil
└── LICENSE.dat
```

Kiểm tra executable:

```bash
export QUESTA_ROOT="$HOME/questasim"

test -x "$QUESTA_ROOT/bin/vsim"
test -x "$QUESTA_ROOT/bin/vlog"
test -x "$QUESTA_ROOT/bin/vopt"
test -x "$QUESTA_ROOT/linux_x86_64/lmgrd"

export PATH="$QUESTA_ROOT/bin:$PATH"
vsim -version 2>&1 | head -4
```

### B8.2. Khởi động license server theo layout baseline

Flow hiện tại dùng local FlexNet server tại `27001@localhost`:

```bash
export QUESTA_ROOT="$HOME/questasim"
export QUESTA_LICENSE_FILE="$QUESTA_ROOT/LICENSE.dat"
export QUESTA_LICENSE_LOG="$QUESTA_ROOT/license_server.log"

test -f "$QUESTA_LICENSE_FILE"

if ! pgrep -x lmgrd >/dev/null; then
  "$QUESTA_ROOT/linux_x86_64/lmgrd" \
    -c "$QUESTA_LICENSE_FILE" \
    -l "$QUESTA_LICENSE_LOG"
fi

export LM_LICENSE_FILE=27001@localhost
export MGLS_LICENSE_FILE=27001@localhost

"$QUESTA_ROOT/linux_x86_64/lmutil" lmstat -a -c 27001@localhost
"$QUESTA_ROOT/bin/vsim" -c -do 'quit -f' </dev/null
```

`vsim -version` chỉ chứng minh executable tồn tại. Chỉ lệnh `vsim -c ...` cuối
cùng mới chứng minh simulator checkout được license.

Nếu tổ chức dùng license server từ xa, phải thay giá trị license và điều chỉnh
`sw/full_system/run_sim.sh`; runner baseline đang chủ động dùng
`27001@localhost` và tìm `$HOME/questasim/LICENSE.dat`.

## B9. Checkout dependency và build RTL

### B9.1. Lấy dependency và sinh compile script

```bash
export PROJECT_ROOT=/home/dungpc/ndmoney4porche/projects/pulp
cd "$PROJECT_ROOT"

./bender checkout
./patch-deps
make scripts
```

Không dùng `make checkout` trên checkout sạch. Target đó chạy Bender rồi đi
thẳng vào `make scripts`, không có vị trí để chèn `./patch-deps`.

Checkpoint:

```bash
./bender --version
test -f Bender.lock
test -s sim/compile.tcl
```

### B9.2. Compile và optimize testbench

```bash
export PROJECT_ROOT=/home/dungpc/ndmoney4porche/projects/pulp
cd "$PROJECT_ROOT"

source setup/vsim.sh
ulimit -n 4096

cd sim
make clean
vmap -c
make lib
make build
make opt
cd "$PROJECT_ROOT"
```

Thứ tự `make clean` rồi `vmap -c` là bắt buộc. `make clean` xóa
`sim/modelsim.ini`; nếu chạy ngược thứ tự thì bước `make lib` hỏng.

Checkpoint RTL build:

```bash
test -f sim/modelsim.ini
test -d sim/work/vopt_tb
test -f rtl/tb/remote_bitbang/librbs.so
file rtl/tb/remote_bitbang/librbs.so
```

Build đầu tiên có thể mất 30–60 phút. Warning không đồng nghĩa với lỗi; bước
`make opt` phải kết thúc với optimized design `vopt_tb`.

## B10. Preflight toàn bộ trước khi chạy demo

```bash
export PROJECT_ROOT=/home/dungpc/ndmoney4porche/projects/pulp
export TOOLCHAIN_ROOT=/opt/pulp-toolchain
export GVSOC_ROOT="$HOME/gvsoc"
export GVSOC_SDK_ROOT="$HOME/pulp-sdk"
export QUESTA_ROOT="$HOME/questasim"

cd "$PROJECT_ROOT"

failed=0

check_file() {
  if test -e "$1"; then
    echo "OK   $1"
  else
    echo "MISS $1"
    failed=1
  fi
}

check_file "$TOOLCHAIN_ROOT/bin/riscv32-unknown-elf-gcc"
check_file "$GVSOC_ROOT/install/bin/gvsoc"
check_file "$GVSOC_SDK_ROOT/configs/pulp-open.sh"
check_file "$QUESTA_ROOT/bin/vsim"
check_file pulp-runtime/configs/pulp.sh
check_file sim/compile.tcl
check_file sim/work/vopt_tb
check_file rtl/tb/remote_bitbang/librbs.so

/usr/bin/python3 -c 'import elftools; print("OK   pyelftools")' || failed=1
command -v gtkwave >/dev/null || failed=1

if test "$failed" -ne 0; then
  echo 'PREFLIGHT FAILED'
  false
fi

echo 'PREFLIGHT PASSED'
```

Khi thấy `PREFLIGHT PASSED`, quay lại Phần A và chạy từ A2.

---

# Phần C — Dùng một ELF khác

Một ELF khác có thể chạy trên cả GVSoC và RTL nếu thỏa đồng thời:

1. ELF32 little-endian RISC-V phù hợp core PULP;
2. memory map/linker script phù hợp target;
3. entry point phù hợp, thông thường `0x1c008080`;
4. runtime và peripheral mà ELF sử dụng tồn tại ở cả hai backend;
5. binary không bị thay đổi giữa hai lượt;
6. nếu muốn map PC về source thì ELF phải có DWARF và không bị strip.

Kiểm tra ELF trước khi chạy:

```bash
export ELF_PATH=/duong/dan/toi/chuong_trinh.elf

test -s "$ELF_PATH"
file "$ELF_PATH"
sha256sum "$ELF_PATH"
/opt/pulp-toolchain/bin/riscv32-unknown-elf-readelf -h "$ELF_PATH"
/opt/pulp-toolchain/bin/riscv32-unknown-elf-readelf -S "$ELF_PATH" | rg 'debug|text|data|bss'
```

Không thay trực tiếp ELF mới vào `flow_demo` rồi kỳ vọng phase timeline vẫn giữ
nguyên. Nếu ELF không có symbol `phaseN_*`, viewer chỉ có thể suy luận các mốc
runtime như `_start`, `main`, `pos_init_stop` và `exit`.

Hai ví dụ ELF ngoài đã được nghiệm thu:

- `report/zcu104_uart_smoke/README.md`;
- `report/zcu104_uart_direct/README.md`.

Các file đó cần decoder baud riêng:

- GVSoC UART checker: `825000`;
- RTL testbench UART monitor: `202250`.

Đây là tham số decoder theo clock hiệu dụng của từng model, không phải bằng
chứng rằng ELF khác nhau.

---

# Phần D — Cách đọc kết quả

## D1. HTML Viewer

Viewer dùng để:

- xem GVSoC và RTL trên hai lane;
- tìm `main`, phase, PC, opcode hoặc source line;
- replay instruction;
- đối chiếu theo cùng phase ngữ nghĩa;
- mở raw trace và VCD liên quan.

Viewer không chạy simulator và không chứng minh handshake RTL.

## D2. Instruction trace

Trace trả lời:

- core nào đang chạy;
- PC/opcode hiện tại;
- hàm và source line nếu có DWARF;
- register và địa chỉ vật lý liên quan.

Trace không hiển thị từng beat do DMA hoặc UDMA tự tạo sau khi CPU cấu hình.

## D3. Waveform RTL

Waveform trả lời:

- clock/reset/fetch/busy thay đổi khi nào;
- request/grant có thực sự xảy ra không;
- valid-ready có handshake không;
- DMA/UDMA bắt đầu và kết thúc khi nào;
- event/status nào làm CPU tiếp tục.

Chuỗi phân tích đúng:

```text
instruction CPU
    -> MMIO hoặc memory transaction
    -> khối phần cứng nhận cấu hình
    -> phần cứng hoạt động tự trị
    -> status/event
    -> CPU tiếp tục
```

---

# Phần E — Bảng xử lý lỗi

| Triệu chứng | Kiểm tra | Cách xử lý |
|---|---|---|
| Không thấy `gvsoc` | `which gvsoc` | `source sw/gvsoc/env.sh` |
| GVSoC thiếu `prettytable` | `which python3` | đảm bảo là `/usr/bin/python3`; cài requirement GVSoC |
| Không có target `pulp-open` | `gvsoc --target=pulp-open target_properties` | build lại `make all TARGETS=pulp-open` |
| `No rule to make target clean` | `echo "$PULPRT_HOME"` | source `pulp-runtime/configs/pulp.sh` hoặc dùng runner |
| `ModuleNotFoundError: elftools` | `/usr/bin/python3 -c 'import elftools'` | `sudo apt install python3-pyelftools` |
| `invalid mode: rU` | tìm trong `slm_hyper.py` | đổi `"rU"` thành `"r"` |
| `sim/compile.tcl` thiếu | `test -f sim/compile.tcl` | `./bender checkout; ./patch-deps; make scripts` |
| `modelsim.ini` thiếu | `test -f sim/modelsim.ini` | trong `sim`: `make clean; vmap -c; make lib` |
| `tb_pulp` không tồn tại | kiểm `make build` phía trước | sửa lỗi đầu tiên của compile/DPI rồi chạy lại build |
| Questa báo license error | `vsim -c -do 'quit -f'` | khởi động `lmgrd`, kiểm port và license file |
| RTL treo | xem phase cuối và watchdog | tăng timeout nếu hợp lý; không bỏ watchdog |
| `vsim-191` nhưng test PASS | kiểm status/exit/marker | coi là nhiễu đã biết của Questa 10.7c |
| Viewer hiện `??:0` | kiểm `.debug_*` và SHA | dùng đúng ELF có DWARF |
| VCD quá lớn | kiểm do-file | chỉ dump signal cần thiết |
| DMA không thấy trong trace | mở waveform | xem `busy`, TCDM và AXI handshake |

---

# Phần F — Danh mục kết quả chuẩn

Sau một lượt hoàn chỉnh:

```text
report/gvsoc_demo/
├── README.md
├── SETUP_AND_RUN_FROM_SCRATCH.md
├── HUONG_DAN_TUNG_BUOC.md
├── BAO_CAO_CONG_VIEC.md
├── elf.sha256
├── flow_viewer.html
├── gvsoc.log
├── gvsoc/
│   ├── fc.log
│   ├── pe0.log
│   └── gvsoc_config.json
└── rtl/
    ├── transcript.log
    ├── raw/
    │   ├── trace_core_1f_0.log
    │   └── trace_core_00_0.log ... trace_core_00_7.log
    └── wave/
        ├── flow_demo.vcd.gz
        └── flow_demo.gtkw
```

Thứ tự điều tra khi có sai khác:

1. `elf.sha256` — có đúng cùng binary không;
2. `gvsoc.log` và `rtl/transcript.log` — chức năng sai ở phase nào;
3. FC/PE raw trace — CPU đã thực thi gì;
4. VCD/GTKWave — phần cứng nhận giao dịch và phản hồi ra sao;
5. `flow_viewer.html` — tổng hợp lại timeline và tìm anchor nhanh.

---

# Phần G — Những bước chỉ chạy một lần và những bước phải chạy lại

| Thao tác | Khi nào chạy lại |
|---|---|
| Cài apt packages | chỉ khi máy thiếu package |
| Cài PULP GCC | một lần/máy |
| Clone/build GVSoC | khi đổi commit/target hoặc build hỏng |
| Clone PULP SDK | khi đổi SDK commit |
| Cài Questa/license | một lần/máy hoặc khi license thay đổi |
| Bender checkout + patch + scripts | checkout sạch hoặc dependency đổi |
| Compile RTL `make build/opt` | RTL/dependency/compile option đổi |
| Build ELF | source C/runtime/compiler option đổi |
| Chạy GVSoC và RTL | mỗi ELF mới |
| Thu VCD | mỗi ELF hoặc danh sách signal mới |
| Sinh viewer | mỗi bộ trace/log/ELF mới |

Quy tắc quan trọng nhất: nếu ELF thay đổi, ghi hash mới và chạy lại **cả hai**
backend. Không trộn trace của binary cũ với waveform của binary mới.
