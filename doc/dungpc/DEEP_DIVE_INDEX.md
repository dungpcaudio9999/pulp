# Mục lục phân tích chuyên sâu RTL PULP

## Phạm vi

Bộ tài liệu này đi tiếp từ [kiến trúc và source map tổng quan](pulp_architecture_and_source_map.md), dựa trên source đang có trong checkout hiện tại. Mỗi kết luận được chia thành hai mức:

- **Đã kiểm chứng local**: có thể lần theo trực tiếp trong `rtl/pulp`, `rtl/tb`, `rtl/includes` hoặc `fpga`.
- **Ranh giới dependency**: cấu trúc sâu hơn thuộc `pulp_soc`/`pulp_cluster`; checkout hiện tại chỉ có wrapper và manifest nên không suy đoán implementation bên trong.

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
- Các output `cluster_fetch_enable_o` và `cluster_boot_addr_o` của SoC hiện được tạo ở top nhưng không nối vào wrapper Cluster. Trong `cluster_domain`, `fetch_en_i=0`, `base_addr_i='0`, `en_sa_boot_i=0`.
- Testbench JTAG không chỉ nạp chương trình: nó kiểm tra TAP/L2, halt FC, ghi DPC, nạp L2, resume core, rồi poll thanh ghi EOC tại `0x1A10_40A0`.

