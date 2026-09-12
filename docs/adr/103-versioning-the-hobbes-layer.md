# ADR-103 — Hobbes is versioned; the experiments are not

**Date:** 2026-09-09 · **Status:** accepted — built (root `VERSION`, the stamp, the four binaries, the held-together test), tagged `v0.1.3-beta` · **Owner:** Max · **Source:** Max, 2026-09-09: "everything outside the Hobbes layer — the experiments largely — are not version changes to Hobbes as much as we'd call internal testing; since their products are versioned I want to version mine"

Amends architecture **§2** (the two-layer statement gains the version
line) and **§8** (status is stated per version from here). Registers
no constraint. Companion: ADR-094 (the `built_by` stamp the version
rides in).

## Context

Every tool in `docs/comparative/field.md` has a version, and every
foreign cell names one (CodeGraphContext 0.6.13, repowise 0.49.0).
Hobbes' own cells name a commit SHA and a checkout — exact, but not a
thing a reader can say out loud, and not a thing that separates the
product from the programme around it. The tree carries both: the
**Hobbes layer** (`go/`, `pipeline/`'s knowledge, derivation, run and
agent packages, `web/`, `tsextract/`, `scip/`, `sandbox/`) and the
**experiments** — the oracle lane, Calvin, the test-time-training
cells, Atlas-0, the benchmark harness — which exist to test the layer
or to test hypotheses about models, and which are recorded as
evidence, never shipped as product (`bench/` is "bench tooling, never
product" in every one of its README lines).

Until now the Python package said `0.0.1`, the web package `0.1.0`,
the Node helpers `0.0.1`, and the Go binaries said nothing. Four
numbers that agree with nothing is worse than none.

## Decision

1. **One version, one file.** The root `VERSION` file holds the
   Hobbes layer's version. Every other copy — `hobbes.__version__`,
   `pipeline/pyproject.toml`, `go/internal/version.Version`, and the
   three `package.json` files with their lockfiles — is a hand-edited
   duplicate that `pipeline/tests/test_version.py` and the Go
   package's own test hold equal to the file. A bump is one commit
   touching all of them, and forgetting one is a red suite, not a
   wrong stamp.
2. **The version is stated where the SHA is.** `built_by` (ADR-094)
   gains `version`, so every artifact says which Hobbes *version* built
   it as well as which commit; `hobbes ingest` prints it on its
   provenance line, every knowledge answer's header repeats it
   (`built by hobbes 0.1.3-beta @ <sha> from <checkout>`), and each of the
   four Go binaries answers `version`. An artifact from before this
   ADR carries no version and the header prints none — never a guess.
3. **What bumps it.** Semantic versioning, and 0.x means the artifact
   schema and the tool surface are not frozen:
   - **patch** — a fix or a lift in the Hobbes layer that changes what
     it draws, refuses or says (a C-n lifted, a wrong edge shape
     vetoed, a converter grain repaired), and documentation of it;
   - **minor** — a capability of the layer: a language, a knowledge
     tool, a schema version, a containment phase, a derivation stage;
   - **major** — reserved: a 1.0 when schema v4's successor is frozen
     and the two-layer statement has held through a release cycle.
4. **What does not bump it.** Anything under `bench/` — a cell
   graded, a foreign tool run, an Atlas-0 world, a Calvin run, a
   training cell — and the experiment records under `docs/`. Those
   are **internal testing**: they measure the layer or a model, and
   their results go in the evidence log, the cell records and the
   hypotheses register at whatever the layer's version was when they
   ran. A finding that leads to a fix bumps the version when the fix
   lands, not when the finding is written. The oracle lane's grade is
   the layer's test, not its release note.
5. **The starting point is 0.1.3-beta, chosen not derived.** Max's
   number: v1 and v2 extraction complete and reviewed, six languages
   compiler-graded, the two-layer statement standing — but the schema
   still moves and nothing is frozen, so 0.x — and **a pre-release
   suffix** (Max, the same evening: "while Hobbes has been proved and
   graded it's still early"). semver's `-beta` sorts before `0.1.3`
   and says exactly that; *beta* rather than *preview* because a
   preview is what precedes grading, and this has been graded. PEP 440
   spells the same version `0.1.3b0`, so `pyproject.toml` carries that
   form and `test_version.py` holds the mapping (`-alpha` → `a0`,
   `-beta` → `b0`, `-preview`/`-rc` → `rc0`); Go and the Node helpers
   take the semver string as is. Leaving beta is its own bump on Max's
   call, not a threshold this ADR sets. The tag `v0.1.3-beta` marks
   this commit; tags are local until the lead publishes them, like
   every push.
6. **`CHANGELOG.md`** at the root, one entry per version, written in
   the same commit as the bump: what changed in the layer, in plain
   words, pointing at the ADRs and constraints. History stays in the
   BUILDLOG; the changelog is the release-grain view a user of a
   versioned tool expects. Its first entry describes what 0.1.3-beta *is*,
   since no prior version exists to diff against.

## Consequences

- `docs/comparative/field.md`'s Hobbes row and every future Hobbes
  cell record can name a version beside the commit, the way the
  foreign rows do. Existing records are not rewritten; they name
  commits, which is exact.
- CLAUDE.md's Status block is stated per version from here; the
  conventions gain one line (bump the version in the same commit as
  the change that earns it, per §3).
- The sandbox image must be rebuilt after a bump for the knowledge
  tools to state it (C-65 already says so of any proxy rebuild).
- A wheel installed outside a checkout now states its version where
  it could only say "no git commit" before.

## Amendment 2026-09-10 (later still) — the number line, and 0.1.9-beta untagged

Max, on the 0.1.9-beta bump: **leave the tag off** (the last tag is
`v0.1.8-beta`; a tag is his call each time, never part of a bump), and
**the version after the next one is 0.11.0-beta, not 0.2.0** — the
minor line the layer moves to is 0.11, chosen, not derived, like the
starting point in §5. Patch bumps continue on the 0.1.x line until
then; a minor bump (§3) lands on 0.11.0-beta.

## Amendment 2026-09-10 (later still, the third) — the 0.1.x line continues; 0.11.0-beta withdrawn

Max, on reading 0.1.10-beta: the conservative line supersedes the
earlier statement — **the layer stays on 0.1.x**, patch by patch
(0.1.10-beta, 0.1.11-beta, …), and 0.11.0-beta is withdrawn. A minor
bump (§3) still lands on 0.2.0-beta when a capability earns it; the
"0.11" statement of the previous amendment no longer holds. Tags remain
his call each time (`v0.1.8-beta` is the last; 0.1.9-beta and
0.1.10-beta untagged). The comparative graphics state the version the
cells were graded on (ADR-102); every Hobbes cell is regraded on
0.1.10-beta so they say one number.

## Amendment 2026-09-12 (the fourth) — 0.2.0-beta: the Calvin harness is the minor

The top-level doc review found the rule and the practice apart: §3
says a capability bumps minor, but the Calvin harness (ADR-107) — the
egress allowlist, Claude Code as the session's doer, `hobbes gate
--map derive`, `hobbes dispatch` and the retention guard — shipped as
patches 0.1.21-beta to 0.1.23-beta. Max: **the harness is enough of a
jump; the layer moves to 0.2.0-beta.** §3 stands as written — a change
to what the layer draws, refuses or says bumps patch, a capability
bumps minor — and patch bumps continue on 0.2.x. The third amendment's
"stays on 0.1.x" held through 0.1.23-beta and no longer does. Tags
remain his call each time: 0.1.9-beta to 0.2.0-beta are untagged, and
the last tag is `v0.1.8-beta`.
