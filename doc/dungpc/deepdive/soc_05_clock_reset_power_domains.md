# SoC 05 — Clock, reset và power domains

## Ba bản đồ riêng

| Domain | Clock | Reset/sequence | Trạng thái power có bằng chứng |
|---|---|---|---|
| Pad/safe | reference qua `pad_frame`, slow clock | reset input đi thẳng qua `safe_domain.rst_no`; rstgen nội bộ không phải output này | Không có power switch được chứng minh |
| SoC/FC/L2/APB | clock từ `soc_clk_rst_gen`, FLL hoặc ref tùy mux | `i_soc_rstgen` đồng bộ nhả theo SoC clock | Clock chạy; không có retention/isolation contract |
| Cluster | clock do SoC generator và gate nội bộ | reset output SoC AND với SoC-control reset; cluster đồng bộ nội bộ | Gate clock khi idle tùy `busy`, không tương đương power off |

Nguồn [pad/safe top](../../../rtl/pulp/pulp.sv#L517), [SoC reset/clock](../../../.bender/git/checkouts/pulp_soc-c519334bd3ac5582/rtl/pulp_soc/pulp_soc.sv#L790), [cluster reset AND](../../../.bender/git/checkouts/pulp_soc-c519334bd3ac5582/rtl/pulp_soc/pulp_soc.sv#L411), [cấu hình hiệu lực](../master_analysis/architecture/deep_dive_00_effective_configuration.md#5-clockreset-hiệu-lực-rtl). TB reference period `30517 ns` không phải frequency core; FLL/mux quyết định SoC/cluster clock.

## CDC/RDC

Hai AXI direction có FIFO Gray cho AW/W/AR/B/R; event ID và event pulse dùng cơ chế khác ([M7](../master_analysis/microarchitecture/micro_07_cdc_clock_reset.md#3-axi-cdc-có-năm-queue-độc-lập)). CDC module đòi reset hai phía theo contract; warm reset một phía khi outstanding chưa được chứng minh an toàn. Cluster gate có thể đóng sau bốn mẫu idle, nhưng HWPE wrapper khi hiện diện giữ busy=1; `incoming_req` ở cluster cần kiểm driver sau elaboration ([integration caveats](../master_analysis/microarchitecture/micro_07_cdc_clock_reset.md#các-khác-biệt-integration-phải-giữ-trong-kết-luận)).

**State model hiện có:** Reset → Active → clock-gated idle → Active. Không đủ dữ liệu để thêm `Off`, `Retention`, `isolation complete` hoặc wake latency tối đa. Kiểm mỗi chuyển trạng thái với transaction outstanding riêng; nếu một side reset, phải có abort/drain/retry được chỉ rõ.
