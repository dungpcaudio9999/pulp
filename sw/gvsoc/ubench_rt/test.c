/*
 * Microbenchmark dung chung cho GVSoC va RTL (Questa).
 *
 * Build bang pulp-runtime nhu sw/full_system, nen CUNG MOT ELF chay duoc:
 *   - GVSoC: gvsoc --target=pulp-open --binary BUILD/.../test run
 *   - RTL:   APP_DIR=$PWD ../../full_system/run_sim.sh
 * Cac phep thu giong sw/gvsoc/ubench (ban PMSIS), them phep thu 8 core doc L2
 * de do tranh chap AXI ma GVSoC khong mo hinh hoa.
 *
 * Doc counter thang qua CSR 0x780+i (PCCR). Chi so 0..16 giong nhau o
 * CV32E40P RTL (riscv_cs_registers.sv: 12 counter noi bo + 5 counter ngoai
 * tu core_region.sv) va GVSoC. Counter 0 dem moi cycle khi core khong bi
 * clock-gate, nen voi vong poll no chinh la so cycle.
 *
 * Output: CSV,<test>,<tham so>,<core>,<counter>=<gia tri>,...
 */
#include "pulp.h"
#include <stdio.h>

#define N_LOOP      1000
#define N_CHASE     256
#define N_TCDM      128
#define DMA_MAX     8192
#define N_BARRIER   100
#define POLL_LIMIT  200000

static const char *evt_name[] = {
    "cycles", "instr", "ld_stall", "jr_stall", "imiss", "ld", "st", "jump",
    "branch", "btaken", "rvc", "elw", "ld_ext", "st_ext", "ld_ext_cyc",
    "st_ext_cyc", "tcdm_cont",
};
#define NB_EVTS 17
#define EVT_MASK ((1 << NB_EVTS) - 1)

typedef struct { unsigned int v[NB_EVTS]; } perf_t;

static inline void perf_begin(void)
{
    cpu_perf_conf_events(EVT_MASK);
    cpu_perf_setall(0);
    cpu_perf_conf(CSR_PCMR_ACTIVE | CSR_PCMR_SATURATE);
}

static inline void perf_end(perf_t *p)
{
    cpu_perf_conf(0);
    for (int i = 0; i < NB_EVTS; i++) p->v[i] = cpu_perf_get(i);
}

static void perf_print(const char *test, int param, int core, perf_t *p)
{
    printf("CSV,%s,%d,%d", test, param, core);
    for (int i = 0; i < NB_EVTS; i++) printf(",%s=%u", evt_name[i], p->v[i]);
    printf("\n");
}

/* ------------------------------------------------------------------ */
/* Kernel asm: so lenh co dinh, giong het ban PMSIS                     */

static void __attribute__((noinline)) k_alu(int n)
{
    asm volatile(
        "1:\n"
        "add t0,t0,t1\n add t0,t0,t1\n add t0,t0,t1\n add t0,t0,t1\n"
        "add t0,t0,t1\n add t0,t0,t1\n add t0,t0,t1\n add t0,t0,t1\n"
        "addi %0,%0,-1\n"
        "bnez %0,1b\n"
        : "+r"(n) :: "t0", "t1");
}

static void __attribute__((noinline)) k_ld_dep(volatile int *p, int n)
{
    asm volatile(
        "1:\n"
        "lw t0,0(%1)\n"
        "add t1,t1,t0\n"
        "addi %0,%0,-1\n"
        "bnez %0,1b\n"
        : "+r"(n) : "r"(p) : "t0", "t1");
}

static void __attribute__((noinline)) k_ld_indep(volatile int *p, int n)
{
    asm volatile(
        "1:\n"
        "lw t0,0(%1)\n"
        "add t1,t1,t2\n"
        "addi %0,%0,-1\n"
        "bnez %0,1b\n"
        : "+r"(n) : "r"(p) : "t0", "t1", "t2");
}

/* Pointer chase: dung ket qua load NGAY lenh sau (lw -> lw) de latency
 * khong bi an sau cac lenh khac trong vong */
static void __attribute__((noinline)) k_chase(void **p, int n)
{
    asm volatile(
        "1:\n"
        "lw %1,0(%1)\n"
        "lw %1,0(%1)\n"
        "addi %0,%0,-2\n"
        "bgtz %0,1b\n"
        : "+r"(n), "+r"(p));
}

static void __attribute__((noinline)) k_stride64(volatile int *p, int n)
{
    asm volatile(
        "1:\n"
        "lw t0,0(%1)\n"
        "addi %1,%1,64\n"
        "addi %0,%0,-1\n"
        "bnez %0,1b\n"
        : "+r"(n), "+r"(p) :: "t0");
}

static void chase_init(void **a, int n)
{
    for (int i = 0; i < n; i++) a[i] = &a[(i + 17) % n];
}

/* ------------------------------------------------------------------ */
/* Du lieu. L2_DATA/L1_DATA la macro section cua pulp-runtime            */

L2_DATA static volatile int ub_l2_word;
L2_DATA static void *ub_l2_chase[N_CHASE];
L2_DATA static int ub_l2_shared[N_TCDM * 16 + 16];
L2_DATA __attribute__((aligned(8))) static char ub_l2_dma[DMA_MAX];

L1_DATA static void *ub_l1_chase[N_CHASE];
L1_DATA __attribute__((aligned(64))) static int ub_l1_tcdm[16 * (N_TCDM + 16)];
L1_DATA __attribute__((aligned(8))) static char ub_l1_dma[DMA_MAX];
L1_DATA static perf_t ub_res[8];

static void single_core_tests(const char *who, volatile int *ld_buf, void **chase_l1)
{
    perf_t p;
    char name[24];
    int n;

#define RUN(suffix, param, body)                                        \
    do {                                                                \
        for (n = 0; who[n]; n++) name[n] = who[n];                      \
        for (int k = 0; suffix[k]; k++) name[n++] = suffix[k];          \
        name[n] = 0;                                                    \
        perf_begin(); body; perf_end(&p);                               \
        perf_print(name, param, 0, &p);                                 \
    } while (0)

    RUN("_alu", N_LOOP, k_alu(N_LOOP));
    RUN("_ld_dep", N_LOOP, k_ld_dep(ld_buf, N_LOOP));
    RUN("_ld_indep", N_LOOP, k_ld_indep(ld_buf, N_LOOP));
    chase_init(ub_l2_chase, N_CHASE);
    RUN("_chase_l2", N_CHASE, k_chase(ub_l2_chase, N_CHASE));
    if (chase_l1) {
        chase_init(chase_l1, N_CHASE);
        RUN("_chase_l1", N_CHASE, k_chase(chase_l1, N_CHASE));
    }
#undef RUN
}

/* Moi core doc N_TCDM word cach nhau 64 B, bat dau tu base + id * step */
static void multi_core_load(const char *test, volatile int *base, int step_bytes)
{
    int id = get_core_id();
    volatile int *p = (volatile int *)((char *)base + id * step_bytes);
    synch_barrier();
    perf_begin();
    k_stride64(p, N_TCDM);
    perf_end(&ub_res[id]);
    synch_barrier();
    if (id == 0)
        for (int c = 0; c < get_core_num(); c++)
            perf_print(test, N_TCDM, c, &ub_res[c]);
    synch_barrier();
}

static int dma_poll(int id)
{
    volatile int n = 0;
    while ((plp_dma_status() & (1 << id)) && n < POLL_LIMIT) n++;
    plp_dma_counter_free(id);
    return n < POLL_LIMIT;
}

static void cluster_tests(void)
{
    int id = get_core_id();
    perf_t p;

    if (id == 0) {
        printf("INFO,cluster,nb_pe=%d\n", get_core_num());
        single_core_tests("cl", ub_l1_tcdm, ub_l1_chase);
    }
    synch_barrier();

    /* TCDM: 8 core, bank rieng (step 4 B) va cung bank 0 (step 64 B) */
    multi_core_load("tcdm_diff_bank", ub_l1_tcdm, 4);
    multi_core_load("tcdm_same_bank", ub_l1_tcdm, 64);
    /* L2: 8 core cung doc L2 qua AXI */
    multi_core_load("l2_8core", ub_l2_shared, 4);

    if (id == 0) {
        for (int dir = 0; dir <= 1; dir++) {
            for (int size = 64; size <= DMA_MAX; size *= 2) {
                perf_begin();
                int cmd = dir ? plp_dma_l1ToExt((mchan_ext_t)(unsigned int)ub_l2_dma,
                                                (unsigned int)ub_l1_dma, size)
                              : plp_dma_extToL1((unsigned int)ub_l1_dma,
                                                (mchan_ext_t)(unsigned int)ub_l2_dma, size);
                int ok = dma_poll(cmd);
                perf_end(&p);
                if (!ok) printf("ERROR,dma_timeout,%d\n", size);
                perf_print(dir ? "dma_l1_to_l2" : "dma_l2_to_l1", size, 0, &p);
            }
        }
    }
    synch_barrier();

    /* Barrier 8 core; core 0 do. Core ngu trong barrier bi clock-gate nen
     * counter 0 chi dem cycle hoat dong: dung timer cluster cho tong thoi gian */
    unsigned int tb = timer_base_cl(0, 0, 0);
    if (id == 0) { timer_reset(tb); timer_start(tb); perf_begin(); }
    for (int i = 0; i < N_BARRIER; i++) synch_barrier();
    if (id == 0) {
        perf_end(&p);
        unsigned int t = timer_count_get(tb);
        printf("CSV,barrier_8core,%d,0,timer=%u", N_BARRIER, t);
        for (int i = 0; i < NB_EVTS; i++) printf(",%s=%u", evt_name[i], p.v[i]);
        printf("\n");
    }
    synch_barrier();
}

int main(void)
{
    if (get_cluster_id() != 0) {
        printf("INFO,start\n");
        single_core_tests("fc", &ub_l2_word, NULL);
        int rc = bench_cluster_forward(0);
        printf("INFO,done,rc=%d\n", rc);
        return rc;
    }

    cluster_tests();
    return 0;
}
