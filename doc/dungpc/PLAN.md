# Kế hoạch tìm hiểu, biên dịch và mô phỏng PULP

## 1. Mục tiêu chung

Mục tiêu của project là:

1. Đọc và hiểu tổng quan kiến trúc PULP và board ZCU104.
2. Bóc tách cấu trúc repository dựa trên `README.md`, `Bender.yml` và RTL.
3. Xác định chính xác code của platform top, SoC/FC, Cluster và testbench.
4. Checkout đúng các dependency đã được khóa phiên bản.
5. Biên dịch thành công RTL simulation platform.
6. Biên dịch software test và chạy mô phỏng FC, Cluster, FC-to-Cluster.
7. Thu waveform, phân tích luồng thực thi và ghi lại kết quả có thể tái lập.
8. Đánh giá khoảng cách giữa port ZCU102 hiện tại và ZCU104.

## 2. Nguyên tắc thực hiện

- Giữ commit `b6ae54700b76395b049742ebfc52c5aaf6e148a5` làm baseline ban đầu.
- Không tự ý nâng dependency hoặc chạy `bender update` trong quá trình tái lập thiết kế.
- Dùng `Bender.lock` để xác định dependency thực tế.
- Tách riêng thay đổi tài liệu, build fix, test và FPGA port thành các commit độc lập.
- Không commit toolchain, Bender cache, simulator work library, Vivado output hoặc waveform dung lượng lớn.
- Mỗi milestone chỉ được đóng khi có bằng chứng và lệnh tái lập được.

## 3. Thứ tự milestone

### Milestone 0 — Baseline và branch làm việc

#### Mục tiêu

Tạo môi trường làm việc tách khỏi nhánh upstream và ghi lại điểm bắt đầu.

#### Công việc

- Tạo hoặc checkout branch `feature/dungpc-work`.
- Ghi lại commit, remote và trạng thái working tree.
- Thu thập link Canva, nhật ký và tài liệu đã làm trước đó nếu có.

#### Definition of Done

- Branch làm việc tồn tại.
- Commit baseline được ghi lại.
- Không có thay đổi không rõ nguồn gốc.

---

### Milestone 1 — Kiến trúc và bản đồ mã nguồn

#### Mục tiêu

Hiểu các domain của PULP và xác định cây phân cấp từ testbench xuống SoC/Cluster.

#### Công việc

1. Đọc các phần tổng quan trong `README.md`.
2. Đọc có chọn lọc `doc/datasheet.pdf`:
   - System on Chip;
   - memory map;
   - Cluster subsystem;
   - DMA và event unit;
   - SoC peripherals;
   - boot và debug/JTAG.
3. Đọc `Bender.yml` và `Bender.lock`.
4. Đọc các file local:
   - `rtl/pulp/pulp.sv`;
   - `rtl/pulp/safe_domain.sv`;
   - `rtl/pulp/soc_domain.sv`;
   - `rtl/pulp/cluster_domain.sv`;
   - `rtl/tb/tb_pulp.sv`;
   - `fpga/pulp-zcu102/rtl/xilinx_pulp.v`;
   - `fpga/pulp-zcu102/constraints/zcu102.xdc`.
5. Lập sơ đồ domain và bảng repository/module/file.
6. Sau khi dependency được checkout, xác minh lại file thật của `pulp_soc` và `pulp_cluster`.

#### Đầu ra

- [Kiến trúc và source map](pulp_architecture_and_source_map.md)
- Sơ đồ Draw.io về các domain của PULP.

#### Definition of Done

- Giải thích được `safe_domain`, `soc_domain`, `cluster_domain` và `pad_frame`.
- Giải thích được hai hướng AXI SoC↔Cluster, event và control path.
- Xác định được simulation top, platform top, SoC wrapper và Cluster wrapper.
- Xác định và kiểm chứng được file implementation thật của SoC/FC và Cluster.
- Có phân tích sơ bộ lý do port ZCU102 không dùng nguyên trạng cho ZCU104.

#### Commit đề xuất

```text
docs: document PULP architecture and RTL source map
```

---

### Milestone 2 — Dependency, toolchain và RTL build

#### Mục tiêu

Từ checkout sạch, tải đúng dependency, sinh compile script, compile RTL và elaborate thành công `tb_pulp` bằng Questa/ModelSim.

#### Công việc

1. Kiểm tra công cụ:

   ```bash
   command -v make gcc python3 curl
   command -v vsim vlog vopt vlib vmap
   ```

2. Kiểm tra Questa/ModelSim license.
3. Nạp environment:

   ```bash
   source setup/vsim.sh
   ```

4. Checkout dependency:

   ```bash
   make checkout
   ```

5. Xác minh revision của `pulp_soc` và `pulp_cluster` theo `Bender.lock`.
6. Sinh và kiểm tra compile scripts:

   ```bash
   make scripts
   rg -n "pulp_soc|pulp_cluster" sim/compile.tcl
   ```

7. Build thư viện remote bitbang.
8. Build RTL:

   ```bash
   make build
   ```

9. Xử lý lỗi theo nhóm: môi trường/license, dependency, compile order, tool compatibility, RTL warning.
10. Chạy lại từ trạng thái build sạch.

#### Definition of Done

- Questa/ModelSim hoạt động và có license.
- Dependency được checkout ở revision đã xác định.
- `sim/compile.tcl` được sinh thành công.
- `make build` trả exit code `0`.
- `tb_pulp` được optimize/elaborate thành `vopt_tb`.
- Build sạch chạy lại thành công.
- Có bản tóm tắt tool version, warning và lỗi đã xử lý.

#### Commit đề xuất

```text
docs: record RTL build environment and dependency revisions
build: fix Questa compatibility for PULP RTL
docs: document reproducible RTL build results
```

Chỉ tạo commit `build:` nếu thực sự phải sửa source hoặc build configuration.

---

### Milestone 3 — Software toolchain và FC smoke test

#### Mục tiêu

Biên dịch được chương trình RISC-V tối thiểu, nạp qua JTAG simulation và chạy thành công trên Fabric Controller.

#### Công việc

1. Cài hoặc khai báo PULP RISC-V GCC toolchain.
2. Kiểm tra:

   ```bash
   riscv32-unknown-elf-gcc --version
   ```

3. Checkout `pulp-runtime` và regression tests.
4. Build test `hello` hoặc test tuần tự nhỏ.
5. Kiểm tra ELF bằng `readelf` và `objdump`.
6. Chạy simulation với `LOAD_L2="JTAG"`.
7. Lưu UART/stdout, exit status và simulator log.

#### Definition of Done

- Software test được compile thành ELF.
- FC boot và fetch chương trình.
- Console/UART có output mong đợi.
- Test trả kết quả thành công và simulator kết thúc có kiểm soát.
- Quy trình chạy lại được bằng các lệnh đã ghi.

#### Commit đề xuất

```text
test: add reproducible FC smoke simulation
```

---

### Milestone 4 — Cluster và FC-to-Cluster simulation

#### Mục tiêu

Chứng minh Cluster hoạt động và FC có thể offload workload sang Cluster.

#### Công việc

Chạy test theo thứ tự:

1. Cluster `multicore`.
2. Parallel matrix multiplication.
3. FC-to-Cluster test, ưu tiên `fcOffload_parMatrixMul32` hoặc test tương đương.
4. Ghi lại:
   - lệnh build;
   - ELF;
   - UART/stdout;
   - exit status;
   - số core tham gia;
   - thời gian simulation;
   - lỗi và cách xử lý.

#### Definition of Done

- Cluster được cấp clock và thoát reset.
- Cluster fetch enable và boot address đúng.
- Các core mong đợi tham gia workload.
- DMA/event/interrupt hoàn tất đúng luồng.
- FC nhận được kết quả hoặc tín hiệu hoàn thành.

#### Commit đề xuất

```text
test: add cluster and FC-to-cluster simulations
```

---

### Milestone 5 — Waveform và phân tích luồng thực thi

#### Mục tiêu

Có bằng chứng waveform giải thích được hoạt động của FC, Cluster và giao tiếp giữa hai domain.

#### Công việc

1. Chạy lại một FC test và một Cluster/offload test với waveform.
2. Quan sát:
   - SoC/Cluster clock và reset;
   - FC program counter;
   - Cluster fetch enable và boot address;
   - AXI SoC→Cluster và Cluster→SoC;
   - TCDM access;
   - DMA, event, interrupt và end-of-computation.
3. Lưu ảnh hoặc bảng tín hiệu đã chú thích.
4. Không commit raw waveform dung lượng lớn trừ khi được yêu cầu.

#### Definition of Done

- Có waveform của ít nhất một test thành công.
- Các giai đoạn boot, offload, compute và completion được chỉ ra.
- Kết quả waveform khớp console log và exit status.

#### Commit đề xuất

```text
docs: add simulation waveform analysis
```

---

### Milestone 6 — Đánh giá ZCU104

#### Mục tiêu

Xác định các thay đổi cần thiết để chuyển FPGA target từ ZCU102 sang ZCU104.

#### Công việc

1. Đọc AMD ZCU104 Board User Guide UG1267.
2. So sánh:
   - FPGA part và board part;
   - reference clock;
   - reset;
   - JTAG và UART;
   - FMC routing;
   - I/O banks và I/O standards;
   - timing constraints;
   - Clocking Wizard IP.
3. Lập bảng gap analysis ZCU102→ZCU104.
4. Nếu assignment yêu cầu bitstream, tạo target riêng:

   ```text
   fpga/pulp-zcu104/
   ├── fpga-settings.mk
   ├── rtl/xilinx_pulp.v
   └── constraints/zcu104.xdc
   ```

5. Port theo thứ tự clock/reset → JTAG/UART → FMC/peripherals.

#### Definition of Done

- Có bảng khác biệt ZCU102–ZCU104.
- Xác định đầy đủ file phải tạo hoặc sửa.
- Không sử dụng nguyên trạng pin constraint của ZCU102.
- Nếu triển khai: elaboration, synthesis, DRC và timing đạt tiêu chí đã đặt.

#### Commit đề xuất

```text
docs: document ZCU102 to ZCU104 porting gaps
fpga: add initial ZCU104 target
```

Phần `fpga:` chỉ thực hiện nếu scope yêu cầu port thật.

---

### Milestone 7 — Báo cáo và bàn giao

#### Mục tiêu

Tổng hợp toàn bộ kết quả thành tài liệu có thể tái lập bởi người khác.

#### Nội dung báo cáo

- Baseline và dependency revisions.
- Kiến trúc PULP/ZCU104.
- Source/module map.
- Môi trường và tool versions.
- Lệnh checkout/build/simulation.
- Test results và waveform.
- Lỗi đã gặp và cách xử lý.
- Kết luận về ZCU104 readiness.

#### Definition of Done

- Một người khác có thể làm theo tài liệu từ checkout sạch.
- Mọi kết luận quan trọng đều có source, log hoặc waveform hỗ trợ.
- Working tree không chứa generated artifact ngoài dự kiến.

## 4. Trạng thái thực hiện

Trạng thái động của project được duy trì trong [PROJECT_STATUS.md](PROJECT_STATUS.md). File này nên được cập nhật khi:

- bắt đầu hoặc hoàn thành một milestone;
- xuất hiện blocker mới;
- dependency/tool version thay đổi;
- có build hoặc simulation result mới;
- scope ZCU104 thay đổi.

