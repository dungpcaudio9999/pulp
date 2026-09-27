# L3 closure — Phạm vi module deep dive của PULP

Ngày chốt: **2026-09-19**.

## Kết luận

Trong **cấu hình hiệu lực của simulation top hiện tại**, phần phân tích tĩnh L3
đã được đóng ở mức module và giao dịch: các khối chức năng chính đều có
inventory state/FSM, ready-valid hoặc request-grant-response, ownership của
response, completion/error semantics và liên kết tới khối kế tiếp.

Trạng thái chính xác là:

| Mức | Trạng thái sau đợt bổ sung |
|---|---|
| L1 — Overview | Đã vượt qua |
| L2 — Structured design analysis | Hoàn tất |
| **L3 — Module deep dive** | **Hoàn tất phân tích tĩnh cho cấu hình hiệu lực** |
| L4 — Cycle-accurate verification | Một phần; component tests có, coverage tích hợp còn thiếu |
| L5 — Sign-off-grade analysis | Chưa đạt |

“L3 hoàn tất” ở đây không có nghĩa RTL đã đúng tuyệt đối, đủ coverage hay đã
sign-off timing/protocol. Nó có nghĩa các module đang hoạt động không còn bị
dùng như hộp đen trong mô hình phân tích; các giả thuyết cần waveform đã được
chuyển thành checklist L4 rõ ràng.

## 1. Scope được chốt

Kết luận áp dụng cho instance/parameter được compile từ `rtl/pulp/pulp.sv` và
`sim/compile.tcl`, gồm:

- FC loại RI5CY (`CORE_TYPE_FC=0`), PMP, FPU/Zfinx;
- một SoC với ROM/L2/APB/timer/event/uDMA/debug/cluster control;
- cluster 8 PE, TCDM 64 KiB/16 bank, shared I-cache 4096 B, MCHAN,
  event unit/barrier, shared FPU và HWPE/datamover;
- AXI C2S 64-bit, S2C 32-bit, CDC depth parameter 8;
- UART×1, SPI×1, I2C×2, SDIO×1, I2S×1, camera×1, filter×1,
  HyperBus với 8 context.

Không nhận closure cho các generate branch không hoạt động: Ibex FC/cluster,
RBE, CSI2/MRAM/JTAG-uDMA/FPGA/external training peripheral, các cấu hình cache,
core-count, bank-count, width hoặc HWPE khác. Leaf arithmetic/technology cells
được phân tích theo contract của parent active path; không mở rộng thành một
cuộc audit library độc lập.

## 2. Ma trận coverage L3

| Domain/module | Nội dung đã lần | Tài liệu |
|---|---|---|
| Effective configuration | top/TB, parameter override, compile source, clock/reset | [Deep dive 00](deep_dive_00_effective_configuration.md) |
| Boot/debug/testbench | reset→ROM→startup, JTAG/DPC, first instruction | [Deep dive 04](deep_dive_04_boot_debug_testbench.md) |
| FC IF/ID/EX/WB | prefetch/FIFO/alignment, forwarding, hazard, redirect, writeback | [M1](../microarchitecture/micro_01_fc_pipeline.md) |
| FC LSU | FSM, split, byte-enable, grant/response, load result | [M2](../microarchitecture/micro_02_fc_lsu.md) |
| FC control plane | IRQ/trap/CSR/debug/WFI/ELW/hardware loop/PMP error boundary | [M9](../microarchitecture/micro_09_fc_control_plane.md) |
| FC→SoC fabric | master/decode/owner, L2 bank, APB conversion, stall propagation | [M3](../microarchitecture/micro_03_fc_soc_interconnect.md), [SoC 01](../soc_rtl/soc_01_fc_memory_rtl.md) |
| APB/timer/interrupt | AW/W→APB, timer next-state, pending/mask/ack/vector/FIFO | [SoC 02](../soc_rtl/soc_02_timer_irq_rtl.md), [M9](../microarchitecture/micro_09_fc_control_plane.md) |
| uDMA core/UART/event | address generators, arbiters, credit, RX/TX, completion/event | [M4](../microarchitecture/micro_04_soc_udma_event.md), [SoC 03](../soc_rtl/soc_03_udma_debug_cluster_rtl.md) |
| uDMA peripherals | SPI/I2C/SDIO/I2S/camera/filter/Hyper topology, FSM, data/event map | [M10](../microarchitecture/micro_10_udma_peripherals.md) |
| Cluster PE/cache | boot/fetch, shared cache geometry/refill/control | [M5](../microarchitecture/micro_05_cluster_memory_dma_eu.md) |
| TCDM/HCI | bank mapping/arbitration/response path | [M5](../microarchitecture/micro_05_cluster_memory_dma_eu.md) |
| MCHAN/EU/barrier | command/parser/queues, AXI completion, event/barrier state | [M5](../microarchitecture/micro_05_cluster_memory_dma_eu.md) |
| Cluster AXI bridges | 4×3 decode, ID owner, axi2mem/axi2per/per2axi, width conversion/busy | [M11](../microarchitecture/micro_11_cluster_axi_bridges.md) |
| FPU/APU | scoreboard, latency class, FMA internals, arbitration/writeback | [M6](../microarchitecture/micro_06_fpu_hwpe.md) |
| HWPE | wrapper/control/datamover/stream/completion/busy contract | [M6](../microarchitecture/micro_06_fpu_hwpe.md) |
| CDC/clock/reset | Gray FIFO/spill, five AXI channels, event crossing, gate/wake/reset ownership | [M7](../microarchitecture/micro_07_cdc_clock_reset.md) |
| Inter-domain transactions | FC↔cluster, DMA round-trip, events, gating | [Deep dive 05](deep_dive_05_domain_transactions.md) |

## 3. Tiêu chí dùng để gọi một hàng là đã đạt L3

Mỗi active path phải trả lời được tối thiểu:

1. instance/generate/parameter nào thực sự active;
2. input nào được accept và theo điều kiện handshake nào;
3. state/register/FIFO nào giữ payload và owner khi downstream stall;
4. priority giữa request, redirect, error, reset hoặc event đồng thời;
5. response quay về producer nào và completion được định nghĩa tại chặng nào;
6. error/busy/wake/reset được truyền hoặc bị cắt ở đâu;
7. ít nhất một transaction end-to-end và một trường hợp backpressure/corner;
8. nguồn RTL và giới hạn suy luận.

Ba khoảng trống trước đợt này — FC control plane, peripheral uDMA ngoài UART,
và cluster AXI bridges — nay đáp ứng cùng tiêu chí. Các phát hiện mới đáng chú ý:

- active RI5CY không nhận cờ bus-error của FC wrapper; PMP fault vẫn có đường
  nội bộ riêng;
- IRQ ID lớn nhất thắng; ack đồng thời event mới cùng bit có priority clear;
- uDMA APB select ngoài range giữ `PREADY=0`, `PSLVERR=0`;
- Hyper có tám context cấu hình nhưng một data TX/RX pair dùng chung;
- cluster có decode gap sau TCDM và không bật default target;
- `axi2per` serialize một outstanding và không propagate peripheral `r_opc`
  thành AXI response error;
- `per2axi` grant bus nội bộ phụ thuộc đồng thời AW/AR/W ready.

Các điểm này là kết quả đọc RTL, chưa phải bug được tái hiện động. Chúng được
đưa vào ma trận L4 để tránh biến nghi vấn tĩnh thành kết luận sign-off.

## 4. Những gì còn lại đều thuộc L4

| Nhóm kiểm chứng | Cần chứng minh bằng simulation/waveform/scoreboard |
|---|---|
| FC pipeline/control | penalty thực, retire order, IRQ/debug/ELW/hardware-loop ở đúng cạnh |
| FC/SoC memory | bank/APB contention, split access, unmapped/error behavior end-to-end |
| uDMA | mỗi protocol với pad/model thật, buffer-vs-EOT, loss/dup event, reset in-flight |
| Cluster cache/TCDM | refill/flush, 8-PE same-bank/different-bank, ordering và throughput |
| MCHAN | burst/read/write response dưới backpressure và dữ liệu round-trip |
| AXI bridges/CDC | simultaneous initiators, width conversion, independent channel stall, reset |
| FPU | numeric corner, flags/rounding, latency và writeback contention |
| HWPE | config→datamover→completion bằng workload và memory scoreboard |
| Power/control | WFI/cluster gate wakeup, clock/reset assertion/deassertion đang in-flight |

Component tests hiện có vẫn có giá trị nhưng không thay thế các hàng tích hợp:
LSU 20 checks; control/DMA component; CDC payload; xbar response. Danh sách test,
tín hiệu và pass criteria nằm ở [M8](../microarchitecture/micro_08_validation.md).

## 5. Điều kiện làm mất hiệu lực closure

Cần mở lại L3 nếu có một trong các thay đổi sau:

- đổi dependency commit/local patch hoặc compile define;
- đổi `CORE_TYPE_*`, FPU/HWPE, số core/bank/DMA, AXI width/depth;
- bật một peripheral/generate branch hiện inactive;
- thay top/testbench hoặc memory/error model;
- phát hiện waveform L4 mâu thuẫn mô hình state/handshake đã ghi.

Vì workspace có dependency patch và tài liệu đang là thay đổi chưa commit,
revision/hash phải được ghi lại ở mỗi lượt L4. Closure này là baseline phân tích,
không phải chứng nhận độc lập hay sign-off artifact.
