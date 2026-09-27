# Hướng dẫn chạy GVSoC cho PULP, từng bước

Tài liệu này dẫn qua toàn bộ các bước của phiên khảo sát GVSoC ngày 2026-09-19: chạy
simulator, chạy test, đo, xem trace và waveform, và (tùy chọn) đối chiếu với RTL.
Mỗi bước ghi rõ lệnh, kết quả mong đợi và nội dung nên chụp màn hình.

Kết luận của khảo sát: [gvsoc_00_plan_do_dac.md](gvsoc_00_plan_do_dac.md).
Báo cáo phiên làm việc: [BAO_CAO_PHIEN_GVSOC.md](../../../../report/gvsoc_20260919/BAO_CAO_PHIEN_GVSOC.md).

Không bước nào sửa RTL hay sửa `~/gvsoc`.

## 0. Chuẩn bị

### 0.1 Điều kiện

| Cần có | Kiểm tra |
|---|---|
| GVSoC đã build | `ls ~/gvsoc/install/bin/gvsoc` |
| PULP SDK | `ls ~/pulp-sdk/configs/pulp-open.sh` |
| Toolchain | `ls /opt/pulp-toolchain/bin/riscv32-unknown-elf-gcc` |
| GTKWave, Graphviz, Firefox | `which gtkwave dot firefox` |
| Questa (chỉ cho bước 12) | `ls ~/questasim/bin/vsim` |

### 0.2 Hai terminal

GVSoC/SDK và `pulp-runtime` cần hai môi trường khác nhau: cả hai cùng đặt biến
`PULP_SDK_HOME` nhưng trỏ vào hai chỗ khác nhau. Mở **hai terminal** và đặt tên
cho dễ nhớ:

- **Terminal A (GVSoC)**: chạy simulator, test SDK, phân tích.
- **Terminal B (build)**: build các chương trình bằng `pulp-runtime` của repo.

Trong **cả hai** terminal, đặt hai biến sau. `OUT` là nơi chứa kết quả của lần chạy
này, tách khỏi `report/gvsoc_20260919/` để không ghi đè kết quả cũ:

```bash
export REPO=$HOME/ndmoney4porche/projects/pulp
export OUT=$HOME/gvsoc_run_$(date +%Y%m%d)
mkdir -p $OUT
cd $REPO
```

> **Quy tắc đường dẫn:** khi dùng `--work-dir`, GVSoC tìm file `--binary` bắt
> đầu từ thư mục làm việc. Vì vậy mọi lệnh bên dưới đều dùng đường dẫn tuyệt đối
> `$REPO/...` cho `--binary`.

---

## Bước 1. Nạp môi trường GVSoC

**Mục đích:** sửa PATH để GVSoC dùng đúng Python và toolchain.

**Terminal A:**

```bash
source $REPO/sw/gvsoc/env.sh
which gvsoc riscv32-unknown-elf-gcc python3
echo $PULP_SDK_HOME
```

**Kết quả mong đợi:**

```text
/home/dungpc/gvsoc/install/bin/gvsoc
/opt/pulp-toolchain/bin/riscv32-unknown-elf-gcc
/usr/bin/python3
/home/dungpc/pulp-sdk
```

`python3` phải là `/usr/bin/python3`. Nếu là miniforge, `gvsoc` sẽ báo
`No module named 'prettytable'`.

**Chụp:** `01_moi_truong.png` — kết quả của 4 dòng trên.

---

## Bước 2. Chạy chương trình đầu tiên

**Mục đích:** xác nhận GVSoC chạy được FC và cluster.

**Terminal A:**

```bash
cd ~/pulp-sdk/tests/hello
make clean all run                      # chạy trên FC
make clean all run USE_CLUSTER=1        # chạy trên cluster
cd $REPO
```

**Kết quả mong đợi:** lần đầu in `Hello from FC`, lần hai in
`Hello from cluster_id: 0, core_id: 0`. Mỗi lần mất vài giây.

**Chụp:** `02_hello.png` — phần cuối của hai lần chạy.

---

## Bước 3. Chạy toàn bộ test SDK

**Mục đích:** biết khối nào của PULP có model trong GVSoC.

**Terminal A:**

```bash
$REPO/sw/gvsoc/step1_sdk_tests.sh $OUT/step1        # ~1 phút
cat $OUT/step1/summary.txt
```

**Kết quả mong đợi:** 12 PASS, 1 FAIL.

| Test | Kết quả | Lý do |
|---|---|---|
| `flash_with_ram` | FAIL | Model HyperFlash không hỗ trợ lệnh erase; SDK cũng tự bỏ qua test này |
| các test còn lại | PASS | |

Script không chạy `cluster/fork_power`: test này sinh file VCD hàng chục GB.

**Chụp:** `03_test_sdk.png` — nội dung `summary.txt`.

---

## Bước 4. Trace lệnh và waveform

**Mục đích:** xem GVSoC ghi lại gì theo thời gian. Dùng `cluster/fork` vì chương
trình nhỏ (VCD khoảng 4.5 MB). Đừng bật VCD đầy đủ cho chương trình lớn:
`ubench_rt` sinh VCD 1.1 GB.

**Terminal A:**

```bash
cd ~/pulp-sdk/tests/cluster/fork
make clean all run runner_args="--trace=insn:insn.log --vcd --event=.*@all.vcd"
ls -la BUILD/PULP/GCC_RISCV/ | grep -E "insn.log|all.vcd|view.gtkw"
sed 's/\x1b\[[0-9;]*m//g' BUILD/PULP/GCC_RISCV/insn.log | grep "cluster/pe3" | head -5
```

**Kết quả mong đợi:** có `insn.log` (~0.9 MB), `all.vcd` (~4.5 MB), `view.gtkw`.
Mỗi dòng trace gồm: thời điểm (ps), cycle, đường dẫn core, hàm:dòng, PC, lệnh, và
giá trị thanh ghi.

**Chụp:** `04a_trace_lenh.png` — 5 dòng trace của pe3.

Mở waveform:

```bash
gtkwave BUILD/PULP/GCC_RISCV/view.gtkw &
cd $REPO
```

Trong GTKWave, ở cây tín hiệu bên trái, mở `chip → cluster → pe0 … pe7`, rồi thêm
`busy` và `elw_stalled` của vài core, cùng `pc` của pe0. Bấm **Zoom Fit**.

**Chụp:** `04b_gtkwave.png` — thấy các core lần lượt bận rồi ngủ ở barrier
(`elw_stalled` lên 1).

---

## Bước 5. Danh mục cơ chế đo

**Mục đích:** liệt kê mọi trace, tín hiệu VCD và dòng công suất mà GVSoC có.

**Terminal A:**

```bash
$REPO/sw/gvsoc/step2_inventory.sh $OUT/step2
cat $OUT/step2/runs.txt
```

**Kết quả mong đợi:** 3 lần chạy `exit=0`; khoảng 1475 đường trace, 2555 tín hiệu
VCD, 262 dòng công suất.

**Chụp:** `05a_danh_muc.png` — nội dung `runs.txt`.

Xem tín hiệu VCD của core và của L1, gom theo component:

```bash
python3 - <<'EOF' > $OUT/step2/vcd_by_component.txt
import re, collections, os
g = collections.defaultdict(set); n = collections.defaultdict(set)
for line in open(os.environ['OUT'] + '/step2/vcd_signals.txt'):
    parts = line.strip().split('/')
    if parts[-1] == 'trace': parts = parts[:-1]
    key = re.sub(r'\d+', 'N', '/'.join(parts[:-1]))
    g[key].add(re.sub(r'\d+', 'N', parts[-1])); n[key].add('/'.join(parts[:-1]))
for k in sorted(g):
    print(f"{k}  [x{len(n[k])}]: {', '.join(sorted(g[k]))}")
EOF
grep -E "^/chip/cluster/(peN|peN/lsu|lN/bankN|dma|event_unit/core_N)  " $OUT/step2/vcd_by_component.txt | cut -c1-200
```

**Chụp:** `05b_tin_hieu_vcd.png` — các nhóm tín hiệu của core, LSU, bank L1, DMA,
event unit.

Tham số chỉnh được lúc chạy và sơ đồ kiến trúc:

```bash
gvsoc --target=pulp-open target_properties
mkdir -p $OUT/diagram && cd $OUT/diagram
gvsoc --target=pulp-open diagram
dot -Tsvg architecture.dot -o architecture.svg
firefox architecture.svg &
cd $REPO
```

`diagram` ghi `architecture.dot` vào **thư mục hiện tại**, nên phải `cd` trước.

**Chụp:**
- `05c_tham_so.png` — bảng `target_properties`: chỉ có 4 tham số (`redmule`,
  `fic`, `binary`, `loopback`).
- `05d_so_do.png` — sơ đồ kiến trúc: cluster (16 bank L1, 9 PE, I-cache, DMA,
  event unit) và SoC (FC, L2, uDMA, interconnect).

---

## Bước 6. Công suất

**Mục đích:** xem component nào có model công suất.

**Terminal A:**

```bash
head -12 $OUT/step2/power.csv
grep "/chip/cluster/l1/bank" $OUT/step2/power.csv | head -4
```

**Kết quả mong đợi:** `/chip/soc/power_trace` bằng 0; toàn bộ công suất của cluster
nằm ở 16 bank L1, mỗi bank chiếm khoảng 6.25%. Core, L2, DMA và interconnect đều
không có model.

**Chụp:** `06_cong_suat.png`.

---

## Bước 7. Microbenchmark (PMSIS)

**Mục đích:** kiểm tra số đo của GVSoC bằng các phép thử có kết quả đoán trước.

**Terminal A:**

```bash
cd $REPO/sw/gvsoc/ubench
make clean all run 2>&1 | grep -E '^(CSV|INFO)' > $OUT/ubench.log
cd $REPO
sw/gvsoc/analyze/csv_table.py $OUT/ubench.log
```

**Kết quả mong đợi** (cột quan trọng):

| Dòng | Giá trị | Ý nghĩa |
|---|---|---|
| `cl_alu` | cycles ≈ 12067, instr 10010 | 10 lệnh + 2 cycle phạt nhánh mỗi vòng |
| `fc_alu` | cycles ≈ 22052 | FC chậm gần gấp đôi cluster (model fetch của FC) |
| `cl_ld_dep` / `cl_ld_indep` | 7070 / 6086; `ld_stall` 1000 / 0 | Phạt load-use 1 cycle |
| `cl_chase_l2` / `cl_chase_l1` | 4934 / 1350 | Load L2 từ cluster tốn thêm ~14 cycle |
| `tcdm_same_bank` / `tcdm_diff_bank` | ~776 / ~794; `tcdm_cont` = 0 | GVSoC không mô hình hoá xung đột bank |

Xem cả 8 core của phép thử TCDM:

```bash
sw/gvsoc/analyze/csv_table.py $OUT/ubench.log --all-cores | grep tcdm
```

**Chụp:** `07a_ubench.png` (bảng core 0) và `07b_tcdm_8core.png`.

---

## Bước 8. Build các chương trình của repo bằng `pulp-runtime`

**Mục đích:** tạo các ELF dùng cho bước 9–12. Các ELF này chạy được trên cả GVSoC
và RTL.

**Terminal B:**

```bash
export PATH=$(echo "$PATH" | tr ':' '\n' | grep -v miniforge3 | paste -sd:)
export PULP_RISCV_GCC_TOOLCHAIN=/opt/pulp-toolchain
source pulp-runtime/configs/pulp.sh
export PULP_PROJECT_HOME=$REPO PULP_SDK_HOME=$REPO/pulp-runtime

(cd sw/gvsoc/ubench_rt    && make clean all)
(cd sw/gvsoc/icache_sweep && make clean all)
(cd sw/full_system        && make clean all SKIP_HWPE=1)
ls -la sw/gvsoc/ubench_rt/build/test/test sw/gvsoc/icache_sweep/build/test/test sw/full_system/build/test/test
sha256sum sw/gvsoc/ubench_rt/build/test/test
```

**Kết quả mong đợi:** mỗi lệnh `make` kết thúc bằng dòng `LD .../build/test/test`,
không có `error`. Build `ubench_rt` hôm 2026-09-19 có sha256 bắt đầu bằng
`49bd9044`. Toolchain và source không đổi thì hash giữ nguyên.

`SKIP_HWPE=1` bỏ qua phase 7 (HWPE), vì GVSoC không có model HWPE. Build mặc định
của `full_system` (không có cờ) vẫn như cũ.

**Chụp:** `08_build.png` — lệnh `ls` và `sha256sum`.

---

## Bước 9. Chạy `full_system` của repo trên GVSoC

**Terminal A:**

```bash
gvsoc --target=pulp-open --work-dir=$OUT/full_system \
      --binary $REPO/sw/full_system/build/test/test run 2>&1 | tee $OUT/full_system.log
```

**Kết quả mong đợi:**

```text
[PHASE 0] FC, L2, duong stdout           ... OK
...
[PHASE 6] MCHAN DMA, AXI hai chieu       ... OK
[PHASE 7] HWPE datamover                 ... SKIP (DEMO_SKIP_HWPE)
[PHASE 3] PMU, cluster clk/rst, AXI      ... OK
[PHASE 8] GPIO, safe domain padmux       ... OK
==== FULL-SYSTEM SUMMARY: SUCCESS (0 phase loi)
```

**Chụp:** `09_full_system.png` — các dòng `PHASE` và `SUMMARY`.

---

## Bước 10. Microbenchmark `ubench_rt` và profile

**Terminal A:**

```bash
gvsoc --target=pulp-open --work-dir=$OUT/ubench_rt \
      --binary $REPO/sw/gvsoc/ubench_rt/build/test/test run > $OUT/ubench_rt_gvsoc.log 2>&1
sw/gvsoc/analyze/csv_table.py $OUT/ubench_rt_gvsoc.log
```

**Kết quả mong đợi:** 29 dòng cho core 0, gồm cả `l2_8core`, `dma_*` và
`barrier_8core`.

**Chụp:** `10a_ubench_rt.png`.

Profile theo lệnh và theo hàm cho pe0 (trace khoảng 100 MB):

```bash
gvsoc --target=pulp-open --work-dir=$OUT/profile \
      --binary $REPO/sw/gvsoc/ubench_rt/build/test/test \
      --trace=cluster/pe0/insn:pe0.log run > /dev/null 2>&1
sed -i 's/\x1b\[[0-9;]*m//g' $OUT/profile/pe0.log
python3 -W ignore $(which gvsoc_analyze_insn) --trace $OUT/profile/pe0.log | head -30
sw/gvsoc/analyze/func_profile.py $OUT/profile/pe0.log --top 15
```

**Kết quả mong đợi:**
- `gvsoc_analyze_insn`: bảng số lần và cycle trung bình theo loại lệnh, ví dụ
  `p.sw` ~21 cycle, `p.lbu` ~12 cycle.
- `func_profile.py`: khoảng 90% thời gian nằm trong `pos_libc_prf`, `strchr`,
  `fputc`, tức là `printf`. Các kernel `k_*` chỉ chiếm vài phần trăm.

**Chụp:** `10b_theo_lenh.png`, `10c_theo_ham.png`.

---

## Bước 11. Quét kích thước code: thử đổi kiến trúc

**Mục đích:** thấy tác động của dung lượng I-cache, và cách tạo biến thể kiến trúc
mà không sửa GVSoC. Target `pulp-open-icache8k` (trong `sw/gvsoc/targets/`) giống
`pulp-open` nhưng shared I-cache là 8 KiB thay vì 4 KiB.

**Terminal A:**

```bash
for T in pulp-open pulp-open-icache8k; do
  gvsoc --target-dir=$REPO/sw/gvsoc/targets --target=$T --work-dir=$OUT/sweep_$T \
        --binary $REPO/sw/gvsoc/icache_sweep/build/test/test run > $OUT/icache_$T.log 2>&1
  echo "== $T"
  sw/gvsoc/analyze/csv_table.py $OUT/icache_$T.log --cols cycles,instr,imiss | grep 8core
done
```

**Kết quả mong đợi** (CPI của dòng `icache_8core`):

| Code | `pulp-open` (4 KiB) | `pulp-open-icache8k` (8 KiB) |
|---|---|---|
| 256 B | 1.02 | 1.02 |
| 1–4 KiB | 1.22–1.31 | 1.22–1.25 |
| 6 KiB | **2.50** | **1.26** |

Code 6 KiB vượt cache 4 KiB nên CPI tăng vọt; với 8 KiB thì vẫn vừa cache.

Xác nhận cấu hình đã được áp dụng:

```bash
grep -o '"nb_sets_bits": [0-9]*' $OUT/sweep_pulp-open-icache8k/gvsoc_config.json | sort | uniq -c
```

Phải thấy 3 dòng có giá trị `6`: shared I-cache của cluster đã thành 8 KiB. Chạy
cùng lệnh trên `$OUT/sweep_pulp-open/gvsoc_config.json` thì không có giá trị `6`.
Các giá trị `3` và `5` còn lại thuộc L0 của từng core và I-cache của FC, không đổi.

**Chụp:** `11a_icache_sweep.png`, `11b_config_icache8k.png`.

---

## Bước 12 (tùy chọn). Đối chiếu với RTL trên Questa

**Mục đích:** chạy **cùng ELF** trên RTL để biết GVSoC lệch bao nhiêu. Bước này
không sửa RTL, chỉ mô phỏng. Mất nhiều thời gian: `ubench_rt` khoảng 11 phút,
`icache_sweep` khoảng 7 phút.

**Terminal B** (runner tự nạp môi trường Questa và `pulp-runtime`; cần biến
`PULP_RISCV_GCC_TOOLCHAIN=/opt/pulp-toolchain` như ở bước 8):

```bash
# License server; runner cũng tự khởi động nếu lmgrd chưa chạy
pgrep -x lmgrd || ~/questasim/linux_x86_64/lmgrd -c ~/questasim/LICENSE.dat \
                    -l ~/questasim/license_server.log

APP_DIR=$REPO/sw/gvsoc/ubench_rt SIM_TIMEOUT="200 ms" WALL_TIMEOUT=7200 \
    sw/full_system/run_sim.sh all run > $OUT/ubench_rt_rtl.log 2>&1
tail -1 $OUT/ubench_rt_rtl.log                      # RUNNER|PASS (exit 0)

APP_DIR=$REPO/sw/gvsoc/icache_sweep SIM_TIMEOUT="200 ms" WALL_TIMEOUT=7200 \
    sw/full_system/run_sim.sh all run > $OUT/icache_rtl.log 2>&1
tail -1 $OUT/icache_rtl.log
```

`all run` dùng ELF đã build ở bước 8, nên hai bên chắc chắn chạy cùng một file.
Nếu terminal có thể bị đóng giữa chừng, thêm `setsid nohup` trước
`sw/full_system/run_sim.sh` và `&` ở cuối lệnh. Theo dõi tiến độ bằng
`tail -f $OUT/ubench_rt_rtl.log`.

Bốn dòng `vsim-191` lúc nạp thiết kế là bình thường; chúng có cả trong log PASS cũ.

So sánh (**Terminal A**):

```bash
sw/gvsoc/analyze/compare_ubench.py $OUT/ubench_rt_gvsoc.log $OUT/ubench_rt_rtl.log
sw/gvsoc/analyze/csv_table.py $OUT/icache_rtl.log --cols cycles,instr,imiss | grep 8core
```

**Kết quả mong đợi** (cột `GVSoC/RTL`):

| Dòng | Tỉ lệ | Ý nghĩa |
|---|---|---|
| `cl_alu`, `cl_ld_dep`, `cl_chase_l2` | 1.00 | Code một core trên cluster khớp RTL |
| `fc_alu` | 1.83 | GVSoC mô hình fetch của FC chậm hơn RTL |
| `tcdm_same_bank` | 0.75 | RTL có `tcdm_cont` = 127; GVSoC không có xung đột bank |
| `dma_*`, `barrier_8core` | 0.73–0.92 | GVSoC nhanh hơn RTL |

I-cache trên RTL: code 1–3 KiB có CPI ~1.01, code 6 KiB có CPI ~2.37.

**Chụp:** `12a_rtl_pass.png` (dòng `RUNNER|PASS`), `12b_so_sanh.png` (bảng
so sánh), `12c_icache_rtl.png`.

---

## Bước 13. Dọn dẹp

Mỗi thư mục chạy GVSoC có một file `hyperflash.bin` 64 MB; các file VCD và trace
cũng lớn:

```bash
find $OUT -name hyperflash.bin -delete
rm -f $OUT/profile/pe0.log
du -sh $OUT
rm -f ~/pulp-sdk/tests/cluster/fork/BUILD/PULP/GCC_RISCV/all.vcd   # sau khi đã chụp GTKWave
```

---

## Danh sách ảnh cần chụp

| Ảnh | Bước | Nội dung |
|---|---|---|
| `01_moi_truong.png` | 1 | Đường dẫn `gvsoc`, toolchain, `python3` |
| `02_hello.png` | 2 | `Hello from FC`, `Hello from cluster_id: 0` |
| `03_test_sdk.png` | 3 | `summary.txt`: 12 PASS, 1 FAIL |
| `04a_trace_lenh.png` | 4 | Trace lệnh của pe3 |
| `04b_gtkwave.png` | 4 | Waveform: `busy`, `elw_stalled` của các core |
| `05a_danh_muc.png` | 5 | Số trace / tín hiệu VCD / dòng công suất |
| `05b_tin_hieu_vcd.png` | 5 | Nhóm tín hiệu của core, LSU, L1, DMA |
| `05c_tham_so.png` | 5 | `target_properties` |
| `05d_so_do.png` | 5 | Sơ đồ kiến trúc |
| `06_cong_suat.png` | 6 | Công suất chỉ ở bank L1 |
| `07a_ubench.png`, `07b_tcdm_8core.png` | 7 | Bảng microbenchmark; TCDM 8 core |
| `08_build.png` | 8 | ELF đã build và sha256 |
| `09_full_system.png` | 9 | `full_system` SUCCESS |
| `10a_ubench_rt.png`, `10b_theo_lenh.png`, `10c_theo_ham.png` | 10 | Bảng `ubench_rt`; profile theo lệnh và theo hàm |
| `11a_icache_sweep.png`, `11b_config_icache8k.png` | 11 | CPI hai target; cấu hình đã áp |
| `12a_rtl_pass.png`, `12b_so_sanh.png`, `12c_icache_rtl.png` | 12 | RTL PASS; bảng GVSoC/RTL; I-cache RTL |

## Lỗi thường gặp

| Triệu chứng | Nguyên nhân | Cách sửa |
|---|---|---|
| `No module named 'prettytable'` | `python3` là miniforge | Chạy lại `source $REPO/sw/gvsoc/env.sh` |
| `Unable to open binary (path: sw/..., error: Bad file descriptor)` | `--binary` là đường dẫn tương đối và có `--work-dir` | Dùng `$REPO/...` |
| `gvsoc` không in gì rồi treo | Chương trình treo; stdout của GVSoC bị buffer nên mất khi bị kill | Thêm `--trace=cluster/pe0/insn:pe0.log` để xem chỗ treo |
| `full_system` treo ở phase 7 | Build không có `SKIP_HWPE=1` | Build lại như bước 8 |
| `gvsoc ... targets` báo `Missing platform_tree library for target 'rv64_untimed'` | Liệt kê cả những target chưa build | Bỏ qua; không cần lệnh này |
| `Unable to checkout a license` (bước 12) | `lmgrd` chưa chạy | Chạy lệnh `lmgrd` ở bước 12 |
| Lỗi `No rule to make target` khi build (bước 8) | Terminal B thiếu biến môi trường của `pulp-runtime` | Chạy lại khối lệnh `export`/`source` ở đầu bước 8 |
