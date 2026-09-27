/*
 * Buoc 3: microbenchmark kiem tra do tin cay cua so do gvsoc.
 *
 * Moi phep thu co ket qua doan truoc duoc (xem cot "Ky vong" trong
 * doc/dungpc/master_analysis/gvsoc/gvsoc_00_plan_do_dac.md). Ket qua in ra dang
 *   CSV,<test>,<tham so>,<core>,<ten counter>=<gia tri>,...
 * de script phan tich doc lai.
 *
 * Luu y: PI_PERF_CYCLES doc tu timer DUNG CHUNG cua cluster (pos/implem/perf.h),
 * nen khi do nhieu core cung luc moi core dung PI_PERF_ACTIVE_CYCLES cua rieng no.
 */
#include "pmsis.h"
#include "pmsis/cluster/dma/cl_dma.h"
#include <stdio.h>

#define N_LOOP      1000   /* so vong cho phep thu ALU / load-use */
#define N_CHASE     256    /* so phan tu pointer chasing */
#define N_TCDM      128    /* so load moi core trong phep thu TCDM */
#define DMA_MAX     16384
#define N_BARRIER   100

/* Tat ca counter cua core; CYCLES (timer) duoc bat rieng khi can */
#define EVT_CORE ((1<<PI_PERF_ACTIVE_CYCLES) | (1<<PI_PERF_INSTR) |          \
                  (1<<PI_PERF_LD_STALL) | (1<<PI_PERF_JR_STALL) |            \
                  (1<<PI_PERF_IMISS) | (1<<PI_PERF_LD) | (1<<PI_PERF_ST) |   \
                  (1<<PI_PERF_JUMP) | (1<<PI_PERF_BRANCH) |                  \
                  (1<<PI_PERF_BTAKEN) | (1<<PI_PERF_RVC) |                   \
                  (1<<PI_PERF_LD_EXT) | (1<<PI_PERF_ST_EXT) |                \
                  (1<<PI_PERF_LD_EXT_CYC) | (1<<PI_PERF_ST_EXT_CYC) |        \
                  (1<<PI_PERF_TCDM_CONT))

static const struct { int id; const char *name; } evts[] = {
    {PI_PERF_ACTIVE_CYCLES, "active"}, {PI_PERF_INSTR, "instr"},
    {PI_PERF_LD_STALL, "ld_stall"},   {PI_PERF_JR_STALL, "jr_stall"},
    {PI_PERF_IMISS, "imiss"},         {PI_PERF_LD, "ld"},
    {PI_PERF_ST, "st"},               {PI_PERF_JUMP, "jump"},
    {PI_PERF_BRANCH, "branch"},       {PI_PERF_BTAKEN, "btaken"},
    {PI_PERF_RVC, "rvc"},             {PI_PERF_LD_EXT, "ld_ext"},
    {PI_PERF_ST_EXT, "st_ext"},       {PI_PERF_LD_EXT_CYC, "ld_ext_cyc"},
    {PI_PERF_ST_EXT_CYC, "st_ext_cyc"}, {PI_PERF_TCDM_CONT, "tcdm_cont"},
};
#define NB_EVTS (sizeof(evts)/sizeof(evts[0]))

typedef struct { unsigned int v[NB_EVTS]; unsigned int cycles; } perf_t;

static inline void perf_begin(void)
{
    pi_perf_conf(EVT_CORE | (1<<PI_PERF_CYCLES));
    pi_perf_reset();
    pi_perf_start();
}

static inline void perf_end(perf_t *p)
{
    pi_perf_stop();
    for (unsigned i = 0; i < NB_EVTS; i++) p->v[i] = pi_perf_read(evts[i].id);
    p->cycles = pi_perf_read(PI_PERF_CYCLES);
}

/* Ban khong doc timer: dung khi nhieu core do cung luc */
static inline void perf_begin_core(void)
{
    pi_perf_conf(EVT_CORE);
    cpu_perf_setall(0);
    cpu_perf_conf(PCMR_ACTIVE | PCMR_SATURATE);
}

static inline void perf_end_core(perf_t *p)
{
    cpu_perf_conf(0);
    for (unsigned i = 0; i < NB_EVTS; i++) p->v[i] = cpu_perf_get(evts[i].id);
    p->cycles = 0;
}

static void perf_print(const char *test, int param, int core, perf_t *p)
{
    printf("CSV,%s,%d,%d,cycles=%u", test, param, core, p->cycles);
    for (unsigned i = 0; i < NB_EVTS; i++) printf(",%s=%u", evts[i].name, p->v[i]);
    printf("\n");
}

/* ------------------------------------------------------------------ */
/* Kernel viet bang asm de so lenh co dinh, khong phu thuoc compiler    */

/* 8 add + addi + bnez = 10 lenh moi vong */
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

/* lw roi dung ngay ket qua: moi vong 1 hazard load-use */
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

/* Cung so lenh nhung lenh sau khong dung ket qua load */
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

/* Pointer chasing: moi load phu thuoc dia chi vao load truoc -> do latency */
static void __attribute__((noinline)) k_chase(void **p, int n)
{
    asm volatile(
        "1:\n"
        "lw %1,0(%1)\n"
        "addi %0,%0,-1\n"
        "bnez %0,1b\n"
        : "+r"(n), "+r"(p));
}

/* Doc n word, moi lan tien 64 B = 16 bank x 4 B -> luon cung mot bank */
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
    /* stride 17 phan tu: nguyen to cung nhau voi 256, di het mang */
    for (int i = 0; i < n; i++) a[i] = &a[(i + 17) % n];
}

/* ------------------------------------------------------------------ */
/* Du lieu                                                              */

static volatile int l2_word;
static void *l2_chase[N_CHASE];
static char l2_dma[DMA_MAX];

static void *l1_chase_p;
static char *l1_tcdm;
static char *l1_dma;
static perf_t l1_res[16];   /* ket qua tung core, cap phat trong L2 cho gon */

/* Cac phep thu chay tren mot core, dung chung cho FC va cluster */
static void single_core_tests(const char *who, int core, volatile int *ld_buf,
                              void **chase_l1)
{
    perf_t p;
    char name[32];

    snprintf(name, sizeof(name), "%s_alu", who);
    perf_begin(); k_alu(N_LOOP); perf_end(&p); perf_print(name, N_LOOP, core, &p);

    snprintf(name, sizeof(name), "%s_ld_dep", who);
    perf_begin(); k_ld_dep(ld_buf, N_LOOP); perf_end(&p); perf_print(name, N_LOOP, core, &p);

    snprintf(name, sizeof(name), "%s_ld_indep", who);
    perf_begin(); k_ld_indep(ld_buf, N_LOOP); perf_end(&p); perf_print(name, N_LOOP, core, &p);

    snprintf(name, sizeof(name), "%s_chase_l2", who);
    chase_init(l2_chase, N_CHASE);
    perf_begin(); k_chase(l2_chase, N_CHASE); perf_end(&p); perf_print(name, N_CHASE, core, &p);

    if (chase_l1) {
        snprintf(name, sizeof(name), "%s_chase_l1", who);
        chase_init(chase_l1, N_CHASE);
        perf_begin(); k_chase(chase_l1, N_CHASE); perf_end(&p); perf_print(name, N_CHASE, core, &p);
    }
}

/* ------------------------------------------------------------------ */
/* Cluster                                                              */

static int tcdm_same_bank;

static void pe_tcdm(void *arg)
{
    int id = pi_core_id();
    /* same bank: moi core bat dau o bank 0; khac bank: core i o bank i */
    volatile int *p = (volatile int *)(l1_tcdm + (tcdm_same_bank ? id * 64 : id * 4));
    pi_cl_team_barrier();
    perf_begin_core();
    k_stride64(p, N_TCDM);
    perf_end_core(&l1_res[id]);
}

static void pe_barrier(void *arg)
{
    int n = (int)arg;
    for (int i = 0; i < n; i++) pi_cl_team_barrier();
}

static void cluster_main(void *arg)
{
    int nb_pe = pi_cl_cluster_nb_pe_cores();
    perf_t p;
    printf("INFO,cluster,nb_pe=%d\n", nb_pe);

    single_core_tests("cl", 0, (volatile int *)l1_tcdm, (void **)l1_chase_p);

    /* TCDM: 8 core cung luc, cung bank va khac bank */
    for (tcdm_same_bank = 0; tcdm_same_bank <= 1; tcdm_same_bank++) {
        pi_cl_team_fork(nb_pe, pe_tcdm, NULL);
        for (int c = 0; c < nb_pe; c++)
            perf_print(tcdm_same_bank ? "tcdm_same_bank" : "tcdm_diff_bank", N_TCDM, c, &l1_res[c]);
    }

    /* DMA L2 -> L1 va L1 -> L2 theo kich thuoc */
    for (int dir = 0; dir <= 1; dir++) {
        for (int size = 64; size <= DMA_MAX; size *= 2) {
            pi_cl_dma_cmd_t cmd;
            perf_begin();
            pi_cl_dma_cmd((int)l2_dma, (int)l1_dma, size,
                          dir ? PI_CL_DMA_DIR_LOC2EXT : PI_CL_DMA_DIR_EXT2LOC, &cmd);
            pi_cl_dma_cmd_wait(&cmd);
            perf_end(&p);
            perf_print(dir ? "dma_l1_to_l2" : "dma_l2_to_l1", size, 0, &p);
        }
    }

    /* Barrier: tru chi phi fork (0 barrier) de ra chi phi moi barrier */
    for (int nc = 1; nc <= nb_pe; nc *= 2) {
        perf_begin(); pi_cl_team_fork(nc, pe_barrier, (void *)0); perf_end(&p);
        perf_print("fork_only", nc, 0, &p);
        perf_begin(); pi_cl_team_fork(nc, pe_barrier, (void *)N_BARRIER); perf_end(&p);
        perf_print("fork_barrier100", nc, 0, &p);
    }
}

int main(void)
{
    printf("INFO,start\n");

    /* FC: chi co L2 (khong co L1 rieng) */
    single_core_tests("fc", 0, &l2_word, NULL);

    struct pi_device cluster_dev;
    struct pi_cluster_conf conf;
    struct pi_cluster_task task;

    pi_cluster_conf_init(&conf);
    pi_open_from_conf(&cluster_dev, &conf);
    if (pi_cluster_open(&cluster_dev)) { printf("ERROR,cluster_open\n"); return -1; }

    l1_chase_p = pmsis_l1_malloc(N_CHASE * sizeof(void *));
    l1_tcdm    = pmsis_l1_malloc(64 * (N_TCDM + 16));
    l1_dma     = pmsis_l1_malloc(DMA_MAX);
    if (!l1_chase_p || !l1_tcdm || !l1_dma) { printf("ERROR,l1_malloc\n"); return -1; }

    pi_cluster_send_task_to_cl(&cluster_dev, pi_cluster_task(&task, cluster_main, NULL));
    pi_cluster_close(&cluster_dev);

    printf("INFO,done\n");
    return 0;
}
