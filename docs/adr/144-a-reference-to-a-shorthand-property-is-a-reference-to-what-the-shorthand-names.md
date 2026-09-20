# ADR-144 — A reference to a shorthand property is a reference to what the shorthand names

**Date:** 2026-09-20 · **Status:** accepted and **built** (0.2.62-beta, unit `12ad`; Max, 2026-09-20: the tier is
**`semantic`**, route (a) of *The open line*), to be built as one dispatched
unit; measured, probed in the image and simulated on nine cells before anything
was drawn · **Owner:** Max ·
**Source:** the cell of `oracle-grading.md` §10.27 (Blueturboguy07/cue), where
176 misses were one untraced shape; his standing direction — honesty and
accuracy before a recall number, and a rule fails toward drawing less.

Registers nothing: the shape was never an entry. It was a silence nobody had
read.

## The shape

`const { f } = require('./m'); f()` is drawn. `const m = require('./m');
m.f()` is not — nor is `import server from './server.js'; server.restart()`
over `export default { start, restart }`. What separates them is the binding,
not the export.

At the member token scip-typescript does not name the function. It names the
**property of the exported object literal** — `` src/`publik.js`/loadBuildConfig0: ``.
A property is a `meta` descriptor, which the helper keeps no definition for, so
the occurrence is filed under `external_refs` (marked `in_repo`, ADR-111) and
the join never sees it. The function gets no reference; lane A draws nothing.

## What the index says (`~/.hobbes/bench/cjs-namespace/mini/`, raw SCIP in the image)

- The index tells the literals apart itself: `module.exports = { alpha }` is
  `alpha1:`, another literal's `alpha` in the same file is `alpha0:`.
- The property's **one definition occurrence** is at the shorthand's token, and
  **the same range** carries a reference to the function, `alpha().`. That
  coincidence of ranges is what a shorthand *is*.
- `delta: alpha` has its value reference at a different range. A method written
  in the literal (`gamma() {…}`) is a `local`. Neither is this rule's.

## The rule

In the helper's decode, for scip-typescript only: a property symbol (descriptor
ending `:`) with **exactly one** definition occurrence, whose **exact range**
also carries references to **exactly one** graph-kind symbol F that has a
definition, is an alias of F. A reference to the property is emitted as a
reference to F — F's name, F's `def_file` and `def_line`. Anything less stays
what it is today: an in-repo external reference, vetoing nothing.

Both hops are the index's, by position. Lane A reads nothing new; the join,
its mirrors, `who_calls` and the tail meet an ordinary reference.

## Measured and simulated (`~/.hobbes/bench/cjs-namespace/`; `PREREG-sim.md` written first; every prediction held)

The prototype was a scratch worktree's `scip/index.mjs`, never merged; the
cells were ingested through it and graded against the standing keys, `-poison`.

| cell | rows before → after | added | contradicted | lost / re-tiered | recall |
|---|---|---|---|---|---|
| cue | 881 → 1,005 | 124 confirmed | 0 | 0 / 0 | 54.3% → **61.8%** |
| xmpp.js | 676 → 705 | 29 confirmed | 0 | 0 / 0 | 81.2% → **84.6%** |
| Express, github-action, Preact, ajv, cheerio, hono, zod | unchanged | 0 | 0 | 0 / 0 | unchanged |

Poison PASS on all nine. Step 0 had predicted the 124 and the 29 from the facts
alone, with the rule modelled as it fires and not filtered by the key; the six
sites it refused on cue are five with no exported literal and one value
property (`newInstallId: randomUUID`).

**`uses` edges, not graded, counted:** cue gains 114 (+2 on github-action). They
sit at the *destructuring* line — `const { startAppLink, … } = require('./src/applink')`
names the same properties — and are what an ESM `import { … }` line already
draws. 53 sit beside a `calls` edge of the same pair, as an import line's does.

## The open line — the tier

Max's word on the routes was "keep syntactic". That was given on my first
framing, where lane A read the exporting file's literal and carried the last
hop (ADR-141's precedent). The fixture changed the premise: **both hops are
the index's**, at exact ranges, and the simulated rows came out `semantic`
because the join meets an ordinary lane B reference.

- **(a) `semantic`, as simulated (recommended).** It is what happened: the
  index proved the property at the site and the function at the property.
  Calling it `syntactic` would understate a proof — the fault ADR-143 fixed.
- **(b) `syntactic`, by marking the aliased reference and downgrading it in
  the join.** More code in the join and every mirror, to say less than is
  known.

## What this leaves

The 49 cue misses whose target is a member *written in* a literal
(`getSettings() {…}`, `MODES.say.buildSystem`) — no symbol, C-9/C-58's floor.
A value property (`delta: alpha`) — refused; unmeasured.

## Accepted (Max, 2026-09-20: `semantic`)

"Yes go with semantic." The rule is the helper's and the rows are what the join
makes of an ordinary reference. **The code facts the unit's brief rests on, read
in the tree:** `decode` (`scip/index.mjs`) collects definitions in a first pass
that skips every non-`GRAPH_KINDS` kind after adding it to `inRepoMonikers`, and
files a reference with no `definitions` entry under `external`; `classify` reads
a descriptor ending `:` as `meta`; the index cache keys on `index.mjs`'s content
(`indexcache.py`), so a changed helper misses it and the facts schema — hence
`HELPER_VERSION` — does not move; `minicjs` is read by
`test_tsjs_reexport.py` alone.

## Built (2026-09-20, 0.2.62-beta)

Unit `S-20260920T180832Z-12ad`: 53 turns of 140, $3.53, five files, all the
partition's; gate clear, verify pass. The rule is in `decode` alone, with a
`rangeKey` that spells SCIP's three-element range out so two occurrences at one
token key the same. `decode` returns `shorthand_refs`; it does not reach the
facts header, which forwards an enumerated list — left so, the doer's call and
the right one for a unit scoped to `decode`. On the host: node 94, pytest 2,146,
thirteen `lane_b` (the new `minicjs` case against a real index). **Nine TS/JS
cells regraded, each row-identical to its simulation, tiers included; seven
other-language cells row-identical pre/post** (`oracle-grading.md` §10.28).

