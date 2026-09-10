# ADR-104 — A member call on a union-typed receiver: lane A abstains, lane B's pick is vetoed, the site is a tail class

**Date:** 2026-09-09 · **Status:** accepted — built, tested, ajv and hono regraded · **Owner:** Max · **Source:** the oracle lane's `static→union-member` shape (ajv 3 rows, 2026-08-28 triage; hono 7 rows, 2026-09-09 1-1), measured before the fix on both clones

Amends the architecture's **§3.1** (a TS/JS rule) and **§3.4** (a tail
class), ADR-045 (the class list). Registers **C-97** and **C-98**
(`docs/constraints/extraction-typescript-javascript.md`); amends C-58's
entry (the TypeScript face). Bumps the layer to **0.1.4-beta**
(ADR-103: a change in what Hobbes draws).

## Context

`n.render()` with `n: A | B`, both classes overriding `render`. The
semantic lane (scip-typescript) puts its occurrence on the **first**
member's declaration, `A.render`, at full certainty; lane A's own
resolver (`resolveExpressionTarget` in the TS helper) takes the first
in-repo declaration of the property symbol — the same pick — so the
lane-agreement check cannot see it. `tsc`'s resolved signature names a
declaration too: on a two-member union the first member's, on ajv's
eleven-member `ChildNode` the shared base's. The oracle lane graded the
eleven-member calls *contradicted* (3 rows) and the two-member calls
*confirmed* (6 rows) — an agreement of two arbitrary picks, not a
truth, which the fixture confirmed on 2026-09-09: a copy of `minits`
with the union case graded 7/7 before any change. hono added seven
rows of the same shape (`c.toString()` on its `Child` union drawn to
`JSXNode.toString` where the compiler says the built-in).

Measured before deciding (the session's `union_sites.cjs`, ts-morph over
the two zones, joined against the grading rows): every member call on a
union receiver, null and undefined stripped —

| repo | union-receiver call sites | with a Hobbes edge to the member | contradicted | confirmed |
|---|---|---|---|---|
| ajv | 15 | 9 | 3 | 6 |
| hono | 36 | 7 | 7 | 0 |

All ten contradictions are in the set; nothing outside it is wrong.
What separates the confirmed six from the contradicted three is only
which declaration `tsc` happened to name, so the rule cannot be "match
`tsc`" without adopting its pick.

## Decision

1. **The helper types the receiver and abstains.** For every call whose
   callee is a property access, the TS helper (facts **v5**) reads the
   receiver's type; when it is a union of two or more non-nullish
   members whose declarations of the accessed member are not one
   declaration, the `calls` record carries `ambiguous: "union-member"`
   and `callee`, `callee_path` and `origin` are null. `T | undefined` is
   one member and not the shape; a union whose members inherit one base
   method resolves as before (one declaration); a literal union of
   primitives shares the lib's declaration and resolves as before.
2. **The join vetoes lane B at that site.** `evidence.join` draws no
   edge for an ambiguous site from either lane and claims lane B's
   occurrence there so it does not resurface as a `uses` reference;
   `agreement` does not compare it; `coverage` counts it **unresolved**.
3. **The tail names it.** A new class **`union-member`**, TS/JS only in
   `CLASSES_AVAILABLE`, in the *cannot resolve* group beside
   `attr-call` and `expr-callee` (not `NOT_MODELLED`: the union's members
   are the reader's to enumerate). The proxy's glossary carries it.
4. **Not taken: matching `tsc`'s pick.** Having lane A take the
   compiler's resolved-signature declaration and override lane B would
   reach 100% against the oracle by adopting the same arbitrary choice
   the oracle makes — a possible dispatch target presented as the
   resolved one, which is the tier violation the triage named. The
   oracle's grain at union sites is recorded as a pick, not a truth
   (`docs/oracle/oracle-misses.md`).
5. **Not taken: drawing every member.** The static meaning of the call
   is "one of these"; drawing all members is C-58's interface-dispatch
   question, which Hobbes does not answer for any language.

## Consequences

- **ajv 1,375/1,378 → 1,410/1,410 (100.0%), contained; recall 62.0% →
  63.5%** on Hobbes 0.1.4-beta (every lift since the 2026-08-27 cell is
  in the regrade). Ten `union-member` sites in the tail, the six
  previously-confirmed two-member picks among them — by design.
- **hono 767/774 → 767/768 (99.9%)**; one row remains where lane A's
  checker could not type the receiver at all. Its cause is a second
  gap, **C-98**: the helper's zone project loads a *solution-style*
  `tsconfig.json` (`files: []` + `references`) as the zone's compiler
  options — no options, ES5 defaults — so `Array.flat` is unknown and
  the receiver is `any`. Lane B already follows references (C-90); the
  lane-A analogue is the next lift and is not in this ADR.
- The fixture `pipeline/tests/fixtures/minits/src/union.ts` holds the
  three cases (override / inherit / inside a class with its own
  override); with lane B on it draws `label → Base.tag` and nothing for
  `draw` or `Holder.render`, tail `union-member 2`, lane disagreements
  0, and grades 5/5 with the two abstained sites as misses.
- `tail_classes_available` for TS/JS gains the class; C-32's "cannot
  report" line for every other language names it. Rebuild the image
  (C-65).
- The claim page's exceptions go from three to two: hono (one row,
  C-98) and quic-go. *C-98 lifted 2026-09-10 (0.1.5-beta): the helper
  types a file under a solution config by the referenced project that
  includes it; hono 768/768, the exception quic-go alone.*

## Tests

`tsextract/test/extract.test.mjs` (the five cases above), `test_evidence.py`
(the veto, the claim, the disposition, the agreement skip),
`test_tail.py` (the class, its availability and decision order, the
C-32 line), `test_tssource.py` (the fixture end to end),
`knowledge_test.go` (the gloss, the rollup, the C-32 line).
