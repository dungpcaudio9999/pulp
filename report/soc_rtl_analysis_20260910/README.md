# Bằng chứng phân tích sâu SoC RTL — 2026-09-10

Đợt này triển khai **phân tích tĩnh có xét cấu hình, phân rã cấu trúc từ trên
xuống và lần giao dịch request/response cùng luồng điều khiển**. Không chạy
compile RTL, simulator hay formal verification mới; không sửa RTL/SW demo.

Tài liệu kết quả:

1. [Phương pháp và mẫu để phân tích source khác](../../doc/dungpc/master_analysis/soc_rtl/soc_00_phuong_phap_phan_tich_rtl.md).
2. [FC → ROM/L2: decode, arbitration, response và chu kỳ](../../doc/dungpc/master_analysis/soc_rtl/soc_01_fc_memory_rtl.md).
3. [APB timer → interrupt: bridge FSM, register, pending/ack và vector](../../doc/dungpc/master_analysis/soc_rtl/soc_02_timer_irq_rtl.md).
4. [uDMA/UART, debug và giao dịch điều khiển cluster](../../doc/dungpc/master_analysis/soc_rtl/soc_03_udma_debug_cluster_rtl.md).

## Tái tạo sổ bằng chứng

Từ root workspace:

```bash
python3 report/soc_rtl_analysis_20260910/collect_evidence.py > /tmp/pulp-soc-evidence.json
diff -u report/soc_rtl_analysis_20260910/evidence.json /tmp/pulp-soc-evidence.json
```

[collect_evidence.py](collect_evidence.py) dùng Python standard library và git,
chỉ đọc source/git rồi xuất JSON ra stdout. Chạy từ thư mục khác cũng được;
root được tìm theo vị trí script. Script yêu cầu mỗi dependency prefix có đúng
một checkout, và mọi literal anchor tồn tại; nếu không, nó dừng để người đọc
chọn lại source thay vì âm thầm lấy một bản khác.

[evidence.json](evidence.json) ghi root HEAD, HEAD/tracked status của 12 dependency,
SHA-256 và số dòng của 50 file đầu vào, vị trí literal anchor phục vụ đọc source.
Inventory textual của `sim/compile.tcl` tìm thấy **811 file RTL duy nhất,
không thiếu file nào**. Bản timer trong dependency `timer_unit` có tên trong
compile list; bản cùng tên trong `pulp_soc/rtl/components` không có tên trong list.

`explicitly_listed_rtl_in_compile_tcl=false` chỉ nói file không được liệt kê
trực tiếp bởi mẫu search. Header có thể được include gián tiếp; trường này
không tự chứng minh file hay module unused. Tương tự, anchor tồn tại không
chứng minh nhánh đó active hoặc hành vi đúng. Parameter, generate, port binding
và next-state đã được đọc riêng trong các bài phân tích.

## Kiểm tra và giới hạn

- Script thu bằng chứng chạy thành công, JSON đọc được; file/hash và anchor có
  thể đối chiếu lại bằng lệnh trên.
- Kiểm tra liên kết local, fragment heading và số dòng source trong bốn bài mới,
  mục lục, tổng quan SoC và README này.
- Kiểm tra whitespace bằng `git diff --check` và kiểm file mới.
- Bảng address/bank/row, byte-enable và chu kỳ là phép tính/suy luận từ RTL có
  giả định, không phải trace thu từ simulator.

Hash chỉ bao phủ danh sách đầu vào đã chọn; để tái lập simulation cần cả compile
environment, source/include đầy đủ, ELF/stimuli, plusargs, clock/reset và log
elaboration. [Audit domain trước đó](../domain_analysis_20260910/README.md) ghi
thêm trạng thái cấu hình chung. Log mô phỏng tháng 09-06 là bằng chứng lịch sử,
không được dùng để nhận PASS cho timer ISR hay UART/uDMA chưa chạy.

Các kết luận mới đáng chú ý: crossbar tạo valid theo grant cố định; APB node miss
có thể chờ mãi; FIFO register đọc ID đã pop; hai lớp event mask ngược polarity;
TX channel event sớm hơn serial completion; debug arbiter có fixed priority;
HAL clear bit và UART RTL cần đối chiếu khi dùng API clear. Tài liệu phân biệt
quan sát source với bug đã tái hiện và nêu tín hiệu/phép thử cần có để xác nhận.
