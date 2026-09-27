# Mục lục phân tích chuyên sâu RTL PULP

Bộ tài liệu phân tích **cấu trúc domain kết hợp giao dịch từ phần mềm xuống RTL**,
đối chiếu implementation ngày **2026-09-10**. Dependency đã có trong checkout;
không còn coi `pulp_soc`/`pulp_cluster` là hộp đen chỉ biết interface.

## Cách đọc và mức bằng chứng

Bắt đầu với cấu hình, sau đó đọc trọn bài reset→lệnh đầu tiên, rồi các domain:

| Bài | Nội dung |
|---|---|
| [00 — Cấu hình hiệu lực](deep_dive_00_effective_configuration.md) | TB/FPGA top, override, dependency compile, clock/reset và nhãn bằng chứng |
| [04 — Reset → FC thực thi](deep_dive_04_boot_debug_testbench.md) | reset chain, boot FSM, ROM instruction, JTAG DPC, startup→main |
| [01 — Safe domain](deep_dive_01_platform_safe_domain.md) | pad routing, OE, reset bypass, GPIO loopback/UART |
| [02 — SoC domain](deep_dive_02_soc_domain.md) | FC, L2 bank/decode, APB, timer IRQ, event/uDMA |
| [03 — Cluster](deep_dive_03_cluster_and_interconnect.md) | PE boot, cache, TCDM/HCI, barrier, MCHAN, FPU/HWPE |
| [05 — Giao dịch xuyên domain](deep_dive_05_domain_transactions.md) | AXI/CDC/event/gating, offload đang có và bài tính toán cần bổ sung |

Mỗi domain trả lời sáu nhóm: vai trò/ranh giới; cấu trúc; hoạt động; phần mềm;
thời gian/hiệu năng; bằng chứng và tiêu chí kiểm chứng.
**[RTL]**, **[SW]**, **[SIM cũ: ngày/lượt]**, **[CẦN ĐO]** được phân biệt rõ.
Đợt domain 2026-09-10 đã đọc implementation và kiểm tra tĩnh, chưa chạy simulator.
Đợt microarchitecture 2026-09-13 bổ sung simulation LSU và các component
uDMA/event/APU/barrier/DMA/CDC/gate/xbar như phần dưới;
chưa có simulation core/full-system mới.

## Microarchitecture: FC → SoC → cluster → FPU/HWPE → CDC

| Tài liệu | Nội dung/trạng thái |
|---|---|
| [Kế hoạch PULP](../microarchitecture/micro_00_plan_phan_tich_pulp.md) | M0–M11, phương pháp, phạm vi và tiến độ |
| [FC pipeline](../microarchitecture/micro_01_fc_pipeline.md) | Zfinx/PMP/RF latch; prefetch, IF/ID/EX/WB, forwarding/hazard, redirect |
| [FC LSU](../microarchitecture/micro_02_fc_lsu.md) | Datapath/FSM, EX stall, split và completion; SIM module PASS 20 checks |
| [FC nối SoC](../microarchitecture/micro_03_fc_soc_interconnect.md) | Load-use/store-load, stall ngược về core, bank contention và APB response |
| [Bằng chứng 2026-09-13](../../../../report/microarchitecture_20260913/README.md) | Testbench/script, log/VCD LSU, revision/hash và giới hạn kiểm chứng |
| [SoC uDMA/event](../microarchitecture/micro_04_soc_udma_event.md) | Credit/inflight, RX queues, completion và event backpressure |
| [Cluster](../microarchitecture/micro_05_cluster_memory_dma_eu.md) | Cache geometry/FSM, HCI banks, MCHAN completion, EU/barrier |
| [FPU/HWPE](../microarchitecture/micro_06_fpu_hwpe.md) | Scoreboard, latency class, FMA datapath, shared arbitration, datamover |
| [CDC/clock/reset](../microarchitecture/micro_07_cdc_clock_reset.md) | Gray pointers/spill, AXI channels, event wake, gating và reset ownership |
| [Kiểm chứng M8](../microarchitecture/micro_08_validation.md) | Kết quả component mới, số đo xbar/CDC, ma trận tích hợp chưa nghiệm thu |
| [FC control plane](../microarchitecture/micro_09_fc_control_plane.md) | IRQ/trap/CSR/debug/WFI/ELW/hardware loop và priority |
| [uDMA peripherals](../microarchitecture/micro_10_udma_peripherals.md) | SPI/I2C/SDIO/I2S/camera/filter/Hyper: topology, FSM, event/completion |
| [Cluster AXI bridges](../microarchitecture/micro_11_cluster_axi_bridges.md) | 4×3 xbar, axi2mem/axi2per/per2axi, width conversion và response owner |
| [L3 closure](L3_CLOSURE.md) | Ma trận module coverage; L3 static hoàn tất cho cấu hình hiệu lực, phần còn lại chuyển L4 |
| [Report M4–M8](../../../../report/microarchitecture_20260913_remaining/README.md) | Bốn bench Verilator, logs/VCD, hashes; lỗi license Questa preflight |

## Đi sâu SoC RTL và học cách phân tích source

Đọc theo thứ tự dưới đây. Mỗi bài đi từ kết nối tới điều kiện handshake,
state/register, response và đối chiếu phần mềm; bảng chu kỳ được ghi rõ là suy
ra từ RTL, không phải số đo mới.

| Bài | Kết quả và cách làm có thể tham khảo |
|---|---|
| [SoC 00 — Phương pháp](../soc_rtl/soc_00_phuong_phap_phan_tich_rtl.md) | Chốt cấu hình/source, lập phiếu giao dịch, lần request/response, đọc FSM, tìm phản ví dụ; có mẫu tái sử dụng |
| [SoC 01 — FC/ROM/L2](../soc_rtl/soc_01_fc_memory_rtl.md) | Master map, address remap, bank/row, arbitration, fixed-latency response, bảng chu kỳ và lỗi |
| [SoC 02 — APB/timer/IRQ](../soc_rtl/soc_02_timer_irq_rtl.md) | AW/W độc lập, APB Setup/Access, timer next-state, pending/mask/ack, vector và FIFO semantics |
| [SoC 03 — uDMA/UART/debug/cluster](../soc_rtl/soc_03_udma_debug_cluster_rtl.md) | Descriptor tới pad, FIFO/CDC, các mốc completion, event queue, debug arbitration và cluster control |

[Bằng chứng SoC](../../../../report/soc_rtl_analysis_20260910/README.md) kèm script
read-only thu hash/revision và vị trí logic để đối chiếu lại khi source thay đổi.

## Những đính chính quan trọng từ implementation

| Nhận định cũ | Kết luận hiện tại và bằng chứng |
|---|---|
| safe domain đồng bộ reset rồi đưa sang SoC | `rst_no=s_rstn`, output `s_rstn_sync` không được dùng ở đường này; SoC có synchronizer riêng — bài 01/04 |
| mặc định wrapper cho biết HWPE thực tế | TB mặc định tắt; runner bật cluster HWPE; top còn override số port từ 9 xuống **4** — bài 00 |
| 12 byte datamover mâu thuẫn RTL | `BW=4*32`, `BW_ALIGNED=BW-32=96 bit=12 B`; payload phù hợp RTL, throughput cần đo — bài 00/03 |
| L1 chỉ biết từ linker; L2 là 512 KiB | RTL L1 64 KiB; L2 shared 512 KiB cộng private 64 KiB; linker là giới hạn riêng — bài 02/03 |
| cluster fetch ngoài bằng 0 nên chưa biết khởi chạy thế nào | FC ghi boot/fetch register qua AXI; `fetch_en_int=fetch_enable_reg_int` — bài 03 |
| DMA khứ hồi kiểm hai giao diện AXI | cả hai transfer MCHAN dùng giao diện **Cluster→SoC**, lần lượt AR/R và AW/W/B — bài 03/05 |
| cluster trả event để `cluster_wait()` xong | runtime hiện poll biến `cluster_running`; core 0 ghi biến khi entry return — bài 03/05 |
| timer phase chứng minh ngắt, GPIO phase chứng minh padmux | hiện chỉ count tăng và PADOUT readback; chưa ISR/loopback — bài 01/02 |
| response uDMA TX luôn giữ valid khi consumer stall | r_valid cập nhật mỗi clock, r_resp là binary ID; phải xét io_tx_fifo credit — M4 |
| CDC FIFO 4 ô chỉ giữ 4 payload chưa giao | thêm 2 ô spill ở destination; SIM đã nhận 6 khi consumer chưa nhận gì — M7/M8 |
| HWPE done làm busy_o hạ để cluster gate | wrapper busy_o=1 khi HWPE hiện diện; job completion khác global busy — M6/M7 |
| STANDALONE là nạp thẳng memory nhanh hơn JTAG | đây là boot từ flash qua ROM/peripheral, cần model/image riêng — bài 04 |

## Trạng thái bằng chứng

[Source audit](../../../../report/domain_analysis_20260910/source_audit.json) ghi root HEAD,
HEAD/status dependency, hash đầu vào và 811 file RTL trong compile script đều tồn tại.
Đây không phải log compile hay dump elaboration. `Bender.yml` và `Bender.lock`
khác revision cluster; có patch local trong dependency, nên dùng đúng source
được compile script trỏ tới và ghi lại trạng thái trước mỗi lượt chạy.

**[SIM cũ: 2026-09-06]** Log full_system lượt 06 PASS và lượt 08 tiêm lỗi core 3
FAIL vẫn có giá trị cho cấu hình/source của các lượt đó. Các tỷ lệ thời gian và
mốc waveform là số liệu lịch sử, không phải bảo đảm hiệu năng hoặc kết quả tái
lập của checkout hiện tại. GPIO loopback, timer ISR, uDMA buffer, FPU và benchmark
bank toàn cluster là các phép thử tích hợp còn cần làm theo bài 05/M8;
component xbar 4×4 và TX credit đã có kiểm chứng mới ở report M4–M8.

Đợt bổ sung 2026-09-19 đã đóng ba khoảng trống L3: FC control plane, các
peripheral uDMA ngoài UART và cluster AXI bridge fabric. Đây là closure phân
tích tĩnh; không thay đổi trạng thái các phép thử tích hợp L4 trong M8.

## Tài liệu liên quan

| Tài liệu | Nội dung |
|---|---|
| [Source map](pulp_architecture_and_source_map.md) | tổng quan; dùng bộ deep-dive này cho các kết luận đã đính chính |
| [full_system-giai-thich](../simulation/full_system-giai-thich.md) | chương trình hiện kiểm tra gì |
| [RUNBOOK](../simulation/RUNBOOK.md) | chuẩn bị và chạy Questa |
| [sw/full_system/README](../../../../sw/full_system/README.md) | cách gọi demo |
| [PROJECT_STATUS](../project/PROJECT_STATUS.md) | lịch sử milestone |
| [Báo cáo tổng kết](../project/BAO-CAO-TONG-KET.md) | tổng kết đợt thử trước |
| [Log full_system](../../../../report/full_system_20260906/) | PASS, lỗi và phép thử âm cũ |
| [Waveform cũ](../../../../report/waveform_20260906/) | timeline và giới hạn tín hiệu đã thu |
