# SoC 03 — Bản đồ địa chỉ và chứng minh biên

Các range SoC interconnect dùng **end exclusive** theo [`soc_mem_map.svh`](../../../rtl/includes/soc_mem_map.svh#L22) và [wrapper](../../../.bender/git/checkouts/pulp_soc-c519334bd3ac5582/rtl/pulp_soc/soc_interconnect_wrap.sv#L182). APB node downstream dùng end inclusive; không áp cùng quy tắc khi tính offset peripheral ([phân tích APB](../master_analysis/soc_rtl/soc_02_timer_irq_rtl.md#4-hai-cấp-decode-apb-và-ba-kiểu-địa-chỉ-không-hợp-lệ)).

| Base | End inclusive | Dung lượng/cửa sổ | Target và lưu ý |
|---|---|---|---|
| `0x1A000000` | `0x1A03FFFF` | 256 KiB cửa sổ | Boot ROM vật lý 8 KiB; index bị cắt nên có alias |
| `0x1C000000` | `0x1C007FFF` | 32 KiB | L2 private bank 0 |
| `0x1C008000` | `0x1C00FFFF` | 32 KiB | L2 private bank 1; demo entry `0x1C008080` |
| `0x1C010000` | `0x1C08FFFF` | 512 KiB | 4 shared L2 banks; `(A-base>>2)&3`, row `offset>>4` |
| `0x10000000` | `0x103FFFFF` | 4 MiB | SoC→cluster AXI window |
| `0x1A100000` | `0x1A3FFFFF` | 3 MiB | AXI→AXI-Lite→APB SoC peripherals |

**Alias riêng:** FC **data** address có prefix `0x000` được remap sang `0x1C0` trước decode ([source](../../../.bender/git/checkouts/pulp_soc-c519334bd3ac5582/rtl/pulp_soc/soc_interconnect_wrap.sv#L119)); không suy mọi master đều có alias này. Cluster có alias địa chỉ riêng theo [defines](../../../rtl/includes/pulp_soc_defines.sv#L20), cần test theo view từng master. Linker có vùng sử dụng khác dung lượng vật lý; xem [đối chiếu](../master_analysis/architecture/deep_dive_02_soc_domain.md#3-hoạt-động-decode-memory-và-sự-kiện-rtl).

| Cặp biên cần thử | Kỳ vọng tĩnh |
|---|---|
| `0x1C00FFFF` / `0x1C010000` | private 1 / shared bank 0 |
| `0x1C08FFFC` / `0x1C090000` | shared bank 3 row 32767 / AXI default |
| `0x1A03FFFF` / `0x1A040000` | ROM window / không còn ROM |
| `0x1A10BFFF` / `0x1A10C000` | APB timer / APB FC HWPE window, HWPE tắt trong runner |

`0x20000000` đi AXI decode error; `0x1A107000` ở trong peripheral window nhưng không có APB slave có thể giữ `PREADY=0`, nên **hai loại invalid khác nhau** ([evidence](../master_analysis/soc_rtl/soc_02_timer_irq_rtl.md#4-hai-cấp-decode-apb-và-ba-kiểu-địa-chỉ-không-hợp-lệ)). Privilege/cacheability/executable attributes chưa có bảng hợp đồng được phê duyệt; không tự điền từ địa chỉ.
