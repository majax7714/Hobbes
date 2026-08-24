# ADR-053 — Two honesty fields in `graph.json`: the verification base and the classes a lane can report

**Date:** 2026-08-21
**Status:** accepted
**Amends:** `docs/hobbes-architecture.md` (§3.4 capture line, §3.7 step 4,
§3.8); `docs/constraints.md` (C-31 unsurfaced → surfaced, C-32 partial →
surfaced)

## Context

Two register entries carried a written candidate fix and no mechanism:

- **C-31** — "supported" is a verified sample, not the language, and
  nothing at ingest said how thin the sample was for the language being
  ingested. §3.8's table is a document, and the register's own rule is
  that a document is not a surfacing. It was one of four `unsurfaced`
  entries (with C-4, C-19, C-20 — those three remain).
- **C-32** — the tail view's classes are observations with boundaries,
  and nothing in the artifact said which classes a given language
  *could* have produced, so a Python tail with no `external-origin`
  read as "no external origins" when it meant "no checker that reports
  origins".

Both fixes were the shallow kind: a pinned table, stamped into the
artifact, read by the consumers that already exist. This session (Max
away, standing instruction: apply the register's easiest candidate fixes)
applied them. C-25's candidate — a per-repo pack disable list — is the
ADR-012 question and was left alone.

## Decision

1. **Both facts ride in `graph.json` as additive fields**, no schema
   bump (the same shape as `packs`, ADR-035 — they change how no
   existing field is read):
   - `tail_classes_available`: per tail-view language present in
     `resolution_coverage`, the classes its providers can report, in
     decision order. Source: `CLASSES_AVAILABLE` in `extract/tail.py`,
     pinned beside the mechanisms that decide it (checker origins are
     tsextract's alone; builtin lists exist for Python and Go;
     `import-binding` is lane A's Python parse; `path-call` needs `::`).
     The suite holds the table against `classify`'s decision tree.
   - `verification_base`: per artifact language, the §3.8 row —
     `{repos, on, depth, note}`. Source: `VERIFICATION_BASE` in
     `extract/verification.py`. **Pinned, not derived**: nothing in a
     repo can compute how many *other* repos Hobbes was verified on. The
     suite parses §3.8 from the architecture and fails when the `on`
     cell and the pinned row differ, so §3.7 step 4 now has teeth: a row
     extended in the document without the code is a red build. A
     language the table does not know is stamped `repos: 0, not
     verified on any repo` — stated, never skipped.

2. **One table, three consumers, no second copy.** The ingest summary
   (`hobbes ingest`), the surface (`/api/overview` passes
   `verification_base` through raw; the language badges render
   `go · 1 repo`, badge single-repo and unverified rows in the stale
   colour, and carry the row as tooltip), and `list_blind_spots` all
   read the artifact. The Go side keeps no table of its own — it prints
   what the artifact carries and nothing when an older artifact carries
   neither field (tested).

3. **The blind-spots line is scoped.** Under a sub-scope,
   `list_blind_spots` prints verification rows only for languages with
   detected call sites there; at `.` it prints every language the
   artifact lists, call sites or not (hcl has none). The existing
   scope test caught the unscoped first cut.

4. **Register wording.** Both entries move to `surfaced`, and each keeps
   what is *still* conceded as its content: C-31 — the surfacing says
   how thin the base is and cannot say what the base missed; C-32 — the
   asymmetry is now legible, not narrower.

## Consequences

- Every ingest prints two new lines under the language list (the base,
  plus one line per single-repo/unverified language) and one per
  language under the capture line. The summary is longer and says less
  that is false by omission.
- Adding a language now touches `VERIFICATION_BASE` in the same commit
  as §3.8 (§3.7 step 4 amended). Widening a provider's tail vocabulary
  touches `CLASSES_AVAILABLE`, or the tail tests fail.
- Pre-ADR-053 artifacts lack both fields; every consumer treats absence
  as "not stated" rather than as a claim.

## Verified

Dogfood ingest: `verification base: go 1 repo, hcl 2 repos, javascript
3 repos, python 3 repos, rust 1 repo, typescript 3 repos`, with go and
rust spelled out; capture lines name e.g. `python: nested-decl,
external-origin, path-call` as unreportable. `/api/overview` on the
dogfood repo returns the six rows. 703 pytest (+15), Go `./...` green
(+1 blind-spots test, overview test extended), 52 vitest; SPA and
`hobbes-web`/`hobbes-proxy` (static + sandbox copy) rebuilt.
