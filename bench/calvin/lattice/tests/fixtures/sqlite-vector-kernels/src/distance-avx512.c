//
//  distance-avx512.c
//  sqlitevector
//
//  Converted to AVX-512
//

#include "distance-avx512.h"
#include "distance-cpu.h"

// Check for AVX512 Foundation (F) and Byte/Word (BW) which are standard on Skylake-X/IceLake+
#if defined(__AVX512F__) && defined(__AVX512BW__) && defined(__AVX512VL__) && defined(__AVX512DQ__) 
#include <immintrin.h>
#include <stdint.h>
#include <math.h>

extern distance_function_t dispatch_distance_table[VECTOR_DISTANCE_MAX][VECTOR_TYPE_MAX];
extern const char *distance_backend_name;
extern turbo_lut_dot_function_t turbo_lut_dot_function;
extern const char *turbo_lut_backend_name;

// Abs for f32 (AVX512F has native abs)
#define _mm512_abs_ps(x) _mm512_abs_ps(x)

// Horizontal sum for __m512 (f32) -> float
static inline float hsum512_ps(__m512 v) {
    return _mm512_reduce_add_ps(v);
}

// Horizontal sum for __m512d (f64) -> double
static inline double hsum512d(__m512d v) {
    return _mm512_reduce_add_pd(v);
}

// per-block Inf mismatch test on 16 lanes (returns true if L1/L2 should be +Inf)
static inline bool block_has_l2_inf_mismatch_16(const uint16_t* a, const uint16_t* b) {
    /* mismatch if (a_inf ^ b_inf) OR (both Inf and signs differ) */
    /* This loop is scalar, but checked per block of 16 to match vector stride */
    for (int k = 0; k < 16; ++k) {
        uint16_t ak = a[k], bk = b[k];
        bool ai = f16_is_inf(ak), bi = f16_is_inf(bk);
        if ((ai ^ bi) || (ai && bi && (f16_sign(ak) != f16_sign(bk)))) return true;
    }
    return false;
}

/* 16�bf16 -> 16�f32: widen to u32, shift <<16, reinterpret as f32 */
static inline __m512 bf16x16_to_f32x16_loadu(const uint16_t* p) {
    // Load 16x u16 (256 bits)
    __m256i v16 = _mm256_loadu_si256((const __m256i*)p);
    // Widen to 16x u32 (512 bits)
    __m512i v32 = _mm512_cvtepu16_epi32(v16);
    // Shift left 16
    v32 = _mm512_slli_epi32(v32, 16);
    // Bitcast to f32
    return _mm512_castsi512_ps(v32);
}

/* Any lane has infinite difference? (a_inf ^ b_inf) || (both inf and signs differ) */
static inline bool block_has_l2_inf_mismatch_bf16_16(const uint16_t* a, const uint16_t* b) {
    for (int k = 0; k < 16; ++k) {
        uint16_t ak = a[k], bk = b[k];
        bool ai = bfloat16_is_inf(ak), bi = bfloat16_is_inf(bk);
        if ((ai ^ bi) || (ai && bi && (bfloat16_sign(ak) != bfloat16_sign(bk)))) return true;
    }
    return false;
}


// MARK: - FLOAT32 -

// A single accumulator makes the loop one dependency chain: an FMA has around four cycles
// of latency, so it retires one vector every four cycles however many FMA ports the core
// has. Four independent accumulators keep them fed; 32 ZMM registers hold them easily.
static inline float float32_distance_l2_impl_avx512(const void* v1, const void* v2, int n, bool use_sqrt) {
    const float* a = (const float*)v1;
    const float* b = (const float*)v2;

    __m512 acc0 = _mm512_setzero_ps(), acc1 = acc0, acc2 = acc0, acc3 = acc0;
    int i = 0;

    for (; i <= n - 64; i += 64) {
        __m512 d0 = _mm512_sub_ps(_mm512_loadu_ps(a + i     ), _mm512_loadu_ps(b + i     ));
        __m512 d1 = _mm512_sub_ps(_mm512_loadu_ps(a + i + 16), _mm512_loadu_ps(b + i + 16));
        __m512 d2 = _mm512_sub_ps(_mm512_loadu_ps(a + i + 32), _mm512_loadu_ps(b + i + 32));
        __m512 d3 = _mm512_sub_ps(_mm512_loadu_ps(a + i + 48), _mm512_loadu_ps(b + i + 48));
        acc0 = _mm512_fmadd_ps(d0, d0, acc0);
        acc1 = _mm512_fmadd_ps(d1, d1, acc1);
        acc2 = _mm512_fmadd_ps(d2, d2, acc2);
        acc3 = _mm512_fmadd_ps(d3, d3, acc3);
    }
    for (; i <= n - 16; i += 16) {
        __m512 d = _mm512_sub_ps(_mm512_loadu_ps(a + i), _mm512_loadu_ps(b + i));
        acc0 = _mm512_fmadd_ps(d, d, acc0);
    }

    float total = hsum512_ps(_mm512_add_ps(_mm512_add_ps(acc0, acc1), _mm512_add_ps(acc2, acc3)));

    for (; i < n; ++i) {
        float d = a[i] - b[i];
        total += d * d;
    }

    return use_sqrt ? sqrtf(total) : total;
}

float float32_distance_l2_avx512(const void* v1, const void* v2, int n) {
    return float32_distance_l2_impl_avx512(v1, v2, n, true);
}

float float32_distance_l2_squared_avx512(const void* v1, const void* v2, int n) {
    return float32_distance_l2_impl_avx512(v1, v2, n, false);
}

float float32_distance_l1_avx512(const void* v1, const void* v2, int n) {
    const float* a = (const float*)v1;
    const float* b = (const float*)v2;

    __m512 acc0 = _mm512_setzero_ps(), acc1 = acc0, acc2 = acc0, acc3 = acc0;
    int i = 0;

    for (; i <= n - 64; i += 64) {
        __m512 d0 = _mm512_sub_ps(_mm512_loadu_ps(a + i     ), _mm512_loadu_ps(b + i     ));
        __m512 d1 = _mm512_sub_ps(_mm512_loadu_ps(a + i + 16), _mm512_loadu_ps(b + i + 16));
        __m512 d2 = _mm512_sub_ps(_mm512_loadu_ps(a + i + 32), _mm512_loadu_ps(b + i + 32));
        __m512 d3 = _mm512_sub_ps(_mm512_loadu_ps(a + i + 48), _mm512_loadu_ps(b + i + 48));
        acc0 = _mm512_add_ps(acc0, _mm512_abs_ps(d0));
        acc1 = _mm512_add_ps(acc1, _mm512_abs_ps(d1));
        acc2 = _mm512_add_ps(acc2, _mm512_abs_ps(d2));
        acc3 = _mm512_add_ps(acc3, _mm512_abs_ps(d3));
    }
    for (; i <= n - 16; i += 16) {
        __m512 d = _mm512_sub_ps(_mm512_loadu_ps(a + i), _mm512_loadu_ps(b + i));
        acc0 = _mm512_add_ps(acc0, _mm512_abs_ps(d));
    }

    float total = hsum512_ps(_mm512_add_ps(_mm512_add_ps(acc0, acc1), _mm512_add_ps(acc2, acc3)));

    for (; i < n; ++i) {
        total += fabsf(a[i] - b[i]);
    }

    return total;
}

float float32_distance_dot_avx512(const void* v1, const void* v2, int n) {
    const float* a = (const float*)v1;
    const float* b = (const float*)v2;

    __m512 acc0 = _mm512_setzero_ps(), acc1 = acc0, acc2 = acc0, acc3 = acc0;
    int i = 0;

    for (; i <= n - 64; i += 64) {
        acc0 = _mm512_fmadd_ps(_mm512_loadu_ps(a + i     ), _mm512_loadu_ps(b + i     ), acc0);
        acc1 = _mm512_fmadd_ps(_mm512_loadu_ps(a + i + 16), _mm512_loadu_ps(b + i + 16), acc1);
        acc2 = _mm512_fmadd_ps(_mm512_loadu_ps(a + i + 32), _mm512_loadu_ps(b + i + 32), acc2);
        acc3 = _mm512_fmadd_ps(_mm512_loadu_ps(a + i + 48), _mm512_loadu_ps(b + i + 48), acc3);
    }
    for (; i <= n - 16; i += 16) {
        acc0 = _mm512_fmadd_ps(_mm512_loadu_ps(a + i), _mm512_loadu_ps(b + i), acc0);
    }

    float total = hsum512_ps(_mm512_add_ps(_mm512_add_ps(acc0, acc1), _mm512_add_ps(acc2, acc3)));

    for (; i < n; ++i) {
        total += a[i] * b[i];
    }

    return -total;
}

float float32_distance_cosine_avx512(const void* a, const void* b, int n) {
    const float* x = (const float*)a;
    const float* y = (const float*)b;

    // one fused pass, not three calls to the dot kernel: the data is read once instead of
    // three times, which is what actually costs on anything larger than L1
    __m512 dot0 = _mm512_setzero_ps(), dot1 = dot0;
    __m512 na0 = dot0, na1 = dot0;
    __m512 nb0 = dot0, nb1 = dot0;
    int i = 0;

    for (; i <= n - 32; i += 32) {
        __m512 a0 = _mm512_loadu_ps(x + i), a1 = _mm512_loadu_ps(x + i + 16);
        __m512 b0 = _mm512_loadu_ps(y + i), b1 = _mm512_loadu_ps(y + i + 16);
        dot0 = _mm512_fmadd_ps(a0, b0, dot0);  dot1 = _mm512_fmadd_ps(a1, b1, dot1);
        na0  = _mm512_fmadd_ps(a0, a0, na0);   na1  = _mm512_fmadd_ps(a1, a1, na1);
        nb0  = _mm512_fmadd_ps(b0, b0, nb0);   nb1  = _mm512_fmadd_ps(b1, b1, nb1);
    }
    for (; i <= n - 16; i += 16) {
        __m512 va = _mm512_loadu_ps(x + i), vb = _mm512_loadu_ps(y + i);
        dot0 = _mm512_fmadd_ps(va, vb, dot0);
        na0  = _mm512_fmadd_ps(va, va, na0);
        nb0  = _mm512_fmadd_ps(vb, vb, nb0);
    }

    float dot = hsum512_ps(_mm512_add_ps(dot0, dot1));
    float norm_a = hsum512_ps(_mm512_add_ps(na0, na1));
    float norm_b = hsum512_ps(_mm512_add_ps(nb0, nb1));

    for (; i < n; ++i) {
        float ai = x[i];
        float bi = y[i];
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

// Same shape as the AVX2 integer kernels, 64 bytes at a time: PSADBW for L1, and PMADDWD
// on widened bytes for squared differences and dot products. The previous versions
// widened every byte to 32 bits before multiplying, on one accumulator chain.
static inline __m512i abs_diff_epu8_512 (__m512i a, __m512i b) {
    return _mm512_or_si512(_mm512_subs_epu8(a, b), _mm512_subs_epu8(b, a));
}

static inline __m512i sqdiff_epu8_512 (__m512i a, __m512i b) {
    __m512i d = abs_diff_epu8_512(a, b);
    __m512i lo = _mm512_unpacklo_epi8(d, _mm512_setzero_si512());
    __m512i hi = _mm512_unpackhi_epi8(d, _mm512_setzero_si512());
    return _mm512_add_epi32(_mm512_madd_epi16(lo, lo), _mm512_madd_epi16(hi, hi));
}

static inline __m512i dot_epu8_512 (__m512i a, __m512i b) {
    const __m512i zero = _mm512_setzero_si512();
    __m512i al = _mm512_unpacklo_epi8(a, zero), ah = _mm512_unpackhi_epi8(a, zero);
    __m512i bl = _mm512_unpacklo_epi8(b, zero), bh = _mm512_unpackhi_epi8(b, zero);
    return _mm512_add_epi32(_mm512_madd_epi16(al, bl), _mm512_madd_epi16(ah, bh));
}

static inline __m512i dot_epi8_512 (__m512i a, __m512i b) {
    __m512i al = _mm512_cvtepi8_epi16(_mm512_castsi512_si256(a));
    __m512i ah = _mm512_cvtepi8_epi16(_mm512_extracti64x4_epi64(a, 1));
    __m512i bl = _mm512_cvtepi8_epi16(_mm512_castsi512_si256(b));
    __m512i bh = _mm512_cvtepi8_epi16(_mm512_extracti64x4_epi64(b, 1));
    return _mm512_add_epi32(_mm512_madd_epi16(al, bl), _mm512_madd_epi16(ah, bh));
}

// widen to 64 bits before folding the lanes: each lane is a running total, and summing
// sixteen of them in 32 bits would cap the usable dimension
static inline uint64_t hsum512_epu32 (__m512i v) {
    const __m512i zero = _mm512_setzero_si512();
    __m512i lo = _mm512_unpacklo_epi32(v, zero);
    __m512i hi = _mm512_unpackhi_epi32(v, zero);
    return (uint64_t)_mm512_reduce_add_epi64(_mm512_add_epi64(lo, hi));
}

static inline int64_t hsum512_epi32_signed (__m512i v) {
    __m512i lo = _mm512_cvtepi32_epi64(_mm512_castsi512_si256(v));
    __m512i hi = _mm512_cvtepi32_epi64(_mm512_extracti64x4_epi64(v, 1));
    return _mm512_reduce_add_epi64(_mm512_add_epi64(lo, hi));
}

// MARK: - INT8 -

// biasing an int8 by 0x80 maps it onto uint8 without changing any difference between two
// elements, so L2 and L1 are the unsigned kernel plus one XOR per vector
#define S8_TO_BIASED_U8_512(_v)             _mm512_xor_si512((_v), _mm512_set1_epi8((char)0x80))

static inline float int8_distance_l2_impl_avx512(const void* v1, const void* v2, int n, bool use_sqrt) {
    const int8_t* a = (const int8_t*)v1;
    const int8_t* b = (const int8_t*)v2;

    __m512i acc0 = _mm512_setzero_si512(), acc1 = acc0;
    int i = 0;

    for (; i <= n - 128; i += 128) {
        acc0 = _mm512_add_epi32(acc0, sqdiff_epu8_512(S8_TO_BIASED_U8_512(_mm512_loadu_si512((const void *)(a + i))),
                                                      S8_TO_BIASED_U8_512(_mm512_loadu_si512((const void *)(b + i)))));
        acc1 = _mm512_add_epi32(acc1, sqdiff_epu8_512(S8_TO_BIASED_U8_512(_mm512_loadu_si512((const void *)(a + i + 64))),
                                                      S8_TO_BIASED_U8_512(_mm512_loadu_si512((const void *)(b + i + 64)))));
    }
    for (; i <= n - 64; i += 64) {
        acc0 = _mm512_add_epi32(acc0, sqdiff_epu8_512(S8_TO_BIASED_U8_512(_mm512_loadu_si512((const void *)(a + i))),
                                                      S8_TO_BIASED_U8_512(_mm512_loadu_si512((const void *)(b + i)))));
    }

    uint64_t total = hsum512_epu32(_mm512_add_epi32(acc0, acc1));

    for (; i < n; ++i) {
        int d = (int)a[i] - (int)b[i];
        total += (uint64_t)(d * d);
    }

    return use_sqrt ? sqrtf((float)total) : (float)total;
}

float int8_distance_l2_avx512(const void* v1, const void* v2, int n) {
    return int8_distance_l2_impl_avx512(v1, v2, n, true);
}

float int8_distance_l2_squared_avx512(const void* v1, const void* v2, int n) {
    return int8_distance_l2_impl_avx512(v1, v2, n, false);
}

float int8_distance_dot_avx512(const void* v1, const void* v2, int n) {
    const int8_t* a = (const int8_t*)v1;
    const int8_t* b = (const int8_t*)v2;

    __m512i acc0 = _mm512_setzero_si512(), acc1 = acc0;
    int i = 0;

    for (; i <= n - 128; i += 128) {
        acc0 = _mm512_add_epi32(acc0, dot_epi8_512(_mm512_loadu_si512((const void *)(a + i)),
                                                   _mm512_loadu_si512((const void *)(b + i))));
        acc1 = _mm512_add_epi32(acc1, dot_epi8_512(_mm512_loadu_si512((const void *)(a + i + 64)),
                                                   _mm512_loadu_si512((const void *)(b + i + 64))));
    }
    for (; i <= n - 64; i += 64) {
        acc0 = _mm512_add_epi32(acc0, dot_epi8_512(_mm512_loadu_si512((const void *)(a + i)),
                                                   _mm512_loadu_si512((const void *)(b + i))));
    }

    int64_t dot = hsum512_epi32_signed(_mm512_add_epi32(acc0, acc1));

    for (; i < n; ++i) dot += (int64_t)((int32_t)a[i] * (int32_t)b[i]);

    return -(float)dot;
}

float int8_distance_l1_avx512(const void* v1, const void* v2, int n) {
    const int8_t* a = (const int8_t*)v1;
    const int8_t* b = (const int8_t*)v2;

    __m512i acc0 = _mm512_setzero_si512(), acc1 = acc0;
    int i = 0;

    for (; i <= n - 128; i += 128) {
        acc0 = _mm512_add_epi64(acc0, _mm512_sad_epu8(S8_TO_BIASED_U8_512(_mm512_loadu_si512((const void *)(a + i))),
                                                      S8_TO_BIASED_U8_512(_mm512_loadu_si512((const void *)(b + i)))));
        acc1 = _mm512_add_epi64(acc1, _mm512_sad_epu8(S8_TO_BIASED_U8_512(_mm512_loadu_si512((const void *)(a + i + 64))),
                                                      S8_TO_BIASED_U8_512(_mm512_loadu_si512((const void *)(b + i + 64)))));
    }
    for (; i <= n - 64; i += 64) {
        acc0 = _mm512_add_epi64(acc0, _mm512_sad_epu8(S8_TO_BIASED_U8_512(_mm512_loadu_si512((const void *)(a + i))),
                                                      S8_TO_BIASED_U8_512(_mm512_loadu_si512((const void *)(b + i)))));
    }

    uint64_t sum = (uint64_t)_mm512_reduce_add_epi64(_mm512_add_epi64(acc0, acc1));

    for (; i < n; ++i) sum += (uint64_t)abs((int)a[i] - (int)b[i]);

    return (float)sum;
}

float int8_distance_cosine_avx512(const void* a, const void* b, int n) {
    const int8_t* x = (const int8_t*)a;
    const int8_t* y = (const int8_t*)b;

    __m512i dacc = _mm512_setzero_si512(), aacc = dacc, bacc = dacc;
    int i = 0;

    for (; i <= n - 64; i += 64) {
        __m512i va = _mm512_loadu_si512((const void *)(x + i));
        __m512i vb = _mm512_loadu_si512((const void *)(y + i));
        dacc = _mm512_add_epi32(dacc, dot_epi8_512(va, vb));
        aacc = _mm512_add_epi32(aacc, dot_epi8_512(va, va));
        bacc = _mm512_add_epi32(bacc, dot_epi8_512(vb, vb));
    }

    int64_t dot = hsum512_epi32_signed(dacc);
    int64_t norm_a = hsum512_epi32_signed(aacc);
    int64_t norm_b = hsum512_epi32_signed(bacc);

    for (; i < n; ++i) {
        int32_t p = x[i], q = y[i];
        dot += (int64_t)(p * q);
        norm_a += (int64_t)(p * p);
        norm_b += (int64_t)(q * q);
    }

    if (norm_a == 0 || norm_b == 0) return 1.0f;

    float cosine_similarity = (float)((double)dot / (sqrt((double)norm_a) * sqrt((double)norm_b)));
    if (cosine_similarity > 1.0f) cosine_similarity = 1.0f;
    if (cosine_similarity < -1.0f) cosine_similarity = -1.0f;
    return 1.0f - cosine_similarity;
}

// MARK: - BIT -

// AVX-512 popcount using lookup table (works on all AVX-512 CPUs)
static inline __m512i popcount_avx512(__m512i v) {
    // Lookup table for popcount of 4-bit values
    const __m512i popcount_lut = _mm512_set_epi8(
        4, 3, 3, 2, 3, 2, 2, 1, 3, 2, 2, 1, 2, 1, 1, 0,
        4, 3, 3, 2, 3, 2, 2, 1, 3, 2, 2, 1, 2, 1, 1, 0,
        4, 3, 3, 2, 3, 2, 2, 1, 3, 2, 2, 1, 2, 1, 1, 0,
        4, 3, 3, 2, 3, 2, 2, 1, 3, 2, 2, 1, 2, 1, 1, 0
    );
    const __m512i low_mask = _mm512_set1_epi8(0x0f);

    __m512i lo = _mm512_and_si512(v, low_mask);
    __m512i hi = _mm512_and_si512(_mm512_srli_epi16(v, 4), low_mask);
    __m512i cnt_lo = _mm512_shuffle_epi8(popcount_lut, lo);
    __m512i cnt_hi = _mm512_shuffle_epi8(popcount_lut, hi);
    return _mm512_add_epi8(cnt_lo, cnt_hi);
}

// Hamming distance for 1-bit packed binary vectors
// n = number of bytes (callers pass (dimension + 7) / 8)
static float bit1_distance_hamming_avx512(const void *v1, const void *v2, int n) {
    const uint8_t *a = (const uint8_t *)v1;
    const uint8_t *b = (const uint8_t *)v2;

    __m512i acc = _mm512_setzero_si512();
    int i = 0;

    // Process 64 bytes at a time
    for (; i + 64 <= n; i += 64) {
        __m512i va = _mm512_loadu_si512((const __m512i *)(a + i));
        __m512i vb = _mm512_loadu_si512((const __m512i *)(b + i));
        __m512i xored = _mm512_xor_si512(va, vb);

#if defined(__AVX512VPOPCNTDQ__)
        // Native popcount (Ice Lake+)
        __m512i popcnt = _mm512_popcnt_epi64(xored);
        acc = _mm512_add_epi64(acc, popcnt);
#else
        // Lookup table popcount (Skylake-X compatible)
        __m512i popcnt = popcount_avx512(xored);
        // Sum bytes to 64-bit using SAD against zero
        acc = _mm512_add_epi64(acc, _mm512_sad_epu8(popcnt, _mm512_setzero_si512()));
#endif
    }

    // Horizontal sum
    uint64_t distance = _mm512_reduce_add_epi64(acc);

    // Handle remaining bytes with scalar code
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

bool init_distance_functions_avx512(void) {
#if defined(__AVX512F__) && defined(__AVX512BW__) && defined(__AVX512VL__) && defined(__AVX512DQ__)
    dispatch_distance_table[VECTOR_DISTANCE_L2][VECTOR_TYPE_F32] = float32_distance_l2_avx512;
    dispatch_distance_table[VECTOR_DISTANCE_L2][VECTOR_TYPE_I8] = int8_distance_l2_avx512;

    dispatch_distance_table[VECTOR_DISTANCE_SQUARED_L2][VECTOR_TYPE_F32] = float32_distance_l2_squared_avx512;
    dispatch_distance_table[VECTOR_DISTANCE_SQUARED_L2][VECTOR_TYPE_I8] = int8_distance_l2_squared_avx512;

    dispatch_distance_table[VECTOR_DISTANCE_COSINE][VECTOR_TYPE_F32] = float32_distance_cosine_avx512;
    dispatch_distance_table[VECTOR_DISTANCE_COSINE][VECTOR_TYPE_I8] = int8_distance_cosine_avx512;

    dispatch_distance_table[VECTOR_DISTANCE_DOT][VECTOR_TYPE_F32] = float32_distance_dot_avx512;
    dispatch_distance_table[VECTOR_DISTANCE_DOT][VECTOR_TYPE_I8] = int8_distance_dot_avx512;

    dispatch_distance_table[VECTOR_DISTANCE_L1][VECTOR_TYPE_F32] = float32_distance_l1_avx512;
    dispatch_distance_table[VECTOR_DISTANCE_L1][VECTOR_TYPE_I8] = int8_distance_l1_avx512;

    dispatch_distance_table[VECTOR_DISTANCE_HAMMING][VECTOR_TYPE_BIT] = bit1_distance_hamming_avx512;

    distance_backend_name = "AVX512";
    // the TurboQuant lookup scan is gather-bound and shared by every backend
    turbo_lut_dot_function = turbo_lut_dot_cpu;
    turbo_lut_backend_name = "AVX512";
    return true;
#else
    return false;
#endif
}
