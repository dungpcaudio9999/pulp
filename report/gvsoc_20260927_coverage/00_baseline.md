# Baseline khảo sát GVSoC ngày 2026-09-27

## Phiên bản

| Thành phần | Phiên bản/cấu hình |
|---|---|
| PULP RTL | `3f06b9c` |
| GVSoC | `3b4c489` |
| PULP SDK | `d4b5bcd` |
| Target | `pulp-open` |
| Toolchain | `/opt/pulp-toolchain`, GCC 7.1.1 |
| RTL simulator | Questa 10.7c |

Luồng GVSoC phải nạp `sw/gvsoc/env.sh`. Gọi `gvsoc` trực tiếp từ shell ban đầu
thất bại vì Python của Miniforge thiếu `prettytable`; script môi trường đưa
`/usr/bin` lên trước `PATH` và giải quyết lỗi này.

## Phạm vi

Phiên chạy chỉ đánh giá target `pulp-open` đối với checkout RTL hiện tại. Nó
không chứng minh coverage của các target GVSoC khác như `rv64`, Snitch, vector
hoặc many-core.

GVSoC chạy ELF trên model C++/Python riêng, không biên dịch hay mô phỏng trực
tiếp `rtl/pulp/*.sv`. Vì vậy mọi kết luận timing trong report chỉ có hiệu lực sau
khi đối chiếu cùng ELF với RTL.

## Tình trạng môi trường

- Còn 19 GiB trên filesystem trước khi chạy.
- Smoke test, inventory và hai target I-cache chạy bằng GVSoC thành công.
- Hai RTL simulation chạy qua JTAG load và kết thúc `RUNNER|PASS (exit 0)`.
- Questa in bốn thông báo nội bộ `vsim-191` và cảnh báo DPI lúc khởi động, nhưng
  vẫn chạy test tới exit status 0; giữ nguyên trong log để truy vết.
