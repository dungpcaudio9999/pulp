# GVSoC `pulp-open`: kết quả khảo sát ngày 2026-09-19

Báo cáo phiên làm việc (việc đã làm, file đã sửa, câu lệnh chạy lại):
[BAO_CAO_PHIEN_GVSOC.md](BAO_CAO_PHIEN_GVSOC.md).
13 phép đo, kèm lệnh chạy và kết quả:
[doc/dungpc/master_analysis/gvsoc/gvsoc_02_ket_qua_da_do.md](../../doc/dungpc/master_analysis/gvsoc/gvsoc_02_ket_qua_da_do.md).
Kết luận và giải thích: [doc/dungpc/master_analysis/gvsoc/gvsoc_00_plan_do_dac.md](../../doc/dungpc/master_analysis/gvsoc/gvsoc_00_plan_do_dac.md).
GVSoC `3b4c489`, PULP SDK `d4b5bcd`, toolchain `/opt/pulp-toolchain` (gcc 7.1.1),
Questa 10.7c.

| Thư mục | Lệnh tạo | Nội dung |
|---|---|---|
| `step1/` | `sw/gvsoc/step1_sdk_tests.sh report/gvsoc_20260919/step1` | `summary.txt` (PASS/FAIL, exit code, thời gian) và log từng test SDK |
| `step2/` | `sw/gvsoc/step2_inventory.sh report/gvsoc_20260919/step2` | `traces.txt`, `vcd_signals.txt`, `vcd_by_component.txt`, `power.csv`, `target_properties.txt`, `architecture.{dot,svg,png}` |
| `step2/analyze_insn/` | trace `cluster/pe0/insn` của `ubench_rt`, rồi `gvsoc_analyze_insn` và `sw/gvsoc/analyze/func_profile.py` | `analyze.txt` (cycle theo loại lệnh), `func_profile.txt` (cycle theo hàm) |
| `step3/` | xem `step3/cmd.txt` | `ubench_run{1,2}.csv`: `sw/gvsoc/ubench` (PMSIS), hai lần chạy giống hệt nhau |
| `step4/` | xem bên dưới | Cùng một ELF `sw/gvsoc/ubench_rt` chạy trên GVSoC (`gvsoc.log`) và RTL Questa (`rtl.log`); `compare.md` do `sw/gvsoc/analyze/compare_ubench.py` sinh ra |
| `step5/` | target `sw/gvsoc/targets/pulp-open-icache8k` | `icache_sweep_*.log`: quét kích thước code trên hai target; `ubench_rt_icache8k.log` |
| `full_system/` | `make all SKIP_HWPE=1` trong `sw/full_system`, rồi `gvsoc --target=pulp-open --binary ...` | `run.log`: phase 0–6, 8 OK; phase 7 SKIP |

Lệnh bước 4:

```bash
# GVSoC
source sw/gvsoc/env.sh
gvsoc --target=pulp-open --binary sw/gvsoc/ubench_rt/build/test/test run
# RTL (runner tự khởi động lmgrd nếu chưa chạy)
APP_DIR=$PWD/sw/gvsoc/ubench_rt SIM_TIMEOUT="200 ms" WALL_TIMEOUT=7200 \
    sw/full_system/run_sim.sh all run
```

`step4/elf.sha256` ghi hash của ELF dùng cho cả hai bên.

Ghi chú:
- `step1/cluster_fork_power.log`: bị dừng tay do sinh VCD 22 GB. File VCD đã xoá.
- Các thư mục chạy GVSoC (`run_*`, `wd_*`, `gvsoc_wd`) đã xoá `hyperflash.bin` 64 MB
  và file VCD. Trace đầy đủ được nén hoặc xoá vì sinh lại được.
- `step2/vcd_by_component.txt` do một đoạn Python inline sinh ra từ `vcd_signals.txt`;
  đoạn này chưa được đưa vào script.
- `step4/rtl.log`: 4 dòng `vsim-191` lúc nạp thiết kế cũng có trong các log PASS
  của `report/full_system_20260906/`, không ảnh hưởng kết quả.
