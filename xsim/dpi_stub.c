// Stub DPI cho lan bring-up dau tien tren XSim.
// SimJTAG.sv luon duoc instantiate trong tb_pulp, nen xelab can symbol
// jtag_tick. Khi ENABLE_OPENOCD = 0 thi SimJTAG bi disable (enable = 0)
// va ham nay khong bao gio duoc goi -> stub la du.
// Muon dung OpenOCD that thi thay bang rtl/tb/remote_bitbang/*.c
#include "svdpi.h"

int jtag_tick(unsigned char *jtag_TCK, unsigned char *jtag_TMS,
              unsigned char *jtag_TDI, unsigned char *jtag_TRSTn,
              unsigned char jtag_TDO)
{
    (void)jtag_TDO;
    *jtag_TCK   = 0;
    *jtag_TMS   = 0;
    *jtag_TDI   = 0;
    *jtag_TRSTn = 1;
    return 0;
}