# Hướng dẫn chạy GVSoC để đánh giá coverage trên PULP

## 1. Mục tiêu và phạm vi

Tài liệu này hướng dẫn tuần tự cách chạy target GVSoC `pulp-open` trên các ELF
của PULP, kiểm tra model chạy được khối nào, quan sát được dữ liệu gì, và hiệu
chuẩn kết quả với RTL Questa.

GVSoC **không mô phỏng trực tiếp** source SystemVerilog trong `rtl/pulp/`.
Luồng thực tế là:

```text
Source C/assembly
       |
       +--> build ELF bằng PULP SDK hoặc pulp-runtime
                |
                +--> GVSoC target pulp-open
                |
                +--> RTL tb_pulp/Questa (cùng ELF, khi cần hiệu chuẩn)
```

Phạm vi của runbook:

- target GVSoC `pulp-open`;
- FC, cluster 8 PE, event unit, L1/L2, I-cache, MCHAN DMA;
- UART, HyperRAM, HyperFlash và filesystem;
- performance counter, trace, VCD và power report;
- `sw/full_system`, `ubench_rt` và `icache_sweep`;
- so sánh cùng ELF với RTL.

Các target `rv64`, Snitch, vector, many-core và các chip khác không thuộc phạm
vi. Kế hoạch và tiêu chí coverage nằm trong
[`GVSOC_PULP_COVERAGE_PLAN.md`](GVSOC_PULP_COVERAGE_PLAN.md).

## 2. Kết quả tham chiếu đã xác nhận

Runbook này đã được chạy thành công ngày 2026-09-27 với:

| Thành phần | Phiên bản |
|---|---|
| PULP RTL | `3f06b9c` |
| GVSoC | `3b4c489` |
| PULP SDK | `d4b5bcd` |
| RISC-V GCC | 7.1.1 |
| Questa | 10.7c |

Report tham chiếu:
[`report/gvsoc_20260927_coverage/`](../../../report/gvsoc_20260927_coverage/README.md).

Thời gian tham khảo:

| Công việc | Thời gian |
|---|---:|
| 13 smoke test SDK | khoảng 1 phút |
| Inventory trace/VCD/power | dưới 1 phút |
| GVSoC microbenchmark và I-cache | dưới 1 phút mỗi lượt |
| RTL `ubench_rt` | 11 phút 39 giây |
| RTL `icache_sweep` | 7 phút 07 giây |

Nên dành khoảng 25–35 phút và ít nhất 2 GiB đĩa trống. **Không chạy**
`cluster/fork_power`: test đó ép `--event=.*` và từng sinh VCD 22 GiB sau
bốn phút.

## 3. Điều kiện cần

Các đường dẫn mặc định:

```text
/home/dungpc/ndmoney4porche/projects/pulp   repo PULP
/home/dungpc/gvsoc                         source/build GVSoC
/home/dungpc/pulp-sdk                      PULP SDK
/opt/pulp-toolchain                        RISC-V GCC
/home/dungpc/questasim                     Questa
```

Kiểm tra:

```bash
export PULP_REPO=/home/dungpc/ndmoney4porche/projects/pulp
cd "$PULP_REPO"

set -e
test -f sw/gvsoc/env.sh
test -x /home/dungpc/gvsoc/install/bin/gvsoc
test -f /home/dungpc/pulp-sdk/configs/pulp-open.sh
test -x /opt/pulp-toolchain/bin/riscv32-unknown-elf-gcc
test -x /home/dungpc/questasim/bin/vsim
test -f pulp-runtime/configs/pulp.sh
test -f sim/compile.tcl
/usr/bin/python3 -c "import elftools, prettytable"
df -h "$PULP_REPO"
echo "Preflight OK"
```

Không có output từ các lệnh `test` là bình thường. Lệnh Python phải exit 0.
Nếu thiếu `prettytable` khi gọi `gvsoc`, xem phần xử lý lỗi ở cuối tài liệu.

## 4. Tạo thư mục kết quả

Dùng một thư mục mới cho mỗi phiên để không ghi đè log cũ:

```bash
export PULP_REPO=/home/dungpc/ndmoney4porche/projects/pulp
export GVSOC_OUT="$PULP_REPO/report/gvsoc_manual_run"
cd "$PULP_REPO"

test ! -e "$GVSOC_OUT"
mkdir -p "$GVSOC_OUT"
```

Nếu `gvsoc_manual_run` đã tồn tại, đổi tên sang một thư mục mới. Không xóa
report cũ chỉ để chạy lại.

## 5. Chuẩn bị hai terminal

GVSoC/PULP SDK và `pulp-runtime` dùng các biến môi trường khác nhau. Nên giữ
hai terminal riêng trong suốt phiên.

### 5.1. Terminal A — GVSoC và PULP SDK

```bash
export PULP_REPO=/home/dungpc/ndmoney4porche/projects/pulp
export GVSOC_OUT="$PULP_REPO/report/gvsoc_manual_run"
cd "$PULP_REPO"

source sw/gvsoc/env.sh

which gvsoc riscv32-unknown-elf-gcc python3
git -C "$GVSOC_HOME" rev-parse --short HEAD
git -C "$PULP_SDK_HOME_GV" rev-parse --short HEAD
```

Kết quả đúng với baseline tham chiếu:

```text
/home/dungpc/gvsoc/install/bin/gvsoc
/opt/pulp-toolchain/bin/riscv32-unknown-elf-gcc
/usr/bin/python3
3b4c489
d4b5bcd
```

`env.sh` cố ý loại Miniforge và Xilinx SDK cũ khỏi `PATH`. Không source
`pulp-runtime/configs/pulp.sh` trong Terminal A.

### 5.2. Terminal B — build bằng pulp-runtime và chạy RTL

```bash
export PULP_REPO=/home/dungpc/ndmoney4porche/projects/pulp
export GVSOC_OUT="$PULP_REPO/report/gvsoc_manual_run"
cd "$PULP_REPO"

export PATH="$(printf '%s' "$PATH" | tr ':' '\n' | grep -vE 'miniforge3|/SDK/2019.1' | paste -sd:)"
export PULP_RISCV_GCC_TOOLCHAIN=/opt/pulp-toolchain
source pulp-runtime/configs/pulp.sh
export PULP_PROJECT_HOME="$PULP_REPO"
export PULP_SDK_HOME="$PULP_REPO/pulp-runtime"
export PULP_RUNTIME_HOME="$PULP_REPO/pulp-runtime"

which riscv32-unknown-elf-gcc python3
```

Kết quả đúng:

```text
/opt/pulp-toolchain/bin/riscv32-unknown-elf-gcc
/usr/bin/python3
```

## 6. Bước 0 — ghi baseline

Chạy ở Terminal A:

```bash
cd "$PULP_REPO"

git rev-parse --short HEAD
git -C "$GVSOC_HOME" rev-parse --short HEAD
git -C "$PULP_SDK_HOME_GV" rev-parse --short HEAD
riscv32-unknown-elf-gcc --version | head -1
gvsoc --target=pulp-open target_properties | tee "$GVSOC_OUT/target_properties.txt"
```

Target đúng phải công bố bốn property:

- `chip/cluster/redmule`;
- `chip/soc/fic`;
- `chip/soc/binary`;
- `uart_checker/loopback`.

Nếu cần kiểm tra cấu hình thực tế, mỗi lần chạy GVSoC sẽ sinh
`gvsoc_config.json` trong work directory. Không suy cấu hình GVSoC từ RTL:
hai phía không tự đồng bộ.

## 7. Bước 1 — smoke test từng khối

Chạy ở Terminal A:

```bash
cd "$PULP_REPO"
sw/gvsoc/step1_sdk_tests.sh "$GVSOC_OUT/step1"
sed -n '1,40p' "$GVSOC_OUT/step1/summary.txt"
```

Kết quả đúng ở baseline:

```text
hello_fc                 PASS
hello_cl                 PASS
cluster_call             PASS
cluster_fork             PASS
dma_1d                   PASS
flash_simple             PASS
flash_with_ram           FAIL
fs_read_fc               PASS
fs_read_cl               PASS
perf_double_buffering    PASS
perf_matmult             PASS
ram_simple               PASS
uart_loopback            PASS
```

Tổng cộng phải có 12 `PASS`. `flash_with_ram` FAIL được phân loại
`PARTIAL`, không phải lỗi build. Log đúng có dạng:

```text
Failed to program specified location (addr: 0x40881,
program_val: 0x01)
```

Điều này cho thấy read/program đơn giản chạy được, nhưng model HyperFlash không
hỗ trợ đầy đủ chuỗi erase/reprogram của test.

Nếu một test khác FAIL, không tiếp tục kết luận coverage từ kết quả tham chiếu.
Mở log tương ứng trong `$GVSOC_OUT/step1/` và phân loại lại nguyên nhân.

## 8. Bước 2 — inventory trace, VCD và power

Test bước 1 đã build ELF `hello` chạy trên cluster. Chạy ở Terminal A:

```bash
export HELLO_ELF=/home/dungpc/pulp-sdk/tests/hello/BUILD/PULP/GCC_RISCV/cl/test/test

test -f "$HELLO_ELF"
sw/gvsoc/step2_inventory.sh "$GVSOC_OUT/step2" "$HELLO_ELF"
cat "$GVSOC_OUT/step2/runs.txt"
```

Kết quả đúng:

```text
trace_all: exit=0
vcd_all: exit=0
power: exit=0
trace paths:  1475
vcd signals:  2555
power rows:   262
```

Các file quan trọng:

| File | Ý nghĩa |
|---|---|
| `step2/traces.txt` | Component có text trace |
| `step2/vcd_signals.txt` | Cây tín hiệu VCD |
| `step2/power.csv` | Power report |
| `step2/run_vcd_all/view.gtkw` | Cấu hình GTKWave |
| `step2/run_*/gvsoc_config.json` | Cấu hình model hiệu lực |

Kiểm tra power:

```bash
grep '/chip/cluster/l1' "$GVSOC_OUT/step2/power.csv" | head
grep '/chip/soc/power_trace' "$GVSOC_OUT/step2/power.csv"
```

Kết quả đúng: power khác 0 chỉ nằm ở L1 cluster; SoC, core, L2, DMA và
interconnect bằng 0. Vì vậy không dùng report này làm power tuyệt đối toàn chip.

### 8.1. Target properties và sơ đồ model

Chạy ở Terminal A:

```bash
gvsoc --target=pulp-open target_properties \
  | tee "$GVSOC_OUT/step2/target_properties.txt"

(
  cd "$GVSOC_OUT/step2"
  gvsoc --target=pulp-open diagram
  dot -Tsvg architecture.dot -o architecture.svg
  dot -Tpng architecture.dot -o architecture.png
)
```

Kết quả đúng phải có:

```text
Diagram written to architecture.dot
```

và ba file `architecture.dot`, `architecture.svg`, `architecture.png`.

## 9. Bước 3 — instruction profile theo lệnh và theo hàm

Trước tiên build `ubench_rt` ở Terminal B:

```bash
cd "$PULP_REPO"
make -C sw/gvsoc/ubench_rt clean all
test -x sw/gvsoc/ubench_rt/build/test/test
```

Sau đó chạy trace ở Terminal A:

```bash
mkdir -p "$GVSOC_OUT/step2/profile"

(
  cd "$GVSOC_OUT/step2/profile"
  gvsoc --target=pulp-open \
    --work-dir="$GVSOC_OUT/step2/profile" \
    --binary="$PULP_REPO/sw/gvsoc/ubench_rt/build/test/test" \
    --trace=cluster/pe0/insn:pe0.log run
) 2>&1 | tee "$GVSOC_OUT/step2/profile/run.log"

/usr/bin/python3 -W ignore \
  /home/dungpc/gvsoc/install/bin/gvsoc_analyze_insn \
  --trace "$GVSOC_OUT/step2/profile/pe0.log" \
  | tee "$GVSOC_OUT/step2/profile/analyze.txt"

sw/gvsoc/analyze/func_profile.py \
  "$GVSOC_OUT/step2/profile/pe0.log" --top 15 \
  | tee "$GVSOC_OUT/step2/profile/func_profile.txt"
```

Kết quả đúng có các đặc điểm:

- `p.sw` khoảng 21,5 cycle;
- `p.lbu` khoảng 12,2 cycle;
- `add` khoảng 1,2 cycle;
- khoảng 90% cycle của PE0 nằm trong `printf` và các hàm con
  `pos_libc_prf`, `strchr`, `fputc`.

Điều này chứng minh mọi vùng benchmark phải đặt `printf` ra ngoài vùng đếm.
Raw trace khoảng 100 MiB; có thể nén sau khi phân tích:

```bash
gzip -f "$GVSOC_OUT/step2/profile/pe0.log"
```

## 10. Bước 4 — chạy `full_system` theo phase

### 10.1. Bản bỏ qua HWPE

Build ở Terminal B:

```bash
cd "$PULP_REPO"
make -C sw/full_system clean all SKIP_HWPE=1
test -x sw/full_system/build/test/test
```

Chạy ở Terminal A:

```bash
mkdir -p "$GVSOC_OUT/full_system_skip"
set -o pipefail

gvsoc --target=pulp-open \
  --work-dir="$GVSOC_OUT/full_system_skip" \
  --binary="$PULP_REPO/sw/full_system/build/test/test" run \
  2>&1 | tee "$GVSOC_OUT/full_system_skip/run.log"
```

Kết quả đúng phải có đủ các trạng thái sau (không kiểm tra thứ tự tuyệt đối,
vì phase 3 hoàn tất bất đồng bộ và dòng `OK` của phase 3 có thể xuất hiện sau
phase 7):

```text
[PHASE 0] ... OK
[PHASE 1] ... OK
[PHASE 2] ... OK
[PHASE 4] ... OK
[PHASE 5] ... OK
[PHASE 6] ... OK
[PHASE 7] ... SKIP (DEMO_SKIP_HWPE)
[PHASE 3] ... OK
[PHASE 8] ... OK
==== FULL-SYSTEM SUMMARY: SUCCESS (0 phase loi)
```

Bản này chứng minh phase 0–6 và 8 chạy được. Nó **không** chứng minh HWPE hoạt
động.

### 10.2. Bản có HWPE, chạy với timeout

Build lại ở Terminal B:

```bash
cd "$PULP_REPO"
make -C sw/full_system clean all
```

Chạy ở Terminal A:

```bash
mkdir -p "$GVSOC_OUT/full_system_hwpe"
set -o pipefail
set +e

timeout 20 stdbuf -oL -eL gvsoc --target=pulp-open \
  --work-dir="$GVSOC_OUT/full_system_hwpe" \
  --binary="$PULP_REPO/sw/full_system/build/test/test" run \
  2>&1 | tee "$GVSOC_OUT/full_system_hwpe/run.log"

hwpe_rc=${PIPESTATUS[0]}
set -e
echo "HWPE exit code: $hwpe_rc"
test "$hwpe_rc" -eq 124
```

Kết quả đúng:

- phase 0–6 in `OK`;
- không có kết quả phase 7;
- timeout trả exit code 124.

Phân loại: HWPE datamover `UNSUPPORTED` trên target này. Không tăng timeout:
chương trình đang chờ một model không tồn tại.

## 11. Bước 5 — microbenchmark GVSoC và tính tất định

Chạy hai lần ở Terminal A:

```bash
mkdir -p "$GVSOC_OUT/step4_microbench"
set -o pipefail

make -C sw/gvsoc/ubench clean all run 2>&1 \
  | tee "$GVSOC_OUT/step4_microbench/run1.log"

make -C sw/gvsoc/ubench run 2>&1 \
  | tee "$GVSOC_OUT/step4_microbench/run2.log"

diff \
  <(grep '^CSV,' "$GVSOC_OUT/step4_microbench/run1.log") \
  <(grep '^CSV,' "$GVSOC_OUT/step4_microbench/run2.log")
```

Kết quả đúng: `diff` không in gì và exit 0.

Các dấu hiệu sanity:

- ALU cluster khoảng 12 cycle/vòng;
- load phụ thuộc chậm hơn load độc lập khoảng 1 cycle/vòng;
- `ld_stall=1000` cho 1.000 load-use;
- same-bank và different-bank gần như không khác nhau;
- `tcdm_cont=0` ở mọi core;
- DMA tiến gần 8 byte/cycle khi block lớn.

Same-bank không chậm hơn là giới hạn của model, không phải kết luận rằng RTL
không có bank contention.

## 12. Bước 6 — build ELF dùng chung cho GVSoC và RTL

Chạy ở Terminal B:

```bash
cd "$PULP_REPO"

make -C sw/gvsoc/ubench_rt clean all
make -C sw/gvsoc/icache_sweep clean all

test -x sw/gvsoc/ubench_rt/build/test/test
test -x sw/gvsoc/icache_sweep/build/test/test

mkdir -p "$GVSOC_OUT/step5_compare"
sha256sum sw/gvsoc/ubench_rt/build/test/test \
  | tee "$GVSOC_OUT/step5_compare/ubench_rt.sha256"
sha256sum sw/gvsoc/icache_sweep/build/test/test \
  | tee "$GVSOC_OUT/step5_compare/icache_sweep.sha256"
```

Không build lại ELF giữa lượt GVSoC và lượt RTL. File hash là bằng chứng hai
simulator nhận cùng chương trình.

## 13. Bước 7 — chạy ELF dùng chung trên GVSoC

Chạy ở Terminal A.

### 13.1. `ubench_rt`

```bash
mkdir -p "$GVSOC_OUT/step5_compare/gvsoc_wd"
set -o pipefail

gvsoc --target=pulp-open \
  --work-dir="$GVSOC_OUT/step5_compare/gvsoc_wd" \
  --binary="$PULP_REPO/sw/gvsoc/ubench_rt/build/test/test" run \
  2>&1 | tee "$GVSOC_OUT/step5_compare/gvsoc.log"

grep 'INFO,done,rc=0' "$GVSOC_OUT/step5_compare/gvsoc.log"
```

Kết quả đúng phải có `INFO,done,rc=0`.

### 13.2. I-cache gốc 4 KiB

```bash
mkdir -p "$GVSOC_OUT/step5_compare/icache_pulp_open"

gvsoc --target-dir="$PULP_REPO/sw/gvsoc/targets" \
  --target=pulp-open \
  --work-dir="$GVSOC_OUT/step5_compare/icache_pulp_open" \
  --binary="$PULP_REPO/sw/gvsoc/icache_sweep/build/test/test" run \
  2>&1 | tee "$GVSOC_OUT/step5_compare/icache_pulp_open.log"
```

### 13.3. I-cache biến thể 8 KiB

```bash
mkdir -p "$GVSOC_OUT/step5_compare/icache_8k"

gvsoc --target-dir="$PULP_REPO/sw/gvsoc/targets" \
  --target=pulp-open-icache8k \
  --work-dir="$GVSOC_OUT/step5_compare/icache_8k" \
  --binary="$PULP_REPO/sw/gvsoc/icache_sweep/build/test/test" run \
  2>&1 | tee "$GVSOC_OUT/step5_compare/icache_8k.log"
```

Hai log phải kết thúc bằng `INFO,done,rc=0`. Với code 6 KiB, kết quả tham chiếu:

```text
pulp-open 4 KiB:          153662 cycle
pulp-open-icache8k:        77342 cycle
```

## 14. Bước 8 — chạy cùng ELF trên RTL Questa

### 14.1. Khởi động license trước

Chạy ở Terminal B. Khởi động license trước khi pipe runner qua `tee` để daemon
không giữ pipe log mở sau khi test đã kết thúc:

```bash
export QUESTA_HOME=/home/dungpc/questasim

if ! pgrep -x lmgrd >/dev/null; then
  "$QUESTA_HOME/linux_x86_64/lmgrd" \
    -c "$QUESTA_HOME/LICENSE.dat" \
    -l "$QUESTA_HOME/license_server.log"
fi

pgrep -a lmgrd
pgrep -a mgcld
```

### 14.2. RTL `ubench_rt`

```bash
cd "$PULP_REPO"
set -o pipefail

APP_DIR="$PULP_REPO/sw/gvsoc/ubench_rt" \
SIM_TIMEOUT="200 ms" \
WALL_TIMEOUT=7200 \
PULP_RISCV_GCC_TOOLCHAIN=/opt/pulp-toolchain \
sw/full_system/run_sim.sh all run \
  2>&1 | tee "$GVSOC_OUT/step5_compare/rtl.log"

grep 'INFO,done,rc=0' "$GVSOC_OUT/step5_compare/rtl.log"
grep 'RUNNER|PASS (exit 0)' "$GVSOC_OUT/step5_compare/rtl.log"
```

Kết quả đúng phải có cả hai dòng trên. Thời gian tham chiếu là 11 phút 39 giây.

Questa 10.7c có thể in bốn thông báo `vsim-191` lúc khởi động và kết thúc bằng
`Errors: 4`. Chỉ chấp nhận đây là cảnh báo đã biết khi:

- test thật sự in `INFO,done,rc=0`;
- testbench nhận status `0x00000000`;
- runner in `RUNNER|PASS (exit 0)`.

Nếu thiếu một trong ba điều kiện, coi lượt chạy là FAIL.

### 14.3. RTL `icache_sweep`

```bash
APP_DIR="$PULP_REPO/sw/gvsoc/icache_sweep" \
SIM_TIMEOUT="200 ms" \
WALL_TIMEOUT=7200 \
PULP_RISCV_GCC_TOOLCHAIN=/opt/pulp-toolchain \
sw/full_system/run_sim.sh all run \
  2>&1 | tee "$GVSOC_OUT/step5_compare/icache_rtl.log"

grep 'INFO,done,rc=0' "$GVSOC_OUT/step5_compare/icache_rtl.log"
grep 'RUNNER|PASS (exit 0)' "$GVSOC_OUT/step5_compare/icache_rtl.log"
```

Thời gian tham chiếu là 7 phút 07 giây.

## 15. Bước 9 — sinh bảng so sánh

Chạy từ terminal nào có `/usr/bin/python3`:

```bash
cd "$PULP_REPO"
set -o pipefail

sw/gvsoc/analyze/compare_ubench.py \
  "$GVSOC_OUT/step5_compare/gvsoc.log" \
  "$GVSOC_OUT/step5_compare/rtl.log" \
  | tee "$GVSOC_OUT/step5_compare/compare.md"

wc -l "$GVSOC_OUT/step5_compare/compare.md"
```

Kết quả đúng: bảng có 31 dòng, gồm header, separator và 29 phép đo.

Các số tham chiếu quan trọng:

| Phép đo | GVSoC | RTL | GVSoC/RTL | Kết luận |
|---|---:|---:|---:|---|
| FC ALU | 22.003 | 12.007 | 1,83 | FC fetch của GVSoC quá chậm |
| Cluster ALU | 12.039 | 12.092 | 1,00 | Khớp |
| Cluster load-use | 7.042 | 7.047 | 1,00 | Khớp |
| Cluster pointer chase L2 | 4.504 | 4.516 | 1,00 | Khớp |
| TCDM khác bank, 8 core | 810 | 931 | 0,87 | GVSoC lạc quan |
| TCDM cùng bank, 8 core | 778 | 1.032 | 0,75 | GVSoC thiếu contention |
| 8 core cùng đọc L2 | 2.570 | 2.686 | 0,96 | Lệch 4% |
| DMA L2->L1 256 B | 81 | 111 | 0,73 | Lệch lớn ở gói nhỏ |
| DMA L2->L1 8 KiB | 1.071 | 1.177 | 0,91 | Lệch 9% |
| Barrier 8 core | 2.596 | 2.864 | 0,91 | Lệch 9% |

### 15.1. So sánh I-cache

```bash
sw/gvsoc/analyze/csv_table.py \
  "$GVSOC_OUT/step5_compare/icache_pulp_open.log" \
  --cols cycles,instr,imiss | grep icache_8core

sw/gvsoc/analyze/csv_table.py \
  "$GVSOC_OUT/step5_compare/icache_8k.log" \
  --cols cycles,instr,imiss | grep icache_8core

sw/gvsoc/analyze/csv_table.py \
  "$GVSOC_OUT/step5_compare/icache_rtl.log" \
  --cols cycles,instr,imiss | grep icache_8core
```

Kết quả tham chiếu, core 0:

| Code | GVSoC 4 KiB | GVSoC 8 KiB | RTL 4 KiB |
|---|---:|---:|---:|
| 256 B | 2.658 | 2.658 | 2.673 |
| 1 KiB | 12.498 | 12.498 | 10.389 |
| 2 KiB | 25.710 | 25.678 | 20.761 |
| 4 KiB | 53.870 | 51.438 | 44.610 |
| 6 KiB | 153.662 | 77.342 | 145.899 |

Điểm gãy khi code vượt shared I-cache 4 KiB phải xuất hiện ở cả GVSoC 4 KiB và
RTL. Target 8 KiB phải tránh được điểm gãy với code 6 KiB.

## 16. Bước 10 — phân loại coverage

Dùng các nhãn:

| Nhãn | Khi sử dụng |
|---|---|
| `PASS` | Chức năng chạy đúng, kết thúc bình thường |
| `PARTIAL` | Chạy được nhưng thiếu thao tác/counter hoặc timing không đủ tin cậy |
| `UNSUPPORTED` | Target không có model |
| `FAIL` | Đáng lẽ được hỗ trợ nhưng test sai |
| `NOT TESTED` | Chưa có test/ELF phù hợp |

Kết luận baseline:

| Khối | Coverage |
|---|---|
| FC | `PASS` chức năng, `PARTIAL` timing |
| Cluster 8 PE | `PASS` |
| Event unit/barrier | `PASS` chức năng, `PARTIAL` timing |
| L1 TCDM | `PARTIAL`, thiếu bank contention |
| L2 | `PASS`; timing một core khớp tốt |
| I-cache | `PASS` chức năng, `PARTIAL` refill timing |
| MCHAN DMA | `PASS` chức năng, `PARTIAL` timing |
| UART | `PASS` |
| HyperRAM | `PASS` |
| HyperFlash | `PARTIAL` |
| Filesystem | `PASS` |
| Shared FPU | `NOT TESTED`, chưa có test độc lập phù hợp |
| HWPE datamover | `UNSUPPORTED` |
| Power | `PARTIAL`, chỉ L1 |

## 17. Kiểm tra cuối

```bash
grep -c ' PASS ' "$GVSOC_OUT/step1/summary.txt"
grep 'FULL-SYSTEM SUMMARY: SUCCESS' "$GVSOC_OUT/full_system_skip/run.log"
grep 'RUNNER|PASS (exit 0)' "$GVSOC_OUT/step5_compare/rtl.log"
grep 'RUNNER|PASS (exit 0)' "$GVSOC_OUT/step5_compare/icache_rtl.log"
wc -l "$GVSOC_OUT/step5_compare/compare.md"

ps -eo pid,etime,stat,cmd \
  | grep -Ei 'gvsoc|vsim|run_sim\.sh' \
  | grep -v grep || true
```

Giá trị mong đợi:

```text
12
FULL-SYSTEM SUMMARY: SUCCESS (0 phase loi)
RUNNER|PASS (exit 0)
RUNNER|PASS (exit 0)
31 .../compare.md
```

Không được còn process `gvsoc`, `vsim` hoặc `run_sim.sh`. `lmgrd` và
`mgcld` có thể tiếp tục chạy; đó là license daemon, không phải simulation.

## 18. Dọn artifact lớn

Mỗi work directory GVSoC có thể chứa `hyperflash.bin` 64 MiB. Đây là scratch
file có thể tái tạo. Kiểm tra trước:

```bash
find "$GVSOC_OUT" -type f -name hyperflash.bin -print
du -sh "$GVSOC_OUT"
```

Sau khi đã giữ log và `gvsoc_config.json`, có thể xóa các file vừa liệt kê:

```bash
find "$GVSOC_OUT" -type f -name hyperflash.bin -delete
```

Không xóa `gvsoc_config.json`, `compare.md`, log RTL/GVSoC, summary smoke
test hoặc các file profile đã tổng hợp.

## 19. Xử lý lỗi thường gặp

| Triệu chứng | Nguyên nhân | Cách xử lý |
|---|---|---|
| `No module named prettytable` hoặc `elftools` | Python Miniforge đứng trước `/usr/bin` | Mở Terminal A mới và `source sw/gvsoc/env.sh` |
| CMake/Xilinx báo thiếu `libidn.so.11` | Xilinx SDK cũ đứng trước system CMake | Dùng lại `env.sh`, không tự chèn Xilinx SDK vào PATH |
| `Unable to open binary` khi có `--work-dir` | Binary là đường dẫn tương đối | Luôn dùng `--binary="$PULP_REPO/.../test"` |
| `flash_with_ram` FAIL tại `0x40881` | HyperFlash model không erase/reprogram đầy đủ | Phân loại `PARTIAL`; không sửa test thành PASS |
| `full_system` treo sau phase 6 | Không có model HWPE datamover | Xác nhận bằng timeout; dùng `SKIP_HWPE=1` cho các phase còn lại |
| `TCDM_CONT=0` khi 8 core cùng bank | Model không có arbitration tương đương RTL | Không dùng counter/timing này; chạy RTL |
| GVSoC không in gì trước khi timeout | stdout bị buffer | Dùng `stdbuf -oL -eL` và marker phase |
| Questa không lấy được license | `lmgrd` chưa chạy | Khởi động license như mục 14.1 |
| Questa in `vsim-191`, `Errors: 4` nhưng runner PASS | Lỗi nội bộ lúc startup của Questa 10.7c trong baseline | Chỉ chấp nhận nếu test `rc=0`, status 0 và runner PASS |
| Runner kết thúc nhưng `tee` còn sống | License daemon được khởi động bên trong pipeline | Khởi động `lmgrd` trước khi gọi runner |
| VCD tăng rất nhanh | Dùng `--event=.*` trên workload dài | Dừng test; chỉ inventory bằng ELF `hello`; không chạy `fork_power` |

## 20. Khi nào phải quay lại RTL

Không dùng GVSoC làm nguồn số tuyệt đối khi:

- nhiều core cùng truy cập một bank L1;
- cần counter `LD_EXT*`, `ST_EXT*`, `TCDM_CONT`, `JR_STALL`;
- workload chạy phần lớn trên FC;
- cần timing chính xác của DMA nhỏ, barrier hoặc refill L0;
- cần HWPE, shared FPU hoặc pad-level behavior;
- cần AXI/APB handshake, backpressure, CDC hoặc reset synchronization;
- cần Fmax, critical path, area hoặc power sign-off.

Trong các trường hợp đó, dùng RTL simulation, CDC, synthesis, STA hoặc
post-layout power analysis tương ứng.
