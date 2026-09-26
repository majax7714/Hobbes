# E3's pool — the C lattice draw, stated before it is made (2026-09-26, D-5 route a)

Max, 2026-09-26: "good to proceed with recommended" (D-5 a: a no-spend draw of permissively licensed C
repos with kernel lattices, by a written rule, the body-shape rule tested on it). No API, Modal or
dispatch spend. Nothing a repo contains trains anything in this step; it is counted.

## The pool

- GitHub repository search, one query per (keyword, licence):
  `<kw> in:name,description,topics,readme language:C license:<spdx> stars:>=20`,
  keywords `simd avx2 avx512 neon sse intrinsics vectorized`, licences
  `mit apache-2.0 bsd-2-clause bsd-3-clause isc zlib unlicense cc0-1.0 bsl-1.0 0bsd`.
  Every result the API returns (≤ 1,000 a query), at most 30 queries a minute.
- The union, de-duplicated by `full_name`, sorted by it, shuffled with `random.Random(20260926)`:
  `pool.json`. The API's `license.spdx_id` is kept per repo.

## The gate, per repo, in pool order (every repo passed over is logged in `draw-log.md` with its reason)

1. Not a fork, not archived.
2. Not sqlite-vector, not owned by `sqliteai`, and no file whose text contains `sqlite-vector` or
   `distance_function_t` beside `dispatch_distance_table` (E3's target is never in its pool).
3. A shallow clone of the default branch carries a licence file whose text agrees with the API's
   SPDX id (`LICENSE*`, `COPYING*`, or the SPDX header of most sources). Disagreement: passed over.
4. **An ISA lattice** (the rule, fixed here):
   - Definitions come from `lattice.scan` (bench/calvin/lattice) over every `.c` and `.h` file,
     outside `test`/`tests`/`bench`/`benchmark(s)`/`example(s)` and outside vendored directories
     (`third_party thirdparty 3rdparty vendor deps external extern contrib`) at any depth.
   - A name is tokenised on `_` and camelCase and lowercased, after joining the ISA spellings that
     split: `sse4_1`→`sse41`, `sse4_2`→`sse42`, `avx512_<x>`→`avx512<x>`.
   - The ISA tokens: `sse sse2 sse3 ssse3 sse41 sse42 avx avx2 avx512 avx512f avx512bw avx512vl
     avx512dq avx512vnni avx512fp16 avx512bf16 avxvnni neon asimd sve sve2 rvv altivec vsx vmx
     power8 power9 wasm simd128 lsx lasx msa`.
   - **An ISA family** is the set of definitions whose names are equal after masking one token that
     is an ISA token, with at least two distinct ISA tokens in it.
   - **The gate:** at least 3 ISA families and at least 8 members in them.
5. **Ingestible:** `uv run hobbes ingest` on the clone, contained (the image, ADR-092), produces a
   `graph.json` whose C symbols include at least 90% of the gate's ISA members by name. An ingest that
   fails, or a compile database that cannot be derived, is logged with its error and the repo is
   passed over.
6. Not taken if it is C++ by majority of source files (`.cc .cpp .cxx .hpp`, against `.c .h`).

**Census, not sample:** every repo that passes is taken, in pool order, up to **40**. Order matters
only for the cap and for reading the log.

## What is measured (stated first)

Per taken repo, and in total:

- **Tasks.** One held-out task per member, non-thin (body > 2 lines, not a single call — a wrapper, as
  E1 sections them). Counted three ways: ISA families (the gate's rule); the **body-shape rule**
  (name-loose families, one token differing, whose members' bodies, tokenised with the varying token
  masked, have `difflib` ratio ≥ 0.6 — fixed as `family-count/count.py` states it, not re-tuned); and
  their union.
- **Validation reach**, per member: (a) a **scalar reference** — a sibling whose ISA token is replaced
  by `c scalar generic ref reference serial portable plain fallback cpu naive`, or removed, with the
  same other tokens; (b) **reached by the repo's tests** (Hobbes' `tests.json`). A member with neither
  is counted and marked `unvalidated`: the card's "only validated examples train" cannot hold it yet.
- **Target likeness:** members whose family has two or more axes (ISA × something the names vary on:
  a type or a metric token) — sqlite-vector's shape — against ISA-only families.

## The body-shape rule's test (pre-registered)

- **Recall:** of the non-thin members of ISA families (the names' ground truth, independent of body
  shape), the share the body-shape rule groups. **Bar: ≥ 0.90.**
- **Precision, by reading:** 20 body-shape families per repo that are not ISA families (all of them if
  fewer), drawn with `random.Random(20260926)`, each read and classed `lattice` (a real pattern on some
  axis — type, width, metric, endianness), `near-copy` (ratio ≥ 0.9 with no axis a name states), or
  `coincidence`. **Bar: coincidence ≤ 20%.**
- If a bar fails, the rule is revised on the **first half** of the taken repos (pool order) and
  re-measured on the **second half** only; both figures are reported.

## The reading, written now

- The pool is compared with ADR-099's 13,688 training records. Three outcomes:
  - **validated tasks ≥ ~5,000:** E3 is priced on this pool (the steps ablation sized by it);
  - **~1,000–5,000:** E3 is priced at 300 steps only, with the pool's size stated as the limit, or a
    widening rule is proposed to Max first;
  - **< ~1,000:** E3 as carded is not fundable from real C; the route back to Max is generated
    siblings (the card's "widened with generated siblings, validated") or E4 first.
- Nothing is concluded from a repo whose licence or ingest could not be verified.
