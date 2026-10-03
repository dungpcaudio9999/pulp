PULP_APP = flow_demo

# main() is built for both the FC and the cluster. bench_cluster_forward()
# invokes the same entry point on all 8 cluster cores.
PULP_APP_SRCS = flow_demo.c

# Keep debug information for PC -> C source mapping. Phase functions are also
# marked noinline so their boundaries remain visible in both trace backends.
PULP_CFLAGS = -O2 -g

# 8 x 4 KiB = 32 KiB, leaving enough of the 64 KiB L1 for demo buffers.
PULP_CFLAGS += -DCLUSTER_STACK_SIZE=0x1000

include $(PULP_SDK_HOME)/install/rules/pulp.mk
