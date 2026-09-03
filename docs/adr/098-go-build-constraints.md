# ADR-098 — Go build constraints: the fallback resolves by the caller's configuration or abstains; the index is one configuration's

**Date:** 2026-09-02 · **Status:** accepted — built, tested, quic-go re-ingested and lane-clean on the shape · **Owner:** Max · **Source:** the four-repo extraction test of 2026-09-02 (BUILDLOG): agent C's quic-go cell, `hobbes lanes` exit 1 with 12 disagreements on build-tag alternates and 2 wrong syntactic edges; Max: "fix build tag and flag rest in constraints"

Amends the architecture's **§3.1** (a Go rule) and **§3.4** (a tail
class). Registers **C-71** (`docs/constraints/extraction-go.md`). The
nine other findings of the same test are registered, not fixed:
C-72–C-80.

## Context

`gosource._call_fallback` — lane A's Go resolver of record for the
sites lane B does not answer (ADR-031) — was written on the premise
that *a top-level name is unique within its package*, and kept one
declaration per `(directory, name)`: the first file iterated. The
premise is false twice over. **Build constraints** (`//go:build linux`,
a `_windows.go` suffix) let one package declare one name in several
mutually exclusive files: quic-go's `setDF` lives in
`sys_conn_df_{linux,darwin,windows}.go` and a `!linux && !windows &&
!darwin` fourth; `newConn` in three; `isECNEnabled` in three. And the
**external test package** (`package p_test`) shares the directory and
may reuse a name. The fallback then reported certainty it did not have:
`sys_conn_df_darwin_test.go` (`darwin`) calling `setDF` was drawn to
`sys_conn_df.go` (`!darwin`); `sys_conn_windows_test.go` to
`sys_conn_no_oob.go` (`!windows`). Two wrong syntactic edges, and
twelve lane disagreements where lane B (indexing on linux) picked the
linux file and lane A the first.

A second fact came with it. **scip-go loads one configuration** — the
box it runs on, which is the image's linux and its pinned Go — so a
file whose constraint excludes it from that configuration gets no
semantic occurrence at all. Eight of quic-go's files
(`sys_conn_df_darwin.go`, `sys_conn_windows.go`, …) showed `resolved
0` in their coverage rows with nothing saying why, and nothing in
`graph.json` said the semantic graph is one configuration's. Java
registers exactly this as C-67 (the one-configuration graph); Go had
no entry.

## Decision

1. **Declarations are kept per `(directory, name)` as a list**, each
   carrying its file's package and `build_constraint`. A bare call
   considers only its own package's declarations (`p_test` is another
   package); a qualified call never the `_test` package's (nothing can
   import it).
2. **`GoFile.build_constraint` is a comparable key, not an evaluation**:
   the `//go:build` expression as written (whitespace-normalised — the
   toolchain's own canonical form) and the GOOS / GOARCH the filename
   suffix implies, joined. Equal keys are compiled together or not at
   all. Evaluating the expression against a target would be *choosing*
   a configuration, which is lane B's job.
3. **Where more than one declaration remains, the call resolves only if
   exactly one declaration's key equals the caller's**; otherwise the
   fallback **abstains** and the tail names the site `build-tag-set`
   (a new class, available for Go, in the C-32 table). This is ADR-096's
   overload rule in Go's shape: a guessed file is a false edge and a
   false disagreement. A sole declaration resolves regardless of
   constraints, as before.
4. **C-71's surfacing**: after coverage rows exist, and only when lane B
   answered somewhere in the Go zone, one `scip-go` degradation record
   per package directory names the constrained files that got no
   semantic resolution and states that the index is one
   configuration's. No record when lane B never ran — that is C-8's.

## Consequences

- quic-go re-ingested: the two wrong syntactic edges are replaced by
  the right ones (`sys_conn_df_darwin_test.TestIPFragmentation →
  sys_conn_df_darwin.setDF`, `sys_conn_windows_test.TestWindowsConn →
  sys_conn_windows.newConn`); every other edge identical; `hobbes
  lanes` goes from 29 disagreements to **17, all C-70's same-line
  shape** (`String()` ×15, `Append`, `Len`); the new record lists the
  eight dark files. `build-tag-set` counts 0 sites there, because every
  abstained site is one lane B resolved (the caller is unconstrained,
  so it is in the configuration) — the class appears where lane B is
  off or the caller is itself dark.
- The graph remains one configuration's. What a `darwin`-only body
  calls is lane A's floor; what it is called *by* through a name the
  linux build also declares is answered for linux. C-71 says so and
  names the candidate lift (a per-configuration index, or `GOOS`
  passes, priced as N× the index).
- The `_test`-package split removes a silent wrong-file case nobody had
  measured (a name declared in both `p` and `p_test`).
- `hobbes lanes` still exits 1 on quic-go: the C-70 shape is a
  registered limit that the self-test reports as a disagreement by
  design. Whether CI should fail on a registered limit is open (noted
  under C-70), not decided here.

## Not done

The oracle regrade of quic-go is recorded in the BUILDLOG if it
finished on this box (the RTA over quic-go's dependency closure is
heavy); the fix is validated by lane agreement and the edge diff
regardless. The one-configuration limit itself is not lifted.
