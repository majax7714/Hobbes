# Workstreams — the backlog grouped for assignment

**Written 2026-08-24; sequencing and W0 refreshed 2026-08-28.** Hobbes is now a group project, and this file is
the lead's assignment map: the parked backlog
([`future_additions.md`](future_additions.md)) and the open register debt
([`constraints/README.md`](constraints/README.md)) grouped into workstreams a person
can own. It **names no new work and un-parks nothing** — every item
cites the entry that parks it, and the standing rule holds: a parked
item opens when Max names it. Sequencing context is
[`session-handoff.md`](session-handoff.md); the register and
`future_additions.md` stay the sources of truth for each item's detail.

**Where the project stands (the sequencing this file assumes):**

1. v1 (M0–M8) and v2 (V2.M0–M7) are complete and reviewed. Extraction
   is accurate and load-bearing — do not re-litigate it.
2. The derivation programme is built (D1/D2 + the benchmark harness);
   its live runs produced method corrections, the contamination finding
   (C-39), P12, and the requirement-decomposer restructure (ADR-084/085)
   — **validated once on the 7B (2026-08-24)**; the eight harness
   defects that run registered are all fixed (ADR-091, ADR-093).
3. **Experiments are parked.** The next run, on Max's explicit go, is
   the removal A/B re-run on the 7B (W3 below) — un-confounded on the
   D5 axis now, still needing an n that splits O4's planner variance.
4. **Containment (ADR-092) is built** in all four phases and reviewed;
   the knowledge proxy runs from the image (ADR-094). Every cell from
   here runs contained; earlier cells are host-run records (P11).
5. The oracle lane's seven-cell loop is triaged (every compiler-graded
   cell at 100%); the drift audit was re-run 2026-08-28 (41 fixes).
6. CI exists (ADR-095, 2026-08-28). Current work is W0's remaining
   discipline items and collaborator onboarding.

---

## W0 — Presentation, doc currency, and verification

*The repo as a thing other people read. Mostly discipline, one real
build item.*

- ~~**CI, for real.**~~ — **built 2026-08-28 (ADR-095)**:
  `.github/workflows/ci.yml` runs the five suites as four jobs plus the
  graph shape (`scripts/ci-graph.sh <base>`: image build → ingest →
  containment stamp → lanes → every compiled invariant checker → review
  → `lane_b` pytest). Validated on the development box only; **the first
  GitHub run is Max's to observe** when he publishes — rootless podman
  under the runner user and the image's rustup download are the two
  things that can differ there. C-19: semgrep now executes in CI;
  dep-cruiser and Rego stay unexercised until a record compiles to them.
- **Fix the one deselected test.**
  `test_venv_environment_lists_the_venvs_own_distributions` (`lane_b`)
  fails under containment because its fake venv symlinks the suite's
  interpreter and answers `{pip}`; `ci-graph.sh` deselects it by name.
  The fix is a real venv in the fixture (`python -m venv` + one
  installed distribution) — small, and it removes the only permanent
  exclusion in CI.
- **Registry-pulled image.** The graph job builds the image every run
  (~4 min). Pull-by-digest from a registry when that starts to hurt;
  the digest becomes part of what a cell record pins.
- **Recurring drift audit.** Re-run 2026-08-28 (41 fixes, one regrade,
  a red pin caught — BUILDLOG). The rule (ADR-033, §9) only works if
  someone re-runs the check; cheap, periodic, assignable to anyone.
  CI now catches the suite counts and the lane agreement; prose claims
  are still a person's job.
- **Extraction evidence upkeep.** `extraction-evidence.md` gets a dated
  entry per test session, `Verified:` line mandatory (P11). Since
  ADR-092 every entry states `containment` or is a host-run record.
- **Duplicate invariants.** `.hobbes/invariants/` carries three
  near-duplicate pairs (I-1/I-7 tfstate, I-2/I-8 derived-never-committed,
  I-6/I-11 env joins) — one inferred, one written; `list_invariants`
  shows both. Merge each pair or record why both stand.
- **Narrative layer on this repo.** `get_module_doc` answers "run
  `hobbes narrate`" here; the tool is empty on the dogfood repo. Running
  it spends model calls, so it opens when Max clears it.

*Profile: any contributor; good first-week territory.*

## W1 — Extraction & graph core

*The stable subsystem. Self-contained items with measured targets —
the best on-ramp for a new contributor who should learn the codebase.*

- **Cross-language module-id namespacing** — the live parked gap
  (`future_additions.md`, C-15): a colliding `widget.py`/`widget.ts`
  drops a file by pipeline-order accident. Deserves its own ADR;
  "before the fourth language lands, or when a real repo hits it."
- **Decorated-declaration line convention** — tssource emits the
  decorator line, SCIP the name line; 131 of dagger's 258 lane
  disagreements are this one off-by-one. A small tsextract facts pass.
- **jest-globals detection + `package.json bin` entry points** (C-13,
  C-14 residue).
- **Java follow-ups (ADR-096, 2026-08-29):** a Spring route pack; the
  `maven-toolchains-plugin` case (a pom that *requires* a JDK major —
  derive `~/.m2/toolchains.xml` from the image's three, C-67); egress
  narrowing or a registry mirror for `index-java` (C-66); a bytecode
  RTA oracle if the CHA recall number is not sharp enough for C-58's
  Java entry; Kotlin lane A if a mixed repo is ever named.
- **`bench-rust` pack for criterion benches** — pack territory, parked
  rather than half-detected.
- **Cache hygiene** — a `hobbes cache` subcommand sweeping
  `~/.hobbes/cache/npm` and keeping the Rust stage's `target/` across
  ingests. Opens when sizes hurt.
- **Oracle-lane findings for the Go join — fixed 2026-08-25, same
  session** (evidence in `oracle-cells/dagger-go-2026-08-25.md`; the
  `goshapes` fixture holds one of each shape). (a) A type conversion
  drawn as a call — the projection now refuses a `calls` edge whose Go
  target is a `type` (→ `uses`). (b)–(d) were one bug, not three: the
  conversion filter dropped any call whose operand is an expression
  when a *type* of the callee's name exists in the package
  (`m.Discovery.UserConfig()`, `.File(...)` in a chain, `(*Gha).Job`);
  the receiver is now recorded as an expression and cannot be a
  conversion. Generic instantiation calls `F[T](…)`, which the grammar
  parses as conversions, are emitted as candidate sites. (e) C-59
  lifted: self-calls are edges. Still open from O4: the C-58 classes
  (closures, interface dispatch, function values) — a design question,
  not a bug.
- **Directory rollup in `list_blind_spots`** — port `rollup_directories`
  to the Go proxy (same rows, agent-facing altitude).

*Profile: one owner for the Python/tree-sitter side, optionally one for
tsextract/Go ports. Every item has a numeric before/after.*

## W2 — Derivation & agent mapping

*The frontier. Needs the most context (agent-mapping.md, ADR-084/085,
architecture §6–6.1); several items wait on Max's call or on run data.*

- **Change-grain lever 2** (ADR-083) — **resolved 2026-08-24 (ADR-086):
  deferred to the 7B run's strict-coverage records**; the build opens,
  or the item dies, on what those records show.
- **Requirement-level rework selection** — the verifier's
  `requirements:` hand-back is read, not acted on (ADR-085's stated
  deferral).
- **Path-grain write enforcement at the mount** (C-38) — write scope is
  enforced at the cut today; the mount-level guarantee is the upgrade,
  shaped by where agents actually stray in runs.
- **Renegotiation re-pin** — a contract-amendment reflection becomes an
  escalate-tier record whose approval re-pins both manifests.
- **Per-unit metering + loss fitting** (C-35) — tokens per unit are
  still unobserved; fitting the declared weights needs run data.

*Profile: the strongest contributor(s); pairs naturally with W3 since
its evidence comes from runs.*

## W3 — Benchmark & measurement

*The verification programme. Every run is gated by Max's explicit go
and the compute-economics gate (≥15 min evaluation before any >30-min
run; GPU-hours stated first).*

- **The next test (first in line, cheap, 7B):** does the 7B planner
  write `requirements:` under the new brief, and how often does
  `--coverage strict` stop the run — the number ADR-084 asked to
  measure. Then the removal A/B (default vs `--proposal-in-brief`).
  This is the "one more test showing Hobbes functionality regardless
  of task success": the harness demonstrating decomposition, coverage,
  and honest plan errors end to end.
- **The oracle-grading lane (ADR-089, `docs/oracle-grading.md`) — cleared
  2026-08-25, phases 1 and 2 done (O1–O4, O6, O7; the dagger Go root not
  gradeable on this box).** Precision-against-oracle and recall for the
  call graph against Go RTA / `tsc` / the Python interpreter / rustc's
  MIR. Every semantic tier graded so far is 100%; the syntactic
  fallback is priced (C-7: 0/3 Go, 6/6 Python executed, 12/30 Rust);
  the misses are C-58 on every language (closures 70–80%) plus Rust's
  generated-code class. **W1 from phase 2 — done the same day (ADR-090):** the
  fallback's fixture-parameter and `format!`→`fn format` name matches
  (18 wrong syntactic edges, two shapes) are vetoed by ADR-046's
  bindings and by symbol kind; C-58 is surfaced *partial* through the
  `below-floor` tail class. **Open for the lane:** O5 (dagger TS), xarray under
  a trace when a workspace exists, the Go root on a bigger box, Rupta as
  a time-boxed reference lane. Spends no GPU.
- **No-GPU instrumentation** — the replay tools already exist
  (`imperatives_unmentioned` over stored handoffs, `brief_sizes.py`,
  spec re-derivation, the C-56 instruments); assignable today without
  touching compute.
- **A decomposed DeepSWE protocol** — the P12-compliant Hobbes arm on
  the uncontaminated set (the Pier substrate stays the *model + prompt*
  baseline). Design work first, runs later.
- **Report upkeep** — the window row (ADR-068 data, unrolled), seed
  adjustments named by the first probe (C-36 candidates: trailing
  punctuation, generic-word weights), image pre-pulls for evaluation at
  scale.
- **Egress narrowing** (C-41) — restrict a live session's network to
  the model endpoint host.

*Profile: one owner for the harness/protocol, one for instrumentation;
instrumentation items are safe for anyone since they spend no GPU.*

## W4 — Surfaces & review

*Everything a human sees. Independent of W2/W3; good for a TS-inclined
contributor.*

- **Plans, partition records, and bench reports in the web surface** —
  all three are CLI-only today.
- **Blind spots into review verdicts and the surface** — `hobbes
  review` weighing a diff that lands in a low-capture region; the graph
  tab marking where the graph goes quiet (both read
  `resolution_coverage.tail`, which already exists).
- **The lane-disagreement tab** — `hobbes lanes` has no view behind it
  (named gap, architecture §7).
- **PR mode over the interactive graph** (ADR-023's reserved room).
- **Review prose** — the "short list of things discovered late" shape
  Max named as the spec (`future_additions.md`, 2026-08-14).
- **Push transport for the Sessions tab** — only if polling starts to
  hurt.

*Profile: TS/React + some Go (the surface server); the review-prose item
needs Python and taste.*

- **ADR-087 follow-ups (host knowledge tools).** (a) `list_blind_spots`
  (and the other scope-taking tools) should accept `path` as an alias
  for `scope`, or the descriptions should name the argument in the
  first sentence — probe 2 lost the boundary tool to a guessed argument
  name. (b) An MCP input-schema rejection never reaches the flight
  recorder, so an *attempted* tool call is indistinguishable in the log
  from no call; record rejections at the server (ADR-015's "never
  unaudited" applies to refusals too). Both parked until named.

## W5 — Safety & policy

*P10's programme: make the guarantees checkable by the system instead
of by luck.*

- **Typed refusals across subsystems** — `PackRefusal` is the worked
  example; the proxy's exec wrapper, the escalation queue, and the
  narrative runner's retry need the same before the checker can reason
  about them.
- **The P10 checker** — "does a broad handler enclose a path that must
  refuse?" as a graph question, once refusals are types (the V2.M6
  parked ask).
- **Decisions surviving a fresh clone** (C-20) — opt `.hobbes/policies/`
  + `invariants/` into git per repo, the ADR-012-sanctioned path.
- ~~**Aided-mode guardrail**~~ — **built 2026-08-24 (ADR-086)**: an
  aided run is recorded `arm=model+prompt` on every path; the machinery
  refuses the Hobbes label, per P12's own language.

*Profile: careful, adversarial mindset; touches Go and Python.*

---

**Cross-cutting discipline for every stream** (unchanged, and the
non-negotiables for new contributors): one ADR per decision; every
concession a surfaced `C-n` in the same commit; tests with the code
they test; the running architecture amended in the same commit as the
code that moves it; append-only BUILDLOG; commit to `main`, never
`git push` (Max publishes); milestone exits stop for Max's review.
