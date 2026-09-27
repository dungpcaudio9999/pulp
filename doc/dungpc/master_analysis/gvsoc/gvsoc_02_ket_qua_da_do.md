# 13 phép đo đã thực hiện bằng GVSoC: lệnh chạy và kết quả

Ngày đo: **2026-09-19**. GVSoC `3b4c489`, target `pulp-open`, toolchain
`/opt/pulp-toolchain` (gcc 7.1.1).

Mỗi mục gồm: đo cái gì, lệnh chạy, kết quả đã đo được, và file kết quả. Tất cả số
trong tài liệu này là số thật, lấy từ `report/gvsoc_20260919/`.

Hướng dẫn chạy từng bước, kèm ảnh cần chụp:
[gvsoc_01_huong_dan_chay.md](gvsoc_01_huong_dan_chay.md).
Kết luận về mức tin cậy: [gvsoc_00_plan_do_dac.md](gvsoc_00_plan_do_dac.md).

## Vì sao đo những thứ này

Mười ba phép đo phục vụ ba mục tiêu khác nhau. Khi đọc kết quả, cần biết mỗi con số
thuộc nhóm nào, vì cách dùng chúng khác hẳn nhau.

| Mục tiêu | Mục | Dùng để làm gì |
|---|---|---|
| **A. Hiệu chuẩn công cụ** — GVSoC nói đúng không | 1, 3, 6, 13 | Biết số nào tin được, số nào không, trước khi dựa vào chúng để ra quyết định |
| **B. Đo hằng số của kiến trúc** — phần cứng này đắt ở đâu | 2, 5, 7, 8, 9 | Có bảng chi phí: một load L2 bao nhiêu cycle, DMA bao nhiêu byte mỗi cycle, một barrier bao nhiêu cycle |
| **C. Hướng dẫn viết phần mềm** — nên làm gì với chương trình của mình | 4, 10, 11, 12 | Biết ngân sách kích thước code, điểm nóng của chương trình, và lợi ích nếu đổi tham số phần cứng |

Câu hỏi thực tế mà bộ số này trả lời được:

| Câu hỏi | Mục trả lời |
|---|---|
| Dữ liệu có đáng mang vào L1 bằng DMA trước khi tính không? | 5, 8 |
| Gói DMA nên lớn bao nhiêu? | 8 |
| Chia việc cho 8 core thì mỗi phần phải lớn cỡ nào mới bõ? | 9 |
| Kernel viết dài bao nhiêu thì bắt đầu chậm vì cache lệnh? | 4, 10 |
| Nên đặt code ở FC hay ở cluster? | 2, 5 |
| Chương trình đang tốn thời gian ở đâu? | 11 |
| Khi nào buộc phải chạy RTL thay vì tin GVSoC? | 6, 13 |

## 0. Chuẩn bị (làm một lần)

```bash
export REPO=$HOME/ndmoney4porche/projects/pulp
export OUT=$HOME/gvsoc_run_$(date +%Y%m%d)
mkdir -p $OUT && cd $REPO
```

**Terminal B** — build các chương trình đo bằng `pulp-runtime`:

```bash
export PATH=$(echo "$PATH" | tr ':' '\n' | grep -v miniforge3 | paste -sd:)
export PULP_RISCV_GCC_TOOLCHAIN=/opt/pulp-toolchain
source pulp-runtime/configs/pulp.sh
export PULP_PROJECT_HOME=$REPO PULP_SDK_HOME=$REPO/pulp-runtime
(cd sw/gvsoc/ubench_rt    && make clean all)
(cd sw/gvsoc/icache_sweep && make clean all)
```

**Terminal A** — môi trường GVSoC, dùng cho mọi lệnh đo bên dưới:

```bash
source $REPO/sw/gvsoc/env.sh
```

Hai lệnh chạy chính, tạo ra dữ liệu cho mục 1–9:

```bash
# (a) 15 phép thử vi mô, bằng pulp-runtime (chạy được cả trên RTL)
gvsoc --target=pulp-open --work-dir=$OUT/ubench_rt \
      --binary $REPO/sw/gvsoc/ubench_rt/build/test/test run > $OUT/ubench_rt.log 2>&1

# (b) bản PMSIS, có thêm phép thử fork/barrier theo số core
(cd $REPO/sw/gvsoc/ubench && make clean all run) 2>&1 | grep -E '^(CSV|INFO)' > $OUT/ubench.log
```

Xem kết quả dưới dạng bảng: `sw/gvsoc/analyze/csv_table.py <log> [--all-cores] [--cols ...]`.

---

## 1. Số lệnh: lệnh, load, store, nhánh, lệnh nén

**Để làm gì:** Xác nhận GVSoC chạy đúng chương trình, và lấy số lệnh làm mẫu số để tính CPI ở mọi phép đo sau. Khi tối ưu code, đây cũng là thước đo trực tiếp: sửa xong thì số lệnh giảm bao nhiêu.

**Đo gì:** GVSoC đếm đúng số lệnh đã chạy hay không, theo từng loại.

```bash
sw/gvsoc/analyze/csv_table.py $OUT/ubench_rt.log --cols instr,ld,st,branch,btaken,rvc
```

**Kết quả:** kernel `k_alu` có thân 10 lệnh, chạy 1000 vòng, GVSoC đếm
`instr = 10003` (3 lệnh vào/ra hàm), `branch = 1000`, `btaken = 999`,
`rvc = 10002`, `ld = 0`, `st = 0`. Kernel load-use đếm `ld = 1000`.

Các số này **khớp RTL** (RTL: `instr = 10007`, chênh do vài lệnh của lời gọi hàm).

**File:** `step4/gvsoc.log`, `step3/ubench_run1.csv`.

---

## 2. Cycle và CPI của từng đoạn code

**Để làm gì:** Biết một vòng lặp thật sự tốn bao nhiêu, và **chọn chỗ đặt code**: cùng một kernel chạy trên FC tốn gần gấp đôi cluster, nên phần tính toán nặng phải đẩy xuống cluster.

**Đo gì:** một vòng lặp tốn bao nhiêu cycle, chia cho số lệnh ra CPI.

```bash
sw/gvsoc/analyze/csv_table.py $OUT/ubench_rt.log --cols cycles,instr
```

**Kết quả:**

| Kernel | Cycle | Cycle mỗi vòng | CPI |
|---|---|---|---|
| `cl_alu` (cluster, 10 lệnh/vòng) | 12039 | 12.04 | 1.20 |
| `fc_alu` (FC, cùng code) | 22003 | 22.00 | 2.20 |

Cluster: 10 lệnh + 2 cycle phạt nhánh rẽ, đúng như CV32E40P. FC chậm gần gấp đôi
vì mô hình fetch (xem mục 13).

**File:** `step4/gvsoc.log`.

---

## 3. Stall load-use (`ld_stall`)

**Để làm gì:** Biết chi phí khi lệnh dùng ngay kết quả của `lw`, tức là **có đáng sắp xếp lại lệnh hay unroll vòng lặp không**. Ở đây phạt chỉ 1 cycle, nên với code nhiều tính toán thì việc đó ít lợi; với vòng lặp toàn load thì đáng.

**Đo gì:** chi phí khi lệnh ngay sau `lw` dùng luôn kết quả.

```bash
sw/gvsoc/analyze/csv_table.py $OUT/ubench_rt.log --cols cycles,ld_stall | grep ld_
```

**Kết quả:** hai kernel có **cùng số lệnh**, chỉ khác chỗ phụ thuộc:

| Kernel | Cycle | `ld_stall` |
|---|---|---|
| `cl_ld_dep` (dùng ngay kết quả load) | 7042 | 1000 |
| `cl_ld_indep` (không dùng) | 6058 | 0 |

Chênh 984 cycle trên 1000 vòng → **phạt load-use đúng 1 cycle**. `ld_stall` đếm
đúng bằng số lần. Trên FC cũng vậy: 7019 so với 6019.

**File:** `step4/gvsoc.log`.

---

## 4. Miss lệnh (`imiss`) theo kích thước code

**Để làm gì:** Đặt **ngân sách kích thước cho kernel**: viết tới bao nhiêu byte code thì bắt đầu chậm vì nạp lệnh. Kết quả cho hai ngưỡng cụ thể để căn khi inline hay unroll.

**Đo gì:** code phải lớn tới đâu thì bắt đầu miss cache lệnh, và tốn thêm bao nhiêu.

```bash
gvsoc --target=pulp-open --work-dir=$OUT/sweep \
      --binary $REPO/sw/gvsoc/icache_sweep/build/test/test run > $OUT/icache.log 2>&1
sw/gvsoc/analyze/csv_table.py $OUT/icache.log --cols cycles,instr,imiss | grep 8core
```

**Kết quả** (8 core cùng chạy, core 0):

| Kích thước code | `imiss` | CPI |
|---|---|---|
| 256 B | 14 | 1.02 |
| 1 KiB | 2176 | 1.22 |
| 2 KiB | 5148 | 1.25 |
| 3 KiB | 8098 | 1.26 |
| 4 KiB | 12842 | 1.31 |
| 6 KiB | **92154** | **2.50** |

Hai ngưỡng: vượt 512 B (L0 riêng của mỗi core) thì CPI lên ~1.22; vượt 4 KiB
(cache dùng chung) thì `imiss` tăng 7 lần và CPI lên 2.50.

**File:** `step5/icache_sweep_pulp-open.log`.

---

## 5. Latency load: L1 và L2, từ cluster và từ FC

**Để làm gì:** Lấy **chi phí một lần chạm bộ nhớ**, cơ sở để quyết định có mang dữ liệu vào L1 bằng DMA trước khi tính hay không. Một load L2 đắt gấp 5 lần một load L1, nên vòng lặp đọc thẳng L2 sẽ rất chậm.

**Đo gì:** một lần đọc bộ nhớ mất bao nhiêu cycle. Dùng pointer chasing: mỗi load
lấy địa chỉ từ load trước, nên latency không bị che.

```bash
sw/gvsoc/analyze/csv_table.py $OUT/ubench_rt.log --cols cycles | grep chase
```

**Kết quả** (256 load mỗi phép):

| Phép thử | Cycle | Cycle mỗi load |
|---|---|---|
| `cl_chase_l1` (cluster đọc L1) | 904 | 3.5 |
| `cl_chase_l2` (cluster đọc L2) | 4504 | 17.6 |
| `fc_chase_l2` (FC đọc L2) | 910 | 3.6 |

→ **Cluster đọc L2 tốn thêm 14.1 cycle** so với đọc L1. Con số này đúng bằng tổng
latency cố định trong generator: `cluster_ico` 2 + `axi_ico` 12. RTL cùng phép thử
cho 14.0 cycle; counter `ld_ext_cyc` của RTL ghi 15.0 cycle mỗi load, vì nó đếm cả
cycle phát lệnh.

FC đọc L2 nhanh ngang cluster đọc L1, vì L2 nằm cùng phía SoC với FC.

**File:** `step4/gvsoc.log`; đối chiếu RTL: `step4/compare.md`.

---

## 6. Xung đột bank L1 khi 8 core cùng truy cập

**Để làm gì:** Định kiểm tra **cách chia dữ liệu cho 8 core** có gây dồn bank không. Kết quả lại cho thấy giới hạn của công cụ, nên đây là phép đo thuộc nhóm hiệu chuẩn: muốn đánh giá layout dữ liệu thì phải chạy RTL.

**Đo gì:** 8 core đọc L1, trường hợp mỗi core một bank riêng, so với cả 8 dồn vào
một bank.

```bash
sw/gvsoc/analyze/csv_table.py $OUT/ubench_rt.log --all-cores --cols cycles,tcdm_cont | grep tcdm
```

**Kết quả:**

| Trường hợp | Cycle (core 0–7) | `tcdm_cont` |
|---|---|---|
| Khác bank | 810–814 | 0 |
| Cùng một bank | 774–778 | 0 |

**Kết luận là một phát hiện về công cụ:** dồn 8 core vào một bank mà GVSoC vẫn
không chậm đi, `tcdm_cont` luôn 0. Đọc source xác nhận: `l1_interleaver_impl.cpp`
chuyển request thẳng tới bank, không có arbitration. **GVSoC không mô hình hoá
xung đột bank.**

RTL cùng phép thử: 1032 so với 931 cycle, `tcdm_cont` = 127 mỗi core.

**File:** `step4/compare_all_cores.md`.

---

## 7. 8 core cùng đọc L2

**Để làm gì:** Biết **đường ra khỏi cluster có nghẽn không** khi cả 8 core cùng dùng. Nếu nghẽn thì phải chuyển sang dùng DMA gom dữ liệu vào L1 thay vì để từng core tự đọc L2.

**Đo gì:** đường ra khỏi cluster có bị nghẽn khi cả 8 core cùng dùng không.

```bash
sw/gvsoc/analyze/csv_table.py $OUT/ubench_rt.log --all-cores --cols cycles | grep l2_8core
```

**Kết quả:** 2564–2570 cycle cho 128 load, tức **20.1 cycle mỗi load**, so với
17.6 cycle khi chỉ một core đọc. RTL: 2686 cycle, tức 21.0 cycle mỗi load.

Cả hai đều cho thấy tranh chấp nhỏ với kiểu truy cập này; GVSoC lệch 4%.

**File:** `step4/gvsoc.log`, `step4/compare.md`.

---

## 8. Throughput DMA và chi phí cố định, hai chiều

**Để làm gì:** Chọn **kích thước gói cho double buffering**: dưới ngưỡng nào thì chi phí gọi lấn át, và trên ngưỡng nào thì thời gian truyền tỉ lệ thuận với dung lượng.

**Đo gì:** DMA truyền nhanh bao nhiêu, và mỗi lần gọi tốn bao nhiêu cycle cố định.

```bash
sw/gvsoc/analyze/csv_table.py $OUT/ubench_rt.log --cols cycles | grep dma
```

**Kết quả** (cycle từ lúc phát lệnh tới lúc DMA báo xong, gồm cả vòng chờ):

| Kích thước | L2 → L1 | L1 → L2 |
|---|---|---|
| 64 B | 178 | 58 |
| 256 B | 81 | 73 |
| 1 KiB | 171 | 178 |
| 4 KiB | 561 | 568 |
| 8 KiB | 1071 | 1093 |

Độ dốc giữa 4 KiB và 8 KiB: **8.0 B/cycle cho L2→L1** và 7.8 B/cycle cho L1→L2,
đúng với bus 64 bit. Chi phí cố định mỗi lần gọi khoảng **50 cycle**. Với gói nhỏ,
chi phí cố định lấn át: 64 B mất gần bằng 512 B.

RTL chậm hơn 8–27%, lệch nhiều nhất ở gói nhỏ.

**File:** `step4/gvsoc.log`, `step3/ubench_run1.csv`.

---

## 9. Chi phí barrier và fork theo số core

**Để làm gì:** Quyết định **độ mịn của song song hoá**: phần việc giao cho mỗi core phải lớn hơn chi phí đồng bộ bao nhiêu lần thì mới bõ.

**Đo gì:** đồng bộ 8 core tốn bao nhiêu.

```bash
sw/gvsoc/analyze/csv_table.py $OUT/ubench.log --cols cycles | grep fork
```

**Kết quả:** đo bằng cách chạy `fork` với 100 barrier, rồi trừ đi `fork` không có
barrier nào:

| Số core | `fork_only` | `fork_barrier100` | Mỗi barrier |
|---|---|---|---|
| 1 | 163 | 1111 | 9.5 |
| 2 | 72 | 1065 | 9.9 |
| 4 | 88 | 1048 | 9.6 |
| 8 | 72 | 1048 | **9.8** |

Chi phí barrier **không tăng theo số core**, đúng với việc barrier làm bằng phần
cứng trong event unit. Chi phí fork khoảng 72 cycle. RTL: 28.6 so với 26.0 cycle
cho mỗi vòng có barrier, tức GVSoC lạc quan ~9%. Phép trừ `fork_only` chỉ chạy trên
GVSoC (bản PMSIS), nên chưa có số barrier thuần của RTL.

**File:** `step3/ubench_run1.csv`.

---

## 10. Ảnh hưởng của dung lượng I-cache (đổi kiến trúc rồi đo lại)

**Để làm gì:** Trả lời câu hỏi kiến trúc: **nếu tăng cache lệnh thì phần mềm nhanh hơn bao nhiêu**, để cân nhắc trước khi đề xuất đổi phần cứng. Cũng là mẫu quy trình cho mọi thí nghiệm 'nếu đổi X thì sao'.

**Đo gì:** nếu tăng cache dùng chung từ 4 KiB lên 8 KiB thì được gì.

```bash
for T in pulp-open pulp-open-icache8k; do
  gvsoc --target-dir=$REPO/sw/gvsoc/targets --target=$T --work-dir=$OUT/sweep_$T \
        --binary $REPO/sw/gvsoc/icache_sweep/build/test/test run > $OUT/icache_$T.log 2>&1
  echo "== $T"
  sw/gvsoc/analyze/csv_table.py $OUT/icache_$T.log --cols cycles,imiss | grep 8core
done
```

**Kết quả** (CPI, 8 core):

| Code | 4 KiB (gốc) | 8 KiB |
|---|---|---|
| 1–3 KiB | 1.22–1.26 | 1.22–1.25 |
| 4 KiB | 1.31 | 1.25 |
| 6 KiB | **2.50** | **1.26** |

Code 6 KiB chạy nhanh gấp đôi khi cache 8 KiB (153662 xuống 77342 cycle). Đây cũng
là ví dụ cho thấy **đổi tham số kiến trúc chỉ cần sửa JSON của target, không phải
build lại GVSoC**: target nằm ở `sw/gvsoc/targets/pulp-open-icache8k.py`.

**File:** `step5/icache_sweep_pulp-open.log`, `step5/icache_sweep_pulp-open-icache8k.log`.

---

## 11. Cycle và CPI theo hàm, theo loại lệnh

**Để làm gì:** Tìm **điểm nóng** của chương trình mà không phải đoán. Ví dụ ở đây: 90% thời gian nằm trong `printf`, nghĩa là mọi phép đo đặt quanh `printf` đều vô nghĩa.

**Đo gì:** thời gian của một core đi vào đâu.

```bash
gvsoc --target=pulp-open --work-dir=$OUT/profile \
      --binary $REPO/sw/gvsoc/ubench_rt/build/test/test \
      --trace=cluster/pe0/insn:pe0.log run > /dev/null 2>&1
sed -i 's/\x1b\[[0-9;]*m//g' $OUT/profile/pe0.log      # bo ma mau
python3 -W ignore $(which gvsoc_analyze_insn) --trace $OUT/profile/pe0.log
sw/gvsoc/analyze/func_profile.py $OUT/profile/pe0.log --top 10
```

**Kết quả theo hàm** (pe0, tổng 1.60 triệu cycle):

| Hàm | Cycle | % | CPI |
|---|---|---|---|
| `pos_libc_prf` | 508026 | 31.7 | 2.32 |
| `strchr` | 428628 | 26.7 | 4.50 |
| `fputc` | 312062 | 19.4 | 2.83 |
| `pos_libc_to_x` | 130726 | 8.1 | 5.75 |
| `memcpy` | 87447 | 5.4 | 5.58 |

→ khoảng **90% thời gian nằm trong `printf`**, các kernel đo chỉ vài phần trăm.
Bài học khi đo: luôn để `printf` ngoài vùng đếm.

**Kết quả theo loại lệnh:** `p.sw` 21.5 cycle, `p.lbu` 12.2 cycle (đọc chuỗi định
dạng từ L2), `add` 1.21 cycle, `lw` 1.81 cycle.

**File:** `step2/analyze_insn/func_profile.txt`, `step2/analyze_insn/analyze.txt`.

---

## 12. Công suất

**Để làm gì:** Xem GVSoC nói được gì về năng lượng. Kết quả: chỉ dùng được để **so sánh tương đối các cách truy cập L1**, không dùng làm số tuyệt đối cho toàn chip.

**Đo gì:** component nào có model công suất và tiêu thụ bao nhiêu.

```bash
gvsoc --target=pulp-open --work-dir=$OUT/power \
      --binary ~/pulp-sdk/tests/hello/BUILD/PULP/GCC_RISCV/cl/test/test --power run
head -12 $OUT/power/power_report.csv
grep "/chip/cluster/l1/bank" $OUT/power/power_report.csv | head -4
```

**Kết quả** (chạy `hello` bản cluster): tổng 83.28 µW, gồm 83.20 µW rò và
0.078 µW động. **Toàn bộ đến từ 16 bank L1**, mỗi bank khoảng 6.25%.
`/chip/soc/power_trace` bằng 0: SoC, L2, DMA, interconnect và core đều không có
model công suất.

Dùng được để so sánh tương đối giữa các cách truy cập L1; không dùng làm số tuyệt đối.

**File:** `step2/power.csv`.

---

## 13. Độ lệch giữa GVSoC và RTL

**Để làm gì:** Mục tiêu quan trọng nhất: biết **tin GVSoC tới đâu và khi nào buộc phải chạy RTL**. Không có mục này thì 12 mục trên chỉ là số của một model, chưa biết đúng sai.

**Đo gì:** số của GVSoC sai bao nhiêu. Cách làm: build **một ELF** bằng
`pulp-runtime` rồi chạy trên cả hai.

```bash
# RTL (Terminal B), ~11 phút
pgrep -x lmgrd || ~/questasim/linux_x86_64/lmgrd -c ~/questasim/LICENSE.dat \
                    -l ~/questasim/license_server.log
APP_DIR=$REPO/sw/gvsoc/ubench_rt SIM_TIMEOUT="200 ms" WALL_TIMEOUT=7200 \
    sw/full_system/run_sim.sh all run > $OUT/ubench_rt_rtl.log 2>&1

# So sánh (Terminal A)
sw/gvsoc/analyze/compare_ubench.py $OUT/ubench_rt.log $OUT/ubench_rt_rtl.log
```

**Kết quả** (29 phép đo, cột GVSoC/RTL):

| Nhóm | Tỉ lệ | Nhận xét |
|---|---|---|
| Code một core trên cluster | 1.00 | Khớp |
| Latency L2 từ cluster | 1.00 | 17.6 so với 17.6 cycle mỗi load |
| 8 core cùng đọc L2 | 0.96 | GVSoC lạc quan 4% |
| 8 core khác bank L1 | 0.87 | |
| 8 core cùng bank L1 | **0.75** | GVSoC thiếu xung đột bank |
| DMA | 0.73–0.92 | Lệch nhất ở gói nhỏ |
| Barrier | 0.91 | |
| Vòng lặp trên FC | **1.83** | GVSoC **chậm hơn** RTL |

RTL chạy `PASS (exit 0)`. Cùng ELF, sha256 `49bd9044…`.

**File:** `step4/compare.md`, `step4/compare_all_cores.md`, `step4/rtl.log`.

---

## Tổng hợp: các hằng số đã đo được của kiến trúc

| Thông số | Giá trị (GVSoC) | RTL |
|---|---|---|
| Phạt nhánh rẽ | 2 cycle | 2 cycle |
| Phạt load-use | 1 cycle | 1 cycle |
| Latency load L1 từ cluster | 3.5 cycle | 3.6 cycle |
| Latency thêm khi cluster đọc L2 | +14.1 cycle | +15.0 cycle |
| Throughput DMA | 8.0 B/cycle | 7.5 B/cycle |
| Chi phí cố định mỗi lệnh DMA | ~51 cycle | ~89 cycle |
| Chi phí một barrier 8 core | 9.8 cycle | chưa đo cùng cách; 100 vòng barrier chậm hơn 9% |
| Chi phí fork | ~72 cycle | chưa đo |
| Dung lượng I-cache dùng chung | 4 KiB | 4 KiB |
| Xung đột bank L1 | **không có** | ~1 cycle mỗi load |
