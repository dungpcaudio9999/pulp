# Hướng dẫn từng bước: chạy một ELF trên GVSoC và RTL PULP

Tài liệu này tái lập toàn bộ demo `flow_demo`: viết/build chương trình C thành
**một ELF duy nhất**, chạy ELF đó trên GVSoC và RTL/Questa, thu log lệnh, thu
waveform, rồi sinh trang HTML để so sánh hai backend.

Các lệnh bên dưới giả sử repository nằm tại:

```text
/home/dungpc/ndmoney4porche/projects/pulp
```

Ngày và môi trường đã kiểm chứng: 2026-10-03, Questa 10.7c,
`/opt/pulp-toolchain`, target GVSoC `pulp-open`.

## 1. Hiểu đúng kết quả sẽ quan sát

```text
flow_demo.c
    |
    +-- PULP GCC -O2 -g --> flow_demo (ELF RISC-V 32-bit)
                              |
                              +-- GVSoC --> FLOW log + FC/PE0 instruction trace
                              |
                              +-- RTL/Questa --> FLOW log + FC/8-PE trace + VCD
                                                        |
                                                        +-- GTKWave
                              |
                              +-- flow_visualize.py --> flow_viewer.html
```

Ba loại bằng chứng bổ sung cho nhau:

| Dữ liệu | Cho biết gì | Không cho biết đầy đủ gì |
|---|---|---|
| `FLOW|...` stdout | Chương trình đã đi qua phase nào, dữ liệu đúng hay sai | Từng instruction và handshake RTL |
| Instruction trace | PC, opcode, register, địa chỉ nhớ của FC/PE | Hoạt động tự trị bên trong DMA/interconnect |
| VCD RTL | Busy/fetch, event unit, TCDM request, AXI valid-ready | Ý nghĩa cấp cao của thuật toán C |

GVSoC là mô hình mô phỏng kiến trúc/timing, không phải RTL. Vì vậy mục tiêu là
chạy **cùng một ELF** rồi đối chiếu hành vi, không khẳng định hai mô hình phải có
cycle giống tuyệt đối.

## 2. Workload đang làm gì

Nguồn chính là `sw/flow_demo/flow_demo.c`. Chương trình chia thành bảy phase có
hàm `noinline` và marker ổn định:

| Phase | Nơi chạy | Hoạt động chính |
|---:|---|---|
| 0 | FC | Khởi tạo dữ liệu L2 và tính checksum |
| 1 | FC | Đọc timer và chạy vòng ALU ngắn |
| 2 | FC | Bật cluster, giao việc và chờ cluster |
| 3 | PE0...PE7 | Tám PE ghi xen kẽ vào L1/TCDM |
| 4 | PE0...PE7 | Barrier rồi đọc chéo dữ liệu của PE kế bên |
| 5 | PE0 | MCHAN DMA L2 -> L1 -> L2, kiểm dữ liệu |
| 6 | FC | Tổng hợp lỗi, in PASS/FAIL và thoát |

Các phần tử giúp trace dễ đọc:

- Mỗi phase nằm trong một hàm `phaseN_*()` và được giữ lại bằng `noinline`.
- Build dùng `-O2 -g`: vẫn có tối ưu nhưng giữ DWARF để ánh xạ PC về source.
- Marker dạng `FLOW|<phase>|BEGIN/END|<name>` xuất hiện ở cả hai backend.
- Tám PE dùng stack 4 KiB/core; tổng 32 KiB, còn chỗ cho dữ liệu L1.
- DMA có giới hạn polling; lỗi phần cứng không biến thành vòng chờ vô hạn.
- PE1...PE7 gom lỗi về PE0 dưới mutex; lỗi của core phụ không bị runtime bỏ qua.

## 3. Điều kiện cần

### 3.1. Công cụ

Kiểm tra nhanh:

```bash
cd /home/dungpc/ndmoney4porche/projects/pulp

test -x /opt/pulp-toolchain/bin/riscv32-unknown-elf-gcc
test -x "$HOME/questasim/bin/vsim"
test -f pulp-runtime/configs/pulp.sh
test -f sim/compile.tcl
test -d sim/work
/usr/bin/python3 -c 'import elftools'
```

Các thành phần cần có:

- PULP RISC-V GCC tại `/opt/pulp-toolchain`;
- GVSoC tại `$HOME/gvsoc` và PULP SDK tại `$HOME/pulp-sdk`;
- QuestaSim tại `$HOME/questasim`, license sử dụng được;
- `pulp-runtime` trong repository;
- `/usr/bin/python3` có `pyelftools`;
- GTKWave nếu muốn xem VCD bằng GUI.

Nếu thiếu `pyelftools`:

```bash
/usr/bin/python3 -m pip install pyelftools
```

### 3.2. Chỉ khi RTL chưa từng được build

Không cần chạy lại mục này nếu đã có `sim/work/vopt_tb` và flow RTL khác đang
chạy được. Trên checkout sạch:

```bash
cd /home/dungpc/ndmoney4porche/projects/pulp
./bender checkout
./patch-deps
make scripts

source setup/vsim.sh
ulimit -n 4096
cd sim
make clean
vmap -c
make lib
make build
make opt
cd ..
```

Không dùng `make checkout` trên checkout sạch của cây nguồn này: cần chèn
`./patch-deps` giữa `bender checkout` và `make scripts`. Hướng dẫn dựng RTL đầy
đủ hơn nằm ở `doc/dungpc/master_analysis/simulation/RUNBOOK.md`.

Kiểm tra đầu ra:

```bash
test -d sim/work/vopt_tb
test -f rtl/tb/remote_bitbang/librbs.so
```

## 4. Bước 1 — xem các file của demo

```bash
cd /home/dungpc/ndmoney4porche/projects/pulp
ls -l sw/flow_demo
```

| File | Vai trò |
|---|---|
| `flow_demo.c` | Workload C |
| `Makefile` | Build ELF bằng `pulp-runtime`, bật `-O2 -g` |
| `flow_visualize.py` | Parse hai format trace và sinh HTML độc lập |
| `flow_wave_capture.do` | Chọn tín hiệu RTL và ghi VCD nén |
| `README.md` | Lệnh chạy ngắn gọn |

Nếu chỉnh workload, giữ nguyên các nguyên tắc sau để viewer còn ánh xạ tốt:

1. phase là hàm `noinline`;
2. marker `FLOW|...` có BEGIN và END;
3. không bỏ `-g`;
4. không dùng dữ liệu ngẫu nhiên nếu cần đối chiếu backend;
5. không tăng stack/buffer vượt ngân sách L1 64 KiB.

## 5. Bước 2 — build đúng một ELF

Mở một shell sạch dành cho build/runtime:

```bash
cd /home/dungpc/ndmoney4porche/projects/pulp

export PATH=$(printf '%s' "$PATH" | tr ':' '\n' | grep -v miniforge3 | paste -sd:)
export PULP_RISCV_GCC_TOOLCHAIN=/opt/pulp-toolchain
source pulp-runtime/configs/pulp.sh
export PULP_PROJECT_HOME="$PWD"
export PULP_SDK_HOME="$PWD/pulp-runtime"
export PULP_RUNTIME_HOME="$PWD/pulp-runtime"

make -C sw/flow_demo clean all
```

ELF được tạo tại:

```text
sw/flow_demo/build/flow_demo/flow_demo
```

Kiểm tra định dạng, debug info và symbol phase:

```bash
file sw/flow_demo/build/flow_demo/flow_demo
/opt/pulp-toolchain/bin/riscv32-unknown-elf-readelf -h \
  sw/flow_demo/build/flow_demo/flow_demo
/opt/pulp-toolchain/bin/riscv32-unknown-elf-readelf -S \
  sw/flow_demo/build/flow_demo/flow_demo | grep debug
/opt/pulp-toolchain/bin/riscv32-unknown-elf-nm -n \
  sw/flow_demo/build/flow_demo/flow_demo | grep phase
```

Kỳ vọng quan trọng:

- `ELF 32-bit`, machine `RISC-V`;
- entry point `0x1c008080`;
- có section `.debug_info` hoặc các section `.debug_*`;
- có symbol `phase0_*` đến `phase6_*`.

Ghi hash ngay sau build:

```bash
mkdir -p report/gvsoc_demo
sha256sum sw/flow_demo/build/flow_demo/flow_demo \
  | tee report/gvsoc_demo/elf.sha256
```

Hash của lượt đã nghiệm thu:

```text
7fff5157f6c4739a53511d85478b6c8951c068487aa24f32fb7e1272ff89c39a
```

Nếu sửa C rồi build lại, hash mới là hợp lệ; điều bắt buộc là **không build lại
giữa lượt GVSoC và lượt RTL**.

## 6. Bước 3 — chạy ELF trên GVSoC và lấy instruction trace

Nên dùng shell riêng vì `sw/gvsoc/env.sh` thay đổi môi trường theo PULP SDK dành
cho GVSoC:

```bash
cd /home/dungpc/ndmoney4porche/projects/pulp
source sw/gvsoc/env.sh

mkdir -p report/gvsoc_demo/gvsoc
gvsoc --target=pulp-open \
  --work-dir="$PWD/report/gvsoc_demo/gvsoc" \
  --binary="$PWD/sw/flow_demo/build/flow_demo/flow_demo" \
  --trace=chip/soc/fc/insn:fc.log \
  --trace=chip/cluster/pe0/insn:pe0.log run \
  2>&1 | tee report/gvsoc_demo/gvsoc.log
```

Ý nghĩa hai trace selector:

- `chip/soc/fc/insn`: từng instruction của Fabric Controller;
- `chip/cluster/pe0/insn`: từng instruction của PE0 trong cluster.

Chỉ trace PE0 trên GVSoC để giữ dung lượng hợp lý. Phase 3 vẫn chứng minh đủ tám
PE qua tám dòng `FLOW|3|CORE|...|pe=0..7`.

Kiểm tra PASS:

```bash
rg 'FLOW\|[0-6]\|' report/gvsoc_demo/gvsoc.log
rg 'FLOW\|6\|RESULT\|PASS\|errors=0' report/gvsoc_demo/gvsoc.log
wc -l report/gvsoc_demo/gvsoc/fc.log \
      report/gvsoc_demo/gvsoc/pe0.log
```

Các giá trị dữ liệu phải thống nhất:

```text
L2 checksum = 0x9c7e7a4a
ALU result  = 0x41eb8881
DMA src     = DMA dst = 0x9c7e7a4a
DMA bytes   = 256
errors      = 0
```

## 7. Bước 4 — chạy chính ELF đó trên RTL/Questa

Mở shell mới, không kế thừa môi trường GVSoC:

```bash
cd /home/dungpc/ndmoney4porche/projects/pulp

APP_DIR="$PWD/sw/flow_demo" \
SIM_TIMEOUT="80 ms" \
WALL_TIMEOUT=3600 \
PULP_RISCV_GCC_TOOLCHAIN=/opt/pulp-toolchain \
sw/full_system/run_sim.sh all run
```

`all run` không có `clean`, vì vậy sử dụng ELF đã build ở bước 2. Nếu muốn build
lại từ sạch, dùng `clean all run`, nhưng sau đó phải ghi lại hash và đảm bảo GVSoC
cũng dùng đúng ELF mới đó.

Hai watchdog có ý nghĩa khác nhau:

- `SIM_TIMEOUT="80 ms"`: giới hạn thời gian mô phỏng;
- `WALL_TIMEOUT=3600`: giới hạn thời gian thực của process group.

Kết quả RTL nằm trong `sw/flow_demo/build/`:

```text
transcript                  stdout và log Questa
trace_core_1f_0.log         FC (cluster id 31, core 0)
trace_core_00_0.log         cluster PE0
...
trace_core_00_7.log         cluster PE7
```

Kiểm tra PASS:

```bash
rg 'FLOW\|6\|RESULT\|PASS\|errors=0' sw/flow_demo/build/transcript
rg 'Received status core: 0x00000000' sw/flow_demo/build/transcript
for n in 0 1 2 3 4 5 6 7; do
  test -s "sw/flow_demo/build/trace_core_00_${n}.log"
done
test -s sw/flow_demo/build/trace_core_1f_0.log
```

Questa 10.7c trong môi trường đã kiểm chứng có thể in bốn `vsim-191`. Đánh giá
thành công theo exit code, marker PASS và `Received status ... 0x00000000`, không
chỉ dựa vào bộ đếm `Errors:` cuối transcript.

## 8. Bước 5 — lưu artifact RTL vào report

```bash
cd /home/dungpc/ndmoney4porche/projects/pulp
mkdir -p report/gvsoc_demo/rtl/raw

cp sw/flow_demo/build/transcript report/gvsoc_demo/rtl/transcript.log
cp sw/flow_demo/build/trace_core_1f_0.log report/gvsoc_demo/rtl/raw/
cp sw/flow_demo/build/trace_core_00_0.log report/gvsoc_demo/rtl/raw/
cp sw/flow_demo/build/trace_core_00_1.log report/gvsoc_demo/rtl/raw/
cp sw/flow_demo/build/trace_core_00_2.log report/gvsoc_demo/rtl/raw/
cp sw/flow_demo/build/trace_core_00_3.log report/gvsoc_demo/rtl/raw/
cp sw/flow_demo/build/trace_core_00_4.log report/gvsoc_demo/rtl/raw/
cp sw/flow_demo/build/trace_core_00_5.log report/gvsoc_demo/rtl/raw/
cp sw/flow_demo/build/trace_core_00_6.log report/gvsoc_demo/rtl/raw/
cp sw/flow_demo/build/trace_core_00_7.log report/gvsoc_demo/rtl/raw/
```

Sao chép giúp report không bị thay đổi khi một test khác tái sử dụng thư mục
`sw/flow_demo/build/`.

## 9. Bước 6 — thu waveform RTL chọn lọc

Không dump đệ quy toàn thiết kế: file rất lớn và khó đọc. Do-file
`flow_wave_capture.do` chỉ lấy 24 nhóm/tín hiệu liên quan tới:

- reset, exit status và FC fetch;
- cluster clock/reset/fetch/busy;
- event-unit busy/clock enable của tám PE;
- MCHAN busy/event/TCDM request-grant;
- AXI read/write valid-ready của DMA.

Sau khi bước RTL thường đã tạo stimuli và symlink trong `build/`, chạy lượt VCD:

```bash
cd /home/dungpc/ndmoney4porche/projects/pulp
export DO_FILES="-do $PWD/sw/flow_demo/flow_wave_capture.do"

APP_DIR="$PWD/sw/flow_demo" \
SIM_TIMEOUT="80 ms" \
WALL_TIMEOUT=3600 \
PULP_RISCV_GCC_TOOLCHAIN=/opt/pulp-toolchain \
sw/full_system/run_sim.sh all run

unset DO_FILES
```

Do-file tự `run`, đọc `/tb_pulp/exit_status`, flush VCD và thoát. Kỳ vọng log có:

```text
FLOW-VCD|signals=24
FLOW-VCD|exit_status=0
```

VCD được ghi theo working directory của Questa:

```text
sw/flow_demo/build/flow_demo.vcd.gz
```

Lưu vào report và kiểm tra file nén:

```bash
mkdir -p report/gvsoc_demo/rtl/wave
cp sw/flow_demo/build/flow_demo.vcd.gz \
   report/gvsoc_demo/rtl/wave/flow_demo.vcd.gz
gzip -t report/gvsoc_demo/rtl/wave/flow_demo.vcd.gz
```

File `report/gvsoc_demo/rtl/wave/flow_demo.gtkw` đã chứa danh sách tín hiệu xem
mặc định. Nếu chưa có, có thể mở VCD, thêm signal bằng GUI rồi Save As thành file
`.gtkw`.

Mở waveform:

```bash
cd report/gvsoc_demo/rtl/wave
gtkwave flow_demo.gtkw
```

### Cách đọc phase DMA trên waveform

1. Trong instruction trace PE0, tìm `phase5_dma` để thấy CPU ghi cấu hình và poll.
2. Trên VCD, tìm khoảng `s_dmac_busy` được assert.
3. Quan sát `tcdm_init_req_o/gnt_i` cho truy cập phía L1/TCDM.
4. Quan sát `axi_master_ar_valid_o/ar_ready_i` và `r_valid_i/r_ready_o` cho chiều đọc.
5. Quan sát `axi_master_aw_valid_o/aw_ready_i` cho chiều ghi.

CPU không thực thi từng beat DMA, nên chỉ xem instruction trace sẽ bỏ mất hoạt
động transfer ở giữa bước cấu hình và bước hoàn thành.

## 10. Bước 7 — sinh HTML viewer

```bash
cd /home/dungpc/ndmoney4porche/projects/pulp

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

Kỳ vọng của bộ artifact hiện tại:

```text
Parsed 207451 raw instructions, kept 7344
```

Viewer cố ý bỏ phần lớn vòng polling `cluster_wait`; raw trace vẫn giữ nguyên.
Nếu giữ toàn bộ vòng này, hàng chục nghìn lệnh giống nhau làm luồng chính khó đọc.

Mở viewer:

```bash
firefox report/gvsoc_demo/flow_viewer.html
```

Không cần web server: dữ liệu JSON, CSS và JavaScript đều được nhúng trong một
file HTML. Các link raw trace/VCD dùng đường dẫn tương đối và hoạt động khi HTML
nằm đúng tại `report/gvsoc_demo/`.

## 11. Bước 8 — sử dụng viewer

### 11.1. Timeline phase

- Chọn `GVSoC` hoặc `RTL` để đổi backend.
- Lane FC cho phase 0, 1, 2 và 6.
- Lane PE0 cho phase 3, 4 và 5.
- Độ rộng block thể hiện thời gian mô phỏng tương đối trong backend đó.

### 11.2. Bảng cycle

Bảng so sánh lấy cycle từ instruction đầu/cuối của hàm phase. Nó bao gồm chi phí
marker/`printf`, vì vậy chỉ dùng để giải thích luồng, không phải benchmark sign-off.

### 11.3. Replay instruction

1. Chọn backend.
2. Chọn FC hoặc PE.
3. Dùng `Lùi`, `Tiếp`, hoặc `Play`.
4. Tìm theo tên hàm, opcode, PC hoặc source.
5. Xem register read/write, physical address và vùng nhớ được phân loại.

Ở RTL, PC được ánh xạ về hàm/file/dòng C bằng `addr2line` và DWARF trong chính
ELF. Với `-O2`, nhiều instruction có thể cùng ánh xạ vào một dòng C; đây là hành
vi bình thường của code tối ưu.

## 12. Bước 9 — kiểm chứng cuối cùng

Chạy toàn bộ checklist:

```bash
cd /home/dungpc/ndmoney4porche/projects/pulp

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
```

Kiểm tra đủ tám PE ở cả log chức năng:

```bash
for n in 0 1 2 3 4 5 6 7; do
  rg "FLOW\|3\|CORE\|cluster_l1\|pe=${n}\|" \
    report/gvsoc_demo/gvsoc.log \
    report/gvsoc_demo/rtl/transcript.log
done
```

Tiêu chí nghiệm thu:

1. cùng hash ELF ở toàn bộ quy trình;
2. GVSoC có `RESULT|PASS`;
3. RTL có `RESULT|PASS` và status `0x00000000`;
4. log có PE0...PE7;
5. checksum nguồn/đích DMA bằng nhau;
6. trace FC/PE không rỗng;
7. VCD hợp lệ và có transition thực;
8. viewer sinh thành công và mở độc lập.

## 13. Kết quả tham chiếu đã đo

| Phase | Core | GVSoC cycles | RTL cycles | GVSoC/RTL |
|---:|---|---:|---:|---:|
| 0 — FC + L2 | FC | 12.224 | 5.761 | 2,122 |
| 1 — FC timer + ALU | FC | 15.598 | 7.143 | 2,183 |
| 2 — launch/wait cluster | FC | 191.663 | 175.519 | 1,092 |
| 3 — 8 PE ghi L1 | PE0 | 44.674 | 43.317 | 1,031 |
| 4 — barrier + đọc chéo | PE0 | 11.397 | 10.991 | 1,037 |
| 5 — DMA L2-L1-L2 | PE0 | 20.025 | 19.493 | 1,027 |
| 6 — summary | FC | 11.989 | 5.559 | 2,157 |

Trong workload này, phase cluster lệch khoảng 2,7–3,7%; phase FC chứa nhiều
`printf` lệch khoảng 2,1 lần. Không diễn giải bảng này thành độ chính xác cycle
tổng quát của GVSoC vì workload, peripheral model và I/O đều ảnh hưởng kết quả.

## 14. Lỗi thường gặp

| Triệu chứng | Nguyên nhân thường gặp | Cách xử lý |
|---|---|---|
| `No rule to make target clean` | Chưa source config runtime | Dùng `run_sim.sh` hoặc source `pulp-runtime/configs/pulp.sh` |
| `ModuleNotFoundError: elftools` | Sai Python/thiếu pyelftools | Cài cho `/usr/bin/python3` |
| `libmpfr.so.4` hoặc `libisl.so.15` | Toolchain cũ thiếu compat libs trong loader path | Dùng `run_sim.sh`, script đã đặt `LD_LIBRARY_PATH` |
| GVSoC không tìm thấy target | Chưa `source sw/gvsoc/env.sh` | Nạp lại environment trong shell GVSoC |
| RTL treo, exit status `-1` | Test chưa kết thúc | Xem phase cuối cùng, để watchdog trả code 124 |
| Không có PE1...PE7 | Cluster không chạy đúng hoặc stack L1 lỗi | Giữ `CLUSTER_STACK_SIZE=0x1000`, kiểm marker từng PE |
| DMA báo xong nhưng checksum sai | Sai địa chỉ/hướng/byte count | Đọc đồng thời trace PE0 và AXI/TCDM waveform |
| Viewer báo `??:0` | ELF không có debug info hoặc không đúng ELF | Build `-g`, kiểm hash và truyền đúng `--elf` |
| HTML không mở link raw trace | Di chuyển HTML khỏi report | Giữ cấu trúc thư mục hoặc cập nhật link tương đối |
| VCD rất lớn | Dump đệ quy toàn hierarchy | Dùng `flow_wave_capture.do` chọn lọc |
| `FLOW-VCD|signals=0` | Hierarchy RTL đã thay đổi | Dùng `find signals` trong Questa và cập nhật pattern do-file |

## 15. Mở rộng demo đúng cách

Muốn thêm phase mới:

1. thêm hàm `static NOINLINE int phase7_...()`;
2. thêm BEGIN/END marker;
3. thêm kiểm tra dữ liệu và timeout nếu có polling;
4. cập nhật `PHASE_NAMES` trong `flow_visualize.py`;
5. build một ELF mới và ghi hash;
6. chạy lại cả GVSoC lẫn RTL;
7. nếu khối chạy tự trị, thêm tín hiệu transaction tương ứng vào do-file;
8. không so cycle cũ với cycle mới nếu binary/hash đã khác.

HWPE, flash, GPIO và floating point chưa nằm trong demo hiện tại. Khi thêm một
khối, trước hết cần xác nhận cả GVSoC target và cấu hình RTL đều có model tương
ứng; nếu không, chỉ có thể quan sát trên một backend và phải ghi rõ giới hạn đó.

## 16. Danh mục đầu ra

```text
report/gvsoc_demo/
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

Đọc nhanh kết quả: mở `flow_viewer.html`. Điều tra chi tiết CPU: mở raw trace.
Điều tra DMA/event/interconnect: mở `flow_demo.gtkw` trong GTKWave.

