# 01 — Bản đồ repository và build

| Lớp | Vị trí | Vai trò đã kiểm |
|---|---|---|
| RTL tích hợp | [`rtl/pulp/`](../../../rtl/pulp/) | `pulp`, `safe_domain`, `soc_domain`, `cluster_domain`, pad frame |
| TB | [`rtl/tb/tb_pulp.sv`](../../../rtl/tb/tb_pulp.sv#L30) | top mô phỏng, reset/JTAG/entry và monitor |
| Cấu hình/địa chỉ | [`rtl/includes/pulp_soc_defines.sv`](../../../rtl/includes/pulp_soc_defines.sv), [`soc_mem_map.svh`](../../../rtl/includes/soc_mem_map.svh#L22) | macro số core và cửa sổ decode |
| Source IP | [`.bender/git/checkouts`](../../../.bender/git/checkouts/) | `pulp_soc`, `pulp_cluster`, core, interconnect, uDMA, timer, CDC |
| Build | [`sim/compile.tcl`](../../../sim/compile.tcl), [`sim/Makefile`](../../../sim/Makefile) | filelist, defines, top/vopt |
| Software | [`sw/full_system`](../../../sw/full_system/), [`pulp-runtime`](../../../pulp-runtime/) | ELF, HAL, boot/cluster APIs |
| Bằng chứng | [`report/`](../../../report/) | log/snapshot theo phiên, không tự chứng minh checkout mới |

[TB instantiation](../../../rtl/tb/tb_pulp.sv#L689) chuyển parameter tới `pulp`; [top](../../../rtl/pulp/pulp.sv#L971) nối SoC và [cluster](../../../rtl/pulp/pulp.sv#L1156). `soc_domain` instantiate [pulp_soc](../../../rtl/pulp/soc_domain.sv#L212), `cluster_domain` instantiate [pulp_cluster](../../../rtl/pulp/cluster_domain.sv#L209). Điều này xác định cây *từ source*, chưa phải dump sau elaboration. Khi cần kết luận một module cụ thể, kiểm `sim/compile.tcl` trước: ví dụ timer được chọn từ dependency `timer_unit`, không lấy bản cùng tên khác trong `pulp_soc` ([phương pháp](../master_analysis/soc_rtl/soc_00_phuong_phap_phan_tich_rtl.md#2-chốt-source-thực-sự-được-dùng)).

**Tái lập cần ghi:** command compile/vopt, defines, parameter, HEAD của từng dependency, patch local và hash ELF/ROM. `Bender.yml` và checkout cluster có revision khác nhau theo [audit cấu hình](../master_analysis/architecture/deep_dive_00_effective_configuration.md#3-implementation-nào-nằm-trong-compile-list-rtl); không tự thay dependency để làm đẹp manifest.
