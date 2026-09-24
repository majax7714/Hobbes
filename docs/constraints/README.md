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

Four parts, and the split is load-bearing (ADR-043):

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
- **Folded entries** (added 2026-09-13, ADR-043 amended) — two entries
  that concede the same information under two numbers, one a face or a
  restatement of the other. The narrower is **folded into** the broader.
  It keeps its number and its full text, so every pointer to it — in
  code, in a record, in another entry — still resolves, and it moves to
  the bottom of its own segment, where a user still meets that face. Its
  heading is marked `— *folded into C-n (date)*`, and an italic line
  under it names the parent and what the folded entry adds; the parent
  gains a **Folds in** line. The concession stands through the parent,
  so the debt summary counts it once, there, and the parent carries the
  weaker of the two surfacing statuses. Folding is not a lift, and
  it is reversible: if the two turn out to differ, the entry returns to
  the active part with a dated note.

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
| [`extraction-call-graph.md`](extraction-call-graph.md) | Extraction — the call graph | C-1, C-2, C-4, C-156, C-5, C-6, C-7, C-8, C-9, C-10, C-58, C-70, C-32, C-170, C-59, C-163, C-169, C-80, C-3 |
| [`extraction-typescript-javascript.md`](extraction-typescript-javascript.md) | Extraction — TypeScript and JavaScript | C-12, C-13, C-63, C-165, C-166, C-167, C-168, C-98, C-99, C-100, C-90, C-89, C-11, C-24, C-97 |
| [`extraction-cross-layer.md`](extraction-cross-layer.md) | Extraction — cross-layer | C-15, C-73 |
| [`extraction-lane-b-environments.md`](extraction-lane-b-environments.md) | Extraction — lane B environments and staging | C-22, C-23, C-27, C-64, C-150, C-158, C-159, C-161, C-74, C-85, C-79, C-16, C-33, C-34 |
| [`extraction-go.md`](extraction-go.md) | Extraction — Go | C-26, C-71, C-102, C-141, C-139 |
| [`extraction-rust.md`](extraction-rust.md) | Extraction — Rust | C-28, C-29, C-30, C-157, C-72 |
| [`extraction-java.md`](extraction-java.md) | Extraction — Java | C-66, C-67, C-68, C-69, C-101 |
| [`extraction-c.md`](extraction-c.md) | Extraction — C (ADR-108, ADR-109, ADR-110) | C-131, C-132, C-133, C-134, C-135, C-136, C-138, C-149, C-130, C-137 |
| [`extraction-cpp.md`](extraction-cpp.md) | Extraction — C++ (ADR-113) | C-142, C-143, C-145, C-146, C-147, C-148, C-151, C-152, C-153, C-160, C-162, C-164, C-144, C-155 |
| [`extraction-enrichment-packs.md`](extraction-enrichment-packs.md) | Extraction — enrichment packs | C-25, C-78, C-14 |
| [`narrative-invariants-review.md`](narrative-invariants-review.md) | Narrative, invariants, and review | C-17, C-19, C-20, C-21, C-154, C-18 |
| [`derivation-plan-mapping.md`](derivation-plan-mapping.md) | Derivation — the plan mapping (D1), the Calvin grounder and `hobbes gate` | C-35, C-36, C-37, C-38, C-91, C-109, C-110, C-111, C-112, C-113, C-117, C-118, C-121, C-122, C-123, C-126, C-104, C-105, C-106, C-107, C-108, C-114, C-116, C-119, C-120 |
| [`verification-benchmark-harness.md`](verification-benchmark-harness.md) | Verification — the benchmark harness (ADR-055), the TTT experiment (ADR-099) and the Calvin M0 local harness (ADR-100) | C-39, C-40, C-41, C-42, C-43, C-44, C-45, C-46, C-47, C-48, C-49, C-50, C-51, C-52, C-53, C-54, C-57, C-81, C-82, C-83, C-84, C-86, C-87, C-88, C-92, C-93, C-103, C-124, C-55, C-56, C-115 |
| [`dispatch-harness.md`](dispatch-harness.md) | The dispatch harness (ADR-107, ADR-112) — `hobbes dispatch`, the session and its records | C-125, C-127, C-128, C-129, C-140 |
| [`system-own-claims.md`](system-own-claims.md) | The system's own claims | C-31, C-60, C-61, C-62, C-65, C-94, C-95, C-96, C-75, C-76, C-77 |

Every entry keeps its `C-n`; an entry's segment is where a user meets
the limit. Lifted, superseded and folded entries appear at the bottom of
their segment, in that order, and are marked in the heading.

---

## Debt summary

**One hundred and seventy entries: one hundred and twenty-four active, twenty-nine lifted, eleven superseded, six folded**

| Status | Count | Entries |
|---|---|---|
| active — surfaced | 96 | every active entry not listed below |
| active — *partial* | 24 | C-1, C-9, C-25, C-58, C-68, C-83, C-88, C-102, C-117, C-125, C-131, C-132, C-133, C-134, C-135, C-138, C-141, C-142, C-149, C-150, C-153, C-164, C-167, C-168 |
| active — **unsurfaced** (debt) | 3 | C-19, C-20, C-112 |
| active — n/a (no user-visible effect yet) | 1 | C-10 |
| lifted | 29 | at the bottom of each segment |
| superseded | 11 | C-55, C-56, C-104–C-108, C-114–C-116, C-124 |
| folded | 6 | C-34 → C-23, C-97 → C-58, C-119 → C-118, C-130 → C-135, C-137 → C-28, C-120 → C-112 |

The table is the register's current state, read from each entry's
heading and its **You find out** field, and
`pipeline/tests/test_register_tally.py` holds it — and the copies in the
root `README.md`, `CLAUDE.md` and `docs/session-handoff.md` — to the
segment files. The dated notes that used to follow it are in
[`HISTORY.md`](HISTORY.md), newest first; a new note goes there.
