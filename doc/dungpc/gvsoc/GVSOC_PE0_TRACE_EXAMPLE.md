# Ví dụ giải thích và phân tích instruction trace của PE0

## 1. PE0 và phạm vi của trace

`pe0` là Processing Element số 0, tức core RISC-V đầu tiên trong cluster PULP.
Cấu trúc liên quan có thể hình dung như sau:

```text
PULP chip
├── FC                     core điều khiển
└── Cluster
    ├── PE0                core cluster số 0
    ├── PE1
    ├── PE2
    ├── ...
    └── PE7
```

Khi chạy GVSoC với:

```bash
--trace=chip/cluster/pe0/insn:pe0.log
```

GVSoC ghi lại các instruction mà PE0 thực thi/retire vào `pe0.log`. Trace này
cho biết PC, cycle, hàm và dòng source, opcode, operand, giá trị thanh ghi và địa
chỉ vật lý của một số thao tác load/store.

Ví dụ trong tài liệu sử dụng trace:

```text
report/gvsoc_20260928_live/pe0.log
```

Trình xem tương tác nằm tại:

[`report/gvsoc_20260928_live/pe0_analyzer.html`](../../../report/gvsoc_20260928_live/pe0_analyzer.html)

## 2. Cách trình bày một trace

Nên giải thích ở hai tầng:

1. Kể câu chuyện tổng thể của chương trình: core được khởi động, đồng bộ, truy
   cập bộ nhớ và thực hiện DMA như thế nào.
2. Chọn một đoạn instruction tiêu biểu để chứng minh kết luận bằng PC, cycle,
   register và địa chỉ bộ nhớ cụ thể.

Không nên đọc tuần tự hàng nghìn instruction trong bài trình bày. Chỉ nên chọn
các checkpoint thể hiện một chuyển đổi trạng thái quan trọng.

## 3. Luồng tổng thể của PE0

Trace hiện tại có thể được tóm tắt như sau:

```text
PE0 được khởi động
    |
    v
Đọc mhartid và xác định đây là core 0
    |
    v
Thiết lập stack riêng của PE0
    |
    v
Nhảy vào cluster_entry_stub và main
    |
    v
Phase 4: barrier và event synchronization
    |
    v
Phase 5: kiểm tra L1/TCDM
    |
    v
Phase 6: DMA giữa L2 và L1
    |
    v
Phase 7: truy cập HWPE
    |
    v
Trace dừng do timeout an toàn
```

Có thể diễn đạt bằng lời:

> GVSoC được cấu hình để ghi instruction trace của PE0, tức core số 0 trong
> cluster PULP. Trace bắt đầu khi PE0 được FC đánh thức. PE0 xác định core ID,
> thiết lập stack, đi vào chương trình cluster, đồng bộ bằng event/barrier,
> kiểm tra TCDM, thực hiện DMA và cuối cùng đi tới phase HWPE.

## 4. Ví dụ 1 — PE0 khởi động và xác định core ID

Đầu trace có các instruction:

```text
cycle 218543  PC=0x1c008080  jal    0, 96
cycle 218567  PC=0x1c0080e0  csrrs  a0, 0, mhartid
cycle 218592  PC=0x1c0080e4  andi   a1, a0, 31
cycle 218593  PC=0x1c0080e8  c.srli a0, a0, 5
cycle 218594  PC=0x1c0080ea  c.li   a2, 31
cycle 218595  PC=0x1c0080ec  beq    a0, a2, 8
```

Cách giải thích:

> Ở cycle 218543, PE0 bắt đầu chạy tại địa chỉ `0x1c008080`. Lệnh `jal`
> chuyển điều khiển tới hàm khởi tạo.
>
> Sau đó, lệnh `csrrs` đọc thanh ghi đặc biệt `mhartid`. Giá trị nhận được là
> `0`, cho biết core đang chạy là PE0.
>
> Lệnh `andi a1, a0, 31` lấy các bit thấp của `mhartid` để tách core ID. Kết
> quả `a1 = 0` tiếp tục xác nhận đây là core 0. Các lệnh tiếp theo kiểm tra
> cluster ID và chọn nhánh khởi tạo dành cho cluster core.

## 5. Ví dụ 2 — thiết lập stack riêng cho PE0

Đoạn tiếp theo:

```text
cycle 218624  auipc sp, 0xf3ff8000
cycle 218647  addi  sp, sp, 1996
cycle 218648  lw    sp, 0(sp)
cycle 218656  lui   gp, 0x1000
cycle 218672  addi  a1, a1, 1
cycle 218673  mul   ra, gp, a1
cycle 218675  add   sp, sp, ra
cycle 218677  jal   0, 7488
```

Cách giải thích:

> Sau khi xác định core ID, runtime thiết lập stack riêng cho PE0.
>
> Lệnh `lw sp, 0(sp)` đọc con trỏ stack từ physical address `0x10000860`.
> Giá trị nhận được là `sp = 0x10000868`.
>
> Chương trình sau đó cộng offset dựa trên core ID để mỗi PE có một vùng stack
> riêng. Cuối cùng, `jal` chuyển sang `cluster_entry_stub`, bắt đầu chạy phần
> ứng dụng trong cluster.

Dòng trace đầy đủ của lệnh load có dạng:

```text
lw sp, 0(sp)  sp=10000868  sp:10000860  PA:10000860
```

Các trường được đọc như sau:

- `sp:10000860`: giá trị đầu vào của `sp` là `0x10000860`;
- `sp=10000868`: sau khi thực hiện, `sp` nhận giá trị `0x10000868`;
- `PA:10000860`: địa chỉ vật lý được truy cập là `0x10000860`.

## 6. Ví dụ 3 — PE0 chờ event tại barrier

Điểm đáng chú ý nhất của trace:

```text
index       = 901
cycle       = 239321
PC          = 0x1c009f16
function    = evt_read32
instruction = p.elw a4, 28(a5)
a5          = 0x00204200
PA          = 0x0020421c
delta cycle = 16758
```

Cách giải thích:

> Tại hàm `evt_read32`, PE0 thực hiện lệnh `p.elw`, tức event load. Core truy
> cập thanh ghi event tại địa chỉ `0x0020421c`.
>
> Khoảng cách từ instruction retire trước tới instruction này là 16.758 cycle.
> Đây không phải PE0 mất 16.758 cycle để thực hiện một phép load thông thường.
> Nó cho thấy PE0 đang ngủ hoặc chờ event đồng bộ từ event unit.
>
> Khoảng chờ này chiếm gần 28% toàn bộ khoảng cycle của trace. Do đó,
> barrier/event synchronization là một thành phần lớn trong thời gian chạy quan
> sát được.

Đây là ví dụ tốt để cho thấy lợi ích của instruction trace. Output chương trình
chỉ cho biết barrier hoàn thành, trong khi trace cho biết core đã chờ ở đâu và
chờ bao lâu.

## 7. Ví dụ 4 — PE0 bắt đầu phase DMA

Khi vào phase DMA:

```text
index       = 4335
cycle       = 249673
function    = phase6_dma
PC          = 0x1c008668
instruction = lui a2, 0x1c000000
a2          = 0x1c000000
```

Cách giải thích:

> PE0 bắt đầu phase 6 bằng cách nạp địa chỉ nền `0x1c000000` vào `a2`. Đây là
> vùng L2 của PULP.
>
> Sau đó chương trình chuẩn bị buffer và descriptor DMA để truyền dữ liệu giữa
> L2 và vùng L1/TCDM tại `0x10000000`.
>
> Trong toàn bộ trace có 1.228 memory access tới L2 và 1.205 access tới
> L1/TCDM. Điều này phù hợp với workload kiểm tra truyền dữ liệu hai chiều.

Khi trace chuyển tới:

```text
function    = demo_dma_wait
instruction = c.swsp 0, 8(sp)
PA          = 0x10001820
```

có thể giải thích:

> Chương trình đã chuyển sang hàm chờ DMA. Lệnh trên cập nhật biến trạng thái
> trên stack của PE0 trong vùng L1/TCDM. Sau đó PE0 kiểm tra trạng thái DMA cho
> tới khi transfer hoàn thành.

## 8. Đoạn thuyết trình mẫu

Có thể sử dụng nguyên đoạn sau trong báo cáo hoặc thuyết trình:

> Trong thí nghiệm, tôi bật instruction trace cho PE0 của cluster PULP. Trace
> thu được 11.301 instruction, trải dài 60.101 cycle.
>
> Ban đầu, PE0 đọc `mhartid` và xác định core ID bằng 0. Runtime sau đó thiết
> lập stack riêng tại vùng `0x10000000` và chuyển điều khiển vào chương trình
> cluster.
>
> Ở phase barrier, PE0 thực hiện lệnh `p.elw` tại địa chỉ `0x1c009f16` để chờ
> event. Khoảng cách tới instruction trước là 16.758 cycle, cho thấy phần lớn
> thời gian ở đây là thời gian ngủ chờ đồng bộ, không phải thời gian tính toán.
>
> Sau barrier, PE0 thực hiện kiểm tra TCDM rồi cấu hình DMA giữa L2 tại
> `0x1c000000` và L1/TCDM tại `0x10000000`.
>
> Trace cuối cùng đi vào phase HWPE nhưng bị dừng bởi timeout. Vì vậy phần trước
> phase 7 có thể dùng để phân tích luồng phần mềm, nhưng không thể dùng trace này
> để kết luận HWPE đã hoạt động đúng.

## 9. Các kết quả định lượng chính

- Trace chứa 11.301 instruction và trải dài 60.101 cycle.
- Có 696 địa chỉ PC, 42 hàm và 60 opcode khác nhau.
- `p.elw` trong `evt_read32` có khoảng chờ lớn nhất: 16.758 cycle.
- Nhóm load/event chiếm 17,7% số instruction nhưng gần 50% tổng cycle-gap, chủ
  yếu do thời gian chờ event.
- Các hàm `printf` và chuỗi hàm con chiếm khoảng 26.220 cycle, tương đương
  43,6% toàn trace.
- Có 2.734 memory operation: 1.228 tới L2, 1.205 tới L1/TCDM, 269 tới vùng
  SoC/peripheral và 32 tới peripheral địa chỉ thấp.
- Riêng instruction trực tiếp trong `phase6_dma` đóng góp 12.876 cycle. Toàn
  khoảng phase 6, bao gồm các hàm con và phần in log, dài khoảng 24.312 cycle.

## 10. Giới hạn khi diễn giải

- `delta cycle` là khoảng cách giữa hai instruction retire. Nó có thể chứa
  latency, stall, thời gian sleep hoặc thời gian chờ event; không được coi trực
  tiếp là latency riêng của instruction hiện tại.
- `pe0.log` chỉ phản ánh PE0. Muốn kết luận về hoạt động song song của toàn
  cluster phải trace thêm PE1–PE7 và ghép các log theo timestamp/cycle.
- Instruction trace phù hợp để phân tích luồng phần mềm, register và memory
  access. Nó không thể hiện đầy đủ pipeline stage, AXI handshake hoặc tín hiệu
  RTL chi tiết.
- Phần `printf` chiếm tỷ lệ cycle lớn nên phải đặt ngoài vùng đo khi đánh giá
  hiệu năng kernel.
- Trace hiện tại kết thúc giữa `phase7_hwpe` do timeout an toàn. Dòng cuối bị
  thiếu operand, vì vậy không được coi phase 7 là đã hoàn tất.

## 11. Cách mở đúng các ví dụ trong viewer

Mở [`pe0_analyzer.html`](../../../report/gvsoc_20260928_live/pe0_analyzer.html),
sau đó sử dụng các nút:

- `Boot PE0`: xem quá trình khởi tạo core;
- `phase4_barrier`: xem phần đồng bộ barrier;
- `Longest wait`: mở trực tiếp lệnh `p.elw` chờ 16.758 cycle;
- `phase5_tcdm`: xem phần kiểm tra L1/TCDM;
- `phase6_dma`: xem lúc bắt đầu DMA;
- `phase7_hwpe`: xem điểm bắt đầu phase HWPE.

Có thể dùng script sau để tạo viewer tương tự cho một instruction trace khác:

```bash
sw/gvsoc/analyze/pe0_visualize.py path/to/pe0.log path/to/pe0_analyzer.html
```

