# Kế hoạch phân tích toàn bộ RTL và xây dựng đặc tả IP cho PULP SoC

## 1. Mục tiêu

Mục tiêu của kế hoạch này là reverse-engineer toàn bộ RTL của PULP SoC theo chuỗi:

```text
RTL inventory
  -> elaborated hierarchy
  -> phân tích từng file/module
  -> kiến trúc từng IP
  -> đặc tả hành vi độc lập với implementation
  -> verification plan
  -> nền tảng để tự phát triển hoặc thay thế IP
```

Sau khi hoàn thành, mỗi IP phải có hai loại tài liệu:

1. **Implementation analysis**
   - RTL hiện tại làm gì.
   - Hierarchy và thuật toán đang dùng.
   - FSM, pipeline, arbitration và buffering.
   - Các assumption, giới hạn và hành vi phụ thuộc implementation.

2. **Clean behavioral specification**
   - Định nghĩa IP từ góc nhìn bên ngoài.
   - Không phụ thuộc cách code của implementation hiện tại.
   - Đủ thông tin để viết lại RTL tương thích.
   - Có verification plan chứng minh implementation mới đáp ứng đặc tả.

Phạm vi compile list hiện tại ước tính khoảng:

- 725 file RTL/header đối với cấu hình simulation.
- 720 file RTL/header đối với cấu hình FPGA.
- Khoảng 50 package/IP phụ thuộc.

Các con số trên bao gồm RTL phần cứng, implementation thay thế, thư viện dùng chung, primitive công nghệ và verification-only code. Không phải tất cả cùng xuất hiện trong một elaborated design.

---

## 2. Cấu trúc tài liệu đề xuất

```text
doc/rtl_spec/
├── 00_scope/
│   ├── source_baseline.md
│   ├── configurations.md
│   ├── rtl_inventory.csv
│   ├── module_index.md
│   └── analysis_status.md
│
├── 01_processing_system/
├── 02_memory/
├── 03_interconnect/
├── 04_udma_peripherals/
├── 05_cluster_control/
├── 06_hwpe/
├── 07_clock_reset_power/
├── 08_boot_debug/
├── 09_pad_io/
├── 10_verification_platform/
│
├── 11_system_scenarios/
├── 12_clean_specs/
├── diagrams/
└── verification_plans/
```

Tài liệu hiện có trong `doc/dungpc/deepdive` và `doc/dungpc/master_analysis` được dùng làm dữ liệu đầu vào. Mọi kết luận cuối cùng phải trace được về RTL, manifest hoặc kết quả elaboration.

---

## 3. Bước 0: Khóa baseline và cấu hình

### 3.1. Chọn các cấu hình chuẩn

Ít nhất phải duy trì bốn cấu hình:

| ID | Mục đích | Cấu hình chính |
|---|---|---|
| `CFG-SIM-BASE` | Simulation mặc định | RI5CY, FPU bật, HWPE tắt |
| `CFG-FULL-SYSTEM` | Demo full-system hiện dùng | 1 FC + 8 PE, cluster HWPE bật |
| `CFG-MAX` | Bao phủ phần cứng tùy chọn | SoC HWPE và cluster HWPE bật |
| `CFG-FPGA` | Biến thể FPGA | FPGA clock, ROM, memory wrapper và constraint |

### 3.2. Ghi lại baseline

`source_baseline.md` phải chứa:

- Git commit của root repository.
- Commit của từng checkout trong `.bender/git/checkouts`.
- Toàn bộ local modification liên quan.
- Phiên bản Bender, simulator, compiler và công cụ lint/elaboration.
- Defines và target dùng để tạo file list.
- Hash của compile list.
- Ngày tạo baseline.

### 3.3. Sinh compile list cho từng cấu hình

Ví dụ:

```bash
./bender script flist -t simulation -t vsim --relative-path
./bender script flist -t fpga -t xilinx --relative-path
```

Mỗi file trong `rtl_inventory.csv` phải có tối thiểu các trường:

```text
file
package
language
defines_required
configuration
synthesizable
verification_only
declared_modules_packages_interfaces
instantiated_in_active_design
analysis_level
owner
status
notes
```

### 3.4. Ba mức phân tích

Không bỏ sót file, nhưng áp dụng chiều sâu phù hợp:

- **L3 - Full specification:** mọi module nằm trong elaborated SoC và ảnh hưởng hành vi hệ thống.
- **L2 - Reusable support IP:** FIFO, arbiter, CDC, bridge, SRAM wrapper và generic interconnect.
- **L1 - Catalog:** primitive công nghệ, assertion helper, package/type, VIP hoặc implementation không được chọn.

Điều kiện hoàn thành bước 0: mọi file trong compile list có đúng một record trong inventory và được gán configuration cùng analysis level.

---

## 4. Quy trình phân tích chuẩn cho mỗi file RTL

Với từng file/module:

1. Xác định vai trò, package sở hữu và parent instantiate module.
2. Liệt kê parameter, localparam, macro và generate condition.
3. Phân loại toàn bộ port:
   - Clock/reset.
   - Control/status.
   - Request/response.
   - Data.
   - Event/interrupt.
   - Test/debug.
4. Xác định protocol và chiều master/slave.
5. Xác định register, memory, state và FIFO.
6. Vẽ FSM và datapath.
7. Phân tích reset value, clock enable và isolation.
8. Xác định latency, throughput và backpressure.
9. Liệt kê corner case và error behavior.
10. Trace tới register map, interrupt map hoặc memory map.
11. Viết assertion dự kiến.
12. Viết test tối thiểu tái hiện hành vi.
13. Đưa module vào diagram của parent.
14. Viết clean spec không phụ thuộc tên signal nội bộ.

Mẫu tài liệu cho một IP:

```text
1. Purpose and non-goals
2. Context and hierarchy
3. Configuration parameters
4. External interfaces
5. Register/address map
6. Functional behavior
7. Datapath
8. Control FSM
9. Arbitration and ordering
10. Clock/reset/power behavior
11. Events and interrupts
12. Error handling
13. Performance model
14. Corner cases
15. Assertions
16. Verification plan
17. Known RTL-specific behavior
18. Clean-room implementation requirements
```

---

## 5. Nhóm 1: Hệ thống xử lý

### Phạm vi

- Fabric Controller subsystem.
- RI5CY/CV32E40P.
- Ibex alternative.
- Cluster `core_region`.
- FPnew, FPU và divide/square-root.
- Interrupt interfaces.
- Instruction/data interfaces.
- Debug request và core sleep.

### File/package chính

- `pulp_soc/rtl/fc/fc_subsystem.sv`
- `cv32e40p`
- `ibex`
- `fpnew`
- `fpu_interco`
- `fpu_div_sqrt_mvp`
- `pulp_cluster/rtl/core_region.sv`

### Diagram cần vẽ

- FC internal architecture.
- Một cluster core island.
- Instruction-fetch flow.
- Load/store flow.
- Interrupt entry/acknowledge.
- Shared-FPU request/response.
- Debug halt/resume sequence.

### Đầu ra

- FC architectural spec.
- Core integration contract.
- Instruction/data bus timing.
- Interrupt model.
- FPU allocation/arbitration spec.
- Bảng khác biệt RI5CY và Ibex.

Thứ tự nghiên cứu: đóng spec giao tiếp core-SoC trước, sau đó phân tích pipeline và execution units bên trong từng CPU.

---

## 6. Nhóm 2: Hệ thống bộ nhớ

### Phạm vi

- Boot ROM.
- Hai private L2 bank.
- Bốn interleaved L2 bank.
- Cluster L1 TCDM.
- SRAM/SCM wrappers.
- Byte enable và read latency.
- Address alias.
- Test-and-set region.
- Instruction-cache hierarchy.

### File/package chính

- `pulp_soc/rtl/pulp_soc/l2_ram_multi_bank.sv`
- `pulp_soc/rtl/pulp_soc/boot_rom.sv`
- `pulp_cluster/rtl/tcdm_banks_wrap.sv`
- `hier-icache`
- `icache-intc`
- `icache_mp_128_pf`
- `scm`
- `tech_cells_generic`

### Diagram cần vẽ

- SoC memory map.
- L2 bank-selection function.
- L2 arbitration path.
- TCDM bank-selection function.
- I-cache hierarchy và refill.
- Core/DMA/HWPE contention tại TCDM.

### Đầu ra

- Memory subsystem spec.
- Timing table cho SRAM và ROM.
- Address-decode equations.
- Arbitration/fairness behavior.
- Cache refill, flush và invalidation behavior.
- Test cho bank conflict, unaligned access và simultaneous masters.

---

## 7. Nhóm 3: Interconnect và bus

Nhóm này phải được thực hiện sớm vì hầu hết các khối khác phụ thuộc vào nó.

### Phạm vi

- AXI crossbar.
- TCDM/LINT crossbar.
- HCI interconnect.
- APB fabric.
- AXI-to-memory.
- AXI-to-APB.
- Peripheral-to-AXI.
- 32-to-64-bit conversion.
- CDC bridge SoC-cluster.
- Address decoder và error slave.

### Package chính

- `axi`
- `axi_slice`
- `axi2mem`
- `axi2per`
- `per2axi`
- `apb`
- `apb_node`
- `apb2per`
- `cluster_interconnect`
- `l2_tcdm_hybrid_interco`
- `hci`

### Diagram cần vẽ

- Master/slave matrix.
- Address-routing tree.
- SoC-to-cluster transaction path.
- Cluster-to-L2 transaction path.
- Read/write channel sequence.
- Width-conversion examples.
- Arbitration state machines.
- CDC FIFO boundaries.

### Đầu ra

- Interconnect architecture spec.
- Ordering model.
- Outstanding transaction limits.
- Burst và atomic support.
- Backpressure rules.
- Error-response rules.
- Formal properties cho no-drop, no-duplicate và stable-while-stalled.

---

## 8. Nhóm 4: uDMA và peripheral

### Phạm vi

- uDMA core.
- RX/TX channel allocation.
- UART.
- SPI/QSPI.
- I2C.
- I2S.
- CPI camera.
- SDIO.
- HyperBus.
- Filter/stream engine.
- GPIO.
- Advanced timer.
- Basic timer.
- SoC event generator.
- SoC control.
- FLL register interface.

### Package chính

- `udma_core`
- `udma_uart`
- `udma_qspi`
- `udma_i2c`
- `udma_i2s`
- `udma_camera`
- `udma_sdio`
- `udma_hyper`
- `udma_filter`
- `udma_external_per`
- `apb_gpio`
- `apb_adv_timer`
- `timer_unit`
- `apb_fll_if`

### Thứ tự phân tích

1. `udma_core` và channel protocol.
2. APB configuration path.
3. L2 RX/TX datapath.
4. Event generation.
5. Từng peripheral adapter.
6. Pad-level behavior.

### Diagram cần vẽ

- uDMA global architecture.
- Channel-allocation map.
- Peripheral -> RX FIFO -> L2.
- L2 -> TX FIFO -> peripheral.
- HyperBus state machine.
- SPI command/data state machine.
- I2C transaction state machine.
- Event routing từ uDMA về FC/cluster.

### Đầu ra

Mỗi peripheral có một spec độc lập, register map, protocol timing và verification plan riêng.

---

## 9. Nhóm 5: Cluster control và peripheral

### Phạm vi

- Cluster control unit.
- Event unit.
- Cluster timer.
- Cluster DMA.
- Peripheral interconnect.
- I-cache control.
- Barrier, mutex và wakeup.
- Core clock/fetch control.
- Cluster busy/isolation.

### File/package chính

- `pulp_cluster/rtl/pulp_cluster.sv`
- `pulp_cluster/rtl/cluster_peripherals.sv`
- `cluster_peripherals`
- `event_unit_flex`
- `mchan`
- `timer_unit`

### Diagram cần vẽ

- Cluster complete hierarchy.
- Eight-core event network.
- Barrier/mutex dispatch.
- Cluster DMA read/write flow.
- Clock gating và wakeup.
- Incoming AXI request đến TCDM/peripheral.
- Cluster outbound access đến L2.

### Đầu ra

- Cluster integration spec.
- Core-control state model.
- DMA programming model.
- Event-unit programming model.
- Multicore synchronization scenarios.

---

## 10. Nhóm 6: HWPE

### Phạm vi

- SoC MAC HWPE.
- Cluster datamover HWPE.
- HWPE control.
- HWPE stream.
- HCI connection.
- Event và busy handling.
- Optional generate branches.

### Package chính

- `hwpe-ctrl`
- `hwpe-stream`
- `hwpe-mac-engine`
- `hwpe-datamover-example`
- `pulp_soc/rtl/fc/fc_hwpe.sv`
- `pulp_cluster/rtl/hwpe_subsystem.sv`

### Diagram cần vẽ

- Control plane và data plane.
- APB/peripheral configuration flow.
- Streaming source/sink.
- TCDM master ports.
- Completion event.
- Datamover internal pipeline.

### Đầu ra

- Generic HWPE integration specification.
- MAC engine spec.
- Datamover spec.
- Hướng dẫn tích hợp accelerator mới.
- Template RTL cho một HWPE mới.

---

## 11. Nhóm 7: Clock, reset và power control

### Phạm vi

- Reference clock.
- SoC, peripheral và cluster clock.
- FLL models/wrappers.
- Reset generation.
- Reset synchronization.
- Clock mux.
- Clock gate.
- Cluster isolation, bypass và power signals.
- CDC/RDC inventory.

### File/package chính

- `pulp_soc/rtl/pulp_soc/soc_clk_rst_gen.sv`
- `pulp_cluster/rtl/cluster_clock_gate.sv`
- `generic_fll`
- `apb_fll_if`
- `common_cells`
- `tech_cells_generic`
- `rtl/pulp/safe_domain.sv`

### Diagram cần vẽ

- Clock tree.
- Reset tree.
- Clock-domain boundaries.
- CDC matrix.
- Reset-release sequence.
- Cluster sleep/wakeup sequence.

### Đầu ra

- Clock/reset specification.
- CDC register.
- Reset-value table.
- Clock-frequency assumptions.
- Assertions về reset release, gated clock và CDC handshake.

---

## 12. Nhóm 8: Boot và debug

### Phạm vi

- Boot select.
- Boot ROM execution.
- JTAG preload.
- SPI/HyperFlash boot.
- RISC-V DMI.
- `dm_top`.
- PULP JTAG memory access.
- Debug arbiter.
- FC và cluster debug request.

### Package chính

- `riscv-dbg`
- `jtag_pulp`
- `adv_dbg_if`
- `rtl/pulp/jtag_tap_top.sv`
- `pulp_soc/rtl/pulp_soc/lint_jtag_wrap.sv`
- `pulp_soc/rtl/pulp_soc/boot_rom.sv`

### Diagram cần vẽ

- Power-on-to-first-instruction sequence.
- JTAG preload sequence.
- SPI/HyperFlash boot sequence.
- JTAG TAP state machine.
- DMI request path.
- Debug halt/resume path.
- Debug memory-access arbitration.

### Đầu ra

- Boot specification.
- Debug architecture specification.
- Boot-mode truth table.
- Hart-ID mapping.
- Debug security boundary và unsupported cases.

---

## 13. Nhóm 9: Pad và external I/O

### Phạm vi

- `pad_frame`.
- `pad_control`.
- Pad mux.
- GPIO fallback.
- Pull-up/pull-down.
- Output-enable polarity.
- Peripheral-to-pad mapping.
- Boot/reset/JTAG dedicated pins.
- FPGA pin wrappers.

### File chính

- `rtl/pulp/pad_frame.sv`
- `rtl/pulp/pad_control.sv`
- `rtl/pulp/safe_domain.sv`
- `fpga/*/rtl`

### Diagram cần vẽ

- Pinout theo peripheral.
- Pad-mux matrix.
- GPIO/peripheral ownership.
- Input/output/output-enable flow.
- Pad reset state.

### Đầu ra

- Pin specification.
- Mux-function table.
- Electrical abstraction assumptions.
- Reset/default-state table.
- FPGA mapping appendix.

---

## 14. Nhóm 10: Verification platform và file không nằm trong silicon

### Phạm vi

- `tb_pulp`.
- JTAG drivers.
- Clock generator.
- Filesystem/DPI.
- UART receiver.
- Camera VIP.
- SPI Flash, HyperRAM, HyperFlash, PSRAM và I2C EEPROM models.
- Simulation scripts.
- FPGA wrapper.
- GVSoC comparison.

### Phân loại bắt buộc

Mỗi file phải được đánh dấu một trong:

- Synthesizable SoC.
- Synthesizable FPGA-only.
- Behavioral memory model.
- External-device VIP.
- Testbench infrastructure.
- Assertion/checker.
- DPI/software helper.
- Legacy/uninstantiated.

### Diagram cần vẽ

- Testbench context.
- DUT-to-VIP connections.
- Boot-stimulus flow.
- ELF preload flow.
- UART/log-checking flow.
- RTL-versus-GVSoC comparison flow.

### Đầu ra

- Verification architecture.
- Testbench user guide.
- Reusable smoke tests.
- Danh sách model không được mang vào synthesis.
- Traceability từ mỗi spec requirement tới test hoặc assertion.

---

## 15. Thứ tự thực hiện thực tế

Không thực hiện máy móc theo thứ tự nhóm 1 đến 10. Thứ tự được đề xuất:

| Phase | Nội dung | Thời lượng solo full-time ước tính |
|---|---|---:|
| 0 | Baseline, file inventory và configuration matrix | 3-5 ngày |
| 1 | Top hierarchy, pad, clock và reset | 1-2 tuần |
| 2 | Interconnect và memory | 2-3 tuần |
| 3 | FC và core integration | 2-3 tuần |
| 4 | uDMA và peripheral | 3-4 tuần |
| 5 | Cluster, DMA, event unit và cache | 3-4 tuần |
| 6 | HWPE | 1-2 tuần |
| 7 | Boot và debug | 1-2 tuần |
| 8 | Testbench, VIP và FPGA variants | 1-2 tuần |
| 9 | System scenarios và clean specs | 2-3 tuần |

Tổng thời gian dự kiến:

- Khoảng 16-24 engineer-weeks cho đặc tả kiến trúc đầy đủ.
- Khoảng 25-35 engineer-weeks nếu phân tích line-by-line cả generic library, alternate CPU và mọi primitive trong compile list.

---

## 16. Bộ diagram bắt buộc

Toàn dự án phải có ít nhất:

1. SoC context diagram.
2. Full SoC block diagram.
3. Clock/reset/power-domain diagram.
4. Master/slave matrix.
5. Address map.
6. Interrupt/event map.
7. Pad-mux/pin map.
8. FC internal diagram.
9. Cluster internal diagram.
10. L2/TCDM/cache memory diagram.
11. uDMA architecture.
12. Mỗi peripheral một datapath/FSM diagram.
13. HWPE data/control plane.
14. Boot sequence diagrams.
15. Debug sequence diagrams.
16. Testbench/VIP topology.

Diagram phải được lưu dưới dạng có thể sửa và review bằng Git, ưu tiên Mermaid, Graphviz, WaveDrom hoặc draw.io source. Ảnh PNG/PDF chỉ là output render.

---

## 17. System scenarios cần trace end-to-end

Sau khi hoàn thành các IP riêng lẻ, phải trace tối thiểu các scenario:

1. Reset đến instruction đầu tiên của FC.
2. JTAG nạp ELF vào L2 và bắt đầu chạy.
3. Boot từ SPI Flash.
4. Boot từ HyperFlash.
5. FC cấu hình uDMA UART TX/RX.
6. Camera CPI truyền frame vào L2.
7. FC bật cluster và phát lệnh cho 8 core.
8. Cluster DMA chuyển dữ liệu L2-TCDM-L2.
9. Multicore barrier và wakeup qua event unit.
10. Cluster HWPE đọc/ghi TCDM và phát completion event.
11. Interrupt peripheral đi tới FC.
12. Debug halt/resume FC và cluster core.
13. Contention giữa FC, uDMA, cluster và debug tại L2.
14. Cluster sleep, clock gate và wakeup.

Mỗi scenario cần:

- Sequence diagram.
- Danh sách module đi qua.
- Clock domain liên quan.
- Address/register liên quan.
- Expected waveform.
- Test tái hiện.

---

## 18. Verification strategy cho IP tự phát triển

Mỗi clean spec phải đi kèm:

- Directed smoke tests.
- Random/constrained-random tests khi thích hợp.
- Protocol assertions.
- Reset assertions.
- Backpressure tests.
- Error-injection tests.
- Coverage model.
- Reference model hoặc scoreboard.
- So sánh implementation mới với RTL gốc ở boundary của IP.

Đối với IP có transaction interface, nên xây dựng wrapper cho phép chạy đồng thời:

```text
Stimulus
  ├── Original RTL
  └── New RTL
        -> transaction/result comparator
```

Đối với CPU, interconnect, cache và DMA, bổ sung formal property hoặc bounded proof cho các invariant cốt lõi.

---

## 19. Definition of Done

Dự án chỉ hoàn thành khi:

- Mọi file trong Bender compile list có trạng thái phân tích.
- Mọi module trong elaborated hierarchy có owner và tài liệu.
- Không còn black box không giải thích trong cấu hình active.
- Mọi bus có protocol, master/slave, width và clock domain.
- Mọi register block có address map và reset value.
- Mọi interrupt/event có source và destination.
- Mọi CDC/RDC crossing được phân loại.
- Mọi FSM quan trọng có state diagram.
- Mỗi IP có behavioral spec độc lập với implementation.
- Mỗi requirement quan trọng có test hoặc assertion tương ứng.
- Các flow boot, DMA, cluster offload, interrupt và debug đều có sequence diagram chạy xuyên toàn SoC.
- Inventory của các cấu hình simulation, full-system, maximum-feature và FPGA đều được reconcile.

---

## 20. Công việc đầu tiên cần thực hiện

Milestone đầu tiên là tạo ba artifact:

1. `doc/rtl_spec/00_scope/rtl_inventory.csv`
2. `doc/rtl_spec/00_scope/configurations.md`
3. `doc/rtl_spec/00_scope/module_index.md`

Cấu hình đầu tiên được elaborate và phân tích là `CFG-FULL-SYSTEM` vì nó bao phủ đường chạy thực tế gồm FC, 8 cluster core và cluster HWPE.

Milestone 0 được coi là đạt khi:

- File list có thể tái tạo bằng một command được ghi lại.
- Mọi file được gán package, loại và analysis level.
- Cây hierarchy từ `tb_pulp` đến leaf module đã được sinh.
- Các module conditional/inactive được đánh dấu rõ.
- Có dashboard số lượng file `todo`, `in-progress`, `reviewed` và `specified`.
