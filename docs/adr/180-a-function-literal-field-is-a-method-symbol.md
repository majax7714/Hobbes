# ADR-180 — A class field holding a function literal is a method symbol

**Date:** 2026-10-04 · **Status:** accepted (Max, 2026-10-04: 2a route (i), "recommended is approved", then
"good to proceed with 2a"); pre-registered before the build
(`~/.hobbes/bench/ts-floor-2026-10-04/PREREG-180.md`), its held-out cell drawn first
(`~/.hobbes/bench/ts-cells/DRAW-RULE.md`) · **Owner:** Max · **Source:** 2a's measurement
(`~/.hobbes/bench/ts-floor-2026-10-04/RESULTS-2a.md`; zod's cell record, last section).

Narrows **C-9** (TS/JS) and **C-58**'s `below-floor` class for this shape.

## What is missing

A TS/JS class field whose initializer is an arrow function or a function expression — `static create =
(…) => new ZodString(…)`, hono's `notFound = (): … => { … }` — is called like a method, and the tsc key
names it as a call target (kind `property`, at the field's name). Hobbes keeps no symbol for it
(`extractSymbols` takes a class's methods only), so lane B's reference lands on a definition line with no
symbol and the call counts `below-floor`. On the keyed cells at 0.2.118-beta the key's `static→property`
misses are zod 1,274 and hono 93, and none elsewhere. Of these, lane B names the field on the site line at
zod 42 and hono 92. Reading the targets with the AST, zod's 42 and 81 of hono's are fields with a function
literal; hono's other 11 rows are typed fields given a value elsewhere. zod's other 1,232 rows reach the
field through a re-exported alias the index writes nothing at (`z.object(..)`); they stay registered (Max:
route (ii)).

## Decision

1. **The symbol.** A field (a `PropertyDeclaration`, `static` or not) of a top-level named class whose
   initializer is an arrow function or a function expression is a symbol of kind `method`, qualname
   `Class.name`, at its **name's** line (where scip-typescript defines it and the key places it), ending where
   the field ends. Its name must be an identifier or a private identifier (`#name`). A qualname the class
   writes twice (a `static` and an instance field of one name) or that equals another symbol's mints nothing.
2. **Its edges are lane B's.** It is an ordinary target: the join's `starting_at` answers with it, so a
   reference lane B writes to it becomes a `calls` edge at a call site and a `uses` edge elsewhere, at
   `semantic` tier, as for a method. `declQualname` does **not** name it, so lane A's own resolution draws
   nothing to it where lane B is silent (Max, 2026-10-02: syntactic unless clearly semantic; here only the
   index's answer is drawn).
3. **Its body is its scope.** The calls written inside the function literal (its body and its parameters'
   defaults) are filed under the field, as a method's are; they ran under the class only because the field
   was not a symbol (ADR-158 files a field initializer under the class because it runs at construction; a
   function literal's body does not). The field's decorators and a non-function initializer stay the
   class's.
4. Helper `HELPER_VERSION` 9 → 10: `symbols` and `scope` gain values; no field changes.

## Predicted (pre-registered in `PREREG-180.md`)

On the held-out cell and on zod and hono: confirmed rises by about the shape's count, contradicted stays 0,
poison passes; every added symbol is a field at its name's line (read one by one on the held-out cell); no
other symbol moves. Test reach may shrink where a test reached a field's body only by constructing its class,
and grow where a test calls the field; both are counted and read. New `uses` and `implements` edges where
lane B references a field as a value or as an interface member's implementation are counted and read.

## Not done

- **zod's alias route** (1,232 rows): a multi-hop lane A read, `syntactic`, held by one cell (route (ii)).
- A typed field given a value elsewhere (hono 11 rows): its value is not a literal at the field.
- A field of a class that is not a top-level named class.
