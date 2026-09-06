# Chuyên sâu 02 — SoC domain và Fabric Controller

## 1. Ranh giới đã kiểm chứng

[`rtl/pulp/soc_domain.sv`](../../rtl/pulp/soc_domain.sv) là wrapper gần như hoàn toàn combinational quanh instance `pulp_soc_i`. Wrapper truyền tham số kiến trúc và dùng `.*` để nối các cổng đồng tên. Chỉ có hai kết nối explicit ở cuối:

- `boot_l2_i = 1'b0`;
- `cluster_dbg_irq_valid_o -> dbg_irq_valid_o`.

Vì source implementation `pulp_soc` chưa có trong checkout, FC pipeline, L2 interconnect, uDMA và peripheral internals không thể được kiểm chứng sâu hơn từ local source. Tuy nhiên interface cho biết rõ trách nhiệm của khối.

## 2. Các nhóm khối con logic của `pulp_soc`

Từ cổng wrapper và hierarchy testbench, `pulp_soc` phải cung cấp các nhóm chức năng sau:

| Nhóm | Bằng chứng interface | Chức năng |
|---|---|---|
| Clock/reset | `ref_clk_i`, `slow_clk_i`, `cluster_clk_o`, `cluster_rstn_o` | tạo/phân phối clock và reset SoC/Cluster |
| FC boot | `bootsel_i`, `fc_fetch_en_*`, `boot_l2_i` | chọn nguồn boot và cho phép FC fetch |
| Debug | JTAG pins, `cluster_dbg_irq_valid_o` | TAP/DMI/debug FC và core Cluster |
| SoC memory/interconnect | AXI async slave/master | nhận truy cập từ Cluster và phát truy cập sang Cluster |
| Peripheral/uDMA | UART, SPI, I2C, I2S, camera, SDIO, HyperBus | giao tiếp ngoại vi và chuyển dữ liệu |
| Cluster control/status | busy, event, DMA/perf handshakes, power/bypass/control outputs | phối hợp FC–Cluster |
| Pad config | `pad_cfg_o`, `pad_mux_o`, GPIO config | software-visible pad/GPIO control |

Testbench truy cập hierarchy `pulp_soc_i.soc_peripherals_i.s_stdout_bus`, xác nhận có ít nhất submodule `soc_peripherals_i` và một APB-like stdout slave trong simulation.

## 3. Boot của FC

Ở `pulp.sv`, `fc_fetch_en_valid_i=1` và `fc_fetch_en_i=1`; vì vậy platform top luôn yêu cầu FC bắt đầu fetch ngay sau reset. Nguồn boot cụ thể vẫn do `bootsel_i` và boot ROM quyết định.

`boot_l2_i` bị wrapper buộc `0`, nên không có đường ngoài để ép chế độ boot-L2 qua cổng này. JTAG boot vẫn hoạt động bằng cách để FC vào boot ROM/wait, halt hart qua debug module, ghi DPC tới entry point trong L2, nạp image rồi resume.

## 4. Memory map local

[`rtl/includes/soc_mem_map.svh`](../../rtl/includes/soc_mem_map.svh) định nghĩa:

| Vùng | Khoảng địa chỉ (end exclusive theo cách khai báo) | Ý nghĩa |
|---|---:|---|
| FC private bank 0 | `0x1C00_0000–0x1C00_8000` | L2/private bank đầu |
| FC private bank 1 | `0x1C00_8000–0x1C01_0000` | chứa entry mặc định TB `0x1C00_8080` |
| L2/TCDM SoC region | `0x1C01_0000–0x1C09_0000` | 512 KiB |
| Alias | `0x0000_0000–0x0010_0000` | alias theo `FC_ALIAS`/configuration |
| Boot ROM | `0x1A00_0000–0x1A04_0000` | reset/boot code |
| AXI plug/Cluster window | `0x1000_0000–0x1040_0000` | cửa sổ sang Cluster |
| Peripheral | `0x1A10_0000–0x1A40_0000` | SoC peripherals |

Kích thước thực tế và decode chi tiết phải xác nhận trong dependency `pulp_soc`; file header chỉ là contract address ở top repository.

## 5. Clock/reset và Cluster control

SoC nhận reset toàn cục đã qua safe domain (`rstn_glob_i`) và xuất clock/reset riêng cho Cluster. Nó cũng xuất `cluster_rtc_o`, `cluster_fetch_enable_o`, `cluster_boot_addr_o`, `cluster_test_en_o`, `cluster_pow_o`, `cluster_byp_o`.

Điểm cần đặc biệt lưu ý: trong top hiện tại, chỉ `cluster_clk` và `cluster_rstn` được cluster wrapper tiêu thụ. Các signal RTC/fetch/boot/test/power/bypass được khai báo hoặc nối ra từ SoC nhưng không đi vào `cluster_domain_i`. Không nên dùng sự thay đổi của chúng làm bằng chứng rằng core Cluster đã fetch.

## 6. Interrupt/event paths

- SoC ghi event vào async event FIFO; Cluster đọc bằng `wptr/rptr/data`.
- Cluster trả `busy_o` về SoC.
- `dbg_irq_valid_o[NB_CORES-1:0]` đi từ debug logic SoC sang Cluster.
- DMA PE event có valid từ Cluster và ack từ SoC.
- Trong `pulp.sv`, `dma_pe_irq_valid_i` và `pf_evt_valid_i` phía SoC bị buộc `'0`, dù Cluster vẫn tạo các output tương ứng. Hai return path này vì thế bị vô hiệu hóa tại integration top hiện tại.

## 7. Điểm quan sát khi debug

Ưu tiên theo chuỗi: reset toàn cục → clock/reset SoC → FC PC/fetch → AXI/APB request → peripheral response. Với Cluster: kiểm tra `s_cluster_clk`, `s_cluster_rstn`, AXI/event pointer movement và `s_cluster_busy`; không dựa riêng vào `s_cluster_fetch_enable`.

