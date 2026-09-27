# Phương pháp phân tích RTL qua SoC domain PULP

Mục tiêu là **giải thích một hành vi bằng chuỗi bằng chứng từ phần mềm tới logic
phần cứng**, rồi lần response ngược về nơi phát lệnh. Phương pháp dùng ở đây là
**phân tích tĩnh có xét cấu hình, kết hợp phân rã cấu trúc từ trên xuống và lần
luồng dữ liệu/điều khiển theo giao dịch**. Sau đó dựng mô hình chu kỳ để tạo giả
thuyết kiểm chứng. Đây không phải formal verification hay mô phỏng mới.

Đợt tiếp theo 2026-09-13 đã triển khai [kế hoạch microarchitecture PULP](../microarchitecture/micro_00_plan_phan_tich_pulp.md),
bắt đầu từ [FC pipeline](../microarchitecture/micro_01_fc_pipeline.md), [LSU](../microarchitecture/micro_02_fc_lsu.md)
rồi [nối SoC interconnect](../microarchitecture/micro_03_fc_soc_interconnect.md). Đợt này có thêm
simulation LSU độc lập; phạm vi và log được tách rõ khỏi phân tích tĩnh dưới đây.

Các ví dụ đã triển khai:

1. [FC → ROM/L2: topology, decode, arbitration, response](soc_01_fc_memory_rtl.md).
2. [FC → APB timer → interrupt → FC](soc_02_timer_irq_rtl.md).
3. [UART/uDMA, debug và điều khiển cluster](soc_03_udma_debug_cluster_rtl.md).

Cấu hình nền theo [bài 00](../architecture/deep_dive_00_effective_configuration.md): RTL Questa,
FC loại 0, FPU bật, HWPE FC tắt, HWPE cluster bật khi gọi runner full_system.
Các file mới phân tích sâu SoC, bổ sung cho [bài tổng quan 02](../architecture/deep_dive_02_soc_domain.md).

## 1. Bắt đầu bằng câu hỏi có thể kiểm chứng

Không bắt đầu bằng “đọc hết SoC”. Chọn một câu hỏi với đầu vào/đầu ra cụ thể:

> Khi FC đọc địa chỉ shared L2 `0x1C010014`, request đi tới bank/row nào,
> được grant lúc nào, và làm sao response quay đúng về FC?

Lập một phiếu giao dịch:

| Trường | Ví dụ |
|---|---|
| Chủ thể | FC data port, không phải instruction port hay DMA |
| Thao tác | aligned 32-bit load |
| Đầu vào | address `0x1C010014`, `req=1`, `wen=1` |
| Điều kiện | reset đã nhả, clock chạy, master giữ request khi chưa grant |
| Chấp nhận | `req && gnt` tại cạnh clock |
| Hoàn tất | `r_valid` cùng dữ liệu/`r_opc`; chưa đồng nghĩa CPU retire |
| Trường hợp đối chứng | đổi address thành `0x1C010024`, cùng bank khác row |

Địa chỉ này là **ví dụ tính decode**, không phải vùng trống được phép ghi khi
chương trình đang chạy. Khi thực nghiệm phải lấy buffer từ linker/allocator.

## 2. Chốt source thực sự được dùng

Đọc `testbench → top → wrapper → implementation`, ghi lại parameter override và
`ifdef/generate`. Tách ba khái niệm:

- File có trong repository.
- File nằm trong compile script.
- Module/nhánh được instantiate trong cấu hình hiệu lực.

Ví dụ đã kiểm tra: có `pulp_soc/rtl/components/apb_timer_unit.sv`, nhưng
`sim/compile.tcl` chọn **`timer_unit/rtl/apb_timer_unit.sv`**. Hai bản khác nhau;
đọc nhầm bản vẫn có thể viết ra một mô tả nghe hợp lý nhưng sai implementation.

Các lệnh thực tế, chạy từ root repo:

```bash
# 1. Điểm vào, nguồn được compile, cấu hình.
rg -n 'pulp_soc|fc_subsystem|apb_timer_unit|lint_2_axi|addr_decode' sim/compile.tcl
rg -n 'CORE_TYPE|USE_FPU|USE_HWPE|fc_fetch_en|rstn_glob' rtl/pulp/pulp.sv

# 2. Tìm definition đúng. Bender cache thường bị ignore nên dùng --hidden --no-ignore.
rg --files --hidden --no-ignore .bender/git/checkouts -g '!**/.git/**' -g '*.sv' | rg '/(apb_timer_unit|tcdm_demux|lint_2_axi)\.sv$'

# 3. Chỉ mở vùng chứa logic cần đọc, giữ số dòng để trích nguồn.
nl -ba .bender/git/checkouts/pulp_soc-c519334bd3ac5582/rtl/pulp_soc/tcdm_demux.sv | sed -n '73,165p'
```

`rg` chỉ định vị bằng chứng, không phải parser elaboration. Kết quả search không
đủ kết luận một nhánh active. Với project khác, thay compile script bằng filelist,
manifest, lệnh compiler hoặc log elaboration tương ứng. Kiểm tra cả include path,
macro command line, library mapping và source trùng tên module.

## 3. Lập sổ kết nối trước khi suy luận chức năng

Với mỗi instance, ghi **port formal ↔ net thực tế ↔ đầu bên kia**:

| Tại FC subsystem | Net trong pulp_soc | Tại interconnect |
|---|---|---|
| `l2_data_master` | `s_lint_fc_data_bus` | `tcdm_fc_data`, remap rồi vào master 0 |
| `l2_instr_master` | `s_lint_fc_instr_bus` | `tcdm_fc_instr`, vào master 1 |

Tên `l2_instr_master` không đảm bảo đích là L2: bus này cũng fetch ROM.
Tên `Slave` của modport mô tả vai trò của module tại interface, không phải
người khởi tạo giao dịch trong câu chuyện. Luôn lần producer của `req`.

Ở interface đóng gói bằng macro, đọc definition macro hoặc interface để biết
bit width/hướng tín hiệu; không suy byte-enable từ localparam không được dùng.
Ví dụ `tcdm_demux` có `BE_WIDTH=2`, nhưng wiring dùng macro interface và không
biến bus byte-enable 4 bit thành 2 bit.

## 4. Lần request tới đích, rồi bắt buộc lần response về

Ghi lại từng biến đổi:

```text
FC addr → remap prefix → decode vùng → chọn bank
→ arbitration → SRAM row/byte-enable
→ SRAM data → response mux → active slave ở demux → FC
```

Với mỗi chặng, hỏi:

1. Có đổi address, width, polarity hoặc ID không?
2. Có buffer/register không? Nó latch ở cạnh nào, theo enable gì?
3. Grant nghĩa là đã nhận vào queue, đã tới memory, hay đã hoàn tất?
4. Response mang ID, hay module nhớ đích từ request trước?
5. Nếu downstream không sẵn sàng thì dữ liệu được ai giữ?

Ví dụ cụ thể: `tcdm_demux` giữ `active_slave_q` để biết response thuộc nhánh cũ,
trong khi `port_sel` combinational có thể đã chỉ tới request mới. Crossbar giữ
`bank_sel_q` và sinh `vld_q` từ grant. Bỏ qua đường response sẽ bỏ sót cả hai
trạng thái lưu này.

## 5. Đọc combinational và sequential như một hệ phương trình

Quy trình cho một FSM:

1. Tìm state register và giá trị reset trong `always_ff`.
2. Tìm next-state defaults ở đầu `always_comb`.
3. Với mỗi state, ghi output, điều kiện chuyển và những thanh ghi sẽ được latch.
4. Xét cả đường không xảy ra handshake, không chỉ đường thành công.
5. Xét response cũ và request mới cùng chu kỳ.

Áp dụng cho `tcdm_demux`:

```text
IDLE + req + gnt                  → PENDING
IDLE + req + !gnt                 → IDLE, chưa chấp nhận
PENDING + !r_valid                → PENDING, không phát request mới
PENDING + r_valid + !new_req      → IDLE
PENDING + r_valid + new_req + gnt → PENDING, đổi active_slave cho lượt mới
```

Đây là cách phát hiện khả năng **back-to-back** dù chỉ có một transaction chờ
response tại một thời điểm. Không suy “một outstanding” thành “luôn phải có
một chu kỳ trống giữa mọi request”.

Với register không có FSM, vẫn dùng cách này: `next=count`, sau đó xét priority
reset/write/increment. `if/else if` khác các `if` độc lập; assignment cuối có thể
ghi đè assignment trước. Ví dụ IRQ acknowledge có ưu tiên cao hơn set pending
cùng chu kỳ; priority IRQ ID lớn nhất xuất phát từ vòng `for` tăng dần ghi đè.

## 6. Dựng bảng chu kỳ với quy ước thời gian rõ ràng

Gọi `C0` là khoảng giữa hai cạnh clock; handshake ở cạnh kết thúc `C0` gọi là
`E1`. Register cập nhật bằng nonblocking assignment sau `E1`, output mới tồn tại
trong `C1`. Consumer lấy output đó tại cạnh kết thúc `C1`.

| Khoảng | Combinational trước cạnh | Register tại cạnh cuối |
|---|---|---|
| C0 | req/grant giao dịch A | chốt bank A, valid và địa chỉ SRAM |
| C1 | response A hợp lệ; có thể req/grant B | consumer nhận A; chốt B |
| C2 | response B hợp lệ | consumer nhận B |

Phải ghi giả định: cùng clock, `RespLat=1`, memory latency 1, không arbitration
stall. Đây là **[SUY RA]** từ RTL, không phải waveform đã đo. Khi có CDC hoặc
backpressure, dùng các mốc handshake thay vì tự gán tổng latency bằng một số cố định.

Không nhầm mô phỏng bằng Python các công thức này với chạy RTL. Python giúp
kiểm tra tính địa chỉ, giải mã instruction và tính nhất quán của bảng; nó không
chứng minh implementation đáp ứng giao thức hay timing.

## 7. Đi ngược từ RTL tới phần mềm

Từ thanh ghi tìm HAL, từ HAL tìm hàm gọi, rồi xét ELF/disassembly nếu cần chứng
minh instruction compiler thực sự phát ra. Đừng dừng ở tên API.

Ví dụ `timer_base_fc(0,1)` thêm 4 vào base timer; helper tên `timer_start_lo_set`
được gọi với base đã dịch nên thực tế ghi **START_HI**. Tên helper có “lo” không
quyết định counter nào hoạt động; phép cộng địa chỉ mới quyết định.

Ví dụ UART có hai nghĩa completion: uDMA đã cấp phát hết request buffer và UART
đã phát hết serial bits. Runtime chờ hai trạng thái; event TX từ uDMA không thay
thế việc kiểm tra stop bit ở pad.

## 8. Tìm phản ví dụ để kiểm tra kết luận

Sau đường chạy thuận lợi, lần ít nhất các nhánh:

| Kết luận muốn đưa ra | Phản ví dụ cần thử/lần |
|---|---|
| mọi địa chỉ sai trả lỗi | địa chỉ nằm trong cửa sổ APB nhưng không thuộc slave nào |
| ngắt đã xử lý sau ack | nguồn vẫn active ở chu kỳ sau ack |
| register UART đã đổi baud | config chỉ được latch sang peripheral clock khi enable chuyển lên |
| private bank dành riêng FC | debug/uDMA/cluster cũng có đường decode tới đó không? |
| mask bit 1 là bật | event generator dùng `~mask`, FC IRQ controller dùng `&mask` |
| grant DMA nghĩa là dữ liệu đã tới UART | grant ở queue address generator có thể sớm hơn memory response |

Phân biệt **hành vi đáng chú ý đã thấy trong RTL** với **bug được xác nhận**.
Muốn kết luận bug cần contract mong đợi và phép kiểm chứng. Ví dụ “APB miss giữ
PREADY=0” là sự thật source; việc phần mềm có thể gặp nó trong workload cụ thể
còn cần chứng minh.

## 9. Ghi bằng chứng và biết khi nào dừng

Một kết luận đạt mức đủ dùng khi có:

```text
Cấu hình áp dụng → dòng RTL/SW → cơ chế → hệ quả → giới hạn → cách kiểm chứng
```

Các bài dùng nhãn **[RTL]**, **[SW]**, **[SUY RA: giả định]**, **[CẦN ĐO]**.
Không có kết quả simulator mới trong đợt phân tích này. Các chỗ đụng cache/core
pipeline/CDC sâu hơn được nêu đúng ranh giới, không thay bằng khẳng định tổng quát.

[Sổ bằng chứng](../../../../report/soc_rtl_analysis_20260910/evidence.json) được tạo bằng
[script thu bằng chứng](../../../../report/soc_rtl_analysis_20260910/collect_evidence.py),
lưu source path/hash, HEAD dependency và các vị trí logic then chốt.
Có thể chạy từ root:

```bash
python3 report/soc_rtl_analysis_20260910/collect_evidence.py > /tmp/pulp-soc-evidence.json
```

Script chỉ đọc file/git và xuất JSON; không build, không sửa source. Nếu source
đổi, dùng diff JSON để biết bằng chứng nào phải đọc lại. Đây là phương tiện hỗ
trợ truy nguyên kết luận, không phải kiểm chứng RTL tự động.

## 10. Mẫu tái sử dụng cho source khác

```text
Câu hỏi/giao dịch:
Cấu hình/top/nhánh active:
Producer và consumer:
Clock/reset mỗi chặng:
Input/address/width/polarity:
Điều kiện acceptance:
State/register cần nhớ:
Decode/arbitration/buffer:
Response/completion/error:
Trình tự phần mềm tương ứng:
Bảng chu kỳ và giả định:
Phản ví dụ:
Source + dòng + revision/hash:
Điều đã xác nhận / điều cần đo:
```

Với phần mềm thuần, thay module/port bằng hàm/API, register/FSM bằng state object,
clock bằng thứ tự gọi hoặc scheduling, handshake bằng return/callback/future,
CDC bằng ranh giới thread/process. Vẫn giữ nguyên nguyên tắc: chọn một hành vi,
lần dữ liệu và điều khiển tới cùng, kiểm tra completion, rồi tìm phản ví dụ.
