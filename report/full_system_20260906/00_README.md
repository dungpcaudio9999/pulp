# `sw/full_system` — chuỗi phát triển và kết quả `2026-09-06`

Chương trình 9 phase theo [plan_demo.md](../../doc/dungpc/plan_demo.md).
Nguồn: [sw/full_system/](../../sw/full_system/).

## Kết quả cuối

| Lượt | Lệnh | Kết quả |
|---|---|---|
| Sạch | `./run_sim.sh` | **SUCCESS**, 9/9 phase OK, status `0x00000000`, log có đủ `CL0_PE0`..`CL0_PE7` |
| Tiêm lỗi | `./run_sim.sh clean all run INJECT_FAULT=1` | **FAIL** đúng như mong đợi, status `0x00000001` |

## Chuỗi chẩn đoán phase 7 (HWPE datamover)

| Log | Thay đổi | Kết quả |
|---|---|---|
| `01` | cấu hình ban đầu | cluster **không chạy**: stack 8 KB × 8 vượt L1 64 KB, `pi_l1_malloc` hỏng và `cluster_start` return im lặng |
| `02` | stack 4 KB + sentinel `demo_cl_ran` | phase 7 FAIL từ word 3 |
| `03` | độ dài theo beat + chờ hai nhịp + chẩn đoán | 40/64 word sai, lộ chu kỳ 8 |
| `04` | dump từng word | mẫu rõ: 3 đúng / 5 sai, lặp theo chu kỳ 8 |
| `05` | `BW = 36` (suy từ `NB_HWPE_PORTS = 9`) | chu kỳ dịch sang 9, **vẫn 3 word đúng** |
| `06` | `BW = 12` (đo được) | **PASS toàn bộ 9 phase** |
| `08` | tiêm lỗi core 3 | FAIL đúng, status khác 0 |

### Cách xác định băng thông thật

Bước `05` không sửa được lỗi nhưng là bước quyết định về phương pháp: nó **tách bạch hai
đại lượng**. Đổi `D0_STRIDE` từ 32 sang 36 byte làm chu kỳ word đúng dịch từ 8 sang 9,
trong khi số word đúng mỗi chu kỳ vẫn luôn là 3. Vậy stride do phần mềm đặt, còn payload
mỗi nhịp là hằng số phần cứng 3 word = 12 byte = 96 bit.

Đáng chú ý: suy luận từ RTL cho ra số **sai**. `hwpe_subsystem` nhận
`N_MASTER_PORT = NB_HWPE_PORTS = 9` (`pulp_cluster.sv:34,1037`) và `datamover_top` lấy
`BW = N_MASTER_PORT*32` bit = 36 byte — nhưng thực đo là 12 byte. Hằng số
`DATAMOVER_BW = 256/8 = 32` trong `test_datamover.c` của dependency cũng sai với cấu
hình này. Ở đây đo thực nghiệm đáng tin hơn đọc tham số.

## Hai lỗi im lặng đã bị bắt trong quá trình

1. **Cluster không chạy mà vẫn báo SUCCESS** (`01`). `cluster_start()` return im lặng khi
   cấp phát stack L1 thất bại, `cluster_wait()` trả về 0 — không phân biệt được với thành
   công. Đã thêm sentinel `demo_cl_ran` ở L2 để phase 3 kiểm chứng.
2. **Lỗi ở core khác 0 bị nuốt mất.** Runtime chỉ giữ giá trị trả về của core 0. Phép thử
   ngược (`08`) chứng minh cơ chế `cl_report()` qua mutex xử lý đúng: core **2** phát hiện
   lỗi và nó tới được exit status.

Nếu làm theo cách hiển nhiên — mỗi core `return` số lỗi của mình, phase 3 tin giá trị trả
về — thì cả hai đều lọt lưới và bài test báo pass.
