# ADR-111 — Lane A's fallback is vetoed where lane B resolved the site outside the repo

**Date:** 2026-09-12 · **Status:** accepted and built (0.2.8-beta). Max approved the proposal when he closed the C-oracle session, and this is its design, written before the dispatch that builds it. The dispatch was `S-20260912T221854Z-42d1`. The acceptance regrade passed, with one term Max accepted: sqlite-vector lost 4 syntactic edges, not 3 (the Record below). · **Owner:** Max · **Source:** C-138, found by O9's random draw (`docs/oracle/cells/sqlite-vector-c-2026-09-12.md`)

This amends the architecture's **§3.4** (the join's table). It narrows
**C-138** (`docs/constraints/extraction-c.md`), and follows ADR-104's
shape. ADR-104 vetoes lane B at a site lane A saw is ambiguous; this ADR
vetoes lane A at a site lane B resolved outside the repo.

## Context

`evidence.join` takes lane A's fallback wherever lane B produced no
*in-repo* resolution at the site (ADR-029's table). It never asks
whether lane B resolved the site to a declaration outside the repo.
Those references are collected at ingest (`external_refs`), and only the
coverage walk (`_dispositions`) reads them.

- **sqliteai/sqlite-vector** defines its own `strcasestr` in an `#if`
  for Windows, musl and WebAssembly. On glibc Linux that arm is dead, and
  the calls are libc's.
- **Lane A reads both arms** (C-131), so its rank-1 fallback names the
  shim.
- **Lane B resolved each call to libc's declaration.** The join did not
  consult it, and drew three `syntactic` edges, all contradicted by
  clang: the cell's only wrong edges.
- **`hobbes lanes` could not see it.** It compares only sites both lanes
  resolved in the repo.

**The helper's "external" is wider than "outside the repo."** `scip/index.mjs`
sends a reference to `external` whenever its moniker has no
*graph-kind* definition in this index. Two kinds of in-repo moniker land
there too:

- a moniker defined in more than one in-repo file, which the helper drops
  from the definitions map as ambiguous (C-28): C file-statics of one
  signature, cargo targets' `crate/` and `main().`, a Go package's
  namespace;
- a moniker whose in-repo definition is a kind the graph does not keep.

`join_cross_unit` adds a third: a moniker two sibling units define keeps
its references external. A veto keyed on every external reference would
remove lane A's fallback at exactly the sites where lane A is the useful
lane.

## Decision

1. **The join takes the external references and vetoes lane A's
   fallback at their sites.** `evidence.join(syntax, semantic, fallback,
   external=None)`. A call or import site with no in-repo resolution,
   whose `(file, line, name)` carries an external reference that is
   outside the repo, draws **no edge**. Lane A's guess there is dropped.
   The key is ADR-104's and the coverage walk's: file, line and name. A
   site lane B resolved in the repo is untouched, and so is a site with
   no external reference: the fallback applies there as before.
2. **Only a reference outside the repo vetoes.**
   - The helper marks an external reference `in_repo: true` when its
     moniker has a definition occurrence in any in-repo document of the
     index, whatever its kind and however many files define it.
   - `join_cross_unit` marks a reference it leaves external because
     sibling units define its moniker ambiguously.
   - A marked reference never vetoes.
3. **Coverage is unchanged.** A vetoed site's fate is `external`, as it
   already was: `_dispositions` counts every site with an external
   reference as `external`, and that is where the site belongs, since
   lane B resolved it outside the repo. The tail classifies only
   unresolved sites, so nothing new enters it.
   - Max's sketch put the site "in the tail as external-origin". The
     coverage row's `external` column is that meaning, already counted.
   - Whether an `in_repo` reference should still count the site
     `external` is C-28's accounting. It is unchanged here and named, not
     moved.
4. **The lanes' self-test counts the vetoes.** `graph["lane_agreement"]`
   gains `external_vetoes`: the number of sites, and up to ten examples
   (the site, and lane A's guess). A veto is not a disagreement, because
   the graph already took lane B's answer, so `hobbes lanes` prints the
   count and its exit status does not change. This is where a user meets
   the sites lane A would have drawn wrong.
5. **Every language takes the rule.** The join is shared, so every
   language takes it with no per-language switch.
   - **Tested per language** with each lane's own external-reference
     form.
   - **Tested end to end on C's shape** in `minic`: a libc function's
     shim in a dead `#if` arm, called where lane B resolves libc's
     declaration.

## Acceptance (before the merge, Max's gate)

- **The regrade.** Every oracle cell with a stored key is re-ingested
  under the new join, exported and graded against its **stored** key; no
  oracle is re-run. At the minimum, that is every contained cell.
- **sqlite-vector** goes from 851/854 to **851/851**, with exactly 3
  fewer syntactic edges.
- **Every other cell keeps its confirmed count.** A lost confirmed edge
  stops the merge.
- **Where the regrade is recorded.** Each cell record takes a signed
  direction-of-fix line (oracle-grading §11), and each report takes the
  vetoes' count.

## Consequences

- **Register.** C-138 is narrowed to its residuals:
  - two same-named occurrences on one line, one outside the repo and one
    the call lane B missed (the key has no column);
  - a sibling unit's in-repo definition of a kind the graph does not
    keep, which `join_cross_unit` cannot mark.
- **Version:** a patch (ADR-103: a change in what Hobbes draws).
- **Not changed:**
  - lane A's own rules (C-131's dead arms are still read);
  - ADR-104's veto;
  - the tail's classes.
