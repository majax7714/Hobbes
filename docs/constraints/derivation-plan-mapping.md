# Derivation — the plan mapping (D1)

*Part of the constraint register — see [`README.md`](README.md) for how to read an entry, the surfacing statuses, and the debt summary.*

### C-35 — Partition quality is unvalidated
- **Cannot tell you:** that a change-spec's partition is a *good* one —
  that its units minimize rework, that its contracts hold through
  implementation, or that its budget and thresholds fit any repo but
  the ones it was sketched against. Every number the mapping runs on
  (tier and edge-type weights, the 0.55 per-hop decay, the 0.2
  threshold, the 60k budget, the 200-commit window, the 300-token
  contract overhead, the human-first threshold) is a declared guess
  from ADR-051's pinned table.
- **Because:** the design (agent-mapping §6) defines partition quality
  as a *measured* number — rework, contract failures, context-fault
  rate, tokens, wall time from the flight recorder — and the record
  now exists (`partition-record.json`, ADR-054: rework files, context
  faults, contract failures, stage wall time) but nothing *fits* the
  weights to it: the loss is still computed under the declared guesses
  (corrected 2026-08-23; the original text said the execution milestone
  was not built). Claiming quality before measuring it would be
  the P11 mistake at mapping scale. One parameter already earned its
  place the hard way: the per-hop decay exists because the dogfood
  exit check measured its absence (one seed → 33 units, the whole
  connected component).
- **Bites at:** every `hobbes plan` run — the partition may split what
  should stay together or bundle what should split, and the spec
  cannot warn you beyond its flags (`oversize`,
  `coordination-heavy`, `human-first`).
- **You find out:** **surfaced** — every plan run prints the C-35
  statement and every change-spec carries it in its `validation`
  field; the flags name the shapes the mapping itself distrusts.
- **Source:** ADR-051 (2026-08-19); the lift path is the parked
  recorder milestone (`future_additions.md`).

### C-36 — Seed resolution is lexical, not understood
- **Cannot tell you:** what a proposal *means*. Seeds resolve by exact
  (case-insensitive) match of proposal terms against node ids, path
  stems, and symbol names — plus explicit `--seed` values. A proposal
  whose intent is clear to a human but whose words match no identifier
  seeds nothing; a prose word that happens to equal a symbol name
  seeds spuriously (stopword-guarded, not solved).
- **Because:** the mapping is deterministic and quota-free by design
  (P5): a generative planner interpreting prose would make the impact
  set a model opinion, unreproducible between runs. The honest
  deterministic reading is exact match plus a refusal to guess —
  unmatched code-shaped terms are reported, never inferred into the
  graph's nearest neighbor.
- **Bites at:** plans phrased in domain language rather than code
  names ("the checkout flow" seeds nothing unless a node is named
  that), and renamed concepts whose old name still matches something.
  *Measured on real issues (ADR-055, eight `psf/requests` SWE-bench
  instances, quota-free): all eight seeded, four seed sets touched a
  gold-patch file. The misses have three shapes — dotted
  `package.function` names (`requests.get`) match no symbol *name*;
  trailing punctuation makes prose look code-shaped (`fine:`,
  `it.`); generic words (`data`, `json`, `session`) seed spuriously.
  Candidate adjustments are in `future_additions.md`; not applied
  before verdicts exist.*
- **You find out:** **surfaced** — `hobbes plan` errors with the
  `--seed` hint when nothing resolves (exit 2), and every change-spec
  lists `unresolved_terms` with the C-36 note; resolved seeds show
  which term hit them, so a spurious seed is visible in the spec.
  *Amended 2026-08-22 (harness restructure, phase 0): the first live
  astropy run seeded the root package (`astropy`) plus fourteen prose
  words (`input`, `open`, `check`, `unit`, …) and the impact set was
  the repository — the candidate patch overlapped the gold files in
  zero places. Two deterministic hygiene rules now set such seeds
  aside when better evidence exists (`impact.filter_seeds`), and the
  spec lists each under `seeds_rejected` with its reason; `hobbes
  plan` prints them. The rules narrow spurious seeding; they do not
  read prose — the generative planner above this layer is the
  restructure's phase 2.* *Amended 2026-08-28 (ADR-093, defect D6): a
  lexical hit on a **hub** (fan-in ≥ 30) is a seed for expansion but
  not work — the spec lists it under `seeds_context`, `hobbes plan`
  prints "seed is context, not work", and a plan whose every seed is
  one is a `SeedError` naming `--seed`; a human's or the planner's
  seed is unaffected.*
- **Source:** ADR-051 (2026-08-19); ADR-093.

### C-37 — A pinned contract is a declaration site, not a signature
- **Cannot tell you:** a cross-unit interface's parameter types,
  return type, or semantic contract. A contract pins the target's
  identity, kind, file and line range, tier, owner, and in-scope
  invariants — the graph carries no richer signature to pin
  (symbols are id/kind/range; SCIP descriptor filtering is C-9).
- **Because:** inventing a signature from source text would be a
  second parser outside the owning lane (I-4's rule) and a guess at
  exactly the moment agents need a fact — two implementers building
  against a paraphrased interface is the rework the contract exists
  to prevent. A pin that says "the function at this site, as it is"
  is smaller and true.
- **Bites at:** contract renegotiation — an agent cannot tell from
  the spec alone whether its counterpart changed a signature, only
  that the declaration site moved; the far side must be read at its
  cited lines (which the pin makes one hop away).
- **You find out:** **surfaced** — every contract entry in every
  change-spec carries `pin: declaration-site, not a type signature
  (C-37)` inline.
- **Source:** ADR-051 (2026-08-19).

### C-38 — A derived write scope is enforced at the cut, not at the mount
- **Amended 2026-08-22 (ADR-061):** an implementer's out-of-scope
  edits are now **dropped at integration** — the candidate patch takes
  only the part of a unit's diff that touches files the unit owns
  (interior + guarding tests). C-38's "before a run has shown where
  agents stray, enforcing would be tuning a guess" was discharged by
  the phase-4 probe: on astropy-13579 four units with unrelated
  interiors all created the same file `astropy/wcs/wcsapi.py` (a file
  none owned, and not the gold `wrappers/sliced_wcs.py`) while the unit
  that owned the gold file did nothing, and a `session_commit.txt`
  scratch note leaked into the patch. The run showed the stray, so the
  cut now enforces the scope: neither a neighbour's file nor a scratch
  note reaches the patch, and no two units can write the same file.
- **Cannot tell you (the residual):** that an agent *could not* have
  written outside its unit *inside its own worktree*. The sandbox still
  mounts the worktree **whole** (rw for an implementer / overlay for a
  read-only role, ADR-060), and the agent policy layer is
  command-pattern, which cannot express "these paths only" — so the
  model can still waste a turn writing a neighbour's file; that work is
  discarded at the cut and recorded. The orchestrator diffs the
  harvested branch against the manifest and records every file outside
  it as **rework** — §6's first loss term — and the integration record
  names what it **dropped**. Two neighbours of the same shape:
  contract **renegotiation has no approval flow** (a reflection lands
  in the orchestrator's inbox for a human; nothing re-pins both sides),
  and **tokens and wall time are unmetered** (the loss lists them as
  unobserved rather than filling them in). *(Metering amended
  2026-08-21, ADR-055: the session's default command now requests
  Claude Code's JSON result envelope and `hobbes bench` reads it per
  unit — a session that emits none is still recorded unobserved,
  never imputed.)*
- **Because:** path-grain write enforcement is mount work inside the
  session image — a per-unit overlay, or bind-mounting interior paths
  rw over a ro worktree — and the base was built to run under the
  benchmark harness first and be corrected from its errors (ADR-052,
  ADR-054). Measuring rework costs nothing and is the signal the loss
  needs; enforcing it before a run has shown where agents actually
  stray would be tuning a guess.
- **Bites at:** the policy manifest's `write_mounts` list, read as a
  guarantee; the partition record's `rework_files`, which is the
  honest form — "wrote outside", not "could not".
- **You find out:** **surfaced** — `partition-record.json` carries the
  per-unit `rework_files` (what the model wrote out of scope) and
  `integration.dropped` (what the cut discarded); the loss lists its
  unobserved terms by name. The brief's "advisory at path grain"
  wording is now "enforced at the cut" (the model may still write out
  of scope, but it will not land).
- **Source:** ADR-054 (2026-08-21); enforced ADR-061 (2026-08-22).

### C-91 — Grounder v0 grounds call sites only, in three languages, and abstains on members of values

- **Amended 2026-09-11 (Calvin M0-Go WP-3, grounder v1):** a **Go**
  member is now judged when the syntax states its receiver's type — a
  receiver or parameter, `var x T`, `:= T{}` / `&T{}` / `new(T)`, or a
  package-level var of those shapes. Rule 1 binds the graph's method, a
  method the diff adds (`gensym`), or one promoted through an embedded
  repo type, else NULL; a struct field reads `field`, a type outside
  the repo `external`, a predeclared type `builtin`. Rule 2 binds a
  method a parent-graph interface declares to that interface method
  (`interface`, inside HSR's denominator, now in-graph + interface +
  NULL). Go members **still abstaining**: receivers typed only by a
  call result (`x := f()`), range variables, package vars set from a
  call (`regexp.MustCompile`), members possibly promoted from an
  out-of-repo embedded type, types defined over named types, and type
  parameters, local types and untyped bindings. Rule 2's implementers
  come from an RTA key at another SHA (the cell's, not each parent's);
  `hobbes ground` passes no key, so its `interface` rows carry
  `implementers: null`. Go's universe is a pinned literal, go1.26.5's
  `go/types.Universe` (44 names), like C-32's builtin lists. Measured
  on the 20-key Go gold run: 2,578 references, `unknown-receiver` 53 → 5,
  13 methods judged by rule 1, 0 NULL, `interface` 0 (no gold site is a
  repo interface call, so rule 2 is settled on tests only). Python and
  TS/JS members are unchanged: v0's abstention below still holds for them.
- **Cannot tell you:** that a fill's **type references, decorators,
  composite literals or attribute reads** name real symbols — the
  grounder (`hobbes ground`, Calvin M0 §2.3) binds the **call sites**
  lane A's providers extract from the post-image and nothing else;
  that a **Rust or Java** fill's references exist at all — it is placed
  and reported `unsupported`; or that a **member on a value** is real —
  `self.x` the class does not declare (inherited, an attribute, or
  invented), `Class.attr` on an imported class, a module-level
  constant's method, a member of a name a JS import binds — each is an
  abstention (`unknown-receiver`), not a NULL, so a hallucinated
  *member* passes where a hallucinated *function* does not.
- **Because:** the providers extract call sites and definitions; the
  graph models functions, methods, classes and types, not values or
  inheritance, and v0 is exact-match-or-NULL with no rule that would
  need either (the design: "measures how often exactness fails, which
  is the residual"). Rust and Java have providers but no unit in the
  set exercises them, and P11 scopes the claim to what ran.
- **Bites at:** HSR (§4.6) — its denominator is in-graph + NULL, so the
  abstained and unsupported references are outside it by construction
  and the rate reads over fewer sites than the fill contains; the
  measured gold run: 155 abstained and 13 unsupported files against
  3,760 sites.
- **You find out:** **surfaced** — every reference row in the ground
  record carries its class; `hobbes ground`'s summary and the batch
  report print the `unknown-receiver` and `unsupported` counts beside
  the NULLs; the record's language table says which languages ran.
- **Source:** Calvin M0 step 3 (2026-09-04, the probe record's fourth
  addendum).

### C-104 — Template v2 shows a capped callee by its signature line until it is confirmed

- **Cannot tell you:** what a callee's body holds, when the callee
  belongs to an anchored symbol with more than `CALLEE_CAP` (k = 20)
  distinct in-repo callees. Under template v2 such a callee is not
  expanded. It is asked in round 1 as an `ANCHOR_CONFIRM` showing its
  signature line only, and its body, callers and tests join the
  template only if the orchestrator confirms it. The confirmation is
  made from one line. A change the task names only through the fan-out
  is not in round 2 unless a confirmation lets it in.
- **Because:** v1 expanded every callee of every seed, and one
  registry symbol (gitleaks' `cmd/generate/config/main.main`, 177–223
  callees) turned eight keys into 181–269 body holes and 3.0–7.5M
  characters each (M0-Go F1). The cap trades that cost for a round-1
  question per held-back callee.
- **Bites at:** v2 templates only; v1 is the default, and the
  `hobbes template` CLI builds v1. On the 20 M0-Go keys at A2, strict
  Go coverage goes from 86/7/6/4 to 86/6/6/5: the hunk lost is 107a41
  `gitlab.go:180`, a new rule that v1 reached only through
  `main.main`'s fan-out, and that at v2 is a declare-hole in a file A2
  does not name. Gold said yes to none of A2's 1,574 cap confirmations.
- **You find out:** **surfaced** — each held-back callee is a named
  round-1 hole (`matcher: callee-cap`, its seed and the seed's callee
  count in the ask), and a v2 template carries `callee_cap` and a
  pruning rule stating the cap.
- **Source:** Calvin M0-Go WP-2, 2026-09-11 (`docs/calvin/calvin-m0-go.md`
  §10, F1; `docs/calvin/calvin-potential.md` §2.1).

### C-105 — A protocol v0.3 pattern answers many holes with one judgement

- **Cannot tell you:** that the orchestrator weighed each hole a pattern
  filled. Under adapter protocol v0.3, `patterns: {"BODY": "unchanged"}`
  (likewise SIGNATURE, or ANCHOR_CONFIRM `"unchanged"`/`"no"`) fills
  every open hole of that type that the reply does not answer
  explicitly. One word can leave a hundred bodies alone or refuse two
  hundred confirmations; no repair then asks those holes one by one.
- **Because:** Max's decision of 2026-09-11. On WP-5's run, refused
  patterns cost 7 of 22 calls and 36% of the spend, and the outcome
  is the one silence already gave: an unanswered BODY or SIGNATURE ends
  unchanged, and an unanswered confirmation is a refusal. v0.3 accepts
  the pattern rather than paying a repair to have each hole restated.
  A pattern never rewrites or confirms, so a change or a "yes" still
  has to be stated per hole.
- **Bites at:** reading a record's "answered" count as per-hole
  attention, and the arm-T readings that ask whether the orchestrator
  considered a symbol (H-a, H-s). The replay of WP-5's records: 321
  holes filled by pattern in 4 exchanges; d29ee5's 208 capped-callee
  confirmations refused in one pattern.
- **You find out:** **surfaced** — every filled-by-pattern hole is
  listed under `by_pattern` (hole id → type) in the exchange and the
  arm-T record, the round record counts `pattern_confirmations`,
  `t-units` rows count pattern fills by type, and every exchange and
  record carries `protocol_version`.
- **Source:** Calvin M0-Go WP-5, 2026-09-11 (Max's decision;
  `docs/calvin/calvin-potential.md` §2.2).

### C-106 — A near-miss name is re-asked, never offered a declaration

- **Cannot tell you:** that a name the orchestrator wrote, one near a
  real one, was meant to be new. Under adapter protocol v0.4 the NULL
  round-trip offers a declaration hole only for a NULL classed `new` or
  `invented` whose bare name is in no module of the parent graph. A
  `near-miss` goes back to the hole that wrote it, as in v0.3, with the
  nearest graph names shown. A near-miss is an exact name in another
  module, or a graph name within edit distance 3 (`ground._NEAR`). The
  same happens to a name declared where the call does not reach. So a
  genuinely new name that lies close to an existing one cannot be
  declared through the loop.
- **Because:** near-miss is the grounder's class for a spelling or
  placement miss. Offering a declaration there would invite a
  duplicate beside the real symbol, so the loop asks again so the
  model can name the existing one.
- **Bites at:** T-loop's closure on short new names and on names beside
  a near sibling. The re-ask may bind the near name, an existing symbol
  the task did not mean, or NULL again. Not measured: WP-7a's replay
  closed all 11 of WP-6's declare-routed sites, and those were `new`
  or `invented`.
- **You find out:** **surfaced** — every NULL site in the arm-T record's
  `loop.sites[]` carries `route` (`declare` or `re-ask`) beside its
  `null_class`, and `loop.routes` counts them.
- **Source:** Calvin M0-Go WP-7a, 2026-09-11 (`adapter.null_route`;
  `docs/calvin/calvin-potential.md` §2.2).

### C-107 — A declaration outside the write partition is placed and recorded, never refused

- **Cannot tell you:** that a declaration the NULL round-trip placed
  stays inside the unit's write partition. The declaration hole offers
  only the partition's files in the binding directory, and for four of
  WP-6's five keys there were none. An answer that names a new file
  there is placed and recorded `in_partition: false`, as NEW_SYMBOL and
  FREEFORM files already are. The partition is not widened and the file
  is not refused.
- **Because:** **Max's decision, 2026-09-11.** Gold declares the name
  outside the partition at 10 of WP-6's 11 NULL sites: new files under
  `rules/` where the partition is `main.go` alone. Refusing them would
  leave 10 of the 11 unclosable.
- **Bites at:** reading arm T's write partition as a write scope (C-38
  is the enforced cut for `hobbes run`, not for arm T). A T diff can
  touch files the template did not assign.
- **You find out:** **surfaced** — each site in `loop.sites[]` carries
  the placed `file` and `in_partition`; the grounding's `edits` and
  `files` rows carry `in_partition`, and its `outside_partition` counts
  the edits outside.
- **Source:** Calvin M0-Go WP-7a, 2026-09-11 (the report's partition
  reading; Max's decision the same day).

### C-108 — A declaration's directory is not checked for a non-Go name or an `after_symbol` placement

- **Cannot tell you:** that a declaration landed in the directory its
  call site binds in, in two cases. The first is a NULL with no `scope`
  (a Python or TS/JS name; grounder v1 sets `scope` for Go only). The
  second is an answer placed by `after_symbol`. The validator checks
  for a file in the binding directory only for a Go name placed by file
  or region.
- **Because:** `scope` is Go's package directory, plus the type for a
  typed receiver, read by rule 1's resolution; Python and TS/JS have no
  such reading in grounder v1. An `after_symbol` placement is
  positioned by the symbol, and the validator does not derive that
  symbol's file (`holes.py`'s declaration check).
- **Bites at:** a declaration in a directory the call does not reach.
  For a Go name the re-grounding still decides whether the call binds;
  what is skipped is the check that would have asked again before
  placing. None of WP-7a's replayed sites took either path.
- **You find out:** *partial* — the pieces are on rows but no row says
  the check was skipped: each site in `loop.sites[]` records the placed
  `file`, the declaration hole records `constraints.declares.dir` (null
  for a non-Go name), and each grounding edit carries its `placement`.
- **Source:** Calvin M0-Go WP-7a, 2026-09-11 (the report's third
  constraint draft).

