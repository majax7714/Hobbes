# Hobbes constraints — the register of what Hobbes cannot tell you

**Split into a folder on 2026-08-25.** The register that was one
1,800-line file is now one file per subsystem segment, listed in the
index below. The rules, the entry formats, and the debt summary live
here; the entries live in the segment files.

**Status: load-bearing.** This is not a caveats page. Principle **P8**
(`hobbes-architecture.md` §1) makes an entry here part of the definition of
done for any decision that concedes information, and **P9** extends that to
information conceded *for* us by a language provider we run — those entries
carry a `Provider` line naming the provider and pinned version, because
unlike our own concessions they can end on an upstream release (ADR-034).

This register is written for **anyone who runs Hobbes**, not for the people
who built it. Named individuals appear only as the source of a decision —
historical attribution, the same role an ADR number plays.

Its audience includes **agents** (ADR-047): what Hobbes cannot see is
itself context — it is how a single-use agent points at the work it must
do by hand — so the register's content reaches sessions through
`list_blind_spots` on the proxy, and the derivation contract
(architecture, "Where this is going") makes the stated complement a
mandatory half of any future derived context.

## Why this file exists

Hobbes' value is that a human can review at the concept level instead of
reading every line. That trade only works if the graph's silence is
*legible*. A gap that is known and stated costs a little trust. A gap the
artifact conceals while presenting a confident surface costs all of it:

> Hobbes is unusable if it's a known liar, even less usable if it's fake
> honest. — Max, 2026-08-15

So every place Hobbes drops, approximates, or cannot recover information
gets an entry below, and an entry is **not finished when it is written
here**. It is finished when it names the place a user meets the limit at
the moment it matters. ADR-029's resolution coverage is the model: 403
unaccounted call sites went from invisible to a per-file number a
reviewer can rank on, and it only got built because someone asked a
question that exposed the hole.

## How the register is organised

Three parts, and the split is load-bearing (ADR-043):

- **Active constraints** — limits that hold today. Grouped by the subsystem
  where a user meets them.
- **Lifted constraints** — limits that no longer hold, kept with **full
  documentation of how they were lifted**. Since the 2026-08-25 split
  each lifted entry sits **at the bottom of its own segment file**, not
  in a separate part — knowing a lift is extraction-specific is more
  useful than a chronological pile. A lift is a technique, and a
  technique has a boundary: an input the technique does not classify falls
  back to being conceded — *silently*, unless the boundary is written down.
  So a lifted entry is not archived trivia; it records the exact mechanism
  of the lift and the residual edge cases that mechanism leaves outside.
  Residue that turns out to matter becomes a new active entry — C-11 →
  C-24 is the worked example, and it happened twice: C-24's own lift left
  residue in turn.
- **Superseded constraints** (added 2026-08-23) — limits that were never
  lifted but whose *path no longer runs*: the mechanism they concede
  information about was retracted or replaced (an experiment path P12
  withdrew, a subsystem v2 replaced). Not lifted — the concession would
  return the day the path does — so each keeps the Was / Superseded-by /
  Would-return-if format, and the debt summary does not count them as
  active. Like lifted entries, they sit at the bottom of their segment.

Entries are numbered `C-n`, sequential and stable, and are **never
renumbered or deleted**. When a constraint is lifted, its entry moves to
its segment's Lifted section keeping its number, because "we used to concede this, and
here is precisely how we stopped" is itself information — the next
constraint usually hides in a lift's edge cases.

## How to read an active entry

| field | means |
|---|---|
| **Cannot tell you** | the limit in a user's terms, not the implementation's |
| **Because** | the mechanism that makes it so |
| **Bites at** | the artifact, tool, or question that goes quiet |
| **You find out** | the surfacing mechanism — how a user learns it, in the moment |
| **Provider** | *(inherited limits only, P9)* the provider and pinned version, and whether an upgrade could lift it |
| **Source** | the ADR or session that conceded it |

**Surfacing status** is the field that matters:

- **surfaced** — a real mechanism tells the user, where they are standing.
- **partial** — something says it, but not at the point of use, or not in
  terms the user can act on.
- **unsurfaced** — documented only. **This is the fake-honest case**, and
  it is debt, not a decision. Every `unsurfaced` row is a bug waiting for
  a milestone that can afford it.

## How to read a lifted entry

| field | means |
|---|---|
| **Was** | the limit as it stood, and why it was conceded then |
| **Lifted by — the technique** | the exact mechanism of the lift — what now classifies the cases the constraint used to concede |
| **Residual edge cases** | inputs the technique does not classify, stated as the technique's boundary — where the old concession quietly survives |
| **Source** | the ADR or session for the concession *and* for the lift |

This file is not `docs/future_additions.md`. That one parks deferred
*work*. This one registers conceded *information*. A deferral that loses
information appears in both, and the entries cross-reference.

---

---

# Index — the segment files

| File | Segment | Entries |
|---|---|---|
| [`extraction-call-graph.md`](extraction-call-graph.md) | Extraction — the call graph | C-1, C-2, C-4, C-5, C-6, C-7, C-8, C-9, C-10, C-58, C-70, C-32, C-80, C-3, C-59 |
| [`extraction-typescript-javascript.md`](extraction-typescript-javascript.md) | Extraction — TypeScript and JavaScript | C-12, C-13, C-63, C-90, C-89, C-11, C-24 |
| [`extraction-cross-layer.md`](extraction-cross-layer.md) | Extraction — cross-layer | C-15, C-73 |
| [`extraction-lane-b-environments.md`](extraction-lane-b-environments.md) | Extraction — lane B environments and staging | C-22, C-23, C-27, C-34, C-64, C-74, C-85, C-79, C-16, C-33 |
| [`extraction-go.md`](extraction-go.md) | Extraction — Go | C-26, C-71 |
| [`extraction-rust.md`](extraction-rust.md) | Extraction — Rust | C-28, C-29, C-30, C-72 |
| [`extraction-java.md`](extraction-java.md) | Extraction — Java | C-66, C-67, C-68, C-69 |
| [`extraction-enrichment-packs.md`](extraction-enrichment-packs.md) | Extraction — enrichment packs | C-25, C-78, C-14 |
| [`narrative-invariants-review.md`](narrative-invariants-review.md) | Narrative, invariants, and review | C-17, C-19, C-20, C-21, C-18 |
| [`derivation-plan-mapping.md`](derivation-plan-mapping.md) | Derivation — the plan mapping (D1) and the Calvin M0 grounder | C-35, C-36, C-37, C-38, C-91 |
| [`verification-benchmark-harness.md`](verification-benchmark-harness.md) | Verification — the benchmark harness (ADR-055), the TTT experiment (ADR-099) and the Calvin M0 local harness (ADR-100) | C-39, C-40, C-41, C-42, C-43, C-44, C-45, C-46, C-47, C-48, C-49, C-50, C-51, C-52, C-53, C-54, C-57, C-81, C-82, C-83, C-84, C-86, C-87, C-88, C-92, C-93, C-55, C-56 |
| [`system-own-claims.md`](system-own-claims.md) | The system's own claims | C-31, C-60, C-61, C-62, C-65, C-75, C-76, C-77 |

Every entry keeps its `C-n`; an entry's segment is where a user meets
the limit. Lifted and superseded entries appear at the bottom of their
segment and are marked in the heading.

---

## Debt summary

**Ninety-three entries: seventy-one active, twenty lifted, two superseded**
(C-92 and C-93 added 2026-09-04 by Calvin M0 step 5, ADR-100 — the
local harness binds a SHA's tests to a source checkout's dependency
trees, and reaches a behaviour only through a test the testmap maps;
C-91 added 2026-09-04 by Calvin M0 step 3 — grounder v0 binds call
sites only, in Python, Go and TS/JS, and abstains on members of values;
C-90 added 2026-09-03 by the same re-ingest and **lifted the same
night** — a tsconfig that `extends` or `references` a config off the
zone's walk-up path is now staged transitively and a solution-style
root gets the generated config: date-fns 15 of 15 zones, lanes 7,601 / 0;
C-89 registered and lifted 2026-09-03 the same hour — an overloaded TS
declaration placed at its implementation where the semantic lane places
it at its first signature, found by date-fns's re-ingest once C-74 gave
it lane B: 54 disagreements and below-floor calls, gone; C-73, C-74 and C-85 **lifted 2026-09-03**, the same session, the last
of the ten: a repo-internal directory link is walked once at its target
and recorded, a workspace's `node_modules` links mount their targets
and the helper tells an indexer's death from its own, and a Python repo
with no venv indexes against an empty listing with the fix named —
measured on a venv-less fixture (0.0% → 68.4%) and a synthetic
workspace (TS6053 → a semantic edge);
C-72 and C-80 **lifted 2026-09-03**, the same session, the two the
four-repo test found on the call graph itself: the Rust fallback
abstains where a path's head does not single out a declaration, and an
expression receiver is a Python call site with the `uses` gloss reworded;
C-78 and C-79 **lifted 2026-09-03**, the same session: the `http-go`
pack reads the receiver and the import before a name counts, and the
dependency reader takes `setup.cfg` and `requirements*.txt` and records
when no manifest declared anything — `setup.py` stays unread;
C-75, C-76 and C-77 **lifted 2026-09-03** — the first three of the
2026-09-02 nine cleared on the lead's direction, easiest first: the
lanes self-test counts only semantic module edges as lane B's and prints
lane B's share, the summary and `hobbes diff` count `calls` and `uses`
apart, and the proxy's tail table carries `below-floor`; the register
no longer holds a line that reads larger than the truth; C-86–C-88 added 2026-09-03 from the review of the TTT results: the
shuffled control's margin is a bound, not the graph's worth (*surfaced*);
the first NLL write-up left the conditioning unstated, a reporting
defect (*surfaced*); an adapter trained on "none recorded" answers
disbelieves the card in front of it (*partial*, candidate fixes named);
C-85 added 2026-09-03 from ADR-099's memorised-cell ingests — a Python
repo with no venv loses lane B entirely in the container and the record
blames the helper (*partial*; **lifted the same day**, above);
C-81–C-84 added 2026-09-03 by ADR-099, the test-time-training
experiment: the adapter is regenerable but not bit-identical across
hardware (*surfaced*, the manifest), held-out names leak through plain
words and the doc rendering is empty where nothing narrated
(*surfaced*, the corpus manifest), the memorisation probe is a coarse
gate (*partial*), and a git-history unit carries the base graph's
context — 92 of this repo's 147 units name files the base never had
(*surfaced*, per unit); C-71–C-80 added 2026-09-02 by the four-repo extraction test — four
random public repos, one per language, each ingested contained and
hand-sampled; two stopped on lane disagreements. **C-71** — the Go
graph is one build configuration's and lane A abstains where
constraints split a name — is the one *fixed and surfaced* the same
day (ADR-098: two wrong syntactic edges and twelve disagreements on
quic-go gone). The other nine are **registered, not fixed**, at Max's
direction ("flag rest in constraints"; **all nine lifted the next day**, above): C-72 the Rust fallback's
last-segment binding (*partial*), C-73 a repo symlink walked as a
second copy (*partial*), C-74 workspace links dangling in the
container with a record that blames the helper (*partial*), C-75
`hobbes lanes` counting the join's fallback as lane B
(**unsurfaced**), C-76 the summary's "call edges" counting `uses`
(**unsurfaced** — the one line that reads *larger* than the truth),
C-77 `list_blind_spots` dropping `below-floor` (**unsurfaced**), C-78
the `http-go` pack firing on any `Handle` (**unsurfaced**), C-79 no
`dependency_coverage` for `setup.py` repos (**unsurfaced**), C-80
`super().m()` / `f().m()` not a site and glossed as not a call
(*partial*). Five of the nine are one-to-ten-line fixes with the
candidate named in the entry; C-70 added 2026-08-29 — two same-named calls on one line can pair with
the wrong resolution, found by Java's fluent chains and measured at
0.05% of dual-resolved sites, surfaced as a lane disagreement;
C-66–C-69 added the same day by ADR-096 — Java: the build runs in the
container with a network (C-66; **narrowed 2026-09-01 by ADR-097**: the networked pass holds no sources, the index pass no network), the
one-configuration graph, generated sources (*partial*), and read-not-resolved
dependency counts — three surfaced on day one; C-65 added 2026-08-28 by ADR-094 — the knowledge proxy pinned to the
image, the host hatch disclosed, surfaced on day one; C-64 added 2026-08-27 by ADR-092 — lane B contained, executing
providers refuse without it, surfaced on day one; C-63 the same day by the
oracle lane's H-17 close, unsurfaced; C-58 added 2026-08-25 by the oracle lane; C-60–C-62 — the trace
asymmetry, the reference-lane rule and design §3's four rules —
registered surfaced the same day by the lane's phase 2, C-62 late for
phase 1; C-59 registered and lifted the same day — unsurfaced, and the first
entry where a coverage number reads *better* because of the gap; audited against the tree on 2026-08-23 — every active entry re-checked
against the code that concedes it; none had been silently lifted). Four of the active are *partial* (C-4, C-58, C-68, C-83); two
are **unsurfaced** (C-19 — narrowed to two tools, and since ADR-095 every compiled config is executed in CI — and C-20; the 2026-09-02 five — C-75, C-76, C-77, C-78, C-79 — were all lifted 2026-09-03; C-63 — *unsurfaced* since 2026-08-27 and never in this count — was **surfaced 2026-09-05**: the site is counted and classed `expr-callee`, ADR-045 amended); C-58 — the interface/closure call hole, whose capture number reads
resolved — moved to *partial* on 2026-08-25 (ADR-090: the `below-floor`
tail class); C-4 moved from unsurfaced to *partial* in that audit, its status
having lagged the ADR-047 denominator statement by a week. The same audit
corrected four drifted prose lines (C-35, C-42, C-46, C-54) and moved
C-55/C-56 to the new Superseded part. C-31 left the unsurfaced list on 2026-08-21 (ADR-053:
the verification base stamped into the artifact and stated wherever a
language list is read), as did C-32's `partial`. The three derivation entries (C-35..C-37,
ADR-051) landed surfaced on day one — the statement prints on every
`hobbes plan` run and rides every change-spec. **Twenty are lifted**, C-33 fastest of
all: registered from the dagger measurement (ADR-048) and lifted one
session later (ADR-049) when Max reviewed the candidate fix and
directed it — the register working as intended, a finding becoming a
fix through review rather than around it. The other six —
C-14 in the 2026-08-16 register paydown (three CLI packs; the entry's
own counter-example is the pinned exit check),
C-11 at V2.M3, C-3 and C-16 in the 2026-08-15 pre-M6 sweep (which also
surfaced C-5 and C-26), C-18 at V2.M6, and C-24 the same day: the JSX
lift was approved with the standing condition that "in every meaningful
sense" keeps its outliers named, which the lifted entry does. That churn
is the point of keeping the register: none of it was knowable before
this file existed, and what remains is the backlog P8 generates.

The **2026-08-16 paydown** worked the register's own ranking, worst
first: C-14 lifted (CLI packs), C-12 narrowed and
surfaced (ADR-041 — the #1 entry's common cases now resolve, its
residue reports itself), C-19 narrowed to two tools (semgrep executes
in the agreement suite, and its emitter survived first contact clean
where import-linter's had not), and C-21 surfaced (ADR-042 — the queue
shows the record a proposal restates, with the I-9/I-3 failure as the
pinned case). Four entries, four mechanisms, each landed with its
tests in one commit.

C-27 arrived the way the register says entries should: C-16's first
working run produced a number (0 of 5 resolved), the number was
investigated rather than explained away, and the investigation found
*two* stacked causes — a hardcoded venv path and an indexer asking the
wrong environment entirely. Both fixed same-day, and the entry records
what remains: discovery is convention-bound, and `dependency_coverage`
is the answer for environments the conventions miss.

V2.M4 added one entry (**C-25**) and it is *partial* rather than
unsurfaced, because `graph.json`'s `packs` list was added in the same
commit as the pack layer. Attributing a layer to the pass that produced it
was the cheap half of the answer; suppressing it is the half that is
deferred.

V2.M5 added **C-26** (also partial) and **widened C-6**, which is the more
interesting event: measuring a second indexer showed the original entry was
filed too narrowly. C-6 was written as "scip-python does not populate
`syntax_kind`" and read as a gap one upgrade could close; `scip-go` omits
it too, so the entry now says no indexer populates it and an upgrade of one
lifts nothing. **A register entry can be wrong by being too specific**, and
nothing catches that except measuring the next case.

The 2026-08-15 audit (before V2.M6) found the complementary failure: **a
register entry can be made wrong by a milestone that never touched it.**
Six entries had drifted, all by M4/M5 side-effects — C-3 materially (Go
emitted stdlib `ext:` nodes where Python and TS dropped them, an asymmetry
no ADR registered), C-15's merge order predated both the pack layer and
Go, and C-5/C-9/C-10/C-14 named mechanisms or providers that had since
moved or multiplied. Nothing detects this today: the register is prose,
and no milestone exit re-reads entries it did not write.

The same day's sweep then paid down the worst of what the audit ranked:
C-3 was lifted outright (ADR-038 — stdlib everywhere, rather than
re-hiding what Go already showed), C-16 was lifted (the manifest walk),
and C-5 and C-26 went from silent to one degradation record per declined
route and per orphan Go directory. C-5's surfacing also caught the Nest
reader *emitting* a computed route with the segment dropped — the one
shape worse than absence, found only because surfacing forced the decline
path to be written down.

V2.M7 added three entries (**C-28/29/30**) and amended two (**C-9**: macro
is the fifth graph kind; **C-6**: a third indexer confirmed the
generalisation) — and it is the first milestone whose **every new entry
arrived surfaced**: C-28 through the decode degradation record, C-29
through a stderr disclosure on every rust ingest, C-30 through
`dependency_coverage`. C-28 also replayed C-6's arc at higher speed:
written for cargo targets in the morning, generalised the same day when
the verification re-ingest showed scip-go duplicating package namespaces
too — and this time the drop *removed two false semantic edges* that had
stood in the Go graph since V2.M5, the register mechanism catching a lie
rather than only naming a silence. C-29 is also a first of its kind: an
entry registering something Hobbes **does** (execute a Rust repo's
`build.rs` and proc macros at ingest) rather than something it cannot
see — the honesty discipline pointed at a capability instead of a gap.

Ranked by how badly each remaining entry misleads, worst first:

*(The two entries that held this list are gone as of the 2026-08-16
paydown: C-12 — cross-zone edges simply absent — is narrowed to
alias-only cases and surfaced (ADR-041), and C-14 — "an empty CLI list
reads as 'no CLI'" — is lifted outright. What remains stays quiet
rather than lying, which is a real difference; the worst residue is
C-4's fixture-thin test reach and C-19's still-unexecuted emitters.)*

**No line in the register inflates a number.** For one day (2026-09-02
to 2026-09-03) C-76 — the summary's "call edges" label counting `uses`
— did, and it was lifted by a relabel on the lead's direction.
Before it, C-11 was the only
entry that made a claim larger than the truth, and V2.M3 lifted it; C-24,
its deliberately-under-reporting residue, was lifted in turn once the
under-report could be replaced with the true edge rather than the safer
inaccuracy. Every remaining limit under-reports or stays silent — so a
Hobbes number can now be read as a floor, which is a property worth
defending in later milestones. **C-31 is the near-exception and the
reason it was filed** (2026-08-16): not a number but a word —
"supported" — that read larger than its evidence, a language list whose
rows presented as peers while their verification bases differ by an
order of magnitude. Architecture §3.8 now scopes the claim; the entry
holds the unsurfaced remainder, deliberately taken as debt with its
candidate surfacing named, rather than pretending a table in a document
reaches a user at ingest.

**The tail view landed the same day** (ADR-045, C-2 amended, C-32
added): the unresolved count now decomposes on every ingest into
observation-based classes, and the 2026-08-16 measurement that
motivated it showed the tails were never uniformly dark — kbet's
worst-looking number (72.1% accounted) hid a tail that is 61%
below-the-floor local bindings the checker could name all along, with
**9 sites of 1,339** fitting no observation at all. The measurement
also produced the session's working vocabulary: *seen and not modelled
by design* is knowledge; *cannot resolve* is the concentrated remainder
this register exists to track; and any of it that turns out to be
**needed** for derived context is a direct entry here, never a
percentage's rounding error.

**Track record so far:** three of the four entries touched at V2.M3 were
*already true and already invisible* before the register existed — C-23 in
particular had a check written specifically to catch it that could not fire
under any circumstances, and C-11 had been honestly documented at M6 and
went on misleading for two milestones. That is the argument for P8 restated
as evidence: being written down in an ADR at the moment of decision did not
stop either of them.
