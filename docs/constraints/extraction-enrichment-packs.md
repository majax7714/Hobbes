# Extraction — enrichment packs

*Part of the constraint register — see [`README.md`](README.md) for how to read an entry, the surfacing statuses, and the debt summary.*

### C-25 — A pack cannot be turned off for a repo where it misfires
- **Cannot tell you:** nothing, directly. What it costs you is the ability
  to *stop* a pack whose edges are wrong for your repo — an Express route
  matched on a receiver that only looks like a router, a `packages` edge to
  a path that is a coincidence.
- **Because:** packs are registered in code and activated by detection
  (ADR-035). There is deliberately no `hobbes.yaml`, so there is no place
  to write "not this one, not here". The alternative — a per-repo registry
  file — collides with ADR-012's "all of `.hobbes/` is personal", and
  inventing that file before anyone had hit this was the speculative
  abstraction the decision avoided.
- **Bites at:** any repo where a framework heuristic guesses wrong. Nothing
  observed yet on the four sanctioned repos, which is the honest reason
  this is a registered cost rather than a solved problem.
- **You find out:** **partial** — `graph.json`'s `packs` list names every
  pack that ran, so a wrong edge is *attributable* to the pass that made
  it. Attributable is not suppressible: you can see which pack to blame and
  you cannot stop it.
- **Candidate fix:** a per-repo disable list. It must live somewhere that
  survives a clone, which makes it the ADR-012 question this milestone
  deferred rather than answered — a pack set is a property of the repo, and
  ADR-012 says the repo's `.hobbes/` is not.
- **Source:** ADR-035, V2.M4.

---

## Lifted constraints in this segment

A lift is a technique, and the technique — not the celebration — is what
these entries document. Each keeps its number, states the limit as it
stood, the exact mechanism that lifted it, and the **residual edge
cases**: inputs the technique does not classify, where the old concession
quietly survives. When a residual case turns out to bite, it becomes a
new active entry and the two cross-reference. Field key: `README.md`,
"How to read a lifted entry".

### C-78 — The `http-go` pack fired on any call named `Handle` or `HandleFunc` — *lifted 2026-09-03*
- **Was:** the pack's `_run` walked every Go file's call sites for a
  *name* in `{Handle, HandleFunc}` and checked neither the receiver,
  nor whether the file imports `net/http`, nor whether the site is a
  type conversion — ADR-037's `_is_conversion` filter was lane A's call
  path's, not the pack's. quic-go (2026-09-02): `windows.Handle(fd)` —
  a conversion to `golang.org/x/sys/windows.Handle` in files that
  import no `net/http` — produced four `http-go extraction degraded … a
  net/http route registration whose pattern is computed (C-5)`
  records. No route was invented (the 57 in `interfaces.json` were
  real); the honesty record was what was wrong, and it presented as a
  decline, not a misfire — *unsurfaced*, and C-25 says a misfiring
  pack cannot be turned off.
- **Lifted by — the technique:** `_is_registration`, three refusals
  read from the lane's own facts before a name match counts: the file
  must import `net/http` (under any alias); a receiver that is
  *another* import's alias is that package's `Handle`, not a route;
  and a receiver-less `Handle(x)` whose name is a type declared in the
  file's package is a conversion (ADR-037's filter, in the pack's
  shape). A local or expression receiver (`mux.Handle`,
  `s.mux.Handle`) still passes on the strength of the file-level
  import. Test: `test_http_go_ignores_a_handle_from_another_package`
  (quic-go's shape plus a same-package `type Handle`, beside a real
  `mux.Handle` in the same file).
- **Residual edge cases:** a file that imports `net/http` *and* a
  package whose `Handle` method it calls through a local
  (`h := windows.Handle(fd); h.Handle(..)` is not Go, but a local of a
  type with a `Handle` method is) would still match — the lane does
  not type locals, and the C-5 record it would produce is a decline
  about a literal-less call, as before. A dot-import of `net/http`
  leaves the receiver empty and the name is then judged against the
  package's types only.
- **Source:** the four-repo extraction test of 2026-09-02 (agent C);
  lifted 2026-09-03.

### C-14 — CLI entry points came from `pyproject.toml` only — *lifted 2026-08-16*
- **Was:** `interfaces.json` read `[project.scripts]` and nothing else,
  so a JS package's `bin` entries and every Go binary were absent — this
  repo's own four binaries (`hobbes-policy`, `hobbes-proxy`,
  `hobbes-session`, `hobbes-web`) missing while two Python console
  scripts were listed, an inventory that read as complete and was not.
  The register ranked it #2 worst ("an empty CLI list reads as 'no
  CLI'").
- **Lifted by — the technique:** three packs on the ADR-035 registry, one
  per remaining language, each reading **declared build targets** from
  the ecosystem's own manifest convention. `cli-ts` reads `package.json`
  `bin` (string and map forms, every manifest, `node_modules` pruned);
  `cli-go` reads the lane's own facts — a file in `package main`
  declaring `func main`, named after its directory, the `go build` rule;
  `cli-rust` reads cargo's three binary shapes (`[[bin]]` tables,
  `src/main.rs`, `src/bin/*`). Each pack carries the per-pack
  removability test, and the lift's exit check is this entry's own
  counter-example, pinned in `test_packs.py`: the dogfood repo's four
  binaries must appear.
- **Residual edge cases:** the technique reads *declared* targets, so a
  binary that exists only in build automation — a Makefile target, an npm
  `scripts` alias, a `go build -o` with a renamed output — is still
  invisible. `setup.py` `entry_points` remains outside too, as the
  original entry said: the Python pack still reads `pyproject.toml`
  manifests only.
- **Source:** M6, `future_additions.md`; widened to Go at the 2026-08-15
  register audit; lifted 2026-08-16.
