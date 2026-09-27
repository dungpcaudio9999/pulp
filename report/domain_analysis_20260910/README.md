# Đối chiếu domain từ source — 2026-09-10

Điểm vào tài liệu: [DEEP_DIVE_INDEX](../../doc/dungpc/master_analysis/architecture/DEEP_DIVE_INDEX.md).
Đợt này phân tích source và sửa tài liệu, **không chạy compile/elaboration/simulation**.

[`source_audit.json`](source_audit.json) lưu:

- root commit và HEAD/status của các dependency đã dùng để lần implementation;
- SHA-256 các đầu vào chính, hash nội dung source RTL được liệt kê theo dependency,
  và hash từng file tracked bị sửa local trong các dependency đó;
- target define trích từ `sim/compile.tcl`, số đường dẫn RTL duy nhất và file bị thiếu;
- word ROM ở offset `0x80`.

Hash `listed_source_content_sha256` được tính trên chuỗi các dòng
`<đường dẫn từ root>\0<SHA-256 nội dung file>\n`, sắp xếp đường dẫn, giới hạn ở các
file `.sv/.v/.vhd/.vhdl` được compile script liệt kê trực tiếp cho dependency.
Không bao gồm mọi header include hay mọi dependency gián tiếp; không dùng nó
thay manifest đầy đủ khi tái lập một lượt simulator.

## Kết quả kiểm tra tĩnh

- 811 đường dẫn RTL duy nhất trong compile script đều tồn tại.
- ROM word `0x4EC0006F` được giải mã trường opcode/rd/immediate: `jal x0,+1260`,
  từ `0x1A000080` tới `0x1A00056C`.
- Các liên kết file local trong tài liệu được cập nhật đã được kiểm tra tồn tại.
- Không thay đổi RTL, runtime, demo C hay cấu hình chạy.

## Các phát hiện dùng để sửa tài liệu

Reset output safe domain bypass kết quả synchronizer; đồng bộ reset FC nằm ở
SoC. HWPE port count hiệu lực là 4; payload datamover `4*32-32=96 bit`.
L2 có 512 KiB shared cộng 64 KiB private. Khởi động cluster đi qua register
boot/fetch; runtime completion dùng memory polling. DMA round-trip dùng một
giao diện AXI Cluster→SoC với cả read và write. Timer count và PADOUT readback
chưa chứng minh IRQ và đường I/O. `USE_FLL` trong TB chỉ chọn dòng log, còn
clock mux được điều khiển bằng JTAG confreg.

Log 2026-09-06 vẫn là bằng chứng lịch sử. Các README đi kèm đã được ghi đính
chính cho diễn giải HWPE và standalone boot; không sửa nội dung log gốc.
