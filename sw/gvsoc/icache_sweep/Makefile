PULP_APP = test

# PULP_APP_SRCS (khong phai PULP_APP_FC_SRCS): main() duoc build cho ca FC
# lan cluster, bench_cluster_forward() goi lai main() tren 8 core cluster.
PULP_APP_SRCS = test.c

PULP_CFLAGS = -O2 -g

# Stack cluster mac dinh 2 KB; printf tren cluster can nhieu hon.
# 8 x 4 KB = 32 KB, con lai du cho du lieu L1 cua benchmark (~25 KB).
PULP_CFLAGS += -DCLUSTER_STACK_SIZE=0x1000

include $(PULP_SDK_HOME)/install/rules/pulp.mk
