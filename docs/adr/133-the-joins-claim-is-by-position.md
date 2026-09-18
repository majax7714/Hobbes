# ADR-133 — The join's claim is by position, not by name

**Date:** 2026-09-18 · **Status:** accepted (Max, 2026-09-18: route a); built and graded at 0.2.45-beta (unit `3569`; `oracle-grading.md` §10.18: fmt 6,993 → 7,012 at 0 contradicted, 43 other stored-key cells ±0, 1,785 `uses` + 11 `calls` symbol edges added, none removed; P108–P113 met). Registers and lifts **C-163**; narrows C-162.

Follows ADR-132, whose P102 missed by 19 rows on this. Max, 2026-09-18:
measure it as its own item before touching a rule every language shares.
A build would be a patch: a constraint's fix.

## Context

`evidence.join` marks a lane B resolution as claimed by
`(file, line, name)`. A matched call or import site therefore hides
**every** resolution of that name on the line, not only the one it
matched: none of the others reaches the unclaimed loop, so none becomes
a `uses` fact, an operator call (ADR-131) or a construction call
(ADR-132). ADR-132 met it as `using fmt::detail::bigint;` …
`bigint n1(42);`; C-162 registers that one shape. The general case —
true `uses` edges withheld in every language — is in no register entry.

## The measurement (`~/.hobbes/bench/join-claim/`, nothing drawn)

**Step 0, what the claim hides** (`probe.py` wraps `join` and replays
its matching; 24 graded clones, `out/`; dagger, the 25th, finished after
the first writing: 734 hidden, 704 `new-uses`, 30 same-target, none at
the matched column — beside the 24's figures below, not in them). The probe's model is checked against a known
number: fmt reads `ctor-outside` 19, ADR-132's P102 rows exactly.

- **6,574 resolutions hidden.** Java carries most (Severed-Chains 2,875,
  spring-data-elasticsearch 1,014, jsoup 592), then TS (hono 893, zod
  775, kbet 121, ajv 55), quic-go 73, fmt 72, hobbes 43; zero on cJSON,
  sqlite-vector, minic, mux, cobra and gitleaks.
- **1,158 sit at the matched hit's own column** (hono 863, zod 266, ajv
  26, hobbes 3): alternates of one reference — `nodes[i].optimizeNodes()`
  resolving to the declaration and an override. ADR-104's abstention
  claims its resolution precisely so these do not resurface; they should
  stay hidden.
- **At another column:** 4,193 onto a definition no matched hit on the
  line names (`new-uses`), 1,204 onto the same definition as the matched
  hit (no new dependency), and fmt's 19 constructors. Read by hand, the
  `new-uses` rows are true dependencies: Java's `Element el = new
  Element("div")` (the type reference hidden by the constructor call's
  claim), TS's `core.$constructor<T> = core.$constructor(…)` (the
  interface hidden by the function), Go's `func (r *body) StreamID()
  quic.StreamID { return r.str.StreamID() }` (the return type hidden by
  the method call), a struct field's key beside a method of its name.
- **The matching itself is not the defect.** Of the sites that matched
  with more than one distinct target of their name on the line, every
  one but 2 (jsoup 1, hobbes 1) took the hit at its own exact column.

**Step 1, the rule simulated** (`ingest_bypos.py` rewrites the claim's
key in memory to `(file, line, name, col)`; `sim.sh` ingests each cell
stock and by-position on the same tree, exports and grades both against
the stored key; `PREREG-sim.md` written first). Eight cells:

| cell | confirmed / contradicted | symbol edges added | module edges added |
|---|---|---|---|
| fmt | 6,993 → **7,012** / 0 → 0 | 20 (11 `calls`, 9 `uses`) | 0 |
| args | 2,567 / 0, unmoved | 0 | 0 |
| jsoup | 18,627 / 0, unmoved | 363 `uses` | 0 |
| Severed-Chains | 29,793 / 0, unmoved | 634 `uses` | 0 |
| zod | 9,731 / 0, unmoved | 244 `uses` | 0 |
| ajv | 1,410 / 0, unmoved | 0 | 0 |
| quic-go | 3,766 / 15, unmoved | 9 `uses` | 1 |
| memchr | 921 / 0, unmoved | 3 `uses` | 0 |

Nothing removed on any cell; nodes and symbols unmoved; poison passes on
both arms everywhere. **P-j1–P-j6 all met** — fmt landed on 7,012, the
number ADR-132 predicted before the claim cost it 19. The one module
edge, `http3/body → interface` on quic-go, is the `quic.StreamID` return
type above: true, and absent today.

What the key cannot judge: a `uses` edge is not exported, so no oracle
grades the 1,262 added `uses` edges. The evidence for them is the hand
read and their shape — each is a reference the index placed at its own
column, of the kind the unclaimed loop already draws whenever no call of
the same name shares the line.

## Decision

Claim by `(file, line, name, col)`. A resolution at another column on a
claimed line goes through the unclaimed loop as any other; one at the
matched hit's own column stays hidden, so ADR-104's abstention and the
same-reference alternates hold. A resolution without a column (`col <
0`) shares the key `-1` with its line's others, which is today's
behaviour among them; a **site** without a column keeps the by-name
claim, since which resolution it matched is not known (no contested
site on the 25 clones was columnless, so the simulation's numbers stand). Three lines of `join`; no schema change, no new
fact kind.

On the build: register the general concession as **C-163** and lift it
in the same commit (what remains hidden — same-column alternates — is
its residual, by design); narrow C-162 (the using-declaration bullet
goes); regrade every stored cell, the prediction being every graded
number ±0 but fmt's +19.

## Routes for Max

- **(a, recommended; taken) build it**, one dispatched unit, then the full
  stored-key regrade. It is an accuracy fix before it is a recall one:
  the graph withholds true dependencies today and says so nowhere. The
  graded effect is fmt +19 confirmed at 0 contradicted; everywhere else
  it adds `uses` edges only.
- **(b)** register the concession (C-163, surfaced in `list_blind_spots`
  as a count) and leave the rule.
