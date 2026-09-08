###############################################################################
# ZCU104 constraints for PULP
#
# Bang chan lay tu doc/dungpc/zcu102-to-zcu104-gap.md muc 2, doi chieu UG1267
# (ZCU104 Evaluation Board User Guide v1.1) va kiem chung ton tai tren package
# xczu7ev-ffvc1156 bang get_package_pins.
#
# CANH BAO — KHONG sao chep reference clock tu target pulpissimo-zcu104 co san
# tren may: no dat clock o F23/E23, thuoc bank 28 ma UG1267 ghi la "UART2 only
# (mostly NC pins)". Chan hop le voi package nen Vivado se build trot lot,
# nhung tren phan cung se KHONG bao gio co clock. Xem gap analysis muc 3.
###############################################################################

#######################################
#             Timing                  #
#######################################

# Reference clock 125 MHz — giong ZCU102, nen khong phai sua clocking wizard
create_clock -period 8.000 -name ref_clk [get_ports ref_clk_p]
set_property CLOCK_DEDICATED_ROUTE ANY_CMT_COLUMN [get_nets ref_clk]

# Camera va I2S khong dung trong ban port nay. Tat clock cua chung.
set_case_analysis 0 i_pulp/safe_domain_i/cam_pclk_o
set_case_analysis 0 i_pulp/safe_domain_i/i2s_slave_sck_o

## JTAG
create_clock -period 100.000 -name tck -waveform {0.000 50.000} [get_ports pad_jtag_tck]
set_input_jitter tck 1.000
set_property CLOCK_DEDICATED_ROUTE FALSE [get_nets pad_jtag_tck_IBUF_inst/O]

# minimize routing delay
set_input_delay -clock tck -clock_fall 5.000 [get_ports pad_jtag_tdi]
set_input_delay -clock tck -clock_fall 5.000 [get_ports pad_jtag_tms]
set_output_delay -clock tck 5.000 [get_ports pad_jtag_tdo]

set_max_delay -to   [get_ports pad_jtag_tdo] 20.000
set_max_delay -from [get_ports pad_jtag_tms] 20.000
set_max_delay -from [get_ports pad_jtag_tdi] 20.000

set_max_delay -datapath_only -from [get_pins i_pulp/soc_domain_i/pulp_soc_i/i_dmi_jtag/i_dmi_cdc/i_cdc_resp/i_src/data_src_q_reg*/C] -to [get_pins i_pulp/soc_domain_i/pulp_soc_i/i_dmi_jtag/i_dmi_cdc/i_cdc_resp/i_dst/data_dst_q_reg*/D] 20.000
set_max_delay -datapath_only -from [get_pins i_pulp/soc_domain_i/pulp_soc_i/i_dmi_jtag/i_dmi_cdc/i_cdc_resp/i_src/req_src_q_reg/C] -to [get_pins i_pulp/soc_domain_i/pulp_soc_i/i_dmi_jtag/i_dmi_cdc/i_cdc_resp/i_dst/req_dst_q_reg/D] 20.000
set_max_delay -datapath_only -from [get_pins i_pulp/soc_domain_i/pulp_soc_i/i_dmi_jtag/i_dmi_cdc/i_cdc_req/i_dst/ack_dst_q_reg/C] -to [get_pins i_pulp/soc_domain_i/pulp_soc_i/i_dmi_jtag/i_dmi_cdc/i_cdc_req/i_src/ack_src_q_reg/D] 20.000

# reset signal
set_false_path -from [get_ports pad_reset]
set_property CLOCK_DEDICATED_ROUTE FALSE [get_nets pad_reset_IBUF_inst/O]

# Set ASYNC_REG attribute for ff synchronizers to place them closer together and
# increase MTBF
set_property ASYNC_REG true [get_cells i_pulp/soc_domain_i/pulp_soc_i/soc_peripherals_i/i_apb_adv_timer/u_tim0/u_in_stage/r_ls_clk_sync_reg*]
set_property ASYNC_REG true [get_cells i_pulp/soc_domain_i/pulp_soc_i/soc_peripherals_i/i_apb_adv_timer/u_tim1/u_in_stage/r_ls_clk_sync_reg*]
set_property ASYNC_REG true [get_cells i_pulp/soc_domain_i/pulp_soc_i/soc_peripherals_i/i_apb_adv_timer/u_tim2/u_in_stage/r_ls_clk_sync_reg*]
set_property ASYNC_REG true [get_cells i_pulp/soc_domain_i/pulp_soc_i/soc_peripherals_i/i_apb_adv_timer/u_tim3/u_in_stage/r_ls_clk_sync_reg*]
set_property ASYNC_REG true [get_cells i_pulp/soc_domain_i/pulp_soc_i/soc_peripherals_i/i_apb_timer_unit/s_ref_clk*]
set_property ASYNC_REG true [get_cells i_pulp/soc_domain_i/pulp_soc_i/soc_peripherals_i/i_ref_clk_sync/i_pulp_sync/r_reg_reg*]
set_property ASYNC_REG true [get_cells i_pulp/soc_domain_i/pulp_soc_i/soc_peripherals_i/u_evnt_gen/r_ls_sync_reg*]

set_property ASYNC_REG true [get_cells i_pulp/cluster_domain_i/cluster_i/cluster_peripherals_i/cluster_timer_wrap_i/timer_unit_i/s_ref_clk*]

# Create asynchronous clock group between slow-clk and SoC clock. Those clocks
# are considered asynchronously and proper synchronization regs are in place
set_clock_groups -asynchronous -group [get_clocks -of_objects [get_pins i_pulp/safe_domain_i/i_slow_clk_gen/slow_clk_o]] -group [get_clocks -of_objects [get_pins i_pulp/soc_domain_i/pulp_soc_i/i_clk_rst_gen/i_fpga_clk_gen/soc_clk_o]] -group [get_clocks -of_objects [get_pins i_pulp/soc_domain_i/pulp_soc_i/i_clk_rst_gen/i_fpga_clk_gen/cluster_clk_o]]

# Create asynchronous clock group between Per Clock and SoC clock. Those clocks
# are considered asynchronously and proper synchronization regs are in place
set_clock_groups -asynchronous -group [get_clocks -of_objects [get_pins i_pulp/soc_domain_i/pulp_soc_i/i_clk_rst_gen/clk_per_o]] -group [get_clocks -of_objects [get_pins i_pulp/soc_domain_i/pulp_soc_i/i_clk_rst_gen/clk_soc_o]]

# Create asynchronous clock group between JTAG TCK and SoC clock.
set_clock_groups -asynchronous -group [get_clocks -of_objects [get_pins i_pulp/pad_jtag_tck]] -group [get_clocks -of_objects [get_pins i_pulp/soc_domain_i/pulp_soc_i/i_clk_rst_gen/clk_soc_o]]

#######################################
#            IO Settings              #
#######################################

## Sys clock — bank 68, cap clock-capable IO_L13P/N_T2L_N0_GC_QBC_68
# UG1267 Bang 3-13, net CLK_125_P / CLK_125_N, nguon la IDT8T49N287 (U182) ngo ra Q6
set_property -dict {PACKAGE_PIN H11 IOSTANDARD LVDS} [get_ports ref_clk_p]
set_property -dict {PACKAGE_PIN G11 IOSTANDARD LVDS} [get_ports ref_clk_n]

## Reset — nut CPU_RESET (SW20), bank 87 3.3V
set_property -dict {PACKAGE_PIN M11 IOSTANDARD LVCMOS33} [get_ports pad_reset]

## JTAG — PMOD0 (J55), bank 87 3.3V. UG1267 Bang 3-23.
# Kenh PL cua FT4232HL da bi chiem, nen JTAG phai ra PMOD0 va CAN ADAPTER ROI
# (Digilent HS2 hoac Olimex ARM-USB-OCD-H), khong cam USB thang duoc.
set_property -dict {PACKAGE_PIN G8 IOSTANDARD LVCMOS33} [get_ports pad_jtag_tms]
set_property -dict {PACKAGE_PIN H8 IOSTANDARD LVCMOS33} [get_ports pad_jtag_tdi]
set_property -dict {PACKAGE_PIN G7 IOSTANDARD LVCMOS33} [get_ports pad_jtag_tdo]
set_property -dict {PACKAGE_PIN H7 IOSTANDARD LVCMOS33} [get_ports pad_jtag_tck]
set_property -dict {PACKAGE_PIN G6 IOSTANDARD LVCMOS33} [get_ports pad_jtag_trst]

## UART — UART2, kenh D cua FT4232HL, bank 28 1.8V
# LUU Y: chuan IO khac ZCU102 (o do la LVCMOS33). Bank 28 la VCC1V8.
set_property -dict {PACKAGE_PIN A20 IOSTANDARD LVCMOS18} [get_ports pad_uart_rx]
set_property -dict {PACKAGE_PIN C19 IOSTANDARD LVCMOS18} [get_ports pad_uart_tx]

## LED — bank 88 3.3V, GPIO_LED_0..3
set_property -dict {PACKAGE_PIN D5 IOSTANDARD LVCMOS33} [get_ports pad_led0]
set_property -dict {PACKAGE_PIN D6 IOSTANDARD LVCMOS33} [get_ports pad_led1]
set_property -dict {PACKAGE_PIN A5 IOSTANDARD LVCMOS33} [get_ports pad_led2]
set_property -dict {PACKAGE_PIN B5 IOSTANDARD LVCMOS33} [get_ports pad_led3]
