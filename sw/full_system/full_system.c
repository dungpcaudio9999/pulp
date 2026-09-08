/* ------------------------------------------------------------------------
 * PULP full-system demo — một chương trình C đánh thức lần lượt từng khối.
 *
 * main() chạy hai lần: lần đầu trên FC (cluster id = 31), lần sau trên cả 8
 * core cluster, do bench_cluster_forward() gọi lại chính main().
 *
 * Xem doc/dungpc/plan_demo.md. Hai điều dễ sai nhất đã được xử lý ở đây:
 *   1. Lỗi ở core 1..7 phải gom qua cl_report(), nếu không sẽ bị nuốt mất.
 *   2. Stack mỗi core cluster mặc định chỉ 2 KB — xem Makefile.
 * ---------------------------------------------------------------------- */

#include "demo.h"
#include "demo_data.h"
#include "hal_datamover.h"

#include "bench/bench.h"
#include "hal/timer/timer_v2.h"
#include "archi/gpio/gpio_v3.h"
#include "hal/dma/mchan_v7.h"

/* ======================= FC =========================================== */

int phase0_banner(void)
{
    PHASE_BEGIN(0, "FC, L2, duong stdout");
    printf("\n");
    printf("          cluster_id=%d core_id=%d nb_pe=%d\n",
           get_cluster_id(), get_core_id(), get_core_num());
    printf("[PHASE 0] %-30s ... OK\n", "FC, L2, duong stdout");
    return 0;
}

int phase1_fc_l2(void)
{
    PHASE_BEGIN(1, "FC core, L2, SoC interco");
    unsigned int c = demo_checksum(demo_l2_src, DEMO_L2_WORDS);
    if (c != DEMO_L2_GOLDEN)
        PHASE_FAIL("checksum L2 = 0x%08x, mong doi 0x%08x", c, DEMO_L2_GOLDEN);
    PHASE_OK();
}

int phase2_timer(void)
{
    PHASE_BEGIN(2, "APB timer, FC clock");

    unsigned int base = timer_base_fc(0, 1);
    timer_reset(base);
    timer_start(base);

    unsigned int t0 = timer_count_get(base);
    for (volatile int i = 0; i < 200; i++) { }
    unsigned int t1 = timer_count_get(base);

    if (t1 == t0)
        PHASE_FAIL("timer dung yen tai %u", t0);
    if (t1 < t0)
        PHASE_FAIL("timer chay lui: %u -> %u", t0, t1);
    PHASE_OK();
}

int phase3_cluster_poweron(void)
{
    PHASE_BEGIN(3, "PMU, cluster clk/rst, AXI");
    printf("\n");

    demo_cl_ran = 0;

    /* Trả về giá trị main() trả từ phía cluster, tức tổng lỗi phase 4..7 */
    int cl = bench_cluster_forward(0);

    printf("[PHASE 3] %-30s ... ", "PMU, cluster clk/rst, AXI");

    /* Không được tin mỗi giá trị trả về. cluster_start() 'return' im lặng khi
     * pi_l1_malloc cho stack thất bại, và khi đó cluster_wait() trả về 0 —
     * y hệt một lần chạy thành công. Sentinel phân biệt hai trường hợp. */
    if (demo_cl_ran != DEMO_CL_RAN_MAGIC)
        PHASE_FAIL("cluster khong he chay (sentinel=0x%08x). Nhieu kha nang "
                   "cap phat stack L1 that bai: kiem tra CLUSTER_STACK_SIZE",
                   demo_cl_ran);
    if (cl != 0)
        PHASE_FAIL("cluster bao %d loi o phase 4-7", cl);
    PHASE_OK();
}

int phase8_gpio(void)
{
    PHASE_BEGIN(8, "GPIO, safe domain padmux");

    /* Truy cap thanh ghi truc tiep, khong dung hal_gpio_*: toan bo khoi HAL
     * GPIO trong pulp-runtime nam trong '#if 0' (hal/gpio/gpio_v3.h:35-99)
     * nen khong link duoc. Bai regression peripherals/spim_flash cung tu
     * viet helper rieng vi ly do nay. */
    const unsigned int paddir = ARCHI_GPIO_ADDR + GPIO_PADDIR_OFFSET;
    const unsigned int padout = ARCHI_GPIO_ADDR + GPIO_PADOUT_OFFSET;

    unsigned int dir_save = pulp_read32(paddir);
    unsigned int out_save = pulp_read32(padout);

    const unsigned int pattern = 0x0000A5A5u;
    pulp_write32(paddir, 0xFFFFFFFFu);      /* toan bo thanh output */
    pulp_write32(padout, pattern);
    unsigned int rb = pulp_read32(padout);

    pulp_write32(padout, out_save);
    pulp_write32(paddir, dir_save);

    if (rb != pattern)
        PHASE_FAIL("padout doc lai 0x%08x, da ghi 0x%08x", rb, pattern);

#ifdef DEMO_PLATFORM_FPGA
    printf("OK  (luu y: zcu102.xdc chua noi LED nao ra ngoai)\n");
    return 0;
#else
    PHASE_OK();
#endif
}

void phase9_summary(int fails)
{
    printf("\n==== FULL-SYSTEM SUMMARY: %s (%d phase loi)\n",
           fails ? "FAIL" : "SUCCESS", fails);
}

/* ======================= Cluster ====================================== */

int phase4_barrier(void)
{
    int me = get_core_id();

    demo_cl_seen[me] = 0xC0DE0000 | me;

    /* Moi core in mot dong, tuan tu hoa bang mutex de khong bi tron lan.
     * Day la bang chung truc quan ma plan_demo.md yeu cau: log phai co du
     * CL0_PE0 den CL0_PE7. */
    eu_mutex_lock(eu_mutex_addr(CL_MUTEX_ID));
    printf("          core %d dang chay\n", me);
    eu_mutex_unlock(eu_mutex_addr(CL_MUTEX_ID));

    synch_barrier();

    if (me != 0) return 0;

    for (int i = 0; i < DEMO_L1_SLOTS; i++)
        if (demo_cl_seen[i] != (int)(0xC0DE0000u | i)) {
            PHASE_BEGIN(4, "8 core, event unit, barrier");
            PHASE_FAIL("core %d khong ghi duoc (doc 0x%08x)", i, demo_cl_seen[i]);
        }

    PHASE_BEGIN(4, "8 core, event unit, barrier");
    PHASE_OK();
}

int phase5_tcdm(void)
{
    int me = get_core_id();

    /* Chốt số lỗi trước khi vào phase, để cuối phase biết được phase NÀY gây
     * ra bao nhiêu lỗi chứ không lẫn với phase trước. */
    int before = demo_cl_fails;

    /* Mỗi core ghi slot riêng, xen kẽ nhau trên toàn dải demo_l1_grid */
    for (int i = 0; i < DEMO_L1_WORDS_PER_SLOT; i++)
        demo_l1_grid[i * DEMO_L1_SLOTS + me] = (me << 16) | i;

#ifdef DEMO_INJECT_FAULT_CORE3
    /* Pha hong co chu dich tren core 3 (khac core 0). Dung de chung minh loi
     * do core != 0 phat hien van truyen duoc ra exit status. Neu bo cl_report()
     * va de moi core 'return' so loi cua minh thi phep thu nay se PASS sai. */
    if (me == 3) demo_l1_grid[3 * DEMO_L1_SLOTS + me] ^= 0xFFFFFFFFu;
#endif

    synch_barrier();

    /* Đọc chéo: mỗi core kiểm tra slot của core kế tiếp */
    int other = (me + 1) % DEMO_L1_SLOTS;
    int bad = 0;
    for (int i = 0; i < DEMO_L1_WORDS_PER_SLOT && !bad; i++) {
        unsigned int want = ((unsigned int)other << 16) | i;
        if (demo_l1_grid[i * DEMO_L1_SLOTS + other] != want) {
            eu_mutex_lock(eu_mutex_addr(CL_MUTEX_ID));
            printf("\n[PHASE 5] core %d thay word %d cua core %d = 0x%08x, "
                   "mong doi 0x%08x\n", me, i, other,
                   demo_l1_grid[i * DEMO_L1_SLOTS + other], want);
            eu_mutex_unlock(eu_mutex_addr(CL_MUTEX_ID));
            bad = 1;
        }
    }

    /* Tự báo lỗi rồi chờ mọi core báo xong, TRƯỚC khi core 0 in kết luận.
     * Nếu in trước thì core 0 sẽ báo OK trong khi core khác vừa báo lỗi —
     * đúng kiểu output gây hiểu nhầm mà cả bài này đang phòng chống. */
    cl_report(bad);
    synch_barrier();

    if (me == 0) {
        PHASE_BEGIN(5, "TCDM va interconnect");
        if (demo_cl_fails != before)
            PHASE_FAIL("%d core bao sai lech, xem cac dong PHASE 5 phia tren",
                       demo_cl_fails - before);
        PHASE_OK();
    }
    return 0;   /* đã tự báo qua cl_report, không trả về nữa kẻo đếm hai lần */
}

/* Chờ DMA có giới hạn.
 *
 * KHÔNG dùng plp_dma_wait() của runtime ở đây. Thân nó là
 *
 *     while (DMA_READ(MCHAN_STATUS_OFFSET) & (1 << counter))
 *         eu_evt_maskWaitAndClr(1 << ARCHI_CL_EVT_DMA0);
 *
 * (mchan_v7.h:414-419) — vòng lặp không có giới hạn, và thân vòng làm core
 * NGỦ chờ sự kiện DMA. Nếu DMA không bao giờ báo xong thì core ngủ vĩnh viễn:
 * không log, không FAIL, mô phỏng đứng im cho tới khi hết giờ. Poll có giới
 * hạn đổi cái treo đó lấy một dòng FAIL đọc được.
 *
 * Trả về 1 nếu transfer xong trước hạn, 0 nếu hết hạn.
 */
static int demo_dma_wait(int id)
{
    int ok = POLL_UNTIL(!(plp_dma_status() & (1 << id)), POLL_LIMIT);
    plp_dma_counter_free(id);
    return ok;
}

int phase6_dma(void)
{
    PHASE_BEGIN(6, "MCHAN DMA, AXI hai chieu");

    const unsigned short nbytes = DEMO_L2_WORDS * 4;

    /* Phép thử ngược cho phase 6: cắt ngắn lượt về 2 word. DMA vẫn báo xong
     * bình thường — chỉ có dữ liệu là thiếu. Nếu phase 6 thật sự đối chiếu
     * dữ liệu thì phải FAIL tại word DEMO_L2_WORDS-2; nếu nó chỉ đọc thanh
     * ghi trạng thái thì sẽ báo OK và lộ ra là phép kiểm tra rỗng. */
#ifdef DEMO_INJECT_FAULT_DMA
    const unsigned short nbytes_back = nbytes - 8;
#else
    const unsigned short nbytes_back = nbytes;
#endif

    for (int i = 0; i < DEMO_L2_WORDS; i++) {
        demo_l1_scratch[i]  = 0;
        demo_l2_dst[i]  = 0;
    }

    /* L2 -> L1 */
    int id = plp_dma_extToL1((unsigned int)demo_l1_scratch,
                             (mchan_ext_t)(unsigned int)demo_l2_src, nbytes);
    if (!demo_dma_wait(id))
        PHASE_FAIL("DMA L2->L1 khong bao xong sau %d lan poll, status=0x%08x",
                   POLL_LIMIT, plp_dma_status());

    /* L1 -> L2, sang vùng đích khác */
    id = plp_dma_l1ToExt((mchan_ext_t)(unsigned int)demo_l2_dst,
                         (unsigned int)demo_l1_scratch, nbytes_back);
    if (!demo_dma_wait(id))
        PHASE_FAIL("DMA L1->L2 khong bao xong sau %d lan poll, status=0x%08x",
                   POLL_LIMIT, plp_dma_status());

    for (int i = 0; i < DEMO_L2_WORDS; i++)
        if (demo_l2_dst[i] != demo_l2_src[i])
            PHASE_FAIL("word %d sau khu hoi = 0x%08x, goc 0x%08x",
                       i, demo_l2_dst[i], demo_l2_src[i]);
    PHASE_OK();
}

int phase7_hwpe(void)
{
    PHASE_BEGIN(7, "HWPE datamover");

#ifdef DEMO_PLATFORM_FPGA
    PHASE_SKIP("ban FPGA dat USE_HWPE_CL=0, khoi nay khong ton tai");
#else
    /* Bang thong cua datamover: N_MASTER_PORT*32 bit = 256 bit = 32 byte
     * moi nhip. MOI truong do dai va stride deu tinh theo don vi nay, KHONG
     * phai byte -- doi chieu test/test_datamover.c cua dependency. Truyen byte
     * vao se chi chuyen duoc vai word dau roi dung. */
    /* Bang thong THAT cua datamover trong cau hinh nay: 12 byte = 3 word
     * moi nhip. Con so nay do bang thuc nghiem, khong phai suy tu RTL:
     * dat D0_STRIDE = 32 byte -> word dung o vi tri 0,1,2 / 8,9,10 / ...
     * dat D0_STRIDE = 36 byte -> word dung o vi tri 0,1,2 / 9,10,11 / ...
     * Tuc stride do phan mem dat, con payload moi nhip co dinh 3 word.
     * Hang so DATAMOVER_BW = 256/8 trong test_datamover.c cua dependency la
     * cua mot cau hinh KHAC va khong dung o day.
     * Bang chung: report/full_system_20260906/ */
    const int BW    = 12;                 /* 12 byte = 3 word */
    const int words = 72;                 /* 288 byte = 24 nhip */
    const int bytes = words * 4;
    const int beats = bytes / BW;

    unsigned int *src = &demo_l1_scratch[0];
    unsigned int *dst = &demo_l1_scratch[words];

    for (int i = 0; i < words; i++) { src[i] = 0xDA7A0000u | i; dst[i] = 0; }

    /* BẮT BUỘC trước mọi thứ khác: HWPE mặc định bị clock-gate. Thiếu bước
     * này thì vòng poll STATUS treo tới hết timeout, và triệu chứng trông
     * y hệt như register map bị sai. */
    DATAMOVER_CG_ENABLE();
    DATAMOVER_SETPRIORITY_DATAMOVER();
    DATAMOVER_RESET_MAXSTALL();
    DATAMOVER_SET_MAXSTALL(8);

    DATAMOVER_WRITE_CMD(DATAMOVER_SOFT_CLEAR, DATAMOVER_SOFT_CLEAR_ALL);
    for (volatile int k = 0; k < 10; k++) { }

    /* Mở event 12. cluster_core_init() chỉ unmask DISPATCH|MUTEX|HW_BAR
     * (kernel/cluster.c:40), nên nếu không mở thì mọi macro chờ event của
     * hal_datamover.h sẽ treo vĩnh viễn. */
    eu_evt_maskSet(1 << DATAMOVER_EVT0);

    /* ACQUIRE bằng poll có giới hạn thay vì DATAMOVER_BARRIER_ACQUIRE, để
     * một HWPE chết không treo cả mô phỏng. */
    int job = -1;
    int got = POLL_UNTIL((DATAMOVER_READ_CMD(job, DATAMOVER_ACQUIRE), job >= 0),
                         POLL_LIMIT);
    if (!got)
        PHASE_FAIL("het gio khi ACQUIRE, job=%d", job);

    DATAMOVER_WRITE_REG(DATAMOVER_REG_IN_PTR,        (unsigned int)src);
    DATAMOVER_WRITE_REG(DATAMOVER_REG_OUT_PTR,       (unsigned int)dst);
    DATAMOVER_WRITE_REG(DATAMOVER_REG_TOT_LEN,       beats);
    DATAMOVER_WRITE_REG(DATAMOVER_REG_IN_D0_LEN,     beats);
    DATAMOVER_WRITE_REG(DATAMOVER_REG_IN_D0_STRIDE,  BW);
    DATAMOVER_WRITE_REG(DATAMOVER_REG_IN_D1_LEN,     beats);
    DATAMOVER_WRITE_REG(DATAMOVER_REG_IN_D1_STRIDE,  0);
    DATAMOVER_WRITE_REG(DATAMOVER_REG_IN_D2_STRIDE,  0);
    DATAMOVER_WRITE_REG(DATAMOVER_REG_OUT_D0_LEN,    beats);
    DATAMOVER_WRITE_REG(DATAMOVER_REG_OUT_D0_STRIDE, BW);
    DATAMOVER_WRITE_REG(DATAMOVER_REG_OUT_D1_LEN,    beats);
    DATAMOVER_WRITE_REG(DATAMOVER_REG_OUT_D1_STRIDE, 0);
    DATAMOVER_WRITE_REG(DATAMOVER_REG_OUT_D2_STRIDE, 0);

    DATAMOVER_WRITE_CMD(DATAMOVER_COMMIT_AND_TRIGGER, DATAMOVER_TRIGGER_CMD);

    /* Chờ hoàn thành. Không được poll thẳng 'status == 0': ngay sau TRIGGER
     * job chưa kịp khởi động nên STATUS vẫn đang là 0, và vòng poll thoát ra
     * tức thì trong khi engine mới chuyển được vài word. Đó chính là nguyên
     * nhân lần chạy trước dừng ở word 3.
     *
     * Vì vậy chờ theo hai nhịp: thấy job khởi động (STATUS != 0) rồi mới chờ
     * nó kết thúc. Nếu nhịp đầu hết giờ thì có thể job đã xong quá nhanh —
     * không coi là lỗi, để phép so sánh dữ liệu bên dưới phán quyết. */
    int status = 0;
    POLL_UNTIL((DATAMOVER_READ_CMD(status, DATAMOVER_STATUS), status != 0),
               POLL_LIMIT / 10);

    int done = POLL_UNTIL((DATAMOVER_READ_CMD(status, DATAMOVER_STATUS),
                           status == 0), POLL_LIMIT);
    if (!done)
        PHASE_FAIL("het gio khi cho STATUS, status=%d job=%d", status, job);

    int nbad = 0, first = -1;
    for (int i = 0; i < words; i++)
        if (dst[i] != src[i]) { if (first < 0) first = i; nbad++; }
    if (nbad) {
        printf("\n");
        printf("          src=0x%08x dst=0x%08x beats=%d BW=%d\n",
               (unsigned int)src, (unsigned int)dst, beats, BW);
        for (int i = 0; i < 16; i++)
            printf("          [%2d] src=0x%08x dst=0x%08x %s\n",
                   i, src[i], dst[i], dst[i] == src[i] ? "ok" : "SAI");
        printf("[PHASE 7] %-30s ... ", "HWPE datamover");
    }
    if (nbad)
        PHASE_FAIL("%d/%d word sai, dau tien la word %d: dst=0x%08x src=0x%08x "
                   "(job=%d status=%d beats=%d BW=%d)",
                   nbad, words, first, dst[first], src[first], job, status,
                   beats, BW);
    PHASE_OK();
#endif
}

/* ======================= main ========================================= */

int main(void)
{
    if (get_cluster_id() != 0) {
        /* ---------------- FC ---------------- */
        int fails = 0;

        printf("\n=== PULP full-system demo ===\n");
        fails += phase0_banner();
        fails += phase1_fc_l2();
        fails += phase2_timer();
        fails += phase3_cluster_poweron();
        fails += phase8_gpio();
        phase9_summary(fails);

        return fails;                       /* TB đọc thành exit status */
    }

    /* ---------------- Cluster, cả 8 core ---------------- */
    if (get_core_id() == 0) {
        demo_cl_fails = 0;
        demo_cl_ran   = DEMO_CL_RAN_MAGIC;   /* FC dùng để biết cluster đã chạy */
        eu_mutex_init(eu_mutex_addr(CL_MUTEX_ID));
    }
    synch_barrier();

    cl_report(phase4_barrier());

    /* phase5 tu bao loi qua cl_report() ben trong (moi core deu co the phat
     * hien), nen KHONG bao lai gia tri tra ve o day. PHASE_FAIL tra ve 1, neu
     * cl_report them lan nua thi loi bi dem hai lan. */
    phase5_tcdm();

    if (get_core_id() == 0) {
        cl_report(phase6_dma());
        cl_report(phase7_hwpe());
    }
    synch_barrier();

    /* Chỉ core 0 có giá trị trả về được runtime giữ lại */
    return (get_core_id() == 0) ? demo_cl_fails : 0;
}
