//
//  distance-neon.c
//  sqlitevector
//
//  Created by Marco Bambini on 20/06/25.
//

#include "distance-neon.h"
#include "distance-cpu.h"
#include <stdbool.h>
#include <stdlib.h>
#include <math.h>


#if defined(__ARM_NEON) || defined(__ARM_NEON__)

#if __SIZEOF_POINTER__ == 4
#define _ARM32BIT_ 1
#endif

#include <arm_neon.h>

extern distance_function_t dispatch_distance_table[VECTOR_DISTANCE_MAX][VECTOR_TYPE_MAX];
extern const char *distance_backend_name;
extern turbo_lut_dot_function_t turbo_lut_dot_function;
extern const char *turbo_lut_backend_name;

// Helper function for 32-bit ARM: vmaxv_u16 is not available in ARMv7 NEON
#ifdef _ARM32BIT_
static inline uint16_t vmaxv_u16_compat(uint16x4_t v) {
    // Use pairwise max to reduce vector
    uint16x4_t m = vpmax_u16(v, v);  // [max(v0,v1), max(v2,v3), max(v0,v1), max(v2,v3)]
    m = vpmax_u16(m, m);              // [max(all), max(all), max(all), max(all)]
    return vget_lane_u16(m, 0);
}
#define vmaxv_u16 vmaxv_u16_compat
#endif

// MARK: FLOAT32 -

// One accumulator turns the loop into a single dependency chain: FMLA has around four
// cycles of latency, so the loop retires one vector every four cycles however many FMA
// pipes the core has. Four independent accumulators keep them all fed.
#if defined(__aarch64__) || defined(__ARM_FEATURE_FMA)
#define VFMA_F32(_acc, _x, _y)              vfmaq_f32((_acc), (_x), (_y))
#else
#define VFMA_F32(_acc, _x, _y)              vmlaq_f32((_acc), (_x), (_y))
#endif

static inline float hsum_f32x4 (float32x4_t v) {
    #if defined(__aarch64__)
    return vaddvq_f32(v);
    #else
    float t[4];
    vst1q_f32(t, v);
    return t[0] + t[1] + t[2] + t[3];
    #endif
}

float float32_distance_l2_impl_neon (const void *v1, const void *v2, int n, bool use_sqrt) {
    const float *a = (const float *)v1;
    const float *b = (const float *)v2;

    float32x4_t acc0 = vdupq_n_f32(0.0f), acc1 = acc0, acc2 = acc0, acc3 = acc0;
    int i = 0;

    for (; i <= n - 16; i += 16) {
        float32x4_t d0 = vsubq_f32(vld1q_f32(a + i     ), vld1q_f32(b + i     ));
        float32x4_t d1 = vsubq_f32(vld1q_f32(a + i +  4), vld1q_f32(b + i +  4));
        float32x4_t d2 = vsubq_f32(vld1q_f32(a + i +  8), vld1q_f32(b + i +  8));
        float32x4_t d3 = vsubq_f32(vld1q_f32(a + i + 12), vld1q_f32(b + i + 12));
        acc0 = VFMA_F32(acc0, d0, d0);
        acc1 = VFMA_F32(acc1, d1, d1);
        acc2 = VFMA_F32(acc2, d2, d2);
        acc3 = VFMA_F32(acc3, d3, d3);
    }
    for (; i <= n - 4; i += 4) {
        float32x4_t d = vsubq_f32(vld1q_f32(a + i), vld1q_f32(b + i));
        acc0 = VFMA_F32(acc0, d, d);
    }

    float sum = hsum_f32x4(vaddq_f32(vaddq_f32(acc0, acc1), vaddq_f32(acc2, acc3)));

    for (; i < n; ++i) {
        float d = a[i] - b[i];
        sum += d * d;
    }

    return use_sqrt ? sqrtf(sum) : sum;
}

float float32_distance_l2_neon (const void *v1, const void *v2, int n) {
    return float32_distance_l2_impl_neon(v1, v2, n, true);
}

float float32_distance_l2_squared_neon (const void *v1, const void *v2, int n) {
    return float32_distance_l2_impl_neon(v1, v2, n, false);
}

float float32_distance_cosine_neon (const void *v1, const void *v2, int n) {
    const float *a = (const float *)v1;
    const float *b = (const float *)v2;

    // three quantities x four accumulators: twelve independent chains, which aarch64's
    // 32 vector registers hold without spilling
    float32x4_t dot0 = vdupq_n_f32(0.0f), dot1 = dot0, dot2 = dot0, dot3 = dot0;
    float32x4_t na0 = dot0, na1 = dot0, na2 = dot0, na3 = dot0;
    float32x4_t nb0 = dot0, nb1 = dot0, nb2 = dot0, nb3 = dot0;
    int i = 0;

    for (; i <= n - 16; i += 16) {
        float32x4_t a0 = vld1q_f32(a + i), a1 = vld1q_f32(a + i + 4);
        float32x4_t a2 = vld1q_f32(a + i + 8), a3 = vld1q_f32(a + i + 12);
        float32x4_t b0 = vld1q_f32(b + i), b1 = vld1q_f32(b + i + 4);
        float32x4_t b2 = vld1q_f32(b + i + 8), b3 = vld1q_f32(b + i + 12);
        dot0 = VFMA_F32(dot0, a0, b0);  dot1 = VFMA_F32(dot1, a1, b1);
        dot2 = VFMA_F32(dot2, a2, b2);  dot3 = VFMA_F32(dot3, a3, b3);
        na0  = VFMA_F32(na0,  a0, a0);  na1  = VFMA_F32(na1,  a1, a1);
        na2  = VFMA_F32(na2,  a2, a2);  na3  = VFMA_F32(na3,  a3, a3);
        nb0  = VFMA_F32(nb0,  b0, b0);  nb1  = VFMA_F32(nb1,  b1, b1);
        nb2  = VFMA_F32(nb2,  b2, b2);  nb3  = VFMA_F32(nb3,  b3, b3);
    }
    for (; i <= n - 4; i += 4) {
        float32x4_t va = vld1q_f32(a + i), vb = vld1q_f32(b + i);
        dot0 = VFMA_F32(dot0, va, vb);
        na0  = VFMA_F32(na0,  va, va);
        nb0  = VFMA_F32(nb0,  vb, vb);
    }

    float dot    = hsum_f32x4(vaddq_f32(vaddq_f32(dot0, dot1), vaddq_f32(dot2, dot3)));
    float norm_a = hsum_f32x4(vaddq_f32(vaddq_f32(na0, na1), vaddq_f32(na2, na3)));
    float norm_b = hsum_f32x4(vaddq_f32(vaddq_f32(nb0, nb1), vaddq_f32(nb2, nb3)));

    for (; i < n; ++i) {
        float ai = a[i];
        float bi = b[i];
        dot     += ai * bi;
        norm_a  += ai * ai;
        norm_b  += bi * bi;
    }

    if (norm_a == 0.0f || norm_b == 0.0f) return 1.0f;
    float cosine_similarity = dot / (sqrtf(norm_a) * sqrtf(norm_b));
    if (cosine_similarity > 1.0f) cosine_similarity = 1.0f;
    if (cosine_similarity < -1.0f) cosine_similarity = -1.0f;
    return 1.0f - cosine_similarity;
}

float float32_distance_dot_neon (const void *v1, const void *v2, int n) {
    const float *a = (const float *)v1;
    const float *b = (const float *)v2;

    float32x4_t acc0 = vdupq_n_f32(0.0f), acc1 = acc0, acc2 = acc0, acc3 = acc0;
    int i = 0;

    for (; i <= n - 16; i += 16) {
        acc0 = VFMA_F32(acc0, vld1q_f32(a + i     ), vld1q_f32(b + i     ));
        acc1 = VFMA_F32(acc1, vld1q_f32(a + i +  4), vld1q_f32(b + i +  4));
        acc2 = VFMA_F32(acc2, vld1q_f32(a + i +  8), vld1q_f32(b + i +  8));
        acc3 = VFMA_F32(acc3, vld1q_f32(a + i + 12), vld1q_f32(b + i + 12));
    }
    for (; i <= n - 4; i += 4) {
        acc0 = VFMA_F32(acc0, vld1q_f32(a + i), vld1q_f32(b + i));
    }

    float dot = hsum_f32x4(vaddq_f32(vaddq_f32(acc0, acc1), vaddq_f32(acc2, acc3)));

    for (; i < n; ++i) {
        dot += a[i] * b[i];
    }

    return -dot;
}

float float32_distance_l1_neon (const void *v1, const void *v2, int n) {
    const float *a = (const float *)v1;
    const float *b = (const float *)v2;

    float32x4_t acc0 = vdupq_n_f32(0.0f), acc1 = acc0, acc2 = acc0, acc3 = acc0;
    int i = 0;

    for (; i <= n - 16; i += 16) {
        acc0 = vaddq_f32(acc0, vabdq_f32(vld1q_f32(a + i     ), vld1q_f32(b + i     )));
        acc1 = vaddq_f32(acc1, vabdq_f32(vld1q_f32(a + i +  4), vld1q_f32(b + i +  4)));
        acc2 = vaddq_f32(acc2, vabdq_f32(vld1q_f32(a + i +  8), vld1q_f32(b + i +  8)));
        acc3 = vaddq_f32(acc3, vabdq_f32(vld1q_f32(a + i + 12), vld1q_f32(b + i + 12)));
    }
    for (; i <= n - 4; i += 4) {
        acc0 = vaddq_f32(acc0, vabdq_f32(vld1q_f32(a + i), vld1q_f32(b + i)));
    }

    float sum = hsum_f32x4(vaddq_f32(vaddq_f32(acc0, acc1), vaddq_f32(acc2, acc3)));

    for (; i < n; ++i) {
        sum += fabsf(a[i] - b[i]);
    }

    return sum;
}

// MARK: - BFLOAT16 -

static inline float32x4_t bf16x4_to_f32x4_u16 (uint16x4_t h) {
    // widen u16 -> u32 and shift left 16: exact bf16->f32 bit pattern
    uint32x4_t u32 = vshll_n_u16(h, 16);
    return vreinterpretq_f32_u32(u32);
}

// MARK: - FLOAT16 -

// vector converter: 4×f16 bits (u16) -> f32x4
static inline float32x4_t f16x4_to_f32x4_u16(uint16x4_t h) {
#if defined(__ARM_FEATURE_FP16_VECTOR_ARITHMETIC)
    /* Fast path: NEON FP16 -> FP32 */
    float16x4_t h16 = vreinterpret_f16_u16(h);
    return vcvt_f32_f16(h16);
#else
    /* Portable per-lane conversion via your helper */
    float tmp[4];
    tmp[0] = float16_to_float32(vget_lane_u16(h, 0));
    tmp[1] = float16_to_float32(vget_lane_u16(h, 1));
    tmp[2] = float16_to_float32(vget_lane_u16(h, 2));
    tmp[3] = float16_to_float32(vget_lane_u16(h, 3));
    return vld1q_f32(tmp);
#endif
}

/* =========================================================================
   Cosine distance (1 - dot/(||a||*||b||)) -- float16 (uint16_t)
   ========================================================================= */
/* =========================================================================
   Dot (returns -dot) -- float16 (uint16_t)
   ========================================================================= */
/* =========================================================================
   L1 (sum |a-b|) -- float16 (uint16_t)
   ========================================================================= */
// MARK: - UINT8 -

// The integer kernels used to widen every byte to 32 bits and multiply there - twelve or
// more instructions per 16 bytes - on a single accumulator chain. NEON has the whole job
// in five: absolute difference, widening multiply, pairwise-accumulate. Products of two
// bytes fit u16, so the only rule is to widen into the u32 accumulator before a second
// product can overflow the u16 lane.
//
// The signed kernels reuse the unsigned ones wherever the arithmetic allows: biasing an
// int8 by 0x80 maps it onto uint8 without changing any difference between two elements,
// so L2 and L1 are the same computation. Dot and cosine need the true signed values.
#define S8_TO_BIASED_U8(_v)                 veorq_u8(vreinterpretq_u8_s8(_v), vdupq_n_u8(0x80))

// dot, |a|^2 and |b|^2 in one pass, two accumulators each
static inline void uint8_sums_neon (const uint8_t *a, const uint8_t *b, int n, uint64_t *dot_out, uint64_t *na_out, uint64_t *nb_out) {
    uint32x4_t dot0 = vmovq_n_u32(0), dot1 = dot0;
    uint32x4_t na0 = dot0, na1 = dot0;
    uint32x4_t nb0 = dot0, nb1 = dot0;
    int i = 0;

    for (; i <= n - 16; i += 16) {
        uint8x16_t va = vld1q_u8(a + i);
        uint8x16_t vb = vld1q_u8(b + i);
        uint8x8_t al = vget_low_u8(va), ah = vget_high_u8(va);
        uint8x8_t bl = vget_low_u8(vb), bh = vget_high_u8(vb);

        dot0 = vpadalq_u16(dot0, vmull_u8(al, bl));
        dot1 = vpadalq_u16(dot1, vmull_u8(ah, bh));
        na0  = vpadalq_u16(na0,  vmull_u8(al, al));
        na1  = vpadalq_u16(na1,  vmull_u8(ah, ah));
        nb0  = vpadalq_u16(nb0,  vmull_u8(bl, bl));
        nb1  = vpadalq_u16(nb1,  vmull_u8(bh, bh));
    }

    uint64x2_t d64 = vpaddlq_u32(vaddq_u32(dot0, dot1));
    uint64x2_t a64 = vpaddlq_u32(vaddq_u32(na0, na1));
    uint64x2_t b64 = vpaddlq_u32(vaddq_u32(nb0, nb1));
    uint64_t dot = vgetq_lane_u64(d64, 0) + vgetq_lane_u64(d64, 1);
    uint64_t na  = vgetq_lane_u64(a64, 0) + vgetq_lane_u64(a64, 1);
    uint64_t nb  = vgetq_lane_u64(b64, 0) + vgetq_lane_u64(b64, 1);

    for (; i < n; ++i) {
        uint32_t x = a[i], y = b[i];
        dot += (uint64_t)(x * y);
        na  += (uint64_t)(x * x);
        nb  += (uint64_t)(y * y);
    }

    *dot_out = dot;
    *na_out = na;
    *nb_out = nb;
}

// MARK: - INT8 -

static inline float int8_distance_l2_neon_imp (const void *v1, const void *v2, int n, bool use_sqrt) {
    const int8_t *a = (const int8_t *)v1;
    const int8_t *b = (const int8_t *)v2;

    // biasing both sides by 0x80 leaves every |a[i] - b[i]| untouched, so this is the
    // unsigned kernel with two extra XORs per vector
    uint32x4_t acc0 = vmovq_n_u32(0), acc1 = acc0, acc2 = acc0, acc3 = acc0;
    int i = 0;

    for (; i <= n - 32; i += 32) {
        uint8x16_t a0 = S8_TO_BIASED_U8(vld1q_s8(a + i     ));
        uint8x16_t b0 = S8_TO_BIASED_U8(vld1q_s8(b + i     ));
        uint8x16_t a1 = S8_TO_BIASED_U8(vld1q_s8(a + i + 16));
        uint8x16_t b1 = S8_TO_BIASED_U8(vld1q_s8(b + i + 16));
        uint8x16_t d0 = vabdq_u8(a0, b0);
        uint8x16_t d1 = vabdq_u8(a1, b1);
        acc0 = vpadalq_u16(acc0, vmull_u8(vget_low_u8(d0),  vget_low_u8(d0)));
        acc1 = vpadalq_u16(acc1, vmull_u8(vget_high_u8(d0), vget_high_u8(d0)));
        acc2 = vpadalq_u16(acc2, vmull_u8(vget_low_u8(d1),  vget_low_u8(d1)));
        acc3 = vpadalq_u16(acc3, vmull_u8(vget_high_u8(d1), vget_high_u8(d1)));
    }
    for (; i <= n - 16; i += 16) {
        uint8x16_t d = vabdq_u8(S8_TO_BIASED_U8(vld1q_s8(a + i)), S8_TO_BIASED_U8(vld1q_s8(b + i)));
        acc0 = vpadalq_u16(acc0, vmull_u8(vget_low_u8(d),  vget_low_u8(d)));
        acc1 = vpadalq_u16(acc1, vmull_u8(vget_high_u8(d), vget_high_u8(d)));
    }

    uint64x2_t sum64 = vpaddlq_u32(vaddq_u32(vaddq_u32(acc0, acc1), vaddq_u32(acc2, acc3)));
    uint64_t total = vgetq_lane_u64(sum64, 0) + vgetq_lane_u64(sum64, 1);

    for (; i < n; ++i) {
        int diff = (int)a[i] - (int)b[i];
        total += (uint64_t)(diff * diff);
    }

    return use_sqrt ? sqrtf((float)total) : (float)total;
}

float int8_distance_l2_neon (const void *v1, const void *v2, int n) {
    return int8_distance_l2_neon_imp(v1, v2, n, true);
}

float int8_distance_l2_squared_neon (const void *v1, const void *v2, int n) {
    return int8_distance_l2_neon_imp(v1, v2, n, false);
}

// signed products need the real values, so no biasing here
static inline void int8_sums_neon (const int8_t *a, const int8_t *b, int n, int64_t *dot_out, int64_t *na_out, int64_t *nb_out) {
    int32x4_t dot0 = vmovq_n_s32(0), dot1 = dot0;
    int32x4_t na0 = dot0, na1 = dot0;
    int32x4_t nb0 = dot0, nb1 = dot0;
    int i = 0;

    for (; i <= n - 16; i += 16) {
        int8x16_t va = vld1q_s8(a + i);
        int8x16_t vb = vld1q_s8(b + i);
        int8x8_t al = vget_low_s8(va), ah = vget_high_s8(va);
        int8x8_t bl = vget_low_s8(vb), bh = vget_high_s8(vb);

        dot0 = vpadalq_s16(dot0, vmull_s8(al, bl));
        dot1 = vpadalq_s16(dot1, vmull_s8(ah, bh));
        na0  = vpadalq_s16(na0,  vmull_s8(al, al));
        na1  = vpadalq_s16(na1,  vmull_s8(ah, ah));
        nb0  = vpadalq_s16(nb0,  vmull_s8(bl, bl));
        nb1  = vpadalq_s16(nb1,  vmull_s8(bh, bh));
    }

    int64x2_t d64 = vpaddlq_s32(vaddq_s32(dot0, dot1));
    int64x2_t a64 = vpaddlq_s32(vaddq_s32(na0, na1));
    int64x2_t b64 = vpaddlq_s32(vaddq_s32(nb0, nb1));
    int64_t dot = vgetq_lane_s64(d64, 0) + vgetq_lane_s64(d64, 1);
    int64_t na  = vgetq_lane_s64(a64, 0) + vgetq_lane_s64(a64, 1);
    int64_t nb  = vgetq_lane_s64(b64, 0) + vgetq_lane_s64(b64, 1);

    for (; i < n; ++i) {
        int32_t x = a[i], y = b[i];
        dot += (int64_t)(x * y);
        na  += (int64_t)(x * x);
        nb  += (int64_t)(y * y);
    }

    *dot_out = dot;
    *na_out = na;
    *nb_out = nb;
}

float int8_distance_cosine_neon (const void *v1, const void *v2, int n) {
    int64_t dot, norm_a, norm_b;
    int8_sums_neon((const int8_t *)v1, (const int8_t *)v2, n, &dot, &norm_a, &norm_b);

    if (norm_a == 0 || norm_b == 0) return 1.0f;

    float cosine_similarity = (float)((double)dot / (sqrt((double)norm_a) * sqrt((double)norm_b)));
    if (cosine_similarity > 1.0f) cosine_similarity = 1.0f;
    if (cosine_similarity < -1.0f) cosine_similarity = -1.0f;
    return 1.0f - cosine_similarity;
}

float int8_distance_dot_neon (const void *v1, const void *v2, int n) {
    const int8_t *a = (const int8_t *)v1;
    const int8_t *b = (const int8_t *)v2;

    int32x4_t acc0 = vmovq_n_s32(0), acc1 = acc0, acc2 = acc0, acc3 = acc0;
    int i = 0;

    for (; i <= n - 32; i += 32) {
        int8x16_t a0 = vld1q_s8(a + i     ), b0 = vld1q_s8(b + i     );
        int8x16_t a1 = vld1q_s8(a + i + 16), b1 = vld1q_s8(b + i + 16);
        acc0 = vpadalq_s16(acc0, vmull_s8(vget_low_s8(a0),  vget_low_s8(b0)));
        acc1 = vpadalq_s16(acc1, vmull_s8(vget_high_s8(a0), vget_high_s8(b0)));
        acc2 = vpadalq_s16(acc2, vmull_s8(vget_low_s8(a1),  vget_low_s8(b1)));
        acc3 = vpadalq_s16(acc3, vmull_s8(vget_high_s8(a1), vget_high_s8(b1)));
    }
    for (; i <= n - 16; i += 16) {
        int8x16_t va = vld1q_s8(a + i), vb = vld1q_s8(b + i);
        acc0 = vpadalq_s16(acc0, vmull_s8(vget_low_s8(va),  vget_low_s8(vb)));
        acc1 = vpadalq_s16(acc1, vmull_s8(vget_high_s8(va), vget_high_s8(vb)));
    }

    int64x2_t sum64 = vpaddlq_s32(vaddq_s32(vaddq_s32(acc0, acc1), vaddq_s32(acc2, acc3)));
    int64_t dot = vgetq_lane_s64(sum64, 0) + vgetq_lane_s64(sum64, 1);

    for (; i < n; ++i) dot += (int64_t)((int32_t)a[i] * (int32_t)b[i]);

    return -(float)dot;
}

float int8_distance_l1_neon(const void *v1, const void *v2, int n) {
    const int8_t *a = (const int8_t *)v1;
    const int8_t *b = (const int8_t *)v2;

    // same biasing trick as L2: absolute differences are unaffected
    uint32x4_t acc0 = vmovq_n_u32(0), acc1 = acc0;
    int i = 0;

    for (; i <= n - 32; i += 32) {
        uint8x16_t d0 = vabdq_u8(S8_TO_BIASED_U8(vld1q_s8(a + i     )), S8_TO_BIASED_U8(vld1q_s8(b + i     )));
        uint8x16_t d1 = vabdq_u8(S8_TO_BIASED_U8(vld1q_s8(a + i + 16)), S8_TO_BIASED_U8(vld1q_s8(b + i + 16)));
        acc0 = vpadalq_u16(acc0, vpaddlq_u8(d0));
        acc1 = vpadalq_u16(acc1, vpaddlq_u8(d1));
    }
    for (; i <= n - 16; i += 16) {
        uint8x16_t d = vabdq_u8(S8_TO_BIASED_U8(vld1q_s8(a + i)), S8_TO_BIASED_U8(vld1q_s8(b + i)));
        acc0 = vpadalq_u16(acc0, vpaddlq_u8(d));
    }

    uint64x2_t sum64 = vpaddlq_u32(vaddq_u32(acc0, acc1));
    uint64_t sum = vgetq_lane_u64(sum64, 0) + vgetq_lane_u64(sum64, 1);

    for (; i < n; ++i) sum += (uint64_t)abs((int)a[i] - (int)b[i]);

    return (float)sum;
}

// MARK: - BIT -

float bit1_distance_hamming_neon (const void *v1, const void *v2, int n) {
    const uint8_t *a = (const uint8_t *)v1;
    const uint8_t *b = (const uint8_t *)v2;
    uint64x2_t acc = vdupq_n_u64(0);
    int i = 0;
    
    // Process 16 bytes at a time
    for (; i + 16 <= n; i += 16) {
        uint8x16_t va = vld1q_u8(a + i);
        uint8x16_t vb = vld1q_u8(b + i);
        uint8x16_t xored = veorq_u8(va, vb);
        
        // vcntq_u8: popcount per byte
        uint8x16_t popcnt = vcntq_u8(xored);
        
        // Sum bytes to 64-bit accumulators
        acc = vpadalq_u32(acc, vpaddlq_u16(vpaddlq_u8(popcnt)));
    }
    
    int distance = (int)(vgetq_lane_u64(acc, 0) + vgetq_lane_u64(acc, 1));
    
    // Handle remainder
    for (; i < n; i++) {
        distance += __builtin_popcount(a[i] ^ b[i]);
    }
    
    return (float)distance;
}



#endif

// MARK: -

bool init_distance_functions_neon (void) {
#if defined(__ARM_NEON) || defined(__ARM_NEON__)
    dispatch_distance_table[VECTOR_DISTANCE_L2][VECTOR_TYPE_F32] = float32_distance_l2_neon;
    dispatch_distance_table[VECTOR_DISTANCE_L2][VECTOR_TYPE_I8] = int8_distance_l2_neon;
    
    dispatch_distance_table[VECTOR_DISTANCE_SQUARED_L2][VECTOR_TYPE_F32] = float32_distance_l2_squared_neon;
    dispatch_distance_table[VECTOR_DISTANCE_SQUARED_L2][VECTOR_TYPE_I8] = int8_distance_l2_squared_neon;
    
    dispatch_distance_table[VECTOR_DISTANCE_COSINE][VECTOR_TYPE_F32] = float32_distance_cosine_neon;
    dispatch_distance_table[VECTOR_DISTANCE_COSINE][VECTOR_TYPE_I8] = int8_distance_cosine_neon;
    
    dispatch_distance_table[VECTOR_DISTANCE_DOT][VECTOR_TYPE_F32] = float32_distance_dot_neon;
    dispatch_distance_table[VECTOR_DISTANCE_DOT][VECTOR_TYPE_I8] = int8_distance_dot_neon;
    
    dispatch_distance_table[VECTOR_DISTANCE_L1][VECTOR_TYPE_F32] = float32_distance_l1_neon;
    dispatch_distance_table[VECTOR_DISTANCE_L1][VECTOR_TYPE_I8] = int8_distance_l1_neon;
    
    dispatch_distance_table[VECTOR_DISTANCE_HAMMING][VECTOR_TYPE_BIT] = bit1_distance_hamming_neon;
    
    distance_backend_name = "NEON";
    // the TurboQuant lookup scan is gather-bound and shared by every backend
    turbo_lut_dot_function = turbo_lut_dot_cpu;
    turbo_lut_backend_name = "NEON";
    return true;
#else
    return false;
#endif
}
