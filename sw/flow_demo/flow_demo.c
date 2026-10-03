/*
 * PULP execution-flow demo.
 *
 * One ELF runs unchanged on GVSoC and the RTL testbench.  The program is
 * intentionally phase-oriented: every phase has a stable noinline function
 * boundary and machine-readable FLOW markers, making instruction traces easy
 * to align with hardware waveforms.
 */

#include "pulp.h"
#include "bench/bench.h"
#include "hal/timer/timer_v2.h"
#include "hal/dma/mchan_v7.h"

#include <stdio.h>

#define FLOW_CORES              8
#define FLOW_L1_WORDS_PER_CORE 16
#define FLOW_DMA_WORDS         64
#define FLOW_MUTEX_ID           0
#define FLOW_POLL_LIMIT    200000
#define FLOW_CLUSTER_MAGIC 0x434c5553u

#define NOINLINE __attribute__((noinline))

/* L2 is visible to the FC, cluster and MCHAN external port. */
L2_DATA static unsigned int flow_l2_src[FLOW_DMA_WORDS];
L2_DATA static unsigned int flow_l2_dst[FLOW_DMA_WORDS];
L2_DATA static volatile unsigned int flow_phase_marker;
L2_DATA static volatile unsigned int flow_cluster_ran;

/* L1/TCDM is shared by the eight cluster cores and the MCHAN local port. */
L1_DATA static volatile unsigned int
    flow_l1_grid[FLOW_CORES * FLOW_L1_WORDS_PER_CORE];
L1_DATA __attribute__((aligned(32))) static unsigned int
    flow_l1_dma[FLOW_DMA_WORDS];
L1_DATA static volatile int flow_cluster_errors;
L1_DATA static volatile unsigned int flow_core_seen[FLOW_CORES];

static NOINLINE void flow_mark(int phase, const char *state, const char *name)
{
    /* This L2 store is a hardware-visible phase marker as well as a compiler
     * barrier.  Low bit is 1 at BEGIN and 2 at END. */
    flow_phase_marker = ((unsigned int)phase << 16) |
                        (state[0] == 'B' ? 1u : 2u);
    asm volatile("" ::: "memory");
    printf("FLOW|%d|%s|%s\n", phase, state, name);
}

static NOINLINE unsigned int flow_checksum(const unsigned int *data, int words)
{
    unsigned int value = 0x13579bdfu;
    for (int i = 0; i < words; ++i) {
        value ^= data[i];
        value = (value << 3) | (value >> 29);
    }
    return value;
}

static void flow_cluster_report(int errors)
{
    if (errors == 0)
        return;

    eu_mutex_lock(eu_mutex_addr(FLOW_MUTEX_ID));
    flow_cluster_errors += errors;
    eu_mutex_unlock(eu_mutex_addr(FLOW_MUTEX_ID));
}

/* ------------------------------- FC ---------------------------------- */

static NOINLINE int phase0_fc_l2(void)
{
    flow_mark(0, "BEGIN", "fc_l2");

    for (int i = 0; i < FLOW_DMA_WORDS; ++i)
        flow_l2_src[i] = 0x10203040u ^ ((unsigned int)i * 0x9e3779b1u);

    unsigned int checksum = flow_checksum(flow_l2_src, FLOW_DMA_WORDS);
    printf("FLOW|0|DATA|fc_l2|checksum=0x%08x|words=%d\n",
           checksum, FLOW_DMA_WORDS);
    flow_mark(0, "END", "fc_l2");
    return checksum == 0 ? 1 : 0;
}

static NOINLINE int phase1_fc_timer_alu(void)
{
    flow_mark(1, "BEGIN", "fc_timer_alu");

    unsigned int timer = timer_base_fc(0, 1);
    timer_reset(timer);
    timer_start(timer);
    unsigned int before = timer_count_get(timer);

    volatile unsigned int acc = 1;
    for (int i = 1; i <= 128; ++i)
        acc = (acc * 33u) ^ (unsigned int)i;

    unsigned int after = timer_count_get(timer);
    printf("FLOW|1|DATA|fc_timer_alu|timer=%u->%u|acc=0x%08x\n",
           before, after, acc);
    flow_mark(1, "END", "fc_timer_alu");
    return after <= before;
}

static NOINLINE int phase2_cluster_launch(void)
{
    flow_mark(2, "BEGIN", "cluster_launch");
    flow_cluster_ran = 0;

    int errors = bench_cluster_forward(0);
    if (flow_cluster_ran != FLOW_CLUSTER_MAGIC) {
        printf("FLOW|2|ERROR|cluster_launch|cluster_not_started|marker=0x%08x\n",
               flow_cluster_ran);
        ++errors;
    }

    printf("FLOW|2|DATA|cluster_launch|cluster_errors=%d\n", errors);
    flow_mark(2, "END", "cluster_launch");
    return errors;
}

/* ----------------------------- Cluster -------------------------------- */

static NOINLINE int phase3_cluster_l1(int core)
{
    if (core == 0)
        flow_mark(3, "BEGIN", "cluster_l1");
    synch_barrier();

    flow_core_seen[core] = 0xc0de0000u | (unsigned int)core;
    for (int i = 0; i < FLOW_L1_WORDS_PER_CORE; ++i) {
        int index = i * FLOW_CORES + core;
        flow_l1_grid[index] = ((unsigned int)core << 24) |
                              (0x005a0000u + (unsigned int)i);
    }

    /* Serializing these eight short lines makes active cores obvious in the
     * application log without interleaved printf output. */
    eu_mutex_lock(eu_mutex_addr(FLOW_MUTEX_ID));
    printf("FLOW|3|CORE|cluster_l1|pe=%d|seen=0x%08x\n",
           core, flow_core_seen[core]);
    eu_mutex_unlock(eu_mutex_addr(FLOW_MUTEX_ID));

    synch_barrier();
    if (core == 0)
        flow_mark(3, "END", "cluster_l1");
    return 0;
}

static NOINLINE int phase4_barrier_cross_read(int core)
{
    if (core == 0)
        flow_mark(4, "BEGIN", "barrier_cross_read");
    synch_barrier();

    int other = (core + 1) % FLOW_CORES;
    int errors = 0;
    for (int i = 0; i < FLOW_L1_WORDS_PER_CORE; ++i) {
        int index = i * FLOW_CORES + other;
        unsigned int expected = ((unsigned int)other << 24) |
                                (0x005a0000u + (unsigned int)i);
        if (flow_l1_grid[index] != expected) {
            errors = 1;
            break;
        }
    }

    flow_cluster_report(errors);
    synch_barrier();
    if (core == 0) {
        printf("FLOW|4|DATA|barrier_cross_read|errors=%d\n",
               flow_cluster_errors);
        flow_mark(4, "END", "barrier_cross_read");
    }
    return errors;
}

static int flow_dma_wait(int id)
{
    volatile int polls = 0;
    while ((plp_dma_status() & (1u << id)) && polls < FLOW_POLL_LIMIT)
        ++polls;
    plp_dma_counter_free(id);
    return polls < FLOW_POLL_LIMIT;
}

static NOINLINE int phase5_dma(void)
{
    flow_mark(5, "BEGIN", "dma_l2_l1_l2");

    const unsigned short bytes = FLOW_DMA_WORDS * sizeof(unsigned int);
    for (int i = 0; i < FLOW_DMA_WORDS; ++i) {
        flow_l1_dma[i] = 0;
        flow_l2_dst[i] = 0;
    }

    int id = plp_dma_extToL1((unsigned int)flow_l1_dma,
                             (mchan_ext_t)(unsigned int)flow_l2_src, bytes);
    if (!flow_dma_wait(id)) {
        printf("FLOW|5|ERROR|dma_l2_l1_l2|direction=L2_TO_L1|status=0x%08x\n",
               plp_dma_status());
        flow_mark(5, "END", "dma_l2_l1_l2");
        return 1;
    }

    id = plp_dma_l1ToExt((mchan_ext_t)(unsigned int)flow_l2_dst,
                         (unsigned int)flow_l1_dma, bytes);
    if (!flow_dma_wait(id)) {
        printf("FLOW|5|ERROR|dma_l2_l1_l2|direction=L1_TO_L2|status=0x%08x\n",
               plp_dma_status());
        flow_mark(5, "END", "dma_l2_l1_l2");
        return 1;
    }

    unsigned int src_sum = flow_checksum(flow_l2_src, FLOW_DMA_WORDS);
    unsigned int dst_sum = flow_checksum(flow_l2_dst, FLOW_DMA_WORDS);
    int errors = src_sum != dst_sum;
    for (int i = 0; i < FLOW_DMA_WORDS && !errors; ++i)
        errors = flow_l2_src[i] != flow_l2_dst[i];

    printf("FLOW|5|DATA|dma_l2_l1_l2|src=0x%08x|dst=0x%08x|bytes=%u\n",
           src_sum, dst_sum, bytes);
    flow_mark(5, "END", "dma_l2_l1_l2");
    return errors;
}

static NOINLINE int phase6_summary(int errors)
{
    flow_mark(6, "BEGIN", "summary");
    printf("FLOW|6|RESULT|%s|errors=%d|phase_marker=0x%08x\n",
           errors ? "FAIL" : "PASS", errors, flow_phase_marker);
    flow_mark(6, "END", "summary");
    return errors;
}

int main(void)
{
    if (get_cluster_id() != 0) {
        int errors = 0;
        printf("\n=== PULP execution-flow demo ===\n");
        errors += phase0_fc_l2();
        errors += phase1_fc_timer_alu();
        errors += phase2_cluster_launch();
        return phase6_summary(errors);
    }

    int core = get_core_id();
    if (core == 0) {
        flow_cluster_errors = 0;
        flow_cluster_ran = FLOW_CLUSTER_MAGIC;
        eu_mutex_init(eu_mutex_addr(FLOW_MUTEX_ID));
    }
    synch_barrier();

    phase3_cluster_l1(core);
    phase4_barrier_cross_read(core);

    if (core == 0)
        flow_cluster_report(phase5_dma());
    synch_barrier();

    return core == 0 ? flow_cluster_errors : 0;
}
