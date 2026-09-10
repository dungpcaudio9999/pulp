# `full_system.c` — bài test đánh thức mọi khối của PULP

Giải thích chi tiết một chương trình: nó test cái gì, hoạt động ra sao, ăn vào gì,
nhả ra gì, và đối chiếu với cái gì để kết luận đúng/sai.

| Cần gì khác | Đọc |
|---|---|
| chạy từ máy trắng | [RUNBOOK.md](RUNBOOK.md) |
| tóm tắt thiết kế và cách gọi | [sw/full_system/README.md](../../sw/full_system/README.md) |
| môi trường testbench quanh chip | [deep_dive_04_boot_debug_testbench.md](deep_dive_04_boot_debug_testbench.md) |
| log thật của các lượt chạy | [report/full_system_20260906/](../../report/full_system_20260906/) |

Nguồn: [sw/full_system/full_system.c](../../sw/full_system/full_system.c) (430 dòng).

---

## 1. Nó test cái gì

Câu hỏi mà bài test này trả lời: **mọi khối lớn trong SoC có thật sự sống và nói chuyện
được với nhau không.**

Không phải test chức năng chi tiết của từng khối — chuyện đó là việc của regression suite
upstream. Đây là *smoke test toàn hệ thống*: mỗi phase đánh thức một khối, ép nó làm một
việc có thể quan sát được, rồi đối chiếu kết quả với một giá trị biết trước.

| Phase | Khối được đánh thức | Chạy ở |
|---|---|---|
| 0 | FC, L2, đường stdout | FC |
| 1 | FC core, L2, SoC interconnect | FC |
| 2 | APB timer, FC clock | FC |
| 3 | PMU, cluster clock/reset, AXI SoC→CL | FC |
| 4 | 8 core cluster, event unit, barrier | cả 8 core |
| 5 | TCDM và interconnect cluster | cả 8 core |
| 6 | MCHAN DMA, AXI hai chiều | core 0 |
| 7 | HWPE datamover | core 0 |
| 8 | GPIO, safe domain padmux | FC |

Phủ được: hai miền xử lý (FC và cluster), ba mức bộ nhớ (L2, L1/TCDM, thanh ghi ngoại vi),
ba loại kết nối (SoC interconnect, AXI, TCDM interconnect), hai bộ máy chuyển dữ liệu
(MCHAN DMA và HWPE), cùng cơ chế đồng bộ (event unit, mutex, barrier).

Không phủ: FPU, i-cache, uDMA và các ngoại vi ngoài (SPI, I2C, I2S, camera), tín hiệu ra
chân pad thật.

---

## 2. Cách build và chạy

### Một lệnh

```bash
cd sw/full_system
./run_sim.sh
```

`run_sim.sh` tự dựng môi trường, chạy preflight, bọc watchdog rồi gọi
`make clean all run`. Nếu repo chưa build RTL bao giờ thì đi từ [RUNBOOK.md](RUNBOOK.md)
trước.

### Các dạng gọi

| Lệnh | Tác dụng | Kỳ vọng |
|---|---|---|
| `./run_sim.sh` | lượt sạch | PASS, exit 0 |
| `./run_sim.sh all` | chỉ build ELF | — |
| `./run_sim.sh clean all run INJECT_FAULT=1` | tiêm lỗi core 3 | **FAIL**, exit 1 |
| `./run_sim.sh clean all run INJECT_FAULT_DMA=1` | tiêm lỗi DMA | **FAIL**, exit 1 |
| `SIM_TIMEOUT="5 ms" ./run_sim.sh` | ép watchdog nổ | exit 124 |
| `make clean all io=uart PLATFORM=fpga` | build cho FPGA | cần bitstream |

### Ba cờ biên dịch trong [Makefile](../../sw/full_system/Makefile)

| Cờ | Giá trị | Vì sao |
|---|---|---|
| `-DCLUSTER_STACK_SIZE=0x1000` | 4 KB/core | mặc định 2 KB tràn im lặng; 8 KB làm `pi_l1_malloc` hỏng |
| `-DDEMO_INJECT_FAULT_CORE3` | qua `INJECT_FAULT=1` | phép thử ngược |
| `-DDEMO_INJECT_FAULT_DMA` | qua `INJECT_FAULT_DMA=1` | phép thử ngược |

`PULP_APP_SRCS` (không phải `PULP_APP_FC_SRCS`) là điều bắt buộc: nó khiến `main()` được
biên dịch cho **cả FC lẫn cluster**, và đó là nền tảng của toàn bộ cơ chế ở mục 3.

**Đừng ghi đè `PULP_CFLAGS` trên dòng lệnh** — làm vậy xoá mất các define mà rule của
runtime thêm bằng `+=`, và build hỏng với lỗi lạc hướng
`archi/chips/PULP_CHIP_STR/pulp.h: No such file`.

---

## 3. Hoạt động như thế nào

### Một `main()`, hai lần thực thi

Điểm lạ nhất của chương trình: `main()` chạy trên hai bộ xử lý khác nhau và tự phân biệt
mình đang ở đâu.

```c
int main(void) {
    if (get_cluster_id() != 0) {      /* FC mang cluster id 31 */
        fails += phase0_banner();
        fails += phase1_fc_l2();
        fails += phase2_timer();
        fails += phase3_cluster_poweron();   /* <-- khoi dong cluster tai day */
        fails += phase8_gpio();
        phase9_summary(fails);
        return fails;                  /* testbench doc thanh exit status */
    }
    /* Cluster: ca 8 core cung chay tiep tu day */
    ...
}
```

Phase 3 gọi `bench_cluster_forward(0)`. Hàm này bật nguồn cluster và bảo 8 core **gọi lại
chính `main()`**; lúc đó `get_cluster_id()` trả 0 nên luồng rẽ xuống nhánh dưới.

Hệ quả với người đọc log: **thứ tự không tuyến tính**. Phase 3 mở ra, phase 4–7 chạy xen
vào giữa, rồi phase 3 mới đóng lại:

```
[PHASE 3] PMU, cluster clk/rst, AXI      ...          <- mo
          core 0..7 dang chay
[PHASE 4] ... OK
[PHASE 5] ... OK
[PHASE 6] ... OK
[PHASE 7] ... OK
[PHASE 3] PMU, cluster clk/rst, AXI      ... OK       <- dong
[PHASE 8] GPIO, safe domain padmux       ... OK
```

### Bố trí bộ nhớ

`L2_DATA` và `L1_DATA` là **macro đặt section** của runtime, không phải tên biến — đó là
lý do mọi biến ở đây mang tiền tố `demo_`.

| Biến | Vùng | Kích thước | Vì sao ở đó |
|---|---|---|---|
| `demo_l2_src` | L2 | 1 KB | nguồn cho checksum và DMA |
| `demo_l2_dst` | L2 | 1 KB | đích của DMA khứ hồi |
| `demo_cl_ran` | L2 *(mặc định)* | 4 B | FC phải ghi được khi cluster còn **tắt** |
| `demo_l1_grid` | L1/TCDM | 1 KB | phase 5 cần đúng bộ nhớ chia sẻ của cluster |
| `demo_l1_scratch` | L1, **căn 32 B** | 1 KB | datamover truy cập theo nhịp 256 bit |
| `demo_cl_fails`, `demo_cl_seen` | L1 | 36 B | 8 core cùng ghi |

Số thật từ ELF đã build (`riscv32-unknown-elf-size -A`):

```
.l2_data        2048    <- demo_l2_src + demo_l2_dst
.l1cluster_g    2116    <- toan bo bien tinh o L1
.text           7740
```

Ngân sách L1: **2 116 B tĩnh + 8 × 4 096 B stack = 34 884 B** trên tổng `0xfffc` = 65 532 B
(`link.ld:7`), tức dùng khoảng **53 %**. Đây là lý do `CLUSTER_STACK_SIZE` không thể là
0x2000: 8 × 8 KB = đúng 64 KB, cộng phần tĩnh là vượt.

---

## 4. Đầu vào

### Đầu vào của chương trình C — không có

Chương trình **không đọc gì từ bên ngoài**: không tham số dòng lệnh, không file, không
stdin. Mọi dữ liệu kiểm tra được biên dịch cứng vào ELF.

Đây là chủ ý: một bài smoke test phải tự chứa để kết quả tái lập được bit-for-bit.

### Dữ liệu kiểm tra — [demo_data.c](../../sw/full_system/demo_data.c)

`demo_l2_src` là 256 word sinh theo dãy Weyl với hằng số tỉ lệ vàng:

```
demo_l2_src[i] = (i * 0x9e3779b1) mod 2^32
```

*(đã kiểm chứng lại trên chính file: khớp cả 256 word)*

Chọn dãy này vì mọi bit đều đổi giữa các phần tử liền kề — một lỗi kẹt bit, hoán vị word
hay đứt nửa bus đều làm sai lệch checksum, khác với dãy `0,1,2,3...` nơi các bit cao gần
như luôn bằng 0.

### Đầu vào của mô phỏng

| Đầu vào | Đường đi |
|---|---|
| `build/test/test` | ELF do PULP GCC sinh |
| `build/vectors/stim.txt` | ELF → `stim_utils.py` → 1 959 dòng `địa_chỉ_dữ_liệu` |
| `+ENTRY_POINT=0x1c008080` | testbench ghi vào CSR `DPC` |
| `-gUSE_HWPE_CL=1` | bắt buộc, nếu không HWPE **không được instantiate** |
| `-gLOAD_L2=JTAG` | chọn đường nạp qua JTAG |

`stim.txt` mới là thứ testbench thật sự nạp, định dạng mỗi dòng `10000020_0000...`:
địa chỉ 32 bit, gạch dưới, rồi 64 bit dữ liệu.

---

## 5. Đầu ra

### Ba kênh, ba mục đích

| Kênh | Nội dung | Ai đọc |
|---|---|---|
| **stdout mô phỏng** | các dòng `[STDOUT-CLxx_PEy]` | người, và tiêu chí pass 1–3 |
| **exit status** | một số nguyên qua thanh ghi EOC | testbench, tiêu chí pass 4 |
| **file trace** | `CORE_n.txt`, `trace_core_00_n.log` | chỉ khi cần gỡ lỗi sâu |

### Đường đi của stdout

Chip mô phỏng không có màn hình. `printf()` ghi vào một địa chỉ APB; testbench bắt bus đó
bằng `tb_fs_handler`, giải mã ra **cluster id và core id** rồi in kèm tiền tố. Nhờ vậy
log phân biệt được `CL31_PE0` (FC) với `CL0_PE0..PE7` (8 core cluster) — thông tin đó nằm
trong *địa chỉ ghi*, không phải trong dữ liệu.

### Đường đi của exit status

```
main() tra ve fails
  -> runtime ghi vao thanh ghi EOC 0x1A1040A0
  -> bit 31 = "da xong", bit 30:0 = ma tra ve
  -> tb_pulp.sv poll moi 50us cho toi khi bit 31 len
  -> exit_status = 0 neu bit 30:0 == 0, nguoc lai = 1
  -> "[TB] ... Received status core: 0x00000000"
  -> ma thoat cua vsim, roi cua run_sim.sh
```

`exit_status` khởi tạo là `-1` (`tb_pulp.sv:156`) và **chỉ** bị ghi đè khi test kết thúc
thật. Nên `-1` sau khi hết giờ nghĩa là "chưa chạy xong" — phân biệt được với cả PASS lẫn
FAIL. Watchdog dựa vào đúng điều này.

| Mã thoát `run_sim.sh` | Nghĩa |
|---|---|
| `0` | PASS |
| `1` | có phase FAIL |
| `124` | treo, watchdog nổ |

---

## 6. So sánh với cái gì

Đây là phần cốt lõi: mỗi phase đối chiếu với **một tham chiếu độc lập**, không phải với
chính nó.

| Phase | Đo được | So với | Nguồn của giá trị đúng |
|---|---|---|---|
| 0 | in ra được `cluster_id/core_id/nb_pe` | — | chỉ cần chạy tới đây |
| 1 | checksum 256 word ở L2 | `DEMO_L2_GOLDEN = 0xc1d7f5f6` | tính sẵn lúc sinh dữ liệu |
| 2 | `t1 = timer_count_get()` | `t0` đọc trước đó | đòi `t1 > t0` |
| 3 | `demo_cl_ran` | `DEMO_CL_RAN_MAGIC = 0x5A11AC7E` | sentinel cluster tự đặt |
| 4 | `demo_cl_seen[i]` | `0xC0DE0000 \| i`, đủ 8 slot | công thức |
| 5 | slot của core `(me+1)%8` | `(other << 16) \| i` | công thức, **đọc chéo** |
| 6 | `demo_l2_dst[i]` sau khứ hồi | `demo_l2_src[i]`, cả 256 word | dữ liệu gốc |
| 7 | `dst[i]` sau datamover | `src[i]`, cả 72 word | dữ liệu gốc |
| 8 | đọc lại `PADOUT` | `0x0000A5A5` vừa ghi | mẫu đã ghi |

Ba nguyên tắc đằng sau bảng này:

**Không khối nào tự chấm bài mình.** Phase 5 để mỗi core kiểm tra slot của *core kế tiếp*,
không phải slot của chính nó. Phase 6 so dữ liệu sau khứ hồi với bản gốc còn nguyên ở L2.

**Checksum vàng tính ngoài chương trình.** `DEMO_L2_GOLDEN` được tính lúc sinh `demo_data.c`
bằng đúng thuật toán mà `demo_checksum()` dùng (xor rồi xoay trái 1 bit). Nếu tính tại
chỗ lúc chạy thì phép so trở thành vô nghĩa.

**Đối chiếu dữ liệu, không đọc thanh ghi trạng thái.** Phase 6 không tin `MCHAN_STATUS`
báo "xong" — nó so từng word. Đó chính là điều mà phép thử ngược `INJECT_FAULT_DMA` chứng
minh.

### Tiêu chí pass — phải đủ cả bốn

1. đủ 9 dòng `[PHASE n] ... OK`
2. log có `[STDOUT-CL0_PE0]` đến `CL0_PE7`
3. `==== FULL-SYSTEM SUMMARY: SUCCESS (0 phase loi)`
4. `[TB] ... Received status core: 0x00000000`

Điểm 2 không thừa: đã từng có lượt chạy báo SUCCESS với status `0x00000000` **trong khi
cluster chưa hề khởi động**.

---

## 7. Bốn cơ chế chống "pass giả"

Phần lớn độ dài của file đến từ đây, không phải từ logic test.

### 7.1 Gom lỗi qua `cl_report()`, không phải `return`

Runtime **chỉ giữ giá trị trả về của core 0** (`kernel/cluster.c`, `cluster_entry_stub`).
Nếu mỗi core `return` số lỗi của mình, lỗi do core 1–7 phát hiện bị vứt đi trong im lặng.

```c
static inline void cl_report(int n) {
    if (n == 0) return;
    eu_mutex_lock(eu_mutex_addr(CL_MUTEX_ID));
    demo_cl_fails += n;
    eu_mutex_unlock(eu_mutex_addr(CL_MUTEX_ID));
}
...
return (get_core_id() == 0) ? demo_cl_fails : 0;
```

Hệ quả tinh tế: `phase5_tcdm()` tự gọi `cl_report()` bên trong, nên `main()` **cố ý bỏ**
giá trị trả về của nó — báo hai lần thì lỗi bị đếm đôi.

### 7.2 Sentinel, không tin giá trị trả về

`cluster_start()` gọi `pi_l1_malloc(cid, 8 * CLUSTER_STACK_SIZE)`; nếu thất bại nó
`return` **im lặng** *trước* dòng `cluster_running = 1` (`kernel/cluster.c:83-87`). Khi đó
`cluster_wait()` trả về 0 — không phân biệt được với một lần chạy thành công.

Không phải giả thuyết: lượt chạy đầu tiên của chính chương trình này báo SUCCESS trong khi
cluster chưa khởi động, vì `CLUSTER_STACK_SIZE=0x2000` làm 8 × 8 KB = đúng 64 KB.

Nay cluster core 0 đặt `demo_cl_ran = DEMO_CL_RAN_MAGIC` và FC kiểm chính biến đó.

### 7.3 `POLL_UNTIL` thay cho mọi vòng chờ vô hạn

`plp_dma_wait()` của runtime là vòng `while` không giới hạn mà thân vòng làm core **ngủ**
chờ sự kiện DMA. DMA không báo xong thì core ngủ vĩnh viễn: không log, không FAIL, mô
phỏng đứng im tới hết giờ.

```c
#define POLL_UNTIL(cond, limit) ({ volatile int _n = 0; \
    while (!(cond) && _n < (limit)) _n++; (_n < (limit)); })
```

Đổi một cái treo lấy một dòng FAIL đọc được kèm `MCHAN_STATUS`. Cùng lý do, phase 7 không
dùng `DATAMOVER_BARRIER()` — macro đó chờ event 12 mà `cluster_core_init()` không unmask.

### 7.4 Hai đường tiêm lỗi

| Cờ | Phá gì | Phải FAIL ở đâu | Chứng minh điều gì |
|---|---|---|---|
| `INJECT_FAULT` | đảo bit dữ liệu của **core 3** | phase 5, status `0x00000001` | lỗi ở core ≠ 0 vẫn tới được exit status |
| `INJECT_FAULT_DMA` | cắt lượt DMA về còn 2 word | phase 6, word 254 | phase 6 đối chiếu **dữ liệu**, không chỉ đọc thanh ghi |

Nếu một trong hai phép này **PASS**, bài test đang hỏng chứ không phải đang tốt. Đây là
phần bắt buộc của một lượt nghiệm thu, không phải tuỳ chọn.

---

## 8. Phase 7 — chỗ khó nhất

Ba thứ ở đây không suy ra được từ tài liệu, phải đo.

### `BW = 12` byte, đo bằng thực nghiệm

Hằng số `DATAMOVER_BW = 256/8 = 32` trong `test_datamover.c` của dependency là của **một
cấu hình khác**. Suy từ RTL (`N_MASTER_PORT = 9` → 36 byte) cũng **sai**.

Cách xác định con số đúng mà không cần đọc thêm RTL: đổi `D0_STRIDE` rồi nhìn mẫu word bị
bỏ sót.

| `D0_STRIDE` đặt | Word đúng | Chu kỳ |
|---|---|---|
| 32 byte (8 word) | 0,1,2 / 8,9,10 / … | 8 |
| 36 byte (9 word) | 0,1,2 / 9,10,11 / … | 9 |

Chu kỳ đi theo stride, còn **số word đúng mỗi chu kỳ luôn là 3**. Vậy stride do phần mềm
đặt, payload mỗi nhịp cố định 3 word = 12 byte = 96 bit do phần cứng.

Đây là bước quan trọng về phương pháp: nó **tách bạch hai đại lượng** đang bị lẫn.

### `DATAMOVER_CG_ENABLE()` phải gọi trước mọi thứ

HWPE mặc định bị clock-gate. Thiếu bước này, vòng poll treo tới hết timeout và triệu chứng
trông **y hệt** như register map bị sai — một hướng gỡ lỗi tốn thời gian vô ích.

### Chờ theo hai nhịp

```c
POLL_UNTIL(status != 0, POLL_LIMIT / 10);   /* cho job khoi dong */
POLL_UNTIL(status == 0, POLL_LIMIT);        /* roi cho no ket thuc */
```

Poll thẳng `status == 0` sẽ thoát **ngay lập tức**: ngay sau `TRIGGER` job chưa kịp chạy
nên `STATUS` vẫn đang là 0. Đó chính là nguyên nhân lượt chạy trước dừng ở word 3.

Nhịp đầu hết giờ **không** bị coi là lỗi — job có thể đã xong quá nhanh; để phép so sánh
dữ liệu phán quyết.

---

## 9. Muốn thêm một phase

Sửa hai file là đủ:

1. [demo.h](../../sw/full_system/demo.h) — khai báo `int phaseN_xxx(void);` vào đúng nhóm
   FC hay Cluster
2. [full_system.c](../../sw/full_system/full_system.c) — viết thân hàm, nối vào `main()`:
   nhánh FC dùng `fails += phaseN()`, nhánh cluster dùng `cl_report(phaseN())`

Thêm khi cần: [demo_data.c](../../sw/full_system/demo_data.c) nếu có dữ liệu vàng mới,
[Makefile](../../sw/full_system/Makefile) nếu thêm đường tiêm lỗi, và bảng phase trong
[README](../../sw/full_system/README.md).

Ba ràng buộc bắt buộc:

- mọi vòng chờ phần cứng dùng `POLL_UNTIL`, không bao giờ `while` trần
- phase chạy trên cluster gom lỗi qua `cl_report()`, không `return`
- đừng `cl_report()` hai lần cho cùng một lỗi

Phase mới nào cũng nên kèm một đường tiêm lỗi. Một phase chưa từng được chứng minh là
biết FAIL thì chưa chứng minh được gì.

---

## 10. Giới hạn đã biết

- **Phase 8 chưa chứng minh tín hiệu ra chân thật.** Nó mới chỉ ghi/đọc lại thanh ghi
  `PADOUT`. Muốn biết có mức logic ra pad hay không thì phải thu thêm nhóm `pad_*` ở
  `tb_pulp`.
- **Phase 7 bị tắt trên bản FPGA** (`PHASE_SKIP`) vì bitstream đặt `USE_HWPE_CL=0`.
- **Không có script sinh `demo_data.c`.** Header ghi "sinh tự động, đừng sửa tay" nhưng
  bộ sinh không nằm trong repo. Muốn đổi dữ liệu thì phải tính lại `DEMO_L2_GOLDEN` bằng
  tay theo đúng thuật toán của `demo_checksum()`.
- **Chỉ 4 phase có tham chiếu ngoài thật sự** (1, 6, 7, và một phần 5). Các phase còn lại
  đối chiếu với công thức tự sinh, nên chúng chứng minh "khối có phản hồi đúng giao thức"
  chứ không chứng minh "khối tính đúng".
