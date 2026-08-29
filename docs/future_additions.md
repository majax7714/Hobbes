# Future additions

Reviewed-and-deferred ideas: things flagged in a BUILDLOG entry, looked at
by Max, and consciously parked — with the context needed to pick them up
later. Not a wishlist; everything here was deferred *on purpose*.

**Audit 2026-08-23 (against the tree, not the entries):** 38 top-level
items + 20 sub-items. **13 built** (struck through, with the ADR that did
it), **8 partial**, **29 still parked**, **6 obsolete**. A built item stays
here struck through — the reasoning is the record.

**Not to be confused with `docs/constraints/README.md`.** This file parks deferred
*work*; the constraint register records conceded *information* — what
Hobbes cannot tell a user, and where they find that out (P8, ADR-030). A
deferral that loses information belongs in both, and the entries
cross-reference: per-test JS reach is C-11, cross-zone TS imports C-12,
package.json bin C-14, cross-language namespacing C-15, soft verdicts C-18,
unexecuted CI configs C-19, clone-local decisions C-20, re-inferred
invariants C-21.

**Subsumed by the v2 extraction architecture (2026-08-14) — do not build
these:** ~~*cross-language module-id namespacing* (moniker-keyed node ids
make the `widget.py` / `widget.ts` collision a non-question)~~ — *retracted
2026-08-23: ADR-033 kept path-based ids, so this one is parked, not
subsumed (see its entry and C-15)* —,
*per-test JS reach* (**done at V2.M3** — see below), and *graph-diff
rename detection* (any path-matching heuristic would be built against ids
that V2.M1 replaces). Their entries stay below for the reasoning; the work
does not.

**Also changed by v2:** *per-package tsconfigs / cross-zone imports* now
applies to **both** lanes — `scip-typescript` is run once per zone for the
same reason `ts-morph` is (V2.M3, ADR-032), so an import across two zones
resolves in neither. Registered as **C-12**. *(Narrowed 2026-08-16,
ADR-041: relative and workspace-package-name imports now resolve at
syntactic tier; what remains — aliases into another zone's config — is
surfaced per file rather than silent.)*

- **Graph-diff rename detection** (from M2, deferred 2026-08-10).
  Node identity is by id (ADR-009), so a package rename — or an id
  re-disambiguation like `tests` → `pipeline:tests` — shows as
  remove+add pairs. Path-based matching could pair them. Revisit if the
  pairs read poorly in real PR review (likely surface: M7 UI or M8
  `hobbes review`).

- **`hobbes diff --worktree` mode** (from M2, deferred 2026-08-10).
  Diff currently sees only committed trees (`git archive`, ADR-009). Max
  develops mostly on main, so `base..working-tree` comparisons haven't
  been needed. If they are, extract the live tree with the pure extractor
  instead of an archive — the plumbing already allows it.

- **Test-reach trimming** (from M1, deferred 2026-08-10).
  Static reach through a CLI entry point is broad — every CLI test
  reaches every subcommand handler via `main`. Honest, but noisy. Options
  when it hurts (likely at M5's behavioral index): depth limits,
  entry-point-aware trimming, or fixture-resolution to sharpen pytest
  reach.

- **System narrative — user-journey walkthroughs** (from M5, deferred
  2026-08-11, Max-confirmed). Architecture §3.2 lists data-flow
  walkthroughs of the top 3–5 user journeys alongside the M5 artifacts,
  but the build plan's M5 line and exit criteria don't need them, and
  picking "top journeys" wants either a heuristic (entry points ranked
  by reach?) or a human list. Natural surface: M7's docs tab, where a
  walkthrough would actually render; the ADR-019 claim/pin schema
  already fits it (a walkthrough is an ordered list of pinned claims).

- **Cartographer sessions in the M4 sandbox** (from M5, ADR-020's
  "deferred, not rejected"). v1 narrative units are single-shot
  tool-less `claude -p` calls. If skeleton gaps show up as shallow docs
  (the cartographer can't follow a chain the extractor missed), move
  narrative generation into sandboxed sessions with the role mounts
  ADR-018 already supports (ro source, rw .hobbes/), and flight-log it.

- ~~**Per-package tsconfigs in monorepos**~~ — **built 2026-08-11** (zoning); residue is C-12, narrowed by ADR-041. *Original note — picked up 2026-08-11, same
  day*: kbet's `@/*` aliases un-deferred this immediately; the helper
  now zones files by nearest tsconfig.json, one ts-morph Project per
  zone (see BUILDLOG tenth-session addendum). Remaining edge: imports
  *across* zones don't resolve (separate programs) — revisit if a real
  monorepo has package-to-package imports.

- ~~**Per-test JS reach**~~ — **built 2026-08-15 at V2.M3** (`797c29e`).
  The helper records each case's extent and the join carries ranges, so a
  call is attributed to the `it()` enclosing it; calls outside every case
  (a `beforeEach`, a `describe` body) are shared by the file's cases,
  because that code really does run for each. Constraint **C-11** is
  lifted; its residue was **C-24** (a test that only renders a component
  reached nothing, since JSX was a `uses` edge and reach follows calls) —
  **also lifted, 2026-08-15**: JSX instantiations are call sites in the
  syntax provider, Max-approved with the outliers named in the register.
  Original note follows.

  (from M6, deferred 2026-08-11). JS test reach
  is file-level: every case in a test file shares the file's
  imports+calls closure, because test bodies are anonymous closures,
  not symbols. Per-case reach would need walking each `it()` callback's
  body for its own call set — doable in the helper if the coarseness
  ever hurts the behavioral index or `tests_guarding`.

- **jest-globals detection and package.json bin entry points** (from
  M6, deferred 2026-08-11). Test files using injected globals (no
  framework import) are inventoried as framework `unknown`; a jest
  config file in the repo could sharpen the label. `interfaces.json`
  CLI entry points still come from pyproject only — package.json `bin`
  is the JS analog when a repo needs it.

- **PR mode over the interactive graph** (from M7, deferred
  2026-08-11). ADR-023 leaves room for it: colouring added/removed edges
  over the same view rather than a second graph surface. It waits on M8,
  which is where `hobbes review` computes the diff the surface would
  render — the M2 graph-diff engine already exists in Python, so the
  open question is only whether the Go server shells out to it or M8
  materializes the delta as an artifact.

- **Compound nodes and layout extensions** (from M7, deferred
  2026-08-11). ADR-023 groups packages by colour and filter, not by
  Cytoscape compound nodes — they fight force layouts at 100–200 nodes
  and make edge endpoints ambiguous. Likewise `cytoscape-dagre`/`fcose`
  are better layered layouts than the built-ins, but the
  breadthfirst-on-focus rule covers the case dagre would serve. Revisit
  if a repo arrives with few, large packages, or if focus mode stops
  being enough.

- **Push transport for the Sessions tab** (from M7, deferred
  2026-08-11). The surface polls (ADR-022) because a push transport
  would still need the server to watch the filesystem, or take a watcher
  dependency, to know when to push. If a long session makes the 2.5s
  poll feel laggy or costly, SSE over an fsnotify watch is the upgrade;
  the `?after=` line cursor already gives it an incremental protocol.

- **Symbol-level graph rendering** (from M7, deferred 2026-08-11).
  Both renderers draw modules only (§10: store symbol-level, render
  module-level) — the dogfood repo alone has 537 symbols and 657 call
  edges. The inspector and `who_calls` answer symbol questions today.
  Revisit only if a review question turns out to need the call graph
  drawn rather than queried.

- ~~**Soft verdicts are delta-based, not source-based**~~ — **built 2026-08-15 at V2.M6** (ADR-039; C-18 lifted): `review.py` runs the reviewer sandbox at the head ref with the diff hunks. *Original note (from M8, deferred
  2026-08-11):* The reviewer session for a `soft` invariant runs through
  the ADR-020 tool-less runner, so it judges from the architecture delta
  and the changed-file list rather than from the files themselves — the
  sessions said so unprompted during the M8 exit check. That is honest
  but shallow: "does this change violate the invariant" often needs the
  diff hunks. The fix is the same one ADR-020 already parks — run these
  in the M4 sandbox with a reviewer role, which now has read-only mounts
  and the knowledge tools (M8). Revisit when a soft verdict is wrong in
  a way source access would have caught.

- **The compiled configs are verified by shape, not by execution** (from
  M8, deferred 2026-08-11). None of import-linter, dependency-cruiser,
  semgrep, or conftest is installed on the dev box, which is exactly why
  ADR-024 makes compilation pure text generation. The emitters are
  asserted against the formats' documented shapes; nothing has run
  `lint-imports` over the generated `.ini`. First CI run that executes
  them is the real test, and any mismatch is an emitter fix plus a
  regression case.

- **import-linter `layers` contracts** (from M8, deferred 2026-08-11).
  ADR-024 ships three rule kinds because three records needed them.
  Layered-architecture contracts ("nothing below may import above") are
  the obvious fourth, and import-linter and dependency-cruiser both
  support them natively — but no invariant has wanted one yet, and
  building the emitter first is the speculative abstraction the
  conventions forbid.

- **Cross-language module-id namespacing** (from M8 review, deferred
  2026-08-11, Max-raised). *Relabelled 2026-08-23:* the preamble above
  files this as "subsumed by moniker-keyed ids", but ADR-033 retracted
  that — ids stayed path-based — so this is a **live, parked gap**, not a
  subsumed one; C-15 is its active, surfaced register entry. Language *selection* is already right —
  discovery is by extension, so each language has exactly one parser and
  no parser sees another's files (I-4). What is not right is what
  happens when two layers want the same node id: a repo-root `widget.py`
  and `widget.ts` both derive the id `widget`, and the merge resolves it
  by pipeline order (Python, then HCL, then TS). That is now **loud** —
  the loser is recorded in `extraction_errors` and warned at ingest —
  but the file is still omitted from the graph, which is data loss
  decided by an accident of ordering.

  The principled fix is to namespace the incoming layer's ids on
  collision, the way `discover.py` already disambiguates Python-internal
  clashes into `root:name`. It was deferred because doing it properly
  means rewriting ids across a whole layer's nodes, module edges,
  symbols, symbol edges, tests, and routes — a change to the M6 contract
  that deserves its own ADR rather than a corner of M8. Pick it up when
  a real repo hits the collision, or before the fourth language lands,
  whichever comes first; the extraction_errors record already names
  every case that would have been affected.

- **Decisions do not survive a fresh clone** (from ADR-026, deferred
  2026-08-11, Max-confirmed as a known limitation). ADR-012 gitignores
  the whole `.hobbes/` in target repos, so `.hobbes/decisions.yaml`,
  `.hobbes/invariants/`, and `.hobbes/policies/` are untracked there.
  Every approval, denial, and intent confirmation is therefore *this
  clone on this machine* — recloning, or moving to another box, asks the
  whole queue again. The "set once, holds until you change it" promise
  holds within a workspace and silently does not across them.

  The fix ADR-012 already allows: opt `.hobbes/policies/` and
  `.hobbes/invariants/` (and the ledger) into git per repo, keeping
  `derived/` ignored — the "repos that already track .hobbes/ content"
  path, which this repo uses. That also makes decisions reviewable in a
  PR and shared with collaborators, which may or may not be wanted.
  Deferred until the re-asking actually costs something.

- **Narration re-infers what is already confirmed** (from ADR-026,
  2026-08-11). The inference unit is told about the repo but not about
  `.hobbes/invariants/`, so it happily re-proposes claims that already
  have confirmed records. Before the ledger existed that was invisible;
  now it means the decision queue can offer you something you settled
  months ago in different words.

  It bit the dogfood repo immediately: all six inferred records
  correspond 1:1 to I-1..I-6, but the statements were rewritten during
  promotion (I-3 and I-4 substantially), so no content key matches and
  `hobbes up` asks about all six. Nothing is wrong — the confirmed
  records stand and a fresh repo is unaffected, since it has an empty
  invariants directory — but the queue is noisier than it should be.

  The root fix is in the narrate prompt: pass the confirmed statements
  in and instruct the pass to propose only what they do not already
  cover. Deferred because it spends quota to verify. Until then, denying
  a superseded inferred wording is the accurate verdict — you did reject
  that phrasing in favour of your own, and the ledger records the
  wording it was asked about.

- **The build-session reports are the spec for `hobbes review`'s prose**
  (Max, 2026-08-14). He noted that the stage-by-stage reports these
  sessions produce — what was measured, what surprised, what it means for
  the next decision — are doing by hand exactly what Hobbes is meant to do
  mechanically, and that the *small notes* are the part that carries.

  Worth treating as evidence rather than a compliment: it says the
  concept-level review a human wants is not a diff summary and not a
  verdict table, but **the short list of things that would have been
  discovered late**. Today `hobbes review` (ADR-025) emits delta,
  verdicts, and coverage — accurate, and none of it is that. The ADR-019
  claim/pin schema already fits: a finding is a claim plus the evidence
  that produced it.

  Concretely, the reports that landed were: a measurement that contradicted
  a published number, a design withdrawn because a safer one measured the
  same, and a gate that caught a fixture bug on first run. All three are
  derivable — a metric that moved, a decision reversed, a test that failed
  for a new reason. Revisit when V2.M6's tier-aware verdicts give the
  reviewer something richer to write from.

- ~~**`hobbes up` output is invisible when stdout is not a tty**~~ —
  **fixed 2026-08-14** (`6b2ac65`), before the v2 programme started.
  Line-buffered at `main()` rather than `flush=True` per print, because
  `narrate` prints per unit and had the same bug. Original note follows.

  (2026-08-13). The Python prints are block-buffered, so
  `hobbes up > up.log 2>&1 &` shows only the Go child's lines until the
  process exits — the "decisions needed" list and the "ready to develop"
  banner sit in the buffer for as long as the command blocks, which is
  the whole point of the command. In a terminal it is correct, because
  a tty is line-buffered, so the flow Max actually uses is unaffected.
  The fix is `flush=True` on the prints in `_cmd_up`/`_print_ready` (or
  running the entry point unbuffered). Left alone for now because it
  only bites redirected or supervised runs, which nothing does yet — but
  it will the first time `hobbes up` goes into a unit file or a wrapper
  script.

- ~~**`hobbes-session` cannot clone a repo on another filesystem**~~ —
  **fixed 2026-08-14** (`6b2ac65`): `git clone --local --no-hardlinks`,
  guarded by a test that asserts object link count rather than staging
  two filesystems. Original note follows.

  (2026-08-13). The session worktree is a local `git clone` into
  `~/.hobbes/sessions/<id>/worktree`, and a local clone hardlinks object
  files by default. When the repo and `$HOME` are on different devices
  the clone dies with `failed to create link ...: Invalid cross-device
  link`, which names the symptom and not the cause. Found by pointing a
  dry run at a repo under `/tmp` (tmpfs); a repo under `$HOME` — the
  normal case — is unaffected. `git clone --no-hardlinks` fixes it at
  the cost of a real copy, or the session dir could be placed beside the
  repo instead of under `$HOME`. Worth doing before anyone works out of
  a mounted volume or a ramdisk checkout.

- **Hobbes as an application, not a per-repo command** (proposed by Max
  2026-08-13, paused the same day). Open a folder; start, refresh, or
  continue developing; status from two checks (does Hobbes exist here,
  and is the stamped SHA HEAD) captured while the user chooses the
  action. Full assessment, including what already exists, the ADR-022
  boundary it crosses, the authentication question app mode raises, and
  the three decisions it waits on: **`docs/m9-application-mode.md`**.

  It subsumes the buffering papercut above by deleting the process that
  buffers. It does *not* subsume the clone papercut — that stays a
  one-line fix either way.

- **Hobbes should catch a general mechanism swallowing a specific
  guarantee** (Max's ask at the V2.M4 review, 2026-08-15; the principle is
  **P10**, ADR-036). V2.M4 wrapped every pack in `except Exception` so that
  a failing pack degrades rather than fails the ingest (P6) — and that
  handler swallowed the refusal guarding **I-1**, so
  `ingest --tf-plan prod.tfstate` began *succeeding* with a warning. Both
  mechanisms were right in isolation; the general one won by default.

  It was caught by a test written two milestones earlier about `.tfstate`
  and an exit code — not by Hobbes, which is the point. **Nothing in the
  system detects this class of gap today.**

  The natural home is **V2.M6's unified checker**, because the question is
  a graph question once refusals are a type rather than a message:
  *does a broad handler enclose a path that must refuse?* `PackRefusal`
  makes refusals a type in one subsystem; the general form needs the same
  in the others (the proxy's exec wrapper, the escalation queue, the
  narrative runner's retry) before the checker has anything to reason
  over. Two steps, in order: give every specific guarantee a type, then
  ask the graph which broad handlers dominate one.

  Worth building because the failure mode is invisible by construction —
  the change that causes it is in a different subsystem, made for an
  unrelated and good reason, by someone not thinking about the guarantee
  at all.

- **Criterion benches as test inventory** (from V2.M7, deferred
  2026-08-15). A criterion bench is a plain function registered by
  `criterion_group!` — no attribute marks it, so `cargo-test` inventory
  (which is `#[test]`-family attributes) does not see it. Detecting the
  registration macro is framework knowledge, which is pack territory
  (§3.5): a `bench-rust` pack reading the macro's arguments from the
  lane's recorded call sites, the same way `http-go` reads routes. Parked
  rather than half-detected — a bench that appears in inventory only when
  spelled one way is worse than none appearing.

- **Cache the Rust staging tree's `target/` across ingests** (from
  V2.M7, deferred 2026-08-15). rust-analyzer compiles build scripts and
  proc macros into the stage's `target/` (72 MB on the spike repo), and
  the stage is deleted after every ingest, so every re-ingest pays the
  compile again. §3.6's content-hash cache is the natural shape; the
  crate registry is already user-global and survives. Worth doing when a
  real Rust repo makes ingest latency hurt; not before.

- **Blind spots into review verdicts and the surface** (from ADR-047,
  2026-08-16). `list_blind_spots` serves agents in sessions; two
  consumers do not read it yet. `hobbes review` could weigh a change
  that lands entirely inside a low-capture region — a diff whose files
  sit at 50% resolution deserves a louder verdict than one in a fully
  accounted module, and today nothing connects the two. The web surface
  has no blind-spot rendering: a reviewer reading the graph tab sees
  the captured fraction with nothing marking where the graph goes
  quiet. Parked until either consumer's shape is decided, not because
  the data is missing — both would read the same
  `resolution_coverage.tail` the tool reads.

- ~~**The derivation carries the complement**~~ — **built 2026-08-19 at D1** (ADR-051): `derive/manifests.py` refuses to serialize a manifest without its complement (`ComplementError`), blind-spot-heavy units are human-first, derived policy narrows. *Original note (the ADR-047 contract,
  recorded here so the milestone inherits it):* When per-task derivation
  is built, derived context must include the task-scoped blind-spot
  statement and derived policy must treat unseen regions as
  low-evidence (narrow or escalate, never widen). This is a
  requirement on the milestone, written down before the milestone
  exists — see architecture "Where this is going".

- ~~**The cross-unit moniker join**~~ — **built 2026-08-18** (ADR-049; C-33 lifted): `scipsource.join_cross_unit`. *Original note (C-33's candidate fix, from ADR-048,
  2026-08-18):* Keep the moniker on `external_refs` rows, join externals
  against the merged definitions across a language's indexing units,
  and stage replace/workspace targets beside their consumers. The
  measured prize is dagger-shaped monorepos: root-module calls into an
  in-repo `replace`d SDK are today's dominant semantic miss. It is a
  helper-contract change, and it argues with C-12's deliberate
  no-reconciliation decision for TS zones — the Go/Rust case is
  stronger (explicit unit graph, exact moniker equality), and that
  argument needs its own review before any code.

- **The directory rollup in `list_blind_spots`** (from ADR-048). The
  proxy's blind-spots tool serves worst *files*; the ingest summary now
  rolls the same rows up per directory, which is the altitude an agent
  scoping a task actually works at. The Go side reads the same
  `resolution_coverage` rows — a port of `rollup_directories`, not a
  second computation.

- **Sweep `~/.hobbes/cache/npm`** (from ADR-050). Provisioned dependency
  trees are keyed by lockfile hash and live forever; a repo that churns
  its lockfile leaves a dead tree per revision (~25–200 MB each). Same
  shape as the Rust `target/` caching note above — worth a `hobbes
  cache` subcommand when the sizes start to matter, not before.

- **The decorated-declaration line convention** (from the ADR-050
  retest). Lane A cites a decorated TS method at its declaration start
  (the decorator line); SCIP cites the name line. Both point at the
  same declaration, but `hobbes lanes` compares `file:line`, so every
  dual-resolved call to a decorated method reports as a disagreement —
  131 of dagger's 258, half the report, all noise. The principled fix
  is tssource emitting the name line (SCIP's convention); it is a
  tsextract facts change and deserves its own small pass rather than a
  tolerance bolted onto the checker.

- **The company-shaped derivation workflow** (Max, 2026-08-19, from a
  friend's idea on agentic breakup; the control-flow proposal for the
  unbuilt derivation milestone — reads together with "The derivation
  carries the complement" above). Approach the eventual context-derived
  coding flow the way a software company structures work: the **user
  proposes** (the head boss — intent, already one of the two things
  that need a human); an **orchestrator** builds what the proposal
  actually *is*, under base derived context; **engineers develop a
  build plan**; a **plan reviewer** (the dev-ops analog) validates it;
  engineers adjust or finalize; the work fans out to **per-feature or
  specialized engineers** — fan-out width a function of codebase size —
  each a single-use agent under per-task derived context; and
  everything returns to the **verifier** before it commits. Companies
  solved role decomposition under exactly Hobbes's constraint — no
  single head holds the whole system — so the structure transfers to
  single-use agents whose "head" is a context window.

  Much of the cast already exists in embryo, which is evidence the
  shape is right: the sandbox roles (implementer / reviewer /
  cartographer, ADR-018/M8) are proto-roles with role-shaped mounts and
  policy; `hobbes review` plus the unified checker are the
  deterministic half of the verifier; the escalation queue is the
  boss's approval surface; and ADR-047's contract applies *per role* —
  every role's derived context carries its complement, and the
  verifier's derived policy is the narrowest of all.

  **The hard part is the role taxonomy** — how many roles, which ones,
  what types. Max's proposed method: map a relational system between
  software companies and their roles, if public data exists (it does in
  usable forms — published engineering ladders, org-topology
  literature, job taxonomies). Two notes to carry into that study.
  *The filter is the design work:* companies hold roles that exist for
  human constraints (coordination overhead, careers, throughput) and
  roles that encode a genuine **verification or context boundary**;
  only the second kind should map onto agents, and telling them apart
  is the actual decision. *The org chart should be derived, not
  authored:* Hobbes already refuses authored config wherever the fact
  is derivable (§3.7, no `hobbes.yaml`), and the same instinct says the
  per-task role structure — how many specialists, split along what
  seams — should be computed from the graph (size, structure, the
  change's blast radius). "Depends on the size of the codebase" is that
  requirement, stated plainly. Parked with the derivation milestone;
  deep extraction testing remains the named current work.

- **D2 — what the base left out** (ADR-054, 2026-08-21 — spawning,
  context faults, the partition record, reflections, and branch
  harvest are built; this is the remainder). *Audited 2026-08-23:* **built**
  — the verifier session (ADR-059, `stages.run_verifier`) and the
  generative planner (ADR-059; ADR-084/085 made it the
  requirement-decomposer); **partial** — path-grain enforcement (at the
  cut, ADR-061, not the mount), metering (stage wall + envelope tokens;
  per-unit tokens still unobserved); **still parked** — renegotiation
  re-pin, loss fitting, re-ingest flag, sub-module grain, approval
  marker, plans in the web surface. Original text follows. **Path-grain write
  enforcement** (C-38): bind interior paths rw over a ro worktree, or
  a per-unit overlay, so `write_mounts` becomes a guarantee instead of
  a measured rework term — do it after the first benchmark runs show
  where agents actually stray. **The verifier session**: the role
  exists (ro worktree) and the review runs in-process; a spawned
  verifier with the integration branch and the contracts in its brief
  is the §2 phase-5 agent. **Renegotiation re-pin**: a reflection that
  proposes a contract amendment should become an escalate-tier record
  whose approval re-pins both sides' manifests; today it lands in the
  orchestrator's inbox for a human. **Metering**: tokens and wall time
  per unit — the loss lists them as unobserved; the harness's dual-arm
  accounting (ADR-052) is the natural place. **Loss fitting**: the
  record exists with ADR-051's declared weights; fitting needs runs.
  **Re-ingest on integrate** as an explicit flag, never a default (the
  run states that commits move standing context; it does not move it).
  **A generative planner above the lexical seeds** (C-36): interpret
  prose into seed sets and declared edges, quota-spending and layered
  on top of the deterministic mapping (P5), never inside it — the
  predicted first benchmark friction. Also still parked from D1's own
  review: sub-module partition grain, a change-spec approval marker
  (the decisions ledger is the natural home — for benchmarks the manual
  gate is off by direction), and rendering plans and partition records
  in the web surface.

- **The benchmark harness — what the build left out** (ADR-055,
  2026-08-21; `hobbes bench` is built and unrun). *Audited 2026-08-23:*
  **built** — pure-arm containment (ADR-058, the swebench image), the
  generative seed planner (ADR-059), vLLM on Modal (ADR-057/074);
  **obsolete** — the Claude-Code session image (ADR-056) and `swebench
  --modal` (broken upstream, C-50; eval is local); **partial** — the
  post-cutoff set (DeepSWE via Pier exists but is retracted as Hobbes
  evidence, P12), seed adjustments (dotted suffix done; punctuation and
  generic weights not), evaluation at scale (workers + ADR-065; pulls
  still manual); **still parked** — bench in the web surface, egress
  narrowing (C-41), Daytona. Original text follows. In the order a live
  run needs them: **a session image that runs Claude Code** — glibc
  base, host `claude` mounted ro, credential, a network mode other
  than `none`; the network is an owner decision that contradicts
  architecture text as written ("no route to the network") and takes
  a register entry when made, narrowed to an API-host egress
  allow-list if podman's network stack permits. **Pure-arm
  containment** — it runs on the host with Bash over a benchmark
  checkout; a container reuses the item above. **A post-cutoff
  instance set** — Verified is all pre-2024 (C-39); SWE-rebench or
  SWE-bench-Live. **Seed adjustments the first probe named** (C-36;
  not applied before verdicts exist): resolve dotted
  `package.function` terms by symbol-id suffix (`requests.get` →
  `requests.api.get`); strip trailing punctuation before the
  code-shaped test (`fine:` is prose); weigh generic one-word seeds
  (`data`, `json`) below identifier-shaped ones. **The generative seed
  planner** above the lexical layer (P5, layered never inside).
  **Evaluation at scale** — `--workers` exists; SWE-bench images are
  large and the first pulls are slow. **`hobbes bench` in the web
  surface** — the report is CLI-only, like plans and partition
  records. *(Amended 2026-08-21, ADR-056: the owned runtime removes
  the "image cannot run Claude Code" item for the small-model ladder;
  what remains of it is **egress narrowing** — restrict the live
  session's network to the model endpoint host (C-41) — and **steps
  2–3**: a vLLM app on Modal plus `swebench --modal`, then Daytona as a
  `hobbes-session` backend with the sandbox's mount/env guarantees
  re-expressed and registered, and the pure arm in a Daytona sandbox.)*

- ~~**Task-tailored unit selection — spawn a selected stream, not every
  unit**~~ — **built 2026-08-21/22** (ADR-058 select-then-cap, ADR-064 C-52 unnamed units not spawned, ADR-083 change-grain interiors). *Original note (Max, 2026-08-21, from watching the first 7B run):* Today the
  orchestrator spawns a session for **every** unit the partition
  produces, in contract order, up to the cap (ADR-058's `--max-units`).
  On the first run most spawned units reflected "No changes made" — the
  proposal did not touch them, but they still cost a full session each.
  The direction: **the plan should largely be a stream of *selected*
  units — the ones the task actually reaches — with the cap as a
  ceiling we *may* spawn, not a target we fill.** Selection is the
  impact set doing real work: a unit with no seed-reachable interior,
  or whose contracts the change never crosses, is context to hand a
  neighbour, not a session to run. Open design: the selection signal
  (seed reach into the unit's interior? a nonzero cut the change
  crosses? a declared-edge touch?), whether an unselected unit still
  contributes standing context to its neighbours, and how selection
  interacts with the cap (select first, then cap the selected). This is
  the execution-side twin of D1's partition quality (C-35) and the
  thing that most reduces the harness's per-instance weight below.

  **Measured 2026-08-21 (strict-pipeline run):** on `astropy-13579`,
  **only 2 of ~9 spawned units edited** (U3, U7); the other seven
  stalled out with "no progress" — spurious units with interiors the
  proposal never touches. The discipline (ADR-058 sixth finding) bounds
  each to ~12 turns, but they still cost a session spawn + round-trips
  each, and they are the bulk of the ~20-min harness arm. A first cut
  at selection: **do not spawn a unit whose interior has no
  seed-reachable node** — it entered the plan only through co-change /
  partition merging, not through the change. Full design still open
  (the signal, whether unselected units feed neighbours' context).

- **Re-evaluate the harness if its weight stays this high** (Max,
  2026-08-21). The first 7B run measured the harness arm at ~40–50 min
  on heavy repos (ingest + plan + one session per unit) against ~1 min
  for the pure arm — the harness is almost the entire cost. Max: "if
  the harness is as much weight as it's presenting then we need to
  eventually re-evaluate the harness." Not now — the full run is fine
  and **need not finish**; **the first 10–20 results are the decision
  point, and a drastic outcome (harness ≈ pure, or far worse) could
  force a refocus** of the whole approach, not just a tuning pass.
  Levers already in hand: unit selection (above), the `--max-turns` /
  `--max-units` caps (the run uses 20/10), and re-using ingest across
  arms. A refocus would question the shape itself — whether a
  per-unit-session fan-out is the right execution model for a
  single-issue benchmark task, or whether a leaner derived-context
  single agent is the better arm to measure.

- ~~**The nudge's blind spot: read-only tool looping**~~ — **built** (`agent/loop.py` `--stall-after`, dry-turn and refused-repeat stalls; ADR-066/076). *Original note (observed
  2026-08-21, first 7B run):* The prose-plan nudge (ADR-058) fires only
  when a turn returns **no tool calls**. A 7B unit on `astropy-13579`
  instead looped ~20 turns calling `tests_guarding`/`reflect`
  (read-only) without ever editing — tool calls every turn, so the
  nudge never triggered, and it burned the full `--max-turns` at ~40s a
  round-trip (~14 min for one unproductive unit). Refinement: treat **N
  consecutive turns with no *mutating* tool call** (edit/write/exec) as
  a nudge trigger too, not just zero-tool-call turns; the loop already
  tracks `edited`. Bounded today by the turn cap, but it is most of the
  harness weight on the units that never solve — related to unit
  selection (an unselected unit would not have spawned) and to the
  harness re-evaluation trigger above. Tune from verdicts, not before.


## A window row in `hobbes bench report` (ADR-068, 2026-08-22)

`calls.jsonl` and the envelope's `prompt_tokens_max` / `calls_saturated`
exist per session; the report does not yet roll them up. Add a per-arm
row: calls, calls saturated, share of implement wall spent at the
window, largest prompt. Small; opens when Max names it.

## The ingest itself inside the sandbox image (ADR-094, 2026-08-28)

Max asked for the whole knowledge piece in the sandbox. The proxy went
in (ADR-094); the ingest stayed on the host, with the provenance stamp
(`built_by`) covering the "which code ran" question the incident
raised. Parked, not declined: lane A executes no repo code (P10 gains
nothing); baking the pipeline's source and wheels into the image means
a ~4-minute rebuild per pipeline edit or a dev mount that un-pins it;
lane B's per-step containers would become nested rootless podman or
collapse into one container and lose ADR-092's network-by-phase
separation. **Opens when** a foreign-repo deployment needs the
pipeline pinned too; the shape then is a pinned wheel in the image
plus a nested-podman decision, not a checkout mount.

## Java as the fifth language (2026-08-28)

Max asked, out of interest, what Java and C would cost. The answer is
`docs/java-build-plan.md` — §3.7's checklist elaborated to five
milestones (ADR-096 + spike, lane A, contained `scip-java`, JUnit/Spring
packs, a bytecode CHA/RTA oracle, the evidence row) and the reasons Java
ranks ahead of C. **Opened 2026-08-29** (ADR-096): J.M0–J.M5 built in
one session — see the ADR, `docs/constraints/extraction-java.md` and
the cell records. What stayed parked from the plan: a Spring route
pack (`@GetMapping` et al. as the Flask/FastAPI shape; `@Autowired`
as C-4's injection class), Kotlin (scip-java indexes it under Gradle,
but there is no Kotlin lane A, so it would be references without call
sites — §3.7's rule), a bytecode RTA (SootUp/WALA) if CHA's dispatch
number proves too coarse, and egress narrowing for the one networked
index step (C-66). Also recorded there, because the question came up:
ingest is per language, gated on discovery — a language with no files
in the repo costs one extension walk and nothing else; only the image
build carries every toolchain.
