# Bằng chứng M4–M8 — 2026-09-13

Phân tích tĩnh SoC uDMA/event, cluster, FPU/HWPE và CDC/clock/reset; kiểm chứng
component bằng Verilator. Không có simulation core/SoC/cluster đầy đủ mới.
Đọc [M8](../../doc/dungpc/master_analysis/microarchitecture/micro_08_validation.md) để xem cấu hình, số đo và phần
nghiệm thu tích hợp còn thiếu.

## Chạy lại

Từ repo root:

```bash
bash report/microarchitecture_20260913_remaining/run.sh
python3 report/microarchitecture_20260913_remaining/collect_evidence.py > report/microarchitecture_20260913_remaining/evidence.json
```

Cần Verilator với `--binary --timing`, make và C++ compiler. Build ở /tmp,
không sửa RTL checkout. `run.sh` lưu compile/run logs, VCD và version vào thư
mục report; khi chạy lại các output này được cập nhật. Binary tạm không thuộc
artifact lưu trữ; script là cách tái tạo. Các bench có watchdog và `$fatal`
nếu check sai. Tham số counter DMA 8 bit là stimulus module, không phải
MCHAN_CMD_WIDTH=10 suy từ default LEN=17/burst=256 của integration.

| Bench | Kết quả | Artifact |
|---|---|---|
| [tb_control.sv](tb_control.sv) | PASS 31 checks: TX credit, event counter, APU dispatcher, barrier, gate | [log](control_run.log), [compile](control_compile.log), [VCD](control.vcd) |
| [tb_cdc.sv](tb_cdc.sv) | PASS 64 ordered payloads; capacity 6, stall 111 source cycles | [log](cdc_run.log), [compile](cdc_compile.log), [VCD](cdc.vcd) |
| [tb_xbar.sv](tb_xbar.sv) | PASS 16 accepted / 16 checked responses; 1 vs 4 service cycles | [log](xbar_run.log), [compile](xbar_compile.log), [VCD](xbar.vcd) |
| [tb_dma_synch.sv](tb_dma_synch.sv) | PASS 12 checks: SID, two completion counters, simultaneous events | [log](dma_synch_run.log), [compile](dma_synch_compile.log), [VCD](dma_synch.vcd) |

[Tool version](tool_version.txt), [source/dependency snapshot](evidence.json).
[LSU đợt đầu](../microarchitecture_20260913/README.md) được giữ riêng.

## Phạm vi và warnings

Compile dùng `--assert -Wno-fatal`; warnings giữ nguyên trong log. Verilator
định nghĩa `VERILATOR`, nên một số SVA nguồn được guard `ifndef VERILATOR`
không chạy; các check procedural `$fatal` và scoreboard trong bench vẫn chạy.
Đây không phải assertion coverage đầy đủ của IP.

Warnings gồm thiếu timescale ở module dependency, width comparisons,
CASEINCOMPLETE và clock-cell COMBDLY. WIDTHTRUNC của isolate_cluster_o là
phát hiện RTL được phân tích tại M7; không giấu bằng sửa source. Simulation
hai trạng thái và clock model lý tưởng không xác nhận X propagation,
metastability, physical glitch/timing hay CDC/RDC constraints.

Xbar target là response fixture một chu kỳ, không phải SRAM. APU bench không
có arithmetic unit/RF; barrier/gate có bốn core input giả; CDC width 16/depth 4
kiểm common primitive, không instantiate AXI/UART wrapper; DMA chỉ instantiate
synch_unit, không kiểm payload copy. TX credit bench không instantiate
udma_tx_channels nên không chứng minh biểu thức s_stall của khối đó đúng.

## Questa preflight

Đã thử binary `/home/dungpc/questasim/bin/vsim` với:

```bash
env LM_LICENSE_FILE=27001@localhost MGLS_LICENSE_FILE=27001@localhost \
  /home/dungpc/questasim/bin/vsim -c -do quit -l /tmp/pulp-micro-vsim-preflight.log
```

Có timeout shell 15 s bao ngoài ở lần thử. Exit code 4: Unable to checkout a
license / Invalid license environment; xem [log](questa_preflight.log).
Chưa elaborate tb_pulp hoặc chạy full_system. Không đổi license server trong
lượt phân tích; kết quả component trên dùng Verilator.

Collector là inventory và kiểm link tĩnh, không phải parser/elaborator RTL.
Hash direct sources và các include được liệt kê, không nhận transitive source
closure hay chứng nhận mọi generate trong full-system đã được compile.
