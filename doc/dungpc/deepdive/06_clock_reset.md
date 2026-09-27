# 06 — Clock, reset và crossing

| Miền | Clock/reset từ source | Giao cắt quan trọng |
|---|---|---|
| Pad/safe | `pad_xtal_in → pad_frame.ref_clk_o`; `safe_domain.rst_no` đi thẳng từ `rst_ni`, dù có rstgen nội bộ ([top](../../../rtl/pulp/pulp.sv#L517), [safe](../../../rtl/pulp/safe_domain.sv#L495)) | pad input và ref clock vào SoC |
| SoC | `soc_clk_rst_gen` tạo SoC clock, đồng bộ nhả SoC reset ([pulp_soc](../../../.bender/git/checkouts/pulp_soc-c519334bd3ac5582/rtl/pulp_soc/pulp_soc.sv#L790)) | FC, ROM/L2, APB, uDMA control |
| Cluster | clock/reset từ SoC; `cluster_rstn_o = s_cluster_rstn && s_cluster_rstn_soc_ctrl` ([source](../../../.bender/git/checkouts/pulp_soc-c519334bd3ac5582/rtl/pulp_soc/pulp_soc.sv#L411)) | AXI hai chiều, event ID, wake |

AXI CDC có **năm queue độc lập AW/W/AR/B/R** cho mỗi chiều; `LOG_DEPTH=3` tạo 8 slot storage/channel, nhưng không chứng minh 8 transaction outstanding vì burst/bridge/tracker giới hạn riêng ([phân tích](../master_analysis/microarchitecture/micro_07_cdc_clock_reset.md#3-axi-cdc-có-năm-queue-độc-lập)). Event pulse dùng handshake/edge propagator; event ID SoC→cluster dùng Gray FIFO, nên phải kiểm riêng. `edge_propagator` có thể gộp pulse khi pending vẫn giữ 1; đây là giới hạn contract producer ([event CDC](../master_analysis/microarchitecture/micro_07_cdc_clock_reset.md#4-event-pulse-và-event-id-là-hai-protocol-khác-nhau)).

**RDC/power:** Gray FIFO yêu cầu hai reset assert phù hợp; reset một phía khi AW/W/B hoặc AR/R còn outstanding chưa có contract abort/drain được chứng minh ([reset contract](../master_analysis/microarchitecture/micro_07_cdc_clock_reset.md#6-reset-contract-và-reset-khi-còn-giao-dịch)). Cluster có clock gate, nhưng chưa có bằng chứng power switch, retention và isolation vật lý đủ để lập state `Off/Retention`. Không đồng nhất clock gating với power-down. Phép thử cần giữ request đang chờ, reset từng phía và quan sát scoreboard/timeout; trước đó chỉ nghiệm thu POR đồng thời hai phía.
