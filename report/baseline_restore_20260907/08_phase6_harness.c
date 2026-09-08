
#include <stdio.h>
#define DEMO_L2_WORDS 256
#define POLL_LIMIT 200000
#define PHASE_BEGIN(n,name) printf("[PHASE %d] %-30s ... ",(n),(name))
#define PHASE_OK() do { printf("OK\n"); return 0; } while (0)
#define PHASE_FAIL(...) do { printf("FAIL  "); printf(__VA_ARGS__); printf("\n"); return 1; } while (0)
#define POLL_UNTIL(cond, limit) ({ volatile int _n=0; while(!(cond) && _n<(limit)) _n++; (_n<(limit)); })
typedef unsigned long mchan_ext_t;
unsigned int demo_l2_src[DEMO_L2_WORDS], demo_l2_dst[DEMO_L2_WORDS], demo_l1_scratch[DEMO_L2_WORDS];
static unsigned int g_status = 0;
static unsigned int plp_dma_status(void) { return g_status; }
static void plp_dma_counter_free(int c) { (void)c; }
/* stub mo phong DMA that: chep n/4 word giua hai vung */
static int plp_dma_extToL1(unsigned long l1, mchan_ext_t l2, unsigned short n) {
    (void)l1; (void)l2;
    for (unsigned i = 0; i < n/4u; i++) demo_l1_scratch[i] = demo_l2_src[i];
    return 1; }
static int plp_dma_l1ToExt(mchan_ext_t l2, unsigned long l1, unsigned short n) {
    (void)l1; (void)l2;
    for (unsigned i = 0; i < n/4u; i++) demo_l2_dst[i] = demo_l1_scratch[i];
    return 1; }
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


int main(void) {
    for (int i = 0; i < DEMO_L2_WORDS; i++) demo_l2_src[i] = 0xA0000000u + i;
    printf("--- DMA hoat dong binh thuong ---\n");
    printf("ket qua: phase6_dma() = %d\n\n", phase6_dma());
    printf("--- DMA khong bao xong (status ket) ---\n");
    g_status = 0xFFFFFFFFu;
    printf("ket qua: phase6_dma() = %d\n", phase6_dma());
    return 0;
}
