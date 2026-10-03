# ADR-170 — `cls(…)` in a classmethod calls its own class, drawn `syntactic`

**Date:** 2026-10-03 · **Status:** accepted (Max, 2026-10-03: "good to write the adr and continue") and
**built** (0.2.99-beta) · **Owner:** Max · **Source:** step 0 (`~/.hobbes/bench/cls-classmethod/step0.py`,
fitted cells only); the held-out icalendar pre-registration (`~/.hobbes/bench/heldout-icalendar/PREREG.md`,
C1–C5, wording frozen before the ingest and the key).

Narrows C-9 (a call through a name below the symbol floor). Draws a new kind of edge.

## What is wrong

A classmethod that constructs its own class writes `cls(…)`:

    @classmethod
    def from_ical(cls, ical):
        return cls(parse(ical))

The index names the parameter `cls` at the call, a local below the symbol floor (C-9), so the join has nothing
to draw and the tail counts the site `local-binding`. The trace sees a construction of the class. On the
fitted cells: rich 58 such sites (55 confirmed by the key at the own class), flask 2, click 0. On the held-out
icalendar cell `cls(…)` sites hold 90 of the 385 `observed→class` misses (§10.46, H7).

## The decision

1. **Lane A records each classmethod's span** (`pysource`): a `def` written directly in a class body whose
   decorators include the bare name `classmethod`, with the class's qualname and the def's first and last
   lines. A classmethod whose body rebinds `cls` (`cls = …`, `for cls in …`, `with … as cls`) is not recorded.
2. **After the join** (as ADR-160's aliases, `clscalls.cls_calls`): a call whose callee is the bare name
   `cls`, whose scope is a recorded classmethod and whose line lies in its span, draws `calls` from the
   classmethod to its class, evidenced `via: "cls"`, at the **`syntactic`** tier (lane B names a parameter;
   the class is read from where the `def` is written — Max, 2026-10-02: syntactic unless clearly semantic).
   A pair the graph already carries a `calls` edge for is left alone; a class the graph keeps no symbol for
   draws nothing.
3. **Only the method's own body.** A `cls(…)` inside a function nested in the classmethod has the nested
   function as its scope and is not drawn (a closure, C-58).
4. **The own class, not a subclass.** A classmethod called through a subclass constructs the subclass; the
   edge names the class the `def` is written in, which is the declared target, as every call through a base
   is (C-60's convention). Resolution coverage is not moved: the join did not resolve the site.
5. `graph["cls_calls"]` counts the classmethods, sites, edges drawn and abstentions, where any is recorded.

## Predicted (step 0 and the pre-registration)

rich +55 confirmed, +2 suspect, 0 contradicted; flask +1, +1; click unchanged (C5). icalendar C1–C4: at most
81 edges; at least half of the executed sites confirmed at the own class; 0 Hobbes-wrong; subclass-only sites
at most 15% of executed sites.

## Alternatives considered

- **`semantic`, because lane B resolved nothing contrary.** The class is the source's position, not the
  index's answer; Max's 2026-10-02 rule makes it `syntactic`.
- **Draw every subclass too.** The dispatch question (C-58); not here.
- **Include nested closures.** A closure can outlive the classmethod and be called with another `cls`
  bound; C-58's shape.

## Built (0.2.99-beta)

`extract/pysource.py` (`ParsedFile.classmethods`, `_classmethods`, `_rebinds_cls`), `extract/clscalls.py`,
`extract/__init__.py` (after the aliases; `_add_alias_call_edges(…, via=)`). Tests: `test_clscalls.py` on the
`minicls` fixture (rich's `rich/control.py` shape; a rebound `cls`, a closure, a staticmethod).

**Regrade** (`~/.hobbes/bench/cls-classmethod/run.sh`, `after/`; stored keys, poison on, all PASS):

| cell | confirmed | suspect | unobserved | recall | sites drawn |
|---|---|---|---|---|---:|
| icalendar (held out) | 3,477 → **3,553** | 16 → 16 | 54 → 58 | 68.7% → **70.2%** | 81 |
| rich | 4,968 → **5,019** | 42 → 44 | 1,133 → 1,134 | 92.5% → **93.5%** | 58 |
| flask | 1,552 → 1,553 | 15 → 16 | – | 55.6% → 55.7% | 2 |
| click | 3,768 → 3,768 | 20 → 20 | – | 82.0% | 0 |
| pyparsing | 3,517 → 3,529 | 66 → 68 | 1,972 → 1,975 | 50.6% → 50.8% | 17 |

**The pre-registration, scored.** C1 met (81 sites drawn, ≤ 81). C2 met (76 of the 77 executed lines confirmed).
C3 met (no new suspect on icalendar: 0 Hobbes-wrong). C4 met (0 subclass-only sites; the 6 sites the trace
saw at a subclass too it also saw at the own class). **C5 missed by one row on rich:** +51 confirmed against
+55 ± 3. Step 0 counted call sites; the grader keeps one row per line and target, and four of rich's lines hold
two `cls(…)` calls. Counted by line, step 0 read +51 confirmed, +2 suspect, 1 unexecuted — what the build reads
exactly. flask (+1, +1) and click met. rich's and flask's new suspects are the step-0 subclass-only sites
(`PromptBase.ask`, `MarkdownElement.create`; flask's one), the declared-target convention.
