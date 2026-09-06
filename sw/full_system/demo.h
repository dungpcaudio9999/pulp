#ifndef __DEMO_H__
#define __DEMO_H__

#include "pulp.h"
#include <stdio.h>

#include "demo_data.h"

/* ------------------------------------------------------------------
 * Báo cáo phase.
 *
 * Chỉ FC và core 0 của cluster được in. Tám core in đồng thời sẽ trộn
 * lẫn vào nhau và log không còn đọc được.
 * ------------------------------------------------------------------ */

#define PHASE_BEGIN(n, name)  printf("[PHASE %d] %-30s ... ", (n), (name))
#define PHASE_OK()            do { printf("OK\n");   return 0; } while (0)
#define PHASE_SKIP(why)       do { printf("SKIP (%s)\n", (why)); return 0; } while (0)

#define PHASE_FAIL(...)                                                     \
    do {                                                                    \
        printf("FAIL  ");                                                   \
        printf(__VA_ARGS__);                                                \
        printf("\n");                                                       \
        return 1;                                                           \
    } while (0)

/* ------------------------------------------------------------------
 * Poll có giới hạn.
 *
 * Mọi vòng chờ phần cứng đều phải dùng cái này. Một khối chết sẽ làm
 * treo toàn bộ mô phỏng, và trên Questa nghĩa là treo tới khi hết giờ
 * chứ không có thông báo gì.
 *
 * Trả về 1 nếu điều kiện thành true trước hạn, 0 nếu hết hạn.
 * ------------------------------------------------------------------ */
#define POLL_UNTIL(cond, limit)                                             \
    ({                                                                      \
        volatile int _n = 0;                                                \
        while (!(cond) && _n < (limit)) _n++;                               \
        (_n < (limit));                                                     \
    })

#define POLL_LIMIT 200000

/* Checksum dùng chung cho phase 1; phải khớp thuật toán sinh demo_data.c */
static inline unsigned int demo_checksum(const unsigned int *p, int n)
{
    unsigned int c = 0;
    for (int i = 0; i < n; i++) {
        c ^= p[i];
        c = (c << 1) | (c >> 31);
    }
    return c;
}

/* ------------------------------------------------------------------
 * Gom lỗi từ 8 core cluster.
 *
 * BẮT BUỘC. Runtime chỉ giữ giá trị trả về của core 0
 * (pulp-runtime/kernel/cluster.c, cluster_entry_stub). Nếu mỗi core
 * chỉ 'return' số lỗi của mình thì lỗi do core 1..7 phát hiện sẽ bị
 * vứt đi trong im lặng và bài test vẫn báo pass.
 * ------------------------------------------------------------------ */
#define CL_MUTEX_ID 0

static inline void cl_report(int n)
{
    if (n == 0) return;
    eu_mutex_lock(eu_mutex_addr(CL_MUTEX_ID));
    demo_cl_fails += n;
    eu_mutex_unlock(eu_mutex_addr(CL_MUTEX_ID));
}

/* FC */
int phase0_banner(void);
int phase1_fc_l2(void);
int phase2_timer(void);
int phase3_cluster_poweron(void);
int phase8_gpio(void);
void phase9_summary(int fails);

/* Cluster */
int phase4_barrier(void);
int phase5_tcdm(void);
int phase6_dma(void);
int phase7_hwpe(void);

#endif
