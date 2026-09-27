# FC pipeline + LSU → SoC: bằng chứng đợt 2026-09-13

Đợt đầu của [kế hoạch](../../doc/dungpc/master_analysis/microarchitecture/micro_00_plan_phan_tich_pulp.md):
[pipeline](../../doc/dungpc/master_analysis/microarchitecture/micro_01_fc_pipeline.md),
[LSU](../../doc/dungpc/master_analysis/microarchitecture/micro_02_fc_lsu.md),
[nối SoC](../../doc/dungpc/master_analysis/microarchitecture/micro_03_fc_soc_interconnect.md).

## Mức bằng chứng

- Pipeline/IF/ID/EX/WB/PMP và interconnect: đọc RTL, nối port/state và dựng
  bảng chu kỳ có giả định; chưa chạy core hoặc full-system mới.
- LSU: mô phỏng module RTL độc lập bằng Icarus Verilog 12.0, **20 checks PASS**.
  TB tự lái memory response, EX-valid và operands/split flag của beat 2.
- Không sửa RTL dependency hoặc phần mềm demo; không thay các log full_system cũ.

## Tái lập phép thử LSU

```bash
bash report/microarchitecture_20260913/run_lsu.sh
```

[run_lsu.sh](run_lsu.sh) compile đúng file LSU trong checkout cùng
[tb_fc_lsu.sv](tb_fc_lsu.sv), đặt build/log/VCD vào `/tmp/pulp-micro-lsu.*` và
in đường dẫn cụ thể. Không cần ELF, Questa library hoặc boot stimulus.

Define VERILATOR trong lệnh Icarus chỉ bỏ block SVA cuối LSU vì Icarus chưa hỗ
trợ các assertion đó; không đổi datapath/FSM. Các check procedural có `$fatal`
trong TB vẫn hoạt động. [compile.log](compile.log) có thông báo Icarus mở rộng
sensitivity list của always_comb khi gặp constant select; compile thành công.

[run.log](run.log) chép output lượt đã chạy, [lsu.vcd](lsu.vcd) lưu waveform
cùng lượt PASS 20 checks. Đây không phải waveform của CPU/full-system.

| Nhóm | Đã kiểm |
|---|---|
| Handshake | reset; chờ grant; chờ response; old response + new grant |
| Metadata | byte load cũ sign-extend đúng khi request mới là word store |
| Store completion | store còn busy/WB chưa ready tới response |
| EX stall | không reissue request đã grant; giữ rdata qua stall |
| Split | ghép word little-endian; BE/rotation của hai store beat |

Chưa kiểm: pipeline tự tạo split/hazard đúng, unsigned/halfword mọi offset,
PMP fault, reset đang có outstanding, arbiter/real SRAM, AXI/APB hay CDC.
Split-store check so payload, không có memory model chứng minh readback.
Không dùng PASS này để nhận timing/contention/ISA correctness cho cả core.

## Snapshot và kiểm tra tài liệu

[collect_evidence.py](collect_evidence.py) chỉ đọc file/git và xuất JSON stdout:

```bash
python3 report/microarchitecture_20260913/collect_evidence.py > /tmp/pulp-micro-evidence.json
diff -u report/microarchitecture_20260913/evidence.json /tmp/pulp-micro-evidence.json
```

[evidence.json](evidence.json) lưu revision/hash source được liên kết trực tiếp
trong bốn bài, input cấu hình bổ sung và test artifacts; không bao phủ mọi
dependency transitive. Compile membership là kiểm tra textual, không phải
elaboration; hash trùng không tự chứng minh hành vi.

Liên kết local/source-line, whitespace và khả năng tái tạo snapshot được kiểm
trước bàn giao. M4–M7 và kiểm chứng tích hợp M8 còn trong kế hoạch; toàn bộ
microarchitecture PULP chưa được nhận hoàn tất.
