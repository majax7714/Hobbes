# Workstreams — the backlog grouped for assignment

**Written 2026-08-24.** Hobbes is now a group project, and this file is
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
   — **built, not yet validated**.
3. **Experiments are parked.** The next run, on Max's explicit go, is
   the 7B validation of ADR-085 (W3 below) — a demonstration that the
   Hobbes machinery works end to end, judged on its own behavior
   (requirements written, coverage held, plan errors at plan cost),
   not on task solve rate.
4. Current work is cleaning, polishing, and verifying — W0.

---

## W0 — Presentation, doc currency, and verification

*The repo as a thing other people read. Mostly discipline, one real
build item.*

- **CI, for real.** The docs now say honestly that no CI exists. The
  shape is already named (`README`): `hobbes ingest && hobbes lanes &&
  hobbes review $BASE..HEAD` plus the five test suites. This is also
  the first execution of the compiled invariant configs — C-19 says two
  of the four emitters have never run, and ADR-039's checker found an
  emitter bug the first time one did.
- **Recurring drift audit.** The 2026-08-24 pass fixed 19 stale claims
  in the running architecture; the rule (ADR-033, §9) only works if
  someone re-runs the check. Cheap, periodic, assignable to anyone.
- **Extraction evidence upkeep.** `extraction-evidence.md` gets a dated
  entry per test session, `Verified:` line mandatory (P11).

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
- **`bench-rust` pack for criterion benches** — pack territory, parked
  rather than half-detected.
- **Cache hygiene** — a `hobbes cache` subcommand sweeping
  `~/.hobbes/cache/npm` and keeping the Rust stage's `target/` across
  ingests. Opens when sizes hurt.
- **Oracle-lane findings for the Go join (O4, 2026-08-25; evidence in
  `oracle-cells/dagger-go-2026-08-25.md`).** (a) **A type conversion
  is drawn as a call** — `dagger.JSON("0")` → `calls` to `type JSON`;
  40 of 40 contradictions across dagger's 19 modules; the join should
  refuse a `calls` edge whose target is a `type` (emit `uses`, or a
  `converts` edge). (b) **Chain continuations are not sites** — a
  call on its own line of a multi-line method chain has no
  tree-sitter site and no edge, and the capture number cannot see it.
  (c) A call on an assignment's left side is drawn as `uses`.
  (d) Method expressions `(*T).M(&x, …)` and generic instantiation
  calls `F[T](…)` draw no edge. (e) C-59: self-calls dropped by
  design. Each has an oracle cell that reruns in minutes.
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
  2026-08-25, O1–O3 done.** Precision-against-oracle and recall for the
  call graph against Go RTA / `tsc` (phase 1) and Python traces / Rust
  MIR (phase 2). Next: O4 dagger (Go, per module), O5 optional (dagger TS).
  O2's honest misses are C-58; its surfacing (a `dispatch` tail
  class) is W1 work when named. Spends no GPU.
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
