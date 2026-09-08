//-----------------------------------------------------------------------------
// Title         : PULP Verilog Wrapper — ZCU104
//-----------------------------------------------------------------------------
// Description :
// Ban rut gon cua fpga/pulp-zcu102/rtl/xilinx_pulp.v cho board ZCU104.
//
// Vi sao rut gon: ban ZCU102 co 54 cong, trong do chi 10 la tin hieu loi. So
// con lai (HyperBus, camera, SDIO, QSPI, I2C, I2S) nam tren card FMC. ZCU104
// chi co FMC LPC — it chan hon FMC HPC cua ZCU102 — nen khong the anh xa
// nguyen ven. Cong khong duoc rang buoc chan se lam implementation bao loi,
// nen phai bo han thay vi de treo.
//
// Chuong trinh sw/full_system chi can UART (stdout), JTAG (nap) va GPIO/LED,
// nen tap cong nay la du. Chi tiet o doc/dungpc/zcu102-to-zcu104-gap.md muc 4.
//-----------------------------------------------------------------------------
// Copyright (C) 2013-2019 ETH Zurich, University of Bologna
// Copyright and related rights are licensed under the Solderpad Hardware
// License, Version 0.51 (the "License"); you may not use this file except in
// compliance with the License. You may obtain a copy of the License at
// http://solderpad.org/licenses/SHL-0.51. Unless required by applicable law
// or agreed to in writing, software, hardware and materials distributed under
// this License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
// CONDITIONS OF ANY KIND, either express or implied. See the License for the
// specific language governing permissions and limitations under the License.
//-----------------------------------------------------------------------------

module xilinx_pulp (
  input wire  ref_clk_p,
  input wire  ref_clk_n,

  inout wire  pad_uart_rx,
  inout wire  pad_uart_tx,

  input wire  pad_reset,

  input wire  pad_jtag_trst,
  input wire  pad_jtag_tck,
  input wire  pad_jtag_tdi,
  output wire pad_jtag_tdo,
  input wire  pad_jtag_tms,

  // LED tren pad du phong. 'inout' chu khong phai 'output' vi day la pad hai
  // chieu cua PULP: padframe tu dieu khien huong. Xem ghi chu cuoi file.
  inout wire  pad_led0,
  inout wire  pad_led1,
  inout wire  pad_led2,
  inout wire  pad_led3
);

  localparam CORE_TYPE = 0; // 0 for RISCY, 1 for ZERORISCY, 2 for MICRORISCY
  localparam USE_FPU   = 1;
  localparam USE_HWPE  = 0;

  wire        ref_clk;
  wire        reset_n;

  assign reset_n = ~pad_reset & pad_jtag_trst;

  //Differential to single ended clock conversion
  IBUFGDS #(
    .IOSTANDARD  ("LVDS" ),
    .DIFF_TERM   ("FALSE"),
    .IBUF_LOW_PWR("FALSE")
  ) i_sysclk_iobuf (
    .I (ref_clk_p),
    .IB(ref_clk_n),
    .O (ref_clk  )
  );

  // Cac pad ngoai vi khong dua ra ngoai deu de HO. Khac voi viec bo cong khoi
  // module: pad van ton tai trong padframe, chi la khong co chan FPGA nao noi
  // toi. Vivado se toi uu bo chung.
  pulp #(
    .CORE_TYPE_FC(CORE_TYPE),
    .CORE_TYPE_CL(CORE_TYPE),
    .USE_FPU     (USE_FPU  ),
    .USE_HWPE    (USE_HWPE ),
    .USE_HWPE_CL (USE_HWPE )
  ) i_pulp (
    .pad_uart_rx    (pad_uart_rx    ), //keep
    .pad_uart_tx    (pad_uart_tx    ), //keep

    .pad_reset_n    (reset_n        ),

    .pad_jtag_tck   (pad_jtag_tck   ), //keep
    .pad_jtag_tdi   (pad_jtag_tdi   ), //keep
    .pad_jtag_tdo   (pad_jtag_tdo   ), //keep
    .pad_jtag_tms   (pad_jtag_tms   ), //keep
    .pad_jtag_trst  (1'b1           ), //keep

    .pad_xtal_in    (ref_clk        ), //keep
    .pad_bootsel0   (               ), //keep
    .pad_bootsel1   (               ), //keep

    // LED: dung bon pad du phong, giong cach PULPissimo lam cho ZCU104.
    .pad_spim_csn1  (pad_led0       ),
    .pad_cam_data0  (pad_led1       ),
    .pad_cam_data1  (pad_led2       ),
    .pad_cam_data2  (pad_led3       )
  );

endmodule

// GHI CHU cho buoc bring-up:
//
// Bon pad LED o tren moi chi duoc NOI ra chan FPGA. De phan mem bat/tat duoc
// chung, con phai chon dung ham thay the (alternate) trong padmux cua
// safe_domain de pad chuyen sang che do GPIO. Viec do chua kiem chung — xem
// phase 8 cua sw/full_system.
