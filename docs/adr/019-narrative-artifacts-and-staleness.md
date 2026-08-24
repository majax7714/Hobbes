# ADR 019: Narrative artifact schema and blob-level staleness

Date: 2026-08-11
Status: accepted

## Context

M5 is the narrative pass (architecture §3.2): module docs, test-behavior
one-liners, and inferred invariants, every claim pinned `file:line @ SHA`
(P3), with stale-badge computation (§3.3) and incremental regeneration.
The architecture fixes *where* generated docs live (§10: `derived/` is
gitignored pipeline output) but not their shape, and says staleness is
"source SHA no longer matches" without saying at what granularity. A
repo-HEAD match would mark *every* doc stale on *any* commit — useless
as a badge, and it couldn't satisfy the M5 exit criterion that an edit
flips "the right" badge.

## Decision

Narrative artifacts live under `.hobbes/derived/docs/`:

- `modules/<module-id>.json` — one per module node: `purpose` (one
  claim), `responsibilities` (claims), `gotchas` (claims, may be empty).
  A **claim** is `{"text": …, "pins": [{"path": …, "line": …}, …]}` with
  at least one pin; a pin cites a 1-based line in a repo file.
- `tests/<test-module-id>.json` — one per test *file* (grouped per
  module, §3.2): `behaviors`, one `{"test": <pytest id>, "text": …,
  "pins": […]}` per test in the file.
- `invariants.inferred.yaml` — inferred invariants in the §10 record
  shape (`id` prefixed `INF-`, `statement`, `scope`,
  `status: inferred`, `evidence` pins, optional `guarded_by`). YAML so
  a confirmed record can be hand-moved into the versioned
  `.hobbes/invariants/` unchanged (adding a `compile:` target is M8's
  concern). **Inferred output never writes to the versioned directory**
  — confirmation is Max moving the record, nothing less.

Every artifact stamps the repo `{sha, dirty}` at generation (ADR-006
stamp) **plus a `sources` list: the git blob SHA of every file the
artifact cites** (its subject file and every pinned path), computed via
`git hash-object` on the working tree.

**Staleness is per-artifact, blob-level:** an artifact is stale iff any
source file's current working-tree blob differs from the stamped blob
(or the file is gone). Fresh artifacts are skipped on regeneration;
`--all` overrides.

This deviates from the build plan's "only changed graph nodes" trigger,
deliberately: blob change is a superset of graph-node change, and the
extra sensitivity is correct for docs — a comment-only edit moves line
numbers, invalidating pins, while leaving the graph untouched. Blob
comparison also needs no git history, so an *uncommitted* edit flips
the badge immediately (which is exactly what the M5 exit check does).

Pins are validated before an artifact is written: path is
repo-relative with no traversal, the file exists, the line is within
the file. Invalid output from the cartographer is rejected (ADR-020
handles retry), never written.

## Alternatives considered

- **Repo-HEAD staleness** — every doc stale on every commit; rejected
  above.
- **Graph-diff-driven regeneration queue** (§3.3's sketch) — needs the
  base graph retained per artifact and misses line drift from
  comment/whitespace edits. Blob stamps are simpler and stricter; the
  graph-diff queue can layer on later if blob sensitivity proves too
  chatty for quota.
- **Markdown docs with a sidecar pin index** — friendlier to read raw,
  but two files that can disagree; the UI (M7) and `get_module_doc`
  render from JSON anyway.
- **Committing docs under `.hobbes/invariants/` directly as
  `inferred`** — blurs the one line §10 draws: the versioned dirs are
  hand-reviewed. Inert-until-confirmed stays physical, not just a
  status field.

## Consequences

- `hobbes docs status` can compute every badge from the artifact alone
  plus `git hash-object` — no history walks, works mid-edit.
- Blob-level stamps make incremental narration cheap and safe: only
  touched modules burn quota on refresh.
- Line-number drift can mark a doc stale whose sentences are still
  true; that is the intended trade (a pin that points at the wrong
  line is a false claim even if the prose holds).
- The narrative auditor (§9, later) gets exact inputs: each claim's
  text, pins, and the blobs they were made against.
