# Extraction — Go

*Part of the constraint register — see [`README.md`](README.md) for how to read an entry, the surfacing statuses, and the debt summary.*

### C-26 — A Go file outside any module gets no semantics
- **Cannot tell you:** where a call goes, for a `.go` file that sits under
  no `go.mod` — a scratch file, a snippet directory, a partially-migrated
  tree.
- **Because:** a Go module is the unit the loader resolves against, so lane
  B runs once per `go.mod` and files under none are skipped rather than
  guessed at. Inventing a `go.mod` for them would invent their dependency
  versions too, and the index would resolve against a module that does not
  exist.
- **Bites at:** those files' call edges, which fall to lane A's fallback —
  correct within their own directory, and blind to anything imported.
- **You find out:** **surfaced** (2026-08-15, the pre-M6 register sweep) —
  one `extraction_errors` record per orphan directory names the files, the
  missing `go.mod`, and the tier their edges fall to. Before that it was
  *partial*: the `syntactic` tier said the answer was lane A's, but nothing
  said why this file in particular got no semantics. The constraint itself
  stands — the files still have no semantics, and inventing a `go.mod`
  would still invent their dependencies — what changed is that the skip is
  visible where a user meets it.
- **Source:** ADR-037, V2.M5; surfaced 2026-08-15.
