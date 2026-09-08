PULP_APP = test

# PULP_APP_SRCS (khac PULP_APP_FC_SRCS cua bai hello) khien main() duoc
# build cho ca FC lan cluster — do la co che offload cua pulp-runtime.
PULP_APP_SRCS = full_system.c demo_data.c

PULP_CFLAGS = -O2 -g

# Stack moi core cluster mac dinh chi 0x800 = 2 KB
# (pulp-runtime/include/pulp.h:21). Bien 'stackSize' trong Makefile cua cac
# regression test cu la cua SDK cu va bi pulp-runtime BO QUA hoan toan.
# Tran stack o day khong gay crash, no am tham lam hong du lieu o L1 ke ben.
# L1 chi co 0x0000fffc ~ 64 KB (link.ld:7). cluster_start() cap phat
# 8 * CLUSTER_STACK_SIZE tu L1; dat 0x2000 thanh ra can dung 64 KB va malloc
# HONG. Khi hong no 'return' im lang TRUOC dong 'cluster_running = 1'
# (kernel/cluster.c:83-87), nen cluster_wait() tra ve 0 ngay va cluster khong
# he chay -- ma test van bao pass. 0x1000 => 8 * 4 KB = 32 KB, con du cho.
PULP_CFLAGS += -DCLUSTER_STACK_SIZE=0x1000

# Phep thu nguoc: 'make ... INJECT_FAULT=1' pha hong du lieu cua core 3.
# Dung bien rieng chu KHONG ghi de PULP_CFLAGS tren dong lenh -- lam vay se
# xoa mat cac define ma rule cua runtime them vao bang '+=' (PULP_CHIP_STR...)
# va build hong voi loi 'archi/chips/PULP_CHIP_STR/pulp.h: No such file'.
ifdef INJECT_FAULT
PULP_CFLAGS += -DDEMO_INJECT_FAULT_CORE3
endif

# Phep thu nguoc cho phase 6: 'make ... INJECT_FAULT_DMA=1' cat ngan luot DMA
# ve 2 word. DMA van bao xong, chi thieu du lieu -- de chung minh phase 6 doi
# chieu du lieu that chu khong phai chi doc thanh ghi trang thai MCHAN.
ifdef INJECT_FAULT_DMA
PULP_CFLAGS += -DDEMO_INJECT_FAULT_DMA
endif

# Build cho FPGA: make all PLATFORM=fpga io=uart
ifeq ($(PLATFORM),fpga)
PULP_CFLAGS += -DDEMO_PLATFORM_FPGA=1
endif

include $(PULP_SDK_HOME)/install/rules/pulp.mk
