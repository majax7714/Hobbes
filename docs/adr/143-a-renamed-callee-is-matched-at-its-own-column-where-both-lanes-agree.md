# ADR-143 — A call whose site name is not its definition's is matched at the site's own column, where both lanes name the same definition

**Date:** 2026-09-20 · **Status:** accepted (Max, 2026-09-20: route **(a)**),
to be built as one dispatched unit; see *Accepted*, at the end. Measured and
simulated before anything was drawn · **Owner:** Max ·
**Source:** ADR-141's last section ("measure it on the TS cells first"), which
Max cleared on 2026-09-20; his standing direction — honesty and accuracy before
a recall number, and a rule fails toward drawing less.

Registers nothing and lifts nothing: no edge is wrong or missing today. What
is wrong is a **tier**: the graph says `syntactic` about a call the index
proved.

## The shape

The join pairs a lane A call site with a lane B resolution by
`(file, line, name)`, the column breaking ties (`evidence.match_resolution`).
The site's name is what was written; the resolution's name is the
definition's. Where they differ the match misses, so the site falls to lane
A's fallback — a `syntactic` `calls` — and lane B's unclaimed resolution
becomes a `semantic` `uses` to the same definition at the same place. One
call, two edges, the weaker tier on the one `who_calls` prints.

Two shapes carry it: a binding renamed at the site (`import { id as xid }`,
`const updateDOM = update`, `var express = require(…)`, Python's `from m
import read_units as read_nll_units`) and a `#private` method call, which
lane A names `#newResponse` and the index `newResponse`.

## Measured (`~/.hobbes/bench/adr141-name-mismatch/`, pre-registered)

Counted by site and target on the graphs of the 0.2.57-beta regrade, graded
against the standing keys: Express 2, Preact 5, xmpp.js 41, ajv 5, cheerio 8,
zod 0, hono 75 — **136 sites, 98 confirmed, 38 outside the graded zone, 0
contradicted**. About half of hono's and four fifths of xmpp.js's lane-A-only
call sites; 0–6% of all call sites. kbet's clone is not on the box.

**Step 0, the join probed** (`probe_join.py`, xmpp.js and hono): where the
by-name match misses and lane A has a fallback, a resolution onto the
fallback's own definition sits at **exactly the site's column** 38 and 76
times; 5 columns off 4 times (xmpp.js's `time.date()` — that occurrence is the
namespace's, not the callee's); and **never** does a resolution at the site's
column name a definition other than lane A's.

## The rule

A call site the by-name match missed, that carries a column and is not
ambiguous (ADR-104), is matched to a resolution when **all** of these hold:

1. lane A's fallback resolves the site;
2. a resolution sits at the site's **own** column on its line;
3. every resolution at that column (`implements` facts aside) names the
   fallback's `(def_file, def_line)`.

Then it is the hit the by-name match would have been: `calls`, `semantic`,
both lanes, claimed by position (ADR-133), its qualifier and argument count
riding as they do on any semantic hit. Anything less — no fallback, no column,
a column that differs, a definition that differs — is what it is today. The
rule cannot draw an edge that is not already drawn; it can only say that two
lanes which independently named one definition at one token agree.

The functions that repeat the join's match so their counts agree with it
(`external_vetoes`, `withheld_fallbacks`, `agreement`, `disagreement_shapes`,
`_dispositions`, and the C++ comparison in `extract/__init__.py`) read the
same match, so a site the rule takes is counted matched everywhere and
`fallback-resolved` nowhere.

## Simulated (`ingest_rule.py`, `PREREG-sim.md`; every prediction held)

The rule in memory, each cell re-ingested contained, stored keys, `-poison`:

| cell | sites matched | rows before → after | tier syntactic → semantic | confirmed | contradicted |
|---|---|---|---|---|---|
| xmpp.js | 38 | 676 → 676 | 38 | 676 → 676 | 0 |
| hono | 76 | 5,420 → 5,420 | 76 | 833 → 833 | 0 |
| ajv | 5 | 1,664 → 1,664 | 5 | 1,499 → 1,499 | 0 |
| cheerio | 8 | 2,688 → 2,688 | 8 | 2,628 → 2,628 | 0 |
| zod | 0 | 9,921 → 9,921 | 0 | 9,872 → 9,872 | 0 |
| Express | 2 | 998 → 998 | 2 | 998 → 998 | 0 |
| Preact | 5 | 2,738 → 2,738 | 5 | 2,447 → 2,447 | 0 |

No row added, none lost, 134 tiers raised, poison PASS on every cell. The
counted shape falls to xmpp.js's 3 namespace-member sites, which the rule
leaves (the column differs) and should. On this repo it takes 2 sites: the
`minicjs` fixture's `test/direct.js` and one Python import alias — the rule is
the join's, so it is every language's, and it is regraded as such before the
merge.

## Routes

- **(a) the rule above** — recommended and taken.
- (b) register the understatement as a constraint and leave the join.
- (c) leave it counted in the handoff.

## Accepted (Max, 2026-09-20: route a)

Built as one dispatched unit. The code facts the brief rests on, read in the
tree before the dispatch:

- `evidence.join` has one product caller, `extract._build_symbol_layer`
  (`extract/__init__.py:495`); `match_resolution` is called at
  `evidence.py:388` (the join), `:646`, `:681`, `:736`, `:808`, `:867` and
  `extract/__init__.py:1141` — the mirrors named above. All but
  `_dispositions` are handed the fallback map beside the sites; how that
  one learns the rule's sites is the unit's to read and settle.
- `test_evidence.py::TestDisambiguation::test_a_resolution_with_a_different_name_does_not_match`
  pins the by-name miss with a columnless site and no fallback; it stays true
  under the rule and stays as written.
- `test_tsjs_reexport.py`'s `lane_b` case asserts that `minicjs`'s
  `test/direct.js` (`var app = require('../lib/app'); app()`) draws its
  call and says nothing of its tier; under the rule that edge is `semantic`
  where lane B ran, which is this ADR's end-to-end case. Its `through` and
  `twohop` callers stay `syntactic` (the index names nothing there).
- Before the merge, on the host: every `lane_b` test, and a regrade of one
  cell per language the rule can reach (the seven above, a Python cell, a Rust
  cell, fmt and args for C++, a Java and a Go cell) — no confirmed row lost, 0
  new contradicted, or the rule does not merge.
- The version, the CHANGELOG, the architecture and the handoff are the
  developer's, after the merge.
