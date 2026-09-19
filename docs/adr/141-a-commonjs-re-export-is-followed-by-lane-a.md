# ADR-141 — A CommonJS re-export is followed by lane A: `module.exports = require("…")` to the required module's own export

**Date:** 2026-09-19 · **Status:** accepted (Max, 2026-09-19: "good with
recommended" — route (a)). C-167 traced and the rule probed; see
*Accepted*, at the end.

Asked in the 2026-09-19 close-out (Max: "we will tackle constraints from
js next session"; the sixth session, "proceed with c-167"). C-167: a
function reached through a CommonJS re-export of `module.exports` draws
no edge — Express's `express()`, 652 of its 1,180 missed pairs.

## The trace (done)

Express's tests `require('..')` the root `index.js`, which is one line —
`module.exports = require('./lib/express')` — and `lib/express.js` ends
the chain with `exports = module.exports = createApplication`. A
reproduction of that shape (`~/.hobbes/bench/c167-reexport/trace/mini/`)
and scip-typescript re-run on a copy of Express, both in the image, give
the same answer in both lanes:

- **Lane B.** scip-typescript names the callee at `test/app.js:9`
  (`var app = express()`) `local 8`: a document-local symbol with no
  definition in that document. It is the re-exporting file's own local —
  `index.js`'s `module.exports` is `local 1` there, and the reproduction's
  `test/app.js` carries exactly `local 1` — written into another
  document. A local is document-scoped in SCIP, so the occurrence names
  nothing; the helper drops every `local` occurrence, so the join sees
  nothing at the site and nothing vetoes lane A. On Express **652 `express(`
  call occurrences carry such a local — exactly the 652 misses** — every one
  through `require('..')`, `'../'`, `'../..'`, `'../../'` or
  `'../../..'`. A direct `require('../lib/express')` is named
  `createApplication().` at the call.
- **Lane A.** ts-morph's `getAliasedSymbol()` stops at `index.js`'s
  `export=` symbol, whose one declaration is the binary expression
  `module.exports = require('./lib/express')`: TypeScript does not treat
  a `require` call on that right side as an alias. The callee's
  declarations are in another repo file and not modelled, so the site
  records `origin: nested` and no callee — the tail's `nested-decl`
  (C-167's entry had said `unclassified`; corrected with this ADR).
- **What does resolve:** `module.exports = lib` after `var lib =
  require(…)` (both lanes; TypeScript aliases an identifier on that right
  side), and a direct require of the defining file. What stays
  unresolved for another reason: `express.Router()` and the like, whose
  targets are functions assigned to a property (`exports.Router = …`),
  below lane A's symbol floor (C-9, C-58) — not this constraint.

## The probe (done)

Pre-registered (`~/.hobbes/bench/c167-reexport/PREREG.md`) before any
re-ingest. The rule, patched into a scratch copy of `tsextract`
(`probe-lanea.patch`): after `getAliasedSymbol()`, where the symbol is
`export=` and its one declaration is `module.exports = require("<spec>")`
(also `exports = module.exports = require(…)`), take the string
literal's **module symbol** — the compiler's own module resolution, not a
type — and continue from that module's `export=`, alias-resolved; at
most eight hops. It changes lane A's callee (and its `origin`), nothing
else. Each cell was copied, ingested with `main` and with the probe, and
graded against its stored key (`js-cells/regrade/h34/<cell>/oracle.json`):

| cell | before | after | graph |
|---|---|---|---|
| Express | 340/340, recall 22.4% | **992/992, recall 65.3%**, 0 contradicted, poison PASS | +100 `calls` edges (652 evidence rows), all into `createApplication`, all `syntactic`; +92 module edges (test → `lib/express`); 0 removed; symbols and nodes unchanged; tail `nested-decl` 706 → 54, `fallback-resolved` 51 → 703 |
| Preact | 2,446/2,446 | identical | row-identical |
| xmpp.js | 552/552 | identical | row-identical |
| `minijs` | 7/7 | identical | row-identical |

P1 (992 ± 5, recall 65.3%) and P2–P4 met. The five TS cells' clones
(kbet, ajv, cheerio, zod, hono) and this repo hold no
`module.exports = require(…)` in any tracked JS file, so they cannot move;
in a `.ts` file `export =` is an `ExportAssignment`, not a binary
expression, and the rule does not fire. There is no TS lane A cache, so
the identical cells were re-extracted, not reused.

## Decision — routes

**(a) Recommended: lane A follows the re-export (the probe's rule).**
The site gets lane A's callee, and the join draws it as lane A's
fallback — `syntactic` tier, because lane B names nothing there. That
is the honest tier: the index did not resolve the call, the compiler's
module resolution and the source's own statement did. The edge is what
the key reads (652 of 652 right on Express). C-167 narrows to what is
left: the index's leaked local (a `Provider` line, P9) keeps these
edges syntactic, and the chain stops at anything but a literal
`require` on the right side (a computed specifier, a conditional). A
patch (0.2.56-beta: what the layer draws). Built as one dispatched unit:
the rule in `tsextract/extract.mjs` beside `resolveExpressionTarget` and
`calleeOrigin`, a tsextract test on a fixture of the shape (`index.js`
re-exporting `lib/`, a caller through `require('..')`, a direct caller,
an identifier re-export, a cycle), and a `lane_b` case that the join
draws it syntactic with nothing vetoed. `minijs` is hand-keyed by
`bench/oracle/internal/grade/minijs_test.go`; the fixture goes beside
it, not into it.

**(b) Read the leaked local in lane B.** Map `local N` back to the
re-exporting document's local of the same number. Rejected: it builds
on scip-typescript's defect, local numbers are per document and collide,
and the index's answer would be believed as `semantic` where the index
answered nothing.

**(c) Draw nothing; name the shape.** A tail class (`reexport`) in place
of `nested-decl` at those sites, C-167 surfaced. Honest, and the recall
stays 22.4% where the answer is one statement away.

## Also measured, not part of this decision

A callee whose site name differs from its definition's name — `var
express = require('../../lib/express'); express()`, a JS private
`#method` — is matched by name in the join, so lane B's resolution there
becomes a `semantic` `uses` and lane A's a `syntactic` `calls`, for one
site. Nothing is wrong and nothing is missed; the tier understates what
the index proved. Counted on the three JS cells: Express 2, Preact 5,
xmpp.js 41 (its `#` methods). Not a constraint yet; a next step would
measure it on the TS cells first.

## Accepted (Max, 2026-09-19: route a)

Built as one dispatched unit. The code facts the brief rests on, read in
the tree and run before the dispatch:

- `getAliasedSymbol()` is called in exactly two places in
  `tsextract/extract.mjs` — `resolveExpressionTarget` (lane A's callee)
  and `calleeOrigin` (the tail's origin when that returned null) — and
  the rule goes after it in both, so a site that now resolves stops
  being counted `nested-decl`.
- The facts schema does not change (same fields, a callee where there
  was null), so `HELPER_VERSION` stays 5, and `tssource.py`, which
  refuses any other version, is untouched. There is no TS lane A cache.
- The fixture `pipeline/tests/fixtures/minicjs/` (a root `index.js`
  re-exporting `lib/app.js`, a second hop `index2.js`, callers through
  `require('..')`, through `index2`, and direct), run through
  `extract_repo` with lane B on `main` and with the probe: on `main`,
  `test/through.js` and `test/twohop.js` draw nothing (`nested-decl`);
  with the probe each draws `test/<file> → lib/app.createApplication`,
  `calls`, `syntactic`, lane `tree-sitter`, tail `fallback-resolved`;
  `test/direct.js` is the same before and after (its `syntactic` `calls`
  beside the `semantic` `uses` — this ADR's last section). Lane B's one
  degradation there is the missing lockfile (C-23), as on any zone
  without one.
- The version, the CHANGELOG, §10.22's Express number, C-167's
  narrowing and the architecture are the developer's, after the merge.
