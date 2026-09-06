# Mục lục phân tích chuyên sâu RTL PULP

## Phạm vi

Bộ tài liệu này đi tiếp từ [kiến trúc và source map tổng quan](pulp_architecture_and_source_map.md), dựa trên source đang có trong checkout hiện tại. Mỗi kết luận được chia thành hai mức:

- **Đã kiểm chứng local**: có thể lần theo trực tiếp trong `rtl/pulp`, `rtl/tb`, `rtl/includes` hoặc `fpga`.
- **Ranh giới dependency**: cấu trúc sâu hơn thuộc `pulp_soc`/`pulp_cluster`.

> **Cập nhật `2026-09-06`:** dependency **đã được checkout** (`make checkout`), nên các kết
> luận từng bị đánh dấu "không suy đoán được" giờ đã kiểm chứng được trực tiếp trong
> `.bender/git/checkouts/`. Một kết luận trong bản gốc đã được chứng minh là **sai** —
> xem mục dưới.

## Thứ tự đọc đề xuất

1. [Platform top, pad frame và safe domain](deep_dive_01_platform_safe_domain.md)
2. [SoC domain và các giao diện của Fabric Controller](deep_dive_02_soc_domain.md)
3. [Cluster domain, TCDM, cache và giao tiếp SoC–Cluster](deep_dive_03_cluster_and_interconnect.md)
4. [Boot, JTAG, testbench và tiêu chí kết thúc mô phỏng](deep_dive_04_boot_debug_testbench.md)

## Cây khối đã kiểm chứng

```text
tb_pulp (simulation only)
└── i_dut: pulp
    ├── pad_frame_i: pad_frame
    ├── safe_domain_i: safe_domain
    │   └── pad_control_i: pad_control
    ├── soc_domain_i: soc_domain
    │   └── pulp_soc_i: pulp_soc              [dependency]
    └── cluster_domain_i: cluster_domain
        └── cluster_i: pulp_cluster           [dependency]
```

Các module `safe_domain_reg_if`, `rtc_clock` và `rtc_date` tồn tại trong cây source, nhưng `safe_domain_reg_if` không được instantiate bởi `safe_domain` và không nằm trong danh sách source của `Bender.yml`. Vì vậy chúng không thuộc datapath đang hoạt động của cấu hình top hiện tại.

## Các kết luận cần nhớ

- `pulp.sv` chủ yếu là integration/netlist bằng code: khai báo dây, tính độ rộng payload AXI và nối ba domain; gần như không chứa state machine xử lý.
- `safe_domain` trong revision này chủ yếu làm pad routing và reset/slow-clock adaptation; các ngõ DFT bị buộc hằng trong cấu hình thường.
- `soc_domain` là wrapper mỏng, truyền hầu hết cổng bằng `.*` vào `pulp_soc`; ngoại lệ đáng chú ý là `boot_l2_i = 0`.
- Hai hướng AXI dùng các mảng slot cùng con trỏ đọc/ghi để đi qua clock-domain boundary. Độ sâu logic là `2^LOG_DEPTH = 8` slot và con trỏ rộng 4 bit khi `LOG_DEPTH=3`.
- Đường Cluster→SoC rộng 64 bit; SoC→Cluster rộng 32 bit.
- ~~Các output `cluster_fetch_enable_o` và `cluster_boot_addr_o` không nối vào wrapper Cluster, `fetch_en_i=0` nên không kết luận được cluster có fetch hay không.~~ **Đính chính `2026-09-06`.** Quan sát về wiring là đúng (`pulp.sv:1159+` buộc `.fetch_en_i(1'b0)`, `.base_addr_i('0)`), nhưng suy luận rút ra thì sai: điều này **không chặn cluster khởi chạy**. Trong `pulp_cluster.sv`, `fetch_en_i` chỉ đi vào `cluster_peripherals_i` (dòng 762), còn fetch enable thật của core là `fetch_en_int = fetch_enable_reg_int` (dòng 550) — do FC ghi qua thanh ghi cluster control. Runtime dùng đúng đường đó: `cluster_start()` gọi `plp_ctrl_core_bootaddr_set_remote()` rồi `eoc_fetch_enable_remote()` (`pulp-runtime/kernel/cluster.c:62-95`). Đã kiểm chứng bằng mô phỏng: cả 8 core cluster chạy và in ra.
- Testbench JTAG không chỉ nạp chương trình: nó kiểm tra TAP/L2, halt FC, ghi DPC, nạp L2, resume core, rồi poll thanh ghi EOC tại `0x1A10_40A0`.


## Kết luận bổ sung từ mô phỏng thực tế `2026-09-06`

Các điểm dưới đây đến từ chạy thật chứ không phải đọc RTL, và ở vài chỗ **mâu thuẫn với
những gì đọc từ RTL hoặc từ tài liệu của dependency**:

- **HWPE mặc định KHÔNG tồn tại trong mô phỏng.** `tb_pulp.sv:42,48` đặt `USE_HWPE = 0` và
  `USE_HWPE_CL = 0`, ghi đè mặc định `1` của `pulp.sv`. Cần truyền `-gUSE_HWPE_CL=1` lúc
  `vsim`; không phải sửa testbench vì bước vopt dùng `-floatparameters+tb_pulp`.
- **Băng thông HWPE datamover thật là 12 byte/nhịp**, đo bằng thực nghiệm. Cả hai nguồn
  "chính thống" đều sai: `DATAMOVER_BW = 256/8 = 32` trong `test_datamover.c` của
  dependency, và suy từ RTL `N_MASTER_PORT = NB_HWPE_PORTS = 9` → 36 byte.
- **L1 chỉ có 64 KB** (`link.ld:7`) và stack của cả 8 core lấy từ đó. `cluster_start()`
  **return im lặng** khi `pi_l1_malloc` thất bại, khiến cluster không chạy mà bài test vẫn
  báo pass.
- **Runtime chỉ giữ giá trị trả về của core 0** (`kernel/cluster.c`, `cluster_entry_stub`),
  nên lỗi do core 1–7 phát hiện sẽ bị vứt đi nếu không gom qua biến dùng chung.
- **HAL GPIO của pulp-runtime nằm trong `#if 0`** (`hal/gpio/gpio_v3.h:35-99`) — không link
  được, phải truy cập thanh ghi trực tiếp.
- **70% thời gian mô phỏng là nạp chương trình qua JTAG**, không phải thực thi.

## Tài liệu và kết quả liên quan

| Tài liệu | Nội dung |
|---|---|
| [BAO-CAO-TONG-KET.md](BAO-CAO-TONG-KET.md) | **báo cáo tổng kết Milestone 7 — điểm vào cho người tiếp nhận** |
| [PROJECT_STATUS.md](PROJECT_STATUS.md) | trạng thái động theo milestone |
| [PLAN.md](PLAN.md) | kế hoạch tổng thể |
| [plan_demo.md](plan_demo.md) | kế hoạch chương trình 9 phase, đã thực hiện xong |
| [nhat-ky-mo-phong-pulp-questasim.md](nhat-ky-mo-phong-pulp-questasim.md) | quy trình dựng môi trường và chạy QuestaSim |
| [lua-chon-simulator.md](lua-chon-simulator.md) | **giải trình chọn Questa để mô phỏng, Vivado chỉ để sinh bitstream** |
| [zcu102-to-zcu104-gap.md](zcu102-to-zcu104-gap.md) | **gap analysis ZCU102→ZCU104, bảng chân đối chiếu UG1267** |
| [sw/full_system/README.md](../../sw/full_system/README.md) | chương trình demo và các quyết định thiết kế |
| [report/cluster_buoc0_20260906/](../../report/cluster_buoc0_20260906/) | bằng chứng cluster hoạt động |
| [report/full_system_20260906/](../../report/full_system_20260906/) | chuỗi chẩn đoán phase 7 |
| [report/waveform_20260906/](../../report/waveform_20260906/) | dòng thời gian và phân bổ thời gian |
