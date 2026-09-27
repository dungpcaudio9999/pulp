# SoC 07 — Ranh giới bảo vệ

## Điều đã xác nhận

FC RI5CY được cấu hình `PULP_SECURE=1` ở [`fc_subsystem`](../../../.bender/git/checkouts/pulp_soc-c519334bd3ac5582/rtl/fc/fc_subsystem.sv#L124), có PMP local và trap cho PMP fetch/data fault theo [FC control plane](../master_analysis/microarchitecture/micro_09_fc_control_plane.md#4-exception-trap-và-bus-error-boundary). Nhưng `r_opc` của bus và đường PMP là hai cơ chế khác; nhánh RI5CY đang dùng không bảo đảm mọi AXI decode error thành trap tương ứng. Debug PULP TAP và RISC-V DM là master trên SoC, có đường tới L2/AXI qua arbiter ([debug path](../master_analysis/soc_rtl/soc_03_udma_debug_cluster_rtl.md#7-debug-là-master-thực-sự-của-soc)).

| Asset/đường | Enforcement thấy được | Chưa chứng minh |
|---|---|---|
| FC instruction/data | PMP trong core | policy nạp lúc boot, quyền của DMA/debug, response bus-error RI5CY |
| ROM/L2 | Decode chọn target; ROM storage | firewall theo initiator, privilege/execute policy |
| Debug access | DM/TAP và arbiter | debug authentication, lifecycle khóa, master permission |
| SoC/cluster APB | address decode | per-register privilege và denied response có side-effect suppression |
| Firmware boot | ROM/JTAG path | secure boot signature/key/root of trust |

**Không có cơ sở để gọi cấu hình này là secure SoC product.** `PULP_SECURE` ở core là parameter triển khai PMP, không phải bằng chứng có lifecycle, boot authentication hay SoC firewall. Test deny phải quan sát cùng lúc: request bị chặn trước target, target state không đổi, initiator nhận đúng response/trap, status/alert theo spec. Trước tiên cần spec quyền và đối chiếu policy từng master; xem [câu hỏi mở](09_open_questions.md).
