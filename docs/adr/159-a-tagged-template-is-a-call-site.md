# ADR-159 — A TS/JS tagged template is a call site

**Date:** 2026-10-01 · **Status:** **built** (0.2.83-beta). This is the honesty audit's last fix (Max,
2026-10-01: "leave 176 177 for next session"; the handoff's next task, measured first; released on Max's
word, "proceed with the not done work and commit"). · **Owner:** Max · **Source:** C-177 (registered at
0.2.80-beta by the honesty audit). Pre-registered and measured: `~/.hobbes/bench/c177-tagged-template/`
(`PREREG.md`, `count.mjs`, `predict.py`, `run.sh`, `compare.py`, `RESULTS.md`).

Lifts C-177.

## The cause

`` tag`text` `` calls `tag` with the template's strings and values. `tsextract`'s `extractCalls` recorded a
`CallExpression` and a component JSX tag only, so a `TaggedTemplateExpression` made no site. The join pairs
an index occurrence with a lane A site by line and name (`evidence.join`); with no site, the occurrence at the
tag fell through to the unclaimed resolutions and became a `uses` edge. So `who_calls` listed the caller under
references, test reach (which closes over `calls`) did not pass through it, and `resolution_coverage` did not
count it. The tsc oracle keys a tagged template as a site (`isSite`), so every graded cell read it as recall.

## Decision

A `TaggedTemplateExpression` is a call site, recorded exactly as a call with its **tag** in callee position:

- An identifier tag, or a property access's name (`b` in `` a.b`x` ``), is the site through the same `push`
  as a call: its position, its name, lane A's fallback (`resolveExpressionTarget`), `calleeOrigin`, the union
  abstention (ADR-104) and `enclosingScope` (ADR-158).
- Any other tag (`` f()`x` ``, `` a[k]`x` ``) is an `<expr>` site, as C-63's callees are.

Nothing else changes. The join, the schema and the facts' fields are unchanged; the facts version is 8,
because what a `calls` record can be changed. Where the index resolves the tag, the join's existing claim
turns the `uses` row into `calls semantic`. Where it does not and lane A resolves the tag, the row is
`syntactic`, as for any call.

## Measured (pre-registered before the code)

Step 0 was a parse-only count of every tagged template in 15 TS/JS repos (`count.mjs`) and a join of each one
with its key and the HEAD graph (`join.py`, `predict.py`). Both arms were ingested with lane B in the image
and graded with `-poison`:

| Cell | Tagged | Confirmed | Recall |
|---|---|---|---|
| ajv | 510 | 1,499 → **1,902** | 67.5% → **86.3%** |
| zod | 14 | 9,872 → 9,885 | 45.8% → 45.8% |
| hono | 115 | 833 → 835 | 59.7% → 59.8% |
| Preact, cheerio, xmpp.js, npq | 13, 1, 73, 1 | unchanged | unchanged |
| 8 repos with none | 0 | unchanged, graph identical | |

- **Contradicted:** 0 on every keyed cell, before and after; poison PASS.
- **As predicted:** every new `semantic` row was a `uses` row at the same (path, line, target) before: ajv
  403, zod 13, hono 21. P1, P2, P6 and P7 were met exactly. Nothing was lost, and test reach only grew
  (hono 28 tests).
- **Missed (P5):** six `syntactic` rows on Preact's `demo/`, which lane B does not index. The tags there are
  a module-level `const html = htm.bind(h)`, a graph symbol, and step 0 had called them locals without
  reading the files. A written `html(…)` draws the same edge, so the rule is as worded; the prediction was
  wrong. P4 missed as worded: three tag-free repos differ only by an `npm ci` log timestamp in
  `extraction_errors`.

## What it does not do

- A tag the graph has no symbol for draws nothing, as the same call would. A package's tag (xmpp.js's 73,
  styled-components, `gql`) is a counted site in the external tail. A local, a parameter, a destructured const
  or an object literal's non-shorthand member is below the floor (C-9, C-58). A shorthand member (`ns = {
  html }`, `` ns.html`x` ``) is followed as ADR-144 follows `ns.html(…)`.
- **Position grain.** The tsc key sites a tagged template at the tag's start (`a` in `` a.b`x` ``); lane A
  sites it at the terminal identifier, where the index's occurrence is. The grade matches by line, so only a
  member tag split across lines would differ, and no keyed cell has an in-repo one. This is recorded as
  C-177's residual edge case.

## Consequences

- C-177 is lifted. The always-on "not detected at all" statement (`list_blind_spots`, the plan manifest) and
  `who_calls`' references heading no longer name it, and each test asserts its absence.
- The tagged-template rows ajv's key already held are now confirmed; the comparative tables re-render the
  Hobbes ajv, zod and hono figures from their cell records.
- Tests: a tsextract case (identifier tag, a member tag at its terminal across lines, an expression tag, the
  substitution's own call, the scope) and `test_tsjs_tagged_template.py` over the new `minitag` fixture (with
  lane B: `semantic`, no `uses` left, the shorthand member drawn; without: `syntactic`, and a test of `page`
  reaches `html`). Both fail on the old helper.
