#ifndef __DEMO_DATA_H__
#define __DEMO_DATA_H__

#include "data/data.h"   /* L2_DATA / L1_DATA: macro dat section cua runtime */

#define DEMO_L2_WORDS            256
#define DEMO_L1_SLOTS              8
#define DEMO_L1_WORDS_PER_SLOT    32

/* Checksum vang cua demo_l2_src, tinh luc sinh file bang dung thuat toan
 * ma demo_checksum() dung: xor roi xoay trai 1 bit. */
#define DEMO_L2_GOLDEN     0xc1d7f5f6u

extern unsigned int demo_l2_src[DEMO_L2_WORDS];
extern unsigned int demo_l2_dst[DEMO_L2_WORDS];
extern unsigned int demo_l1_grid[DEMO_L1_SLOTS * DEMO_L1_WORDS_PER_SLOT];
extern unsigned int demo_l1_scratch[DEMO_L2_WORDS];
extern volatile unsigned int demo_cl_ran;   /* sentinel: cluster da chay chua */
#define DEMO_CL_RAN_MAGIC 0x5A11AC7Eu

extern volatile int demo_cl_fails;
extern volatile int demo_cl_seen[DEMO_L1_SLOTS];

#endif
