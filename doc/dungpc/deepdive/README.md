# Deep dive SoC RTL PULP

Phân tích tĩnh theo [SoC RTL Analysis Guide](../../../../uni/SoC_RTL_Analysis_Guide.md), áp dụng cho **`tb_pulp.i_dut` với runner `sw/full_system/run_sim.sh`**. Root HEAD khi đọc: `ce0628648cb0b7d2d29ed348a235b6b12442034a`. Đây là kết luận từ source, không phải lượt compile/elaborate hay mô phỏng mới. Bằng chứng động cũ chỉ được dùng khi ghi rõ report và cấu hình của lượt chạy.

Quy ước: **[RTL]** nối được tới code hiện có; **[SW]** là contract phần mềm; **[SUY RA]** là hệ quả logic cần thử; **[CHƯA CHỨNG MINH]** thiếu spec, elaboration, assertion hoặc waveform tương ứng. Source trong `.bender/git/checkouts` là dependency của checkout này; không suy các biến thể khác từ cùng tên module.

## Tài liệu nền

| Bước | Tài liệu |
|---|---|
| 00–02 | [Phạm vi/cấu hình](00_scope_and_configuration.md) · [Bản đồ repo](01_repository_map.md) · [Kiến trúc](02_architecture.md) |
| 03–05 | [Giao diện](03_interfaces.md) · [Giao dịch chủ đạo](04_dominant_flow.md) · [Điều khiển và state](05_control_and_state.md) |
| 06–09 | [Clock/reset](06_clock_reset.md) · [Ca biên](07_corner_cases.md) · [Kiểm chứng](08_verification_points.md) · [Câu hỏi mở](09_open_questions.md) |

## Tài liệu SoC

| Bản đồ | Giao dịch và hệ thống |
|---|---|
| [Kết nối khối](soc_01_block_and_connectivity_map.md) | [Interconnect và ordering](soc_06_interconnect_and_ordering.md) |
| [Master–slave](soc_02_master_slave_matrix.md) | [Ranh giới bảo vệ](soc_07_security_boundaries.md) |
| [Địa chỉ](soc_03_address_map.md) | [Boot](soc_08_boot_flow.md) |
| [Ngắt/event](soc_04_interrupt_map.md) | [Kịch bản hệ thống](soc_09_system_scenarios.md) |
| [Clock/reset/power](soc_05_clock_reset_power_domains.md) | |

Các phân tích trước đây nằm ở [master_analysis](../master_analysis/README.md). Hai snapshot `evidence.json` cũ ghi hash và đường dẫn tài liệu ở thời điểm chúng được tạo; chúng không phải bằng chứng rằng source hiện tại đã được elaboration.
