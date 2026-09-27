/*
 * Quet kich thuoc code de thay tac dong cua I-cache cluster.
 *
 * Moi kernel la mot vong lap co than dai K lenh c.add (2 B/lenh), tuc
 * footprint ~ K*2 byte. Chay tren core 0 mot minh, roi tren ca 8 core cung
 * luc (8 core chay cung doan code, dung chung shared I-cache).
 *
 * Ky vong (I-cache cluster: L0 private 512 B/core, shared L1):
 *   footprint <= 512 B          : ~1 cycle/lenh
 *   512 B < footprint <= shared : miss L0, hit shared -> cham hon mot it
 *   footprint > shared          : miss ca shared, refill tu L2 -> cham han
 * So sanh target pulp-open (shared 2 bank x 2 KiB = 4 KiB, bang RTL) va
 * pulp-open-icache8k (sw/gvsoc/targets, shared 8 KiB).
 *
 * Build bang pulp-runtime nhu ubench_rt nen chay duoc ca tren RTL.
 */
#include "pulp.h"
#include <stdio.h>

#define N_ITER 20

#define STR_(x) #x
#define STR(x) STR_(x)

/* K lenh add trong than vong -> footprint K*2 B (lenh nen c.add) */
#define KERNEL(K)                                                       \
    static void __attribute__((noinline, aligned(64))) k_##K(int n)     \
    {                                                                   \
        asm volatile(                                                   \
            "1:\n"                                                      \
            ".rept " STR(K) "\n add t0,t0,t1\n .endr\n"                 \
            "addi %0,%0,-1\n"                                           \
            "bnez %0,1b\n"                                              \
            : "+r"(n) :: "t0", "t1");                                   \
    }

KERNEL(128)    /* 256 B  */
KERNEL(512)    /* 1 KiB  */
KERNEL(1024)   /* 2 KiB  */
KERNEL(1536)   /* 3 KiB  */
KERNEL(2048)   /* 4 KiB  */
KERNEL(3072)   /* 6 KiB  */

typedef void (*kfn_t)(int);
static const struct { kfn_t fn; int k; } kernels[] = {
    {k_128, 128}, {k_512, 512}, {k_1024, 1024},
    {k_1536, 1536}, {k_2048, 2048}, {k_3072, 3072},
};
#define NB_K (sizeof(kernels) / sizeof(kernels[0]))

typedef struct { unsigned int cycles, instr, imiss; } res_t;
L1_DATA static res_t sw_res[8];

static inline void perf_begin(void)
{
    /* counter 0 = cycle, 1 = instr, 4 = imiss */
    cpu_perf_conf_events((1 << 0) | (1 << 1) | (1 << 4));
    cpu_perf_setall(0);
    cpu_perf_conf(CSR_PCMR_ACTIVE | CSR_PCMR_SATURATE);
}

static inline void perf_end(res_t *r)
{
    cpu_perf_conf(0);
    r->cycles = cpu_perf_get(0);
    r->instr  = cpu_perf_get(1);
    r->imiss  = cpu_perf_get(4);
}

static void print_res(const char *test, int bytes, int core, res_t *r)
{
    printf("CSV,%s,%d,%d,cycles=%u,instr=%u,imiss=%u\n",
           test, bytes, core, r->cycles, r->instr, r->imiss);
}

int main(void)
{
    if (get_cluster_id() != 0) {
        printf("INFO,start\n");
        int rc = bench_cluster_forward(0);
        printf("INFO,done,rc=%d\n", rc);
        return rc;
    }

    int id = get_core_id();
    int nb = get_core_num();

    for (unsigned i = 0; i < NB_K; i++) {
        int bytes = kernels[i].k * 2;

        /* Core 0 mot minh. Chay 1 vong truoc de nap cache (warm-up) */
        if (id == 0) {
            res_t r;
            kernels[i].fn(1);
            perf_begin(); kernels[i].fn(N_ITER); perf_end(&r);
            print_res("icache_1core", bytes, 0, &r);
        }
        synch_barrier();

        /* 8 core cung chay cung kernel */
        kernels[i].fn(1);
        synch_barrier();
        perf_begin(); kernels[i].fn(N_ITER); perf_end(&sw_res[id]);
        synch_barrier();
        if (id == 0)
            for (int c = 0; c < nb; c++) print_res("icache_8core", bytes, c, &sw_res[c]);
        synch_barrier();
    }
    return 0;
}
