# Microarchitecture 11 — Cluster AXI crossbar và các bridge memory/peripheral

Phân tích bổ sung L3 ngày 2026-09-19. Bài M5 đã mô tả PE/cache/HCI/TCDM/MCHAN;
bài này đóng phần còn thiếu giữa các khối đó: ai là AXI initiator, decode đi
đâu, bridge nhớ owner thế nào, response quay lại bằng ID nào và busy giữ clock
ra sao.

Đây là phân tích **[RTL]** cho cấu hình hiệu lực. Arbitration latency và corner
case đồng thời chưa được waveform xác nhận nên nằm ở L4.

## 1. Hai hướng bus có độ rộng khác nhau

| Hướng | Data width tại biên domain | Đường chính |
|---|---:|---|
| Cluster → SoC (C2S) | 64 bit | core/DMA/cache miss → cluster xbar → external master → AXI CDC → SoC |
| SoC → Cluster (S2C) | 32 bit trước converter | SoC xbar → AXI CDC → 32→64 width converter → cluster xbar |

Top đặt `LOG_DEPTH=3`, tức mỗi AXI channel CDC có storage cơ sở 8 entry (phần
spill/ready đã phân tích ở M7). Ở S2C, `axi_dw_converter_intf` nằm **sau** CDC
phía cluster và upsize 32→64, với `AXI_MAX_READS=1`. Vì converter xử lý lane,
size và burst, không được giả định một request 32-bit luôn ánh xạ một-một vào
một beat 64-bit nội bộ, nhất là khi burst/cross-boundary.

Nguồn:
[pulp.sv](../../../../rtl/pulp/pulp.sv),
[pulp_cluster.sv](../../../../.bender/git/checkouts/pulp_cluster-48721e3ce381c984/rtl/pulp_cluster.sv).

## 2. Cluster crossbar: 4 initiator × 3 target

`cluster_bus_wrap` tạo bốn AXI slave ports theo nghĩa **initiator đi vào xbar**:

| Port | Signal integration | Producer |
|---:|---|---|
| 0 | `s_core_ext_bus` | PE/peripheral interconnect đi ra ngoài qua `per2axi` |
| 1 | `s_core_instr_bus` | shared instruction cache refill |
| 2 | `s_dma_ext_bus` | MCHAN external transfers |
| 3 | `s_data_slave_64` | SoC truy cập cluster sau CDC + width converter |

Ba AXI master ports theo nghĩa **target đi ra xbar**:

| Target | Khoảng địa chỉ, với `base=0x1000_0000+(cluster_id<<22)` | Consumer |
|---|---|---|
| 0 | `[base, base+TCDM_SIZE)` | `axi2mem` → 4 HCI ports → TCDM |
| 1 | `[base+0x0020_0000, base+0x0040_0000)` | `axi2per` → cluster peripheral bus |
| 2 | `[base+0x0040_0000, 0xffff_ffff)` | external AXI C2S → SoC |

Với cluster 0 và TCDM 64 KiB, khoảng sau TCDM đến `0x101f_ffff` không match
rule nào. Xbar tắt default master cho cả bốn input; địa chỉ không match được
xử lý ở decode-error path của AXI xbar, không bị âm thầm forward sang SoC.

Xbar có `NoSlvPorts=4`, `NoMstPorts=3`, no-latency mode. Output AXI ID rộng
thêm `$clog2(4)=2` bit để mang source port; response dùng phần route này quay
đúng initiator. Giới hạn transaction được đặt từ max(DMA outstanding, số core)
và tổng DMA+core, nhưng bridge đích có thể siết concurrency mạnh hơn.

Nguồn:
[cluster_bus_wrap.sv](../../../../.bender/git/checkouts/pulp_cluster-48721e3ce381c984/rtl/cluster_bus_wrap.sv),
[cluster_bus_defines.sv](../../../../rtl/includes/cluster_bus_defines.sv).

## 3. Đường vào TCDM: `axi2mem`

`axi2mem` nhận AXI 64-bit và tách mỗi beat thành hai lane 32-bit. Nó xuất bốn
TCDM/HCI ports:

- port 0–1: hai half read;
- port 2–3: hai half write.

Address/ID/last cho mỗi half có transaction FIFO sâu 2. Read data có hai FIFO
32-bit sâu 2 rồi được ghép thành RDATA 64-bit; write data/strobe 64-bit có FIFO
và được tách thành hai lane. Vì mỗi half có grant/response riêng, response AXI
chỉ được tạo khi dữ liệu/đồng bộ cần thiết của beat đã hội đủ; không được dùng
grant của một bank làm completion của toàn beat.

Write response được sinh sau đồng bộ completion của hai write-side paths;
read response mang ID/last đã lưu. AXI channel đầu vào còn có buffer depth 2,
trong khi address tracking ở read/write channel có FIFO sâu 4. Các tầng queue
này giải thích vì sao AW/AR accepted chưa có nghĩa request TCDM đã được grant.

`busy_o` đếm transaction từ AW handshake tới B handshake và từ AR handshake
tới handshake của R có `last`. Vì vậy bridge vẫn busy trong lúc response bị
AXI consumer backpressure, không chỉ lúc TCDM request đang assert.

Nguồn:
[axi2mem.sv](../../../../.bender/git/checkouts/axi2mem-e6a6085b4dfb755a/axi2mem.sv),
[axi2mem_tcdm_unit.sv](../../../../.bender/git/checkouts/axi2mem-e6a6085b4dfb755a/axi2mem_tcdm_unit.sv),
[axi2mem_trans_unit.sv](../../../../.bender/git/checkouts/axi2mem-e6a6085b4dfb755a/axi2mem_trans_unit.sv).

### Transaction mẫu: SoC đọc TCDM

```text
SoC AR32 accepted
 -> S2C CDC
 -> width converter tạo AR64/lane metadata
 -> xbar target TCDM
 -> axi2mem lưu AR/ID, phát hai request 32-bit cần thiết
 -> HCI arbitrate/bank response
 -> axi2mem ghép R64 + original widened ID
 -> width converter chọn R32
 -> CDC response
 -> SoC xbar trả đúng master
```

Mỗi mũi tên có thể stall độc lập; bảng không gán số chu kỳ cố định.

## 4. AXI → cluster peripheral: `axi2per`

Bridge này hạ AXI 64-bit thành một request peripheral 32-bit. Request FSM chỉ
có `TRANS_IDLE/TRANS_PENDING` và cho phép **một transaction đang chờ response**.

Priority và acceptance:

- nếu AR valid, read được xét trước write;
- write chỉ phát khi AW và W cùng valid ở đầu ra các buffer;
- request chỉ pop khỏi AXI buffer khi peripheral `gnt`;
- sau grant, bridge không nhận request mới cho đến `per_master_r_valid` và AXI
  R/B side có thể hoàn tất.

Address bit 2 chọn half thấp/cao của WDATA/WSTRB. Với read, peripheral data
32-bit được đặt vào half tương ứng của RDATA 64-bit. Bridge lưu type, AXI ID và
bit address 2 để tạo đúng R hoặc B response. `r_opc` từ peripheral hiện không
được chuyển thành AXI error: RRESP/BRESP bị buộc zero trong response channel;
đây là giới hạn error propagation cần nhớ.

Do serialization một-entry, giới hạn outstanding của crossbar không làm đường
peripheral thành multi-outstanding. Contention thật sự gồm arbitration tại xbar,
grant peripheral và backpressure R/B.

Nguồn:
[axi2per_req_channel.sv](../../../../.bender/git/checkouts/axi2per-73355017779c4307/axi2per_req_channel.sv),
[axi2per_res_channel.sv](../../../../.bender/git/checkouts/axi2per-73355017779c4307/axi2per_res_channel.sv).

## 5. Cluster peripheral/core → AXI: `per2axi`

`per2axi` làm hướng ngược: request 32-bit từ cluster peripheral interconnect
thành AXI single-beat 64-bit trên `s_core_ext_bus`. Quy ước bus nội bộ dùng
`wen=0` cho write, `wen=1` cho read.

- Write chỉ assert AWVALID và WVALID khi cả AWREADY và WREADY đã cao; data và
  strobe được đặt vào half theo address bit 2.
- Read chỉ assert ARVALID khi ARREADY cao.
- One-hot requester ID được encode thành AXI ID; response ID được decode lại
  one-hot để trả đúng PE/peripheral source.
- Response logic ưu tiên R nếu RVALID và BVALID đồng thời; nó hạ ready của
  channel còn lại trong lượt đó. Với read, bit address 2 đã lưu theo ID chọn
  lower/upper 32-bit từ RDATA.

Một quirk thấy trực tiếp trong source là:

```text
per_slave_gnt = aw_ready && ar_ready && w_ready
```

Grant của cả read lẫn write phụ thuộc **cả ba** ready, dù request chỉ dùng một
nhóm channel. Vì logic valid phía AXI lại chỉ cần channel liên quan, một channel
không liên quan có thể làm grant bus nội bộ bị trì hoãn hoặc tạo quan hệ ready
khó thấy. Đây chưa được gọi là lỗi chức năng nếu không có counterexample theo
giao thức, nhưng phải là một test contention/backpressure bắt buộc ở L4.

`busy_o` đếm AW→B và AR→last-R giống `axi2mem`, nên response pending giữ cluster
busy. Nguồn:
[per2axi_req_channel.sv](../../../../.bender/git/checkouts/per2axi-09e2f0897050514a/src/per2axi_req_channel.sv),
[per2axi_res_channel.sv](../../../../.bender/git/checkouts/per2axi-09e2f0897050514a/src/per2axi_res_channel.sv).

## 6. Response ownership và backpressure end-to-end

| Chặng | Thông tin ownership được giữ ở đâu | Completion ở chặng đó |
|---|---|---|
| Cluster xbar | AXI ID được mở rộng bằng source-port bits | R/B quay đúng input port |
| `axi2mem` | FIFO address/ID/last cho từng half | R-last hoặc B handshake |
| `axi2per` | một register type/ID/address-half | peripheral r_valid rồi AXI R/B |
| `per2axi` | AXI ID encode từ requester one-hot; address-half theo ID | AXI R/B rồi internal r_valid |
| CDC | FIFO riêng AW/W/B/AR/R | pop ở clock đích, không phải lúc push nguồn |
| Width converter | transaction/lane metadata, max one read | response thu hẹp về beat 32-bit |

Không có một tín hiệu `done` chung cho cả chuỗi. Ví dụ `per_master_gnt` chỉ cho
biết bridge đã nhận request, `per_master_r_valid` hoàn tất bus peripheral, còn
AXI R/B handshake mới cho phép giải phóng ownership ở phía initiator.

## 7. Clock gating/busy closure

Trong `pulp_cluster`, internal busy là OR của peripheral subsystem, `per2axi`,
`axi2per`, `axi2mem`, DMA và HWPE; sau đó OR với `core_busy[]` thành `busy_o`.
Vì ba bridge đếm accepted-but-not-returned transactions, một AXI request đang
chờ response giữ cluster khỏi bị xem là idle. CDC reset/in-flight caveat vẫn áp
dụng như M7: reset có thể xóa queue/ownership, không phải completion hợp lệ.

## 8. Kết luận L3 và checklist L4

L3 của cluster fabric đã đóng được topology, address rule, ID ownership,
serialization, lane conversion, response và busy propagation. Các phép đo/case
sau chuyển sang L4:

1. Bốn initiator cùng tranh một target, kiểm fairness/order theo AXI ID.
2. S2C read/write 8/16/32-bit, burst và crossing 64-bit boundary qua converter.
3. `axi2mem` hai half vào cùng/khác bank, grant lệch nhau, R/B backpressure.
4. `axi2per` read-vs-write priority và AW/W đến lệch nhau.
5. `per2axi` giữ thấp từng AWREADY/ARREADY/WREADY để định lượng quirk grant.
6. Decode gap/unmapped và peripheral `r_opc`, kiểm response lỗi thực sự quan sát
   được ở mỗi initiator.
7. Clock-gate/reset khi transaction đang nằm trong bridge hoặc CDC.

Revision nguồn đã đọc: `pulp_cluster 040fc3e3b2db`, `axi2mem 6973e0434d26`,
`axi2per a99ef2fac9f3`, `per2axi 892fcad60b63`.
