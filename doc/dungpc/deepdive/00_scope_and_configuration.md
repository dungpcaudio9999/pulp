# 00 — Phạm vi và cấu hình

## Đối tượng

Top **`tb_pulp.i_dut:pulp`**, luồng Questa của [`run_sim.sh`](../../../sw/full_system/run_sim.sh#L76). Testbench đặt `CORE_TYPE_FC=0`, `CORE_TYPE_CL=0`, `RISCY_FPU=1`, `USE_HWPE=0`, `USE_HWPE_CL=0`, `LOAD_L2=JTAG`, `STIM_FROM=JTAG` ([TB](../../../rtl/tb/tb_pulp.sv#L36)). Runner thêm `-gUSE_HWPE_CL=1`, baud 115200 và entry `0x1C008080` ([runner](../../../sw/full_system/run_sim.sh#L84)); vì thế cấu hình demo có HWPE cluster, còn TB mặc định không có. FC dùng nhánh RI5CY/RISCY, cluster 8 PE từ `NB_CORES=8` ([defines](../../../rtl/includes/pulp_soc_defines.sv#L91)).

[`pulp.sv`](../../../rtl/pulp/pulp.sv#L1156) truyền 16 bank TCDM, 64 KiB L1, 512 KiB L2 parameter, I-cache 4 KiB và **4 HWPE master port** vào `cluster_domain`; mặc định 9 port của wrapper bị override. `PULP_FPGA_EMUL` là nhánh FPGA riêng; không trộn với TB Questa. Luồng này không chọn GVSoC hoặc XSim.

## Ranh giới bằng chứng

HEAD root như [README](README.md). [Audit cũ](../../../report/domain_analysis_20260910/source_audit.json) ghi compile list và trạng thái dependency ngày 2026-09-10; [bài cấu hình](../master_analysis/architecture/deep_dive_00_effective_configuration.md) giải thích chi tiết. Trong đợt này đã đọc trực tiếp top, wrapper, decoder, bridge, timer/ITC và CDC; **chưa chạy lại compiler/simulator**. Cấu hình động không được suy từ file RTL có trong repo nhưng không instantiate.

| Source đang đọc | HEAD / SHA-256 | Trạng thái tracked khi đối chiếu |
|---|---|---|
| Root | `ce0628648cb0b7d2d29ed348a235b6b12442034a` | Runner `sw/full_system/run_sim.sh` đang có thay đổi local |
| `pulp_soc` | `d878151e0e40` | sửa local `rtl/pulp_soc/soc_interconnect.sv` |
| `pulp_cluster` | `040fc3e3b2db` | sửa local `rtl/cluster_bus_wrap.sv` |
| `cv32e40p` / `timer_unit` | `8d58109ab61e` / `3f4ee3e5b387` | không có thay đổi tracked |
| `common_cells` | `b5ec8905ed78` | sửa local `Bender.yml` |

Hash key files: `rtl/pulp/pulp.sv` `b172970b8201c1eb…`, `rtl/tb/tb_pulp.sv` `dc33426ca466e1fa…`, `sim/compile.tcl` `22ef808d9fd21d73…`, `rtl/includes/soc_mem_map.svh` `dd2986a9dddbd839…`, runner `b48411259a3e3f92…` (SHA-256, hiển thị rút gọn). Muốn tái lập byte-for-byte phải lưu đủ `sha256sum` và diff dependency trước khi build.

| Mục | Giá trị đã xác định | Hệ quả cần kiểm |
|---|---|---|
| Boot | JTAG, entry `0x1C008080` | Theo ROM→debug→fetch ứng dụng |
| FC/cluster | 1 FC, 8 PE | Tranh chấp L2 và cluster L1 |
| HWPE | SoC tắt, cluster bật bởi runner | Vùng APB HWPE SoC và clock gate cần xét riêng |
| Security SKU/lifecycle | Không tìm thấy cấu hình sản phẩm/phê duyệt | Không khẳng định secure boot hay policy hệ thống |
