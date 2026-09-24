# ADR-150 — A Python moniker one file defines at several lines is no lane B answer

**Date:** 2026-09-24 · **Status:** accepted and **built** (0.2.70-beta, unit `4732`; Max, 2026-09-24:
"proceed with recommended", route a) · **Owner:** Max · **Source:** flask's key (`oracle-grading.md` §10.35): three
`semantic` edges Hobbes drew wrong, `tests/test_helpers.py` 251, 281 and 310, recorded at
0.2.69-beta with the cause unread. Drivers `~/.hobbes/bench/py-multidef/` (`RESULTS.md`).

Registers **C-170** (a provider limit, P9). Draws less; adds nothing.

## The cause

scip-python names a def nested inside a **method** by the class and its own name. Every
function scope between them is dropped from the descriptor:

```python
class T:
    def a(self):
        def index():
            def generate(): …     # t/T#generate().
            return generate()
    def b(self):
        def index():
            def generate(): …     # t/T#generate().  — the same symbol
            return generate()
```

Read in the image on a ten-line fixture: two definition occurrences of `t/T#generate().`
and of `t/T#index().`. A def nested in a **module-level** function keeps its path
(`t/f().inner()`), so the shape is a method's nested defs only.

The helper (`scip/index.mjs` `decode`) keeps a moniker one file defines at several lines at
its **smallest line**, in every language but C++ (ADR-113 §2, `abstainMultiDefined`). That
line is ADR-109's reading of C's `#if` alternatives: one definition written twice. In
Python the lines are often different objects, and every reference to any of them is filed
under the first. flask's three sites name a sibling test method's `generate`/`gen`, and
click's `src/click/core.py:1888`, in `Group.group`'s `decorator`, names `Group.command`'s
`decorator` at 1830: a fourth wrong edge, one of click's 21 suspects.

## Measured

Monikers of graph kinds one file defines at several lines (`classify.py`, the defs'
enclosing chains read with `ast`): flask 9, click 2, attrs 20, this repo @ `2c915a8` 10.
Nearly all of them are a method's same-named nested defs. The rest are names scip-python
places twice in one scope: a class attribute, or a method defined twice in one class body.
**Corrected 2026-09-24, at the unit's review.** The first form of this table counted
parameter monikers, which the helper never keeps. Read that way, it showed `@overload`,
property and same-scope columns. A fixture in the image then showed that scip-python 0.6.6
emits **one** definition for a property's getter and setter, for an `@overload`'s stubs
and for an `if`/`else` def. None of them is a multi-defined moniker, and this rule does
not touch them. The ingest's own record counts 9 on flask and 2 on click.

Graded rows riding on a smallest line: all of them nested defs (flask 2 confirmed, 3
suspect; click 1 confirmed, 1 suspect). The rule as worded, built in a scratch worktree
and graded on the stored keys (flask-py, `click-py-r3`):

| cell | confirmed | suspect | contradicted | poison |
|---|---|---|---|---|
| flask | 1,521 → 1,519 (56.4% → 56.3%) | 18 → 15 | 0 | PASS |
| click | 3,755 → 3,754 (82.3%) | 21 → 20 | 0 | PASS |

The exports differ by exactly seven `semantic` edges removed, none added: the four wrong,
and three right only because their site called the first def. Syntactic confirmed rows are
unchanged, so lane A does not draw the sites back (it has no rule for a bare call to a
nested def). Lane A's symbols carry every one of the defs under its own id, so no node is
lost.

## The decision

**Route a.** Python takes C++'s abstention: a moniker one file defines at more than one
line, of any kind but a namespace, has no definition in the decode, and a reference to it is
recorded as an in-repo external reference (`in_repo: true`), so ADR-111's veto does not
fire on it. The count is surfaced by the `scip-decode` degradation record, **worded for
Python**: it names the nested-def shape and any other name scip-python places twice in one
scope, and cites this ADR and C-170 (corrected at the review; see *Built*). C++'s wording is unchanged, and C keeps
the smallest line.

Routes not taken:
- **b**, abstaining only where the definitions sit in different enclosing scopes and
  keeping the smallest line for the rest: the same graded effect, more machinery. What
  is left is a name placed twice in one scope, where the first definition is not the one
  that runs (a method defined twice binds the second). So the rest is a guess too, and
  refusing it is the reading that fails toward drawing less. *(Corrected 2026-09-24: the
  first form argued from `@overload` stubs and `if`/`else` defs, which scip-python does
  not give several definitions.)*
- **c**, lane A drawing a bare-name call to the one def of that name in the enclosing
  function's own body. It would put back all seven edges, each at its right def: a recall
  rule, to be measured on its own, after this one.

## What it costs

Three confirmed edges on the two keyed cells, each right by the accident of order, and
every other reference to a moniker scip-python shares. Those carry no graded row on the
three Python keys.

## What this leaves

C-170 names what the index cannot say, and what Hobbes now declines to guess. Route c is the
recall that is left. It goes on the extraction candidates, measured first.

## Built (0.2.70-beta, unit `4732`)

As decided. One defect was fixed at the review (`e47b35b`), and it was the brief's: the
degradation record named `@overload` stubs, property setters and conditional defs. It now
names only the nested-def shape and "any other name it places twice in one scope". Host:
`lane_b` 17 of 17, pytest 2,402, scip node 97. flask 1,521 → 1,519 confirmed and 18 → 15
suspect; click 3,755 → 3,754 and 21 → 20; 0 contradicted and poison PASS on both. flask's
export is identical to the probe's (`oracle-grading.md` §10.36).
