# ADR-186 — A reviewed ref reads the checkout's dependency trees

**Date:** 2026-10-29 · **Status:** accepted (Max, 2026-10-29: "good for the recommended routes": register a
C-n and have the review use the checkout's installed dependencies at both ends) · **Owner:** Max ·
**Source:** the tests for the opencode fork (`currently-open.md`), C-198.

## Context

`hobbes review` and `hobbes diff` extract each end of a range from `git archive` in a scratch directory
(`graphdiff.extract_all_at_ref`, ADR-009). An archive holds only tracked files, so neither end had a
`node_modules` or a Python virtual environment. `hobbes ingest` reads the checkout, which has both.

In the opencode fork, a workspace package is a relative symlink inside `node_modules`
(`packages/tui/node_modules/@opencode/client -> ../../../client`), so every cross-package import resolves
through it. Without it the review's graph had fewer edges and its tests reached fewer modules than the
graph the knowledge tools serve. Measured on `main` (`1f93eb1`): 18 of ADR-185's 222 "lost every guard"
modules are reached by a TUI test in `ingest`'s graph and by none in the archive's. `tests_guarding` said
guarded; the review said lost. Nothing named the difference.

What was measured, each against `ingest` at the same commit (`2ca4260`):
- **Archive, nothing linked:** 0 of the 18 reached.
- **Each `node_modules` symlinked whole:** 14 of 18. A workspace link then resolves to the checkout's
  copy of the package, outside the scratch root, and is dropped.
- **Mirrored one level (symlinks copied, real directories linked absolute), `.venv` linked:** test reach
  identical for all 5,812 tests, Python identical; but 4 module edges, 1 tier and 568 TS files' resolution
  counts differ, systematically (a second run agrees with the first). Lane B runs in the container
  (ADR-092), where an absolute link into the checkout dangles.
- **Hardlinked into a scratch on the checkout's filesystem, venvs linked:** identical to `ingest` in test
  reach, nodes, module and symbol edges, tiers and dependency coverage; one `bench` file's resolution
  counts differ, and two runs of the same archive differ in the same way (two `bench` files). Linking
  took 1.6 s for 25 `node_modules` trees (63k files).

## Decision

1. **The scratch sits on the checkout's filesystem:** `<repo>/.hobbes/tmp/`, removed afterwards with any
   directory the extraction created for it. Hardlinks cannot cross filesystems, and `/tmp` is often
   tmpfs.
2. **Each end gets the checkout's dependency trees.** For every directory the ref's tree has, a
   `node_modules` in the same place in the checkout is hardlinked in (directories made, files linked,
   symlinks copied as they are), and so is a `.venv` or `venv` that holds a `pyvenv.cfg` (the marker
   `find_venv` reads). Nothing is copied. A tree the ref already holds is left alone.
3. **A link that fails is said, and that end reads without it.** It fails toward drawing less: the end is
   extracted as before for that directory, never with a half-linked tree.
4. **It is said where the user is standing.** `hobbes review` and `hobbes diff` print what each end read
   and that both read today's install (C-198); `review --json` carries the list as `environments`.

## Consequences

- The review's coverage delta and `tests_guarding` agree on this repo; the 18 leave ADR-185's list.
- **Both ends read the install the checkout has now, not the one each ref declared.** A range that
  changes a dependency is reviewed with the head's (or a stale) install at both ends. Registered as
  C-198's residual, with where it bites.
- A dependency tree inside the repo of another shape (a vendored directory, a Go or Cargo cache placed
  in the repo) is not carried: C-198.
- CI's `graph` job installs no fork dependencies, so its ingest and its review both read the fork without
  them; they agree with each other, and the record changes nothing there.
- Version: the review and the diff draw and say something new, so this is a patch (0.3.6-beta).
