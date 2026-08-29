# Oracle lane — review of the defect record (2026-08-27)

**What this is.** Outcomes of a full review of the defect record
(`oracle-defects.md`, H-1..H-17): whether each claim correctly
attributes its defect and whether each fix was well chosen; the action
items that fell out; the defect-handling method the review surfaced;
and one new instrument (the seen tally, §4). This doc does not
supersede the log — the log stays the record. This is the review, the
method, and the tally's initial state. External review, adopted by
Max; the tally is maintained in the same commit as the log entry that
changes it.

## 1. Review verdict

All seventeen entries attribute their defect to the correct side. None
is a Hobbes error misfiled as an oracle error, and the two large
recall/precision corrections (H-5's 119 false contradictions, H-16's
649 false misses) are real: `tsc` genuinely resolves a call through a
const of callable type to the anonymous call signature, and `.await`
genuinely lowers to a poll of the coroutine compiled from the async
fn's body, carried in MIR as a second call at the authored site. The
grain convention (D-O4: callee identity is the binding) is the
defensible one for a source-level knowledge layer, and the provenance
convention (sites in code the author didn't write are dropped and
counted) is the single rule underneath H-13/H-15/H-16.

H-9 is physics, not a bug: RTA requires `InstantiateGenerics`,
whole-program SSA of dagger's root closure exceeds the box, and
`GOMEMLIMIT` is a soft limit — when live heap exceeds it, Go thrashes
GC and allocates anyway. Subtree grading with the kernel's verdict
printed is the honest fallback; the parked state stands.

Two dispositions were pushed back on: H-11's null-tolerance (A-3) and
H-17's proposed blanket silence for element-access callees (A-4).
Everything else stands as logged.

## 2. Action register

| ID | From | Action | State |
|---|---|---|---|
| A-1 | H-1 | A library module with no tests has no RTA root even after the init fix. The cell record must print "no roots exist" as its own state, distinguishable from "graded empty". | **Done 2026-08-27** — `state: no-roots` on the export and `recall: NOT GRADED — no roots exist` on the report; `testdata/noroots` |
| A-2 | H-2, H-10 | Verify both sides of a cell import one membership function. H-10's fix shares the exclude list; if the prefix-plus-exclude logic is still written twice (export and oracle), RC-1 remains open and a third instance is available the next time either side's scoping evolves. Five-minute check. | **Verified — it was written twice** (`gorta.underModule/excludedBy`, `export.under/excluded`); **done 2026-08-27** — both call `edges.Under`/`edges.Excluded`. The TS/Python/Rust extractors keep their own predicate in their own language; noted, not deduplicable across runtimes |
| A-3 | H-11 | Emit `[]` at the serializer (initialize the slice; Go's `encoding/json` marshals nil as `null`) rather than requiring null-tolerance in every future consumer. One line; the cheap side of the trade. | **Done 2026-08-27** — `rows`, `misses`, `tags`, `root_names` initialised |
| A-4 | H-17 | Site rule for element-access callees: fixture first, rule second. Add the three shapes (`a["lit"]()`, `a[Symbol.x]()`, computed `a[k]()`) to `minits`, observe what Hobbes' scip lane actually emits for each, then set the rule per argument kind — grade where a source binding exists on both sides (literal string/number, well-known Symbol member, if the checker returns a non-anonymous declaration), silence only the genuinely dynamic computed case. Blanket silence forfeits a class Hobbes plausibly covers (`process.env["X"]`, index signatures, generated clients). Then fix the loop. | **Done 2026-08-27, in that order** — fixture (three shapes, `minits/src/lookup.ts`), observation (Hobbes draws no edge for any: C-63), rule (D-O4 bullet), loop. ajv regraded in 2 s |
| A-5 | H-17 | `descend(node)` helper that throws when the returned node is identical to its input; retrofit all walk-down loops in the oracle extractors. Turns the next non-terminating walk into a stack trace with a position instead of silent CPU. | **Done 2026-08-27** — `descend()` in `tsc-oracle.mjs`, every walk through it; Go has no hand walks, Rust's two stop on a fixed point |
| A-6 | H-17 | Per-file watchdog in the oracle driver, logging the last node position visited on timeout. The hang cost more to locate (11m47s + an instrumented copy) than to fix; that cost repeats without the guard. | **Done 2026-08-27** — worker-thread watchdog in `tsc-oracle.mjs`, `--watchdog` seconds (120), last file:line printed, exit 3 |
| A-7 | H-4 | Optional: `x/tools/go/callgraph/vta` as a second column for the func-value→* class only — maintained, materially tighter than RTA on func values. Costs memory (see H-9); an option, not a recommendation. | Optional |
| A-8 | §3.8 | State precision figures as lower bounds (most contradictions triage to oracle-wrong, so precision is bounded below by construction), and track the oracle-wrong : hobbes-wrong triage ratio per cell as a quoted number. | **Done 2026-08-27** — README, `oracle-grading.md`, architecture §3.8 wording; the ratio `oracle-wrong : hobbes-wrong : untriaged` is a required line of every cell record from here |
| A-9 | H-9 | Parked pending ~32 GB+ free. P8/P9 wait on it. | Parked |

## 3. Method

### 3.1 The n=1 symmetry

At first sighting of a defect, both available moves are
low-information, and the risks are symmetric:

- **Generalizing at n=1** attributes a single-instance problem to
  unseen siblings — it writes a policy over instances not yet observed.
  Had H-13's fix been generalized on sight to "drop every site in a
  foreign expansion," H-15 would have been silently mishandled: its
  correct treatment turned out to be *reclassify* (macro→function, a
  semantically real class worth counting), not drop. The class had
  internal structure only visible at the second and third sightings.
- **Patching at n=1** carries low confidence in the other direction —
  the patch may correct one copy of a duplicated definition and leave
  the class open. H-2's fix corrected a copy; the definition count
  stayed at two, and H-10 arrived later through a new feature
  (`--exclude`) landing on only one of them. No retrospective
  discipline catches this case: H-10 did not exist at H-2 time. Only a
  structural fix (definition count = one) prevents it.

Neither move is safe because *n* is recorded nowhere. The tally (§4)
records it, making the confidence of every patch explicit and the
promotion decision auditable.

### 3.2 Decision rule at first sighting

Generalize immediately only when the generalization is pure
deduplication — same definition, multiple copies, no semantic choice
being made (RC-1's membership function; RC-6's descend guard). When
the generalization would be a policy over a class — a rule about what
counts, what drops, what's silent — patch the instance, fixture it, tag
the root provisional, and let the second sighting reveal the class's
shape before naming the rule. This is refactoring's rule-of-three
applied to defect handling, and the log already follows it: D-O4
emerged from the grain cluster after multiple sightings, the
provenance rule from the Rust cluster after three.

### 3.3 Containment over prevention

The lane's safety comes from recurrence being cheap, not rare.
Fixtures plus triage-before-quote (design §8) bound recurrence cost
near zero: H-10 cost 250 false misses in one small cell, was caught in
triage before any number was quoted, fixed the same day, and fixtured.
Optimize recurrence cost, not recurrence probability — the latter is
where process-for-its-own-sake starts.

### 3.4 What not to add

No defect taxonomy beyond §4's one table. No class registry. No
mandatory compare-against-all-priors step on new entries. The log's
pattern paragraph performs the relational look, written when a pattern
actually emerges rather than checked on every entry. The only standing
reflex: when a new entry's "Was" smells like a root with n≥2 in the
tally, glance back for the sibling before closing.

## 4. Seen tally

**Semantics.** Every log entry maps to exactly one root (secondary
relations go in notes). A root carries *n* (sightings), its sighting
list, and a closure state:

- **provisional** — n=1, instance patched and fixtured, class shape unknown;
- **shaped** — n≥2, structure visible, rule pending or partially landed;
- **closed-structural** — the definition count is one, or a mechanical guard exists; the root cannot recur by construction;
- **closed-policy** — a named rule exists; a new sighting is a rule violation to fix, not a new defect class.

Per-defect status (open/patched) stays in the log; the tally tracks
roots. Maintained in the same commit as the log entry that changes it
— the log's own rule, extended.

| RC | Root | Sightings | n | Closure | Notes |
|---|---|---|---|---|---|
| RC-1 | Cell membership / scope defined in more than one place | H-2, H-10 | 2 | closed-structural | A-2 (2026-08-27): both Go sides call `edges.Under`/`edges.Excluded`. Per-runtime extractors (TS/py/rust) keep a local predicate — a sighting there reopens this row. |
| RC-2 | Code nobody wrote attributed to a source line | H-13, H-15, H-16, H-21 | 4 | closed-policy | Provenance rule: drop and count by default; reclassify when the dropped class is semantically real (macro→function). H-21 added the converse: a *declaration* the compiler synthesised at a source line a reader can point at (javac's default constructor, at the class line) is kept — dropping it costs real pairs. |
| RC-3 | Oracle right at a different grain than the binding | H-3, H-5, H-6, H-18, H-19 | 5 | closed-policy | D-O4, extended 2026-08-27 with the element-access bullet (A-4) and 2026-08-28 with the function-valued-binding (abstract) and `@overload`-anchor bullets. Two sightings against a closed-policy root in one triage: the rule held, its bullet list was short. |
| RC-4 | Silence that reads as a result | H-1, H-12 | 2 | closed-policy | RR-6: absence prints as its own state. A-1 landed 2026-08-27 (`no-roots`). |
| RC-5 | Ratio quoted with unlabeled over-approximation or mismatched denominator | H-4, H-14 | 2 | closed-policy | Split by class, label inflation; numerator and denominator from one index. Log rule 2. |
| RC-6 | Walk-down loop that does not strictly descend | H-17 | 1 | closed-structural | `descend()` guard landed 2026-08-27 (A-5); site rule landed via RC-3's element-access extension (A-4). |
| RC-8 | One declaration, two spellings — a cross-compilation identity key that is not canonical | H-20 | 1 | closed-structural | The key a shard emits must be built from the element model, never from a printed type: annotations, type-variable bounds and generic arguments all differ between a source compilation and the class file another compilation resolves against. Any future oracle that joins facts across separate compiler runs inherits this row. |
| RC-7 | Miss-class taxonomy diverges across languages | H-7 | 1 | provisional | Patched: local-binding split from closure; TS modes derived from binding shape so Go and TS classes read alike. Watch for the Rust/Python analogue. |
| — | Cosmetic | H-8, H-11 | 2 | — | H-11 → A-3. |
| — | Environment limit (not a defect root) | H-9 | 1 | parked | A-9. |

Coverage check: 19 of 19 entries mapped.

**Promotion mechanics.** New defect → assign to an existing RC or open
a new one at *provisional*. Assignment to an RC with n≥2 triggers the
§3.4 sibling glance. A root moves provisional → shaped at its second
sighting; shaped → closed when either the structural fix lands or the
class's shape is understood well enough to name the policy. A sighting
against a closed-policy root is a violation of the named rule and is
fixed as such — it does not reopen the root unless it shows the rule
itself was wrong.

## 5. Reviewer rules register

Accumulated one sentence at a time from the log; collected here so
review can cite them.

| RR | Rule | Source |
|---|---|---|
| RR-1 | A walk-down loop must strictly descend on every branch; enforced mechanically by a `descend()` that throws on no progress. | H-17 |
| RR-2 | Wrapper unwinding is a strict whitelist of known synthetic kinds; instantiations (`Origin() != nil`) are source functions — fold to origin, never unwind. | H-3 |
| RR-3 | Both sides of a cell diff consume one membership function and one node-identity mapping, round-trip tested. | H-2, H-10, H-12 |
| RR-4 | Sites in code the author didn't write are dropped and counted — or reclassified when the dropped class is semantically real. | H-13, H-15, H-16 |
| RR-5 | A ratio's numerator and denominator come from one index. | H-14 |
| RR-6 | Absence prints as its own state, never as an empty result. | H-1, H-9's cell record |
| RR-7 | An over-approximating class is quoted only next to its inflation label. | H-4, log rule 2 |

(Design §8's "no cell number quoted before triage is complete" already
exists as a rule; referenced, not duplicated.)

## 6. Open items carried forward

A-1 through A-6 and A-8 landed on 2026-08-27 (states in §2); A-7 optional; A-9 parked (H-9's root
module and each rooted subtree need ~32 GB+ free; P8/P9 wait). H-17
remains the sequencing exemplar: rule → fixtures → loop, in that order
— fixing the loop first would set an identity convention implicitly,
which is how H-5 happened.
