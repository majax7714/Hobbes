"""The intrinsic inventory: the two function forms clang writes, the macro form, and what is dropped.

The header text here is written from the real headers' shapes (`avx2intrin.h`, `emmintrin.h`,
`avx512fintrin.h`, `f16cintrin.h`): the two-line declaration, the one-line declaration, the `#define`
form with its continuation, and the neighbours that must not be read as intrinsics.
"""

from pathlib import Path

from lattice import intrinsics

AVX2 = """/*===---- avx2intrin.h - AVX2 intrinsics -----------------------------------===*/

#ifndef __IMMINTRIN_H
#error "Never use <avx2intrin.h> directly; include <immintrin.h> instead."
#endif

#define __DEFAULT_FN_ATTRS256 __attribute__((__always_inline__, __nodebug__, __target__("avx2"), __min_vector_width__(256)))

static __inline__ __m256 __DEFAULT_FN_ATTRS256
_mm256_fmadd_ps(__m256 __A, __m256 __B, __m256 __C)
{
  return (__m256)__builtin_ia32_vfmaddps256((__v8sf)__A, (__v8sf)__B, (__v8sf)__C);
}

static __inline__ __m256i __DEFAULT_FN_ATTRS256 _mm256_abs_epi8(__m256i __a)
{
  return (__m256i)__builtin_elementwise_abs((__v32qs)__a);
}

#define _mm256_extractf128_pd(V, M) \\
  ((__m128d)__builtin_ia32_vextractf128_pd256((__v4df)(__m256d)(V), (int)(M)))

static __inline__ int __DEFAULT_FN_ATTRS
__lzcnt32(unsigned int __X)
{
  return __builtin_ia32_lzcnt_u32(__X);
}
"""

ODDITIES = """static __inline__ void __attribute__((__always_inline__, __nodebug__, __target__("sse")))
_mm_stream_ps(float *__p, __m128 __a)
{
  __builtin_nontemporal_store((__v4sf)__a, (__v4sf *)__p);
}

static __inline__ unsigned short __DEFAULT_FN_ATTRS128 _cvtss_sh(float __a, const int __imm)
{
  return 0;
}

static __inline__ void *__DEFAULT_FN_ATTRS _mm_malloc(size_t __size, size_t __align)
{
  return 0;
}

extern __inline __m128 _mm_declared_elsewhere(__m128 __a);
"""


def test_the_two_line_form_is_normalised_to_one_line():
    index = intrinsics.index({"avx2intrin.h": AVX2})
    entry = index["_mm256_fmadd_ps"]
    assert entry["signature"] == "__m256 _mm256_fmadd_ps(__m256 __A, __m256 __B, __m256 __C)"
    assert entry["header"] == "avx2intrin.h"
    assert entry["macro"] is False


def test_the_one_line_form_reads_the_same_way():
    index = intrinsics.index({"avx2intrin.h": AVX2})
    assert index["_mm256_abs_epi8"]["signature"] == "__m256i _mm256_abs_epi8(__m256i __a)"


def test_the_macro_form_is_its_define_line_without_the_continuation():
    entry = intrinsics.index({"avx2intrin.h": AVX2})["_mm256_extractf128_pd"]
    assert entry["signature"] == "#define _mm256_extractf128_pd(V, M)"
    assert entry["macro"] is True


def test_the_attribute_macros_and_the_written_out_attribute_are_dropped():
    index = intrinsics.index({"avx2intrin.h": AVX2, "xmmintrin.h": ODDITIES})
    assert "__DEFAULT_FN_ATTRS256" not in index["_mm256_fmadd_ps"]["signature"]
    assert index["_mm_stream_ps"]["signature"] == "void _mm_stream_ps(float *__p, __m128 __a)"
    assert "__attribute__" not in index["_mm_stream_ps"]["signature"]


def test_a_multi_word_return_type_and_a_pointer_return_survive():
    index = intrinsics.index({"xmmintrin.h": ODDITIES})
    assert index["_cvtss_sh"]["signature"] == "unsigned short _cvtss_sh(float __a, const int __imm)"
    assert index["_mm_malloc"]["signature"] == "void * _mm_malloc(size_t __size, size_t __align)"


def test_a_name_outside_the_two_namespaces_is_skipped():
    index = intrinsics.index({"avx2intrin.h": AVX2})
    assert "__lzcnt32" not in index
    assert "__DEFAULT_FN_ATTRS256" not in index  # the attribute's own `#define` is not an intrinsic
    assert sorted(index) == ["_mm256_abs_epi8", "_mm256_extractf128_pd", "_mm256_fmadd_ps"]


def test_a_declaration_that_is_not_clangs_definition_form_is_not_read():
    # the reader knows one form, `static … inline …`; an `extern __inline` prototype is not it
    assert "_mm_declared_elsewhere" not in intrinsics.index({"xmmintrin.h": ODDITIES})


def test_the_first_header_to_define_a_name_owns_it():
    index = intrinsics.index({
        "a.h": "static __inline__ __m128 __DEFAULT_FN_ATTRS _mm_dup_ps(__m128 __a)\n{\n}\n",
        "b.h": "static __inline__ __m256 __DEFAULT_FN_ATTRS _mm_dup_ps(__m256 __a)\n{\n}\n",
    })
    assert index["_mm_dup_ps"]["header"] == "a.h"
    assert index["_mm_dup_ps"]["signature"] == "__m128 _mm_dup_ps(__m128 __a)"


def test_load_reads_a_directory_and_names_headers_relative_to_it(tmp_path):
    (tmp_path / "avx2intrin.h").write_text(AVX2)
    nested = tmp_path / "sse"
    nested.mkdir()
    (nested / "xmmintrin.h").write_text(ODDITIES)
    index = intrinsics.load(tmp_path)
    assert index["_mm256_fmadd_ps"]["header"] == "avx2intrin.h"
    assert index["_mm_stream_ps"]["header"] == str(Path("sse") / "xmmintrin.h")
    assert str(tmp_path) not in "".join(entry["header"] for entry in index.values())
