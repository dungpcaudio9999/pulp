# SoC 08 — Boot từ reset đến ứng dụng

| Mốc | Owner và điều kiện | Quan sát cần có |
|---|---|---|
| 1. Hard reset | TB assert `s_rst_n=0`, sau đó nhả; pad/safe chuyển reset tới SoC/cluster ([TB](../../../rtl/tb/tb_pulp.sv#L792)) | reset từng domain và clock ổn định |
| 2. Boot select | JTAG mode: `LOAD_L2=JTAG`, `STIM_FROM=JTAG`, `s_bootsel=01` ([TB](../../../rtl/tb/tb_pulp.sv#L840)) | boot FSM/chọn ROM path |
| 3. FC ROM fetch | FC reset/boot path fetch tại ROM; ROM window từ `0x1A000000` ([map](soc_03_address_map.md)) | instruction request/grant/response, PC/trace |
| 4. Debug load/halt | TB dùng JTAG/TAP nạp image vào L2, chỉnh DPC/entry, resume FC ([phân tích boot](../master_analysis/architecture/deep_dive_04_boot_debug_testbench.md#4-góc-nhìn-phần-mềm-rom--jtag-resume--main-rtl-sw)) | từng write L2, DPC, debug resume |
| 5. App entry | TB default/runner `0x1C008080`; FC fetch code L2 rồi startup→`main` ([TB](../../../rtl/tb/tb_pulp.sv#L791)) | instruction valid, runtime marker, exit code |
| 6. Cluster release | Runtime ghi boot address `0x10200040+4*p`, fetch mask `0x10200008` qua SoC→cluster AXI/CDC ([trace](../master_analysis/soc_rtl/soc_03_udma_debug_cluster_rtl.md#8-fc-store-khởi-chạy-cluster-vượt-ranh-giới-soc-ở-đâu)) | B response, PE fetch/PC, completion software |

`STANDALONE` là đường flash/ROM khác, cần model và image thích hợp; không coi đó là preload L2 trực tiếp ([TB branch](../../../rtl/tb/tb_pulp.sv#L819)). Các mốc boot và cluster release tách biệt: FC nhận B của fetch-mask store chưa chứng minh PE đã thực thi. Chưa có evidence cho authentication, lifecycle strap hoặc failure/retry policy; không thêm các mốc secure-boot của guide vào sản phẩm này khi chưa thấy implementation.
