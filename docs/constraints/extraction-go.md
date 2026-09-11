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

### C-71 — The Go semantic graph is one build configuration's, and lane A abstains where constraints split a name
- **Cannot tell you:** what a file compiled only under another
  configuration (`//go:build darwin`, `_windows.go`, `!go1.25`) calls
  through a name its own package declares several times — nor, for any
  file a constraint excludes from the configuration the index ran on,
  where its calls go at all beyond lane A's floor. The semantic graph
  is **the configuration of the box the index ran on** (the image:
  linux, its pinned Go), presented without a configuration stamp.
- **Because:** scip-go loads the module the way `go build` would on
  its host, so excluded files contribute no occurrence and are never
  resolved; and one package may legally declare one name once per
  mutually exclusive constraint, which the v1 fallback did not know
  ("a top-level name is unique within its package" — first file won;
  quic-go, 2026-09-02: 12 lane disagreements, 2 wrong syntactic edges).
  Since ADR-098 the fallback keys declarations by package and
  `build_constraint` (the `//go:build` line as written plus the
  filename's GOOS/GOARCH), resolves a split name only when exactly one
  declaration shares the caller's key, and otherwise **abstains** —
  evaluating the constraint against a target would be choosing a
  configuration, which is not lane A's to do.
- **Bites at:** platform-split packages (network syscalls, terminal
  handling, filesystem notification), version-gated test files, cgo
  alternates. `who_calls` on a darwin-only helper answers from the
  linux graph; `tests_guarding` on a `_windows_test.go` reaches only
  what lane A's floor drew.
- **You find out:** **surfaced** (2026-09-02, ADR-098): one `scip-go`
  degradation record per package directory names the constrained
  files that got no semantic resolution and says the index is one
  configuration's (quic-go: eight files, on stderr, in
  `extraction_errors`, in `list_blind_spots`); the tail names an
  abstained site `build-tag-set` (*cannot resolve*, in the C-32 table
  for Go); a resolved-by-constraint edge is `syntactic`, as every
  fallback edge is (C-7). What is *not* surfaced: which configuration
  the graph is — no `GOOS/GOARCH` stamp exists — and the sites inside
  a dark file that lane B would have answered differently under its
  own configuration. Candidate lift: index per configuration the
  constraints name (N× the index, unioned with a configuration tag per
  edge), or a `GOOS`/`GOARCH` ingest flag stamped into `graph.json`.
- **Provider:** scip-go 0.2.7 — one configuration per run is the
  tool's shape (`go/packages` loads for the host); an upgrade does not
  lift it, a second run under another `GOOS` would.
- **Source:** the four-repo extraction test of 2026-09-02 (agent C,
  quic-go); ADR-098.

### C-102 — Lane A skips a `var ( … )` group inside a Go function, so its names are not local bindings
- **Cannot tell you:** that a name declared in a parenthesised
  `var ( … )` group inside a Go function is a local. The tail view does
  not class a call through it `local-binding` (ADR-046, C-32), and
  ADR-090's scope veto does not see it.
- **Because:** `gosource._local_bindings` records a function-level
  `var` by reading the `var_spec` children of a `var_declaration`;
  tree-sitter-go wraps a parenthesised group's specs in a
  `var_spec_list`, which the walk does not descend. Parameters, `:=`,
  `range` targets and the one-line `var x T` are recorded.
- **Bites at:** two places, both only where lane B leaves the site
  unresolved or did not run (C-26, C-71). The tail: a call through
  such a name reads `unclassified` (*cannot resolve*) where it is
  *seen, not modelled by design*, so the Go tail reads darker than the
  truth there. Lane A's fallback: a bare call through such a name that
  shares a package-level function's name is not vetoed, so the
  fallback can bind it to that namesake — C-7's wrong-edge shape; not
  measured. Found by reading during the Calvin M0-Go grounder's gold
  run (gitleaks, `peekBuf` at 8a8306288e95). The grounder reads Go
  locals with its own walk, which descends `var_spec_list`, so its
  classes are unaffected.
- **You find out:** *partial* — the site is counted in the tail, never
  dropped, and a fallback edge is `syntactic` (C-7); but the class
  names the wrong reason and nothing names the var group. Candidate
  lift: descend `var_spec_list` in `_local_bindings` (a few lines),
  with a re-ingest, since it moves the tail's counts and the veto's
  reach.
- **Source:** Calvin M0-Go WP-3, 2026-09-11
  (`docs/calvin/calvin-m0-go.md`); ADR-046, ADR-090.
