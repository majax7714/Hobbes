# Oracle cell — sqliteai/sqlite-vector, build root `.`, 2026-09-12 (O9, the C random draw)

**Repo:** https://github.com/sqliteai/sqlite-vector, clone at `~/.hobbes/bench/oracle/repos/sqlite-vector`, commit `0c2223ada9dce1fa33248c8835a15f51d9a0f655` (shallow).
- **Drawn at random,** by the rule committed before the draw (`oracle-grading.md` §10.5, `b7d17b8`).
  - The pool: GitHub's `language:c stars:300..3000 pushed:>2026-03-01`, the 1,000 results the search API returns (of 2,858), sorted by full name and shuffled with `random.Random(20260912)`.
  - Draw 1, **jfernandez/bpftop** (`5a67ec0`), was passed over. Its root Makefile's one target is `cargo build`, and its one C file is a BPF program cargo's build script compiles. Offline, bear records no C compile, and the ingest's C root got no semantic edge. The record it drew is C-135's surfacing gap, amended the same day.
  - Draw 2, **sqliteai/sqlite-vector**, was taken: not a fork, not archived, a root Makefile, and both the ingest and the oracle derived a compile database offline.
- **The shape:** a SQLite extension, whose `src/` holds the extension and one SIMD distance kernel per architecture (AVX2, AVX-512, SSE2, NEON, RVV, generic), plus a 263k-line vendored SQLite amalgamation in `libs/`. The Makefile's default target builds `dist/vector.so` from `src/*.c` alone.
- **Ingest:** SHA `0c2223ad` (dirty: the `.gitignore` line, ADR-012). Hobbes 0.2.4-beta at `055d3fe`, lane B on, scip-clang over bear's record of `make -k`, contained.
- **Oracle:** `c-clang`, clang 18.1.3. Roots line: `compile database: make (7 units)`, 0 failed.

**Command:** `bench/oracle/run-cell.sh ~/.hobbes/bench/oracle/repos/sqlite-vector . ~/.hobbes/bench/oracle/sqlite-vector-c --lang c` (re-run with `--no-ingest` after `17def60`). Runtime 11 s.

## Numbers, Hobbes 0.2.4-beta (report.txt, verbatim)

```
cell   oracle Ubuntu clang version 18.1.3 (1ubuntu1) -ast-dump=json (resolution)  sha 0c2223ad
oracle ran contained (ADR-092)
hobbes edges 19748: confirmed 851  contradicted 3  abstract 0  silent 18894 map[not-loaded:18775 unreachable:119]
coverage: map[sites_dynamic:360 sites_external:1721 sites_link_ambiguous:0 sites_macro:0 sites_static:1091 sites_tu_split:0 sites_undefined:0 units:7 units_failed:0]
precision-against-oracle 99.6% (851/854)
recall 100.0% (1091/1091 in-repo oracle pairs) over every resolved site in the cell (resolution oracle: no roots); external oracle pairs 1721; misses map[]
recall-collapsed 100.0% (851/851 pairs at site-line × target-file × target-name grain: a symbol's overload signatures fold, and so do repeats of one callee on one line; the per-signature line above is the standing grade)
  recall[static→function   ] 100.0% (1091/1091)  misses 0 = 0.0% of all misses
  tier semantic   confirmed 851  contradicted 0  abstract 0  silent 0
  tier syntactic  confirmed 0  contradicted 3  abstract 0  silent 18894
  line-grain tolerance used on 343 edge(s) (several oracle sites on one line)
  contradicted src/sqlite-vector.c:380  hobbes src/sqlite-vector.c:31 (src/sqlite-vector.strcasestr)  oracle :0 (strcasestr)
  contradicted src/sqlite-vector.c:398  hobbes src/sqlite-vector.c:31 (src/sqlite-vector.strcasestr)  oracle :0 (strcasestr)
  contradicted src/sqlite-vector.c:420  hobbes src/sqlite-vector.c:31 (src/sqlite-vector.strcasestr)  oracle :0 (strcasestr), src/sqlite-vector.c:332 (sqlite_strdup)
poison check: PASS — 19748 seeded wrong edges: 854 refused, 18894 unjudged (oracle silent there), 0 falsely confirmed
```

| bucket | count |
|---|---|
| hobbes edges (graded) | 19,748 (851 semantic, 18,897 syntactic) |
| excluded before grading | 3,188 edges to `macro` symbols |
| confirmed | 851 (all semantic) |
| contradicted | **3 (all syntactic, all hobbes-wrong)** |
| silent | 18,894 (not-loaded 18,775, unreachable 119) |
| precision-against-oracle | **99.6%** (851/854); semantic tier 851/851 |
| in-repo oracle pairs | 1,091 |
| recall | 100.0% (1,091/1,091) |
| external oracle pairs | 1,721: SIMD intrinsics, which a system header's `static inline` defines (`_mm_setzero_si128`, `_mm256_loadu_si256`), `__builtin_inff`, libm and libc |
| lane agreement at the ingest | 1,084 sites, 0 disagreements |

**Triage ratio (A-8):** 3 contradicted, so `oracle-wrong 0 : hobbes-wrong 3 : untriaged 0`.

## Contradicted (3, syntactic tier, lane `tree-sitter`): hobbes-wrong

`src/sqlite-vector.c:31` defines its own `strcasestr`, guarded:

```c
#if defined(_WIN32) || ((defined(__linux__) && !defined(__GLIBC__) && !defined(__ANDROID__))) || defined(SQLITE_WASM_EXTRA_INIT)
// Provide strcasestr function implementation for environments that lack it:
char *strcasestr(const char *haystack, const char *needle) {
```

On a glibc Linux build that arm is dead, and the three calls (`:380`, `:398`, `:420`) are libc's `strcasestr`. The oracle says so: external, declared in `<string.h>`. Two things put Hobbes' edges there:
- **C-131:** lane A reads both arms of an `#if` as if both were live, so the file defines `strcasestr` and the fallback's rank 1 (a same-file function) names it.
- **C-138:** `evidence.join` takes lane A's guess wherever lane B produced no *in-repo* resolution. It never asks whether lane B resolved the site to a declaration outside the repo, which is what the build compiles here.

This is the first compiler-graded C edge Hobbes got wrong, and it sits at the syntactic tier, where contradictions were predicted to concentrate (§10.2's P2, and its C counterpart P19, undecidable on cJSON). Found in the cell, not fixed: the veto is a join rule every language shares (C-138).

## Misses

None. Every call `src/` spells directly to a definition the build compiles is drawn, semantic (1,091/1,091). No macro-expanded call reaches an in-repo function: the extension's calls into SQLite go through `sqlite3ext.h`'s object-like macros (`#define sqlite3_create_function sqlite3_api->create_function`). Those are dynamic sites (360), calls through the extension API's function-pointer table, with no targets. Hobbes draws them to the macro, and those edges are excluded.

## Silent (18,894, all syntactic, charged to nobody)

- **`not-loaded` 18,775:** `libs/sqlite3.c` 18,502, the vendored amalgamation, which the default target does not compile (the extension links against the host's SQLite); `test/` 273.
- **`unreachable` 119:**
  - `src/distance-rvv.c` 64 and `src/distance-neon.c` 48: compiled, but their bodies are `#if`-guarded to RISC-V and ARM, so on x86_64 clang sees no call there;
  - `src/distance-cpu.c` 3: the dispatch lines to those kernels, in the same arms;
  - `libs/sqlite3.h` 3: API declarations inside `#ifdef` options the build does not set;
  - `src/sqlite-vector.c` 1.

**Poison check:** PASS — 19,748 seeded wrong edges: 854 refused, 18,894 unjudged, 0 falsely confirmed.

**Direction of fix** (no proposals):
- The 3 contradicted: Hobbes. Either the join vetoes lane A's guess where lane B resolved the site to an out-of-repo declaration (C-138, every language), or lane A learns the configured arm (C-131, the compile database's `-D`s).
- Silent: neither side.

**Pre-registration (`oracle-grading.md` §10.5), P23:**
- The semantic tier is **met** (851/851).
- `static→*` recall ≥ 80% is **met** (100%).
- "0 hobbes-wrong after triage" is **met on the semantic tier and missed cell-wide**: 3 syntactic edges are hobbes-wrong. The clause was written beside the semantic number and is graded both ways here, the stricter reading first.

P24 is met here.
