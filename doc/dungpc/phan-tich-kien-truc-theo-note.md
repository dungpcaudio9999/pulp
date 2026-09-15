# Phân tích kiến trúc PULP theo phương pháp trong `noteforanalysis.md`

Tài liệu này áp dụng đúng quy trình đã đề ra: Bước 0 → 5 lớp → 10 transaction → 6 câu hỏi.
Khác biệt so với các deep-dive trước: mọi con số ở đây đọc từ RTL đã checkout trong
`.bender/git/checkouts/`, không suy từ sơ đồ. Chỗ nào chưa xác minh được thì ghi rõ là chưa.

Revision đang phân tích: `pulp_soc-c519334bd3ac5582`, `pulp_cluster-48721e3ce381c984`.

---

## Cảnh báo đặt trước: sơ đồ đang dùng KHÔNG khớp RTL của repo này

Đây là kết luận quan trọng nhất, và nó phải nằm trước mọi thứ khác, vì nếu không thì
cả 5 lớp phía dưới sẽ được đọc bằng một bản đồ sai.

Sơ đồ khối trong ảnh là sơ đồ PULP/PULPissimo "kinh điển": một `SoC BUS` đứng giữa, một
`APB BUS` treo bên trái, `L2 MEMORY` là một khối liền. RTL trong repo này là bản
`soc_interconnect` viết lại năm 2020 (Manuel Eggimann, `pulp_soc/rtl/pulp_soc/soc_interconnect.sv`),
có cấu trúc khác hẳn:

| Sơ đồ nói | RTL thật |
|---|---|
| Một `SoC BUS` duy nhất | 3 tầng: L2 demux (mỗi master một cái) → 3 crossbar song song |
| `L2 MEMORY` một khối | 4 bank interleaved + 2 bank private + boot ROM, **ba crossbar khác nhau** |
| SoC BUS nối thẳng APB BUS | 4 chặng đổi protocol: lint → AXI → AXI-Lite → APB → apb_node |
| Bridge là `axi2per`/`per2axi`/`axi2mem`/`apb2per` | Những IP đó trong revision này **chỉ nằm trong cluster** |

Điểm cuối cần nhấn mạnh vì chính `noteforanalysis.md` (Lớp 2) đã viết *"Liệt kê hết bridge
ra — đó chính là axi2per, per2axi, axi2mem, apb2per"*. Kiểm chứng:

```
$ grep -rln "axi2per\|per2axi" .bender/git/checkouts/*/rtl/
.bender/git/checkouts/pulp_cluster-.../rtl/axi2per_wrap.sv
.bender/git/checkouts/pulp_cluster-.../rtl/per2axi_wrap.sv
.bender/git/checkouts/pulp_cluster-.../rtl/pulp_cluster.sv
```

Không có hit nào trong `pulp_soc`. Bốn IP đó là bridge **của cluster**, không phải của SoC.
Dùng sơ đồ cũ để đi tìm chúng trong `pulp_soc` sẽ mất thời gian vô ích.

Sơ đồ vẫn dùng được, nhưng chỉ ở mức "có những khối gì" — không dùng được ở mức "nối với
nhau ra sao".

---

## Bước 0 — Trả lời 5 câu hỏi sơ đồ không nói

### 1. Address decoding: decode ở đâu, dải nào

Decode xảy ra ở **ba chỗ nối tiếp nhau**, không phải một chỗ:

1. `tcdm_demux` (`soc_interconnect.sv:100`) — mỗi master port có một instance riêng, chia
   3 hướng theo `L2_DEMUX_RULES`: private+ROM → port 1, interleaved TCDM → port 2, còn lại
   → port 0 (AXI).
2. `contiguous_crossbar` — decode tiếp trong nhánh port 1 để tách bank0 / bank1 / ROM.
3. `axi_xbar` — decode trong nhánh port 0 để tách cluster plug / APB peripherals.

Rồi trong nhánh APB còn một tầng nữa là `apb_node` (11 slave).
Nhánh interleaved thì **không decode theo dải** mà theo bit địa chỉ (xem Lớp 2).

Nguồn dải địa chỉ: [rtl/includes/soc_mem_map.svh](../../rtl/includes/soc_mem_map.svh) và
[rtl/includes/periph_bus_defines.sv](../../rtl/includes/periph_bus_defines.sv).

### 2. Chính sách phân xử

| Nơi | Chính sách | Bằng chứng |
|---|---|---|
| Interleaved xbar (L2) | round-robin, **một arbiter mỗi bank** | `interleaved_crossbar.sv:100` dùng `xbar` với `rr_i='0`, `ExtPrio=0` → `rr_arb_tree` |
| Contiguous xbar | round-robin (cùng IP `xbar`) | `contiguous_crossbar.sv` |
| Cluster TCDM (HCI log interco) | round-robin, flag chỉ cập nhật khi được grant | `cluster_interconnect/rtl/low_latency_interco/ArbitrationTree.sv:32-34` |
| AXI xbar (SoC & cluster) | round-robin của `axi_xbar` (pulp-platform/axi) | `axi_xbar_intf` |

Ai thắng khi đụng: round-robin, nên không có master nào bị đói vĩnh viễn. Nhưng vì arbiter
là **per-bank**, hai master đụng nhau chỉ khi trúng **cùng một bank**, không phải khi trúng
cùng vùng địa chỉ.

### 3. Outstanding transaction và backpressure

Đây là chỗ note đoán đúng là "sơ đồ không nói", và câu trả lời khá bất ngờ:

```systemverilog
// soc_interconnect.sv:271
MaxMstTrans: 1,   // "The TCDM ports do not support outstanding transactions anyways"
MaxSlvTrans: 4,
```

Nghĩa là **phía SoC gần như không có outstanding**. Toàn bộ master của AXI xbar trong SoC
đều xuất phát từ `lint2axi_wrap`, mà giao thức TCDM/lint là request–grant–response 1 chu kỳ,
không pipeline được. Trong khi cluster thì khác:

```systemverilog
// cluster_bus_wrap.sv:125
MaxSlvTrans: DMA_NB_OUTSND_BURSTS + NB_CORES,   // = 8 + 8 = 16
```

Backpressure: ở lớp TCDM là `gnt` bị hạ (kèm quy tắc cứng trong comment của
`soc_interconnect.sv:158`: *"EVERY SLAVE IS EXPECTED TO HAVE CONSTANT LATENCY OF 1 CYCLE.
Asserting grant without asserting r_valid in the next cycle results in undefined behavior"*).
Ở lớp AXI là `ready` theo chuẩn. Ở biên clock là FIFO đầy (`cdc_fifo_gray`).

Hệ quả thực tế đáng nhớ: băng thông cluster→L2 **không** đến từ outstanding mà đến từ
song song hoá — một cổng AXI 64-bit được `axi64_2_lint32_wrap` xẻ thành **4 cổng lint 32-bit**
chạy đồng thời (`soc_interconnect_wrap.sv:69`).

### 4. Mạng event/interrupt

Xem Lớp 4. Tóm tắt: 17 event từ peripheral → `soc_event_generator` → rẽ 3 hướng
(FC / cluster / peripheral), FC nhận qua `apb_interrupt_cntrl`, cluster nhận qua
`cdc_fifo_gray` 8 entry × 8 bit.

### 5. Trục thời gian

Xem Lớp 5.

---

## Lớp 1 — Địa chỉ

### 1.1 Memory map, góc nhìn FC

| Dải | Kích thước | Target | Đi qua |
|---|---:|---|---|
| `0x0000_0000 – 0x0010_0000` | 1 MiB | alias của `0x1C0x_xxxx` | **chỉ cổng FC data**, xem cảnh báo dưới |
| `0x1000_0000 – 0x1040_0000` | 4 MiB | Cluster (TCDM + periph cluster) | L2 demux p0 → axi_xbar → AXI S→C → CDC |
| `0x1A00_0000 – 0x1A04_0000` | 256 KiB | Boot ROM | L2 demux p1 → contiguous xbar |
| `0x1A10_0000 – 0x1A40_0000` | 3 MiB | APB peripherals | L2 demux p0 → axi_xbar → AXI-Lite → APB |
| `0x1C00_0000 – 0x1C00_8000` | 32 KiB | L2 private bank0 | L2 demux p1 → contiguous xbar |
| `0x1C00_8000 – 0x1C01_0000` | 32 KiB | L2 private bank1 | L2 demux p1 → contiguous xbar |
| `0x1C01_0000 – 0x1C09_0000` | 512 KiB | L2 interleaved (4 bank) | L2 demux p2 → interleaved xbar |
| còn lại | — | `0xBADACCE5` | `tcdm_error_slave` |

Tổng L2 = 64 KiB private + 512 KiB interleaved = 576 KiB
(`NB_L2_CHANNELS=4`, `L2_BANK_SIZE=32768` word 32-bit → 4 × 128 KiB).

**Bẫy đáng ghi lại:** cái alias `0x000` → `0x1C0` chỉ tồn tại trên **cổng data của FC**,
không có trên cổng instruction:

```systemverilog
// soc_interconnect_wrap.sv:129-133
always_comb begin
    tcdm_fc_data_addr_remapped.add = tcdm_fc_data.add;
    if (tcdm_fc_data.add[31:20] == 12'h000)
        tcdm_fc_data_addr_remapped.add[31:20] = 12'h1c0;
end
...
`TCDM_ASSIGN_INTF(master_ports[0], tcdm_fc_data_addr_remapped)  // data: đã remap
`TCDM_ASSIGN_INTF(master_ports[1], tcdm_fc_instr)               // instr: KHÔNG remap
```

Nên nạp dữ liệu vào `0x0000_1000` thì đọc được, nhưng **nhảy** tới `0x0000_1000` để thực thi
thì fetch đi thẳng vào error slave. Đây đúng là loại chi tiết mà note gọi là "chỗ tôi đoán sai".

### 1.2 Memory map, góc nhìn một cluster core

Note nói đây là "hai bản đồ khác nhau" — đúng, và khác nhiều hơn dự đoán. Core trong cluster
không đi qua address decoder theo dải, mà qua `core_demux` decode bằng
**12 bit cao** (`core_demux.sv:141-143`, với `CLUSTER_ID=0`):

| `add[31:20]` | Dải | Hướng | Độ trễ |
|---|---|---|---|
| `0x100` | `0x1000_0000+` | TCDM read/write → HCI log interco | 1 chu kỳ |
| `0x101` | `0x1010_0000+` | TCDM test-and-set (đọc kèm set bit) | 1 chu kỳ |
| `0x102` | `0x1020_0000+` | DEMUX periph: event unit, mchan | thấp, bỏ qua cluster bus |
| còn lại | mọi thứ khác | cổng PE → peripheral interco → cluster bus → AXI → SoC | cao, qua CDC |

Trong nhánh `0x102`, `data_add_int[14]` tách tiếp event unit và DMA (`core_demux.sv:231`).

Điểm then chốt về hiệu năng: **event unit và DMA của cluster nằm trên đường DEMUX, không nằm
trên cluster bus.** Nghĩa là core nói chuyện với event unit và trigger DMA mà không đụng AXI,
không qua CDC. Đó chính là lý do barrier và DMA-trigger trong PULP rẻ tới mức dùng được
ở vòng lặp trong. Sơ đồ khối vẽ DMA và event unit như hai khối treo trên bus, làm mất hẳn
thông tin này.

Phía sau, `cluster_bus_wrap.sv:100-120` decode lần nữa cho các master của cluster bus:

```
cluster_base = 0x1000_0000 + (cluster_id << 22)
  [base, base+TCDM_SIZE)          -> tcdm_master   (AXI vào TCDM, cho SoC/debug)
  [base+0x0020_0000, +0x0040_0000)-> periph_master
  [base+0x0040_0000, 0xFFFF_FFFF] -> ext_master    (ra SoC)
```

### 1.3 Ma trận master–slave (SoC interconnect)

9 master port + 4 HWPE port. Slave: 4 bank interleaved, 2 bank private, ROM, cluster, APB.

| Master | idx | L2 intlv | L2 priv | ROM | Cluster | APB |
|---|---|:-:|:-:|:-:|:-:|:-:|
| FC data (có alias) | 0 | ✓ | ✓ | ✓ | ✓ | ✓ |
| FC instr | 1 | ✓ | ✓ | ✓ | ✓ | ✓ |
| uDMA TX | 2 | ✓ | ✓ | ✓ | ✓ | ✓ |
| uDMA RX | 3 | ✓ | ✓ | ✓ | ✓ | ✓ |
| Debug (lint_jtag) | 4 | ✓ | ✓ | ✓ | ✓ | ✓ |
| Cluster AXI 64b → lint ×4 | 5–8 | ✓ | ✓ | ✓ | ✓ | ✓ |
| HWPE ×4 | intlv-only | ✓ | ✗ | ✗ | ✗ | ✗ |

Ô trống có ý nghĩa, đúng như note nói. Ở đây chỉ có một hàng trống — HWPE — và nó trống
**do thiết kế cố ý**, có hẳn phần cứng chặn:

```systemverilog
// soc_interconnect.sv:131-147
// Master interleaved-only đi ra ngoài vùng interleaved -> tcdm_error_slave -> 0xBADACCE5
```

Hai quan sát về những ô **không** trống mà lẽ ra ta hay tưởng là trống:

- Cluster có đường tới **APB peripherals**. Cluster core đọc/ghi được thanh ghi SoC, không
  bắt buộc phải nhờ FC.
- Cluster có đường tới **cluster plug** (`0x1000_0000`). Về mặt topology đây là vòng
  cluster → SoC → cluster. Đường này tồn tại vì crossbar nối đầy đủ, nhưng
  `cluster_bus_wrap` đã route vùng đó về `tcdm_master` nội bộ từ trước, nên bình thường
  không ai đi vòng. Đáng ghi chú là *có thể* đi, không phải *nên* đi.

---

## Lớp 2 — Giao thức & băng thông

### 2.1 Bảng protocol thật

| Đoạn | Protocol | Rộng | Lớp độ trễ |
|---|---|---:|---|
| FC ↔ soc_interconnect | TCDM/lint (`XBAR_TCDM_BUS`) | 32 | 1 chu kỳ cứng |
| uDMA ↔ soc_interconnect | TCDM/lint | 32 | 1 chu kỳ |
| soc_interconnect ↔ L2 bank | TCDM/lint | 32 | 1 chu kỳ cứng |
| soc_interconnect → cluster | AXI4 | 32 | pipelined, qua CDC |
| cluster → soc_interconnect | AXI4 | 64 | pipelined, qua CDC |
| soc_interconnect → peripherals | AXI4 → AXI4-Lite → APB | 32 | nhiều chu kỳ |
| Core cluster ↔ TCDM | HCI | 32 | 1 chu kỳ |
| HWPE ↔ TCDM | HCI rộng | 4×32 = 128 | 1 chu kỳ |
| Cluster bus | AXI4 | 64 | pipelined |

### 2.2 Danh sách bridge — bản đúng

Chuỗi SoC → APB (đọc từ `soc_interconnect.sv` và `soc_interconnect_wrap.sv:160-260`):

```
FC data (lint 32)
  -> tcdm_demux                     [decode]
  -> lint2axi_wrap                  [BRIDGE 1: lint -> AXI4 32b]
  -> axi_xbar                       [decode, round-robin]
  -> axi_to_axi_lite_intf           [BRIDGE 2: AXI4 -> AXI4-Lite]
  -> axi_lite_to_apb_intf           [BRIDGE 3: AXI4-Lite -> APB]
  -> apb_node_wrap                  [decode 11 slave]
  -> apb_gpio / apb_soc_ctrl / udma / ...
```

Ba lần đổi protocol cho một lần ghi thanh ghi GPIO. Đây là lý do vì sao trong PULP, ghi
một thanh ghi peripheral đắt hơn hẳn ghi một word vào L2 — và vì sao vòng lặp nóng không
bao giờ nên đụng APB.

Chuỗi cluster → SoC:

```
core cluster -> core_demux -> peripheral interco -> per2axi_wrap  [BRIDGE, cluster]
  -> cluster_bus (axi_xbar 64b) -> ext_master
  -> axi_cdc_src                                   [CDC, clock cluster -> soc]
  -> axi_cdc_dst (trong pulp_soc)
  -> axi64_2_lint32_wrap                           [BRIDGE: 1 AXI 64 -> 4 lint 32]
  -> 4 tcdm_demux -> interleaved xbar -> 4 L2 bank
```

Chiều ngược (SoC → cluster): `lint2axi` → `axi_xbar` → `axi_cdc_src` → `axi_cdc_dst` →
`cluster_bus` → `axi2mem_wrap` (vào TCDM) hoặc `axi2per_wrap` (vào cluster periph).

### 2.3 Nút thắt băng thông

Note nói lớp này đáng đầu tư nhất. Bốn nút thắt đọc được từ RTL:

1. **Cổng AXI cluster→SoC 64-bit** là điểm hẹp duy nhất cho toàn bộ 8 core + DMA khi đụng L2.
   Được giảm nhẹ bằng cách xẻ 4 lint port, nhưng vẫn là một cổng.
2. **`MaxMstTrans: 1`** ở AXI xbar SoC — mọi truy cập L2 từ FC là blocking round-trip.
3. **4 bank L2 interleaved** so với **16 bank TCDM cluster**. Xác suất bank conflict ở L2
   cao hơn hẳn: 9 master tranh 4 bank, trong khi 16 requester tranh 16 bank ở cluster.
4. **Đường APB** — 3 bridge nối tiếp, mỗi lần truy cập nhiều chu kỳ.

Interleaving của L2: chọn bank bằng **2 bit ngay trên bit byte-offset**:

```systemverilog
// interleaved_crossbar.sv:95
assign port_sel[i] = master_ports[i].add[$clog2(BE_WIDTH)+PORT_SEL_WIDTH-1 : $clog2(BE_WIDTH)];
//  với BE_WIDTH=4, NR_SLAVE_PORTS=4  ->  add[3:2]
```

Nghĩa là word liên tiếp rơi vào bank liên tiếp. Truy cập tuần tự trải đều; truy cập
stride 4 word (16 byte) thì **toàn bộ dồn vào một bank** — đây là failure mode cần nhớ.
Ở cluster, `NB_TCDM_BANKS=16` nên bit chọn bank là `add[5:2]`, stride gây conflict là 64 byte.

---

## Lớp 3 — Miền vật lý

### 3.1 Đếm FLL → đếm clock domain

`soc_clk_rst_gen.sv` có đúng **3 FLL**, mỗi cái có APB slave riêng để cấu hình:

| FLL | Clock ra | Cấp cho |
|---|---|---|
| `i_fll_soc` | `clk_soc_o` | FC, soc_interconnect, L2, debug |
| `i_fll_per` | `clk_per_o` | uDMA và peripheral |
| `i_fll_cluster` | `clk_cluster_o` | toàn bộ cluster |

Reset: `rstn_soc_sync_o` và `rstn_cluster_sync_o` — hai reset đã đồng bộ riêng.
Ngoài ra còn `ref_clk` (32 kHz, cho RTC) và `test_clk`, `sel_fll_clk_i` để bypass FLL khi
test/FPGA (trên FPGA các FLL bị thay bằng clock source khác — xem
[zcu102-to-zcu104-gap.md](zcu102-to-zcu104-gap.md)).

### 3.2 Điểm CDC — danh sách đầy đủ

Note hỏi "mỗi tín hiệu qua biên được đồng bộ bằng cách gì". Trả lời, đúng 3 điểm:

| # | Biên | Cơ chế | Vị trí |
|---|---|---|---|
| 1 | Cluster → SoC, AXI 64b | `axi_cdc_src` / `axi_cdc_dst` (gray-code FIFO cho cả 5 channel) | `pulp_cluster.sv:1410` ↔ `pulp_soc.sv:448` |
| 2 | SoC → Cluster, AXI 32b | `axi_cdc_src` / `axi_cdc_dst` | `pulp_soc.sv:509` ↔ `pulp_cluster.sv:1459` |
| 3 | SoC → Cluster, event | `cdc_fifo_gray_src` / `cdc_fifo_gray_dst`, 8 entry × 8 bit | `pulp_soc.sv:719` ↔ `pulp_cluster.sv:1505` |

Cả ba đều là **dual-clock gray FIFO**, không phải 2-FF synchronizer. Hợp lý: đây là các
kênh có data, và gray pointer cho phép truyền cả bó dữ liệu chỉ với một pointer cần đồng bộ.
Payload ở top được pack thành vector phẳng nên `pulp.sv` phải tự tính width — hai đầu bắt
buộc dùng cùng công thức (đã ghi trong deep_dive_03).

Các tín hiệu điều khiển lẻ qua biên (`dbg_irq_valid`, `busy`, `fetch_en`) thì đi
handshake valid/ack hoặc được coi là quasi-static.

### 3.3 Power

Cluster power-gate được: `pulp.sv` có chuỗi điều khiển qua `apb_soc_ctrl` (`pw_*`,
`cluster_rstn`, `cluster_clk_en`). Trình tự bật/tắt và isolation cell nằm ở
`safe_domain.sv` + `apb_soc_ctrl.sv`. Đây là phần tôi **chưa xác minh đủ sâu** để khẳng định
thứ tự chính xác — cần đọc `apb_soc_ctrl.sv` phần `r_pwr` và mô phỏng lại. Ghi nhận là
việc chưa xong, không đoán.

---

## Lớp 4 — Điều khiển & sự kiện

Note nói đúng: lớp này gần như vắng mặt trên sơ đồ, và nó mới là trọng tâm của PULP.

### 4.1 Cấu trúc

```
17 event nguồn từ peripheral (per_events_i)
        |
   soc_event_generator  (APB slave @ 0x1A10_6000, EVNT_WIDTH=8)
        |
   soc_event_arbiter --> soc_event_queue (QUEUE_SIZE=2)
        |
   +----+----------------+------------------+
   |                     |                  |
fc_event_*          cl_event_*         pr_event_*
   |                     |                  |
apb_interrupt_cntrl   cdc_fifo_gray      peripheral
(FC EU)               (8 entry, 8 bit)
   |                     |
FC core irq_i        cluster event unit
```

### 4.2 Bản đồ 32 event của FC

Đọc từ `soc_peripherals.sv:220-248`:

| Bit | Nguồn |
|---|---|
| 0–7 | dành cho SW event |
| 8 | `dma_pe_evt_i` — cluster DMA xong |
| 9 | `dma_pe_irq_i` |
| 10, 11 | timer lo / hi |
| 12 | `pf_evt_i` (prefetch) |
| 14 | ref clock rise/fall (RTC) |
| 15 | GPIO |
| 17–20 | advanced timer 0–3 |
| 26 | **dành cho SoC event FIFO — nhưng đang gán `1'b0`** |
| 29 | FC error event |
| 30, 31 | FC high-priority event |

Bit 26 là chỗ đáng chú ý: comment nói `RESERVED for soc event FIFO` nhưng RTL gán cứng 0.
Cần xác minh trong mô phỏng xem đường event peripheral→FC đi bằng lối nào khác
(`fc_event_valid_o` vào thẳng `apb_interrupt_cntrl` qua `event_fifo_*`, không qua
`fc_events_o`). Đây là ứng viên tốt cho một transaction story.

### 4.3 Mô hình "CPU ngủ, event đánh thức"

Bằng chứng cụ thể trong RTL cho luận điểm của note:

- `event_unit_flex` có `hw_barrier_unit.sv`, `hw_dispatch.sv`, `hw_mutex_unit.sv` — barrier,
  dispatch và mutex là **phần cứng**, không phải vòng lặp phần mềm.
- Event unit nằm ở vùng `0x102` của `core_demux` → core truy cập nó **không qua cluster bus**.
- FC dùng `apb_interrupt_cntrl` với `event_fifo_*`: event được xếp hàng, core có thể ngủ
  giữa chừng mà không mất event.

Ba dữ kiện này cùng nói một điều: chi phí "ngủ rồi bị đánh thức" được thiết kế để rẻ hơn
chi phí "thức và polling". Đó là câu trả lời cho câu hỏi tại sao PULP ultra-low-power, và
nó nằm ở lớp 4 chứ không ở lớp 1–2.

---

## Lớp 5 — Vòng đời

```
POR
 -> rstn_glob, 3 FLL khởi động (hoặc bypass nếu sel_fll_clk=0)
 -> rstn_soc_sync nhả
 -> FC fetch tại r_bootaddr = 0x1A00_0080        <-- apb_soc_ctrl.sv:177 (reset value)
      = BOOT_ROM_START (0x1A00_0000) + 0x80
 -> boot ROM code đọc pad_bootsel[1:0]           <-- pulp.sv:508, 672, 1012
 -> chọn nguồn boot (JTAG / SPI flash / preload...)
 -> nạp chương trình vào L2
 -> FC chạy main
 -> [khi cần cluster]
      FC ghi apb_soc_ctrl: power on, clock en, nhả cluster reset
      FC ghi boot addr cho từng core cluster qua AXI S->C
      FC ghi fetch_enable_reg                    <-- pulp_cluster.sv:550
        (KHÔNG phải cổng fetch_en_i, cổng đó bị buộc 1'b0 ở top —
         xem deep_dive_03 mục 5, đã xác minh bằng mô phỏng 2026-09-06)
 -> 8 core chạy, dùng barrier phần cứng ở event unit
 -> cluster xong -> event -> FC
 -> FC tắt clock/power cluster
```

---

## Phương pháp 2 — 10 transaction story

Quy ước của note: Lần 1 = dự đoán trên sơ đồ, Lần 2 = xác minh trong RTL, Lần 3 = waveform.
Dưới đây **Lần 1 và Lần 2 đã làm xong**. Lần 3 chưa — cần chạy mô phỏng và đó là việc tiếp theo.

### 1. FC nạp lệnh đầu tiên sau reset

```
FC fetch @0x1A00_0080
 -> tcdm_fc_instr (master_ports[1], KHÔNG remap)
 -> tcdm_demux: khớp rule BOOT_ROM -> port 1
 -> contiguous_crossbar: rule idx 2 -> boot_rom_slave
 -> boot_rom.sv
```
Dự đoán sai ở Lần 1: tôi tưởng ROM nằm sau cùng một bus với L2. Thực tế ROM và 2 bank
private dùng chung `contiguous_crossbar`, còn L2 interleaved là crossbar **khác**.

### 2. FC ghi một thanh ghi GPIO

```
FC store @0x1A10_1000
 -> tcdm_fc_data -> remap không áp dụng (prefix 0x1A1)
 -> tcdm_demux: không khớp rule nào -> port 0 (default)
 -> lint2axi_wrap -> axi_xbar (rule idx 1: PERIPHERALS)
 -> axi_to_axi_lite -> axi_lite_to_apb -> apb_node (slave 1: GPIO)
 -> apb_gpio
```
Sai ở Lần 1: tôi đếm 1 bridge, thực tế 3.

### 3. Một byte UART vào → uDMA ghi thẳng vào L2

```
pad -> udma_uart RX -> udma_core channel
 -> tcdm_udma_rx (master_ports[3])
 -> tcdm_demux: khớp TCDM rule -> port 2
 -> interleaved_crossbar: bank = add[3:2]
 -> l2_interleaved_slaves[bank]
```
CPU không tham gia. uDMA chạy ở `clk_per`, nhưng cổng lint của nó vào interconnect ở
`clk_soc` — điểm này **cần kiểm tra lại**: hoặc uDMA có CDC nội bộ, hoặc cổng TCDM của
nó chạy `clk_soc`. Chưa xác minh, đánh dấu là câu hỏi mở.

### 4. FC bật cluster

Chuỗi thanh ghi trong `apb_soc_ctrl` (@0x1A10_4000): power → clock enable → reset release →
boot addr per-core → fetch enable. Thứ tự chính xác và tên field **chưa xác minh** —
cần đọc `apb_soc_ctrl.sv` phần `r_pwr`/`r_cl_*` và đối chiếu `pulp-runtime/kernel/cluster.c`.

### 5. FC giao việc cho cluster

Đã xác minh trong deep_dive_03: `plp_ctrl_core_bootaddr_set_remote()` rồi
`eoc_fetch_enable_remote()` (`pulp-runtime/kernel/cluster.c:62-95`), đường đi là
FC → axi_xbar → AXI S→C → CDC → cluster_bus → axi2per → cluster peripherals → `fetch_enable_reg`.

### 6. Cluster DMA kéo một tile L2 → TCDM

```
core ghi lệnh DMA @0x102xxxxx -> core_demux -> DEMUX periph (add[14]) -> mchan
mchan phát 2 luồng:
  - tcdm_master (s_hci_dma) -> HCI interco -> 16 bank TCDM   [ghi đích]
  - ext_master (s_dma_ext_bus) -> cluster_bus -> ext_master
      -> axi_cdc_src -> axi_cdc_dst -> axi64_2_lint32
      -> 4 lint port -> 4 tcdm_demux -> interleaved xbar -> L2  [đọc nguồn]
```
Chỗ học được: DMA có thể có tới 8 burst outstanding trên cluster bus
(`DMA_NB_OUTSND_BURSTS=8`) nhưng phía SoC `MaxMstTrans=1`. Điểm nghẽn nằm ở biên SoC,
không nằm ở DMA.

### 7. 8 core cùng đọc TCDM trong một chu kỳ

16 bank, arbiter round-robin **riêng cho từng bank**. Nếu 8 core trúng 8 bank khác nhau:
tất cả được grant cùng chu kỳ. Nếu 2 core trúng cùng bank: 1 thắng, 1 bị hạ `gnt` và
core đó stall (không có buffer, `CORE_DEMUX` giữ request). Bank = `add[5:2]`.

### 8. I$ miss của một core → refill qua AXI

Đi qua `hier-icache` (private mode, 8 bank, 4-way, 4096). Đường ra: `instr_slave` của
`cluster_bus` → `ext_master` → CDC → SoC → L2. **Chưa trace chi tiết trong RTL** —
`hier_icache` có thêm một tầng L1.5 dùng chung mà tôi chưa đọc.

### 9. Barrier

`hw_barrier_unit.sv` trong `event_unit_flex`. Core ghi vào barrier register qua vùng
`0x102` (DEMUX, không qua bus), rồi thực thi lệnh sleep. Core cuối cùng chạm barrier
khiến unit phát event đánh thức cả nhóm. **Chưa đọc chi tiết FSM** của `hw_barrier_unit`.

### 10. Cluster xong việc → event → FC

`dma_pe_evt_i` → `fc_events_o[8]`, hoặc `dma_pe_irq_i` → `fc_events_o[9]`
(`soc_peripherals.sv:221-222`) → `apb_interrupt_cntrl` → `core_irq_req`/`core_irq_id` →
FC core (`fc_subsystem.sv:172-173`).

---

## Phương pháp 3 — 6 câu hỏi, áp cho 3 khối then chốt

### `soc_interconnect`

1. **Master/slave?** Cả hai — slave với 9+4 master port, master với L2/ROM/AXI slave.
2. **Protocol?** TCDM/lint ở cả hai phía trừ nhánh AXI; AXI4 32-bit ra cluster và peripheral.
3. **Cấu hình bằng gì?** **Không có thanh ghi nào.** Toàn bộ address map là `localparam`
   compile-time (`soc_interconnect_wrap.sv:96-115`). Muốn đổi memory map phải sửa
   `soc_mem_map.svh` và re-synthesize.
4. **Báo cáo bằng gì?** Không có interrupt. Lỗi báo bằng **data**: `0xBADACCE5` kèm `r_opc`.
5. **Clock domain?** `clk_soc`, không tắt được.
6. **Xóa đi thì gì hỏng?** Tất cả. Đây là khối duy nhất nối FC với bộ nhớ của chính nó.
   Không có đường vòng nào.

### `event_unit_flex` (cluster)

1. Slave thuần, từ phía core.
2. `XBAR_PERIPH_BUS` qua DEMUX (không phải AXI).
3. Thanh ghi ở vùng `0x102xxxxx`, core cluster ghi trực tiếp.
4. Báo bằng event → đánh thức core đang sleep.
5. `clk_cluster`, tắt cùng cluster.
6. **Xóa đi thì gì hỏng?** Đồng bộ hoá giữa 8 core phải chuyển sang spinlock trên TCDM.
   Vẫn chạy được, nhưng core không ngủ được nữa → mất toàn bộ lợi thế công suất.
   Đây là ví dụ rõ nhất cho ý của note: câu 6 mới lộ ra vai trò thật.

### `axi64_2_lint32_wrap`

1. Slave phía AXI, master phía lint.
2. AXI4 64-bit → 4 × TCDM 32-bit.
3. Không cấu hình được, thuần combinational/pipeline.
4. Không báo cáo gì.
5. `clk_soc` (nằm sau `axi_cdc_dst`).
6. **Xóa đi thì gì hỏng?** Cluster mất hoàn toàn đường tới L2 → mọi offload chết. Và nếu
   thay bằng bridge 64→1×32 thì băng thông cluster→L2 tụt 4 lần. Khối này chính là
   câu trả lời cho "làm sao 1 cổng AXI nuôi nổi 8 core".

---

## Bốn sản phẩm của note — tình trạng

| Sản phẩm | Tình trạng |
|---|---|
| Memory map 1 trang, 2 góc nhìn | ✅ Lớp 1.1 và 1.2 |
| Ma trận master–slave | ✅ Lớp 1.3 |
| Sơ đồ clock/power/reset + CDC | 🟡 clock và CDC xong (Lớp 3.1, 3.2); power sequence chưa |
| 10 transaction story + waveform | 🟡 Lần 1 + Lần 2 xong cho 10/10; Lần 3 (waveform) chưa làm |

---

## Sổ "những chỗ tôi đoán sai"

Note nói tập ghi chú này có giá trị hơn toàn bộ phần đọc suôn sẻ. Đây là mục đó.

1. **Sơ đồ đang dùng là của một revision khác.** `soc_interconnect` đã được viết lại năm
   2020 thành kiến trúc 3 tầng. Sơ đồ một-bus là sai về topology.
2. **`axi2per`/`per2axi`/`axi2mem`/`apb2per` không nằm trong SoC.** Chúng là bridge của
   cluster. Note đã ghi sai chỗ này ở Lớp 2.
3. **Alias `0x000` chỉ có trên cổng data của FC**, không có trên cổng instruction.
4. **Đường FC → APB có 3 bridge**, không phải 1.
5. **Event unit và DMA của cluster không nằm trên cluster bus** mà trên đường DEMUX riêng.
   Sơ đồ vẽ chúng như khối treo trên bus, làm mất đặc điểm quan trọng nhất của chúng.
6. **`MaxMstTrans: 1` ở SoC** — tôi đã đoán PULP có outstanding sâu ở phía SoC. Không có.
   Băng thông đến từ song song hoá (4 lint port), không từ pipelining.
7. **L2 chỉ có 4 bank interleaved, trong khi TCDM cluster có 16.** Tôi đã đoán hai bên
   tương đương. Chênh 4 lần, và điều đó đổi hẳn cách nghĩ về bank conflict ở L2.
8. **`fc_events_o[26]` được comment là SoC event FIFO nhưng gán cứng `1'b0`.**
   Chưa biết đường thật đi lối nào.

## Câu hỏi mở, cần mô phỏng để trả lời

- uDMA chạy `clk_per`, cổng TCDM vào interconnect ở `clk_soc` — CDC ở đâu?
- Trình tự thanh ghi chính xác khi FC bật cluster (`apb_soc_ctrl`).
- `hier_icache` tầng L1.5 dùng chung: refill đi qua đâu.
- FSM của `hw_barrier_unit`.
- Đường event peripheral → FC thật sự đi lối nào nếu bit 26 bị gán 0.
