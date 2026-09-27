# Preprocessed excerpts — D-12's availability fixture

Cut on 2026-09-27 from sqlite-vector @ `0c2223a`. Each file was preprocessed in the `hobbes-session:local`
image (Ubuntu clang 18.1.3) as `clang -O2 -Isrc -Ilibs <build.ISA_FLAGS[isa]> -E -dD src/distance-<isa>.c`.
The enabled-feature macros come from `clang -O2 <flags> -dM -E -x c /dev/null`, written after the
`@@MACROS@@` line.

Each excerpt keeps, for nine intrinsics, the line marker in force and the definition's lines. For a macro,
it also keeps the first three function heads of its header, which give the macro its features. Parsed as the
whole output is, the excerpt gives each name the same status as the whole file: 27 of 27 (name, file) pairs.

Status by file:
- **sse2:** `_mm_add_epi32` and `_mm_castsi128_ps` are available; everything else is undeclared.
- **avx2:** every `_mm_`/`_mm256_` name is available; the three `_mm512_` names are not.
- **avx512:** all are available but `_mm512_popcnt_epi64`, which needs `avx512vpopcntdq`.
