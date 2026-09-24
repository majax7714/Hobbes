"""Rebuild `tests/fixtures/sqlite-vector-kernels/` from a sqlite-vector checkout at 0c2223a.

Usage: python scripts/make_fixture.py <sqlite-vector>/src tests/fixtures/sqlite-vector-kernels/src

Each kernel file keeps its float32, int8 and bit1 functions verbatim and loses its float16, bfloat16 and uint8
functions and their dispatch-table lines. The headers, `libs/fp16/` and the licence are copied unchanged by hand
(PROVENANCE.md). The brace count is line-based and good for these files, whose dropped functions hold no brace in
a comment or string; a rebuilt fixture is checked by compiling it (the lattice tests do)."""
import re, sys, pathlib
DROP = re.compile(r'^(static inline )?float (float16|bfloat16|uint8)_distance_[a-z0-9_]+ ?\(')
def spans(lines):
    i = 0
    while i < len(lines):
        if DROP.match(lines[i]):
            depth, j, seen = 0, i, False
            while True:
                depth += lines[j].count('{') - lines[j].count('}')
                seen = seen or '{' in lines[j]
                if seen and depth == 0:
                    break
                j += 1
            # drop blank lines after
            k = j + 1
            while k < len(lines) and lines[k].strip() == '':
                k += 1
            yield i, k
            i = k
        else:
            i += 1
def trim(text):
    lines = text.split('\n')
    drop = set()
    for a, b in spans(lines):
        drop.update(range(a, b))
    out = [l for n, l in enumerate(lines) if n not in drop
           and not re.search(r'= *(float16|bfloat16|uint8)_distance_', l)]
    return '\n'.join(out)
src, dst = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
for name in ['distance-cpu.c', 'distance-sse2.c', 'distance-avx2.c', 'distance-avx512.c', 'distance-neon.c',
             'distance-rvv.c']:
    (dst / name).write_text(trim((src / name).read_text()))
