//
//  distance-sse2.c
//  sqlitevector
//
//  Created by Marco Bambini on 20/06/25.
//

#include "distance-sse2.h"
#include "distance-cpu.h"

#if defined(__SSE2__) || (defined(_MSC_VER) && (defined(_M_X64) || (_M_IX86_FP >= 2)))
#include <emmintrin.h>
#include <stdint.h>
#include <math.h>

extern distance_function_t dispatch_distance_table[VECTOR_DISTANCE_MAX][VECTOR_TYPE_MAX];
extern const char *distance_backend_name;
extern turbo_lut_dot_function_t turbo_lut_dot_function;
extern const char *turbo_lut_backend_name;

// accumulate 32-bit
#define ACCUMULATE(MUL, ACC)                    \
    acc_tmp = _mm_unpacklo_epi16(MUL, _mm_setzero_si128()); \
    ACC = _mm_add_epi32(ACC, acc_tmp);          \
    acc_tmp = _mm_unpackhi_epi16(MUL, _mm_setzero_si128()); \
    ACC = _mm_add_epi32(ACC, acc_tmp);

// proper sign-extension from int16_t to int32_t
#define SIGN_EXTEND_EPI16_TO_EPI32_LO(v) \
    _mm_srai_epi32(_mm_unpacklo_epi16(_mm_slli_epi32((v), 16), (v)), 16)

#define SIGN_EXTEND_EPI16_TO_EPI32_HI(v) \
    _mm_srai_epi32(_mm_unpackhi_epi16(_mm_slli_epi32((v), 16), (v)), 16)

static inline double hsum128d(__m128d v) {
    __m128d sh = _mm_unpackhi_pd(v, v);
    __m128d s  = _mm_add_sd(v, sh);
    return _mm_cvtsd_f64(s);
}

static inline __m128d mm_abs_pd(__m128d x) {
    const __m128d sign = _mm_set1_pd(-0.0);
    return _mm_andnot_pd(sign, x);
}

static inline __m128 f16x4_to_f32x4_loadu(const uint16_t* p) {
    float tmp[4];
    tmp[0] = float16_to_float32(p[0]);
    tmp[1] = float16_to_float32(p[1]);
    tmp[2] = float16_to_float32(p[2]);
    tmp[3] = float16_to_float32(p[3]);
    return _mm_loadu_ps(tmp);
}

/* load 4 bf16 -> __m128 of f32 */
static inline __m128 bf16x4_to_f32x4_loadu(const uint16_t* p) {
    float tmp[4];
    tmp[0] = bfloat16_to_float32(p[0]);
    tmp[1] = bfloat16_to_float32(p[1]);
    tmp[2] = bfloat16_to_float32(p[2]);
    tmp[3] = bfloat16_to_float32(p[3]);
    return _mm_loadu_ps(tmp);
}


// MARK: - FLOAT32 -

// A single accumulator makes the loop one dependency chain, so it retires one vector per
// add latency however many ports the core has. Two independent accumulators double that
// while still fitting the eight XMM registers available on 32-bit x86.
static inline float hsum128_ps (__m128 v) {
    __m128 s = _mm_add_ps(v, _mm_movehl_ps(v, v));
    s = _mm_add_ss(s, _mm_shuffle_ps(s, s, 0x55));
    return _mm_cvtss_f32(s);
}

static inline float float32_distance_l2_impl_sse2 (const void *v1, const void *v2, int n, bool use_sqrt) {
    const float *a = (const float *)v1;
    const float *b = (const float *)v2;

    __m128 acc0 = _mm_setzero_ps(), acc1 = _mm_setzero_ps();
    int i = 0;

    for (; i <= n - 8; i += 8) {
        __m128 d0 = _mm_sub_ps(_mm_loadu_ps(a + i    ), _mm_loadu_ps(b + i    ));
        __m128 d1 = _mm_sub_ps(_mm_loadu_ps(a + i + 4), _mm_loadu_ps(b + i + 4));
        acc0 = _mm_add_ps(acc0, _mm_mul_ps(d0, d0));
        acc1 = _mm_add_ps(acc1, _mm_mul_ps(d1, d1));
    }
    for (; i <= n - 4; i += 4) {
        __m128 d = _mm_sub_ps(_mm_loadu_ps(a + i), _mm_loadu_ps(b + i));
        acc0 = _mm_add_ps(acc0, _mm_mul_ps(d, d));
    }

    float total = hsum128_ps(_mm_add_ps(acc0, acc1));

    for (; i < n; ++i) {
        float d = a[i] - b[i];
        total += d * d;
    }

    return use_sqrt ? sqrtf(total) : total;
}

float float32_distance_l2_sse2 (const void *v1, const void *v2, int n) {
    return float32_distance_l2_impl_sse2(v1, v2, n, true);
}

float float32_distance_l2_squared_sse2 (const void *v1, const void *v2, int n) {
    return float32_distance_l2_impl_sse2(v1, v2, n, false);
}

float float32_distance_l1_sse2 (const void *v1, const void *v2, int n) {
    const float *a = (const float *)v1;
    const float *b = (const float *)v2;

    const __m128 sign = _mm_set1_ps(-0.0f);
    __m128 acc0 = _mm_setzero_ps(), acc1 = _mm_setzero_ps();
    int i = 0;

    for (; i <= n - 8; i += 8) {
        __m128 d0 = _mm_sub_ps(_mm_loadu_ps(a + i    ), _mm_loadu_ps(b + i    ));
        __m128 d1 = _mm_sub_ps(_mm_loadu_ps(a + i + 4), _mm_loadu_ps(b + i + 4));
        acc0 = _mm_add_ps(acc0, _mm_andnot_ps(sign, d0));   // abs using bitmask
        acc1 = _mm_add_ps(acc1, _mm_andnot_ps(sign, d1));
    }
    for (; i <= n - 4; i += 4) {
        __m128 d = _mm_sub_ps(_mm_loadu_ps(a + i), _mm_loadu_ps(b + i));
        acc0 = _mm_add_ps(acc0, _mm_andnot_ps(sign, d));
    }

    float total = hsum128_ps(_mm_add_ps(acc0, acc1));

    for (; i < n; ++i) {
        total += fabsf(a[i] - b[i]);
    }

    return total;
}

float float32_distance_dot_sse2 (const void *v1, const void *v2, int n) {
    const float *a = (const float *)v1;
    const float *b = (const float *)v2;

    __m128 acc0 = _mm_setzero_ps(), acc1 = _mm_setzero_ps();
    int i = 0;

    for (; i <= n - 8; i += 8) {
        acc0 = _mm_add_ps(acc0, _mm_mul_ps(_mm_loadu_ps(a + i    ), _mm_loadu_ps(b + i    )));
        acc1 = _mm_add_ps(acc1, _mm_mul_ps(_mm_loadu_ps(a + i + 4), _mm_loadu_ps(b + i + 4)));
    }
    for (; i <= n - 4; i += 4) {
        acc0 = _mm_add_ps(acc0, _mm_mul_ps(_mm_loadu_ps(a + i), _mm_loadu_ps(b + i)));
    }

    float total = hsum128_ps(_mm_add_ps(acc0, acc1));

    for (; i < n; ++i) {
        total += a[i] * b[i];
    }

    return -total;
}

float float32_distance_cosine_sse2 (const void *v1, const void *v2, int n) {
    const float *a = (const float *)v1;
    const float *b = (const float *)v2;

    // the three quantities are already independent chains, so one accumulator each keeps
    // the register file within reach of 32-bit x86
    __m128 acc_dot = _mm_setzero_ps();
    __m128 acc_a2 = _mm_setzero_ps();
    __m128 acc_b2 = _mm_setzero_ps();

    int i = 0;
    for (; i <= n - 4; i += 4) {
        __m128 va = _mm_loadu_ps(a + i);
        __m128 vb = _mm_loadu_ps(b + i);

        acc_dot = _mm_add_ps(acc_dot, _mm_mul_ps(va, vb));
        acc_a2  = _mm_add_ps(acc_a2, _mm_mul_ps(va, va));
        acc_b2  = _mm_add_ps(acc_b2, _mm_mul_ps(vb, vb));
    }

    float dot = hsum128_ps(acc_dot);
    float norm_a = hsum128_ps(acc_a2);
    float norm_b = hsum128_ps(acc_b2);

    for (; i < n; ++i) {
        float ai = a[i];
        float bi = b[i];
        dot    += ai * bi;
        norm_a += ai * ai;
        norm_b += bi * bi;
    }

    if (norm_a == 0.0f || norm_b == 0.0f) return 1.0f;

    float cosine_similarity = dot / (sqrtf(norm_a) * sqrtf(norm_b));
    if (cosine_similarity > 1.0f) cosine_similarity = 1.0f;
    if (cosine_similarity < -1.0f) cosine_similarity = -1.0f;
    return 1.0f - cosine_similarity;
}

// MARK: - FLOAT16 -

// MARK: - BFLOAT16 -

// MARK: - UINT8 -

// MARK: - INT8 -

// SSE2 does not support 8-bit integer multiplication directly
// Unpack to 16-bit signed integers
// Multiply using _mm_mullo_epi16, and accumulate in 32-bit lanes

static inline float int8_distance_l2_impl_sse2 (const void *v1, const void *v2, int n, bool use_sqrt) {
    const int8_t *a = (const int8_t *)v1;
    const int8_t *b = (const int8_t *)v2;
    
    __m128i acc = _mm_setzero_si128();
    int i = 0;

    for (; i <= n - 16; i += 16) {
        __m128i va = _mm_loadu_si128((const __m128i *)(a + i));
        __m128i vb = _mm_loadu_si128((const __m128i *)(b + i));

        // unpack to 16-bit signed integers
        __m128i va_lo = _mm_unpacklo_epi8(va, _mm_cmpgt_epi8(_mm_setzero_si128(), va));
        __m128i vb_lo = _mm_unpacklo_epi8(vb, _mm_cmpgt_epi8(_mm_setzero_si128(), vb));
        __m128i va_hi = _mm_unpackhi_epi8(va, _mm_cmpgt_epi8(_mm_setzero_si128(), va));
        __m128i vb_hi = _mm_unpackhi_epi8(vb, _mm_cmpgt_epi8(_mm_setzero_si128(), vb));

        // compute (a - b)
        __m128i diff_lo = _mm_sub_epi16(va_lo, vb_lo);
        __m128i diff_hi = _mm_sub_epi16(va_hi, vb_hi);

        // square differences
        __m128i sq_lo = _mm_mullo_epi16(diff_lo, diff_lo);
        __m128i sq_hi = _mm_mullo_epi16(diff_hi, diff_hi);

        // widen and accumulate
        acc = _mm_add_epi32(acc, _mm_unpacklo_epi16(sq_lo, _mm_setzero_si128()));
        acc = _mm_add_epi32(acc, _mm_unpackhi_epi16(sq_lo, _mm_setzero_si128()));
        acc = _mm_add_epi32(acc, _mm_unpacklo_epi16(sq_hi, _mm_setzero_si128()));
        acc = _mm_add_epi32(acc, _mm_unpackhi_epi16(sq_hi, _mm_setzero_si128()));
    }

    int32_t partial[4];
    _mm_storeu_si128((__m128i *)partial, acc);
    int32_t total = partial[0] + partial[1] + partial[2] + partial[3];

    for (; i < n; ++i) {
        int diff = (int)a[i] - (int)b[i];
        total += diff * diff;
    }

    return use_sqrt ? sqrtf((float)total) : (float)total;
}

float int8_distance_l2_sse2 (const void *v1, const void *v2, int n) {
    return int8_distance_l2_impl_sse2(v1, v2, n, true);
}

float int8_distance_l2_squared_sse2 (const void *v1, const void *v2, int n) {
    return int8_distance_l2_impl_sse2(v1, v2, n, false);
}

float int8_distance_dot_sse2 (const void *v1, const void *v2, int n) {
    const int8_t *a = (const int8_t *)v1;
    const int8_t *b = (const int8_t *)v2;

    __m128i acc = _mm_setzero_si128();
    int i = 0;

    for (; i <= n - 16; i += 16) {
        __m128i va = _mm_loadu_si128((const __m128i *)(a + i));
        __m128i vb = _mm_loadu_si128((const __m128i *)(b + i));

        // Manual sign-extension: int8_t → int16_t
        __m128i zero = _mm_setzero_si128();
        __m128i va_sign = _mm_cmpgt_epi8(zero, va);
        __m128i vb_sign = _mm_cmpgt_epi8(zero, vb);

        __m128i va_lo = _mm_unpacklo_epi8(va, va_sign);
        __m128i va_hi = _mm_unpackhi_epi8(va, va_sign);
        __m128i vb_lo = _mm_unpacklo_epi8(vb, vb_sign);
        __m128i vb_hi = _mm_unpackhi_epi8(vb, vb_sign);

        // Multiply int16 × int16 → int16 (overflow-safe because dot products are small)
        __m128i mul_lo = _mm_mullo_epi16(va_lo, vb_lo);
        __m128i mul_hi = _mm_mullo_epi16(va_hi, vb_hi);

        // Correct signed extension: int16 → int32
        acc = _mm_add_epi32(acc, SIGN_EXTEND_EPI16_TO_EPI32_LO(mul_lo));
        acc = _mm_add_epi32(acc, SIGN_EXTEND_EPI16_TO_EPI32_HI(mul_lo));
        acc = _mm_add_epi32(acc, SIGN_EXTEND_EPI16_TO_EPI32_LO(mul_hi));
        acc = _mm_add_epi32(acc, SIGN_EXTEND_EPI16_TO_EPI32_HI(mul_hi));
    }

    int32_t partial[4];
    _mm_storeu_si128((__m128i *)partial, acc);
    int32_t total = partial[0] + partial[1] + partial[2] + partial[3];

    for (; i < n; ++i) {
        total += (int)a[i] * (int)b[i];
    }

    return -(float)total;
}

float int8_distance_l1_sse2 (const void *v1, const void *v2, int n) {
    const int8_t *a = (const int8_t *)v1;
    const int8_t *b = (const int8_t *)v2;
    
    __m128i acc = _mm_setzero_si128();
    int i = 0;

    for (; i <= n - 16; i += 16) {
        __m128i va = _mm_loadu_si128((const __m128i *)(a + i));
        __m128i vb = _mm_loadu_si128((const __m128i *)(b + i));

        __m128i va_lo = _mm_unpacklo_epi8(va, _mm_cmpgt_epi8(_mm_setzero_si128(), va));
        __m128i vb_lo = _mm_unpacklo_epi8(vb, _mm_cmpgt_epi8(_mm_setzero_si128(), vb));
        __m128i va_hi = _mm_unpackhi_epi8(va, _mm_cmpgt_epi8(_mm_setzero_si128(), va));
        __m128i vb_hi = _mm_unpackhi_epi8(vb, _mm_cmpgt_epi8(_mm_setzero_si128(), vb));

        __m128i diff_lo = _mm_sub_epi16(va_lo, vb_lo);
        __m128i diff_hi = _mm_sub_epi16(va_hi, vb_hi);

        // Absolute value via max/min since _mm_abs_epi16 is SSE3+
        diff_lo = _mm_sub_epi16(_mm_max_epi16(diff_lo, _mm_sub_epi16(_mm_setzero_si128(), diff_lo)),
                                _mm_setzero_si128());
        diff_hi = _mm_sub_epi16(_mm_max_epi16(diff_hi, _mm_sub_epi16(_mm_setzero_si128(), diff_hi)),
                                _mm_setzero_si128());

        acc = _mm_add_epi32(acc, _mm_unpacklo_epi16(diff_lo, _mm_setzero_si128()));
        acc = _mm_add_epi32(acc, _mm_unpackhi_epi16(diff_lo, _mm_setzero_si128()));
        acc = _mm_add_epi32(acc, _mm_unpacklo_epi16(diff_hi, _mm_setzero_si128()));
        acc = _mm_add_epi32(acc, _mm_unpackhi_epi16(diff_hi, _mm_setzero_si128()));
    }

    int32_t partial[4];
    _mm_storeu_si128((__m128i *)partial, acc);
    int32_t total = partial[0] + partial[1] + partial[2] + partial[3];

    for (; i < n; ++i) {
        total += abs((int)a[i] - (int)b[i]);
    }

    return (float)total;
}

float int8_distance_cosine_sse2 (const void *v1, const void *v2, int n) {
    const int8_t *a = (const int8_t *)v1;
    const int8_t *b = (const int8_t *)v2;

    __m128i acc_dot = _mm_setzero_si128();
    __m128i acc_a2  = _mm_setzero_si128();
    __m128i acc_b2  = _mm_setzero_si128();

    int i = 0;
    for (; i <= n - 16; i += 16) {
        __m128i va = _mm_loadu_si128((const __m128i *)(a + i));
        __m128i vb = _mm_loadu_si128((const __m128i *)(b + i));

        // Manual sign extension from int8_t → int16_t
        __m128i zero = _mm_setzero_si128();
        __m128i va_sign = _mm_cmpgt_epi8(zero, va);
        __m128i vb_sign = _mm_cmpgt_epi8(zero, vb);

        __m128i va_lo = _mm_unpacklo_epi8(va, va_sign);  // lower 8 int8_t → int16_t
        __m128i va_hi = _mm_unpackhi_epi8(va, va_sign);  // upper 8 int8_t → int16_t
        __m128i vb_lo = _mm_unpacklo_epi8(vb, vb_sign);
        __m128i vb_hi = _mm_unpackhi_epi8(vb, vb_sign);

        // Multiply and accumulate
        __m128i dot_lo = _mm_mullo_epi16(va_lo, vb_lo);
        __m128i dot_hi = _mm_mullo_epi16(va_hi, vb_hi);
        __m128i a2_lo  = _mm_mullo_epi16(va_lo, va_lo);
        __m128i a2_hi  = _mm_mullo_epi16(va_hi, va_hi);
        __m128i b2_lo  = _mm_mullo_epi16(vb_lo, vb_lo);
        __m128i b2_hi  = _mm_mullo_epi16(vb_hi, vb_hi);

        // Unpack 16-bit to 32-bit and accumulate
        acc_dot = _mm_add_epi32(acc_dot, SIGN_EXTEND_EPI16_TO_EPI32_LO(dot_lo));
        acc_dot = _mm_add_epi32(acc_dot, SIGN_EXTEND_EPI16_TO_EPI32_HI(dot_lo));
        acc_dot = _mm_add_epi32(acc_dot, SIGN_EXTEND_EPI16_TO_EPI32_LO(dot_hi));
        acc_dot = _mm_add_epi32(acc_dot, SIGN_EXTEND_EPI16_TO_EPI32_HI(dot_hi));

        acc_a2 = _mm_add_epi32(acc_a2, SIGN_EXTEND_EPI16_TO_EPI32_LO(a2_lo));
        acc_a2 = _mm_add_epi32(acc_a2, SIGN_EXTEND_EPI16_TO_EPI32_HI(a2_lo));
        acc_a2 = _mm_add_epi32(acc_a2, SIGN_EXTEND_EPI16_TO_EPI32_LO(a2_hi));
        acc_a2 = _mm_add_epi32(acc_a2, SIGN_EXTEND_EPI16_TO_EPI32_HI(a2_hi));

        acc_b2 = _mm_add_epi32(acc_b2, SIGN_EXTEND_EPI16_TO_EPI32_LO(b2_lo));
        acc_b2 = _mm_add_epi32(acc_b2, SIGN_EXTEND_EPI16_TO_EPI32_HI(b2_lo));
        acc_b2 = _mm_add_epi32(acc_b2, SIGN_EXTEND_EPI16_TO_EPI32_LO(b2_hi));
        acc_b2 = _mm_add_epi32(acc_b2, SIGN_EXTEND_EPI16_TO_EPI32_HI(b2_hi));
    }

    // Horizontal sum of SIMD accumulators
    int32_t _d[4], _a[4], _b[4];
    _mm_storeu_si128((__m128i *)_d, acc_dot);
    _mm_storeu_si128((__m128i *)_a, acc_a2);
    _mm_storeu_si128((__m128i *)_b, acc_b2);

    int32_t total_dot = _d[0] + _d[1] + _d[2] + _d[3];
    int32_t total_a2  = _a[0] + _a[1] + _a[2] + _a[3];
    int32_t total_b2  = _b[0] + _b[1] + _b[2] + _b[3];

    // Handle tail
    for (; i < n; ++i) {
        int va = a[i];
        int vb = b[i];
        total_dot += va * vb;
        total_a2  += va * va;
        total_b2  += vb * vb;
    }

    float denom = sqrtf((float)total_a2 * (float)total_b2);
    if (denom == 0.0f) return 1.0f;
    float cosine_sim = total_dot / denom;
    if (cosine_sim > 1.0f) cosine_sim = 1.0f;
    if (cosine_sim < -1.0f) cosine_sim = -1.0f;
    return 1.0f - cosine_sim;
}

// MARK: - BIT -

static inline __m128i popcount_sse2 (__m128i v) {
    // Classic parallel bit count algorithm vectorized for SSE2
    
    const __m128i mask1 = _mm_set1_epi8(0x55);  // 01010101
    const __m128i mask2 = _mm_set1_epi8(0x33);  // 00110011
    const __m128i mask4 = _mm_set1_epi8(0x0f);  // 00001111
    
    // x = x - ((x >> 1) & 0x55555555)
    __m128i t = _mm_and_si128(_mm_srli_epi16(v, 1), mask1);
    v = _mm_sub_epi8(v, t);
    
    // x = (x & 0x33333333) + ((x >> 2) & 0x33333333)
    t = _mm_and_si128(_mm_srli_epi16(v, 2), mask2);
    v = _mm_add_epi8(_mm_and_si128(v, mask2), t);
    
    // x = (x + (x >> 4)) & 0x0f0f0f0f
    t = _mm_srli_epi16(v, 4);
    v = _mm_and_si128(_mm_add_epi8(v, t), mask4);
    
    // Now each byte contains popcount for that byte (0-8)
    return v;
}

float bit1_distance_hamming_sse2 (const void *v1, const void *v2, int n) {
    const uint8_t *a = (const uint8_t *)v1;
    const uint8_t *b = (const uint8_t *)v2;
    __m128i acc = _mm_setzero_si128();
    int i = 0;
    
    // Process 16 bytes at a time
    for (; i + 16 <= n; i += 16) {
        __m128i va = _mm_loadu_si128((const __m128i *)(a + i));
        __m128i vb = _mm_loadu_si128((const __m128i *)(b + i));
        __m128i xored = _mm_xor_si128(va, vb);
        __m128i popcnt = popcount_sse2(xored);
        
        // Sum bytes using SAD (sum of absolute differences against zero)
        // This sums all 16 bytes into two 64-bit values
        acc = _mm_add_epi64(acc, _mm_sad_epu8(popcnt, _mm_setzero_si128()));
    }
    
    // Horizontal sum of the two 64-bit accumulators
    int distance = _mm_cvtsi128_si64(acc) + _mm_cvtsi128_si64(_mm_srli_si128(acc, 8));
    
    // Handle remainder with scalar code
    for (; i < n; i++) {
        #if defined(__GNUC__) || defined(__clang__)
        distance += __builtin_popcount(a[i] ^ b[i]);
        #else
        uint8_t x = a[i] ^ b[i];
        x = x - ((x >> 1) & 0x55);
        x = (x & 0x33) + ((x >> 2) & 0x33);
        distance += (x + (x >> 4)) & 0x0f;
        #endif
    }
    
    return (float)distance;
}



#endif

// MARK: -

bool init_distance_functions_sse2 (void) {
#if defined(__SSE2__) || (defined(_MSC_VER) && (defined(_M_X64) || (_M_IX86_FP >= 2)))
    dispatch_distance_table[VECTOR_DISTANCE_L2][VECTOR_TYPE_F32] = float32_distance_l2_sse2;
    dispatch_distance_table[VECTOR_DISTANCE_L2][VECTOR_TYPE_I8] = int8_distance_l2_sse2;
    
    dispatch_distance_table[VECTOR_DISTANCE_SQUARED_L2][VECTOR_TYPE_F32] = float32_distance_l2_squared_sse2;
    dispatch_distance_table[VECTOR_DISTANCE_SQUARED_L2][VECTOR_TYPE_I8] = int8_distance_l2_squared_sse2;
    
    dispatch_distance_table[VECTOR_DISTANCE_COSINE][VECTOR_TYPE_F32] = float32_distance_cosine_sse2;
    dispatch_distance_table[VECTOR_DISTANCE_COSINE][VECTOR_TYPE_I8] = int8_distance_cosine_sse2;
    
    dispatch_distance_table[VECTOR_DISTANCE_DOT][VECTOR_TYPE_F32] = float32_distance_dot_sse2;
    dispatch_distance_table[VECTOR_DISTANCE_DOT][VECTOR_TYPE_I8] = int8_distance_dot_sse2;
    
    dispatch_distance_table[VECTOR_DISTANCE_L1][VECTOR_TYPE_F32] = float32_distance_l1_sse2;
    dispatch_distance_table[VECTOR_DISTANCE_L1][VECTOR_TYPE_I8] = int8_distance_l1_sse2;
    
    dispatch_distance_table[VECTOR_DISTANCE_HAMMING][VECTOR_TYPE_BIT] = bit1_distance_hamming_sse2;
    
    distance_backend_name = "SSE2";
    // the TurboQuant lookup scan is gather-bound and shared by every backend
    turbo_lut_dot_function = turbo_lut_dot_cpu;
    turbo_lut_backend_name = "SSE2";
    return true;
#else
    return false;
#endif
}
