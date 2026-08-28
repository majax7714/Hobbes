# Narrative, invariants, and review

*Part of the constraint register — see [`README.md`](README.md) for how to read an entry, the surfacing statuses, and the debt summary.*

### C-17 — Narrative claims are pinned, not proven
- **Cannot tell you:** that a module doc's sentence is true — only which
  line it was written from, at which SHA.
- **Because:** narrative is LLM-written over the deterministic skeleton
  (P5). Pins make a claim checkable by a human; they do not check it.
- **Bites at:** the Docs tab and `get_module_doc`.
- **You find out:** **surfaced** — every claim carries `{text, pins}` and
  the UI resolves a pin to its source line, so disbelief is one click.
  Staleness badges on SHA drift.
- **Source:** ADR-019.

### C-19 — Two of the four compiled CI configs have never been executed (semgrep runs in CI since ADR-095)
- **Cannot tell you:** that a generated dependency-cruiser config or
  Rego policy actually runs. **import-linter left this list at V2.M6**
  (ADR-039): the agreement suite runs `lint-imports` over generated
  configs on every test run, and the first real execution found a real
  emitter bug — unmatched ignore pairs failed a clean repo. **semgrep
  left it 2026-08-16**: a dev dependency now, with the same treatment —
  a violating tree fails, a clean one passes, path exclusions actually
  exclude, and the dogfood repo's own I-5 rule runs against the real
  `narrate/` package on every test run (so a new write path in
  `narrate/` fails the suite before it fails a reviewer). The semgrep
  emitter survived its first execution clean, which is worth recording
  precisely because import-linter's did not: the argument for executing
  the remaining two stands on the one bug found, not on bugs being
  everywhere.
- **Because:** compilation is pure text generation by design (no target
  toolchain needed), and dependency-cruiser and conftest are not
  installed here. Those two emitters are asserted against documented
  formats only.
- **Bites at:** `hobbes invariants compile` output for dep-cruiser and
  rego, the first time anyone runs them in real CI.
- **You find out:** **unsurfaced** for those two. The files look
  finished. **Since ADR-095 (2026-08-28)** `scripts/ci-graph.sh`
  compiles and *executes every emitted config* on each push — the
  semgrep rule (I-5) has run in CI; a confirmed record compiling to
  dep-cruiser or Rego would fail the job until the tool is on the
  runner, which is where a user would meet it. No such record exists in
  this repo, so the two emitters remain unexercised, not silently passed.
- **Source:** M8, `future_additions.md`; narrowed at V2.M6, 2026-08-16,
  and ADR-095.

### C-20 — Decisions do not survive a fresh clone
- **Cannot tell you:** on a new machine or a re-clone, that you already
  approved an invariant or confirmed a policy. The whole queue asks again.
- **Because:** ADR-012 gitignores all of `.hobbes/` in target repos, so
  the ledger, invariants and policies are per-clone, per-machine.
- **Bites at:** `hobbes up`'s "set once, holds until you change it"
  promise, which holds within a workspace and silently does not across
  them.
- **You find out:** **unsurfaced.** Re-asking looks like a first run.
- **Source:** ADR-026, confirmed as a known limitation at review.

### C-21 — Narration re-proposes invariants that are already confirmed
- **Cannot tell you:** that an inferred invariant is a reworded duplicate
  of a record you settled months ago — decisions key on a content hash of
  (statement, scope), so a rewording does not match.
- **Because:** the inference unit is told about the repo but not about
  `.hobbes/invariants/`.
- **Bites at:** originally filed as a signal-to-noise cost — all six of this
  repo's inferred records correspond 1:1 to I-1..I-6 and none match by key.
  **The observed cost is worse than that, and the evidence is now in.**
- **Observed 2026-08-15 — a duplicate was approved carrying a claim its
  original had been corrected to remove.** Promoting from the inferred set
  through the surface produced **I-9**, whose statement ends "all other
  pushes escalate". That is false: `.hobbes/policies/repo.policy` denies
  `git push*` outright. It is false in *exactly* the way the M5 inferred
  wording of I-3 was false, which the M8 promotion caught and rewrote —
  I-3's file still carries the note explaining why. Narration re-proposed
  the uncorrected text, the queue could not show that a corrected record
  already existed, and the approval versioned the false claim on a record
  Hobbes will now compile and check against.
- **You find out:** **surfaced** (2026-08-16, ADR-042) — the fix the
  entry named, built where it named it: each pending proposal arrives
  with its nearest confirmed record when the statement overlap crosses a
  deterministic threshold (word-set Jaccard, no model), rendered as a
  "possible restatement of I-n" banner carrying the confirmed prose and
  the instruction to read it before approving. The I-9/I-3 pair — the
  observed failure — is the pinned test case: the reworded proposal
  names I-3 beside itself, an unrelated proposal names nothing, and a
  retired record is history, not a neighbour. The *constraint* stands:
  narration still does not know about `.hobbes/invariants/` and still
  re-proposes; what changed is that the reviewer now decides while
  looking at the record being reworded.
- **Honest residue:** the neighbour is lexical. A restatement sharing no
  vocabulary with its original scores below the threshold and arrives
  bare — the mechanism catches rewords, not paraphrases, and says so
  here rather than pretending otherwise.
- **Source:** ADR-026, `future_additions.md`. Instance recorded
  2026-08-15; surfaced by ADR-042 (2026-08-16).

---

## Lifted constraints in this segment

A lift is a technique, and the technique — not the celebration — is what
these entries document. Each keeps its number, states the limit as it
stood, the exact mechanism that lifted it, and the **residual edge
cases**: inputs the technique does not classify, where the old concession
quietly survives. When a residual case turns out to bite, it becomes a
new active entry and the two cross-reference. Field key: `README.md`,
"How to read a lifted entry".

### C-18 — Soft invariant verdicts judged the delta, not the source — *lifted at V2.M6*
- **Was:** soft verdicts ran through the tool-less ADR-020 runner, so a
  reviewer session judged from the architecture delta and a changed-file
  list, not the files — honest but shallow, and the M8 exit-check
  sessions said so unprompted.
- **Lifted by — the technique:** ADR-039 — `--soft` runs each in-scope
  soft invariant in the M4 reviewer sandbox: worktree mounted read-only
  at the review's head ref (`hobbes-session --ref`, added for this), the
  knowledge tools, and the range's diff hunks in the prompt. A missing
  sandbox is an **error recorded on the answer**, never a silent fallback
  to the delta prompt — that fallback would have quietly recreated this
  entry, which is why the technique forbids it by construction.
- **Residual edge cases:** the technique needs podman, the session image,
  and quota; where any is absent the verdict is an error, not a shallower
  judgment — the error path *is* the surfacing. And a source-based
  verdict is still an LLM's reading of real files: better evidence, not
  proof (C-17's distinction applies to it unchanged).
- **Source:** M8, `future_additions.md`; lifted at V2.M6 (ADR-039).
