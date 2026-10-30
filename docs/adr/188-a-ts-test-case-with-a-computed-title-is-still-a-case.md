# ADR-188 — A TS/JS test case with a computed title is still a case, named by its title's source

**Date:** 2026-10-30 · **Status:** accepted (Max, 2026-10-30: "for the gap recommended approach is good",
route (a) of two) · **Owner:** Max · **Source:** `currently-open.md` (found writing `merman`'s tests, PR #10).

## Context

`tsextract/extract.mjs` inventories a TS/JS case from an `it(…)` or `test(…)` call, naming it by its first
argument when that is a string literal (`'…'`, `"…"` or a template with no `${…}`). Any other title, a
template with a substitution, a variable or a call, made `extractTests` return before recording the case:
the case was not a test, so its reach reached no module, `tests_guarding` never named it, and the review
never counted it. Nothing said so. No `C-n` named it, so it was precedent 1. `describeChain` did the same to a
`describe(…)` with a computed title: it left that level out of the case's name, again silently.

Measured on this repo: about 8 of some 1,335 TS/JS cases have a computed title, 7 of them in the TUI's own
tests (`form.test.tsx`, `tool-display.test.ts`, …); `merman`'s one was unrolled.

## Decision

1. **The case is kept.** An `it`/`test` call whose first argument is not a string literal is a case all the
   same, with its extent, so its reach is computed like any other's. A call with no argument is still not
   a case.
2. **It is named by its title's source text**, as written (`` `draws ${kind}` ``, `name`), and a `describe`
   level with a computed title enters the name the same way. The case carries `computed_title: true`.
3. **It is counted where a user meets it.** One `ts-test-titles` degradation record per ingest gives the
   number of such cases and examples, so `list_blind_spots` and the ingest summary say it.
4. **The residual is registered (C-199).** A source-text name is not the name the runner prints. A loop
   that makes several cases from one call (`for … test(\`…${x}\`)`) is one case in the inventory, its reach
   the union of theirs. Anything that matches a runner's results by name (a harness reading a JSON report)
   cannot match these cases.

## Consequences

- Reach that a computed-title case had was never counted; it now is, so a module reached only by such a case
  may now be guarded. That changes what the layer draws (the test inventory and its reach): a patch.
- The record and C-199 make the naming limit visible instead of the drop.
