# Ma trận cấu hình RTL và GVSoC `pulp-open`

| Hạng mục | RTL checkout | GVSoC `pulp-open` | Hệ quả khi dùng |
|---|---|---|---|
| Cluster PE | 8 (`pulp_soc_defines.sv`) | Cấu hình có 9 core; PE8 không chạy workload | Chỉ so core 0–7 |
| L1 TCDM | 64 KiB, 16 bank, có arbitration | 64 KiB, 16 bank; model không tính bank contention | Không dùng GVSoC để đo tranh chấp cùng bank |
| L2 | 512 KiB | 2 vùng private 32 KiB và vùng shared lớn hơn RTL | Giữ ELF/dữ liệu trong 512 KiB khi so sánh |
| I-cache cluster | Shared 4 KiB; đường private/L0 512 B | Shared 2 bank, tổng 4 KiB; L0 512 B | Điểm gãy dung lượng khớp, refill penalty lệch |
| FC fetch | RTL test không có phạt vòng lặp tương ứng | `fc_fetch_ico` có latency cố định | Vòng lặp FC trên GVSoC bi quan tới 1,83 lần |
| Cluster interconnect | Có arbitration/backpressure RTL | Router transaction-level với latency cấu hình | Tải đa core phải đối chiếu RTL |
| Cluster DMA | MCHAN trong RTL | Có model MCHAN | Chạy đúng chức năng; timing nhanh hơn RTL 8–27% |
| Shared FPU | Có cấu hình shared FP trong cluster | Không có model tương đương đã kiểm chứng | `NOT TESTED`; không dùng `APU_CONT` |
| HWPE | Datamover, `NB_HWPE_PORTS=4` tại top | Không có model datamover | `full_system` phase 7 timeout |
| Boot | JTAG load trong `tb_pulp` | Nạp ELF trực tiếp | Không so thời gian boot |
| Power | RTL chưa được dùng làm chuẩn power | Non-zero chỉ ở 16 bank L1 | Chỉ dùng tương đối cho L1 |

Nguồn RTL chính: `rtl/includes/pulp_soc_defines.sv`, `rtl/pulp/pulp.sv` và
`rtl/pulp/cluster_domain.sv`. Cấu hình GVSoC thực tế được lưu trong các file
`gvsoc_config.json` của từng work directory trong report này.

Target chỉ công bố bốn property lúc chạy: bật RedMulE, bật FIC, đường dẫn binary
và UART checker loopback. Những thay đổi cấu hình khác cần target generator/JSON
riêng hoặc sửa model.
