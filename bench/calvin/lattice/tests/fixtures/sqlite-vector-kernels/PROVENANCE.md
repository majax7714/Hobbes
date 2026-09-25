# sqlite-vector's kernel files, trimmed — a real-source fixture

- **From:** https://github.com/sqliteai/sqlite-vector at `0c2223ada9dce1fa33248c8835a15f51d9a0f655` (the oracle
  cell's clone, `docs/oracle/cells/sqlite-vector-c-2026-09-12.md`). Apache-2.0, `LICENSE.md` beside this file.
- **What changed:** each `src/distance-*.c` lost its float16, bfloat16 and uint8 functions and their
  `dispatch_distance_table` lines (`scripts/make_fixture.py`). Everything else, and every header and
  `libs/fp16/`, is byte-for-byte the target's.
- **What is left per ISA file:** 13 names: float32 and int8 × {`_impl`, `l2`, `l2_squared`, `l1`, `dot`,
  `cosine`}, and `bit1_distance_hamming_<isa>`; 11 table slots.
- **Checked** (2026-09-24, in `hobbes-session:local`, clang 18): every file compiles with the Makefile's
  flags plus `-Wno-unused-function` (trimmed helpers go unused), and after `init_distance_functions(true)`
  then each of `init_distance_functions_{sse2,avx2,avx512}`, all 11 slots each installs agree with the
  scalar table on 37-element inputs.
- **Real-source quirks it keeps:** AVX-512's `bit1_distance_hamming_avx512` is `static`, every `_impl`
  is `static inline`, NEON's int8 helper is spelled `int8_distance_l2_neon_imp`, and signatures are
  written both `name (` and `name(`.
- **`Makefile` is this repo's, not the target's.** It builds the six objects so that `bear`
  can record a compile database. Nothing links.
- **`derived/`** holds the fixture's own Hobbes ingest and clang oracle key, built 2026-09-24 by
  `bench/oracle/run-cell.sh <a git copy of this dir> . <out> --lang c` in the image (Hobbes
  0.2.70-beta, clang 18.1.3). The copy's checkout path was removed from `graph.json`'s
  `built_by`. `report.txt` is the grade: 126/126 confirmed, recall 136/136 in-repo pairs,
  788 external pairs (the intrinsics), poison PASS. It is real derived data for the facts
  tests, and its line numbers are this fixture's, not the full target's.
