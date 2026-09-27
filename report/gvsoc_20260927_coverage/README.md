# Kết quả đánh giá coverage GVSoC — 2026-09-27

Phiên này thực hiện kế hoạch tại
[`doc/dungpc/gvsoc/GVSOC_PULP_COVERAGE_PLAN.md`](../../doc/dungpc/gvsoc/GVSOC_PULP_COVERAGE_PLAN.md)
trên target `pulp-open`.

## Kết quả chính

- 12/13 smoke test SDK `PASS`; `flash_with_ram` là `PARTIAL` do model không hỗ
  trợ chuỗi erase/reprogram cần thiết.
- Inventory thu được 1.475 trace path, 2.555 VCD signal và 262 power row.
- `full_system` phase 0–6 và 8 `PASS`; phase 7 HWPE `UNSUPPORTED`.
- Hai lượt microbenchmark PMSIS cho các dòng `CSV` giống hệt nhau.
- `ubench_rt` chạy cùng ELF trên GVSoC và RTL; RTL `PASS` sau 11 phút 39 giây.
- `icache_sweep` chạy trên GVSoC 4 KiB, GVSoC 8 KiB và RTL; RTL `PASS` sau
  7 phút 07 giây.

## Các số đối chiếu tiêu biểu

| Phép đo | GVSoC | RTL | GVSoC/RTL |
|---|---:|---:|---:|
| FC ALU 1.000 vòng | 22.003 | 12.007 | 1,83 |
| Cluster ALU | 12.039 | 12.092 | 1,00 |
| Cluster pointer chase L2 | 4.504 | 4.516 | 1,00 |
| TCDM cùng bank, 8 core | 778 | 1.032 | 0,75 |
| 8 core cùng đọc L2 | 2.570 | 2.686 | 0,96 |
| DMA L2->L1, 8 KiB | 1.071 | 1.177 | 0,91 |
| Barrier 8 core, 100 vòng | 2.596 | 2.864 | 0,91 |

I-cache, core 0 khi 8 core chạy:

| Code | GVSoC 4 KiB | GVSoC 8 KiB | RTL 4 KiB |
|---|---:|---:|---:|
| 256 B | 2.658 | 2.658 | 2.673 |
| 1 KiB | 12.498 | 12.498 | 10.389 |
| 2 KiB | 25.710 | 25.678 | 20.761 |
| 4 KiB | 53.870 | 51.438 | 44.610 |
| 6 KiB | 153.662 | 77.342 | 145.899 |

## Chỉ mục bằng chứng

| Đường dẫn | Nội dung |
|---|---|
| `versions.txt`, `00_baseline.md` | Phiên bản và phạm vi |
| `configuration_matrix.md` | Ánh xạ cấu hình RTL/GVSoC |
| `coverage_matrix.md` | Coverage cuối cùng theo khối |
| `step1/summary.txt` | Smoke-test PASS/FAIL và thời gian |
| `step2/` | Trace/VCD/power inventory và profile |
| `full_system_skip/run.log` | Phase 0–6, 8 PASS; phase 7 SKIP |
| `full_system_hwpe/run.log` | Bản đầy đủ dừng sau phase 6 và timeout |
| `step4_microbench/run{1,2}.log` | Hai lượt deterministic microbenchmark |
| `step5_compare/gvsoc.log` | `ubench_rt` trên GVSoC |
| `step5_compare/rtl.log` | Cùng ELF trên RTL Questa |
| `step5_compare/compare.md` | Bảng 29 phép đo GVSoC/RTL |
| `step5_compare/icache_*.log` | Sweep I-cache trên hai target và RTL |

## Kết luận sử dụng

Dùng GVSoC để kiểm tra chức năng phần mềm, profile và so sánh tương đối các
phương án. Chạy lại trên RTL khi số cycle tuyệt đối quan trọng, khi có nhiều core
tranh chấp L1, khi workload chạy nhiều trên FC, hoặc khi liên quan HWPE/shared
FPU/pad timing. GVSoC không thay thế RTL simulation cho protocol, CDC và reset,
không thay thế synthesis/STA cho area và timing sign-off.
