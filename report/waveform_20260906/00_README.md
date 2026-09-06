# Milestone 5 — thu và phân tích waveform `2026-09-06`

Đối tượng: chương trình [sw/full_system](../../sw/full_system/) (9 phase, pass sạch).
Cách thu: [sw/full_system/wave_capture.do](../../sw/full_system/wave_capture.do).

## Cách chạy lại

```bash
cd sw/full_system && ./run_sim.sh all      # bảo đảm ELF mới nhất
# rồi chạy vsim trực tiếp với wave_capture.do (xem lệnh trong 01_thu_waveform.log)
```

Kết quả: `sw/full_system/build/full_system.vcd.gz` (4.6 MB nén, 16 tín hiệu, 18.27 ms).
VCD **không được commit** — tái tạo được và nằm trong `.gitignore`.

## Dòng thời gian

| Thời điểm | Sự kiện |
|---:|---|
| 101.0 ns | JTAG `trstn` nhả |
| 51 801.0 ns | reset hệ thống nhả |
| 53 379.4 ns | FC core busy lần đầu (chạy boot ROM / vòng chờ debug) |
| 12 844 273.4 ns | **FC fetch entry point `0x1c008080` — chương trình bắt đầu chạy** |
| 16 944 358.7 ns | **cluster core bắt đầu fetch** (phase 3 khởi động cluster) |
| 18 270 301.0 ns | testbench `$stop`, `exit_status = 0x00000000` |

## Phân bổ thời gian — phát hiện chính

| Giai đoạn | Dài (ms) | % |
|---|---:|---:|
| Reset và khởi tạo | 0.052 | 0.3% |
| **Nạp chương trình qua JTAG** | **12.792** | **70.0%** |
| FC thực thi (phase 0–2 + khởi động cluster) | 4.100 | 22.4% |
| Cluster thực thi (phase 4–7) | 1.326 | 7.3% |

**70% thời gian mô phỏng là nạp chương trình, không phải chạy nó.** Với
`-gLOAD_L2=JTAG`, testbench đẩy toàn bộ ELF qua giao thức JTAG mô phỏng từng bit. Phần
thực thi thật chỉ chiếm 29.7%.

Hệ quả: muốn rút ngắn vòng lặp debug thì đổi sang `-gLOAD_L2=STANDALONE` (nạp thẳng vào
mô hình bộ nhớ) sẽ cắt được phần lớn 12.8 ms này. Đánh đổi: không còn kiểm chứng đường
JTAG/debug — nên giữ ít nhất một lần chạy `LOAD_L2=JTAG` để bảo chứng đường nạp.

## Một mốc giả cần loại bỏ

Lần thu đầu có mốc `0.0 ns — cluster báo busy`. Đây **không phải sự kiện thật**:
`hwpe_subsystem.sv` gán cứng `assign busy_o = 1'b1`, nên tín hiệu busy ở mức cluster đã
bằng 1 ngay tại thời điểm 0, trước cả khi có clock. Đã bỏ khỏi báo cáo.

## Giới hạn của đợt đo này

- Chỉ thu 16 tín hiệu ở mức top và biên cluster/FC. Chưa thu bus instruction/data hay
  giao dịch AXI — muốn xem chi tiết giao thức thì phải mở rộng danh sách trong
  `wave_capture.do`, và dung lượng sẽ tăng nhanh.
- Chưa xác minh tín hiệu ra chân GPIO thật. Phase 8 mới chỉ chứng minh ghi/đọc lại được
  thanh ghi `PADOUT`; muốn biết có mức logic ra pad hay không thì cần thu thêm nhóm
  `pad_*` ở `tb_pulp`.

## Bẫy kỹ thuật khi viết do-file

`when` chỉ nhận biểu thức trên **tín hiệu**, không nhận biến Tcl. Viết
`when {... && $::now > 5000000}` sẽ bị Tcl thay `$::now` bằng `0` ngay lúc định nghĩa,
vsim báo `No objects found matching '0'` rồi **dừng ở prompt chờ nhập** — ở chế độ batch
nghĩa là treo vô hạn cho tới khi bị giết, không phải thoát với mã lỗi.
