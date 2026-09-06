# Bước 0 — chạy test cluster có sẵn (2026-09-06)

Mục đích: xác định cluster có boot và chạy được không, TRƯỚC khi viết
`sw/full_system/` theo `doc/dungpc/plan_demo.md`.

| Bài test | Kết quả | Bằng chứng |
|---|---|---|
| `parallel_bare_tests/multicore` | FAIL (status `0x00000025`) | 8 core in ra `CL0_PE0`..`CL0_PE7`; PE1-PE7 `SUMMARY: SUCCESS`, PE0 `FAIL` |
| `mchan_tests/testMCHAN_TCDM2TCDM_tx_rx` | **PASS** (status `0x00000000`) | 128/256/512/1024/2048/4096 giao dịch TX+RX đồng thời đều OK |

## Kết luận

**Cluster hoạt động.** Bằng chứng quyết định là dải `[STDOUT-CL0_PE0]` đến
`[STDOUT-CL0_PE7]` — bài `hello` trước đó chỉ có `CL31` (chính là FC).

Cái được chứng minh:

- PMU, cluster clock/reset, AXI SoC->Cluster (khởi chạy được cluster)
- 8 core cùng chạy, event unit và barrier đủ để đồng bộ và in ra
- MCHAN DMA và AXI hai chiều, ổn định qua mọi kích thước truyền

## Vì sao `multicore` FAIL mà không phải lỗi cluster

`multicore/Makefile` khai báo `nbPe = 4` và `stackSize = 10000`. Cả hai là biến
của SDK cũ và **pulp-runtime bỏ qua hoàn toàn** (không xuất hiện ở đâu trong
`pulp-runtime/rules/`). Runtime hardcode `ARCHI_CLUSTER_NB_PE 8`
(`archi/chips/pulp/properties.h:91`) và `CLUSTER_STACK_SIZE 0x800` = 2 KB
(`pulp-runtime/include/pulp.h:21`).

Bài sudokusolver đệ quy, viết cho stack ~10 KB, chạy với 2 KB nên tràn sang
vùng L1 kề bên. Log cho thấy đúng điều đó: 4 hàng đầu của lời giải đúng, từ
hàng 5 trở đi lẫn các giá trị `268435852`+ = `0x1000_000C`+, tức địa chỉ TCDM
rò vào mảng kết quả. PE0 chạy solver nên hỏng; PE1-PE7 làm việc nhẹ hơn nên
`SUCCESS`. Việc `mchan` pass sạch củng cố cách giải thích này.

## Hệ quả cho plan_demo.md

Phase nào dùng đệ quy hoặc mảng cục bộ lớn phải tự đặt
`-DCLUSTER_STACK_SIZE=...` trong `PULP_CFLAGS`; không tin `stackSize` của Makefile.

## Môi trường

Xem `04_environment_used.sh`. Lưu ý Phụ lục B của
`nhat-ky-mo-phong-pulp-questasim.md` thiếu bước `source pulp-runtime/configs/pulp.sh`,
mà thiếu nó thì `rules/pulp.mk` dùng `-include` sẽ im lặng không nạp target nào
và make báo `No rule to make target 'clean'`.
