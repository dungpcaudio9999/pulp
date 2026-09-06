# Demo full-system cho PULP — chương trình C đánh thức mọi khối

> ## ✅ ĐÃ THỰC HIỆN XONG — `2026-09-06`
>
> Kế hoạch này đã được triển khai đầy đủ tại [sw/full_system/](../../sw/full_system/).
> **9/9 phase pass**, status `0x00000000`, log có đủ `CL0_PE0`..`CL0_PE7`. Phép thử ngược
> (`INJECT_FAULT=1`) cho FAIL đúng như mong đợi với status `0x00000001`.
>
> | Tài liệu | Nội dung |
> |---|---|
> | [sw/full_system/README.md](../../sw/full_system/README.md) | sáu quyết định thiết kế không hiển nhiên và hai cạm bẫy môi trường |
> | [report/cluster_buoc0_20260906/](../../report/cluster_buoc0_20260906/) | Bước 0 — bằng chứng cluster hoạt động |
> | [report/full_system_20260906/](../../report/full_system_20260906/) | chuỗi chẩn đoán phase 7 và kết quả cuối |
> | [report/waveform_20260906/](../../report/waveform_20260906/) | Milestone 5 — dòng thời gian và phân bổ thời gian |
>
> **Khác biệt lớn nhất so với kế hoạch:** băng thông HWPE datamover không phải 32 byte như
> `test_datamover.c` của dependency ghi, cũng không phải 36 byte như suy ra từ RTL
> (`NB_HWPE_PORTS = 9`), mà là **12 byte** — đo bằng thực nghiệm. Phase 7 phải sửa bốn
> vòng mới chạy, đúng như phần "Rủi ro đã biết" dự đoán.
>
> Phần còn lại của tài liệu này giữ nguyên làm bản ghi lập luận thiết kế.


> Bản sửa `2026-09-06`. Các mục đánh dấu **[đã kiểm]** là những chi tiết đã được đối chiếu
> trực tiếp với RTL/runtime trong dependency đã checkout, không phải suy đoán.

## Context

Bài `hello` hiện tại chỉ chạy trên FC (bằng chứng: `[STDOUT-CL31_PE0]`, CL31 = `FC_CORE_CLUSTER_ID`)
— cluster domain chưa bao giờ được bật. Rà soát toàn bộ `regression_tests/` cho thấy **không có bài
nào phủ hết các khối** trong một binary duy nhất, và bộ test đầy đủ hơn ở `tests/` thì clone từ
GitLab nội bộ ETH nên không lấy được. Riêng HWPE là khối có trong RTL mà chưa có bài regression nào
chạm tới — nhưng xem cảnh báo ngay dưới đây về việc nó bị tắt trong testbench.

> ### ✅ Phase 7 (HWPE) — đã giải quyết `2026-09-06`
>
> `rtl/tb/tb_pulp.sv:42,48` đặt **`USE_HWPE = 0`** và **`USE_HWPE_CL = 0`**, ghi đè mặc
> định `1` của `rtl/pulp/pulp.sv`. Nghĩa là mặc định HWPE datamover **không hề được
> instantiate** dưới `tb_pulp` — phase 7 viết đúng đến mấy cũng đọc về rác hoặc treo.
>
> **Cách xử lý đã kiểm chứng: truyền `-gUSE_HWPE_CL=1` lúc `vsim`. Không cần sửa
> `tb_pulp.sv`, không cần build lại.** Bước vopt dùng `-floatparameters+tb_pulp`
> (`sim/Makefile:41`) nên tham số vẫn override được lúc runtime. Bằng chứng ở
> [report/cluster_buoc0_20260906/07_hwpe_conclusion.md](../../report/cluster_buoc0_20260906/07_hwpe_conclusion.md):
>
> ```
> /tb_pulp/.../cluster_i/hwpe_gen/hwpe_subsystem_i (hwpe_subsystem)
> /tb_pulp/.../hwpe_subsystem_i/datamover_gen/hwpe_top_wrap_i (datamover_top)
> ```
>
> Cũng xác nhận engine là `datamover_top`, khớp `hal_datamover.h`.
>
> **Cách truyền cờ — phải qua biến môi trường, không phải dòng lệnh make:**
>
> ```bash
> export vsim_flags="+ENTRY_POINT=0x1c008080 -permit_unmatched_virtual_intf \
>                    -gBAUDRATE=115200 -gUSE_HWPE_CL=1"
> make run
> ```
>
> `vsim_flags` dùng `?=` rồi `+=` (`default_rules.mk:155`). Biến môi trường được `?=`
> giữ nguyên và các `+=` vẫn nối thêm `-gLOAD_L2=JTAG`. Nếu truyền
> `make run vsim_flags=...` trên dòng lệnh thì biến đó ghi đè cả các `+=`, làm **mất**
> `-gLOAD_L2=JTAG` và chương trình sẽ không được nạp.

Mục tiêu: **một chương trình C duy nhất** lần lượt đánh thức từng khối và tự kiểm tra kết quả, chạy
được cả trên Questa (verify ngay) lẫn trên FPGA sau này (demo qua UART). Đây là hạng mục B trong kế
hoạch hai bước; hạng mục A (port ZCU104) làm sau và độc lập.

## Bước 0 — ĐÃ CHẠY XONG `2026-09-06`: cluster hoạt động

Evidence đầy đủ ở [report/cluster_buoc0_20260906/](../../report/cluster_buoc0_20260906/).

| Bài test | Kết quả |
|---|---|
| `mchan_tests/testMCHAN_TCDM2TCDM_tx_rx` | **PASS**, status `0x00000000`, 128→4096 giao dịch TX/RX đồng thời |
| `parallel_bare_tests/multicore` | FAIL status `0x00000025`, nhưng **8 core đều boot và in ra** |

Bằng chứng quyết định: log có đủ `[STDOUT-CL0_PE0]` đến `[STDOUT-CL0_PE7]`, trong khi
bài `hello` chỉ có `CL31` (chính là FC). **Phase 3–6 dưới đây do đó đã được bảo chứng
bằng thực nghiệm** — chúng chỉ còn là lớp bọc quanh cơ chế đã chạy được:

- Phase 3 — PMU, cluster clk/rst, AXI SoC→CL: cluster khởi chạy được
- Phase 4 — 8 core, event unit, barrier: cả 8 core chạy và đồng bộ đủ để in
- Phase 5 — TCDM: mchan đọc ghi TCDM qua mọi kích thước
- Phase 6 — MCHAN DMA, AXI hai chiều: pass sạch

### Vì sao `multicore` FAIL mà không phải lỗi cluster

`multicore/Makefile` khai báo `nbPe = 4` và `stackSize = 10000`. **pulp-runtime bỏ qua
cả hai** — chúng không xuất hiện ở bất kỳ đâu trong `pulp-runtime/rules/`. Runtime
hardcode `ARCHI_CLUSTER_NB_PE 8` (`archi/chips/pulp/properties.h:91`) và
`CLUSTER_STACK_SIZE 0x800` = 2 KB (`pulp-runtime/include/pulp.h:21`).

Bài sudokusolver đệ quy, viết cho stack ~10 KB, chạy với 2 KB nên tràn sang vùng L1 kề
bên. Log khớp chính xác: bốn hàng đầu của lời giải đúng, từ hàng năm trở đi lẫn các giá
trị `268435852`+ = `0x1000_000C`+ — địa chỉ TCDM rò vào mảng kết quả. PE0 chạy solver
nên hỏng, PE1–PE7 làm việc nhẹ hơn nên `SUCCESS`. Việc `mchan` pass sạch củng cố cách
giải thích này.

> ### ⚠ Hệ quả bắt buộc cho chương trình sắp viết
>
> **Stack mỗi core cluster chỉ 2 KB.** Phase nào dùng đệ quy hoặc mảng cục bộ lớn phải
> tự đặt trong `Makefile`:
> ```make
> PULP_CFLAGS += -DCLUSTER_STACK_SIZE=0x2000
> ```
> Đừng tin `stackSize` của Makefile — nó không có tác dụng. Tràn stack ở đây **không
> gây crash**, nó âm thầm làm hỏng dữ liệu ở L1 kề bên, đúng như bài `multicore` cho thấy.

## Môi trường chạy — bắt buộc đúng đủ

Xem [nhật ký QuestaSim](nhat-ky-mo-phong-pulp-questasim.md), Phụ lục B. Bốn điểm dễ
sai nhất, cả bốn đều đã tự vấp phải ngày `2026-09-06`:

| Thiếu gì | Triệu chứng |
|---|---|
| `lmgrd` chưa chạy | `Fatal: Invalid license environment` |
| `LD_LIBRARY_PATH` → `compat-libs` | `cc1: libmpfr.so.4: cannot open shared object file` |
| Chưa rời conda | `ModuleNotFoundError: No module named 'elftools'` |
| Chưa `source pulp-runtime/configs/pulp.sh` | `No rule to make target 'clean'` |

Cái cuối nguy hiểm nhất vì `rules/pulp.mk` dùng `-include`, nên make **im lặng** không
nạp target nào và thông báo lỗi không hề gợi ý nguyên nhân.

## Bốn cơ chế then chốt đã xác minh

**1. Cùng một source chạy được trên cả sim lẫn FPGA. [đã kiểm]** `pos_putc()` trong
`pulp-runtime/lib/libc/minimal/io.c:244-251` rẽ nhánh theo `CONFIG_IO_UART`: bằng 0 thì ghi vào
fake stdout `ARCHI_STDOUT_ADDR` (tb bắt được, in ra transcript), bằng 1 thì đẩy qua UART thật.
Bật bằng `make io=uart` (`rules/pulpos/default_rules.mk:33-38`). Không cần `#ifdef` nào trong code.

**2. Offload cluster. [đã kiểm]** `bench_cluster_forward(0)` (`pulp-runtime/kernel/bench.c:276`)
gọi `cluster_start` rồi `cluster_wait`, và **trả về giá trị `main()` trả từ phía cluster**
(`bench.c:262-270`). Nghĩa là `main()` chạy hai lần — lần đầu trên FC, lần sau trên cả 8 core
cluster. Xem mục **Gom lỗi từ 8 core** để biết giới hạn quan trọng của cơ chế trả về này.

**3. Tie-off `fetch_en_i` KHÔNG chặn offload. [đã kiểm]** `rtl/pulp/pulp.sv:1159+` buộc
`.fetch_en_i(1'b0)` và `.base_addr_i('0)` cho `cluster_domain` — deep-dive Milestone 1 từng đánh
dấu đây là nghi vấn. Đã truy xong: trong `pulp_cluster.sv`, `fetch_en_i` chỉ đi vào
`cluster_peripherals_i` (dòng 762), còn fetch enable thật của core là
`fetch_en_int = fetch_enable_reg_int` (dòng 550), do FC ghi qua thanh ghi cluster control.
Runtime dùng đúng đường đó: `cluster_start()` gọi `plp_ctrl_core_bootaddr_set_remote()` rồi
`eoc_fetch_enable_remote()` (`pulp-runtime/kernel/cluster.c:62-95`). **Không cần sửa RTL.**
Ghi lại ở đây để khỏi phát hiện lại giữa lúc debug rồi hiểu nhầm là nguyên nhân.

**4. HWPE đã có HAL sẵn — không cần suy ra register map. [đã kiểm]** Dependency
`hwpe-datamover-example` ship kèm HAL và bài test tham chiếu:

```
.bender/git/checkouts/hwpe-datamover-example-a9b2d6689c13b9f9/test/
├── hal_datamover.h      ← register map đầy đủ + macro điều khiển
└── test_datamover.c     ← bài test tham chiếu (API PMSIS, chỉ đọc tham khảo)
```

`hal_datamover.h` khai báo `DATAMOVER_ADDR_BASE 0x00201000` — khớp độc lập với
`ARCHI_HWCE_ADDR` = `ARCHI_CLUSTER_ADDR (0x00000000)` + `0x00200000` + `0x1000`
(`archi/chips/pulp/memory_map.h:81,91,98`). **Copy header này vào project thay vì tự viết.**

## Files sẽ tạo — `/home/dungpc/ndmoney4porche/projects/pulp/sw/full_system/`

| File | Nội dung |
|---|---|
| `full_system.c` | `main()` hai nhánh FC/cluster + toàn bộ phase |
| `demo.h` | Macro `PHASE_BEGIN/OK/FAIL/SKIP`, bảng kết quả, khai báo phase |
| `demo_data.c` / `demo_data.h` | Mảng `L2_DATA` (`.data`) và `L1_DATA` (`.heapsram`) + checksum vàng |
| `hal_datamover.h` | **Copy nguyên** từ dependency (mục 4 ở trên), không viết lại |
| `Makefile` | `PULP_APP_SRCS` + target sim/fpga |
| `README.md` | Cách chạy cả hai chế độ + log chạy được làm mốc |

Thư mục `sw/` không nằm trong `.gitignore` nên được fork của bạn track. Build chạy được từ vị trí bất
kỳ vì `PULP_SDK_HOME` và `VSIM_PATH` đều là biến môi trường tuyệt đối
(`configs/common.sh:13-14`, `default_rules.mk:280-298`).

## Gom lỗi từ 8 core — bắt buộc, không phải tuỳ chọn

Runtime **chỉ giữ giá trị trả về của core 0**:

```c
// pulp-runtime/kernel/cluster.c — cluster_entry_stub()
if (hal_core_id() == 0) { cluster_retval = retval; cluster_running = 0; }
```

Nếu để mỗi core `return fails` của riêng nó, một sai lệch TCDM do core 3 phát hiện sẽ **bị vứt đi
trong im lặng** và bài test vẫn báo pass. Vì vậy dùng một biến đếm dùng chung trong L1, bảo vệ bằng
mutex của event unit (`eu_mutex_lock`/`eu_mutex_unlock`, `hal/eu/eu_v3.h:384-413`; event
`PULP_MUTEX_EVENT` đã được `cluster_core_init()` unmask sẵn):

```c
__attribute__((section(".heapsram"))) volatile int cl_fails;

static void cl_report(int n) {
  if (n == 0) return;
  eu_mutex_lock(eu_mutex_addr(0));
  cl_fails += n;
  eu_mutex_unlock(eu_mutex_addr(0));
}
```

Core 0 khởi tạo `cl_fails = 0` và `eu_mutex_init()` **trước** barrier đầu tiên; mọi core gọi
`cl_report()`; core 0 đọc `cl_fails` **sau** `synch_barrier()` cuối cùng rồi mới `return`.

## Cấu trúc `main()`

```c
int main() {
  if (get_cluster_id() != 0) {          /* ---- chạy trên FC (CL31) ---- */
    int fails = 0;
    phase0_banner();
    fails += phase1_fc_l2();
    fails += phase2_timer();
    fails += phase3_cluster_poweron();   /* gọi bench_cluster_forward(0) */
    fails += phase8_gpio();
    phase9_summary(fails);
    return fails;                        /* TB đọc thành exit status */
  } else {                               /* ---- chạy trên 8 core cluster ---- */
    if (get_core_id() == 0) {
      cl_fails = 0;
      eu_mutex_init(eu_mutex_addr(0));
    }
    synch_barrier();

    cl_report(phase4_barrier());
    cl_report(phase5_tcdm());
    if (get_core_id() == 0) {
      cl_report(phase6_dma());
      cl_report(phase7_hwpe());
    }
    synch_barrier();

    return (get_core_id() == 0) ? cl_fails : 0;
  }
}
```

## Các phase

| # | Khối được đánh thức | Cách kiểm chứng | API |
|---|---|---|---|
| 0 | FC, L2, đường stdout | In cluster id, core id, `get_core_num()` | `pulp.h:63-78` |
| 1 | FC core, L2, SoC interco | Checksum mảng `L2_DATA`, so với hằng số | `demo_data.h` |
| 2 | APB timer, FC clock | Đọc `timer_count_get` hai lần, phải tăng | `hal/timer/timer_v2.h:68` |
| 3 | **PMU, cluster clk/rst, AXI SoC→CL** | `bench_cluster_forward(0)` trả về | `bench/bench.h` |
| 4 | **Cluster 8 core, event unit, barrier** | Mỗi core ghi ô riêng, `synch_barrier()`, core 0 kiểm đủ 8 | `pulp.h:78`, `hal/eu/eu_v3.h` |
| 5 | **TCDM + interconnect** | 8 core ghi xen kẽ `L1_DATA`, barrier, đọc chéo verify | `demo_data.h` |
| 6 | **MCHAN DMA, AXI hai chiều** | L2→TCDM→L2 khứ hồi, `memcmp` với gốc | `hal/dma/mchan_v7.h:84+` |
| 7 | **HWPE datamover** | Xem trình tự bên dưới | `hal_datamover.h` |
| 8 | GPIO + safe domain padmux | `hal_gpio_paddir_set` + `padout_set`, đọc lại `padout_get` | `hal/gpio/gpio_v3.h:65-80` |
| 9 | — | Bảng tổng kết, `return` số phase lỗi | — |

Mỗi phase độc lập và tự bọc: mọi vòng poll đều có bộ đếm timeout để một khối chết không treo cả
chương trình. Phase bị vô hiệu hoá in `SKIP` kèm lý do thay vì biến mất khỏi output.

Mảng của phase 5 phải mang `__attribute__((section(".heapsram")))` để nằm thật trong TCDM —
nếu không, "test TCDM" sẽ vô tình chạy trên L2 và luôn pass.

## Phase 7 — trình tự đúng cho datamover

Ba bước chuẩn bị mà bản kế hoạch cũ bỏ sót. Quan trọng nhất là **bật clock gate**: HWPE mặc định bị
clock-gate, thiếu bước này thì vòng poll STATUS treo tới hết timeout và triệu chứng **giống hệt
"register map sai"** — rất dễ mất nhiều giờ đi nhầm hướng.

```c
DATAMOVER_CG_ENABLE();              /* clus_ctrl 0x00200000+0x18, mask 0x800 — BẮT BUỘC */
DATAMOVER_SETPRIORITY_DATAMOVER();  /* ưu tiên HCI so với core/DMA */
DATAMOVER_RESET_MAXSTALL();
DATAMOVER_SET_MAXSTALL(8);
DATAMOVER_WRITE_CMD(DATAMOVER_SOFT_CLEAR, DATAMOVER_SOFT_CLEAR_ALL);
for (volatile int k = 0; k < 10; k++);   /* soft-clear cần vài chu kỳ */
/* rồi mới: ACQUIRE → nạp job register → COMMIT_AND_TRIGGER → poll STATUS */
```

Job register nằm ở `DATAMOVER_REGISTER_OFFS 0x40`, ghi qua `DATAMOVER_WRITE_REG(offset, value)`:

| Offset | Tên | Ý nghĩa |
|---|---|---|
| `0x00` | `DATAMOVER_REG_IN_PTR` | địa chỉ nguồn |
| `0x04` | `DATAMOVER_REG_OUT_PTR` | địa chỉ đích |
| `0x08` | `DATAMOVER_REG_TOT_LEN` | tổng độ dài |
| `0x0c`/`0x10` | `IN_D0_LEN` / `IN_D0_STRIDE` | chiều 0 nguồn |
| `0x14`/`0x18` | `IN_D1_LEN` / `IN_D1_STRIDE` | chiều 1 nguồn |
| `0x1c` | `IN_D2_STRIDE` | chiều 2 nguồn |
| `0x20`–`0x30` | `OUT_D0_LEN` … `OUT_D2_STRIDE` | tương tự cho đích |

Đây là **cặp len/stride xen kẽ**, không phải "một dãy stride" như bản kế hoạch cũ ghi — dùng
đúng tên define trong header thì không thể nhầm. (Đối chiếu phía RTL:
`datamover_top.sv:184-197` bind `hwpe_params[0..12]` theo đúng thứ tự này.)

**Chờ hoàn thành: dùng `DATAMOVER_BUSYWAIT()` (poll STATUS), không dùng `DATAMOVER_BARRIER()`.**
Macro barrier chờ event `DATAMOVER_EVT0 = 12`, nhưng `cluster_core_init()` chỉ unmask
`DISPATCH | MUTEX | HW_BAR` (`kernel/cluster.c:40-43`) nên event 12 sẽ không bao giờ tới và
chương trình treo. Bọc poll bằng bộ đếm timeout như các phase khác.

Header còn có sẵn `DATAMOVER_compare_int(actual, golden, len)` để verify và in bảng sai lệch.

Lưu ý khi đọc `test_datamover.c`: bài đó viết theo API PMSIS (`pi_cl_l1_malloc`,
`pi_cl_team_barrier`) nên **không compile được** với pulp-runtime; chỉ dùng làm tham chiếu trình tự.
Bản thân `hal_datamover.h` là define thuần nên dùng trực tiếp được.

## Xử lý khác biệt sim vs FPGA

Makefile truyền `-DDEMO_PLATFORM_FPGA=1` cho bản FPGA. Ảnh hưởng:

- **Phase 7 (HWPE)** → `SKIP`. Bản FPGA đặt `USE_HWPE = 0` **và** `USE_HWPE_CL = 0`
  (`fpga/pulp-zcu102/rtl/xilinx_pulp.v:93,127-128`) nên khối này không tồn tại trên board.
  Tham số gating HWPE của cluster là `USE_HWPE_CL` (`rtl/pulp/pulp.sv:1159`), không phải
  `USE_HWPE` — nếu tự dựng target FPGA mới thì phải tắt cả hai.
- **Phase 8 (GPIO)** → vẫn chạy nhưng in cảnh báo rằng chưa có LED nào được nối ra
  (toàn bộ LED trong `zcu102.xdc` đang bị comment).
- Các phase còn lại giống hệt nhau ở hai chế độ.

Cảnh báo phạm vi: mọi ghi chú FPGA ở trên đều nói về **zcu102** vì đó là target duy nhất tồn tại
trong repo (`fpga/pulp-zcu102`). Hạng mục A nhắm **ZCU104**, hiện **chưa có target nào** — phần
FPGA của kế hoạch này chỉ áp dụng được sau khi hạng mục A dựng xong target đó.

## Build & chạy

```bash
# Questa (mặc định, fake stdout)
cd /home/dungpc/ndmoney4porche/projects/pulp
source setup/vsim.sh && source pulp-runtime/configs/pulp.sh
export PULP_RISCV_GCC_TOOLCHAIN=$HOME/ndmoney4porche/tools/v1.0.16-pulp-riscv-gcc-ubuntu-16
cd sw/full_system && make clean all run

# FPGA (UART thật) — dùng sau khi có bitstream
make clean all io=uart PLATFORM=fpga
```

## Verification

1. `make clean all run` trên Questa, kiểm tra transcript có đủ 10 dòng `[PHASE n] ... OK`.
2. Xác nhận cluster thực sự sống: log phải xuất hiện `[STDOUT-CL0_PE0]` đến `CL0_PE7`
   (hiện tại bài `hello` chỉ có `CL31`). Đây là bằng chứng quyết định cho phase 3–7.
3. `echo $?` sau `make run` phải bằng 0; và `[TB] ... Received status core: 0x00000000`.
4. **Thử nghiệm ngược trên core khác 0.** Sửa hỏng có chủ đích giá trị kỳ vọng của phase 5
   **chỉ trên core 3**, chạy lại, xác nhận exit status khác 0. Đây là phép thử duy nhất chứng minh
   cơ chế gom lỗi ở trên hoạt động; nếu chỉ phá phase 6 (vốn chạy trên core 0) thì lỗi im lặng
   mô tả ở mục **Gom lỗi từ 8 core** sẽ lọt lưới.
5. Thử nghiệm ngược lần hai trên phase 6 để xác nhận các phase độc lập với nhau: phase đó `FAIL`
   còn các phase khác vẫn `OK`.
6. Ghi lại log chạy được vào `sw/full_system/README.md` làm mốc tham chiếu.

## Rủi ro đã biết

**Ngân sách thời gian mô phỏng.** Bài `hello` (chỉ FC, 1668 byte text) mất 22 giây wall-clock cho
5.39 ms sim-time. Chương trình 9 phase với 8 core, DMA và HWPE sẽ lâu hơn nhiều bậc. Nếu nạp JTAG
trở thành nút cổ chai, cân nhắc `-gLOAD_L2=STANDALONE`.

**Phase 7 vẫn là phần rủi ro nhất, nhưng đã giảm đáng kể.** Register map không còn phải suy đoán
(mục 4 và trình tự phase 7 ở trên). Rủi ro còn lại là cấu hình HCI và tương tác clock-gate với
phần còn lại của cluster. Nếu sau vài vòng vẫn không chạy, để phase này ở trạng thái `FAIL` có ghi
chú rõ ràng thay vì kéo dài, rồi báo lại để bạn quyết — các phase khác không bị ảnh hưởng.

**Phase 3 trên FPGA chưa kiểm chứng được lúc này.** Bản FPGA không có FLL thật (thay bằng MMCM
`fpga_clk_gen`), nên trình tự bật nguồn cluster có thể khác trên phần cứng. Trên Questa thì không
vấn đề. Chỉ phát hiện được khi có bitstream — thuộc hạng mục A.

**Nhiễu simulator, không phải hồi quy.** Bài FC-only đã sinh sẵn 4 lỗi
`(vsim-191) unexpected internal error: vsimfunc.c(1989)` của Questa 10.7c mà vẫn pass, cùng warning
`jtag_tick` DPI không tìm thấy. Đừng quy các thông báo này cho code mới.

**Toolchain.** `PULP_RISCV_GCC_TOOLCHAIN` phải trỏ đúng; bản build `hello` ngày `2026-09-04` đã
chạy được với `riscv32-unknown-elf-gcc` 7.1.1 nên đường dẫn trong mục Build ở trên là đã xác minh.
