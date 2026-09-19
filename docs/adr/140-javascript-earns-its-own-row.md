# ADR-140 — JavaScript earns its own row: the claim corrected first, then graded cells

**Date:** 2026-09-19 · **Status:** accepted (Max, 2026-09-19: "route a is good", and the §3.8 row split within the architecture: "if you mean split within architecture then yes"). Step 1 built (0.2.53-beta); steps 2 done (the measurement below); steps 3–5 open.

Asked in the 2026-09-19 top-level review: *could we add JavaScript as a
usable language?* A step-1 build is a patch: a change to what the layer
says, registering its concession (C-165). The later steps add a
language's evidence, which is a patch too (ADR-103's fourth amendment).

## Context

JavaScript is not a missing language; it is an ungraded one. Both lanes
already take `.js .jsx .mjs .cjs`: lane A is a ts-morph project with
`allowJs` (`checkJs` off), and lane B is scip-typescript over the same
zones, with `scipsource._generated_tsconfig` mirroring lane A's default
project where the repo gives no config. A JavaScript repo ingests and
draws edges.

What it lacks is evidence (P11). §3.8's row was **TypeScript /
JavaScript**, and `verification.py` pinned `javascript` as a verbatim
copy of TypeScript's row — 4 repos, multi-repo. Every JavaScript ingest
therefore vouched for itself, in the ingest summary, the surface's badge
and `list_blind_spots`, on cells nobody had checked contained any.

## The measurement (step 2, done)

The five graded TS/JS cells' reports (`~/.hobbes/bench/v018/{kbet-ts,
ajv-ts,cheerio-ts,zod,hono-build}/report.json`, the 2026-09-09/10
regrades), each row's site and target path read by extension:

| cell | confirmed | confirmed touching a JS file | JS rows, any bucket |
|---|---|---|---|
| kbet | 630 | 0 | 0 |
| ajv | 1,410 | 0 | 9 silent |
| cheerio | 2,628 | 0 | 5 silent |
| zod | 9,731 | 0 | 11 silent |
| hono (`tsconfig.build.json`) | 768 | 0 | 2 silent |
| **total** | **15,167** | **0** | 27 silent |

Every one of those 27 rows is `silent`, meaning outside the program the
zone's `tsc` loaded. JavaScript's graded evidence is zero. The oracle
could not have produced any: `bench/oracle/ts/tsc-oracle.mjs` refuses a
zone with no `tsconfig.json`.

## Decision — route (a)

1. **Correct the claim now (built, 0.2.53-beta).** `verification.py`'s
   `javascript` row is 0 repos, depth `unverified`, and a zero row that
   names its reason prints it: `not verified on any repo — the
   TypeScript row's five graded cells are TypeScript programs, …
   (C-165)`. §3.8 splits into a **TypeScript** row (unchanged) and a
   **JavaScript** row stating the above; the test that pins the two
   tables together maps each label to one language. None of the
   consumers changes: the ingest summary spells out any row at one repo
   or fewer, the surface badges `unverified` apart, and `list_blind_spots`
   prints the note. C-165 is registered, surfaced.
2. **Measure first (done, above).**
3. **Let the oracle grade a zone with no tsconfig.** A `tsc-oracle.mjs`
   option that builds its program from the same generated config lane B
   uses (`allowJs`, ESNext, Bundler resolution, JSX preserved, an explicit
   file list), so the key and the ingest see one program. The key must
   not borrow Hobbes' own reading of which files belong to the zone:
   the file list is the discovered source set, stated in the cell
   record. Under `bench/`, so no version moves; it gets its own fixture
   test (a small CommonJS and ESM tree, `minijs`).
4. **Pre-register, then grade two or three shapes, contained.** At least
   a CommonJS Node library (`require`, `module.exports`,
   `exports.x = …`, prototype methods) and an ESM package with JSDoc
   types; the third drawn at random from JavaScript repos with no
   `tsconfig.json`. The pre-registration (`oracle-grading.md` §10) states
   the predictions: which shapes land below the symbol floor (C-9,
   C-58), what the tail classes, and precision. Misses are read by class
   before any rule is written, and any rule is its own ADR.
5. **Name the repos in the row.** `verification.py` and §3.8 extended in
   the same commit as the evidence (§3.7 step 4), C-165 narrowed or
   lifted by what the cells show.

## Rejected

- **(b) Step 1 only.** Honest, but it leaves JavaScript unclaimable, and
  the machinery for it is already built.
- **Keep the row joint and add JS cells to it.** The joint row is what
  hid the gap: a reader cannot tell which language a joint count
  vouches for.

## Consequences

- A JavaScript repo now says it rests on no graded evidence; nothing it
  draws changes.
- This repo's own ingest shows the row: its languages include
  `javascript` (`scip/index.mjs`, `tsextract/`, the oracle's
  `tsc-oracle.mjs`), which read "4 repos" until 0.2.53-beta.
- Steps 3–5 spend no API or Modal money; a dispatched unit spends the
  subscription.
