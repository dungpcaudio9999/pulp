# Kiến trúc, bản đồ mã nguồn PULP và quan hệ với ZCU104

## 1. Phạm vi và baseline

Tài liệu này mô tả cấu trúc của hệ thống PULP trong repository hiện tại, cách SoC/FC giao tiếp với Cluster, vị trí top-level RTL và testbench, đồng thời giải thích vai trò của board ZCU104.

Baseline khi khảo sát:

- Repository: `pulp`
- Branch: `feature/dungpc-work`
- Commit: `b6ae54700b76395b049742ebfc52c5aaf6e148a5`
- Tài liệu kiến trúc local: [`doc/datasheet.pdf`](../datasheet.pdf)
- Manifest dependency: [`Bender.yml`](../../Bender.yml)
- Dependency lock: [`Bender.lock`](../../Bender.lock)

> **Trạng thái dependency:** tại thời điểm viết, các repository dependency chưa được checkout vào working tree. Vì vậy các đường dẫn của `pulp_soc` và `pulp_cluster` bên dưới là đường dẫn bên trong repository nguồn; đường dẫn cache vật lý trên máy cần được xác nhận lại từ `sim/compile.tcl` sau khi chạy `make checkout` và `make scripts`.

## 2. Các domain của PULP

Ở mức tích hợp cao nhất, module `pulp` chia thiết kế thành ba domain chính: `safe_domain`, `soc_domain` và `cluster_domain`. `pad_frame` nằm ở biên I/O của chip nhưng không phải một domain xử lý độc lập.

```text
Pads / external interfaces
          |
     +----v-----+
     | pad_frame|
     +----+-----+
          |
 +--------v---------+
 |    safe_domain   |  reset, slow/reference clock, pad mux/control
 +--------+---------+
          |
 +--------v---------+       asynchronous AXI, events and control
 |     soc_domain   |<--------------------------------------------+
 | +--------------+ |                                             |
 | |   pulp_soc   | |                                             |
 | | FC, L2, uDMA | |                                             |
 | | peripherals | |                                             |
 | +--------------+ |                                             |
 +--------+---------+                                             |
          |                                                       |
          +--------------------------------------------+----------+
                                                       |
                                              +--------v---------+
                                              |  cluster_domain  |
                                              | +--------------+ |
                                              | | pulp_cluster | |
                                              | | 8 cores, L1  | |
                                              | | DMA, event   | |
                                              | +--------------+ |
                                              +------------------+
```

### 2.1. `safe_domain`

Module [`safe_domain`](../../rtl/pulp/safe_domain.sv) được instantiate thành `safe_domain_i` trong [`pulp.sv`](../../rtl/pulp/pulp.sv#L737). Domain này nằm giữa pad-level I/O và logic hệ thống, đảm nhiệm các chức năng luôn cần thiết để hệ thống có thể khởi động và giao tiếp:

- nhận reference clock và reset ngoài;
- tạo hoặc phân phối slow clock, reset và các tín hiệu test/DFT;
- điều khiển pad mux và pad configuration;
- chuyển tiếp tín hiệu GPIO, UART, SPI, I2C, I2S, camera, SDIO và HyperBus giữa pad frame và SoC.

### 2.2. `soc_domain`

Module [`soc_domain`](../../rtl/pulp/soc_domain.sv) được instantiate thành `soc_domain_i` trong [`pulp.sv`](../../rtl/pulp/pulp.sv#L972). Đây là wrapper local của `pulp_soc`, chứa hoặc kết nối:

- Fabric Controller (FC), là core điều khiển chính;
- bộ nhớ L2 và SoC interconnect;
- uDMA và các peripheral của SoC;
- JTAG/debug;
- logic clock/reset cho SoC và Cluster;
- các cổng AXI, event và control nối sang Cluster.

Implementation `pulp_soc` được instantiate thành `pulp_soc_i` tại [`soc_domain.sv`](../../rtl/pulp/soc_domain.sv#L212).

### 2.3. `cluster_domain`

Module [`cluster_domain`](../../rtl/pulp/cluster_domain.sv) được instantiate thành `cluster_domain_i` trong [`pulp.sv`](../../rtl/pulp/pulp.sv#L1156). Đây là wrapper local của compute cluster. Cấu hình hiện tại cho thấy:

- 8 core, từ macro `NB_CORES` trong [`pulp_soc_defines.sv`](../../rtl/includes/pulp_soc_defines.sv#L92);
- TCDM/L1 dung lượng `64 KiB`;
- 16 TCDM banks;
- L2 address-space parameter `512 KiB` được truyền cho Cluster;
- 4 DMA ports;
- shared instruction cache;
- boot address mặc định `0x1C000000`.

Implementation `pulp_cluster` được instantiate thành `cluster_i` tại [`cluster_domain.sv`](../../rtl/pulp/cluster_domain.sv#L209).

## 3. Giao tiếp giữa SoC/FC và Cluster

FC không nối trực tiếp tới từng core trong Cluster. Việc điều khiển và trao đổi dữ liệu đi qua logic trong `pulp_soc`, các interface bất đồng bộ ở top-level, rồi tới `pulp_cluster`. Cách tổ chức này cho phép SoC và Cluster chạy ở các clock domain khác nhau.

### 3.1. Hai hướng AXI bất đồng bộ

Top-level tạo hai nhóm bus AXI độc lập. Mỗi kênh AXI (`AW`, `W`, `B`, `AR`, `R`) được biểu diễn bằng vùng data cùng read/write pointer, tức dạng giao tiếp CDC/FIFO bất đồng bộ.

| Hướng | Tên tín hiệu ở `pulp.sv` | Ý nghĩa chính |
|---|---|---|
| Cluster → SoC | `s_cluster_soc_bus_*` | Cluster core/DMA truy cập L2, peripheral hoặc address space phía SoC |
| SoC → Cluster | `s_soc_cluster_bus_*` | FC/debug hoặc SoC master truy cập TCDM/peripheral/address space phía Cluster |

Ở phía `soc_domain_i`:

- `s_cluster_soc_bus_*` nối vào các cổng `async_data_slave_*` vì SoC nhận request từ Cluster;
- `s_soc_cluster_bus_*` nối ra các cổng `async_data_master_*` vì SoC phát request sang Cluster.

Ở phía `cluster_domain_i`, vai trò được đảo tương ứng:

- `s_cluster_soc_bus_*` nối ra `async_data_master_*`;
- `s_soc_cluster_bus_*` nối vào `async_data_slave_*`.

Các kết nối SoC nằm tại [`pulp.sv`](../../rtl/pulp/pulp.sv#L1106), còn các kết nối Cluster nằm tại [`pulp.sv`](../../rtl/pulp/pulp.sv#L1237).

### 3.2. Event, interrupt và handshake

Ngoài AXI data path, hai domain còn trao đổi:

- event bất đồng bộ qua `s_event_wptr`, `s_event_rptr` và `s_event_dataasync`;
- trạng thái `s_cluster_busy` từ Cluster về SoC;
- interrupt/debug qua `s_cluster_irq` và `s_dbg_irq_valid`;
- handshake DMA/performance-event qua các tín hiệu `s_dma_pe_*` và `s_pf_evt_*`.

Event path đi từ các cổng `async_cluster_events_*` của `soc_domain_i` tới các cổng cùng tên của `cluster_domain_i`.

### 3.3. Clock, reset, boot và khởi chạy Cluster

`soc_domain` xuất các tín hiệu điều khiển Cluster:

- `s_cluster_clk`;
- `s_cluster_rstn`;
- `s_cluster_fetch_enable`;
- `s_cluster_boot_addr`;
- `s_cluster_test_en`.

Các tín hiệu này được đưa vào `cluster_domain_i`. Vì vậy, về mặt luồng điều khiển, FC/SoC có thể cấu hình boot address, bật clock/reset và cho phép các core Cluster bắt đầu fetch. Cluster báo trạng thái bận và các event hoàn thành về SoC.

Luồng offload tổng quát là:

```text
FC chuẩn bị dữ liệu/chương trình trong L2
        |
        v
FC cấu hình boot address và trạng thái Cluster
        |
        v
SoC cấp clock/reset, bật cluster_fetch_enable
        |
        v
Cluster core chạy; DMA di chuyển dữ liệu L2 <-> TCDM
        |
        v
Cluster phát event/interrupt hoặc cập nhật trạng thái hoàn thành
        |
        v
FC tiếp tục xử lý kết quả
```

## 4. Vị trí top-level RTL và code thật của SoC/Cluster

### 4.1. Cây phân cấp chính

```text
Simulation top: rtl/tb/tb_pulp.sv::tb_pulp
└── DUT: rtl/pulp/pulp.sv::pulp
    ├── rtl/pulp/pad_frame.sv::pad_frame
    ├── rtl/pulp/safe_domain.sv::safe_domain
    ├── rtl/pulp/soc_domain.sv::soc_domain
    │   └── pulp_soc/rtl/pulp_soc/pulp_soc.sv::pulp_soc
    └── rtl/pulp/cluster_domain.sv::cluster_domain
        └── pulp_cluster/rtl/pulp_cluster.sv::pulp_cluster

FPGA top: fpga/pulp-zcu102/rtl/xilinx_pulp.v::xilinx_pulp
└── DUT: rtl/pulp/pulp.sv::pulp
```

### 4.2. Bản đồ repository và file

| Lớp | Repository | Module | File |
|---|---|---|---|
| Platform top | `pulp` | `pulp` | [`rtl/pulp/pulp.sv`](../../rtl/pulp/pulp.sv) |
| Pad boundary | `pulp` | `pad_frame` | [`rtl/pulp/pad_frame.sv`](../../rtl/pulp/pad_frame.sv) |
| Safe-domain wrapper | `pulp` | `safe_domain` | [`rtl/pulp/safe_domain.sv`](../../rtl/pulp/safe_domain.sv) |
| SoC wrapper | `pulp` | `soc_domain` | [`rtl/pulp/soc_domain.sv`](../../rtl/pulp/soc_domain.sv) |
| SoC implementation | `pulp_soc` | `pulp_soc` | `rtl/pulp_soc/pulp_soc.sv` trong repository `pulp-platform/pulp_soc` |
| FC implementation | `pulp_soc` | `fc_subsystem` | `rtl/fc/fc_subsystem.sv` trong repository `pulp-platform/pulp_soc` |
| SoC peripheral block | `pulp_soc` | `soc_peripherals` | `rtl/pulp_soc/soc_peripherals.sv` trong repository `pulp-platform/pulp_soc` |
| Cluster wrapper | `pulp` | `cluster_domain` | [`rtl/pulp/cluster_domain.sv`](../../rtl/pulp/cluster_domain.sv) |
| Cluster implementation | `pulp_cluster` | `pulp_cluster` | `rtl/pulp_cluster.sv` trong repository `pulp-platform/pulp_cluster` |
| Simulation top | `pulp` | `tb_pulp` | [`rtl/tb/tb_pulp.sv`](../../rtl/tb/tb_pulp.sv) |
| ZCU102 FPGA top | `pulp` | `xilinx_pulp` | [`fpga/pulp-zcu102/rtl/xilinx_pulp.v`](../../fpga/pulp-zcu102/rtl/xilinx_pulp.v) |

Nguồn upstream:

- [`pulp-platform/pulp_soc`](https://github.com/pulp-platform/pulp_soc)
- [`pulp-platform/pulp_cluster`](https://github.com/pulp-platform/pulp_cluster)

### 4.3. Phiên bản dependency cần chú ý

[`Bender.yml`](../../Bender.yml#L16) khai báo:

- `pulp_soc` theo version constraint `~3.0.0`;
- `pulp_cluster` theo commit yêu cầu `db2e173b8b7562092fb9d922d64e0a7bd21da411`.

Trong khi đó, [`Bender.lock`](../../Bender.lock#L258) hiện khóa:

- `pulp_soc`: version `3.0.1`, revision `d878151e0e40912642c5275d470cef76258f5fc6`;
- `pulp_cluster`: revision `040fc3e3b2dbf11ce0d08bf7554f310c483b8c9f`.

Do manifest và lock hiện không thể hiện cùng revision trực tiếp cho `pulp_cluster`, cần coi `Bender.lock` là baseline tái lập của checkout hiện tại và không tự ý chạy `bender update`. Sau checkout, phải xác nhận revision cùng danh sách file thực sự được compile:

```bash
source setup/vsim.sh
make checkout
make scripts
rg -n "pulp_soc|pulp_cluster" sim/compile.tcl
```

Nếu quyết định cập nhật lock để khớp manifest, đó phải là một thay đổi dependency riêng, có lý do, commit riêng và được build/regression lại.

## 5. Testbench instantiate DUT như thế nào

Simulation top là module `tb_pulp` trong [`rtl/tb/tb_pulp.sv`](../../rtl/tb/tb_pulp.sv#L30). DUT được instantiate theo cấu trúc:

```systemverilog
pulp #(
  .CORE_TYPE_FC (CORE_TYPE_FC),
  .CORE_TYPE_CL (CORE_TYPE_CL),
  .USE_FPU      (RISCY_FPU),
  .USE_HWPE     (USE_HWPE),
  .USE_HWPE_CL  (USE_HWPE_CL)
) i_dut (
  // Kết nối các pad tới wire/model của testbench
  // SPI, UART, camera, SDIO, I2C, I2S, GPIO, HyperBus,
  // reset, JTAG, reference clock và boot select
);
```

Instantiation bắt đầu tại [`tb_pulp.sv`](../../rtl/tb/tb_pulp.sv#L690), instance DUT có tên `i_dut`.

Các thành phần quan trọng quanh DUT:

- `tb_clk_gen` tạo reference clock cho `pad_xtal_in`;
- reset testbench được nối vào `pad_reset_n`;
- `SimJTAG` tạo các tín hiệu JTAG mô phỏng;
- parameter `LOAD_L2`, mặc định là `"JTAG"`, chọn cách nạp chương trình;
- các VIP/model đại diện cho UART, SPI flash, camera, I2C/I2S và external memory tùy cấu hình;
- biến `exit_status` lưu kết quả để simulator trả mã thành công/thất bại.

Testbench hỗ trợ ba cách vận hành chính, được mô tả thêm trong [`rtl/tb/README.md`](../../rtl/tb/README.md):

1. `LOAD_L2="JTAG"`: nạp chương trình vào L2 qua JTAG rồi chạy;
2. `LOAD_L2="STANDALONE"`: boot từ flash/model ngoại vi;
3. bật OpenOCD/remote bitbang để debugger ngoài điều khiển DUT.

Testbench còn truy cập theo hierarchy `i_dut.soc_domain_i.pulp_soc_i...` để kết nối filesystem/stdout model. Điều này xác nhận trực tiếp cây instance:

```text
tb_pulp.i_dut
└── soc_domain_i
    └── pulp_soc_i
        └── soc_peripherals_i
```

## 6. ZCU104 liên quan gì đến thiết kế

ZCU104 không phải một khối bên trong kiến trúc PULP. Nó là nền tảng FPGA dùng để hiện thực phần RTL PULP trong Programmable Logic của Zynq UltraScale+ MPSoC. Thiết kế RTL lõi `pulp` về cơ bản độc lập với board; lớp phụ thuộc board nằm ở FPGA wrapper, device/board settings, IP tạo clock và file constraint.

Repository hiện chỉ có target ZCU102 và VCU118, thể hiện trong [`fpga/README.md`](../../fpga/README.md) và [`fpga/Makefile`](../../fpga/Makefile). Với ZCU102, chuỗi tích hợp là:

```text
ZCU102 pins/connectors
        |
        v
fpga/pulp-zcu102/rtl/xilinx_pulp.v
        |
        v
rtl/pulp/pulp.sv
```

Wrapper [`xilinx_pulp.v`](../../fpga/pulp-zcu102/rtl/xilinx_pulp.v) thực hiện ba việc chính:

- nhận differential reference clock qua primitive `IBUFGDS`;
- ghép reset/JTAG và map UART/FMC signals;
- instantiate `pulp` thành instance `i_pulp`.

ZCU104 dùng thiết bị Zynq UltraScale+ MPSoC `XCZU7EV-2FFVC1156`, theo [AMD ZCU104 Board User Guide UG1267](https://docs.amd.com/v/u/en-US/ug1267-zcu104-eval-bd). Target hiện tại lại được cấu hình riêng cho ZCU102:

- part `xczu9eg-ffvb1156-2-e`;
- board part `xilinx.com:zcu102:part0:3.2`;
- các giá trị này nằm trong [`fpga-settings.mk`](../../fpga/pulp-zcu102/fpga-settings.mk).

## 7. Vì sao không thể dùng nguyên trạng port ZCU102 cho ZCU104

Có thể tái sử dụng RTL `pulp` và phần lớn cấu trúc wrapper, nhưng không thể dùng nguyên trạng target ZCU102 vì các thành phần sau gắn chặt với board:

| Thành phần | ZCU102 hiện tại | Vấn đề khi dùng trên ZCU104 |
|---|---|---|
| FPGA device | `xczu9eg-ffvb1156-2-e` | ZCU104 dùng ZU7EV; chọn sai part làm project/synthesis target sai thiết bị |
| Vivado board part | `xilinx.com:zcu102:part0:3.2` | Board automation và interface metadata không phù hợp ZCU104 |
| Pin mapping | Các `PACKAGE_PIN` trong `zcu102.xdc` | Package pin/connectivity tới clock, UART, JTAG và FMC không được giả định giống nhau |
| I/O standard | `LVDS_25`, `LVCMOS33`, `LVCMOS18` theo từng pin/bank | Phải kiểm tra lại bank voltage và connector của ZCU104 để tránh lỗi DRC hoặc rủi ro phần cứng |
| Clock | `ref_clk_p/n` được map và constraint riêng cho ZCU102 | Clock source, pin và constraint phải được xác nhận theo UG1267/schematic ZCU104 |
| Reset/JTAG/UART | Pin cố định trong `zcu102.xdc` | Vị trí, polarity, connector và cable path cần map lại |
| FMC peripherals | QSPI, SDIO, camera, I2S, I2C và HyperBus map tới các FMC pin cụ thể | Routing FMC và mezzanine connection cần được lập lại cho ZCU104 |
| Timing/CDC | Constraint chứa nhiều hierarchical path và clock groups | Phải chạy lại elaboration, timing và CDC trên device/clock topology mới |
| Clock IP | Xilinx Clocking Wizard được sinh theo target board/settings | IP cần được regenerate cho part và tần số mục tiêu mới |

Đặc biệt, [`zcu102.xdc`](../../fpga/pulp-zcu102/constraints/zcu102.xdc) gán trực tiếp package pin cho reference clock, reset, JTAG, UART và toàn bộ tín hiệu FMC. Đưa file này vào project ZCU104 có thể gây lỗi package pin, sai I/O bank hoặc ánh xạ tín hiệu tới chân không kết nối đúng ngoại vi.

Target ZCU104 đúng nên được tách riêng, ví dụ:

```text
fpga/pulp-zcu104/
├── fpga-settings.mk
├── rtl/xilinx_pulp.v
└── constraints/zcu104.xdc
```

Trình tự port an toàn là chỉ đưa clock, reset, JTAG và UART lên trước; sau khi elaboration, synthesis và timing đạt yêu cầu mới thêm các interface FMC/HyperBus khác.

## 8. Kết luận

- PULP top-level gồm `safe_domain`, `soc_domain` và `cluster_domain`, với `pad_frame` làm biên I/O.
- `soc_domain` chứa wrapper của `pulp_soc`; FC nằm trong `pulp_soc`.
- `cluster_domain` chứa wrapper của `pulp_cluster` với cấu hình hiện tại là 8 core và TCDM 64 KiB.
- SoC và Cluster trao đổi dữ liệu hai chiều bằng các kênh AXI bất đồng bộ, đồng thời có event, interrupt, DMA handshake và các tín hiệu quản lý clock/reset/boot riêng.
- Top-level chung là `rtl/pulp/pulp.sv`; simulation top là `rtl/tb/tb_pulp.sv`; FPGA top cho ZCU102 là `fpga/pulp-zcu102/rtl/xilinx_pulp.v`.
- Code implementation thật của SoC và Cluster nằm trong hai repository dependency `pulp_soc` và `pulp_cluster`, không nằm đầy đủ trong checkout top-level hiện tại.
- ZCU104 là FPGA implementation target, không thay đổi kiến trúc logic PULP nhưng bắt buộc phải có board settings, wrapper review, clock IP và XDC riêng thay cho target ZCU102.

## 9. Nguồn đối chiếu

- [`README.md`](../../README.md)
- [`Bender.yml`](../../Bender.yml)
- [`Bender.lock`](../../Bender.lock)
- [`doc/datasheet.pdf`](../datasheet.pdf)
- [`rtl/pulp/pulp.sv`](../../rtl/pulp/pulp.sv)
- [`rtl/pulp/soc_domain.sv`](../../rtl/pulp/soc_domain.sv)
- [`rtl/pulp/cluster_domain.sv`](../../rtl/pulp/cluster_domain.sv)
- [`rtl/tb/tb_pulp.sv`](../../rtl/tb/tb_pulp.sv)
- [`fpga/pulp-zcu102/rtl/xilinx_pulp.v`](../../fpga/pulp-zcu102/rtl/xilinx_pulp.v)
- [`fpga/pulp-zcu102/constraints/zcu102.xdc`](../../fpga/pulp-zcu102/constraints/zcu102.xdc)
- [AMD ZCU104 Board User Guide UG1267](https://docs.amd.com/v/u/en-US/ug1267-zcu104-eval-bd)
- [PULP SoC repository](https://github.com/pulp-platform/pulp_soc)
- [PULP Cluster repository](https://github.com/pulp-platform/pulp_cluster)
