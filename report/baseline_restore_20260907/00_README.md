# Khôi phục baseline và làm chắc demo — `2026-09-07`

Tương ứng bước 1 và bước 2 của kế hoạch. Mục đích cuối là **board chạy**, nên
mọi thứ ở đây phục vụ việc đi tiếp tới synthesis ZCU104.

## Kết quả một dòng

Dependency và compile script đã khôi phục được trên máy này. **Hai lượt mô phỏng
thì không** — máy này không có Questa, không có toolchain RISC-V, không có
`pyelftools` (xem `01_moi_truong.log`). Các sửa đổi cho watchdog và phase 6 đã
được kiểm chứng ở mức logic, chưa kiểm chứng trên RTL.

## Các file

| File | Nội dung |
|---|---|
| `01_moi_truong.log` | Khảo sát công cụ trên máy hiện tại — cơ sở cho kết luận trên |
| `02_bender_checkout.log` | Khôi phục dependency; bẫy `make bender` khi curl hỏng |
| `03_patch_deps_scripts.log` | Hai typo trong `Bender.yml` upstream và cách xử lý |
| `04_quet_bender_yml.py` | Script quét mọi `Bender.yml` tìm đường dẫn hỏng, chạy lại được |
| `05_quet_ket_qua.log` | Kết quả quét sau khi patch: 0 đường dẫn hỏng |
| `06_watchdog_tclsh.log` | Kiểm chứng `run_and_exit` bằng tclsh với stub, 5 đường |
| `07_runner_watchdog.log` | Kiểm chứng đối số runner và watchdog wall-clock |
| `08_phase6_harness.c` | Harness host cho `phase6_dma()` |
| `09_phase6_injection.log` | Ba kết cục của phase 6 phân biệt được |
| `10_thu_lai_20260908.log` | Thử lại sau khi cài Questa + Vivado: chẩn đoán `vopt` hỏng |

## Quy trình tái lập trên máy có đủ công cụ

```bash
cd <repo>
make pulp-runtime                  # clone v0.0.15; clone trần là đủ, không cần build
rm -f bender                       # phòng khi lần cài trước hỏng giữa chừng
make bender                        # curl có thể trả 503 — kiểm tra ./bender chạy được
./bender checkout
./patch-deps                       # BẮT BUỘC, xem 03_patch_deps_scripts.log
make scripts
make build vopt                    # cần Questa

export QUESTA_HOME=...             # không còn hardcode trong run_sim.sh nữa
export PULP_RISCV_GCC_TOOLCHAIN=...

./sw/full_system/run_sim.sh                          # lượt sạch
./sw/full_system/run_sim.sh clean all run INJECT_FAULT=1      # lỗi ở core 3
./sw/full_system/run_sim.sh clean all run INJECT_FAULT_DMA=1  # lỗi dữ liệu DMA
SIM_TIMEOUT="5 ms" ./sw/full_system/run_sim.sh        # ép TIMEOUT để thử watchdog
```

Kỳ vọng: `0` cho lượt sạch, `1` cho hai lượt tiêm lỗi, `124` cho lượt ép timeout.

## Việc còn nợ

`make build` + `vopt_tb` và hai lượt mô phỏng thật chưa chạy được ở đây. Đó là
điều kiện hoàn thành còn thiếu của bước 1, và là thứ đầu tiên phải làm trên máy
có Questa.
