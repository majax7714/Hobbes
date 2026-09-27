# 2058 "/usr/lib/llvm-18/lib/clang/18/include/emmintrin.h" 3
static __inline__ __m128i __attribute__((__always_inline__, __nodebug__, __target__("sse2,no-evex512"), __min_vector_width__(128))) _mm_add_epi32(__m128i __a,

# 590 "/usr/lib/llvm-18/lib/clang/18/include/tmmintrin.h" 3
static __inline__ __m128i __attribute__((__always_inline__, __nodebug__, __target__("ssse3,no-evex512"), __min_vector_width__(64)))
_mm_shuffle_epi8(__m128i __a, __m128i __b)

# 188 "/usr/lib/llvm-18/lib/clang/18/include/pmmintrin.h" 3
static __inline__ __m128d __attribute__((__always_inline__, __nodebug__, __target__("sse3,no-evex512"), __min_vector_width__(128)))
_mm_hadd_pd(__m128d __a, __m128d __b)

# 315 "/usr/lib/llvm-18/lib/clang/18/include/avx2intrin.h" 3
static __inline__ __m256i __attribute__((__always_inline__, __nodebug__, __target__("avx2,no-evex512"), __min_vector_width__(256)))
_mm256_add_epi32(__m256i __a, __m256i __b)

# 3459 "/usr/lib/llvm-18/lib/clang/18/include/avx2intrin.h" 3
#define _mm256_extracti128_si256(V,M) ((__m128i)__builtin_ia32_extract128i256((__v4di)(__m256i)(V), (int)(M)))
static __inline__ __m256i __attribute__((__always_inline__, __nodebug__, __target__("avx2,no-evex512"), __min_vector_width__(256)))
_mm256_maskload_epi32(int const *__X, __m256i __M)
static __inline__ __m256i __attribute__((__always_inline__, __nodebug__, __target__("avx2,no-evex512"), __min_vector_width__(256)))
_mm256_maskload_epi64(long long const *__X, __m256i __M)
static __inline__ __m128i __attribute__((__always_inline__, __nodebug__, __target__("avx2,no-evex512"), __min_vector_width__(128)))
_mm_maskload_epi32(int const *__X, __m128i __M)

# 9335 "/usr/lib/llvm-18/lib/clang/18/include/avx512fintrin.h" 3
static __inline__ float __attribute__((__always_inline__, __nodebug__, __target__("avx512f,evex512"), __min_vector_width__(512)))
_mm512_reduce_add_ps(__m512 __W) {

# 636 "/usr/lib/llvm-18/lib/clang/18/include/avx512fintrin.h" 3
#define _mm512_extracti32x4_epi32(A,imm) ((__m128i)__builtin_ia32_extracti32x4_mask((__v16si)(__m512i)(A), (int)(imm), (__v4si)_mm_undefined_si128(), (__mmask8)-1))
static __inline __m512i __attribute__((__always_inline__, __nodebug__, __target__("avx512f,evex512"), __min_vector_width__(512)))
_mm512_zextsi256_si512(__m256i __a)
static __inline__ __m512i __attribute__((__always_inline__, __nodebug__, __target__("avx512f,evex512"), __min_vector_width__(512)))
_mm512_and_epi32(__m512i __a, __m512i __b)
static __inline__ __m512i __attribute__((__always_inline__, __nodebug__, __target__("avx512f,evex512"), __min_vector_width__(512)))
_mm512_mask_and_epi32(__m512i __src, __mmask16 __k, __m512i __a, __m512i __b)

# 16 "/usr/lib/llvm-18/lib/clang/18/include/avx512vpopcntdqintrin.h" 3
static __inline__ __m512i __attribute__((__always_inline__, __nodebug__, __target__("avx512vpopcntdq,evex512"), __min_vector_width__(512))) _mm512_popcnt_epi64(__m512i __A) {

# 4726 "/usr/lib/llvm-18/lib/clang/18/include/emmintrin.h" 3
static __inline__ __m128 __attribute__((__always_inline__, __nodebug__, __target__("sse2,no-evex512"), __min_vector_width__(128))) _mm_castsi128_ps(__m128i __a) {

@@MACROS@@
#define __AVX2__ 1
#define __AVX512BW__ 1
#define __AVX512DQ__ 1
#define __AVX512F__ 1
#define __AVX512VL__ 1
#define __AVX__ 1
#define __BIGGEST_ALIGNMENT__ 1
#define __CONSTANT_CFSTRINGS__ 1
#define __CRC32__ 1
#define __DBL_DECIMAL_DIG__ 1
#define __DBL_DIG__ 1
#define __DBL_HAS_DENORM__ 1
#define __DBL_HAS_INFINITY__ 1
#define __DBL_HAS_QUIET_NAN__ 1
#define __DBL_MAX_EXP__ 1
#define __DBL_MAX__ 1
#define __ELF__ 1
#define __EVEX256__ 1
#define __EVEX512__ 1
#define __F16C__ 1
#define __FLOAT128__ 1
#define __FLT16_HAS_DENORM__ 1
#define __FLT16_HAS_INFINITY__ 1
#define __FLT16_HAS_QUIET_NAN__ 1
#define __FLT16_MANT_DIG__ 1
#define __FLT16_MAX_EXP__ 1
#define __FLT_DENORM_MIN__ 1
#define __FLT_EPSILON__ 1
#define __FLT_HAS_DENORM__ 1
#define __FLT_HAS_INFINITY__ 1
#define __FLT_HAS_QUIET_NAN__ 1
#define __FLT_MAX_EXP__ 1
#define __FLT_MIN__ 1
#define __FMA__ 1
#define __FXSR__ 1
#define __GCC_ASM_FLAG_OUTPUTS__ 1
#define __GNUC_PATCHLEVEL__ 1
#define __GNUC_STDC_INLINE__ 1
#define __INT8_MAX__ 1
#define __INT_FAST16_WIDTH__ 1
#define __INT_FAST8_MAX__ 1
#define __INT_LEAST16_WIDTH__ 1
#define __INT_LEAST8_MAX__ 1
#define __LDBL_DIG__ 1
#define __LDBL_EPSILON__ 1
#define __LDBL_HAS_DENORM__ 1
#define __LDBL_HAS_INFINITY__ 1
#define __LDBL_HAS_QUIET_NAN__ 1
#define __LDBL_MAX_EXP__ 1
#define __LDBL_MAX__ 1
#define __LITTLE_ENDIAN__ 1
#define __LP64__ 1
#define __MMX__ 1
#define __OPTIMIZE__ 1
#define __ORDER_LITTLE_ENDIAN__ 1
#define __POPCNT__ 1
#define __SCHAR_MAX__ 1
#define __SHRT_WIDTH__ 1
#define __SIZEOF_FLOAT128__ 1
#define __SIZEOF_INT128__ 1
#define __SIZEOF_LONG_DOUBLE__ 1
#define __SIZE_MAX__ 1
#define __SSE2_MATH__ 1
#define __SSE2__ 1
#define __SSE3__ 1
#define __SSE4_1__ 1
#define __SSE4_2__ 1
#define __SSE_MATH__ 1
#define __SSE__ 1
#define __SSSE3__ 1
#define __STDC_HOSTED__ 1
#define __STDC_UTF_16__ 1
#define __STDC_UTF_32__ 1
#define __STDC__ 1
#define __UINT64_MAX__ 1
#define __UINTMAX_MAX__ 1
#define __UINTPTR_MAX__ 1
#define __UINT_FAST64_MAX__ 1
#define __UINT_LEAST64_MAX__ 1
#define __WINT_UNSIGNED__ 1
#define __XSAVE__ 1
#define __amd64__ 1
#define __clang__ 1
#define __clang_major__ 1
#define __clang_minor__ 1
#define __code_model_small__ 1
#define __gnu_linux__ 1
#define __k8__ 1
#define __linux__ 1
#define __llvm__ 1
#define __tune_k8__ 1
#define __unix__ 1
#define __x86_64__ 1
