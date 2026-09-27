# Ma trận coverage GVSoC trên PULP

## Coverage chức năng

| Khối/chức năng | Test/ELF | Kết quả | Timing/fidelity | Giới hạn và bằng chứng |
|---|---|---|---|---|
| FC, L2, stdout | SDK `hello_fc`; `full_system` phase 0–2 | `PASS` | `PARTIAL` | Load-use/L2 khớp; vòng ALU FC GVSoC/RTL = 1,83 |
| Cluster 8 PE | `hello_cl`, `cluster/call`, `cluster/fork`; phase 3–4 | `PASS` | Một core khớp tốt | Model cấu hình thêm PE8 nhưng workload chỉ dùng 8 PE |
| Event unit/barrier | `cluster/fork`; `barrier_8core` | `PASS` | `PARTIAL` | GVSoC 2.596 vs RTL 2.864 cycle, tỷ lệ 0,91 |
| L1 TCDM | `cl_chase_l1`, same/diff bank; phase 5 | `PARTIAL` | Không tin contention | Same bank: 778 vs 1.032 cycle; GVSoC `tcdm_cont=0`, RTL = 127 |
| L2 | `cl_chase_l2`, `l2_8core` | `PASS` | Tốt cho một core | Một core 4.504 vs 4.516; 8 core GVSoC nhanh hơn 4% |
| Shared I-cache | `icache_sweep` 256 B–6 KiB | `PASS` | `PARTIAL` | Điểm gãy 4 KiB khớp; GVSoC phạt L0/refill cao hơn RTL |
| MCHAN DMA | SDK `dma/1d`; phase 6; size sweep | `PASS` | `PARTIAL` | GVSoC/RTL 0,73–0,92; lệch nhất ở gói nhỏ |
| UART | SDK `uart/loopback` | `PASS` | Chưa hiệu chuẩn timing | Loopback kết thúc exit 0 |
| HyperRAM | SDK `ram/simple` | `PASS` | Chưa hiệu chuẩn timing | Read/write cơ bản hoạt động |
| HyperFlash read/program | SDK `flash/simple` | `PASS` | Chưa hiệu chuẩn timing | Luồng đơn giản hoạt động |
| HyperFlash erase/reprogram | SDK `flash/with_ram` | `PARTIAL` | Không áp dụng | Model báo không thể program bit 0 thành 1 tại `0x40881` |
| Filesystem | SDK `fs/read`, FC và cluster | `PASS` | Chưa hiệu chuẩn timing | Hai biến thể đều exit 0 |
| Perf counter cơ bản | SDK perf tests; `ubench_rt` | `PARTIAL` | Một số counter khớp | Instr/load/store/branch/LD_STALL dùng được |
| Perf counter mở rộng | `ubench_rt` | `UNSUPPORTED` | Không dùng | `LD_EXT*`, `ST_EXT*`, `TCDM_CONT`, `JR_STALL` luôn 0 trên GVSoC |
| Shared FPU | Không có test độc lập trong SDK hiện tại | `NOT TESTED` | Không dùng | Chưa có model shared-FPU tương đương được chứng minh |
| HWPE datamover | `full_system` phase 7 | `UNSUPPORTED` | Không dùng | Bản đầy đủ timeout sau phase 6; bản skip chạy SUCCESS |
| GPIO/safe-domain padmux | `full_system` phase 8 | `PARTIAL` | Không đo timing pin | Chỉ chứng minh đường truy cập thanh ghi/model, không chứng minh pad RTL |
| Power | `hello_cl --power` | `PARTIAL` | Chỉ tương đối | Non-zero chỉ ở L1; core/L2/DMA/interconnect bằng 0 |

## `full_system` theo phase

| Phase | Nội dung | Kết quả GVSoC |
|---:|---|---|
| 0 | FC, L2, stdout | `PASS` |
| 1 | FC core, L2, SoC interconnect | `PASS` |
| 2 | APB timer, FC clock | `PASS` |
| 3 | PMU, cluster clock/reset, AXI | `PASS` |
| 4 | 8 core, event unit, barrier | `PASS` |
| 5 | TCDM và interconnect | `PASS` |
| 6 | MCHAN DMA, AXI hai chiều | `PASS` |
| 7 | HWPE datamover | `UNSUPPORTED`; timeout ở bản đầy đủ, `SKIP` ở bản có cờ |
| 8 | GPIO, safe-domain padmux | `PASS` ở mức phần mềm/model |

## Mức tin cậy sau khi đối chiếu RTL

| Mức | Đại lượng |
|---|---|
| Khớp khoảng ±2% | Số lệnh chính, load-use, code một core trên cluster khi vừa L0, latency load L2 từ cluster |
| Dùng so sánh tương đối | DMA, barrier, code đa core, I-cache sweep, power L1 |
| Sai hướng hoặc lệch lớn | FC tight loop; refill L0 của code 1–4 KiB |
| Không dùng | TCDM contention và sáu counter luôn 0; shared FPU; power ngoài L1; HWPE |
