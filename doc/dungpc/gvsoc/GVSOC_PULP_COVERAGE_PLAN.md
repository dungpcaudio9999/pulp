# Kế hoạch đánh giá GVSoC trên PULP

## 1. Mục tiêu

Xác định target GVSoC `pulp-open` chạy và quan sát được những chức năng nào của
checkout PULP hiện tại, mức tương ứng giữa model GVSoC và RTL, và giới hạn cần
ghi rõ trước khi dùng kết quả để phân tích hiệu năng.

GVSoC không mô phỏng trực tiếp các file SystemVerilog trong `rtl/pulp/`. Nó chạy
ELF trên model C++/Python riêng. Vì vậy công việc gồm hai nhánh tách biệt:

1. **Coverage chức năng:** khối/phần mềm nào chạy được trên `pulp-open`.
2. **Fidelity:** kết quả chức năng và timing có tương ứng với RTL hay không.

Phạm vi trước mắt chỉ là target `pulp-open` và phần mềm của repo này. Các target
`rv64`, Snitch, vector, many-core và những target chip khác không thuộc phạm vi.

## 2. Đầu ra bắt buộc

- Phiên bản RTL, GVSoC, SDK/runtime và toolchain dùng để đo.
- Ma trận ánh xạ cấu hình RTL với target `pulp-open`.
- Kết quả smoke test theo từng khối: `PASS`, `PARTIAL`, `UNSUPPORTED`, `FAIL`,
  hoặc `NOT TESTED`.
- Danh mục trace, VCD, performance counter và power model thực sự có dữ liệu.
- Kết quả `full_system` theo phase, gồm điểm dừng và nguyên nhân.
- So sánh cùng một ELF giữa GVSoC và RTL cho các phép đo đại diện.
- Bảng coverage cuối cùng, mỗi kết luận có đường dẫn tới log hoặc source.

## 3. Quy tắc phân loại

| Nhãn | Ý nghĩa |
|---|---|
| `PASS` | Chức năng chạy đúng, kết thúc bình thường và có bằng chứng đầu ra |
| `PARTIAL` | Chạy được nhưng thiếu thao tác, counter hoặc timing đáng tin cậy |
| `UNSUPPORTED` | Target không có model cho chức năng tương ứng |
| `FAIL` | Chức năng được kỳ vọng hỗ trợ nhưng test sai hoặc simulator lỗi |
| `NOT TESTED` | Chưa có ELF/test đủ để đưa ra kết luận |

Một test chạy thành công chỉ chứng minh coverage chức năng. Không được suy ra
timing đúng nếu chưa đối chiếu với RTL bằng cùng một ELF.

## 4. Các bước thực hiện

### Bước 0 — Khóa baseline và cấu hình

Ghi lại:

- commit của repo PULP, GVSoC và PULP SDK;
- phiên bản toolchain, Python và simulator RTL;
- target `pulp-open` và các tham số cấu hình hiệu lực;
- số PE, dung lượng/bank L1 và L2, I-cache, DMA, peripheral, FPU và HWPE của hai
  phía RTL/GVSoC.

Đầu ra: `00_baseline.md`, `versions.txt` và `configuration_matrix.md`.

### Bước 1 — Smoke test theo khối

Chạy test nhỏ theo thứ tự:

```text
FC boot -> cluster start/fork -> L1/L2 -> cluster DMA
        -> Flash/RAM/filesystem -> UART -> performance counter
```

Lệnh chính:

```bash
source sw/gvsoc/env.sh
sw/gvsoc/step1_sdk_tests.sh <report>/step1
```

Không chạy `cluster/fork_power`, vì test này ép ghi toàn bộ VCD và từng tạo file
22 GB. Mỗi test phải có exit code, thời gian chạy, log và nhãn kết quả.

### Bước 2 — Kiểm kê khả năng quan sát

Chạy một ELF nhỏ có cả FC và cluster với:

- toàn bộ component trace;
- toàn bộ VCD event;
- power report;
- target properties và sơ đồ component;
- instruction trace để profile theo lệnh và theo hàm.

Lệnh chính:

```bash
sw/gvsoc/step2_inventory.sh <report>/step2 <elf>
```

Đầu ra phải phân biệt rõ "khối chạy được" và "đại lượng đo được". Counter tồn
tại nhưng luôn bằng 0 phải được đánh dấu không dùng được.

### Bước 3 — Chạy phần mềm tích hợp của repo

Build và chạy `sw/full_system`. Mỗi phase cần marker đầu/cuối để xác định phase
nào PASS, treo, hoặc không được model hỗ trợ.

```bash
# Môi trường pulp-runtime
source pulp-runtime/configs/pulp.sh
make -C sw/full_system clean all SKIP_HWPE=1

# Môi trường GVSoC
source sw/gvsoc/env.sh
gvsoc --target=pulp-open --binary sw/full_system/build/test/test run
```

Chạy bản có HWPE khi an toàn để xác nhận điểm dừng; dùng timeout và lưu log. Không
được coi bản `SKIP_HWPE=1` là bằng chứng HWPE hoạt động.

### Bước 4 — Microbenchmark và kiểm tra độ hợp lý

Chạy các kernel có kết quả dự đoán được:

- ALU và branch penalty;
- load-use stall;
- L1/L2 latency;
- truy cập cùng/khác bank TCDM;
- DMA theo kích thước;
- fork/barrier theo số core;
- code-size sweep cho I-cache.

Chạy lặp lại ít nhất hai lần trên GVSoC để kiểm tra tính tất định. Tách `printf`
ra ngoài vùng đo.

### Bước 5 — Đối chiếu cùng ELF với RTL

Build `sw/gvsoc/ubench_rt` và `sw/gvsoc/icache_sweep` bằng `pulp-runtime`, sau đó
chạy chính các ELF đó trên `pulp-open` và `tb_pulp`/Questa.

So sánh số lệnh, cycle, stall, latency L1/L2, DMA, barrier, TCDM contention và
I-cache. Phân loại từng đại lượng:

- khớp RTL;
- lệch có hệ thống nhưng dùng so sánh tương đối được;
- sai hướng hoặc thiếu model;
- không dùng được.

### Bước 6 — Lập ma trận coverage cuối cùng

Mỗi hàng phải có:

| Khối/chức năng | RTL | GVSoC model | Test/ELF | Chức năng | Timing | Giới hạn | Bằng chứng |
|---|---|---|---|---|---|---|---|

Các khối tối thiểu: FC, cluster PE, event unit, L1/TCDM, L2, I-cache, cluster DMA,
UART, Flash, RAM, filesystem, shared FPU, HWPE và power model.

## 5. Thứ tự ưu tiên

1. Hoàn thành configuration matrix và smoke-test coverage.
2. Chạy `full_system` theo phase.
3. Kiểm kê các cơ chế đo thực sự có dữ liệu.
4. Dùng một tập microbenchmark nhỏ để hiệu chuẩn timing.
5. Chỉ viết hoặc sửa model GVSoC sau khi coverage table chứng minh model đó là
   khoảng trống quan trọng.

## 6. Tiêu chí hoàn thành

Kế hoạch hoàn thành khi mọi khối trong phạm vi có một nhãn coverage, mọi nhãn có
bằng chứng tái tạo được, và tài liệu chỉ rõ trường hợp nào có thể dùng GVSoC,
trường hợp nào phải quay lại RTL simulation, synthesis, STA hoặc công cụ CDC.

## 7. Trạng thái thực hiện ngày 2026-09-27

- [x] Bước 0 — khóa baseline và lập configuration matrix.
- [x] Bước 1 — chạy 13 smoke test SDK: 12 `PASS`, Flash erase/program
  `PARTIAL`.
- [x] Bước 2 — kiểm kê 1.475 trace path, 2.555 VCD signal, 262 power row;
  tạo profile theo lệnh và theo hàm.
- [x] Bước 3 — `full_system` phase 0–6 và 8 `PASS`; phase 7
  `UNSUPPORTED` và timeout do thiếu model HWPE datamover.
- [x] Bước 4 — chạy microbenchmark GVSoC hai lần; toàn bộ dòng `CSV` giống nhau.
- [x] Bước 5 — chạy cùng ELF `ubench_rt` và `icache_sweep` trên GVSoC và RTL
  Questa; cả hai lượt RTL `PASS`.
- [x] Bước 6 — lập ma trận coverage cuối cùng.

Kết quả của lần chạy này nằm tại
[`report/gvsoc_20260927_coverage/`](../../../report/gvsoc_20260927_coverage/README.md).
