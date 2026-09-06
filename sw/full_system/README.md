# `full_system` — demo đánh thức mọi khối của PULP

Một chương trình C duy nhất, chạy hai lần: lần đầu trên FC (cluster id 31),
lần sau trên cả 8 core cluster thông qua `bench_cluster_forward()`.

## Chạy

```bash
./run_sim.sh                # clean all run
./run_sim.sh all            # chỉ build
```

`run_sim.sh` tự dựng toàn bộ môi trường vì `source setup/vsim.sh` là **chưa đủ**.
Xem [nhật ký QuestaSim](../../doc/dungpc/nhat-ky-mo-phong-pulp-questasim.md).

Bản FPGA (dùng sau khi có bitstream):

```bash
make clean all io=uart PLATFORM=fpga
```

## Các phase

| # | Khối | Chạy ở đâu |
|---|---|---|
| 0 | FC, L2, đường stdout | FC |
| 1 | FC core, L2, SoC interconnect (checksum) | FC |
| 2 | APB timer, FC clock | FC |
| 3 | PMU, cluster clk/rst, AXI SoC→CL | FC |
| 4 | 8 core cluster, event unit, barrier | tất cả 8 core |
| 5 | TCDM và interconnect (ghi xen kẽ, đọc chéo) | tất cả 8 core |
| 6 | MCHAN DMA, AXI hai chiều (L2→L1→L2) | core 0 |
| 7 | HWPE datamover | core 0 |
| 8 | GPIO, safe domain padmux | FC |

## Sáu quyết định thiết kế không hiển nhiên

**1. Gom lỗi qua `cl_report()`, không phải `return`.** Runtime chỉ giữ giá trị trả về
của core 0 (`pulp-runtime/kernel/cluster.c`, `cluster_entry_stub`). Nếu mỗi core chỉ
`return` số lỗi của mình thì lỗi do core 1–7 phát hiện **bị vứt đi trong im lặng** và
bài test vẫn báo pass. Vì vậy mọi core cộng vào `demo_cl_fails` dưới mutex của event
unit, và chỉ core 0 trả giá trị đó về.

**2. Phase 3 kiểm tra sentinel, không tin giá trị trả về.** `cluster_start()` gọi
`pi_l1_malloc(cid, 8 * CLUSTER_STACK_SIZE)` để cấp stack; nếu thất bại nó **`return`
im lặng** *trước* dòng `cluster_running = 1` (`kernel/cluster.c:83-87`). Khi đó
`cluster_wait()` trả về `cluster_retval` = 0 — **không phân biệt được với một lần chạy
thành công**. Đây không phải giả thuyết: lần chạy đầu tiên của chương trình này báo
`SUMMARY: SUCCESS` với status `0x00000000` trong khi cluster chưa hề khởi động, vì
`CLUSTER_STACK_SIZE=0x2000` khiến 8 × 8 KB = đúng 64 KB, vượt dung lượng L1. Nay cluster
core 0 đặt `demo_cl_ran = DEMO_CL_RAN_MAGIC` (biến ở L2) và FC kiểm tra nó.

**3. Tên biến có tiền tố `demo_`.** `L2_DATA` và `L1_DATA` trong pulp-runtime là **macro
đặt section** (`data/data.h:39,42`), không phải tên biến. Đặt trùng tên sẽ làm hỏng mọi
biểu thức chứa nó, với thông báo lỗi hoàn toàn lạc hướng kiểu "too few arguments".
Ta dùng chính hai macro đó làm attribute để đặt dữ liệu vào đúng vùng nhớ.

**4. Phase 8 truy cập thanh ghi GPIO trực tiếp.** Toàn bộ HAL GPIO của pulp-runtime nằm
trong `#if 0` (`hal/gpio/gpio_v3.h:35-99`) nên không link được. Bài regression
`peripherals/spim_flash` cũng tự viết helper riêng vì lý do này.

**5. Phase 7 dùng `BW = 12` byte, đo bằng thực nghiệm.** Hằng số
`DATAMOVER_BW = 256/8 = 32` trong `test_datamover.c` của dependency là của **một cấu
hình khác** và sai ở đây. Cách xác định con số đúng mà không cần đọc thêm RTL: đặt
`D0_STRIDE` khác nhau rồi nhìn mẫu word bị bỏ sót.

| `D0_STRIDE` đặt | Word đúng | Chu kỳ |
|---|---|---|
| 32 byte (8 word) | 0,1,2 / 8,9,10 / … | 8 |
| 36 byte (9 word) | 0,1,2 / 9,10,11 / … | 9 |

Chu kỳ đi theo stride, còn số word đúng mỗi chu kỳ luôn là 3. Vậy **stride do phần mềm
đặt, payload mỗi nhịp cố định 3 word = 12 byte = 96 bit do phần cứng**. Đặt `BW = 12`
thì phase 7 pass. Log của cả chuỗi chẩn đoán ở
[report/full_system_20260906/](../../report/full_system_20260906/).

**6. Phase 7 poll `STATUS` theo hai nhịp, không dùng `DATAMOVER_BARRIER()`.** Macro barrier của
`hal_datamover.h` chờ event `DATAMOVER_EVT0 = 12`, nhưng `cluster_core_init()` chỉ
unmask `DISPATCH | MUTEX | HW_BAR` — event 12 sẽ không bao giờ tới và chương trình treo.
Trước đó phải gọi `DATAMOVER_CG_ENABLE()`: HWPE mặc định bị clock-gate, thiếu bước này
vòng poll treo tới hết timeout và triệu chứng trông y hệt như register map sai.

## Hai cạm bẫy môi trường

**Ngân sách L1 rất chật.** L1 chỉ có `0x0000fffc` ≈ 64 KB (`link.ld:7`) và stack của cả
8 core được cấp từ đó. Hai hướng hỏng ngược nhau:

- **Quá nhỏ:** mặc định `CLUSTER_STACK_SIZE` là 0x800 = 2 KB
  (`pulp-runtime/include/pulp.h:21`). Tràn stack **không gây crash**, nó âm thầm làm
  hỏng dữ liệu ở L1 kề bên — đúng như `parallel_bare_tests/multicore` cho thấy.
  Biến `stackSize` trong Makefile của các test cũ là của SDK cũ và bị **bỏ qua hoàn toàn**.
- **Quá lớn:** 8 × 8 KB = 64 KB làm `pi_l1_malloc` thất bại, và cluster **không chạy
  trong im lặng** (xem quyết định 2 ở trên).

Makefile ở đây đặt `-DCLUSTER_STACK_SIZE=0x1000` → 8 × 4 KB = 32 KB, còn dư chỗ cho
~2 KB mảng tĩnh và phần heap.

**Phase 7 cần `-gUSE_HWPE_CL=1`.** `rtl/tb/tb_pulp.sv:48` đặt `USE_HWPE_CL = 0` nên mặc
định HWPE không được instantiate. `run_sim.sh` truyền cờ này qua **biến môi trường**
`vsim_flags`, không phải dòng lệnh make — biến trên dòng lệnh make sẽ ghi đè cả các dòng
`+=` phía sau và làm mất `-gLOAD_L2=JTAG`, khiến chương trình không được nạp.

## Tiêu chí pass

1. Đủ 9 dòng `[PHASE n] ... OK`
2. Log có `[STDOUT-CL0_PE0]` đến `CL0_PE7` — bằng chứng cluster thật sự sống
3. `==== FULL-SYSTEM SUMMARY: SUCCESS`
4. `[TB] ... Received status core: 0x00000000`

## Phép thử ngược

Bật `-DDEMO_INJECT_FAULT_CORE3` để phá hỏng có chủ đích dữ liệu của **core 3**:

```bash
./run_sim.sh clean all run INJECT_FAULT=1
```

Dùng biến `INJECT_FAULT`, **đừng ghi đè `PULP_CFLAGS`** trên dòng lệnh: làm vậy sẽ xoá
luôn các define mà rule của runtime thêm bằng `+=` và build hỏng với lỗi lạc hướng
`archi/chips/PULP_CHIP_STR/pulp.h: No such file`.

Bài test phải FAIL với status khác 0. Đây là phép thử **quan trọng nhất** trong bộ này:
nó chứng minh lỗi do một core **khác core 0** phát hiện vẫn tới được exit status. Nếu bỏ
`cl_report()` và để mỗi core `return` số lỗi của mình, phép thử này sẽ PASS sai — lỗi bị
nuốt mất hoàn toàn trong im lặng.

Bốn lỗi `vsim-191` và warning `jtag_tick` là nhiễu đã biết của Questa 10.7c, không phải
hồi quy của chương trình này.
