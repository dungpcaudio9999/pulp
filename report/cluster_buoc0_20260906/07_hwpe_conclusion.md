# Phase 7 (HWPE) — kết luận `2026-09-06`

`rtl/tb/tb_pulp.sv:48` đặt `USE_HWPE_CL = 0`, nên mặc định HWPE **không** được
instantiate trong mô phỏng.

Phép thử: nạp `vopt_tb` rồi `find instances -bydu datamover_top` / `hwpe_subsystem`.

| Cấu hình | Kết quả | Log |
|---|---|---|
| mặc định | không tìm thấy instance nào | `06_hwpe_probe_off.log` |
| `-gUSE_HWPE_CL=1` | tìm thấy cả hai | `05_hwpe_probe_on.log` |

```
/tb_pulp/i_dut/cluster_domain_i/cluster_i/hwpe_gen/hwpe_subsystem_i (hwpe_subsystem)
/tb_pulp/i_dut/cluster_domain_i/cluster_i/hwpe_gen/hwpe_subsystem_i/datamover_gen/hwpe_top_wrap_i (datamover_top)
```

## Kết luận

**Không cần sửa `tb_pulp.sv`, không cần `make build` lại.** Generic áp được ngay lúc
`vsim` vì bước vopt dùng `-floatparameters+tb_pulp` (`sim/Makefile:41`), giữ tham số ở
dạng override được lúc runtime.

Đồng thời xác nhận engine được sinh ra là `datamover_top` (không phải RBE hay MAC
engine), khớp với register map trong `hal_datamover.h`.

## Cách truyền cờ qua `make run`

`vsim_flags` trong `pulp-runtime/rules/pulpos/default_rules.mk:155` dùng `?=` rồi các
dòng `+=` phía sau. Vì vậy phải đặt qua **biến môi trường**, không phải dòng lệnh make —
biến trên dòng lệnh make sẽ ghi đè cả các `+=` và làm mất `-gLOAD_L2=JTAG`.

```bash
export vsim_flags="+ENTRY_POINT=0x1c008080 -permit_unmatched_virtual_intf \
                   -gBAUDRATE=115200 -gUSE_HWPE_CL=1"
make run
```

`?=` thấy biến đã có từ môi trường nên giữ nguyên, còn các `+=` vẫn nối thêm
`+bootmode=jtag` và `-gLOAD_L2=JTAG` như bình thường.
