# Master analysis — PULP

Tài liệu phân tích được nhóm theo chủ đề. Các log, dữ liệu đo và script tái lập nằm trong [`report/`](../../../report/); các liên kết từ từng bài dẫn tới bằng chứng tương ứng. Bắt đầu với [bản đồ kiến trúc](architecture/pulp_architecture_and_source_map.md), sau đó đọc [mục lục chuyên sâu](architecture/DEEP_DIVE_INDEX.md).

Các file `evidence.json` trong `report/` là ảnh chụp lịch sử, nên vẫn ghi đường dẫn và hash tài liệu tại thời điểm thu thập. Script thu thập đã dùng đường dẫn mới cho các lần chạy tiếp theo.

## Kế hoạch và tổng kết

- [Kế hoạch PULP](project/PLAN.md)
- [Trạng thái dự án](project/PROJECT_STATUS.md)
- [Báo cáo tổng kết](project/BAO-CAO-TONG-KET.md)

## Kiến trúc và các domain

- [Bản đồ kiến trúc và mã nguồn](architecture/pulp_architecture_and_source_map.md)
- [Giải thích kiến trúc theo 6 phần](architecture/giai-thich-kien-truc-pulp-6-phan.md)
- [Mục lục phân tích chuyên sâu](architecture/DEEP_DIVE_INDEX.md)
- [Ma trận L3 closure](architecture/L3_CLOSURE.md)
- [00 — Cấu hình hiệu lực](architecture/deep_dive_00_effective_configuration.md)
- [01 — Safe domain](architecture/deep_dive_01_platform_safe_domain.md)
- [02 — SoC domain](architecture/deep_dive_02_soc_domain.md)
- [03 — Cluster và interconnect](architecture/deep_dive_03_cluster_and_interconnect.md)
- [04 — Boot, debug và testbench](architecture/deep_dive_04_boot_debug_testbench.md)
- [05 — Giao dịch xuyên domain](architecture/deep_dive_05_domain_transactions.md)

## Phân tích RTL SoC

- [00 — Phương pháp phân tích RTL](soc_rtl/soc_00_phuong_phap_phan_tich_rtl.md)
- [01 — FC, ROM và L2](soc_rtl/soc_01_fc_memory_rtl.md)
- [02 — Timer và interrupt](soc_rtl/soc_02_timer_irq_rtl.md)
- [03 — uDMA, debug và cluster](soc_rtl/soc_03_udma_debug_cluster_rtl.md)

## Microarchitecture

- [00 — Kế hoạch](microarchitecture/micro_00_plan_phan_tich_pulp.md)
- [01 — FC pipeline](microarchitecture/micro_01_fc_pipeline.md)
- [02 — FC LSU](microarchitecture/micro_02_fc_lsu.md)
- [03 — FC và SoC interconnect](microarchitecture/micro_03_fc_soc_interconnect.md)
- [04 — SoC uDMA và event](microarchitecture/micro_04_soc_udma_event.md)
- [05 — Cluster memory, DMA và event unit](microarchitecture/micro_05_cluster_memory_dma_eu.md)
- [06 — FPU và HWPE](microarchitecture/micro_06_fpu_hwpe.md)
- [07 — CDC, clock và reset](microarchitecture/micro_07_cdc_clock_reset.md)
- [08 — Kiểm chứng](microarchitecture/micro_08_validation.md)
- [09 — FC control plane](microarchitecture/micro_09_fc_control_plane.md)
- [10 — uDMA peripherals](microarchitecture/micro_10_udma_peripherals.md)
- [11 — Cluster AXI bridges](microarchitecture/micro_11_cluster_axi_bridges.md)

## Mô phỏng RTL và full system

- [Lựa chọn simulator](simulation/lua-chon-simulator.md)
- [Nhật ký mô phỏng QuestaSim](simulation/nhat-ky-mo-phong-pulp-questasim.md)
- [Kế hoạch demo full system](simulation/plan_demo.md)
- [Giải thích chương trình full_system.c](simulation/full_system-giai-thich.md)
- [Runbook chạy full system](simulation/RUNBOOK.md)

## GVSoC

- [00 — Kế hoạch và kết luận đo đạc](gvsoc/gvsoc_00_plan_do_dac.md)
- [01 — Hướng dẫn chạy](gvsoc/gvsoc_01_huong_dan_chay.md)
- [02 — Kết quả đã đo](gvsoc/gvsoc_02_ket_qua_da_do.md)

## FPGA ZCU104

- [Khoảng cách ZCU102 → ZCU104](fpga/zcu102-to-zcu104-gap.md)
- [Tài liệu board UG1267](fpga/ug1267-zcu104-eval-bd.pdf)
