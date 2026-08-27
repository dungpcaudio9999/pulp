# Trạng thái project PULP

## 1. Thông tin snapshot

- Ngày cập nhật: `2026-08-27`
- Repository: `pulp`
- Branch: `feature/dungpc-work`
- HEAD: `b6ae54700b76395b049742ebfc52c5aaf6e148a5`
- Upstream baseline: `b6ae547`
- Giai đoạn hiện tại: kết thúc bản nháp Milestone 1, chuẩn bị Milestone 2
- Trạng thái tổng thể: **đang thực hiện**

## 2. Tổng quan milestone

| Milestone | Nội dung | Trạng thái | Ghi chú |
|---|---|---|---|
| 0 | Baseline và branch | Hoàn thành | Branch `feature/dungpc-work` đã tồn tại tại commit baseline |
| 1 | Kiến trúc và source map | Gần hoàn thành | Đã có Markdown và Draw.io; chưa xác minh dependency local và chưa commit |
| 2 | Dependency, toolchain và RTL build | Chưa bắt đầu | Thiếu Bender và Questa/ModelSim |
| 3 | Software toolchain và FC smoke test | Chưa bắt đầu | Thiếu PULP RISC-V GCC |
| 4 | Cluster/offload simulation | Chưa bắt đầu | Phụ thuộc Milestone 2 và 3 |
| 5 | Waveform analysis | Chưa bắt đầu | Phụ thuộc test simulation thành công |
| 6 | Đánh giá/port ZCU104 | Chưa bắt đầu | Chưa có Vivado; actual port vẫn là scope tùy chọn |
| 7 | Báo cáo và bàn giao | Chưa bắt đầu | Thực hiện sau khi có build/simulation evidence |

## 3. Công việc đã hoàn thành

### Baseline

- Đã tạo/checkout branch `feature/dungpc-work`.
- Đã chốt commit ban đầu `b6ae547`.
- Branch local và remote feature branch đang cùng baseline tại lần kiểm tra gần nhất.

### Khảo sát repository

- Đã đọc `README.md`, `Bender.yml`, `Bender.lock` và các README liên quan.
- Đã xác định platform top `rtl/pulp/pulp.sv`.
- Đã xác định ba domain chính:
  - `safe_domain`;
  - `soc_domain`;
  - `cluster_domain`.
- Đã xác định simulation top `rtl/tb/tb_pulp.sv`.
- Đã xác định FPGA top hiện tại cho ZCU102 là `fpga/pulp-zcu102/rtl/xilinx_pulp.v`.
- Đã xác định `soc_domain.sv` và `cluster_domain.sv` chỉ là wrapper; implementation chính nằm trong dependency `pulp_soc` và `pulp_cluster`.
- Đã phân tích sơ bộ hai hướng asynchronous AXI, event, control, boot và status giữa SoC và Cluster.

### Artifact đã tạo

- [Kiến trúc và bản đồ mã nguồn PULP](pulp_architecture_and_source_map.md)
- Kế hoạch project: [PLAN.md](PLAN.md)
- Sơ đồ Draw.io: `/home/dungpc9/ndmoney4porche/uni/diagram/pulp_domains.drawio`

## 4. Trạng thái working tree

Tại lần kiểm tra gần nhất:

- `doc/dungpc/pulp_architecture_and_source_map.md` đang là file untracked.
- `PLAN.md` và `PROJECT_STATUS.md` mới được tạo, chưa commit.
- Sơ đồ `pulp_domains.drawio` nằm ngoài repository `pulp`, nên chưa được Git của repository này quản lý.
- Chưa có commit mới trên branch sau baseline `b6ae547`.

Lệnh kiểm tra lại:

```bash
cd /home/dungpc9/ndmoney4porche/uni/pulp
git branch --show-current
git rev-parse HEAD
git status --short
```

## 5. Trạng thái dependency

Chưa có bằng chứng dependency đã được checkout:

- chưa có executable `./bender`;
- chưa có `.bender/` cache;
- chưa có `sim/compile.tcl`;
- chưa xác minh checkout local của `pulp_soc` và `pulp_cluster`.

Revision trong `Bender.lock` cần được xác nhận sau checkout:

| Dependency | Version/revision trong lock |
|---|---|
| `pulp_soc` | version `3.0.1`, revision `d878151e0e40912642c5275d470cef76258f5fc6` |
| `pulp_cluster` | revision `040fc3e3b2dbf11ce0d08bf7554f310c483b8c9f` |

Lưu ý: `Bender.yml` yêu cầu trực tiếp revision `db2e173...` cho `pulp_cluster`, khác revision đang nằm trong `Bender.lock`. Không chạy `bender update` cho tới khi nguyên nhân và ảnh hưởng được đánh giá riêng.

## 6. Trạng thái toolchain

### Có sẵn

| Tool | Trạng thái |
|---|---|
| `make` | Có: `/usr/bin/make` |
| `gcc` | Có: `/usr/bin/gcc` |
| `python3` | Có: `/usr/bin/python3` |
| `curl` | Có: `/usr/bin/curl` |

### Chưa có trong `PATH`

| Tool | Ảnh hưởng |
|---|---|
| `vsim` | Không thể chạy/elaborate RTL simulation |
| `vlog` | Không thể compile Verilog/SystemVerilog bằng Questa/ModelSim |
| `vopt` | Không thể optimize `tb_pulp` thành `vopt_tb` |
| `vlib`, `vmap` | Không thể tạo/map simulator library |
| `vivado` | Chưa thể synthesize FPGA hoặc port ZCU104 |
| `riscv32-unknown-elf-gcc` | Chưa thể build software test cho PULP |

## 7. Build và simulation status

| Hạng mục | Trạng thái |
|---|---|
| Bender download | Chưa thực hiện |
| Dependency checkout | Chưa thực hiện |
| `make scripts` | Chưa thực hiện |
| `sim/compile.tcl` | Chưa tồn tại |
| Remote bitbang library | Chưa build |
| RTL compile | Chưa chạy |
| `tb_pulp` elaboration | Chưa chạy |
| FC software build | Chưa chạy |
| FC simulation | Chưa chạy |
| Cluster simulation | Chưa chạy |
| Waveform | Chưa có |
| ZCU104 synthesis | Chưa chạy |

## 8. Blocker hiện tại

### Blocker chính cho Milestone 2

Questa/ModelSim và các command `vsim`, `vlog`, `vopt`, `vlib`, `vmap` chưa có trong `PATH`. Chưa xác định license simulator có khả dụng hay không.

Milestone 2 chưa thể được coi là hoàn thành nếu không có simulator và license hoạt động.

### Blocker cho các milestone sau

- Chưa có PULP RISC-V GCC toolchain.
- Chưa có Vivado cho phần FPGA/ZCU104.
- Link Canva và nhật ký công việc trước đó chưa được đưa vào workspace để đối chiếu.

## 9. Next actions theo thứ tự

1. Review các file tài liệu Milestone 1.
2. Quyết định có chuyển `pulp_domains.drawio` vào `pulp/doc/dungpc` để Git quản lý hay không.
3. Commit tài liệu Milestone 1:

   ```text
   docs: document PULP architecture and project plan
   ```

4. Xác nhận Questa/ModelSim installation, `PATH` và license.
5. Chạy:

   ```bash
   source setup/vsim.sh
   make checkout
   ```

6. Xác minh revision thực tế của `pulp_soc` và `pulp_cluster`.
7. Cập nhật source map nếu đường dẫn hoặc revision thực tế khác tài liệu.
8. Chạy `make scripts` và kiểm tra `sim/compile.tcl`.
9. Chạy `make build`, lưu log và phân loại lỗi.
10. Sau khi RTL build thành công, chuyển sang cài RISC-V GCC và FC smoke test.

## 10. Tiêu chí đóng Milestone 1

Milestone 1 chỉ được chuyển sang **Hoàn thành** khi:

- tài liệu và sơ đồ đã được review;
- file SoC/Cluster thật được xác minh sau dependency checkout;
- các tài liệu cần quản lý đã được đưa vào Git;
- commit tài liệu đã được tạo;
- `PROJECT_STATUS.md` được cập nhật sang trạng thái hoàn thành.

## 11. Cách cập nhật file status

Mỗi lần cập nhật cần thay đổi tối thiểu:

1. Ngày snapshot.
2. Trạng thái milestone trong bảng tổng quan.
3. Artifact hoặc kết quả mới.
4. Blocker đã phát sinh hoặc đã giải quyết.
5. Next actions.
6. Commit/HEAD mới nếu đã commit.

