# Kế hoạch phân tích microarchitecture PULP

Ngày bắt đầu: 2026-09-13. Tổ chức tài liệu theo domain, phân tích từng khối có
datapath/control/state rõ ràng, sau đó nối bằng giao dịch xuyên khối/domain.
Không suy cấu hình từ tài liệu của một phiên bản CV32E40P khác: dùng RTL trong
checkout và compile list của workspace này.

## 1. Phạm vi và trình tự

Đợt đầu: **FC pipeline + LSU → SoC interconnect**. Theo yêu cầu tiếp tục, đã
triển khai phân tích tĩnh M4–M7 và thêm bốn bench component cho M8. Ngày
2026-09-19 bổ sung M9–M11 để đóng các khoảng trống module-level còn lại. Phần
kiểm chứng tích hợp vẫn được theo dõi riêng ở L4, không dùng closure L3 để nhận
hoàn tất M8.

| Mốc | Công việc và đầu ra | Trạng thái hiện tại |
|---|---|---|
| M0 | Chốt source/core/parameter/clock/reset; bảng bằng chứng revision/hash | Đã chốt source tĩnh, 2026-09-13 |
| M1 | [FC pipeline](micro_01_fc_pipeline.md): IF/ID/EX/WB, prefetch, forwarding/hazard, redirect | Đã phân tích integer/memory; chưa SIM core |
| M2 | [FC LSU](micro_02_fc_lsu.md): datapath/FSM, byte-enable, sign extension, split, grant/response | Đã phân tích; SIM LSU độc lập PASS 20 checks |
| M3 | [FC → SoC](micro_03_fc_soc_interconnect.md): chu kỳ, contention, outstanding, stall propagation | Đã nối đường tĩnh; chưa SIM tích hợp |
| M4 | [SoC uDMA/event](micro_04_soc_udma_event.md): credit, completion, arbitration | Đã phân tích đường UART/uDMA/event; SIM TX credit + event counter |
| M5 | [Cluster](micro_05_cluster_memory_dma_eu.md): PE, cache, TCDM, DMA, EU/barrier | Đã phân tích tĩnh các đường chính; SIM barrier + DMA synch; chưa SIM cache/HCI |
| M6 | [FPU/HWPE](micro_06_fpu_hwpe.md): dispatch, datapath, latency, arbitration, writeback | Đã phân tích tĩnh; SIM APU dispatcher; chưa kiểm số học/FP-HWPE tích hợp |
| M7 | [CDC/clock/reset](micro_07_cdc_clock_reset.md): queue, wake, reset ownership | Đã phân tích contract, gồm reset in-flight; SIM FIFO hai clock + gate; chưa SIM reset tích hợp |
| M8 | [Kiểm chứng](micro_08_validation.md): scoreboard, timing, throughput và giới hạn | Một phần: LSU 20 checks; control 31 + DMA 12; CDC 64 payload; xbar 16 response. Full-system chưa chạy, Questa preflight lỗi license |
| M9 | [FC control plane](micro_09_fc_control_plane.md): trap/IRQ/CSR/debug/WFI/ELW/hardware loop | Đã phân tích state, priority, redirect, save/restore và error boundary; test cycle corner chuyển L4 |
| M10 | [uDMA peripherals](micro_10_udma_peripherals.md): SPI/I2C/SDIO/I2S/camera/filter/Hyper | Đã chốt topology, APB/data/event map, FSM và completion; pad/protocol tests chuyển L4 |
| M11 | [Cluster AXI bridges](micro_11_cluster_axi_bridges.md): xbar/axi2mem/axi2per/per2axi/width conversion | Đã chốt decode, ID owner, serialization, response và busy; contention/backpressure tests chuyển L4 |

M1–M3 đi sâu đường integer/memory của FC; M9 đóng control plane của FC. FPU chỉ được xét ở ranh giới gây
stall/writeback contention, phần nội bộ thuộc M6. M3 dùng kết quả decode/xbar
đã có trong các bài SoC, bổ sung tác động ngược lên pipeline. Khối dùng chung
chỉ phân tích implementation một lần, rồi ghi khác biệt integration/parameter.

## 2. Phương pháp thực hiện mỗi mốc

1. Chọn câu hỏi kiểm chứng được: ví dụ load chưa grant giữ stage nào, hay
   response load đến thì dependent instruction lấy operand từ đâu?
2. Chốt file compile, parameter override, generate và wiring của instance.
3. Vẽ datapath và inventory state: register, valid bit, counter, FIFO, FSM.
4. Viết điều kiện acceptance/completion, next-state và priority; lần cả request
   xuôi lẫn response/stall ngược về producer.
5. Lập bảng chu kỳ có giả định, xét no-stall, grant chậm, response chậm,
   back-to-back, redirect hoặc reset khi có transaction.
6. Đối chiếu instruction/HAL/workload; phân biệt đoạn assembly minh họa với
   instruction thực trong ELF đã được kiểm.
7. Ghi source + vị trí + hash; phân loại [RTL], [SUY RA], [CẦN ĐO], [SIM mới].
8. Thiết kế phép kiểm chứng có tiêu chí pass/fail; chỉ ghi [SIM mới] khi đã chạy
   đúng RTL và lưu log/config. Kiểm tra link/hash không thay thế RTL simulation.

Quy ước chu kỳ: C0 là khoảng trước cạnh E1; register cập nhật tại E1 tạo trạng
thái C1. Handshake là điều kiện được nhận tại cạnh, không chỉ một xung nhìn thấy
giữa chu kỳ. Không cộng một chu kỳ cho mỗi wrapper combinational.

## 3. Câu hỏi bắt buộc cho đợt FC → SoC

| Phần | Câu hỏi phải trả lời |
|---|---|
| IF | Prefetch chứa gì? Có bao nhiêu request chờ? Redirect xử lý response cũ thế nào? |
| ID | Register file đọc/ghi ở đâu? Operand được forward từ EX/WB khi nào? |
| EX/WB | ALU và load ghi register bằng đường nào? Ai tạo ready/valid? |
| Hazard | Load-use, jalr, multicycle và LSU stall khác nhau thế nào? |
| LSU | Grant khác response ra sao? Store có chờ response? Split load/store ghép dữ liệu thế nào? |
| Interconnect | FC instruction/data dùng master nào? Ai nhớ owner/đích response? |
| Timing | Bank grant chậm và AXI response chậm truyền về pipeline thế nào? |
| Completion/error | Bus response có đủ để nói instruction retire/trap không? |

## 4. Tiêu chí hoàn tất và nghiệm thu

M0–M3 đạt mức **phân tích tĩnh hoàn tất** khi có source map/config, sơ đồ
datapath/control, điều kiện ready/valid/FSM cụ thể, ít nhất một load và một store
đi trọn core→memory→core, trường hợp dependency/stall/split, giới hạn suy luận
và danh sách tín hiệu/phép thử. Phải kiểm lại liên kết và tính nhất quán nguồn.

M8 là tiêu chí riêng: waveform/scoreboard xác nhận các giả thuyết, data và thứ
tự completion đúng, đo được thời gian từng chặng trong cấu hình đã lưu. Không
gọi M0–M3 là timing sign-off hay xác nhận throughput thực tế trước khi có M8.

Closure toàn L3 dùng cùng tiêu chí cho M4–M7 và M9–M11, được tổng hợp tại
[L3_CLOSURE](../architecture/L3_CLOSURE.md). Closure chỉ áp dụng cấu hình hiệu lực; branch
inactive và mọi xác nhận cycle/protocol động không nằm trong tuyên bố này.

## 5. Nhật ký triển khai

- 2026-09-13: lưu kế hoạch; bắt đầu kiểm cấu hình và đọc implementation FC,
  prefetch, pipeline, LSU, sau đó nối SoC interconnect.
- 2026-09-13: hoàn thành đợt phân tích tĩnh M0–M3 trong phạm vi integer/memory;
  tạo ba bài chi tiết, xác định FC Zfinx=1, RF latch, PMP active, hai đường RF
  write, prefetch một outstanding và bốn state LSU. Chạy LSU độc lập PASS 20
  checks; lưu log/VCD và snapshot tại [report](../../../../report/microarchitecture_20260913/README.md).
  Tại thời điểm kết thúc đợt đầu, M4–M7 chưa triển khai; được tiếp tục ở lượt dưới.

Tài liệu nền: [phương pháp phân tích RTL](../soc_rtl/soc_00_phuong_phap_phan_tich_rtl.md),
[FC–memory](../soc_rtl/soc_01_fc_memory_rtl.md), [APB–timer](../soc_rtl/soc_02_timer_irq_rtl.md),
[mục lục domain](../architecture/DEEP_DIVE_INDEX.md).

- 2026-09-13, lượt tiếp tục: tạo M4–M8, đi từ credit/queue tới cache/refill,
  TCDM/MCHAN/EU, FPU/HWPE và CDC/gating/reset. Sửa nhận định response TX luôn
  được giữ; ghi rõ binary ID trong s_stall, CDC spill capacity, HWPE busy hằng
  và incoming wake chưa thấy driver trong cluster source.
- Lưu [bốn bench và report mới](../../../../report/microarchitecture_20260913_remaining/README.md).
  Đã chạy component; ma trận nghiệm thu tích hợp còn lại có stimulus/signal/
  pass criteria tại M8. Questa preflight exit 4 do license; không dùng kết quả
  component để nhận toàn bộ plan đã hoàn tất.
- 2026-09-19: hoàn tất phân tích tĩnh bổ sung M9–M11. FC control plane đã có
  IRQ/trap/debug/sleep/ELW/hardware-loop; uDMA đã bao phủ mọi peripheral active;
  cluster fabric đã có xbar và ba bridge. Chốt L3 cho cấu hình hiệu lực tại
  [L3_CLOSURE](../architecture/L3_CLOSURE.md); không chạy thêm RTL simulation trong lượt này.
