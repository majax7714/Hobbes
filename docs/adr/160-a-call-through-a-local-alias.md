# ADR-160 — A call through a local alias is drawn to what the alias's right-hand side names

**Date:** 2026-10-02 · **Status:** accepted (Max, 2026-10-02: "good to move with recommended, syntatic over
semantic when not clearly semantic to preserve honesty"); to be built after the held-out pyparsing cell is
graded at 0.2.83-beta · **Owner:** Max · **Source:** the C-9 step 0, `~/.hobbes/bench/c9-local-alias/`
(`RESULTS.md`, `probe.py`, `count.py`, `run.sh`, `before/`, `probe/`); the held-out pre-registration
`~/.hobbes/bench/heldout-pyparsing/PREREG.md`.

Narrows **C-9** (the call side of a local binding). Draws more, at the `syntactic` tier.

## What is missing

A function that binds a local name to a global, or to an attribute, and then calls the local draws no edge:

```python
def _get_pulse_segments(self, …):
    _Segment = Segment                                   # uses rich.segment.Segment (semantic)
    …
    append(_Segment(bar, _Style(color=from_triplet(color))))   # no edge; tail `local-binding`
```

Lane B names `Segment` at the alias line and draws `uses` to the class. At the call it names the local
variable, which is below the symbol floor (C-9), so the join draws nothing and the tail calls the site
`local-binding`. Until 0.2.84-beta the tail's gloss also said such a call "stays inside that file"; that was
corrected first (C-32, precedent 1).

## Measured (step 0, no code changed)

Read exactly with `ast` (the rule's binding conditions below), the right-hand side resolved by the graph's
own edge at the alias line, then simulated by adding one edge per site to the HEAD export and grading it with
the HEAD oracle:

| cell | sites the rule draws | RHS outside the repo or unresolved | refused (bound twice) |
|---|---:|---:|---:|
| rich | 155 | 158 (`parts.append`, …) | 16 |
| flask | 0 | 0 | 2 |
| click | 0 | 6 | 5 |

- rich: 4,844 → 4,979 confirmed (+135), recall 90.20% → 92.72%, 0 contradicted, poison PASS; 2 unobserved.
- **The 18 new suspects are one shape:** `get_style = theme.get_style_for_token` with `theme` declared
  `SyntaxTheme`, the trace seeing a subclass's override. The direct `theme.get_style_for_token(…)` draws the
  same declared-target edge and reads suspect at HEAD (5 rows). The alias carries the direct call's
  convention (C-58); it adds no new kind of wrong edge.
- The cell record's bucket (rich 121, flask 12, click 24) was a regex over the site's line. Read exactly,
  the shape is rich's alone among the keyed cells; across 20 other Python trees the bare-name idiom is rare
  (0–17 sites each).

**rich is fitted for this ADR.** Every measured row is rich's, and rich was the held-out cell, so the next
held-out cell, pyparsing 3.3.3, was picked, pre-registered and graded at 0.2.83-beta before this rule is
built (Max's route 1). Its predictions A1–A6 score the rule as built.

## The decision

1. **The scope's fact (in `pysource`, which owns the grammar).** For each function definition F, the names
   F's own scope binds **exactly once, by a plain assignment `N = R`**: one target, the identifier N; R an
   identifier or an attribute chain of identifiers (`Segment`, `self.render`, `theme.get_style_for_token`),
   whose root is not N. Written in F's own body, at its top level or inside an `if`, `try`, loop or `with`,
   never inside a nested def, class or lambda. Recorded per definition with its lines, as ADR-153's
   `local_defs` are: `(N, the assignment's line, R's last name)`. A name is left out on every refusal
   ADR-153 step 1 lists, read for this binder:
   - a second binding of N of any form in F's own body — another assignment (a chained `N = M = R` too),
     augmented or annotated assignment, walrus, `for`/`with`/`except` target, import, `del`, a `def` or
     `class` of N;
   - a parameter of F, of any kind;
   - a `global` or `nonlocal` naming N anywhere under F;
   - a lambda parameter or comprehension `for` target named N in F's own scope;
   - and F is refused whole where its own body holds a `match` or a `type` alias statement.

   A name N is also left out where the file writes F's qualname more than once and the definitions disagree
   (ADR-153's correction), so the call's line names the definition.
2. **The site.** A call whose callee is the bare name N, whose lane A scope is F, on a line inside the
   definition that binds N. A call in a nested def or a class body inside F has another scope and is not
   this rule's. A call inside a lambda or a comprehension in F is F's (lane A's scope is the innermost
   *definition*); step 1 already refuses N wherever either one binds it.
3. **The target, read off the settled graph** (as ADR-156 reads a `with` item's class): F's `semantic`
   edges with an evidence row at (F's file, the assignment's line) whose target's last name is R's last
   name. Exactly one target T, and T is drawn. None — R names something outside the repo, below the floor,
   or the index is silent — and the site abstains `no-rhs-edge`. More than one, and it abstains
   `ambiguous-rhs`. Nothing here infers a type: T is lane B's answer at R.
4. **The edge.** `calls` from F to T, **`syntactic`** (Max: the binding is read from syntax; only the
   right-hand side is the index's), evidence at each site `{path, line, via: "alias"}`. A pair the graph
   already carries a `calls` edge for is left alone and counted `already-drawn`. The counts go to
   `graph["aliases"]` (`aliases`, `sites`, `drawn`, `abstained` by reason), absent where no file binds an
   alias that is called.
5. **Without lane B there is no `semantic` edge at R, so nothing is drawn** (P6).
6. **Not guarded, on purpose** (ADR-153 step 5). A call before the assignment, or after a branch that did not
   run it, raises `UnboundLocalError`; with one binding there is nothing else the name can hold. A binding
   inside a loop holds R's value at that pass, which is what the direct call `R(…)` at that line would reach,
   and lane B's answer at R is the same one either way.

## Not taken

- **`semantic`** (Max, 2026-10-02): the index never names the call's target at the call.
- **Calls from a nested def or lambda** where N is free: rich 1 site; the scope chain is more machinery.
- **Module-level aliases** (`X = Y` at module level, called from functions): rich's 11 are all
  `windll.kernel32.*`, outside the repo; a module-level name can also be rebound from outside the module.
- **Class-level aliases** (`_parse = _parseNoCache`): a call through one is an attribute call, the index's.
- **Moving resolution coverage.** As ADR-145, ADR-147 and ADR-156: the join did not resolve the site, so the
  tail still counts it `local-binding` and the percentage stays a floor; the gloss now says what such a
  binding may hold.

## What it costs

A post-pass beside `withstmt`, before the test map, so test reach follows the new edges. On rich, about 155
more `calls` edges. A wrong right-hand-side answer would now be drawn twice (the `uses` at the alias and the
`calls` at each site); that is the index's error, carried, and the tier says so.

## What this leaves

C-9 keeps every other local binding: a parameter holding a callable, a value a call returned, a multiply
bound name, and the aliases above. Other languages are not read (TS/JS has its checker's own `local-binding`
proof; Go and Java were not measured).
